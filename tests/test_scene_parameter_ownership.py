import sys
from dataclasses import dataclass, fields
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene import SceneWorkspace
from src.config.scene_parameter_ownership import (
    ALLOWED_PARAMETER_OWNER_LAYERS,
    REQUIRED_SCENE_PARAMETER_PATHS,
    audit_parameter_execution_consumers,
    audit_scene_parameter_ownership,
    classify_scene_parameter,
    parameter_consumer_anchors,
    scene_parameter_ownership_specs,
)


def test_scene_parameter_ownership_registry_covers_scene_workspace_fields():
    result = audit_scene_parameter_ownership()
    specs = scene_parameter_ownership_specs()
    top_level_paths = {path for path in specs if "." not in path}
    scene_fields = {field.name for field in fields(SceneWorkspace)}

    assert result.is_clean
    assert scene_fields <= top_level_paths
    assert set(REQUIRED_SCENE_PARAMETER_PATHS) <= set(specs)
    assert {
        spec.owner_layer for spec in specs.values()
    } <= set(ALLOWED_PARAMETER_OWNER_LAYERS)


def test_scene_parameter_ownership_classifies_high_risk_scene_board_parameters():
    assert classify_scene_parameter("input_source_profile.material_schema_id").owner_layer == "material"
    assert classify_scene_parameter("compliance_profile.object_preflight.scan_targets").owner_layer == "scene"
    assert classify_scene_parameter("formula_convert.output_mode").owner_layer == "scene"
    assert classify_scene_parameter("formula_style.unify_font").owner_layer == "scene"
    assert classify_scene_parameter("watermark.enabled").owner_layer == "scene"
    assert classify_scene_parameter("watermark.text").owner_layer == "scene"
    assert classify_scene_parameter("output.final_docx") is None
    assert (
        classify_scene_parameter(
            "delivery_presets.0.artifacts.final_docx"
        ).owner_layer
        == "output"
    )
    assert classify_scene_parameter("delivery_presets.0.filename_template").owner_layer == "output"
    assert classify_scene_parameter("delivery_presets.3.content_visibility_rules").owner_layer == "output"
    assert classify_scene_parameter("header_footer.page_number_plan").owner_layer == "template"
    assert classify_scene_parameter("document_scope").owner_layer == "scene"
    assert classify_scene_parameter("application_boundary") is None
    assert classify_scene_parameter("format_scope") is None
    assert classify_scene_parameter("default_material_profile_id").owner_layer == "scene"
    assert classify_scene_parameter("section_styles") is None


def test_scene_parameter_ownership_requires_exact_nested_registration():
    specs = scene_parameter_ownership_specs()

    assert "table.row_height_pt" not in specs
    assert classify_scene_parameter("table.row_height_pt") is None
    assert classify_scene_parameter("watermark.opacity") is None
    assert classify_scene_parameter("delivery_presets.0.unknown_flag") is None
    assert classify_scene_parameter("delivery_presets.-1.filename_template") is None


def test_template_baselines_are_not_reintroduced_as_scene_compatibility_fields():
    scene = SceneWorkspace()

    assert not hasattr(scene, "output")

    for path in ("table", "header_footer", "toc", "caption", "formula_table"):
        assert not hasattr(scene, path)
        ownership = classify_scene_parameter(path)
        assert ownership is not None
        assert ownership.owner_layer == "template"
        assert ownership.template_baseline is True

    assert audit_scene_parameter_ownership().is_clean


def test_scene_parameter_ownership_audit_flags_new_scene_fields():
    @dataclass
    class FutureSceneWorkspace(SceneWorkspace):
        experimental_knob: str = ""

    result = audit_scene_parameter_ownership(FutureSceneWorkspace)

    assert result.missing_top_level_paths == ("experimental_knob",)
    assert not result.is_clean


def test_scene_parameter_execution_consumers_have_code_anchors():
    result = audit_parameter_execution_consumers()
    anchors = parameter_consumer_anchors()
    declared_consumers = {
        spec.execution_consumer
        for spec in scene_parameter_ownership_specs().values()
    }

    assert result.is_clean
    assert declared_consumers == set(anchors)
    assert anchors["material preflight"][0].source_path == "src/config/material_schema_registry.py"
    assert any(
        anchor.source_path == "src/report_writer.py"
        for anchor in anchors["report writer"]
    )
    assert any(
        anchor.source_path
        == "src/services/production_runtime/execution_runtime.py"
        for anchor in anchors["batch runner"]
    )
    assert any(
        anchor.source_path
        == "src/services/production_runtime/batch_reporting.py"
        for anchor in anchors["batch runner"]
    )
