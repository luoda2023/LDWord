"""Synchronous production-execution facade for GUI, CLI, and assistant."""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
import hashlib
import json
from pathlib import Path

from src.application.materials import (
    ExecutionMaterialFinalizeRequest,
    ExecutionMaterialSnapshot,
    finalize_execution_material_snapshot,
)
from src.config.execution_target import resolve_execution_target
from src.config.document_structure_contract import (
    DocumentStructureEvidence,
    RegionDecision,
)
from src.config.resolver import resolve_config
from src.config.scene import SceneWorkspace
from src.config.scene_surface_registry import (
    scene_uses_exam_paper_surface,
    scene_uses_official_document_surface,
)
from src.config.template import TemplateConfig
from src.config.work_mode import execution_work_mode_issue, resolve_work_mode_id
from src.pipeline.runner import plan_pipeline_output_paths
from src.services.execution_session.support import file_sha256
from src.services.document_structure_evidence import (
    build_document_structure_evidence,
    document_structure_evidence_is_current,
)
from src.services.production_runtime.execution_runtime import (
    WorkbenchProductionRunner,
)


ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


@dataclass(frozen=True, slots=True)
class ProductionExecutionRequest:
    input_path: Path
    output_root: Path
    mode_id: str
    scene: SceneWorkspace
    template: TemplateConfig
    plan_id: str
    plan_path: str = ""
    plan_source_type: str = ""
    template_id: str = ""
    template_path: str = ""
    template_source_type: str = ""
    document_type_id: str = ""
    output_suffix: str = "_formatted"
    exam_scale_profile_id: str = ""
    exam_visual_quality_required: bool = False
    require_format_change: bool = False
    session_overrides: Mapping[str, object] = field(default_factory=dict)
    material_snapshot: ExecutionMaterialSnapshot | None = None
    document_structure_evidence: DocumentStructureEvidence | None = None
    document_scope_decisions: tuple[RegionDecision, ...] = ()


def execute_production_request(
    request: ProductionExecutionRequest,
    *,
    progress_callback: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
) -> dict[str, object]:
    input_path = Path(request.input_path).expanduser().resolve()
    output_root = Path(request.output_root).expanduser().resolve()
    if not input_path.is_file():
        return _terminal("failed", f"input_document_missing:{input_path}")
    suffix = input_path.suffix.casefold()
    exam_markdown = (
        suffix in {".md", ".markdown"}
        and scene_uses_exam_paper_surface(
            request.scene,
            mode_id=request.mode_id,
        )
    )
    official_draft = (
        suffix == ".json"
        and scene_uses_official_document_surface(
            request.scene,
            mode_id=request.mode_id,
        )
    )
    if suffix != ".docx" and not exam_markdown and not official_draft:
        return _terminal(
            "failed",
            f"input_document_unsupported:{input_path.suffix}",
        )
    if output_root.exists() and not output_root.is_dir():
        return _terminal(
            "failed",
            f"output_root_is_not_directory:{output_root}",
        )
    scene = copy.deepcopy(request.scene)
    mode_issue = execution_work_mode_issue(
        scene,
        requested_mode_id=request.mode_id,
    )
    if mode_issue:
        return _terminal("failed", mode_issue)
    mode_id = resolve_work_mode_id(
        scene,
        requested_mode_id=request.mode_id,
    )
    structure_evidence = request.document_structure_evidence
    scope_decisions = tuple(request.document_scope_decisions or ())
    if suffix == ".docx" and mode_id not in {"official", "exam"}:
        if structure_evidence is None:
            structure_evidence = build_document_structure_evidence(input_path)
        elif not document_structure_evidence_is_current(structure_evidence, input_path):
            return _terminal("failed", "document_structure_evidence_stale")
        if not structure_evidence.ready:
            return _terminal(
                "failed",
                ";".join(structure_evidence.issues)
                or "document_structure_evidence_not_ready",
            )
    snapshot = request.material_snapshot
    if snapshot is not None:
        if not snapshot.execution_ready:
            snapshot, issues = finalize_production_material_snapshot(
                request,
                snapshot,
                input_path=input_path,
                output_root=output_root,
                scene=scene,
                mode_id=mode_id,
            )
            if snapshot is None:
                return _terminal(
                    "failed",
                    ",".join(issues)
                    or "execution_material_snapshot_not_finalized",
                )
        if snapshot.work_mode_id != mode_id:
            return _terminal("failed", "execution_material_mode_mismatch")
        if (
            request.document_type_id
            and snapshot.document_type
            and request.document_type_id != snapshot.document_type
        ):
            return _terminal(
                "failed",
                "execution_material_document_type_mismatch",
            )
    output_root.mkdir(parents=True, exist_ok=True)
    runner = WorkbenchProductionRunner(
        doc_path=str(input_path),
        template=copy.deepcopy(request.template),
        scene=scene,
        session_overrides=dict(request.session_overrides),
        material_snapshot=snapshot,
        output_dir=output_root,
        output_suffix=request.output_suffix,
        document_type_id=request.document_type_id,
        exam_scale_profile_id=request.exam_scale_profile_id,
        exam_visual_quality_required=request.exam_visual_quality_required,
        require_format_change=request.require_format_change,
        document_scope_context=(structure_evidence, scope_decisions),
    )
    try:
        return runner.run(
            progress_callback or (lambda _current, _total, _message: None),
            cancel_check or (lambda: False),
        )
    except KeyboardInterrupt:
        return _terminal("cancelled", "execution_cancelled_by_keyboard_interrupt")
    except Exception as exc:
        return _terminal("failed", f"{type(exc).__name__}: {exc}")


def finalize_production_material_snapshot(
    request: ProductionExecutionRequest,
    snapshot: ExecutionMaterialSnapshot,
    *,
    input_path: Path | None = None,
    output_root: Path | None = None,
    scene: SceneWorkspace | None = None,
    mode_id: str = "",
) -> tuple[ExecutionMaterialSnapshot | None, tuple[str, ...]]:
    """Finalize one bound material record against the real production plan."""

    if not isinstance(snapshot, ExecutionMaterialSnapshot):
        return None, ("execution_material_snapshot_type_invalid",)
    if len(snapshot.records) != 1:
        return None, ("single_document_execution_requires_one_material_record",)
    source = Path(input_path or request.input_path).expanduser().resolve()
    destination = Path(output_root or request.output_root).expanduser().resolve()
    active_scene = copy.deepcopy(scene or request.scene)
    active_mode = str(mode_id or request.mode_id or "").strip()
    record = snapshot.records[0]
    values = dict(record.field_values)
    owners = dict(record.field_owners)
    try:
        config = resolve_config(
            copy.deepcopy(request.template),
            active_scene,
            dict(request.session_overrides),
            entity_data=values,
            field_scopes=owners,
            exact_material_placeholders=True,
        )
        planned = plan_pipeline_output_paths(
            source,
            config,
            output_dir=destination,
            output_suffix=request.output_suffix,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return None, (f"execution_output_plan_failed:{type(exc).__name__}",)
    if not planned:
        return None, ("execution_output_plan_empty",)

    target = resolve_execution_target(
        mode_id=active_mode,
        scene=active_scene,
        document_path=str(source),
        official_document_type_id=request.document_type_id,
    )
    if target.issues:
        return None, tuple(target.issues)
    template_revision = _production_template_revision(request)
    if target.master_path:
        master_path = Path(target.master_path).expanduser()
        if not master_path.is_file():
            return None, ("approved_master_missing",)
        master_id = target.master_id
        master_revision = "sha256:" + file_sha256(master_path)
    else:
        master_id = "pipeline.generic.v1"
        master_revision = "sha256:" + hashlib.sha256(
            b"alavette.pipeline.generic.master.v1"
        ).hexdigest()
    finalized = finalize_execution_material_snapshot(
        ExecutionMaterialFinalizeRequest(
            snapshot=snapshot,
            template_id=(
                str(request.template_id or "").strip()
                or str(getattr(request.template, "name", "") or "").strip()
                or "workbench.inline.template"
            ),
            template_revision=template_revision,
            master_id=master_id,
            master_revision=master_revision,
            recipe_version=1,
            output_root=str(destination),
            output_paths=tuple(str(path) for path in planned.values()),
            supported_field_keys=tuple(sorted(values)),
            supported_resource_roles=tuple(sorted(snapshot.resource_domains)),
        )
    )
    if not finalized.ok or finalized.snapshot is None:
        return None, tuple(item.code for item in finalized.issues)
    return finalized.snapshot, ()


def _production_template_revision(
    request: ProductionExecutionRequest,
) -> str:
    configured = str(request.template_path or "").strip()
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return "sha256:" + file_sha256(path)
    template = request.template
    payload = asdict(template) if is_dataclass(template) else repr(template)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _terminal(status: str, error_text: str) -> dict[str, object]:
    return {
        "status": status,
        "output_path": "",
        "output_paths": {},
        "report_paths": [],
        "failed_count": 0 if status == "cancelled" else 1,
        "artifact_failure_count": 0,
        "error_text": error_text,
    }


__all__ = ["ProductionExecutionRequest", "execute_production_request"]
