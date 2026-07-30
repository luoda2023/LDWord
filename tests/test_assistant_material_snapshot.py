from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from docx import Document

from src.assistant.adapters.production_adapter import AssistantProductionAdapter
from src.assistant.adapters.workspace_state_adapter import WorkspaceSnapshot
from src.assistant.application.document_job_controller import DocumentJobController
from src.assistant.application.plan_builder import FormDocumentPlanBuilder
from src.assistant.contracts.material_snapshot import MaterialContextSnapshot
from src.config.material_context import MaterialExecutionContext


def _workspace(source: Path) -> WorkspaceSnapshot:
    return WorkspaceSnapshot(
        mode_id="custom",
        mode_label="通用版",
        scene_id="custom",
        scene_source_type="builtin",
        template_id="default",
        template_source_type="builtin",
        input_path=str(source),
        input_name=source.name,
        input_exists=True,
        material_summary={},
    )


def test_material_snapshot_round_trip_is_frozen_and_content_addressed():
    live = MaterialExecutionContext(
        package_id="package-a",
        profile_id="profile-a",
        entity_data={"project_name": "Alpha"},
    )

    snapshot = MaterialContextSnapshot.capture(live)
    restored = snapshot.restore()

    assert restored.field_values_frozen is True
    assert restored.resolved_entity_data() == {"project_name": "Alpha"}
    assert snapshot.reference()["digest"] == snapshot.digest
    assert snapshot.reference()["field_count"] == 1

    tampered = snapshot.to_dict()
    tampered["context"]["frozen_field_values"]["project_name"] = "Beta"
    with pytest.raises(ValueError, match="digest mismatch"):
        MaterialContextSnapshot.from_dict(tampered)


def test_approved_plan_rejects_material_drift_before_executor_runs(tmp_path):
    source = tmp_path / "source.docx"
    document = Document()
    document.add_paragraph("Stable production input")
    document.save(source)
    approved_material = MaterialExecutionContext(
        entity_data={"project_name": "Alpha"}
    )
    snapshot = MaterialContextSnapshot.capture(approved_material)
    plan = FormDocumentPlanBuilder().build(
        query="统一这份 Word 文档格式",
        workspace=_workspace(source),
        turn_id="turn-material-binding",
        route_id_override="quick_formatting_general",
    )
    plan = replace(plan, material_snapshot_ref=snapshot.reference())
    executor_calls: list[object] = []

    def _executor(request, **_kwargs):
        executor_calls.append(request)
        return {
            "status": "success",
            "output_path": "",
            "output_paths": {},
            "report_paths": [],
            "failed_count": 0,
            "artifact_failure_count": 0,
            "error_text": "",
        }

    adapter = AssistantProductionAdapter(executor=_executor)
    preflight = adapter.build_preflight(
        plan,
        material_context=snapshot.restore(),
    )
    assert preflight.ready is True, preflight.issues
    approval = DocumentJobController.approve(
        session_id="session-material-binding",
        plan=plan,
        preflight=preflight,
    )

    result = adapter.execute_approved_plan(
        plan,
        preflight,
        approval,
        material_context=MaterialExecutionContext(
            entity_data={"project_name": "Beta"}
        ),
    )

    assert result["status"] == "failed"
    assert result["error_text"] == "material_context_changed_after_preflight"
    assert executor_calls == []
