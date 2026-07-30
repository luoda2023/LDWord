import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.control_contract_registry import (
    REQUIRED_CONTROL_CONTRACT_IDS,
    audit_control_contract_registry,
    build_control_contract_summary,
    get_control_contract,
    list_control_contracts,
    resolve_control_contract_evidence_locations,
)
from src.config.resolved import ResolvedConfig


def test_control_contract_registry_covers_v16_required_style_controls():
    contracts = {contract.contract_id: contract for contract in list_control_contracts()}
    result = audit_control_contract_registry(project_root=ROOT)

    assert result.is_clean
    assert set(REQUIRED_CONTROL_CONTRACT_IDS) <= set(contracts)
    assert contracts["body.left_indent"].canonical_control == "IndentInput"
    assert contracts["body.right_indent"].canonical_control == "IndentInput"
    assert contracts["body.special_indent"].canonical_control == "SpecialIndentInput"
    assert contracts["body.line_spacing"].canonical_control == (
        "StyledComboBox + SpacingInput"
    )
    assert contracts["body.space_before"].canonical_control == "SpacingInput"
    assert contracts["body.space_after"].canonical_control == "SpacingInput"


def test_control_contract_registry_covers_n2_130_scene_output_material_plugin_controls():
    contracts = {contract.contract_id: contract for contract in list_control_contracts()}

    assert contracts["scene.formula_conversion_strategy"].owner_layer == "scene"
    assert contracts["scene.formula_conversion_strategy"].canonical_control == (
        "scene policy + workbench/runtime gate"
    )
    assert "scene.formula_convert.output_mode" in contracts[
        "scene.formula_conversion_strategy"
    ].parameter_paths
    assert "full LaTeX" in contracts[
        "scene.formula_conversion_strategy"
    ].disabled_state_rule

    watermark = contracts["scene.watermark_status"]
    assert watermark.owner_layer == "scene"
    assert "scene.watermark.enabled" in watermark.parameter_paths
    assert "scene.watermark.text" in watermark.parameter_paths
    assert "visual baseline" in watermark.template_surface

    material = contracts["material.schema_selection"]
    assert material.owner_layer == "material"
    assert "material_schema_registry.*" in material.parameter_paths
    assert "unknown schema" in material.disabled_state_rule

    delivery = contracts["output.delivery_preset"]
    assert delivery.owner_layer == "output"
    assert "scene.default_delivery_preset_id" in delivery.parameter_paths
    assert "DeliveryPreset" in delivery.notes

    visibility = contracts["output.content_visibility_rules"]
    assert visibility.owner_layer == "output"
    assert "scene.delivery_presets.*.content_visibility_rules" in visibility.parameter_paths
    assert visibility.canonical_control == "TextArea + StyledComboBox + insert action"

    plugin = contracts["plugin.manual_gate"]
    assert plugin.owner_layer == "plugin"
    assert "plugin_manual_gate.*" in plugin.parameter_paths
    assert "manual confirmation" in plugin.canonical_control


def test_control_contract_registry_locks_pairing_units_and_disabled_rules():
    left = get_control_contract("body.left_indent")
    right = get_control_contract("body.right_indent")
    before = get_control_contract("body.space_before")
    after = get_control_contract("body.space_after")
    special = get_control_contract("body.special_indent")
    line = get_control_contract("body.line_spacing")

    assert left.unit_set == ("chars", "pt", "cm")
    assert right.unit_set == left.unit_set
    assert left.paired_contract_ids == ("body.right_indent",)
    assert right.paired_contract_ids == ("body.left_indent",)

    assert before.unit_set == ("pt", "lines", "cm", "mm", "in", "auto")
    assert after.unit_set == before.unit_set
    assert before.paired_contract_ids == ("body.space_after",)
    assert after.paired_contract_ids == ("body.space_before",)
    assert "auto" in before.disabled_state_rule

    assert special.unit_set == ("chars", "pt", "cm")
    assert "mode=none" in special.disabled_state_rule
    assert special.owner_layer == "template"
    assert special.template_surface == "TemplatePanel StyleDetail"
    assert special.scene_surface == ""

    assert line.unit_set == ("exact", "single", "one_half", "double", "multiple")
    assert "single/one_half/double" in line.disabled_state_rule


def test_control_contract_registry_keeps_row_height_out_of_generic_table_config():
    row_height = get_control_contract("fixed_layout.table_row_height")
    config = ResolvedConfig()

    assert not hasattr(config.table, "row_height_pt")
    assert row_height.owner_layer == "scene"
    assert row_height.canonical_control == "FixedLayoutRowHeightPolicy + OOXML helper"
    assert row_height.template_surface == "not_generic_template"
    assert "form_batch_documents" in row_height.scene_surface
    assert "word.w:trHeight" in row_height.parameter_paths
    assert "fixed-layout policy" in row_height.workbench_surface
    assert "generic TableConfig" in row_height.notes


def test_control_contract_summary_exposes_control_and_owner_layer():
    summary = build_control_contract_summary(
        get_control_contract("scene.formula_conversion_strategy")
    )

    assert "scene.formula_conversion_strategy [scene]" in summary
    assert "scene policy + workbench/runtime gate" in summary
    assert "公式策略" in summary
    assert "word_native/image_fallback/keep_source/manual_review" in summary


def test_control_contract_evidence_locations_resolve_source_lines():
    locations = resolve_control_contract_evidence_locations(
        "body.special_indent",
        project_root=ROOT,
    )

    assert locations
    assert all(location.contract_id == "body.special_indent" for location in locations)
    assert all(location.source_path for location in locations)
    assert all(location.marker for location in locations)
    assert all(location.line_number > 0 for location in locations)
    assert any(
        location.source_path == "src/shared/ui/paragraph_style_inputs.py"
        and location.marker == "class SpecialIndentInput"
        for location in locations
    )
