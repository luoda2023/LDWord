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
)
from src.assistant.contracts.document_plan import DocumentPlan
from src.assistant.contracts.execution import ExecutionApproval, PreflightReceipt
from src.assistant.contracts.material_snapshot import MaterialContextSnapshot
from src.assistant.contracts.task_plan import CAPABILITY_EXECUTABLE
from src.config.execution_target import resolve_execution_target
from src.config.library import (
    get_scene_entry,
    get_template_entry,
    load_scene_from_library,
    load_template_from_library,
)
from src.config.material_context import MaterialExecutionContext
from src.config.scene_family_application import apply_planned_scene_family_defaults
from src.services.exam_markdown_source import load_exam_markdown_source
from src.services.production_execution import ProductionExecutionRequest, execute_production_request


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
        material_context: MaterialExecutionContext | None = None,
    ) -> PreflightReceipt:
        input_path = Path(str(plan.production_input_ref.get("path") or "")).expanduser()
        output_root = Path(plan.output_policy.output_root or (input_path.parent if input_path.name else ""))
        scene_id = str(plan.scene_ref.get("id") or "")
        template_id = str(plan.template_ref.get("id") or "")
        issues: list[str] = []
        warnings: list[str] = []
        fingerprints: dict[str, str] = {}
        material_snapshot = MaterialContextSnapshot.capture(material_context)
        material_digest = material_snapshot.digest
        fingerprints["materials"] = material_digest
        expected_material_digest = str(
            plan.material_snapshot_ref.get("digest") or ""
        )
        if (
            expected_material_digest
            and expected_material_digest != material_digest
        ):
            issues.append("material_context_digest_mismatch")
        if material_snapshot.has_resolution_errors:
            issues.append("material_context_resolution_failed")
        _append_material_context_findings(
            plan,
            material_snapshot.restore(),
            issues=issues,
        )
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
        return PreflightReceipt(
            preflight_id=uuid4().hex,
            plan_id=plan.plan_id,
            plan_revision=plan.revision,
            plan_fingerprint=plan.fingerprint,
            input_hash=input_hash,
            material_context_digest=material_digest,
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
        material_context: MaterialExecutionContext | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> dict[str, object]:
        if plan.fingerprint != preflight.plan_fingerprint:
            return _failed("plan_changed_after_preflight")
        if not approval.authorizes(preflight):
            return _failed("execution_approval_mismatch")
        material_snapshot = MaterialContextSnapshot.capture(material_context)
        expected_material_digest = str(
            plan.material_snapshot_ref.get("digest") or ""
        )
        if (
            material_snapshot.digest != preflight.material_context_digest
            or (
                expected_material_digest
                and material_snapshot.digest != expected_material_digest
            )
        ):
            return _failed("material_context_changed_after_preflight")
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
            material_context=(material_context or MaterialExecutionContext()),
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
    issues: list[str],
    warnings: list[str],
) -> None:
    if plan.production_contract.validator_id != "exam_items_v1":
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
                )
            )


def _append_material_context_findings(
    plan: DocumentPlan,
    material_context: MaterialExecutionContext,
    *,
    issues: list[str],
) -> None:
    if str(plan.capability_ref.route_id or "") != "bidding_document_authoring":
        return
    if not material_context.package_id:
        issues.append("bidding_material_package_missing")
    if "bid_materials_v1" not in set(material_context.material_schema_ids):
        issues.append("bidding_material_schema_mismatch")
    fields = material_context.resolved_entity_data()
    for key in ("company_name", "project_name", "legal_person"):
        if not str(fields.get(key) or "").strip():
            issues.append(f"bidding_material_field_missing:{key}")
    roles = {
        str(item.role or "").strip().casefold()
        for item in material_context.asset_items
        if str(item.path or "").strip()
    }
    for role in ("logo", "seal"):
        if role not in roles:
            issues.append(f"bidding_material_asset_missing:{role}")


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
