"""Production adapter between the runner, Pipeline, and material assembly.

The material assembler owns composition, staging, image planning, layout and
atomic publication.  This module only adapts the existing Pipeline callback
contract; it deliberately contains no DOCX assembly implementation of its own.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, is_dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from docx import Document
from docx.oxml.ns import qn

from src.app_meta import APP_DATA_DIR_NAME
from src.config.entity import EntityProfile
from src.config.library import CONFIG_LIBRARY_ROOT
from src.config.material_context import MaterialExecutionContext
from src.config.materials import normalize_asset_role
from src.config.material_schema_registry import MATERIAL_SCHEMA_MAP
from src.modules.registry import create_all_modules
from src.pipeline.module_selection import build_module_selection_plan
from src.pipeline.result import PipelineResult
from src.pipeline.runner import (
    Pipeline,
    pipeline_terminal_assembly_owner,
    pipeline_output_target_matches_source,
    plan_pipeline_output_paths,
)
from src.services.material_assets.intake import build_image_source_items
from src.services.material_content.artifact_repository import (
    ContentArtifactRepository,
    ContentArtifactRepositoryError,
)
from src.services.material_attachments import (
    AttachmentBundleBuildRequest,
    AttachmentBundleProcessingError,
    AttachmentBundleService,
    AttachmentProcessingDiagnostic,
)
from src.services.material_execution import (
    AssemblyDiagnostic,
    AssemblyFailureCode,
    AssemblyStage,
    MaterialAssemblyCancelled,
    MaterialAssemblyError,
    MaterialAssemblyRequest,
    MaterialAssemblyService,
    MaterialPipelineOutcome,
    MaterialVariantRequest,
    PipelineVisibilityEvidence,
    VisibilityEvidenceKind,
)
from src.shared.engine.field_refresh import (
    document_has_toc,
    refresh_doc_fields_with_word,
)
from src.shared.engine.block_visibility import BlockVisibilityReceipt
from src.shared.engine.office_image_layout_contracts import OfficeImageProvider
from src.shared.engine.office_layout_capability_gate import (
    resolve_office_layout_capability,
)


_ASSEMBLY_RULE_VERSIONS = {
    "fields": "material-field-resolution-v1",
    "content": "content-ir-v2",
    "images": "image-material-v1",
    "freeze": "material-snapshot-builder-v1",
    "attachments": "attachment-bundle-v1",
}
_CONTENT_IMAGE_MARKER_PREFIX = "LarkContentImage_"


@dataclass(frozen=True, slots=True)
class MaterialAssemblyRuntimeOutcome:
    result: PipelineResult
    elapsed_seconds: float
    modules_enabled: int
    modules_total: int


def material_assembly_is_active(context: MaterialExecutionContext) -> bool:
    """Return whether this request owns work for the new assembler.

    The image-rules presenter retains optional definitions for the standard
    roles before a user selects any file.  Those dormant rules are configuration,
    not an execution request; activating on their mere presence would route all
    Workbench traffic into the assembler and incorrectly block specialised
    exam/official-document surfaces.  Content rules are active by definition.
    Image rules activate only when required or when their role owns a selected
    asset item.
    """

    if context.content_rules:
        return True
    if context.attachment_bindings:
        return True
    return _has_active_image_rule(context)


def _has_active_image_rule(context: MaterialExecutionContext) -> bool:
    """Return whether an image rule owns work in this execution request."""

    if not context.image_material_rules:
        return False
    selected_roles = {
        normalize_asset_role(getattr(item, "role", ""))
        for item in context.asset_items
        if str(
            getattr(item, "path", "")
            or getattr(item, "source_path", "")
            or ""
        ).strip()
        and normalize_asset_role(getattr(item, "role", ""))
    }
    return any(
        bool(rule.required)
        or normalize_asset_role(rule.source_role) in selected_roles
        for rule in context.image_material_rules.values()
    )


def run_workbench_material_assembly(
    *,
    input_path: Path,
    output_dir: Path,
    output_suffix: str,
    config,
    material_context: MaterialExecutionContext,
    progress_cb,
    cancel_check,
    force_delivery_presets: bool,
    official_master=None,
    document_structure_evidence=None,
    document_scope_decisions=(),
) -> MaterialAssemblyRuntimeOutcome:
    """Execute one active material request through the sole staging contract."""

    started_at = time.perf_counter()
    modules_total = len(create_all_modules())
    adapter: _WorkbenchMaterialPipelineAdapter | None = None

    try:
        if cancel_check():
            raise MaterialAssemblyCancelled(AssemblyStage.PREFLIGHT)
        progress_cb(0, 1, "Preparing material assembly")

        final_paths = plan_pipeline_output_paths(
            input_path,
            config,
            output_dir=output_dir,
            output_suffix=output_suffix,
            force_delivery_presets=force_delivery_presets,
        )
        if not final_paths:
            raise _preflight_error(
                "material assembly requires at least one staged DOCX output"
            )
        source_collisions = {
            variant_id: final_path
            for variant_id, final_path in final_paths.items()
            if pipeline_output_target_matches_source(input_path, final_path)
        }
        if source_collisions:
            detail = "; ".join(
                f"{variant_id}={final_path}"
                for variant_id, final_path in source_collisions.items()
            )
            raise _preflight_error(
                "material assembly output resolves to the input document; "
                f"source overwrite is forbidden: {detail}"
            )

        image_rules = tuple(
            material_context.image_material_rules[key]
            for key in sorted(
                material_context.image_material_rules,
                key=str.casefold,
            )
        )
        image_sources = build_image_source_items(
            material_context.asset_items,
            image_rules,
        )
        profile = _entity_profile(material_context)
        schema_id, schema_version = _material_schema_contract(material_context)
        variants = tuple(
            MaterialVariantRequest(
                variant_id=variant_id,
                variant_version=_variant_version(config, variant_id),
                final_output_path=final_path,
                rule_versions={"delivery": _variant_version(config, variant_id)},
            )
            for variant_id, final_path in final_paths.items()
        )

        cache_root = _material_cache_root()
        image_risk = _has_image_layout_risk(material_context)
        provider = (
            _qualified_office_provider(
                cache_root / "office-layout-capability.json",
            )
            if image_risk
            else OfficeImageProvider.WORD
        )
        if cancel_check():
            raise MaterialAssemblyCancelled(AssemblyStage.PREFLIGHT)

        # Active execution must never run the legacy insertion module.  If an
        # unrelated legacy image survived context routing, blocking is safer
        # than silently dropping it or inserting it twice.
        if list(getattr(config, "images", ()) or ()):
            raise _preflight_error(
                "legacy image insertion cannot be combined with the "
                "transactional material assembly chain"
            )

        adapter = _WorkbenchMaterialPipelineAdapter(
            config=config,
            output_dir=output_dir,
            output_suffix=output_suffix,
            progress_cb=progress_cb,
            cancel_check=cancel_check,
            force_delivery_presets=force_delivery_presets,
            official_master=official_master,
            image_rule_tokens=tuple(rule.anchor_token for rule in image_rules),
            document_structure_evidence=document_structure_evidence,
            document_scope_decisions=tuple(document_scope_decisions or ()),
        )
        request = MaterialAssemblyRequest(
            source_docx_path=str(input_path),
            profile=profile,
            frozen_field_values=dict(material_context.frozen_field_values),
            material_schema_id=schema_id,
            material_schema_version=schema_version,
            variants=variants,
            office_provider=provider,
            rule_versions=_ASSEMBLY_RULE_VERSIONS,
            image_rules=image_rules,
            image_source_items=image_sources,
            runtime_image_watermark_text=material_context.image_watermark_text,
            image_cache_dir=str(cache_root / "images"),
            work_root=str(cache_root / "work"),
        )
        receipt = MaterialAssemblyService(adapter).execute(
            request,
            cancel_check=cancel_check,
        )
        result = adapter.result
        if result is None:
            raise _preflight_error(
                "material pipeline completed without returning PipelineResult"
            )
        result.output_paths = {
            item.variant.variant_id: item.final_output.path
            for item in receipt.variants
        }
        result.material_assembly_receipt = receipt
        result.material_assembly_error = None
        attachment_receipts, attachment_errors = _process_attachment_bundles(
            input_path=input_path,
            output_dir=output_dir,
            receipt=receipt,
            provider=provider,
            image_cache_dir=cache_root / "images",
            cancel_check=cancel_check,
        )
        result.attachment_bundle_receipts = attachment_receipts
        result.attachment_bundle_errors = attachment_errors
        if attachment_errors:
            attachment_cancelled = _attachment_processing_was_cancelled(
                attachment_errors
            )
            result.status = (
                "cancelled" if attachment_cancelled else "partial_success"
            )
            result.cancelled = attachment_cancelled
            if attachment_cancelled:
                result.success = False
            result.failed_items.extend(
                {
                    "kind": "attachment_bundle",
                    "role": role,
                    "error": str(error),
                    "diagnostics": [
                        item.to_dict() for item in error.diagnostics
                    ],
                }
                for role, error in attachment_errors.items()
            )
            detail = "; ".join(
                f"{role}: {error}" for role, error in attachment_errors.items()
            )
            result.error = (
                f"{result.error}; {detail}" if result.error else detail
            )
        progress_cb(
            1,
            1,
            (
                "Material assembly cancelled after core publication"
                if result.cancelled
                else "Material assembly completed"
            ),
        )
        return MaterialAssemblyRuntimeOutcome(
            result=result,
            elapsed_seconds=time.perf_counter() - started_at,
            modules_enabled=adapter.modules_enabled,
            modules_total=adapter.modules_total,
        )
    except MaterialAssemblyError as exc:
        result = _failed_assembly_result(
            exc,
            config=config,
            pipeline_result=adapter.result if adapter is not None else None,
        )
        return MaterialAssemblyRuntimeOutcome(
            result=result,
            elapsed_seconds=time.perf_counter() - started_at,
            modules_enabled=(adapter.modules_enabled if adapter else 0),
            modules_total=(adapter.modules_total if adapter else modules_total),
        )
    except Exception as exc:
        error = _preflight_error(str(exc) or type(exc).__name__)
        result = _failed_assembly_result(
            error,
            config=config,
            pipeline_result=adapter.result if adapter is not None else None,
        )
        return MaterialAssemblyRuntimeOutcome(
            result=result,
            elapsed_seconds=time.perf_counter() - started_at,
            modules_enabled=(adapter.modules_enabled if adapter else 0),
            modules_total=(adapter.modules_total if adapter else modules_total),
        )


class _WorkbenchMaterialPipelineAdapter:
    """One callback invocation, one PipelineResult, and exact stage targets."""

    def __init__(
        self,
        *,
        config,
        output_dir: Path,
        output_suffix: str,
        progress_cb,
        cancel_check,
        force_delivery_presets: bool,
        official_master,
        image_rule_tokens: tuple[str, ...],
        document_structure_evidence,
        document_scope_decisions: tuple[object, ...],
    ) -> None:
        self.config = config
        self.output_dir = output_dir
        self.output_suffix = output_suffix
        self.progress_cb = progress_cb
        self.cancel_check = cancel_check
        self.force_delivery_presets = force_delivery_presets
        self.official_master = official_master
        self.image_rule_tokens = image_rule_tokens
        self.document_structure_evidence = document_structure_evidence
        self.document_scope_decisions = document_scope_decisions
        self.result: PipelineResult | None = None
        self.modules_enabled = 0
        self.modules_total = 0

    def __call__(self, request, *, cancel_check=None) -> MaterialPipelineOutcome:
        effective_cancel = cancel_check or self.cancel_check
        terminal_owner = pipeline_terminal_assembly_owner(self.config)
        if terminal_owner:
            raise RuntimeError(
                f"terminal assembler '{terminal_owner}' must execute outside "
                "the generic material staging transaction"
            )
        modules = create_all_modules()
        selection = build_module_selection_plan(
            modules,
            self.config.is_module_enabled,
        )
        enabled = list(selection.select_modules(modules))
        enabled = [
            module
            for module in enabled
            if str(module.meta.name or "") != "image_insertion"
        ]
        self.modules_enabled = len(enabled)
        self.modules_total = len(modules)

        overrides = {
            target.variant_id: target.owned_stage_output_path
            for target in request.targets
        }
        pipeline = Pipeline(
            modules=enabled,
            config=self.config,
            output_dir=str(self.output_dir),
            output_suffix=self.output_suffix,
            progress_callback=self.progress_cb,
            cancel_check=effective_cancel,
            force_delivery_presets=self.force_delivery_presets,
            official_master=self.official_master,
            logical_source_path=request.logical_source_path,
            output_path_overrides=overrides,
            output_paths_are_owned_stages=True,
            defer_field_refresh=True,
            document_structure_evidence=self.document_structure_evidence,
            document_scope_decisions=self.document_scope_decisions,
        )
        self.result = pipeline.execute(request.prepared_input.path)
        if self.result.status == "cancelled" or self.result.cancelled:
            raise MaterialAssemblyCancelled(AssemblyStage.PIPELINE)
        if not self.result.success:
            raise RuntimeError(
                str(self.result.error or "formatting pipeline failed during staging")
            )
        _verify_pipeline_stage_paths(self.result, request.targets)
        evidence = _visibility_evidence(
            self.result,
            request.targets,
            config=self.config,
        )
        removed_by_variant = {
            item.variant_id: frozenset(item.removed_content_image_markers)
            for item in evidence
        }
        for target in request.targets:
            stage_path = Path(target.owned_stage_output_path)
            if _variant_has_pending_image_work(
                stage_path,
                image_rule_tokens=self.image_rule_tokens,
                removed_content_markers=removed_by_variant[target.variant_id],
            ):
                continue
            _best_effort_refresh_staged_fields(stage_path)
        return MaterialPipelineOutcome(visibility_evidence=evidence)


def _entity_profile(context: MaterialExecutionContext) -> EntityProfile:
    return EntityProfile(
        profile_id=context.profile_id or "workbench-profile",
        profile_name=context.profile_name or "Workbench material",
        fields=dict(context.frozen_field_values),
        assets_dir=context.entity_assets_dir,
        field_scopes=dict(context.field_scopes),
        field_functions=dict(context.field_functions),
        timeline_plans=dict(context.timeline_plans),
        field_aliases=dict(context.field_aliases),
        image_material_rules=dict(context.image_material_rules),
        content_bindings=dict(context.content_bindings),
        content_rules=list(context.content_rules),
        attachment_bindings=dict(context.attachment_bindings),
    )


def _material_schema_contract(
    context: MaterialExecutionContext,
) -> tuple[str, str]:
    schema_ids = tuple(context.material_schema_ids)
    if not schema_ids:
        return "workbench-context", "v1"
    versions = tuple(
        str(getattr(MATERIAL_SCHEMA_MAP.get(schema_id), "version", "unregistered"))
        for schema_id in schema_ids
    )
    return "+".join(schema_ids), "+".join(versions)


def _process_attachment_bundles(
    *,
    input_path: Path,
    output_dir: Path,
    receipt,
    provider: OfficeImageProvider,
    image_cache_dir: Path,
    cancel_check,
) -> tuple[dict[str, object], dict[str, AttachmentBundleProcessingError]]:
    bindings = tuple(receipt.intake_snapshot.attachment_bindings)
    if not bindings:
        return {}, {}
    root = output_dir / f"{input_path.stem}_attachments"
    receipts: dict[str, object] = {}
    errors: dict[str, AttachmentBundleProcessingError] = {}
    try:
        service = AttachmentBundleService()
    except Exception as exc:
        error = _attachment_runtime_error(
            "attachment_service_initialization_failed",
            str(exc) or type(exc).__name__,
        )
        return {}, {binding.role: error for binding in bindings}
    role_directories: dict[str, str] = {}
    for binding in bindings:
        directory_name = _safe_attachment_role_directory(binding.role)
        collision_role = role_directories.get(directory_name.casefold())
        if collision_role is not None:
            errors[binding.role] = AttachmentBundleProcessingError(
                (
                    AttachmentProcessingDiagnostic(
                        code="attachment_role_output_collision",
                        message=(
                            f"roles {collision_role!r} and {binding.role!r} "
                            "map to the same output directory"
                        ),
                    ),
                )
            )
            continue
        role_directories[directory_name.casefold()] = binding.role
        try:
            receipts[binding.role] = service.process(
                AttachmentBundleBuildRequest(
                    snapshot=receipt.intake_snapshot,
                    dependency_index=receipt.dependency_index,
                    binding_role=binding.role,
                    final_directory=str(root / directory_name),
                    image_cache_dir=str(image_cache_dir),
                    office_provider=provider,
                ),
                cancel_check=cancel_check,
            )
        except AttachmentBundleProcessingError as exc:
            errors[binding.role] = exc
        except Exception as exc:
            errors[binding.role] = _attachment_runtime_error(
                "attachment_bundle_unexpected_failure",
                str(exc) or type(exc).__name__,
            )
    return receipts, errors


def _attachment_processing_was_cancelled(
    errors: Mapping[str, AttachmentBundleProcessingError],
) -> bool:
    return any(
        str(diagnostic.code or "").casefold().endswith("cancelled")
        for error in errors.values()
        for diagnostic in error.diagnostics
    )


def _safe_attachment_role_directory(role: str) -> str:
    value = str(role or "").strip()
    safe = "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "_"
        for char in value
    ).strip(" .")
    return safe or "attachment"


def _attachment_runtime_error(
    code: str,
    message: str,
) -> AttachmentBundleProcessingError:
    return AttachmentBundleProcessingError(
        (
            AttachmentProcessingDiagnostic(
                code=code,
                message=message,
            ),
        )
    )


def _variant_version(config, variant_id: str) -> str:
    preset = next(
        (
            item
            for item in list(getattr(config, "delivery_presets", ()) or ())
            if str(getattr(item, "preset_id", "") or "") == variant_id
        ),
        None,
    )
    if preset is None:
        return "pipeline-final-v1"
    payload = _plain_value(preset)
    digest = sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return f"delivery-preset-{digest[:16]}"


def _material_cache_root() -> Path:
    local_appdata = str(os.getenv("LOCALAPPDATA") or "").strip()
    base = Path(local_appdata) if local_appdata else Path.home() / "AppData" / "Local"
    root = base / APP_DATA_DIR_NAME / "cache" / "material-execution"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _qualified_office_provider(
    cache_path: Path,
) -> OfficeImageProvider:
    return resolve_office_layout_capability(cache_path).provider


def _has_image_layout_risk(context: MaterialExecutionContext) -> bool:
    if _has_active_image_rule(context):
        return True
    repository = ContentArtifactRepository(CONFIG_LIBRARY_ROOT / "content_artifacts")
    for binding in context.content_bindings.values():
        try:
            artifact = repository.validate(binding.artifact_ref)
        except ContentArtifactRepositoryError:
            # Snapshot preflight will report the invalid artifact. Until then,
            # retain the stricter layout capability requirement.
            return True
        if any(
            resource.media_type.casefold().startswith("image/")
            for resource in artifact.manifest.resources
        ):
            return True
    return False


def _verify_pipeline_stage_paths(result: PipelineResult, targets) -> None:
    actual = {
        str(key): Path(value).resolve()
        for key, value in dict(result.output_paths or {}).items()
    }
    expected = {
        target.variant_id: Path(target.owned_stage_output_path).resolve()
        for target in targets
    }
    if actual != expected or any(not path.is_file() for path in actual.values()):
        raise RuntimeError(
            "pipeline violated the material staging contract: output paths do not "
            "match the assembler-owned targets"
        )


def _visibility_evidence(result: PipelineResult, targets, *, config):
    receipts = dict(
        getattr(getattr(result, "context", None), "content_visibility_receipts", None)
        or {}
    )
    evidence: list[PipelineVisibilityEvidence] = []
    for target in targets:
        raw = receipts.get(target.variant_id)
        if raw is None:
            if _variant_declares_visibility_rules(config, target.variant_id):
                raise RuntimeError(
                    f"variant {target.variant_id!r} declared visibility rules but "
                    "returned no visibility receipt"
                )
            evidence.append(
                PipelineVisibilityEvidence(
                    variant_id=target.variant_id,
                    kind=VisibilityEvidenceKind.NOT_APPLICABLE,
                    not_applicable_reason=(
                        "variant has no content visibility transformation"
                    ),
                )
            )
            continue
        if not isinstance(raw, Mapping):
            raise RuntimeError(
                f"variant {target.variant_id!r} returned an invalid visibility receipt"
            )
        if not str(raw.get("receipt_id") or "").strip():
            raise RuntimeError(
                f"variant {target.variant_id!r} returned no canonical visibility receipt"
            )
        try:
            receipt = BlockVisibilityReceipt.from_dict(raw)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"variant {target.variant_id!r} returned a corrupted visibility receipt: {exc}"
            ) from exc
        evidence.append(
            PipelineVisibilityEvidence(
                variant_id=target.variant_id,
                kind=VisibilityEvidenceKind.RECEIPT,
                visibility_receipt_id=receipt.receipt_id,
                removed_content_image_markers=receipt.removed_content_image_markers,
            )
        )
    return tuple(evidence)


def _variant_declares_visibility_rules(config, variant_id: str) -> bool:
    return any(
        str(getattr(preset, "preset_id", "") or "") == variant_id
        and bool(list(getattr(preset, "content_visibility_rules", ()) or ()))
        for preset in list(getattr(config, "delivery_presets", ()) or ())
    )


def _variant_has_pending_image_work(
    path: Path,
    *,
    image_rule_tokens: tuple[str, ...],
    removed_content_markers: frozenset[str],
) -> bool:
    try:
        document = Document(str(path))
        for part in document.part.package.parts:
            root = getattr(part, "_element", None)
            if root is None:
                continue
            text = "".join(item.text or "" for item in root.iter(qn("w:t")))
            if any(token in text for token in image_rule_tokens):
                return True
            for bookmark in root.iter(qn("w:bookmarkStart")):
                name = str(bookmark.get(qn("w:name")) or "")
                if (
                    name.startswith(_CONTENT_IMAGE_MARKER_PREFIX)
                    and name not in removed_content_markers
                ):
                    return True
        return False
    except Exception:
        # Planning owns authoritative DOCX validation; avoid an extra Office
        # open when this cheap advisory inspection cannot prove there is no job.
        return True


def _best_effort_refresh_staged_fields(path: Path) -> None:
    try:
        document = Document(str(path))
        if document_has_toc(document):
            refresh_doc_fields_with_word(str(path), timeout_sec=30)
    except Exception:
        return


def _failed_assembly_result(
    error: MaterialAssemblyError,
    *,
    config,
    pipeline_result: PipelineResult | None,
) -> PipelineResult:
    if pipeline_result is not None:
        result = pipeline_result
        result.success = False
        result.status = (
            "cancelled"
            if isinstance(error, MaterialAssemblyCancelled)
            else "failed"
        )
        result.cancelled = isinstance(error, MaterialAssemblyCancelled)
        result.output_paths = {}
        result.error = str(error)
        result.config = config
    else:
        result = PipelineResult(
            success=False,
            status=(
                "cancelled"
                if isinstance(error, MaterialAssemblyCancelled)
                else "failed"
            ),
            error=str(error),
            cancelled=isinstance(error, MaterialAssemblyCancelled),
            config=config,
        )
    result.material_assembly_receipt = None
    result.material_assembly_error = error
    result.attachment_bundle_receipts = {}
    result.attachment_bundle_errors = {}
    return result


def _preflight_error(message: str) -> MaterialAssemblyError:
    return MaterialAssemblyError(
        (
            AssemblyDiagnostic(
                code=AssemblyFailureCode.INVALID_REQUEST,
                stage=AssemblyStage.PREFLIGHT,
                message=message or "material assembly preflight failed",
            ),
        )
    )


def _plain_value(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _plain_value(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _plain_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_value(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


__all__ = [
    "MaterialAssemblyRuntimeOutcome",
    "material_assembly_is_active",
    "run_workbench_material_assembly",
]
