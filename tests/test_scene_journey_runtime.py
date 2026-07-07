import json
import sys
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.resolved import ResolvedConfig  # noqa: E402
from src.config.scene import ComplianceProfile, InputSourceProfile, ObjectPreflightPolicy  # noqa: E402
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
        delivery_presets=[],
    )
    config.scene_id = scene_id
    config.category = category
    return config


def test_scene_journey_runtime_maps_project_product_professional_and_import_paths():
    project = build_scene_journey_runtime_evidence(
        _runtime_config(
            rule_family="project_application",
            material_schema_id="project_application_materials_v1",
        )
    )
    assert project.status == "manual_gate_required"
    assert "application_reports" in project.pack_ids
    assert "project_application" in project.family_ids
    assert "success" in project.journey_type_ids
    assert "degraded" in project.journey_type_ids
    assert "manual_boundary" in project.journey_type_ids
    assert "missing_items_report" in project.report_expectations
    assert "budget_attachment_report" in project.report_expectations
    assert "sample_manifest_child_drilldown" in project.artifact_channel_ids
    assert "material_repair" in project.repair_target_types
    assert "rule_source" in project.repair_target_types

    product = build_scene_journey_runtime_evidence(
        _runtime_config(
            rule_family="product_sales_documents",
            material_schema_id="product_assets_v1",
        )
    )
    assert "product_sales_documents" in product.family_ids
    assert "application_reports_product_asset_degraded" in product.fixture_ids
    assert "asset_report" in product.report_expectations
    assert "customer_internal_version_report" in product.report_expectations
    assert "delivery_preset" in product.repair_target_types

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
    assert "finance_quote_documents" in professional.family_ids
    assert professional.manual_gate_ids == ("professional_disclosure_review_gate",)
    assert "professional_source_quality_report" in professional.report_expectations
    assert "plugin_manual_gate" in professional.repair_target_types
    assert "boundary_confirmation" in professional.repair_target_types

    import_ai = build_scene_journey_runtime_evidence(
        _runtime_config(
            scene_id="import_ai_boundary",
            category="import_ai_boundary",
            rule_family="import_ai_boundary",
        )
    )
    assert import_ai.status == "manual_gate_required"
    assert import_ai.pack_ids == ("import_ai_boundary",)
    assert import_ai.manual_gate_ids == ("import_ai_conversion_gate",)
    assert "failure" in import_ai.journey_type_ids
    assert "handoff" in import_ai.journey_type_ids
    assert "conversion_confidence_report" in import_ai.report_expectations
    assert "import_handoff" in import_ai.report_expectations
    assert "import_handoff" in import_ai.repair_target_types


def test_pipeline_records_scene_journey_runtime_and_reports(tmp_path):
    doc_path = tmp_path / "project.docx"
    document = Document()
    document.add_paragraph("Project application body")
    document.save(doc_path)

    config = _runtime_config(
        rule_family="project_application",
        material_schema_id="project_application_materials_v1",
    )
    result = Pipeline([], config, output_dir=str(tmp_path)).execute(str(doc_path))

    assert result.success is True
    evidence = result.context.scene_journey_runtime
    assert evidence.status == "manual_gate_required"
    assert "application_reports" in evidence.pack_ids
    assert "project_application" in evidence.family_ids
    assert "missing_items_report" in evidence.report_expectations
    assert "material_repair" in evidence.repair_target_types
    assert any(
        item.rule_name == "scene_journey_runtime"
        and "paths=" in item.after
        and "artifacts=" in item.after
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
    assert runtime["status"] == "manual_gate_required"
    assert "application_reports" in runtime["pack_ids"]
    assert "project_application" in runtime["family_ids"]
    assert "sample_manifest_child_drilldown" in runtime["artifact_channel_ids"]
    assert "material_repair" in runtime["repair_target_types"]
    assert runtime["path_count"] >= 6

    markdown = report_md.read_text(encoding="utf-8")
    assert "## 场景旅程运行时证据" in markdown
    assert "application_reports" in markdown
    assert "missing_items_report" in markdown
