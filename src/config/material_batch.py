"""Build per-profile material contexts for batch execution."""

from __future__ import annotations

import copy
import re
from string import Formatter
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Sequence

from src.config.asset_resolution import (
    AssetDiagnostic,
    asset_diagnostic_payload,
    directory_content_revision,
    file_content_revision,
    resolve_profile_assets,
)
from src.config.entity import EntityArchive, EntityProfile
from src.config.material_context import MaterialExecutionContext
from src.config.materials import normalize_asset_role
from src.config.material_schema_registry import get_material_schema


@dataclass(slots=True)
class MaterialBatchItem:
    profile_id: str
    profile_name: str
    output_dir: str
    context: MaterialExecutionContext


@dataclass(frozen=True, slots=True)
class MaterialBatchPreflightResult:
    issues: tuple[str, ...] = ()
    output_paths: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.issues


@dataclass(slots=True)
class MaterialBatchSelection:
    mode_id: str = ""
    scene_id: str = ""
    package_id: str = ""
    archive: EntityArchive = field(default_factory=EntityArchive)
    profile_ids: list[str] = field(default_factory=list)
    output_dir_template: str = "{entity_name}"
    base_context: MaterialExecutionContext = field(default_factory=MaterialExecutionContext)
    source_kind: str = ""
    source_path: str = ""
    item_metadata: dict[str, dict[str, object]] = field(default_factory=dict)

    def clone(self) -> "MaterialBatchSelection":
        return MaterialBatchSelection(
            mode_id=str(self.mode_id or ""),
            scene_id=str(self.scene_id or ""),
            package_id=str(self.package_id or ""),
            archive=copy.deepcopy(self.archive),
            profile_ids=list(self.profile_ids),
            output_dir_template=str(self.output_dir_template or "{entity_name}"),
            base_context=self.base_context.clone(),
            source_kind=str(self.source_kind or ""),
            source_path=str(self.source_path or ""),
            item_metadata=copy.deepcopy(self.item_metadata),
        )

    def resolved_mode_id(self) -> str:
        explicit = str(self.mode_id or "").strip()
        if explicit:
            return explicit
        return self.base_context.resolved_mode_id()

    def is_compatible_with(self, *, mode_id: str, scene_id: str = "") -> bool:
        target_mode = str(mode_id or "").strip()
        selection_mode = self.resolved_mode_id()
        if selection_mode and target_mode and selection_mode != target_mode:
            return False
        target_scene = str(scene_id or "").strip()
        selection_scene = str(self.scene_id or "").strip()
        if selection_scene and target_scene and selection_scene != target_scene:
            return False
        return self.base_context.is_compatible_with(
            mode_id=target_mode,
            scene_id=target_scene,
        )


def build_material_batch_items(
    archive: EntityArchive,
    *,
    profile_ids: Sequence[str] | None = None,
    base_output_dir: str | Path = "",
    output_dir_template: str = "{entity_name}",
    base_context: MaterialExecutionContext | None = None,
) -> list[MaterialBatchItem]:
    selected_profiles = _select_profiles(archive, profile_ids)
    base = Path(base_output_dir) if str(base_output_dir or "").strip() else Path()
    shared_context = (
        base_context.clone()
        if isinstance(base_context, MaterialExecutionContext)
        else MaterialExecutionContext()
    )
    items: list[MaterialBatchItem] = []

    for profile in selected_profiles:
        entity_name = (
            profile.fields.get("entity_name")
            or profile.fields.get("company_name")
            or profile.profile_name
            or profile.profile_id
            or "entity"
        )
        output_path = _material_batch_output_path(
            base=base,
            template=output_dir_template,
            archive_id=archive.archive_id,
            archive_name=archive.archive_name,
            profile_id=profile.profile_id,
            profile_name=profile.profile_name,
            entity_name=entity_name,
        )
        assets_dir = profile.assets_dir or shared_context.entity_assets_dir
        role_specs = []
        for schema_id in shared_context.material_schema_ids:
            try:
                role_specs.extend(get_material_schema(schema_id).asset_roles)
            except KeyError:
                continue
        profile_resolution = resolve_profile_assets(profile, role_specs=role_specs)
        profile_roles = set(profile_resolution.owners)
        shared_roles = {
            normalize_asset_role(item.role)
            for item in shared_context.asset_items
            if normalize_asset_role(item.role)
        }
        conflicting_asset_roles = profile_roles.intersection(shared_roles)
        asset_items = [
            *[
                item
                for item in profile_resolution.items
                if normalize_asset_role(item.role) not in conflicting_asset_roles
            ],
            *[
                copy.deepcopy(item)
                for item in shared_context.asset_items
                if normalize_asset_role(item.role) not in conflicting_asset_roles
            ],
        ]
        source_conflict_diagnostics = [
            AssetDiagnostic(
                code="asset_source_conflict",
                role=role,
                message=(
                    f"asset role {role!r} is owned by both the profile and "
                    "the batch base context"
                ),
            )
            for role in sorted(conflicting_asset_roles)
        ]
        image_material_rules = _merge_image_material_rules(
            shared_context.image_material_rules,
            profile.image_material_rules,
        )
        context = MaterialExecutionContext(
            mode_id=shared_context.mode_id,
            scene_id=shared_context.scene_id,
            package_id=shared_context.package_id,
            material_schema_ids=tuple(shared_context.material_schema_ids),
            compatible_profile_ids=tuple(shared_context.compatible_profile_ids),
            compatible_master_families=tuple(
                shared_context.compatible_master_families
            ),
            archive_id=archive.archive_id,
            archive_name=archive.archive_name,
            profile_id=profile.profile_id,
            profile_name=profile.profile_name,
            entity_data={**shared_context.entity_data, **dict(profile.fields)},
            field_scopes={
                **shared_context.field_scopes,
                **dict(profile.field_scopes),
            },
            field_functions={
                **copy.deepcopy(shared_context.field_functions),
                **copy.deepcopy(profile.field_functions),
            },
            timeline_plans={
                **copy.deepcopy(shared_context.timeline_plans),
                **copy.deepcopy(profile.timeline_plans),
            },
            field_aliases={
                **shared_context.field_aliases,
                **dict(profile.field_aliases),
            },
            exact_material_placeholders=shared_context.exact_material_placeholders,
            entity_assets_dir=assets_dir,
            images=copy.deepcopy(shared_context.images),
            asset_items=asset_items,
            asset_diagnostics=[
                *copy.deepcopy(shared_context.asset_diagnostics),
                *[
                    asset_diagnostic_payload(diagnostic)
                    for diagnostic in (
                        *profile_resolution.diagnostics,
                        *source_conflict_diagnostics,
                    )
                ],
            ],
            image_rules=copy.deepcopy(shared_context.image_rules),
            image_material_rules=image_material_rules,
            image_watermark_text=shared_context.image_watermark_text,
            content_bindings={
                **copy.deepcopy(shared_context.content_bindings),
                **copy.deepcopy(profile.content_bindings),
            },
            content_rules=_merge_content_rules(
                shared_context.content_rules,
                profile.content_rules,
            ),
            attachment_bindings={
                **copy.deepcopy(profile.attachment_bindings),
                **copy.deepcopy(shared_context.attachment_bindings),
            },
        )
        items.append(
            MaterialBatchItem(
                profile_id=profile.profile_id,
                profile_name=profile.profile_name,
                output_dir=str(output_path),
                context=context,
            )
        )
    return items


def _merge_content_rules(shared_rules, profile_rules):
    """Merge by rule identity while keeping deterministic input order."""

    merged = {
        str(rule.rule_id): copy.deepcopy(rule)
        for rule in tuple(shared_rules or ())
    }
    for rule in tuple(profile_rules or ()):
        merged[str(rule.rule_id)] = copy.deepcopy(rule)
    return list(merged.values())


def _merge_image_material_rules(shared_rules, profile_rules):
    """Merge by rule_id; profile facts override shared facts deterministically."""

    merged = {
        str(rule_id): copy.deepcopy(rule)
        for rule_id, rule in dict(shared_rules or {}).items()
    }
    merged.update(
        {
            str(rule_id): copy.deepcopy(rule)
            for rule_id, rule in dict(profile_rules or {}).items()
        }
    )
    return dict(sorted(merged.items()))


def check_material_batch_preflight(
    archive: EntityArchive,
    *,
    profile_ids: Sequence[str] | None = None,
    base_output_dir: str | Path = "",
    output_dir_template: str = "{entity_name}",
) -> MaterialBatchPreflightResult:
    """Block ambiguous profile identities and colliding final directories."""

    selected_profiles = _select_profiles(archive, profile_ids)
    issues: list[str] = []
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    output_paths: list[str] = []
    path_owners: dict[str, list[str]] = {}
    base = Path(base_output_dir) if str(base_output_dir or "").strip() else Path()

    for index, profile in enumerate(selected_profiles, start=1):
        profile_id = str(profile.profile_id or "").strip()
        if not profile_id:
            issues.append(f"profile_id_missing:{index}")
        elif profile_id in seen_ids:
            duplicate_ids.add(profile_id)
        else:
            seen_ids.add(profile_id)
        entity_name = (
            profile.fields.get("entity_name")
            or profile.fields.get("company_name")
            or profile.profile_name
            or profile_id
            or "entity"
        )
        try:
            output_path = _material_batch_output_path(
                base=base,
                template=output_dir_template,
                archive_id=archive.archive_id,
                archive_name=archive.archive_name,
                profile_id=profile_id,
                profile_name=profile.profile_name,
                entity_name=entity_name,
            )
        except (KeyError, ValueError, IndexError) as exc:
            issues.append(f"output_dir_invalid:{index}:{exc}")
            continue
        rendered = str(output_path)
        output_paths.append(rendered)
        key = str(output_path.resolve()).casefold()
        owner = profile_id or profile.profile_name or str(index)
        path_owners.setdefault(key, []).append(owner)
        issues.extend(_asset_integrity_issues(profile, owner))

    for profile_id in sorted(duplicate_ids):
        issues.append(f"duplicate_profile_id:{profile_id}")
    for owners in path_owners.values():
        if len(owners) > 1:
            issues.append(f"duplicate_output_path:{','.join(owners)}")

    return MaterialBatchPreflightResult(
        issues=tuple(issues),
        output_paths=tuple(output_paths),
    )


def _asset_integrity_issues(profile: EntityProfile, owner: str) -> list[str]:
    issues: list[str] = []
    collection_revision = str(
        profile.asset_metadata.get("__collection__", {}).get("sha256", "") or ""
    ).strip()
    if (
        collection_revision
        and directory_content_revision(Path(profile.assets_dir))
        != collection_revision
    ):
        issues.append(f"asset_hash_mismatch:{owner}:__collection__")
    for role, path_text in profile.asset_paths.items():
        expected = str(
            profile.asset_metadata.get(str(role), {}).get("sha256", "") or ""
        ).strip()
        if expected and file_content_revision(Path(path_text)) != expected:
            issues.append(f"asset_hash_mismatch:{owner}:{role}")
    for index, raw in enumerate(profile.asset_items, start=1):
        item = dict(raw)
        expected = str(item.get("content_hash", "") or "").strip()
        if not expected:
            continue
        identity = str(item.get("item_id", "") or item.get("role", "") or index)
        if (
            file_content_revision(Path(str(item.get("path", "") or "")))
            != expected
        ):
            issues.append(f"asset_hash_mismatch:{owner}:{identity}")
    return issues


def _select_profiles(archive: EntityArchive, profile_ids: Sequence[str] | None) -> list[EntityProfile]:
    if profile_ids is None:
        return list(archive.profiles)
    if not profile_ids:
        return []
    requested = {str(profile_id) for profile_id in profile_ids}
    return [profile for profile in archive.profiles if profile.profile_id in requested]


def _safe_path_segment(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(value or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned or "entity"


_BATCH_OUTPUT_FIELDS = {
    "archive_id",
    "archive_name",
    "profile_id",
    "profile_name",
    "entity_name",
}
_WINDOWS_RESERVED_PATH_NAMES = {
    "aux",
    "clock$",
    "con",
    "nul",
    "prn",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


def _material_batch_output_path(
    *,
    base: Path,
    template: str,
    archive_id: object,
    archive_name: object,
    profile_id: object,
    profile_name: object,
    entity_name: object,
) -> Path:
    """Render one output directory and prove it remains below ``base``."""

    template_text = str(template or "").strip()
    if not template_text:
        raise ValueError("output_dir_template_empty")
    values = {
        "archive_id": _safe_path_segment(str(archive_id or "")),
        "archive_name": _safe_path_segment(str(archive_name or "")),
        "profile_id": _safe_path_segment(str(profile_id or "")),
        "profile_name": _safe_path_segment(str(profile_name or "")),
        "entity_name": _safe_path_segment(str(entity_name or "")),
    }
    for _literal, field_name, format_spec, conversion in Formatter().parse(
        template_text
    ):
        if field_name is None:
            continue
        if field_name not in _BATCH_OUTPUT_FIELDS:
            raise ValueError(f"output_dir_template_field_invalid:{field_name}")
        if format_spec or conversion:
            raise ValueError(
                f"output_dir_template_expression_invalid:{field_name}"
            )
    rendered = template_text.format_map(values).strip()
    if not rendered:
        raise ValueError("output_dir_rendered_empty")
    windows_relative = PureWindowsPath(rendered)
    if windows_relative.anchor or windows_relative.is_absolute():
        raise ValueError("output_dir_absolute_forbidden")
    if any(part in {".", ".."} for part in windows_relative.parts):
        raise ValueError("output_dir_traversal_forbidden")
    if re.search(r'[<>:"|?*\x00-\x1f]', rendered):
        raise ValueError("output_dir_character_invalid")
    for part in windows_relative.parts:
        if part.rstrip(" .") != part:
            raise ValueError("output_dir_trailing_character_invalid")
        device_name = part.split(".", 1)[0].casefold()
        if device_name in _WINDOWS_RESERVED_PATH_NAMES:
            raise ValueError(f"output_dir_device_name_forbidden:{device_name}")

    relative = Path(*windows_relative.parts)
    output_path = base / relative
    validate_material_batch_output_target(output_path, base_output_dir=base)
    return output_path


def validate_material_batch_output_target(
    output_path: str | Path,
    *,
    base_output_dir: str | Path,
) -> None:
    """Revalidate one rendered target immediately before a batch write."""

    base_lexical = Path(base_output_dir).absolute()
    output_lexical = Path(output_path).absolute()
    try:
        lexical_relative = output_lexical.relative_to(base_lexical)
    except ValueError as exc:
        raise ValueError("output_dir_outside_base") from exc
    if not lexical_relative.parts:
        raise ValueError("output_dir_equals_base")
    cursor = base_lexical
    for part in lexical_relative.parts:
        cursor /= part
        try:
            is_junction = bool(
                getattr(cursor, "is_junction", lambda: False)()
            )
            if cursor.is_symlink() or is_junction:
                raise ValueError(f"output_dir_reparse_forbidden:{part}")
        except OSError as exc:
            raise ValueError(f"output_dir_reparse_check_failed:{part}") from exc

    base_resolved = base_lexical.resolve(strict=False)
    output_resolved = output_lexical.resolve(strict=False)
    try:
        relative = output_resolved.relative_to(base_resolved)
    except ValueError as exc:
        raise ValueError("output_dir_outside_base") from exc
    if not relative.parts:
        raise ValueError("output_dir_equals_base")


__all__ = [
    "MaterialBatchItem",
    "MaterialBatchPreflightResult",
    "MaterialBatchSelection",
    "build_material_batch_items",
    "check_material_batch_preflight",
    "validate_material_batch_output_target",
]
