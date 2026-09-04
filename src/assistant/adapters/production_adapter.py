"""Approved Assistant document plans routed into Form's production facade."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
import hashlib
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from src.assistant.domain.exam_authoring_contract import (
    generated_exam_blockers,
    generated_exam_warnings,
)
from src.assistant.contracts.document_plan import DocumentPlan
from src.assistant.contracts.execution import ExecutionApproval, PreflightReceipt
from src.application.materials import (
    ExecutionMaterialFinalizeRequest,
    ExecutionMaterialSnapshot,
    finalize_execution_material_snapshot,
)
from src.assistant.contracts.material_snapshot import MaterialExecutionEnvelope
from src.assistant.contracts.task_plan import CAPABILITY_EXECUTABLE
from src.config.execution_target import resolve_execution_target
from src.config.library import (
    get_scene_entry,
    get_template_entry,
    load_scene_from_library,
    load_template_from_library,
)
from src.config.scene_family_application import apply_planned_scene_family_defaults
from src.config.resolver import resolve_config
from src.config.scene_surface_registry import scene_uses_exam_paper_surface
from src.pipeline.runner import plan_pipeline_output_paths
from src.services.exam_markdown_source import load_exam_markdown_source
from src.services.production_execution import (
    ProductionExecutionRequest,
    execute_production_request,
    production_material_template_contract,
)
from src.services.production_runtime.material_artifacts import (
    plan_material_artifact_paths,
)
from src.shared.engine.exam_question_schema import (
    exam_delivery_filename_stem,
    plan_exam_delivery_output_paths,
)
from src.shared.engine.exam_markdown_content import inspect_exam_markdown_payload
from src.config.official_document_profiles import (
    get_official_document_assembly_contract,
)
from src.services.official_draft_source import load_official_draft_source


AUTHORING_ONLY_MATERIAL_WARNING = (
    "当前资料与目标文档模式不同，已作为内容起草依据使用；"
    "正式生产将仅使用已生成并校验的结构化草稿。"
)
MATERIAL_USAGE_AUTHORING_ONLY = "authoring_only"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class AssistantProductionAdapter:
    def __init__(
        self,
        *,
        executor: Callable[..., dict[str, object]] = execute_production_request,
    ) -> None:
        self._executor = executor

    def build_preflight(
        self,
        plan: DocumentPlan,
        *,
        material_snapshot: ExecutionMaterialSnapshot | None = None,
    ) -> PreflightReceipt:
        input_path = Path(str(plan.production_input_ref.get("path") or "")).expanduser()
        output_root = Path(plan.output_policy.output_root or (input_path.parent if input_path.name else ""))
        scene_id = str(plan.scene_ref.get("id") or "")
        template_id = str(plan.template_ref.get("id") or "")
        issues: list[str] = []
        warnings: list[str] = []
        fingerprints: dict[str, str] = {}
        material_envelope = MaterialExecutionEnvelope.capture(material_snapshot)
        material_digest = material_envelope.digest
        fingerprints["materials"] = material_digest
        expected_material_digest = str(
            plan.material_snapshot_ref.get("digest") or ""
        )
        if (
            expected_material_digest
            and expected_material_digest != material_digest
        ):
            issues.append("material_snapshot_digest_mismatch")
        execution_material, material_usage_issue = (
            _execution_material_snapshot_for_plan(
                plan,
                material_snapshot,
            )
        )
        if material_usage_issue == "execution_material_mode_mismatch":
            issues.append(material_usage_issue)
        elif material_usage_issue == MATERIAL_USAGE_AUTHORING_ONLY:
            warnings.append(AUTHORING_ONLY_MATERIAL_WARNING)
            fingerprints["material_usage"] = MATERIAL_USAGE_AUTHORING_ONLY
        input_hash = ""
        if (
            plan.capability_ref.capability_id
            and plan.capability_ref.status != CAPABILITY_EXECUTABLE
        ):
            issues.append("assistant_capability_not_executable")
        issues.extend(
            f"plan_blocked:{item.code}"
            for item in plan.blocking_issues
        )
        if not input_path.is_file():
            issues.append("input_document_missing")
        elif input_path.suffix.casefold() not in set(
            plan.production_contract.accepted_suffixes or (".docx",)
        ):
            issues.append("input_document_unsupported")
        elif (
            input_path.suffix.casefold() == ".docx"
            and not _valid_delivery_artifact(
                input_path,
                artifact_key="final_docx",
            )
        ):
            issues.append("input_document_invalid")
        else:
            input_hash = file_sha256(input_path)
            source = plan.production_input_artifact
            if (
                source is not None
                and source.digest.startswith("sha256:")
                and source.digest != f"sha256:{input_hash}"
            ):
                issues.append("input_artifact_digest_mismatch")
            _append_domain_input_findings(
                plan,
                input_path,
                material_snapshot=execution_material,
                issues=issues,
                warnings=warnings,
            )
        if not plan.work_mode_id:
            issues.append("work_mode_missing")
        scene_entry = get_scene_entry(scene_id, mode_id=plan.work_mode_id) if scene_id else None
        if scene_entry is None or not scene_entry.is_available:
            issues.append("scene_unavailable")
        else:
            fingerprints["scene"] = _entry_fingerprint(scene_entry.path)
        projected_scene = None
        if scene_entry is not None and scene_entry.is_available:
            try:
                projected_scene = deepcopy(
                    load_scene_from_library(scene_id, mode_id=plan.work_mode_id)
                )
                projection_issue = _apply_plan_scene_contract(
                    projected_scene,
                    plan,
                )
                if projection_issue:
                    issues.append(projection_issue)
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                issues.append(
                    f"assistant_scene_projection_failed:{type(exc).__name__}"
                )
        template_entry = (
            get_template_entry(template_id, mode_id=plan.work_mode_id)
            if template_id
            else None
        )
        if template_entry is None or not template_entry.is_available:
            issues.append("template_unavailable")
        else:
            fingerprints["template"] = _entry_fingerprint(template_entry.path)
        if (
            scene_entry is not None
            and scene_entry.is_available
            and plan.production_contract.terminal_assembler in {"exam", "official"}
        ):
            try:
                scene = projected_scene or load_scene_from_library(
                    scene_id,
                    mode_id=plan.work_mode_id,
                )
                target = resolve_execution_target(
                    mode_id=plan.work_mode_id,
                    scene=scene,
                    document_path=str(input_path),
                    official_document_type_id=(
                        plan.production_contract.document_type_id
                    ),
                )
                issues.extend(target.issues)
                if target.master_path:
                    master_path = Path(target.master_path)
                    if master_path.is_file():
                        fingerprints["master"] = file_sha256(master_path)
                    else:
                        issues.append("approved_master_missing")
            except (OSError, RuntimeError, ValueError) as exc:
                issues.append(f"execution_target_unresolved:{type(exc).__name__}")
        if output_root.exists() and not output_root.is_dir():
            issues.append("output_root_is_not_directory")
        if input_path and output_root:
            try:
                if input_path.resolve() == output_root.resolve():
                    issues.append("output_root_overwrites_input_document")
            except OSError:
                issues.append("execution_path_resolution_failed")
        if plan.output_policy.overwrite:
            warnings.append("output_replacement_requested")
        if (
            execution_material is not None
            and not issues
            and projected_scene is not None
            and template_entry is not None
        ):
            try:
                projected_template = load_template_from_library(
                    template_id,
                    mode_id=plan.work_mode_id,
                )
                finalized_snapshot, finalize_issues = (
                    _finalize_material_snapshot_for_plan(
                        plan,
                        execution_material,
                        scene=projected_scene,
                        template=projected_template,
                        template_path=template_entry.path,
                        input_path=input_path,
                        output_root=output_root,
                    )
                )
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                issues.append(
                    f"execution_material_finalize_failed:{type(exc).__name__}"
                )
            else:
                issues.extend(finalize_issues)
                if finalized_snapshot is not None:
                    fingerprints["execution_material"] = (
                        finalized_snapshot.snapshot_id
                    )
        return PreflightReceipt(
            preflight_id=uuid4().hex,
            plan_id=plan.plan_id,
            plan_revision=plan.revision,
            plan_fingerprint=plan.fingerprint,
            input_hash=input_hash,
            material_snapshot_digest=material_digest,
            output_root=str(output_root),
            ready=not issues,
            issues=tuple(issues),
            warnings=tuple(warnings),
            resource_fingerprints=fingerprints,
        )

    def execute_approved_plan(
        self,
        plan: DocumentPlan,
        preflight: PreflightReceipt,
        approval: ExecutionApproval,
        *,
        material_snapshot: ExecutionMaterialSnapshot | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> dict[str, object]:
        if plan.fingerprint != preflight.plan_fingerprint:
            return _failed("plan_changed_after_preflight")
        if not approval.authorizes(preflight):
            return _failed("execution_approval_mismatch")
        material_envelope = MaterialExecutionEnvelope.capture(material_snapshot)
        expected_material_digest = str(
            plan.material_snapshot_ref.get("digest") or ""
        )
        if (
            material_envelope.digest != preflight.material_snapshot_digest
            or (
                expected_material_digest
                and material_envelope.digest != expected_material_digest
            )
        ):
            return _failed("material_snapshot_changed_after_preflight")
        execution_material, material_usage_issue = (
            _execution_material_snapshot_for_plan(
                plan,
                material_snapshot,
            )
        )
        if material_usage_issue == "execution_material_mode_mismatch":
            return _failed(material_usage_issue)
        if material_usage_issue == MATERIAL_USAGE_AUTHORING_ONLY and (
            preflight.resource_fingerprints.get("material_usage")
            != MATERIAL_USAGE_AUTHORING_ONLY
            or "execution_material" in preflight.resource_fingerprints
        ):
            return _failed("execution_material_policy_changed_after_preflight")
        input_path = Path(str(plan.production_input_ref.get("path") or "")).expanduser()
        if not input_path.is_file() or file_sha256(input_path) != preflight.input_hash:
            return _failed("input_changed_after_preflight")
        scene_id = str(plan.scene_ref.get("id") or "")
        template_id = str(plan.template_ref.get("id") or "")
        scene_entry = get_scene_entry(scene_id, mode_id=plan.work_mode_id)
        template_entry = get_template_entry(template_id, mode_id=plan.work_mode_id)
        if scene_entry is None or template_entry is None:
            return _failed("approved_resource_missing")
        if (
            _entry_fingerprint(scene_entry.path) != preflight.resource_fingerprints.get("scene")
            or _entry_fingerprint(template_entry.path)
            != preflight.resource_fingerprints.get("template")
        ):
            return _failed("approved_resource_changed")
        scene = deepcopy(load_scene_from_library(scene_id, mode_id=plan.work_mode_id))
        projection_issue = _apply_plan_scene_contract(scene, plan)
        if projection_issue:
            return _failed(projection_issue)
        template = load_template_from_library(template_id, mode_id=plan.work_mode_id)
        master_fingerprint = preflight.resource_fingerprints.get("master")
        if master_fingerprint:
            target = resolve_execution_target(
                mode_id=plan.work_mode_id,
                scene=scene,
                document_path=str(input_path),
                official_document_type_id=plan.production_contract.document_type_id,
            )
            if (
                not target.master_path
                or not Path(target.master_path).is_file()
                or file_sha256(Path(target.master_path)) != master_fingerprint
            ):
                return _failed("approved_resource_changed")
        if execution_material is not None:
            try:
                execution_material, finalize_issues = (
                    _finalize_material_snapshot_for_plan(
                        plan,
                        execution_material,
                        scene=scene,
                        template=template,
                        template_path=template_entry.path,
                        input_path=input_path,
                        output_root=Path(preflight.output_root),
                    )
                )
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                return _failed(
                    f"execution_material_finalize_failed:{type(exc).__name__}"
                )
            if finalize_issues or execution_material is None:
                return _failed(
                    "execution_material_finalize_blocked:"
                    + ",".join(finalize_issues or ("unknown",))
                )
            if (
                execution_material.snapshot_id
                != preflight.resource_fingerprints.get("execution_material")
            ):
                return _failed("execution_material_changed_after_preflight")
        request = ProductionExecutionRequest(
            input_path=input_path,
            output_root=Path(preflight.output_root),
            mode_id=plan.work_mode_id,
            scene=scene,
            template=template,
            plan_id=scene_id,
            plan_path=str(scene_entry.path),
            plan_source_type=scene_entry.source_type,
            template_id=template_id,
            template_path=str(template_entry.path),
            template_source_type=template_entry.source_type,
            document_type_id=plan.production_contract.document_type_id,
            output_suffix=plan.output_policy.filename_suffix,
            exam_scale_profile_id=str(
                plan.scene_ref.get("scale_profile_id") or ""
            ),
            exam_visual_quality_required=(
                plan.production_contract.terminal_assembler == "exam"
            ),
            material_snapshot=execution_material,
        )
        result = self._executor(
            request,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )
        if not isinstance(result, Mapping):
            return _failed("production_executor_returned_invalid_result")
        payload = dict(result)
        payload.setdefault("output_path", "")
        payload.setdefault("output_paths", {})
        payload.setdefault("report_paths", [])
        missing_delivery = _missing_delivery_artifacts(plan, payload)
        if missing_delivery and str(payload.get("status") or "") == "success":
            payload["status"] = "failed"
            payload["error_text"] = (
                "delivery_contract_incomplete:" + ",".join(missing_delivery)
            )
        try:
            payload["assistant_input_hash_unchanged"] = (
                input_path.is_file() and file_sha256(input_path) == preflight.input_hash
            )
        except OSError:
            payload["assistant_input_hash_unchanged"] = False
        payload["assistant_plan_id"] = plan.plan_id
        payload["assistant_plan_revision"] = plan.revision
        payload["assistant_approval_id"] = approval.approval_id
        return payload


def _finalize_material_snapshot_for_plan(
    plan: DocumentPlan,
    snapshot: ExecutionMaterialSnapshot,
    *,
    scene,
    template,
    template_path: Path,
    input_path: Path,
    output_root: Path,
) -> tuple[ExecutionMaterialSnapshot | None, tuple[str, ...]]:
    """Freeze the exact production resources and outputs before execution."""

    if len(snapshot.records) > 1:
        return None, ("single_document_execution_requires_one_material_record",)
    record = snapshot.records[0] if snapshot.records else None
    values = dict(record.field_values) if record is not None else {}
    owners = dict(record.field_owners) if record is not None else {}
    output_root = Path(output_root).expanduser().resolve()
    target = resolve_execution_target(
        mode_id=plan.work_mode_id,
        scene=scene,
        document_path=str(input_path),
        official_document_type_id=plan.production_contract.document_type_id,
    )
    if target.issues:
        return None, tuple(target.issues)
    try:
        config = resolve_config(
            template,
            scene,
            {},
            entity_data=values,
            field_scopes=owners,
            exact_material_placeholders=True,
        )
        if (
            input_path.suffix.casefold() in {".md", ".markdown"}
            and scene_uses_exam_paper_surface(
                scene,
                mode_id=plan.work_mode_id,
            )
        ):
            import_result = load_exam_markdown_source(input_path)
            planned = plan_exam_delivery_output_paths(
                config,
                output_dir=output_root,
                source_stem=exam_delivery_filename_stem(
                    payload=import_result.payload,
                    fallback=input_path.stem,
                ),
            )
        else:
            planned = plan_pipeline_output_paths(
                input_path,
                config,
                output_dir=output_root,
                output_suffix=plan.output_policy.filename_suffix,
            )
        planned.update(
            plan_material_artifact_paths(
                input_path=input_path,
                output_dir=output_root,
                config=config,
            )
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return None, (
            f"execution_output_plan_failed:{type(exc).__name__}",
        )
    if not planned:
        return None, ("execution_output_plan_empty",)
    template_revision = "sha256:" + file_sha256(Path(template_path))
    if target.master_path:
        master_path = Path(target.master_path)
        if not master_path.is_file():
            return None, ("approved_master_missing",)
        master_id = target.master_id
        master_revision = "sha256:" + file_sha256(master_path)
    else:
        master_id = "pipeline.generic.v1"
        master_revision = "sha256:" + hashlib.sha256(
            b"alavette.pipeline.generic.master.v1"
        ).hexdigest()
    supported_fields, supported_roles, contract_issues = (
        production_material_template_contract(input_path, snapshot)
    )
    if contract_issues:
        return None, contract_issues
    finalized = finalize_execution_material_snapshot(
        ExecutionMaterialFinalizeRequest(
            snapshot=snapshot,
            template_id=str(plan.template_ref.get("id") or ""),
            template_revision=template_revision,
            master_id=master_id,
            master_revision=master_revision,
            recipe_version=1,
            output_root=str(output_root),
            output_paths=tuple(str(path) for path in planned.values()),
            supported_field_keys=tuple(sorted(supported_fields)),
            supported_resource_roles=tuple(sorted(supported_roles)),
        )
    )
    if not finalized.ok or finalized.snapshot is None:
        return None, tuple(item.code for item in finalized.issues)
    return finalized.snapshot, ()


def _execution_material_snapshot_for_plan(
    plan: DocumentPlan,
    snapshot: ExecutionMaterialSnapshot | None,
) -> tuple[ExecutionMaterialSnapshot | None, str]:
    """Separate authoring evidence from material injected into production."""

    if snapshot is None or snapshot.work_mode_id == plan.work_mode_id:
        return snapshot, ""
    source = plan.production_input_artifact
    if source is not None and source.source_kind == "assistant_generated":
        return None, MATERIAL_USAGE_AUTHORING_ONLY
    return None, "execution_material_mode_mismatch"


def public_execution_result(result: Mapping[str, object]) -> dict[str, object]:
    """Return a model-safe result without absolute local paths."""

    output = {
        "status": str(result.get("status") or "failed"),
        "failed_count": int(result.get("failed_count") or 0),
        "artifact_failure_count": int(result.get("artifact_failure_count") or 0),
        "error_text": str(result.get("error_text") or ""),
        "input_hash_unchanged": bool(result.get("assistant_input_hash_unchanged", False)),
    }
    paths: list[str] = []
    output_path = str(result.get("output_path") or "")
    if output_path:
        paths.append(Path(output_path).name)
    raw_paths = result.get("output_paths")
    if isinstance(raw_paths, Mapping):
        paths.extend(Path(str(value)).name for value in raw_paths.values() if str(value))
    for key in ("material_manifest_paths", "material_package_paths"):
        raw_material_paths = result.get(key)
        if isinstance(raw_material_paths, Mapping):
            paths.extend(
                Path(str(value)).name
                for value in raw_material_paths.values()
                if str(value) and Path(str(value)).suffix
            )
    output["artifact_names"] = sorted(set(paths))
    return output


def _entry_fingerprint(path: Path) -> str:
    return file_sha256(Path(path))


def _append_domain_input_findings(
    plan: DocumentPlan,
    input_path: Path,
    *,
    material_snapshot: ExecutionMaterialSnapshot | None,
    issues: list[str],
    warnings: list[str],
) -> None:
    validator_id = plan.production_contract.validator_id
    if validator_id == "official_document_draft_v1":
        try:
            source = load_official_draft_source(input_path)
        except (OSError, TypeError, ValueError) as exc:
            issues.append(
                f"official_draft_source_invalid:{type(exc).__name__}"
            )
            return
        if (
            plan.production_contract.document_type_id
            and source.document_type_id
            != plan.production_contract.document_type_id
        ):
            issues.append("official_draft_document_type_mismatch")
        material_values = _single_material_field_values(material_snapshot)
        merged_values = {**dict(source.fields), **material_values}
        issues.extend(
            f"official_draft_field_missing:{key}"
            for key in _official_required_field_keys(
                source.document_type_id,
                merged_values,
            )
        )
        warnings.extend(
            f"official_draft_warning:{message}"
            for message in source.warnings
        )
        return
    if validator_id == "official_document_v1":
        document_type_id = str(
            plan.production_contract.document_type_id or ""
        ).strip()
        values = _single_material_field_values(material_snapshot)
        if material_snapshot is None:
            issues.append("official_material_snapshot_required")
        issues.extend(
            f"official_material_field_missing:{key}"
            for key in _official_required_field_keys(
                document_type_id,
                values,
            )
        )
        return
    if validator_id != "exam_items_v1":
        return
    try:
        result = load_exam_markdown_source(input_path)
    except (OSError, UnicodeError, ValueError) as exc:
        issues.append(f"exam_source_invalid:{type(exc).__name__}")
        return
    if result.error_count:
        issues.extend(
            f"exam_source_error:{item.kind}"
            for item in result.issues
            if str(item.severity or "").casefold() == "error"
        )
    if result.summary.question_count < 1:
        issues.append("exam_source_error:question_count_zero")
    warnings.extend(
        f"exam_source_warning:{item.kind}"
        for item in result.issues
        if str(item.severity or "").casefold() != "error"
    )
    for finding in inspect_exam_markdown_payload(result.payload):
        code = f"{finding.kind}:{finding.path}"
        if finding.severity == "error":
            issues.append(f"exam_source_error:{code}")
        else:
            warnings.append(f"exam_source_warning:{code}")
    source = plan.production_input_artifact
    if source is not None and source.source_kind == "assistant_generated":
        try:
            markdown = input_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            issues.append("exam_source_error:generated_source_unreadable")
        else:
            issues.extend(
                f"exam_source_error:{code}"
                for code in generated_exam_blockers(
                    markdown,
                    result,
                    intent=plan.intent,
                    scene_id=str(plan.scene_ref.get("id") or ""),
                    scale_profile_id=str(
                        plan.scene_ref.get("scale_profile_id") or ""
                    ),
                )
            )
            warnings.extend(
                f"exam_source_warning:{code}"
                for code in generated_exam_warnings(
                    markdown,
                    result,
                    intent=plan.intent,
                    scene_id=str(plan.scene_ref.get("id") or ""),
                    scale_profile_id=str(
                        plan.scene_ref.get("scale_profile_id") or ""
                    ),
                )
            )


def _single_material_field_values(
    snapshot: ExecutionMaterialSnapshot | None,
) -> dict[str, str]:
    if snapshot is None or not snapshot.records:
        return {}
    if len(snapshot.records) != 1:
        return {}
    return dict(snapshot.records[0].field_values)


def _official_required_field_keys(
    document_type_id: str,
    values: Mapping[str, object],
) -> tuple[str, ...]:
    contract = get_official_document_assembly_contract(document_type_id)
    if contract is None:
        return ("document_type",)
    return tuple(
        binding.field_key
        for binding in contract.field_bindings
        if binding.required
        and not str(values.get(binding.field_key) or "").strip()
    )


def _missing_delivery_artifacts(
    plan: DocumentPlan,
    payload: Mapping[str, object],
) -> tuple[str, ...]:
    required = tuple(plan.delivery_contract.required_artifact_keys)
    if not required:
        return ()
    output_path = str(payload.get("output_path") or "").strip()
    raw_paths = payload.get("output_paths")
    output_paths = (
        {str(key): str(value) for key, value in raw_paths.items() if str(value)}
        if isinstance(raw_paths, Mapping)
        else {}
    )
    missing: list[str] = []
    for key in required:
        if (
            key == "final_docx"
            and output_path
            and _valid_delivery_artifact(Path(output_path), artifact_key=key)
        ):
            continue
        if key == "material_manifest":
            manifest_paths = payload.get("material_manifest_paths")
            manifest_path = (
                str(manifest_paths.get("material") or "")
                if isinstance(manifest_paths, Mapping)
                else ""
            )
            if not manifest_path:
                manifest_path = str(
                    output_paths.get("archive_manifest")
                    or output_paths.get("archive_manifest_md")
                    or ""
                )
            if manifest_path and _valid_delivery_artifact(
                Path(manifest_path),
                artifact_key=key,
            ):
                continue
        if key == "material_package":
            package_paths = payload.get("material_package_paths")
            package_path = (
                str(package_paths.get("zip") or "")
                if isinstance(package_paths, Mapping)
                else ""
            )
            if package_path and _valid_delivery_artifact(
                Path(package_path),
                artifact_key=key,
            ):
                continue
        artifact_path = output_paths.get(key, "")
        if not artifact_path or not _valid_delivery_artifact(
            Path(artifact_path),
            artifact_key=key,
        ):
            missing.append(key)
    return tuple(missing)


def _valid_delivery_artifact(path: Path, *, artifact_key: str = "") -> bool:
    if not path.is_file():
        return False
    try:
        if path.stat().st_size <= 0:
            return False
    except OSError:
        return False
    if artifact_key in {
        "final_docx",
        "student",
        "answer_key",
        "teacher",
        "analysis",
        "answer_sheet",
    } and path.suffix.casefold() != ".docx":
        return False
    if path.suffix.casefold() != ".docx":
        return True
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
    except (OSError, BadZipFile):
        return False
    return {"[Content_Types].xml", "word/document.xml"} <= names


def _apply_exam_delivery_contract(scene: object, plan: DocumentPlan) -> None:
    if plan.production_contract.terminal_assembler != "exam":
        return
    exam_paper = getattr(scene, "exam_paper", None)
    if exam_paper is None:
        return
    required = set(plan.delivery_contract.required_artifact_keys)
    if required == {"student"}:
        exam_paper.answer_policy = "student_only"
    elif required == {"answer_key"}:
        exam_paper.answer_policy = "answer_only"
    else:
        exam_paper.answer_policy = "student_plus_answer"


def _apply_plan_scene_contract(scene: object, plan: DocumentPlan) -> str:
    """Project the approved route family and delivery onto one runtime scene."""

    if plan.production_contract.terminal_assembler == "exam":
        master_id = str(plan.scene_ref.get("master_id") or "").strip()
        if master_id:
            scene.master_id = master_id
    elif plan.production_contract.terminal_assembler == "official":
        master_id = str(plan.production_contract.master_id or "").strip()
        if master_id:
            scene.master_id = master_id

    family_id = str(plan.scene_ref.get("family_id") or "").strip()
    if family_id:
        try:
            application = apply_planned_scene_family_defaults(
                scene,
                family_id=family_id,
            )
        except (KeyError, TypeError, ValueError) as exc:
            return (
                f"assistant_scene_family_projection_failed:{family_id}:"
                f"{type(exc).__name__}"
            )
        if not application.applied:
            return f"assistant_scene_family_not_applicable:{family_id}"

    _apply_exam_delivery_contract(scene, plan)
    preset_id = str(plan.delivery_contract.default_preset_id or "").strip()
    if not preset_id:
        return ""
    preset_ids = {
        str(getattr(item, "preset_id", "") or "").strip()
        for item in tuple(getattr(scene, "delivery_presets", ()) or ())
        if str(getattr(item, "preset_id", "") or "").strip()
    }
    if preset_id not in preset_ids:
        return f"assistant_delivery_preset_unavailable:{preset_id}"
    scene.default_delivery_preset_id = preset_id
    return ""


def _failed(message: str) -> dict[str, object]:
    return {
        "status": "failed",
        "output_path": "",
        "output_paths": {},
        "report_paths": [],
        "failed_count": 0,
        "artifact_failure_count": 0,
        "error_text": message,
    }


__all__ = [
    "AssistantProductionAdapter",
    "file_sha256",
    "public_execution_result",
]
