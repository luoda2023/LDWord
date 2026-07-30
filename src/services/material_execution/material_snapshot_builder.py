"""Service boundary that freezes one mutable material profile into a verified snapshot.

This module is the filesystem-facing boundary of the Freeze phase.  It does
not inspect the target DOCX, resolve tokens or anchors, or transform image
pixels.  It only verifies already-declared source facts and then delegates the
immutable/canonical representation to :class:`MaterialSnapshot`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from hashlib import sha256
import math
import mimetypes
from pathlib import Path
import warnings

from PIL import Image, UnidentifiedImageError

from src.config.attachment_materials import AttachmentBinding, AttachmentItem
from src.config.content_artifacts import ContentMaterialBinding
from src.config.content_materials import (
    ContentInsertionRule,
    FileAssetRef,
)
from src.config.library import CONFIG_LIBRARY_ROOT
from src.config.entity import EntityProfile
from src.config.image_materials import (
    FrozenImageMaterialRule,
    ImageCardinality,
    ImageSourceBinding,
)
from src.config.materials import IMAGE_EXTENSIONS
from src.config.material_snapshot import MaterialSnapshot
from src.services.material_content.artifact_repository import (
    ContentArtifactRepository,
    ContentArtifactRepositoryError,
)
from src.shared.engine.material_token_contract import (
    FrozenMaterialTokenEvidence,
    MaterialTokenKind,
    MaterialTokenNamespace,
    MaterialTokenProducer,
    material_token_key,
    parse_material_token,
)
from src.shared.engine.material_timeline import timeline_owned_field_keys


_MARKDOWN_EXTENSIONS = frozenset({".md", ".markdown"})
_MARKDOWN_MEDIA_TYPES = frozenset(
    {"text/markdown", "text/plain", "text/x-markdown"}
)
_IMAGE_MEDIA_TYPES_BY_EXTENSION: Mapping[str, frozenset[str]] = {
    ".bmp": frozenset({"image/bmp", "image/x-ms-bmp"}),
    ".jpeg": frozenset({"image/jpeg"}),
    ".jpg": frozenset({"image/jpeg"}),
    ".png": frozenset({"image/png"}),
    ".tif": frozenset({"image/tiff"}),
    ".tiff": frozenset({"image/tiff"}),
    ".webp": frozenset({"image/webp"}),
}


@dataclass(frozen=True, slots=True)
class MaterialSnapshotBuildDiagnostic:
    """One blocking, deterministic Freeze diagnostic."""

    code: str
    domain: str
    message: str
    path: str = ""

    def __post_init__(self) -> None:
        for name in ("code", "domain", "message"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be empty")
        if not isinstance(self.path, str):
            raise TypeError("path must be a string")


class MaterialSnapshotBuildError(ValueError):
    """Raised when a caller explicitly requires a successful snapshot."""

    def __init__(
        self,
        diagnostics: Sequence[MaterialSnapshotBuildDiagnostic],
    ) -> None:
        self.diagnostics = tuple(diagnostics)
        if not self.diagnostics:
            raise ValueError("MaterialSnapshotBuildError requires diagnostics")
        if any(
            not isinstance(item, MaterialSnapshotBuildDiagnostic)
            for item in self.diagnostics
        ):
            raise TypeError(
                "diagnostics must contain MaterialSnapshotBuildDiagnostic values"
            )
        summary = "; ".join(
            f"{item.code} ({item.path or item.domain}): {item.message}"
            for item in self.diagnostics
        )
        super().__init__(f"material snapshot Freeze failed: {summary}")


@dataclass(frozen=True, slots=True)
class MaterialSnapshotBuildRequest:
    """Fully resolved inputs accepted by the Freeze boundary.

    ``frozen_field_values`` must already include field-function and timeline
    results.  The builder deliberately never consults ``profile.fields`` or
    recomputes those values.  Image policy and source selection must already
    have crossed ``ImagePolicyFreezer``; target-DOCX plans do not belong here.
    """

    profile: EntityProfile
    frozen_field_values: Mapping[str, object]
    material_schema_id: str
    material_schema_version: str
    rule_versions: Mapping[str, str]
    frozen_image_rules: tuple[FrozenImageMaterialRule, ...] = ()
    image_source_bindings: tuple[ImageSourceBinding, ...] = ()
    source_root: str | Path | None = None
    content_artifact_root: str | Path | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.profile, EntityProfile):
            raise TypeError("profile must be an EntityProfile")
        if not isinstance(self.frozen_field_values, Mapping):
            raise TypeError("frozen_field_values must be a mapping")
        if not isinstance(self.rule_versions, Mapping):
            raise TypeError("rule_versions must be a mapping")
        for name, expected_type in (
            ("frozen_image_rules", FrozenImageMaterialRule),
            ("image_source_bindings", ImageSourceBinding),
        ):
            values = getattr(self, name) or ()
            if not isinstance(values, Sequence) or isinstance(
                values, (str, bytes, bytearray)
            ):
                raise TypeError(f"{name} must be a sequence")
            values = tuple(values)
            if any(not isinstance(item, expected_type) for item in values):
                raise TypeError(
                    f"{name} must contain only {expected_type.__name__} values"
                )
            object.__setattr__(self, name, values)
        if self.source_root is not None and not isinstance(
            self.source_root, (str, Path)
        ):
            raise TypeError("source_root must be a path when provided")
        if self.content_artifact_root is not None and not isinstance(
            self.content_artifact_root, (str, Path)
        ):
            raise TypeError("content_artifact_root must be a path when provided")


@dataclass(frozen=True, slots=True)
class MaterialSnapshotBuildResult:
    """Atomic Freeze result; diagnostics and a snapshot never coexist."""

    snapshot: MaterialSnapshot | None
    diagnostics: tuple[MaterialSnapshotBuildDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        diagnostics = tuple(self.diagnostics or ())
        if self.snapshot is not None and not isinstance(
            self.snapshot, MaterialSnapshot
        ):
            raise TypeError("snapshot must be a MaterialSnapshot when provided")
        if any(
            not isinstance(item, MaterialSnapshotBuildDiagnostic)
            for item in diagnostics
        ):
            raise TypeError(
                "diagnostics must contain MaterialSnapshotBuildDiagnostic values"
            )
        object.__setattr__(self, "diagnostics", diagnostics)
        if self.snapshot is not None and diagnostics:
            raise ValueError("a diagnostic result cannot retain a partial snapshot")
        if self.snapshot is None and not diagnostics:
            raise ValueError("a failed result must contain diagnostics")

    @property
    def ok(self) -> bool:
        return self.snapshot is not None

    @property
    def error(self) -> MaterialSnapshotBuildError | None:
        return (
            None
            if not self.diagnostics
            else MaterialSnapshotBuildError(self.diagnostics)
        )

    def require_snapshot(self) -> MaterialSnapshot:
        if self.snapshot is None:
            raise MaterialSnapshotBuildError(self.diagnostics)
        return self.snapshot


@dataclass(slots=True)
class _DiagnosticCollector:
    items: list[MaterialSnapshotBuildDiagnostic] = field(default_factory=list)

    def add(
        self,
        code: str,
        domain: str,
        message: str,
        path: str = "",
    ) -> None:
        self.items.append(
            MaterialSnapshotBuildDiagnostic(
                code=code,
                domain=domain,
                message=message,
                path=path,
            )
        )


class MaterialSnapshotBuilder:
    """Validate all four material domains and atomically create a snapshot."""

    def build(
        self,
        request: MaterialSnapshotBuildRequest,
    ) -> MaterialSnapshotBuildResult:
        if not isinstance(request, MaterialSnapshotBuildRequest):
            raise TypeError("request must be a MaterialSnapshotBuildRequest")

        diagnostics = _DiagnosticCollector()
        source_root = _validated_source_root(request.source_root, diagnostics)
        _validate_snapshot_metadata(request, diagnostics)
        _validate_plain_value(
            request.frozen_field_values,
            path="field_values",
            domain="field",
            diagnostics=diagnostics,
            active=set(),
        )
        field_token_bindings = _freeze_field_token_bindings(
            request.frozen_field_values,
            request.profile.field_aliases,
            timeline_owned_field_keys(
                request.profile.timeline_plans,
                include_inactive=True,
            ),
            diagnostics=diagnostics,
        )

        content_bindings, content_rules, content_revisions = _freeze_content_domain(
            request.profile,
            repository=ContentArtifactRepository(
                request.content_artifact_root
                or (CONFIG_LIBRARY_ROOT / "content_artifacts")
            ),
            diagnostics=diagnostics,
        )
        attachment_bindings, attachment_revisions = _freeze_attachment_domain(
            request.profile,
            source_root=source_root,
            diagnostics=diagnostics,
        )
        frozen_image_rules, image_sources, image_revisions = _freeze_image_domain(
            request.frozen_image_rules,
            request.image_source_bindings,
            source_root=source_root,
            diagnostics=diagnostics,
        )

        if diagnostics.items:
            return MaterialSnapshotBuildResult(
                snapshot=None,
                diagnostics=tuple(diagnostics.items),
            )

        source_revisions = {
            **content_revisions,
            **attachment_revisions,
            **image_revisions,
        }
        token_evidence = _build_token_evidence(
            request.profile,
            field_token_bindings,
            content_rules,
            frozen_image_rules,
            attachment_bindings,
        )
        try:
            snapshot = MaterialSnapshot(
                field_values=request.frozen_field_values,
                field_token_bindings=field_token_bindings,
                content_bindings=content_bindings,
                content_rules=content_rules,
                frozen_image_rules=frozen_image_rules,
                image_source_bindings=image_sources,
                attachment_bindings=attachment_bindings,
                token_evidence=token_evidence,
                material_schema_id=request.material_schema_id,
                material_schema_version=request.material_schema_version,
                rule_versions=request.rule_versions,
                source_revisions=source_revisions,
            )
        except (TypeError, ValueError) as exc:
            # MaterialSnapshot remains the authoritative recursive freeze and
            # resolved-watermark boundary.  Never expose a partially built
            # instance if that final boundary rejects the payload.
            diagnostics.add(
                "snapshot_contract_invalid",
                "snapshot",
                str(exc),
                "MaterialSnapshot",
            )
            return MaterialSnapshotBuildResult(
                snapshot=None,
                diagnostics=tuple(diagnostics.items),
            )
        return MaterialSnapshotBuildResult(snapshot=snapshot)

    def build_or_raise(
        self,
        request: MaterialSnapshotBuildRequest,
    ) -> MaterialSnapshot:
        return self.build(request).require_snapshot()


def _build_token_evidence(
    profile: EntityProfile,
    field_token_bindings: Mapping[str, str],
    content_rules: Sequence[ContentInsertionRule],
    image_rules: Sequence[FrozenImageMaterialRule],
    attachment_bindings: Sequence[AttachmentBinding],
) -> tuple[FrozenMaterialTokenEvidence, ...]:
    function_fields = {
        str(key or "").strip()
        for key in profile.field_functions
        if str(key or "").strip()
    }
    evidence: list[FrozenMaterialTokenEvidence] = []
    for token_key, field_id in field_token_bindings.items():
        ref = parse_material_token(token_key)
        producer = (
            MaterialTokenProducer.FUNCTION
            if ref.namespace is MaterialTokenNamespace.TEXT
            and field_id in function_fields
            else ref.default_producer
        )
        evidence.append(
            FrozenMaterialTokenEvidence(
                token=ref.token,
                kind=MaterialTokenKind.FIELD,
                producer=producer,
                resource_id=field_id,
            )
        )
    evidence.extend(
        FrozenMaterialTokenEvidence(
            token=rule.anchor_token,
            kind=MaterialTokenKind.CONTENT,
            producer=MaterialTokenProducer.FILE_BINDING,
            resource_id=rule.content_id,
        )
        for rule in content_rules
    )
    evidence.extend(
        FrozenMaterialTokenEvidence(
            token=rule.anchor_token,
            kind=MaterialTokenKind.IMAGE,
            producer=MaterialTokenProducer.IMAGE_BINDING,
            resource_id=rule.source_role,
        )
        for rule in image_rules
    )
    evidence.extend(
        FrozenMaterialTokenEvidence(
            token=binding.anchor_token,
            kind=MaterialTokenKind.ATTACHMENT,
            producer=MaterialTokenProducer.ATTACHMENT_BINDING,
            resource_id=binding.role,
        )
        for binding in attachment_bindings
    )
    return tuple(sorted(evidence, key=lambda item: item.token.casefold()))

def build_material_snapshot(
    request: MaterialSnapshotBuildRequest,
) -> MaterialSnapshotBuildResult:
    """Build one atomic Freeze result with the default stateless builder."""

    return MaterialSnapshotBuilder().build(request)


def build_material_snapshot_or_raise(
    request: MaterialSnapshotBuildRequest,
) -> MaterialSnapshot:
    """Build and raise :class:`MaterialSnapshotBuildError` on diagnostics."""

    return MaterialSnapshotBuilder().build_or_raise(request)


def _validated_source_root(
    raw_root: str | Path | None,
    diagnostics: _DiagnosticCollector,
) -> Path | None:
    if raw_root is None or not str(raw_root).strip():
        return None
    candidate = Path(raw_root).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        diagnostics.add(
            "source_root_missing",
            "path",
            "source_root does not exist or cannot be resolved",
            str(candidate),
        )
        return candidate.resolve(strict=False)
    if not resolved.is_dir():
        diagnostics.add(
            "source_root_not_directory",
            "path",
            "source_root must identify a directory",
            str(resolved),
        )
    return resolved


def _validate_snapshot_metadata(
    request: MaterialSnapshotBuildRequest,
    diagnostics: _DiagnosticCollector,
) -> None:
    for name in (
        "material_schema_id",
        "material_schema_version",
    ):
        value = getattr(request, name)
        if not isinstance(value, str) or not value.strip():
            diagnostics.add(
                "snapshot_metadata_missing",
                "snapshot",
                f"{name} must be a non-empty string",
                name,
            )
    for key in sorted(request.rule_versions, key=lambda item: str(item)):
        value = request.rule_versions[key]
        if not isinstance(key, str) or not key.strip():
            diagnostics.add(
                "rule_version_key_invalid",
                "snapshot",
                "rule version keys must be non-empty strings",
                "rule_versions",
            )
        if not isinstance(value, str) or not value.strip():
            diagnostics.add(
                "rule_version_value_invalid",
                "snapshot",
                "rule version values must be non-empty strings",
                f"rule_versions.{key}",
            )


def _freeze_field_token_bindings(
    field_values: Mapping[str, object],
    raw_aliases: object,
    timeline_field_keys: Sequence[str],
    *,
    diagnostics: _DiagnosticCollector,
) -> dict[str, str]:
    """Resolve mutable alias chains into one immutable token-to-field map.

    Consumers must not interpret ``EntityProfile.field_aliases`` themselves.
    Every accepted token key points directly at a key in the already-frozen
    field value mapping, so later document processors have no alias recursion
    or UI state to consult.
    """

    canonical_keys: set[str] = set()
    for raw_key in sorted(field_values, key=lambda item: str(item).casefold()):
        if not isinstance(raw_key, str) or not raw_key.strip():
            diagnostics.add(
                "field_key_invalid",
                "field",
                "field value keys must be non-empty strings",
                "field_values",
            )
            continue
        key = _normalized_token_key(raw_key)
        if not key:
            diagnostics.add(
                "field_key_invalid",
                "field",
                "field value keys must contain a token key",
                f"field_values.{raw_key}",
            )
            continue
        if key != raw_key.strip():
            diagnostics.add(
                "field_key_wrapped",
                "field",
                "field value keys must be canonical keys without placeholder braces",
                f"field_values.{raw_key}",
            )
            continue
        if key in canonical_keys:
            diagnostics.add(
                "field_key_duplicate",
                "field",
                f"duplicate canonical field key {key!r}",
                f"field_values.{raw_key}",
            )
            continue
        canonical_keys.add(key)

    if not isinstance(raw_aliases, Mapping):
        diagnostics.add(
            "field_aliases_invalid",
            "field",
            "profile.field_aliases must be a mapping",
            "profile.field_aliases",
        )
        return _field_namespace_bindings(
            {key: key for key in sorted(canonical_keys, key=str.casefold)},
            timeline_field_keys,
        )

    aliases: dict[str, str] = {}
    for raw_alias in sorted(raw_aliases, key=lambda item: str(item).casefold()):
        raw_target = raw_aliases[raw_alias]
        if not isinstance(raw_alias, str) or not isinstance(raw_target, str):
            diagnostics.add(
                "field_alias_invalid",
                "field",
                "field aliases and targets must be strings",
                "profile.field_aliases",
            )
            continue
        alias = _normalized_token_key(raw_alias)
        target = _normalized_token_key(raw_target)
        if not alias or not target:
            diagnostics.add(
                "field_alias_invalid",
                "field",
                "field aliases and targets must contain a token key",
                f"profile.field_aliases.{raw_alias}",
            )
            continue
        previous = aliases.get(alias)
        if previous is not None and previous != target:
            diagnostics.add(
                "field_alias_duplicate",
                "field",
                f"normalized alias {alias!r} has conflicting targets",
                f"profile.field_aliases.{raw_alias}",
            )
            continue
        aliases[alias] = target

    bindings = {key: key for key in canonical_keys}
    resolved: dict[str, str | None] = {}

    def resolve(alias: str) -> str | None:
        cached = resolved.get(alias, ...)
        if cached is not ...:
            return cached
        trail: list[str] = []
        current = alias
        while current in aliases:
            if current in trail:
                cycle = trail[trail.index(current) :] + [current]
                diagnostics.add(
                    "field_alias_cycle",
                    "field",
                    "field alias cycle detected: " + " -> ".join(cycle),
                    f"profile.field_aliases.{alias}",
                )
                for item in trail:
                    resolved[item] = None
                return None
            cached_target = resolved.get(current, ...)
            if cached_target is not ...:
                for item in trail:
                    resolved[item] = cached_target
                return cached_target
            trail.append(current)
            current = aliases[current]
        if current not in canonical_keys:
            diagnostics.add(
                "field_alias_target_missing",
                "field",
                f"field alias resolves to missing frozen field {current!r}",
                f"profile.field_aliases.{alias}",
            )
            for item in trail:
                resolved[item] = None
            return None
        for item in trail:
            resolved[item] = current
        return current

    for alias in sorted(aliases, key=str.casefold):
        target = resolve(alias)
        if target is None:
            continue
        if alias in canonical_keys and alias != target:
            diagnostics.add(
                "field_alias_shadows_canonical",
                "field",
                f"alias {alias!r} cannot redirect a canonical field to {target!r}",
                f"profile.field_aliases.{alias}",
            )
            continue
        bindings[alias] = target
    return _field_namespace_bindings(bindings, timeline_field_keys)


def _field_namespace_bindings(
    identifier_bindings: Mapping[str, str],
    timeline_field_keys: Sequence[str],
) -> dict[str, str]:
    """Close field identities over the two registered field namespaces.

    Profile fields and aliases remain logical identifiers.  The immutable
    snapshot is the boundary that expands them into canonical token keys, so
    no downstream consumer has to guess whether a bare name is text or time.
    """

    timeline_keys = {
        str(item or "").strip()
        for item in timeline_field_keys
        if str(item or "").strip()
    }
    bindings: dict[str, str] = {}
    for identifier, target in identifier_bindings.items():
        namespace = (
            MaterialTokenNamespace.TIME
            if target in timeline_keys
            else MaterialTokenNamespace.TEXT
        )
        bindings[
            material_token_key(
                "{{@" + namespace.value + ":" + identifier + "}}"
            )
        ] = target
    return dict(sorted(bindings.items(), key=lambda item: item[0].casefold()))


def _normalized_token_key(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("{{@") or text.startswith("@"):
        try:
            ref = parse_material_token(text)
        except (TypeError, ValueError):
            return text
        return ref.identifier if ref.kind is MaterialTokenKind.FIELD else text
    if text.startswith("{{") and text.endswith("}}"):
        return text[2:-2].strip()
    if text.startswith("${") and text.endswith("}"):
        return text[2:-1].strip()
    return text


def _freeze_content_domain(
    profile: EntityProfile,
    *,
    repository: ContentArtifactRepository,
    diagnostics: _DiagnosticCollector,
) -> tuple[
    tuple[ContentMaterialBinding, ...],
    tuple[ContentInsertionRule, ...],
    dict[str, str],
]:
    raw_bindings = profile.content_bindings
    raw_rules = profile.content_rules
    if not isinstance(raw_bindings, Mapping):
        diagnostics.add(
            "content_bindings_invalid",
            "content",
            "profile.content_bindings must be a mapping",
            "profile.content_bindings",
        )
        return (), (), {}
    if not isinstance(raw_rules, Sequence) or isinstance(
        raw_rules, (str, bytes, bytearray)
    ):
        diagnostics.add(
            "content_rules_invalid",
            "content",
            "profile.content_rules must be a sequence",
            "profile.content_rules",
        )
        return (), (), {}

    valid_bindings: dict[str, ContentMaterialBinding] = {}
    for raw_key in sorted(raw_bindings, key=lambda item: str(item).casefold()):
        binding = raw_bindings[raw_key]
        path = f"profile.content_bindings.{raw_key}"
        if not isinstance(raw_key, str) or not raw_key.strip():
            diagnostics.add(
                "content_binding_key_invalid",
                "content",
                "content binding keys must be non-empty strings",
                path,
            )
            continue
        if not isinstance(binding, ContentMaterialBinding):
            diagnostics.add(
                "content_binding_type_invalid",
                "content",
                "content binding must be a ContentMaterialBinding",
                path,
            )
            continue
        if raw_key != binding.content_id:
            diagnostics.add(
                "content_binding_key_mismatch",
                "content",
                "mapping key must equal binding.content_id",
                path,
            )
            continue
        valid_bindings[binding.content_id] = binding

    valid_rules: list[ContentInsertionRule] = []
    seen_rule_ids: set[str] = set()
    referenced_ids: set[str] = set()
    rule_counts: dict[str, int] = {}
    for index, rule in enumerate(raw_rules):
        path = f"profile.content_rules[{index}]"
        if not isinstance(rule, ContentInsertionRule):
            diagnostics.add(
                "content_rule_type_invalid",
                "content",
                "content rule must be a ContentInsertionRule",
                path,
            )
            continue
        if rule.rule_id in seen_rule_ids:
            diagnostics.add(
                "content_rule_duplicate",
                "content",
                f"duplicate content rule_id {rule.rule_id!r}",
                path,
            )
            continue
        seen_rule_ids.add(rule.rule_id)
        valid_rules.append(rule)
        referenced_ids.add(rule.content_id)
        rule_counts[rule.content_id] = rule_counts.get(rule.content_id, 0) + 1
        if rule.content_id not in valid_bindings:
            diagnostics.add(
                "content_rule_binding_missing",
                "content",
                f"rule references missing content binding {rule.content_id!r}",
                path,
            )

    for content_id in sorted(set(valid_bindings) - referenced_ids):
        diagnostics.add(
            "content_binding_rule_missing",
            "content",
            "content binding is not closed by any insertion rule",
            f"profile.content_bindings.{content_id}",
        )
    for content_id in sorted(valid_bindings, key=str.casefold):
        count = rule_counts.get(content_id, 0)
        if count <= 1:
            continue
        path = f"profile.content_bindings.{content_id}"
        diagnostics.add(
            "binding_rule_cardinality_invalid",
            "content",
            f"content binding requires exactly one rule, found {count}",
            path,
        )
        diagnostics.add(
            "duplicate_content_rules",
            "content",
            f"content id has {count} rules with the same canonical anchor",
            path,
        )

    frozen_bindings: list[ContentMaterialBinding] = []
    for content_id in sorted(valid_bindings, key=str.casefold):
        binding = valid_bindings[content_id]
        try:
            repository.validate(binding.artifact_ref)
        except ContentArtifactRepositoryError as exc:
            diagnostics.add(
                exc.code,
                "content",
                "compiled content artifact is missing or invalid",
                f"content:{binding.content_id}",
            )
            continue
        frozen_bindings.append(binding)

    return tuple(frozen_bindings), tuple(valid_rules), {}


def _freeze_attachment_domain(
    profile: EntityProfile,
    *,
    source_root: Path | None,
    diagnostics: _DiagnosticCollector,
) -> tuple[tuple[AttachmentBinding, ...], dict[str, str]]:
    raw_bindings = profile.attachment_bindings
    if not isinstance(raw_bindings, Mapping):
        diagnostics.add(
            "attachment_bindings_invalid",
            "attachment",
            "profile.attachment_bindings must be a mapping",
            "profile.attachment_bindings",
        )
        return (), {}

    frozen_bindings: list[AttachmentBinding] = []
    revisions: dict[str, str] = {}
    for raw_role in sorted(raw_bindings, key=lambda item: str(item).casefold()):
        binding = raw_bindings[raw_role]
        label = f"profile.attachment_bindings.{raw_role}"
        if not isinstance(raw_role, str) or not raw_role.strip():
            diagnostics.add(
                "attachment_binding_key_invalid",
                "attachment",
                "attachment binding keys must be non-empty strings",
                label,
            )
            continue
        if not isinstance(binding, AttachmentBinding):
            diagnostics.add(
                "attachment_binding_type_invalid",
                "attachment",
                "attachment binding must be an AttachmentBinding",
                label,
            )
            continue
        if raw_role != binding.role:
            diagnostics.add(
                "attachment_binding_key_mismatch",
                "attachment",
                "mapping key must equal binding.role",
                label,
            )
            continue
        if len(binding.items) < binding.min_items or (
            binding.required and not binding.items
        ):
            diagnostics.add(
                "attachment_items_missing",
                "attachment",
                "attachment binding does not satisfy its required/min_items contract",
                label,
            )

        frozen_items: list[AttachmentItem] = []
        for item in binding.items:
            item_label = f"attachment:{binding.role}:{item.item_id}"
            try:
                binding.validate_item(item)
            except (TypeError, ValueError) as exc:
                diagnostics.add(
                    "attachment_item_contract_invalid",
                    "attachment",
                    str(exc),
                    item_label,
                )
                continue
            path = _validate_file_ref(
                item.file_ref,
                domain="attachment",
                label=item_label,
                source_root=source_root,
                expected_extensions=(
                    frozenset(binding.accepted_extensions)
                    if binding.accepted_extensions
                    else None
                ),
                expected_media_types=None,
                diagnostics=diagnostics,
            )
            if path is None:
                continue
            normalized_ref = replace(item.file_ref, source_path=str(path))
            frozen_items.append(replace(item, file_ref=normalized_ref))
            revisions[item_label] = normalized_ref.content_sha256

        frozen_binding = replace(binding, items=tuple(frozen_items))
        frozen_bindings.append(frozen_binding)
        revisions[f"attachment:{binding.role}"] = frozen_binding.binding_revision
    return tuple(frozen_bindings), revisions


def _freeze_image_domain(
    raw_rules: Sequence[FrozenImageMaterialRule],
    raw_sources: Sequence[ImageSourceBinding],
    *,
    source_root: Path | None,
    diagnostics: _DiagnosticCollector,
) -> tuple[
    tuple[FrozenImageMaterialRule, ...],
    tuple[ImageSourceBinding, ...],
    dict[str, str],
]:
    rules = tuple(raw_rules)
    sources = tuple(raw_sources)
    for attribute, code in (
        ("rule_id", "image_rule_id_duplicate"),
        ("source_role", "image_rule_role_duplicate"),
        ("anchor_token", "image_rule_anchor_duplicate"),
    ):
        seen: set[str] = set()
        for index, rule in enumerate(rules):
            value = getattr(rule, attribute)
            if value in seen:
                diagnostics.add(
                    code,
                    "image",
                    f"duplicate frozen image rule {attribute} {value!r}",
                    f"frozen_image_rules[{index}]",
                )
            seen.add(value)

    rules_by_role = {item.source_role: item for item in rules}
    seen_item_ids: set[str] = set()
    seen_role_sequences: set[tuple[str, int]] = set()
    by_role: dict[str, list[ImageSourceBinding]] = {}
    frozen_sources: list[ImageSourceBinding] = []
    revisions: dict[str, str] = {}
    for index, binding in enumerate(sources):
        label = f"image_source_bindings[{index}]"
        if binding.item_id in seen_item_ids:
            diagnostics.add(
                "image_source_item_duplicate",
                "image",
                f"duplicate image source item_id {binding.item_id!r}",
                label,
            )
        seen_item_ids.add(binding.item_id)
        role_sequence = (binding.role, binding.sequence)
        if role_sequence in seen_role_sequences:
            diagnostics.add(
                "image_source_sequence_duplicate",
                "image",
                "role/sequence must identify exactly one image source",
                label,
            )
        seen_role_sequences.add(role_sequence)
        if binding.role not in rules_by_role:
            diagnostics.add(
                "image_source_rule_missing",
                "image",
                f"image source uses undeclared role {binding.role!r}",
                label,
            )
        by_role.setdefault(binding.role, []).append(binding)
        path = _validate_file_ref(
            binding.file_ref,
            domain="image",
            label=f"image:{binding.role}:{binding.item_id}",
            source_root=source_root,
            expected_extensions=frozenset(IMAGE_EXTENSIONS),
            expected_media_types=None,
            diagnostics=diagnostics,
        )
        if path is None:
            continue
        if not _validate_image_payload(
            path,
            binding.file_ref,
            label=label,
            diagnostics=diagnostics,
        ):
            continue
        normalized_ref = replace(binding.file_ref, source_path=str(path))
        frozen_binding = replace(binding, file_ref=normalized_ref)
        frozen_sources.append(frozen_binding)
        revisions[
            f"image:{binding.role}:{binding.item_id}"
        ] = normalized_ref.content_sha256

    for index, rule in enumerate(rules):
        selected = by_role.get(rule.source_role, ())
        if rule.required and not selected:
            diagnostics.add(
                "required_image_source_missing",
                "image",
                f"required role {rule.source_role!r} has no selected image",
                f"frozen_image_rules[{index}]",
            )
        if rule.cardinality is ImageCardinality.SINGLE and len(selected) > 1:
            diagnostics.add(
                "single_image_cardinality_exceeded",
                "image",
                f"role {rule.source_role!r} permits one image but has {len(selected)}",
                f"frozen_image_rules[{index}]",
            )

    return (
        tuple(sorted(rules, key=lambda item: item.rule_id.casefold())),
        tuple(
            sorted(
                frozen_sources,
                key=lambda item: (
                    item.role.casefold(),
                    item.sequence,
                    item.item_id.casefold(),
                ),
            )
        ),
        revisions,
    )


def _validate_image_payload(
    path: Path,
    file_ref: FileAssetRef,
    *,
    label: str,
    diagnostics: _DiagnosticCollector,
) -> bool:
    format_contracts = {
        "PNG": ("image/png", frozenset({".png"})),
        "JPEG": ("image/jpeg", frozenset({".jpg", ".jpeg"})),
        "WEBP": ("image/webp", frozenset({".webp"})),
        "BMP": ("image/bmp", frozenset({".bmp"})),
        "TIFF": ("image/tiff", frozenset({".tif", ".tiff"})),
    }
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as probe:
                detected_format = str(probe.format or "").upper()
                width, height = probe.size
                probe.verify()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        diagnostics.add(
            "image_decompression_bomb",
            "image",
            "image dimensions exceed Pillow safety limits",
            label,
        )
        return False
    except (OSError, ValueError, UnidentifiedImageError):
        diagnostics.add(
            "image_payload_invalid",
            "image",
            "file bytes are not a supported raster image",
            label,
        )
        return False
    if width <= 0 or height <= 0 or detected_format not in format_contracts:
        diagnostics.add(
            "image_payload_unsupported",
            "image",
            f"unsupported raster format {detected_format or '<unknown>'}",
            label,
        )
        return False
    expected_media_type, extensions = format_contracts[detected_format]
    if file_ref.media_type.casefold() != expected_media_type:
        diagnostics.add(
            "image_payload_mime_mismatch",
            "image",
            f"image bytes are {expected_media_type}, not {file_ref.media_type}",
            label,
        )
        return False
    if path.suffix.casefold() not in extensions:
        diagnostics.add(
            "image_payload_extension_mismatch",
            "image",
            f"image bytes are {detected_format}, not {path.suffix or '<none>'}",
            label,
        )
        return False
    return True


def _validate_plain_value(
    value: object,
    *,
    path: str,
    domain: str,
    diagnostics: _DiagnosticCollector,
    active: set[int],
) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            diagnostics.add(
                "non_finite_value",
                domain,
                "NaN and infinity are forbidden in a material snapshot",
                path,
            )
        return
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in active:
            diagnostics.add(
                "recursive_value",
                domain,
                "recursive containers are not supported",
                path,
            )
            return
        active.add(identity)
        for raw_key in sorted(value, key=lambda item: str(item)):
            if not isinstance(raw_key, str):
                diagnostics.add(
                    "mapping_key_invalid",
                    domain,
                    "snapshot mapping keys must be strings",
                    path,
                )
                continue
            _validate_plain_value(
                value[raw_key],
                path=f"{path}.{raw_key}",
                domain=domain,
                diagnostics=diagnostics,
                active=active,
            )
        active.remove(identity)
        return
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        identity = id(value)
        if identity in active:
            diagnostics.add(
                "recursive_value",
                domain,
                "recursive containers are not supported",
                path,
            )
            return
        active.add(identity)
        for index, item in enumerate(value):
            _validate_plain_value(
                item,
                path=f"{path}[{index}]",
                domain=domain,
                diagnostics=diagnostics,
                active=active,
            )
        active.remove(identity)
        return
    diagnostics.add(
        "unsupported_value_type",
        domain,
        f"unsupported snapshot value type {type(value).__name__}",
        path,
    )


def _validate_file_ref(
    file_ref: FileAssetRef,
    *,
    domain: str,
    label: str,
    source_root: Path | None,
    expected_extensions: frozenset[str] | None,
    expected_media_types: frozenset[str] | None,
    diagnostics: _DiagnosticCollector,
) -> Path | None:
    if not isinstance(file_ref, FileAssetRef):
        diagnostics.add(
            "file_ref_type_invalid",
            domain,
            "source must be a FileAssetRef",
            label,
        )
        return None
    if Path(file_ref.original_name).name != file_ref.original_name or any(
        separator in file_ref.original_name for separator in ("/", "\\")
    ):
        diagnostics.add(
            "file_original_name_invalid",
            domain,
            "original_name must be a plain file name without path segments",
            label,
        )

    raw_path = Path(file_ref.source_path).expanduser()
    if not raw_path.is_absolute():
        if source_root is not None:
            raw_path = source_root / raw_path
        elif ".." in raw_path.parts:
            diagnostics.add(
                "source_path_escape",
                domain,
                "relative source_path cannot traverse without a source_root",
                file_ref.source_path,
            )
            return None
    resolved = raw_path.resolve(strict=False)
    if source_root is not None and not _is_within(resolved, source_root):
        diagnostics.add(
            "source_path_escape",
            domain,
            "source_path escapes the declared source_root",
            str(resolved),
        )
        return None
    if not _validate_current_file(
        resolved,
        declared_sha256=file_ref.content_sha256,
        declared_size=file_ref.byte_size,
        declared_media_type=file_ref.media_type,
        domain=domain,
        label=label,
        expected_extensions=expected_extensions,
        expected_media_types=expected_media_types,
        diagnostics=diagnostics,
    ):
        return None

    source_extension = resolved.suffix.casefold()
    original_extension = Path(file_ref.original_name).suffix.casefold()
    if source_extension != original_extension:
        diagnostics.add(
            "file_extension_mismatch",
            domain,
            "source_path and original_name extensions do not match",
            label,
        )
        return None
    return resolved


def _validate_current_file(
    path: Path,
    *,
    declared_sha256: str,
    declared_size: int,
    declared_media_type: str,
    domain: str,
    label: str,
    expected_extensions: frozenset[str] | None,
    expected_media_types: frozenset[str] | None,
    diagnostics: _DiagnosticCollector,
) -> bool:
    if not path.is_file():
        diagnostics.add(
            "source_file_missing",
            domain,
            "current source file does not exist",
            str(path),
        )
        return False
    extension = path.suffix.casefold()
    media_type = _normalize_media_type(declared_media_type)
    valid = True
    if expected_extensions is not None and extension not in expected_extensions:
        diagnostics.add(
            "source_extension_invalid",
            domain,
            f"source extension {extension or '<none>'!r} is not allowed",
            label,
        )
        valid = False
    if expected_media_types is not None and media_type not in expected_media_types:
        diagnostics.add(
            "source_media_type_invalid",
            domain,
            f"declared MIME {declared_media_type!r} is not allowed",
            label,
        )
        valid = False
    extension_media_types = _media_types_for_extension(extension)
    if extension_media_types and media_type not in extension_media_types:
        diagnostics.add(
            "source_mime_extension_mismatch",
            domain,
            "declared MIME does not match the source extension",
            label,
        )
        valid = False
    try:
        actual_size = path.stat().st_size
        actual_sha256 = _file_sha256(path)
    except OSError as exc:
        diagnostics.add(
            "source_file_unreadable",
            domain,
            f"current source file cannot be read: {exc}",
            str(path),
        )
        return False
    if actual_size != declared_size:
        diagnostics.add(
            "source_size_mismatch",
            domain,
            f"declared byte_size {declared_size} != current size {actual_size}",
            label,
        )
        valid = False
    if actual_sha256 != declared_sha256:
        diagnostics.add(
            "source_hash_mismatch",
            domain,
            "declared SHA-256 does not match the current file",
            label,
        )
        valid = False
    return valid


def _media_types_for_extension(extension: str) -> frozenset[str]:
    if extension in _MARKDOWN_EXTENSIONS:
        return _MARKDOWN_MEDIA_TYPES
    if extension in _IMAGE_MEDIA_TYPES_BY_EXTENSION:
        return _IMAGE_MEDIA_TYPES_BY_EXTENSION[extension]
    guessed, _encoding = mimetypes.guess_type(f"source{extension}")
    if not guessed:
        return frozenset()
    return frozenset({_normalize_media_type(guessed)})


def _normalize_media_type(value: object) -> str:
    return str(value or "").split(";", 1)[0].strip().casefold()


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except (OSError, RuntimeError, ValueError):
        return False
    return True


__all__ = [
    "MaterialSnapshotBuildDiagnostic",
    "MaterialSnapshotBuildError",
    "MaterialSnapshotBuildRequest",
    "MaterialSnapshotBuildResult",
    "MaterialSnapshotBuilder",
    "build_material_snapshot",
    "build_material_snapshot_or_raise",
]
