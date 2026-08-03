import sys
from dataclasses import asdict
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import src.config.dataclass_utils as dataclass_utils
from src.config.dataclass_utils import dict_to_dataclass
from src.config.migration import upgrade_scene_formula_policy_ownership
from src.config.resolver import resolve_config
from src.config.scene import SceneWorkspace
from src.config.template import StyleConfig, TemplateConfig


def test_template_config_hosts_feature_specific_configs():
    template = TemplateConfig()

    assert bool(template.caption.figure_prefix)
    assert template.caption.auto_insert is True
    assert template.caption.format_inserted is False
    assert template.table.border_mode == "three_line"
    assert template.table.table_alignment == "center"
    assert template.table.color_table_accent == "blue"
    assert template.table.color_table_variant == "header_grid"
    assert not hasattr(template.toc, "enabled")
    assert template.header_footer.page_number_enabled is True
    assert template.reference_style.hanging_indent_cm == 0.74
    assert not hasattr(template.reference_style, "font_cn")
    assert not hasattr(template.reference_style, "font_en")
    assert not hasattr(template.reference_style, "size_pt")
    for removed_formula_root in (
        "formula_table",
        "formula_style",
        "equation_numbering",
    ):
        assert not hasattr(template, removed_formula_root)


def test_template_config_ignores_legacy_table_row_height_field():
    template = dict_to_dataclass(
        TemplateConfig,
        {
            "table": {
                "layout_mode": "full",
                "row_height_pt": 24,
            },
        },
    )

    assert template.table.layout_mode == "full"
    assert not hasattr(template.table, "row_height_pt")


def test_legacy_scene_reference_typography_becomes_inherited_style_override():
    template = TemplateConfig()
    template.styles["body"] = StyleConfig(alignment="right", bold=True)
    payload = asdict(SceneWorkspace(mode_id="custom"))
    payload["reference_style"].update(
        {"font_cn": "黑体", "font_en": "Calibri", "size_pt": 11}
    )

    upgraded = upgrade_scene_formula_policy_ownership(payload)
    scene = dict_to_dataclass(SceneWorkspace, upgraded)
    resolved = resolve_config(template, scene)

    assert set(upgraded["reference_style"]) == {
        "hanging_indent_cm",
        "space_after_pt",
        "space_after_unit",
    }
    assert not hasattr(scene.reference_style, "font_cn")
    assert resolved.styles["references_body"].font_cn == "黑体"
    assert resolved.styles["references_body"].font_en == "Calibri"
    assert resolved.styles["references_body"].size_pt == 11
    assert resolved.styles["references_body"].alignment == "right"
    assert resolved.styles["references_body"].bold is True


def test_dataclass_materialization_fails_closed_when_type_hints_break(monkeypatch):
    dataclass_utils._resolved_type_hints.cache_clear()

    def fail_type_hint_resolution(_dataclass_type):
        raise NameError("injected unresolved forward reference")

    monkeypatch.setattr(
        dataclass_utils,
        "get_type_hints",
        fail_type_hint_resolution,
    )

    with pytest.raises(NameError, match="unresolved forward reference"):
        dict_to_dataclass(TemplateConfig, {"name": "must not partially load"})


def test_dataclass_materialization_reuses_resolved_type_hints(monkeypatch):
    dataclass_utils._resolved_type_hints.cache_clear()
    original = dataclass_utils.get_type_hints
    resolved_types = []

    def count_type_hint_resolution(dataclass_type):
        resolved_types.append(dataclass_type)
        return original(dataclass_type)

    monkeypatch.setattr(
        dataclass_utils,
        "get_type_hints",
        count_type_hint_resolution,
    )

    dict_to_dataclass(TemplateConfig, {"name": "first"})
    dict_to_dataclass(TemplateConfig, {"name": "second"})

    assert resolved_types == [TemplateConfig]


def test_scene_has_no_duplicate_template_appearance_fields():
    template = TemplateConfig()
    template.caption.figure_prefix = "Fig"
    template.caption.auto_insert = True
    template.caption.format_inserted = False
    template.table.layout_mode = "smart"
    template.header_footer.page_number_enabled = True
    template.header_footer.header_mode = "styleref"
    template.toc.max_level = 3

    scene = SceneWorkspace()
    for field_name in (
        "caption",
        "table",
        "header_footer",
        "toc",
        "formula_table",
        "output",
    ):
        assert not hasattr(scene, field_name)

    resolved = resolve_config(template, scene)

    assert resolved.caption.figure_prefix == "Fig"
    assert resolved.caption.auto_insert is True
    assert resolved.caption.format_inserted is False
    assert resolved.table.layout_mode == "smart"
    assert resolved.header_footer.page_number_enabled is True
    assert resolved.header_footer.header_mode == "styleref"
    assert resolved.toc.max_level == 3

    assert resolved.get_with_source("caption.figure_prefix").source == "template"
    assert resolved.get_with_source("caption.auto_insert").source == "template"
    assert resolved.get_with_source("caption.format_inserted").source == "template"
    assert resolved.get_with_source("table.layout_mode").source == "template"
    assert resolved.get_with_source("header_footer.page_number_enabled").source == "template"
    assert resolved.get_with_source("header_footer.header_mode").source == "template"
    assert resolved.get_with_source("toc.max_level").source == "template"


def test_resolve_config_keeps_explicit_template_overrides_available():
    template = TemplateConfig()
    template.table.layout_mode = "smart"
    template.caption.figure_prefix = "Fig"

    scene = SceneWorkspace(
        template_overrides={
            "table.layout_mode": "full",
            "caption.figure_prefix": "Figure",
        }
    )

    resolved = resolve_config(template, scene)

    assert resolved.table.layout_mode == "full"
    assert resolved.caption.figure_prefix == "Figure"
    assert resolved.get_with_source("table.layout_mode").source == "scene"
    assert resolved.get_with_source("caption.figure_prefix").source == "scene"


def test_resolve_config_keeps_scene_owned_runtime_policy_fields():
    template = TemplateConfig()
    template.watermark.enabled = False
    assert not hasattr(template, "output")

    scene = SceneWorkspace(mode_id="thesis")
    rules = scene.ensure_thesis_formula_rules()
    rules.formula_style.unify_font = False
    rules.equation_numbering.numbering_format = "global"
    scene.watermark.enabled = True
    scene.watermark.text = "内部传阅"
    scene.default_delivery_preset().artifacts.final_docx = False
    scene.template_overrides["output.final_docx"] = True

    resolved = resolve_config(
        template,
        scene,
        session_overrides={"output.final_docx": True},
    )

    assert resolved.formula_style.unify_font is False
    assert resolved.equation_numbering.numbering_format == "global"
    assert resolved.watermark.enabled is True
    assert resolved.watermark.text == "内部传阅"
    assert resolved.output.final_docx is False
    resolved.output.final_docx = True
    assert scene.default_delivery_preset().artifacts.final_docx is False
    assert resolved.get_with_source("formula_style.unify_font").source == "scene"
    assert resolved.get_with_source("equation_numbering.numbering_format").source == "scene"
    assert resolved.get_with_source("watermark.enabled").source == "scene"
    assert resolved.get_with_source("output.final_docx").source == "scene"


def test_default_valued_formula_policy_has_no_template_competitor():
    template = TemplateConfig()
    scene = SceneWorkspace(mode_id="thesis")

    resolved = resolve_config(template, scene)

    assert resolved.formula_style.unify_font is True
    assert resolved.formula_style.unify_size is True
    assert resolved.formula_style.unify_spacing is True
    assert resolved.equation_numbering.numbering_format == "chapter.seq"
    assert resolved.get_with_source("formula_style.unify_font").source == "scene"
    assert resolved.get_with_source("formula_style.unify_size").source == "scene"
    assert resolved.get_with_source("formula_style.unify_spacing").source == "scene"
    assert resolved.get_with_source("equation_numbering.numbering_format").source == "scene"


def test_thesis_formula_defaults_match_the_v02_proven_behavior():
    rules = SceneWorkspace(mode_id="thesis").ensure_thesis_formula_rules()

    assert rules.formula_enabled is True
    assert rules.formula_convert.enabled is True
    assert rules.formula_convert.output_mode == "word_native"
    assert rules.formula_convert.low_confidence_policy == "skip_and_mark"
    assert rules.formula_convert.office_fallback_enabled is False
    assert rules.formula_convert.office_fallback_timeout_sec == 30
    assert rules.formula_to_table.enabled is True
    assert rules.formula_to_table.block_only is True
    assert rules.equation_numbering.enabled is True
    assert rules.equation_numbering.numbering_format == "chapter.seq"
    assert rules.formula_style.enabled is True
    assert rules.formula_style.unify_font is True
    assert rules.formula_style.unify_size is True
    assert rules.formula_style.unify_spacing is True

    table = rules.formula_table
    assert table.formula_font_name == "Cambria Math"
    assert table.formula_font_size_pt == 12.0
    assert table.formula_line_spacing == 1.0
    assert table.formula_space_before_pt == 0.0
    assert table.formula_space_after_pt == 0.0
    assert table.block_alignment == "center"
    assert table.table_alignment == "center"
    assert table.formula_cell_alignment == "center"
    assert table.number_alignment == "right"
    assert table.number_font_name == "Times New Roman"
    assert table.number_font_size_pt == 10.5
    assert table.auto_shrink_number_column is True

    assert rules.chem_typography.enabled is False
    assert not any(rules.chem_typography.scopes.values())


def test_formula_enablement_has_one_persisted_owner_and_runtime_projection():
    scene = SceneWorkspace(mode_id="thesis")
    rules = scene.ensure_thesis_formula_rules()
    rules.formula_convert.enabled = False
    rules.formula_to_table.enabled = True
    rules.equation_numbering.enabled = False
    rules.formula_style.enabled = False
    rules.chem_typography.enabled = True

    assert not (
        {"formula_convert", "equation_table_format", "chem_typography"}
        & set(scene.module_switches)
    )

    resolved = resolve_config(TemplateConfig(), scene)

    assert resolved.module_switches["formula_convert"] is False
    assert resolved.module_switches["equation_table_format"] is True
    assert resolved.module_switches["chem_typography"] is False

    rules.chem_typography.scopes["body"] = True
    resolved = resolve_config(TemplateConfig(), scene)
    assert resolved.module_switches["chem_typography"] is True
    assert resolved.formula_to_table.enabled is True

    rules.formula_enabled = False
    resolved = resolve_config(TemplateConfig(), scene)
    assert resolved.module_switches["formula_convert"] is False
    assert resolved.module_switches["equation_table_format"] is False
    assert resolved.module_switches["chem_typography"] is True
    assert rules.formula_to_table.enabled is True


def test_resolve_config_ignores_scene_page_number_strategy_fields():
    template = TemplateConfig()
    template.header_footer.page_number_enabled = True
    template.header_footer.front_matter_page_number_format = "upperRoman"
    template.header_footer.body_page_number_start = 1

    scene = SceneWorkspace(
        template_overrides={
            "header_footer.page_number_enabled": False,
            "header_footer.front_matter_page_number_format": "lowerRoman",
            "header_footer.body_page_number_start": 5,
        }
    )

    resolved = resolve_config(template, scene)

    assert resolved.header_footer.page_number_enabled is True
    assert resolved.header_footer.front_matter_page_number_format == "upperRoman"
    assert resolved.header_footer.body_page_number_start == 1
    assert resolved.get_with_source("header_footer.page_number_enabled").source == "template"
