import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.dataclass_utils import dict_to_dataclass
from src.config.resolver import resolve_config
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig


def test_template_config_hosts_feature_specific_configs():
    template = TemplateConfig()

    assert bool(template.caption.figure_prefix)
    assert template.caption.auto_insert is True
    assert template.caption.format_inserted is False
    assert template.table.border_mode == "three_line"
    assert template.table.table_alignment == "center"
    assert template.table.color_table_accent == "blue"
    assert template.table.color_table_variant == "header_grid"
    assert template.toc.enabled is True
    assert template.header_footer.page_number_enabled is True
    assert template.reference_style.hanging_indent_cm == 0.74


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


def test_resolve_config_keeps_template_baseline_for_scene_legacy_feature_fields():
    template = TemplateConfig()
    template.caption.figure_prefix = "Fig"
    template.caption.auto_insert = True
    template.caption.format_inserted = False
    template.table.layout_mode = "smart"
    template.header_footer.page_number_enabled = True
    template.header_footer.header_mode = "styleref"
    template.toc.max_level = 3

    scene = SceneWorkspace()
    scene.caption.figure_prefix = "Figure"
    scene.caption.auto_insert = False
    scene.caption.format_inserted = True
    scene.table.layout_mode = "full"
    scene.header_footer.header_mode = "fixed"
    scene.toc.max_level = 4

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
    template.formula_style.unify_font = True
    template.equation_numbering.numbering_format = "chapter.seq"
    template.watermark.enabled = False
    template.output.final_docx = True

    scene = SceneWorkspace()
    scene.formula_style.unify_font = False
    scene.equation_numbering.numbering_format = "global"
    scene.watermark.enabled = True
    scene.watermark.text = "内部传阅"
    scene.output.final_docx = False

    resolved = resolve_config(template, scene)

    assert resolved.formula_style.unify_font is False
    assert resolved.equation_numbering.numbering_format == "global"
    assert resolved.watermark.enabled is True
    assert resolved.watermark.text == "内部传阅"
    assert resolved.output.final_docx is False
    assert resolved.get_with_source("formula_style.unify_font").source == "scene"
    assert resolved.get_with_source("equation_numbering.numbering_format").source == "scene"
    assert resolved.get_with_source("watermark.enabled").source == "scene"
    assert resolved.get_with_source("output.final_docx").source == "scene"


def test_resolve_config_ignores_scene_page_number_strategy_fields():
    template = TemplateConfig()
    template.header_footer.page_number_enabled = True
    template.header_footer.front_matter_page_number_format = "upperRoman"
    template.header_footer.body_page_number_start = 1

    scene = SceneWorkspace()
    scene.header_footer.page_number_enabled = False
    scene.header_footer.front_matter_page_number_format = "lowerRoman"
    scene.header_footer.body_page_number_start = 5

    resolved = resolve_config(template, scene)

    assert resolved.header_footer.page_number_enabled is True
    assert resolved.header_footer.front_matter_page_number_format == "upperRoman"
    assert resolved.header_footer.body_page_number_start == 1
    assert resolved.get_with_source("header_footer.page_number_enabled").source == "template"
