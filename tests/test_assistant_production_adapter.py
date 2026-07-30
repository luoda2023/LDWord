from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from docx import Document

from src.assistant.adapters import production_adapter as module
from src.assistant.adapters.production_adapter import AssistantProductionAdapter
from src.assistant.adapters.workspace_state_adapter import WorkspaceSnapshot
from src.assistant.application.plan_builder import FormDocumentPlanBuilder
from src.assistant.contracts.document_plan import DocumentPlan, OutputPolicy
from src.assistant.contracts.execution import ExecutionApproval


def _plan(input_path: Path, output_root: Path) -> DocumentPlan:
    return DocumentPlan(
        plan_id="assistant-plan-1",
        revision=1,
        intent="统一排版",
        created_by_turn_id="turn-1",
        input_document_ref={"path": str(input_path), "name": input_path.name},
        work_mode_id="custom",
        scene_ref={"id": "custom"},
        template_ref={"id": "default"},
        output_policy=OutputPolicy(output_root=str(output_root)),
    )


def _patch_resources(monkeypatch, tmp_path):
    scene_path = tmp_path / "scene.json"
    template_path = tmp_path / "template.json"
    scene_path.write_text("scene-v1", encoding="utf-8")
    template_path.write_text("template-v1", encoding="utf-8")
    scene_entry = SimpleNamespace(path=scene_path, is_available=True, source_type="builtin")
    template_entry = SimpleNamespace(path=template_path, is_available=True, source_type="builtin")
    monkeypatch.setattr(module, "get_scene_entry", lambda *_args, **_kwargs: scene_entry)
    monkeypatch.setattr(module, "get_template_entry", lambda *_args, **_kwargs: template_entry)
    monkeypatch.setattr(module, "load_scene_from_library", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(module, "load_template_from_library", lambda *_args, **_kwargs: object())
    return scene_path, template_path


def _approval(preflight):
    return ExecutionApproval(
        approval_id="approval-1",
        session_id="session-1",
        plan_id=preflight.plan_id,
        plan_revision=preflight.plan_revision,
        preflight_hash=preflight.evidence_hash,
        input_hash=preflight.input_hash,
        output_root=preflight.output_root,
        overwrite_policy="deny",
        approved_at="2026-07-16T00:00:00+00:00",
    )


def test_preflight_binds_input_plan_and_resource_hashes(tmp_path, monkeypatch):
    input_path = tmp_path / "input.docx"
    Document().save(input_path)
    _patch_resources(monkeypatch, tmp_path)
    plan = _plan(input_path, tmp_path / "out")

    preflight = AssistantProductionAdapter().build_preflight(plan)

    assert preflight.ready
    assert preflight.plan_fingerprint == plan.fingerprint
    assert preflight.input_hash == module.file_sha256(input_path)
    assert set(preflight.resource_fingerprints) == {
        "materials",
        "scene",
        "template",
    }
    assert preflight.resource_fingerprints["materials"] == (
        preflight.material_context_digest
    )


def test_approved_plan_is_the_only_path_to_form_execution(tmp_path, monkeypatch):
    input_path = tmp_path / "input.docx"
    Document().save(input_path)
    _patch_resources(monkeypatch, tmp_path)
    calls = []

    def executor(request, **kwargs):
        calls.append((request, kwargs))
        return {
            "status": "success",
            "output_path": str(tmp_path / "out" / "result.docx"),
            "output_paths": {},
            "report_paths": [],
            "failed_count": 0,
            "artifact_failure_count": 0,
            "error_text": "",
        }

    adapter = AssistantProductionAdapter(executor=executor)
    plan = _plan(input_path, tmp_path / "out")
    preflight = adapter.build_preflight(plan)
    result = adapter.execute_approved_plan(plan, preflight, _approval(preflight))

    assert result["status"] == "success"
    assert result["assistant_input_hash_unchanged"] is True
    assert calls[0][0].input_path == input_path
    assert calls[0][0].plan_id == "custom"


def test_execution_rejects_changed_input_or_resource(tmp_path, monkeypatch):
    input_path = tmp_path / "input.docx"
    Document().save(input_path)
    scene_path, _template_path = _patch_resources(monkeypatch, tmp_path)
    calls = []
    adapter = AssistantProductionAdapter(executor=lambda *_args, **_kwargs: calls.append(1) or {})
    plan = _plan(input_path, tmp_path / "out")
    preflight = adapter.build_preflight(plan)
    approval = _approval(preflight)

    input_path.write_bytes(input_path.read_bytes() + b"changed")
    assert adapter.execute_approved_plan(plan, preflight, approval)["error_text"] == "input_changed_after_preflight"
    assert calls == []

    Document().save(input_path)
    fresh = adapter.build_preflight(plan)
    fresh_approval = _approval(fresh)
    scene_path.write_text("scene-v2", encoding="utf-8")
    assert adapter.execute_approved_plan(plan, fresh, fresh_approval)["error_text"] == "approved_resource_changed"
    assert calls == []


def test_qualification_archive_plan_projects_family_and_package_delivery(tmp_path):
    input_path = tmp_path / "qualification-index.docx"
    Document().save(input_path)
    workspace = WorkspaceSnapshot(
        mode_id="custom",
        mode_label="通用版",
        scene_id="custom",
        scene_source_type="builtin",
        template_id="default",
        template_source_type="builtin",
        input_path=str(input_path),
        input_name=input_path.name,
        input_exists=True,
        material_summary={
            "package_id": "qualification-main",
            "profile_id": "company-a",
            "field_count": 2,
            "asset_count": 2,
        },
    )
    plan = FormDocumentPlanBuilder().build(
        query="整理投标资质证书材料",
        workspace=workspace,
        turn_id="turn-qualification",
    )
    plan = DocumentPlan.from_dict(
        {
            **plan.to_dict(),
            "output_policy": {
                "output_root": str(tmp_path / "out"),
                "filename_suffix": "_archive",
                "overwrite": False,
            },
        }
    )
    captured = []

    def executor(request, **_kwargs):
        captured.append(request)
        output_root = Path(request.output_root)
        output_root.mkdir(parents=True, exist_ok=True)
        manifest = output_root / "material_manifest.json"
        package = output_root / "qualification.zip"
        manifest.write_text("{}", encoding="utf-8")
        package.write_bytes(b"PK-package")
        return {
            "status": "success",
            "output_path": "",
            "output_paths": {},
            "report_paths": [],
            "material_manifest_paths": {"material": str(manifest)},
            "material_package_paths": {"zip": str(package)},
            "failed_count": 0,
            "artifact_failure_count": 0,
            "error_text": "",
        }

    adapter = AssistantProductionAdapter(executor=executor)
    preflight = adapter.build_preflight(plan)
    result = adapter.execute_approved_plan(
        plan,
        preflight,
        _approval(preflight),
    )

    assert preflight.ready, preflight.issues
    assert result["status"] == "success"
    assert captured
    request = captured[0]
    assert request.scene.input_source_profile.material_schema_id == (
        "qualification_archive_assets_v1"
    )
    assert request.scene.default_delivery_preset_id == "attachment_package"
    assert {
        item.preset_id for item in request.scene.delivery_presets
    } == {
        "attachment_package",
        "missing_items_report",
        "archive_manifest",
    }
