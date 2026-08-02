from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from docx import Document

from src.application.materials import (
    ExecutionMaterialRecord,
    ExecutionMaterialSnapshot,
    project_execution_material_record_snapshot,
)
from src.config.scene import SceneWorkspace
from src.config.builtin_templates import create_builtin_template
from src.config.template import TemplateConfig
from src.domain.materials import MaterialPackageRef, MaterialRunSelection
from src.services.docx_format_change import compare_docx_formatting
from src.services.execution_run_log import append_execution_run
from src.services.production_execution import (
    ProductionExecutionRequest,
    execute_production_request,
)
from src.services.document_structure_evidence import build_document_structure_evidence
from src.services.production_runtime.formatting_runtime import (
    apply_required_format_change_policy,
)
from src.modules.fill.entity_fill import EntityFillModule
from src.ui.panels.workbench.document_input_manifest import (
    discover_document_inputs,
)
from src.ui.panels.workbench.execution_session_controller import (
    ExecutionBuildResult,
    WorkbenchExecutionSessionController,
    _FileProductionRunner,
    _ProductionRunner,
    _batch_format_change_evidence,
)


def _record(record_id: str, display_name: str) -> ExecutionMaterialRecord:
    return ExecutionMaterialRecord(
        record_id=record_id,
        display_name=display_name,
        group_id="",
        field_values={},
        field_owners={},
        resources={},
        resource_owners={},
    )


def _snapshot(*records: ExecutionMaterialRecord) -> ExecutionMaterialSnapshot:
    return ExecutionMaterialSnapshot(
        snapshot_id="",
        run_id="run-test",
        package_ref=MaterialPackageRef(
            package_id=f"pkg_{'a' * 32}",
            revision=f"sha256:{'b' * 64}",
        ),
        work_mode_id="custom",
        material_contract_id="generic_document_v1",
        recipe_id="document_batch",
        scene_id="custom",
        document_type="",
        package_display_name="Materials",
        package_field_values={},
        package_field_owners={},
        groups=(),
        records=records,
    )


def _selection() -> MaterialRunSelection:
    return MaterialRunSelection(
        package_ref=MaterialPackageRef(
            package_id=f"pkg_{'a' * 32}",
            revision=f"sha256:{'b' * 64}",
        ),
        selected_record_ids=(f"rec_{'c' * 32}",),
    )


def test_material_selection_builds_the_formatting_runner(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "source.docx"
    Document().save(source)
    snapshot = _snapshot(_record(f"rec_{'c' * 32}", "Record"))
    monkeypatch.setattr(
        "src.ui.panels.workbench.execution_session_controller."
        "bind_workbench_material",
        lambda *_args, **_kwargs: (snapshot, ()),
    )
    monkeypatch.setattr(
        "src.ui.panels.workbench.execution_session_controller."
        "build_threaded_runner",
        lambda runner, **_kwargs: ExecutionBuildResult(worker=runner),
    )
    controller = WorkbenchExecutionSessionController(
        resolve_document_path=lambda: source,
    )
    mapped_root = tmp_path / "outputs" / "source"
    evidence = build_document_structure_evidence(source)

    build = controller.build_file_batch_worker(
        document_paths=(str(source),),
        template=TemplateConfig(name="Template"),
        scene=SceneWorkspace(mode_id="custom"),
        selection=_selection(),
        mode_id="custom",
        template_id="template",
        output_root=str(tmp_path / "outputs"),
        output_roots_by_path={str(source).casefold(): str(mapped_root)},
        document_structure_evidence=evidence,
    )

    assert isinstance(build.worker, _ProductionRunner)
    request = build.worker._request
    assert request.material_snapshot is not None
    assert request.require_format_change is True
    assert request.output_root == mapped_root
    assert request.output_suffix == "-formatted"
    assert request.document_structure_evidence is evidence


def test_multiple_material_records_each_enter_production_formatting(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "source.docx"
    Document().save(source)
    first = _record(f"rec_{'c' * 32}", "First")
    second = _record(f"rec_{'d' * 32}", "Second")
    snapshot = _snapshot(first, second)
    monkeypatch.setattr(
        "src.ui.panels.workbench.execution_session_controller."
        "bind_workbench_material",
        lambda *_args, **_kwargs: (snapshot, ()),
    )
    monkeypatch.setattr(
        "src.ui.panels.workbench.execution_session_controller."
        "build_threaded_runner",
        lambda runner, **_kwargs: ExecutionBuildResult(worker=runner),
    )
    controller = WorkbenchExecutionSessionController(
        resolve_document_path=lambda: source,
    )
    output_root = tmp_path / "outputs"

    build = controller.build_record_batch_worker(
        document_paths=(str(source),),
        template=TemplateConfig(name="Template"),
        scene=SceneWorkspace(mode_id="custom"),
        selection=_selection(),
        mode_id="custom",
        template_id="template",
        output_root=str(output_root),
    )

    assert isinstance(build.worker, _FileProductionRunner)
    assert [
        request.material_snapshot.records[0].record_id
        for request in build.worker._requests
    ] == [first.record_id, second.record_id]
    assert {
        request.output_root.name for request in build.worker._requests
    } == {"First", "Second"}


def test_material_fields_are_filled_inside_production_pipeline(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "source.docx"
    document = Document()
    document.add_paragraph("{{@text:client}}")
    document.save(source)
    record = replace(
        _record(f"rec_{'c' * 32}", "Record"),
        field_values={"client": "ACME"},
        field_owners={"client": "record"},
    )
    monkeypatch.setattr(
        "src.services.production_runtime.execution_runtime.create_all_modules",
        lambda: [EntityFillModule()],
    )

    result = execute_production_request(
        ProductionExecutionRequest(
            input_path=source,
            output_root=tmp_path / "outputs",
            mode_id="custom",
            scene=SceneWorkspace(mode_id="custom"),
            template=create_builtin_template("default", mode_id="custom"),
            plan_id="custom",
            template_id="default",
            output_suffix="-formatted",
            material_snapshot=_snapshot(record),
        )
    )

    output = Path(str(result["output_path"]))
    assert result["status"] == "success"
    assert result["modules_enabled"] == 1
    assert Document(output).paragraphs[0].text == "ACME"


def test_record_projection_resets_stale_finalization():
    record = _record(f"rec_{'c' * 32}", "Record")
    snapshot = _snapshot(record)
    finalized_shape = replace(
        snapshot,
        template_id="old-template",
        template_revision=f"sha256:{'1' * 64}",
        master_id="old-master",
        master_revision=f"sha256:{'2' * 64}",
        output_root="C:\\old",
        output_paths=("C:\\old\\result.docx",),
        preflight_receipt={"status": "passed"},
    )

    projected = project_execution_material_record_snapshot(
        finalized_shape,
        record.record_id,
    )

    assert projected.records == (record,)
    assert not projected.execution_ready
    assert projected.template_id == ""
    assert projected.output_paths == ()


def test_output_root_cannot_contain_the_input_document(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    output_root.mkdir()
    source = output_root / "source.docx"
    Document().save(source)
    controller = WorkbenchExecutionSessionController(
        resolve_document_path=lambda: source,
    )

    build = controller.build_file_batch_worker(
        document_paths=(str(source),),
        template=TemplateConfig(name="Template"),
        scene=SceneWorkspace(mode_id="custom"),
        selection=None,
        mode_id="custom",
        output_root=str(output_root),
    )

    assert build.worker is None
    assert build.error_text.startswith("workbench_output_root_contains_input:")


def test_output_planning_rejects_same_stem_collision(tmp_path):
    docx_source = tmp_path / "source.docx"
    markdown_source = tmp_path / "source.md"
    Document().save(docx_source)
    markdown_source.write_text("# source", encoding="utf-8")
    controller = WorkbenchExecutionSessionController(
        resolve_document_path=lambda: docx_source,
    )

    build = controller.build_file_batch_worker(
        document_paths=(str(docx_source), str(markdown_source)),
        template=TemplateConfig(name="Template"),
        scene=SceneWorkspace(mode_id="custom"),
        selection=None,
        mode_id="custom",
        output_root=str(tmp_path / "outputs"),
    )

    assert build.worker is None
    assert build.error_text.startswith("workbench_output_path_collision:")


def test_manifest_does_not_reingest_alavette_output_directories(tmp_path):
    Document().save(tmp_path / "source.docx")
    generated = tmp_path / "Alavette-Output" / "通用文档"
    generated.mkdir(parents=True)
    Document().save(generated / "generated.docx")

    manifest = discover_document_inputs(
        (str(tmp_path),),
        accepted_suffixes=(".docx",),
    )

    assert [Path(item.source_path).name for item in manifest.documents] == [
        "source.docx"
    ]


def test_semantic_format_evidence_ignores_noop_package_rewrite(tmp_path):
    source = tmp_path / "source.docx"
    document = Document()
    document.add_paragraph("Body")
    document.save(source)
    noop = tmp_path / "noop.docx"
    Document(source).save(noop)
    changed = tmp_path / "changed.docx"
    modified = Document(source)
    modified.paragraphs[0].runs[0].bold = True
    modified.save(changed)

    noop_evidence = compare_docx_formatting(source, noop)
    changed_evidence = compare_docx_formatting(source, changed)

    assert noop_evidence["format_changed"] is False
    assert changed_evidence["format_changed"] is True


def test_content_evidence_ignores_run_segmentation(tmp_path):
    source = tmp_path / "source.docx"
    original = Document()
    original.add_paragraph("Body")
    original.save(source)
    segmented = tmp_path / "segmented.docx"
    modified = Document(source)
    paragraph = modified.paragraphs[0]
    paragraph.clear()
    paragraph.add_run("Bo")
    paragraph.add_run("dy")
    modified.save(segmented)

    evidence = compare_docx_formatting(source, segmented)

    assert evidence["content_changed"] is False


def test_required_format_change_downgrades_noop_success():
    payload = {"status": "success", "summary": "done"}
    evidence = {"status": "compared", "format_changed": False}

    apply_required_format_change_policy(payload, evidence, required=True)

    assert payload["status"] == "partial_success"
    assert payload["warnings"][0].startswith("formatting_noop:")


def test_batch_format_evidence_reports_any_unchanged_document():
    evidence = _batch_format_change_evidence(
        [
            {
                "format_change_evidence": {
                    "status": "compared",
                    "format_changed": True,
                }
            },
            {
                "format_change_evidence": {
                    "status": "compared",
                    "format_changed": False,
                }
            },
        ]
    )

    assert evidence["format_changed"] is False
    assert evidence["documents_unchanged"] == 1


def test_execution_receipt_persists_branch_and_format_evidence(tmp_path):
    path = append_execution_run(
        {
            "status": "partial_success",
            "execution_route": "production_with_material",
            "input_paths": ["C:/input.docx"],
            "output_path": "C:/output.docx",
            "format_change_evidence": {
                "schema_version": "docx-format-change-v1",
                "status": "compared",
                "format_changed": False,
            },
        },
        log_root=tmp_path,
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["execution_route"] == "production_with_material"
    assert payload["format_change_evidence"]["format_changed"] is False
