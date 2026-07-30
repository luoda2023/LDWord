import builtins
import json
import subprocess
import sys
from pathlib import Path

import pytest
from docx import Document


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.resolved import ResolvedConfig  # noqa: E402
from src.config.scene import (  # noqa: E402
    ComplianceProfile,
    DeliveryPreset,
    InputSourceProfile,
    ObjectPreflightPolicy,
)
from src.pipeline.runner import Pipeline  # noqa: E402
from src.report_writer import write_json_report, write_markdown_report  # noqa: E402
from src.shared.engine.scene_journey_runtime import (  # noqa: E402
    build_scene_journey_runtime_evidence,
)


def _runtime_config(
    *,
    scene_id: str = "report",
    category: str = "report",
    rule_family: str,
    material_schema_id: str = "",
    delivery_preset_id: str = "",
) -> ResolvedConfig:
    config = ResolvedConfig(
        input_source_profile=InputSourceProfile(
            material_schema_id=material_schema_id,
            material_schema_ids=[],
        ),
        compliance_profile=ComplianceProfile(
            rule_family=rule_family,
            object_preflight=ObjectPreflightPolicy(enabled=False),
        ),
        delivery_presets=(
            [DeliveryPreset(preset_id=delivery_preset_id)]
            if delivery_preset_id
            else []
        ),
    )
    config.scene_id = scene_id
    config.category = category
    return config


def test_scene_journey_runtime_projects_only_resolved_runtime_contracts():
    project = build_scene_journey_runtime_evidence(
        _runtime_config(
            rule_family="project_application",
            material_schema_id="project_application_materials_v1",
            delivery_preset_id="application_package",
        )
    )
    assert project.status == "contract_projected"
    assert project.evidence_scope == "runtime_contract"
    assert project.static_audit_status == "not_run"
    assert project.source_scan_performed is False
    assert project.pack_ids == ("application_reports",)
    assert project.family_ids == ("project_application",)
    assert project.capability_ids == ("project_application",)
    assert project.contract_ids == ("family:project_application",)
    assert not hasattr(project, "request_cell_ids")
    assert not hasattr(project, "fixture_ids")
    assert "material_field_consistency" in project.report_expectations
    assert "delivery_artifact_report" in project.report_expectations
    assert "delivery:application_package" in project.artifact_channel_ids
    assert "material_repair" in project.repair_target_types
    assert "delivery_preset" in project.repair_target_types

    product = build_scene_journey_runtime_evidence(
        _runtime_config(
            rule_family="product_sales_documents",
            material_schema_id="product_assets_v1",
        )
    )
    assert product.family_ids == ("product_sales_documents",)
    assert product.contract_ids == ("family:product_sales_documents",)
    assert product.artifact_channel_ids == ("execution_report",)

    professional = build_scene_journey_runtime_evidence(
        _runtime_config(
            scene_id="professional_disclosure",
            category="professional_disclosure",
            rule_family="finance_quote_documents",
            material_schema_id="finance_quote_fields_v1",
        )
    )
    assert professional.status == "manual_gate_required"
    assert professional.pack_ids == ("professional_disclosure",)
    assert professional.family_ids == ("finance_quote_documents",)
    assert professional.manual_gate_ids == (
        "professional_disclosure_review_gate",
    )
    assert "plugin_manual_gate" in professional.repair_target_types
    assert "boundary_confirmation" in professional.repair_target_types
    assert "manual_gate_receipt" in professional.artifact_channel_ids

    import_ai = build_scene_journey_runtime_evidence(
        _runtime_config(
            scene_id="import_ai_boundary",
            category="import_ai_boundary",
            rule_family="import_ai_boundary",
        )
    )
    assert import_ai.status == "manual_gate_required"
    assert import_ai.pack_ids == ("import_ai_boundary",)
    assert import_ai.family_ids == ()
    assert import_ai.contract_ids == ("pack:import_ai_boundary",)
    assert import_ai.manual_gate_ids == ("import_ai_conversion_gate",)
    assert "conversion_confidence_report" in import_ai.report_expectations


def test_pipeline_runtime_does_not_import_audits_or_scan_repository(
    tmp_path,
    monkeypatch,
):
    doc_path = tmp_path / "project.docx"
    document = Document()
    document.add_paragraph("Project application body")
    document.save(doc_path)

    config = _runtime_config(
        rule_family="project_application",
        material_schema_id="project_application_materials_v1",
    )
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name in {
            "src.config.scene_user_journey_fixture_audit",
            "src.config.scene_business_capability_matrix_audit",
        }:
            raise AssertionError(f"runtime imported static audit: {name}")
        return real_import(name, *args, **kwargs)

    def fail_read_text(*_args, **_kwargs):
        raise AssertionError("pipeline runtime attempted a repository text scan")

    with monkeypatch.context() as runtime_guard:
        runtime_guard.setattr(builtins, "__import__", guarded_import)
        runtime_guard.setattr(Path, "read_text", fail_read_text)
        result = Pipeline([], config, output_dir=str(tmp_path)).execute(str(doc_path))

    assert result.success is True
    evidence = result.context.scene_journey_runtime
    assert evidence.status == "contract_projected"
    assert evidence.evidence_scope == "runtime_contract"
    assert evidence.source_scan_performed is False
    assert evidence.static_audit_status == "not_run"
    assert any(
        item.rule_name == "scene_journey_runtime"
        and "scope=runtime_contract" in item.after
        and "static_audit=not_run" in item.after
        for item in result.tracker.get_all()
    )

    report_json = tmp_path / "project_report.json"
    report_md = tmp_path / "project_report.md"
    write_json_report(
        result,
        input_path=doc_path,
        output_path=None,
        report_path=report_json,
        elapsed=0.1,
        modules_enabled=0,
        modules_total=0,
    )
    write_markdown_report(
        result,
        input_path=doc_path,
        report_path=report_md,
        elapsed=0.1,
        modules_enabled=0,
        modules_total=0,
    )

    payload = json.loads(report_json.read_text(encoding="utf-8"))
    runtime = payload["scene_journey_runtime"]
    assert runtime["status"] == "contract_projected"
    assert runtime["evidence_scope"] == "runtime_contract"
    assert runtime["static_audit_status"] == "not_run"
    assert runtime["source_scan_performed"] is False
    assert runtime["contract_ids"] == ["family:project_application"]
    assert "fixture_ids" not in runtime
    assert "request_cell_ids" not in runtime

    markdown = report_md.read_text(encoding="utf-8")
    assert "Evidence scope: runtime_contract" in markdown
    assert "Static audit: not_run" in markdown
    assert "Source scan during execution: no" in markdown
    assert "Runtime contracts: family:project_application" in markdown


def test_explicit_static_audit_entry_still_runs_real_source_scans(monkeypatch):
    from src.config.scene_journey_static_audit import (
        build_scene_journey_static_audit_evidence,
    )
    from src.config import scene_user_journey_fixture_audit

    read_paths: list[Path] = []
    real_read_text = Path.read_text

    def observed_read_text(path, *args, **kwargs):
        read_paths.append(path)
        return real_read_text(path, *args, **kwargs)

    with monkeypatch.context() as scan_observer:
        scan_observer.setattr(Path, "read_text", observed_read_text)
        result = build_scene_journey_static_audit_evidence(project_root=ROOT)

    assert result.evidence_scope == "static_audit"
    assert result.source_scan_performed is True
    assert result.source_evidence_count > 0
    assert result.journey_path_count > 0
    assert result.capability_count > 0
    assert read_paths
    assert any(path.suffix == ".py" for path in read_paths)

    def prove_scan_is_called(*_args, **_kwargs):
        raise RuntimeError("real source scan reached")

    monkeypatch.setattr(
        scene_user_journey_fixture_audit,
        "scan_scene_source_markers",
        prove_scan_is_called,
    )
    with pytest.raises(RuntimeError, match="real source scan reached"):
        build_scene_journey_static_audit_evidence(project_root=ROOT)


def test_cold_runtime_import_does_not_load_static_audit_modules():
    command = (
        "import json,sys; "
        "before=set(sys.modules); "
        "import src.shared.engine.scene_journey_runtime; "
        "loaded=set(sys.modules)-before; "
        "print(json.dumps(sorted(m for m in loaded if '_audit' in m)))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", command],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == []
