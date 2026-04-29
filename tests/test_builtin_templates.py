import sys
import json
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.builtin_templates import create_builtin_template, list_builtin_template_ids
from src.config.loader import load_template
from src.shared.engine.toc_style_ops import sync_toc_styles


def test_every_declared_builtin_template_id_resolves_to_a_template_config():
    for template_id in list_builtin_template_ids():
        template = create_builtin_template(template_id)

        assert template.name
        assert template.description is not None


def test_thesis_template_uses_real_config_payload_instead_of_name_only_shell():
    template = create_builtin_template("thesis_gbt")

    assert template.page_setup.margin.top_cm == 3.8
    assert "body" in template.styles
    assert template.styles["body"].font_cn
    assert "heading1" in template.heading_numbering.level_bindings
    assert "toc_title" in template.styles
    assert "toc_level1" in template.styles
    assert "toc_level2" in template.styles
    assert "toc_level3" in template.styles

    assert template.styles["toc_title"].size_pt == 16
    assert template.styles["toc_title"].bold is True
    assert template.styles["toc_title"].alignment == "center"
    assert template.styles["toc_level1"].size_pt == 14
    assert template.styles["toc_level2"].size_pt == 12
    assert template.styles["toc_level2"].left_indent_chars == 1
    assert template.styles["toc_level3"].size_pt == 10.5
    assert template.styles["toc_level3"].left_indent_chars == 2
    assert [phase.phase_id for phase in template.header_footer.page_number_plan.phases] == [
        "front",
        "body",
    ]
    assert template.header_footer.front_matter_page_number_format == "upperRoman"
    assert template.header_footer.body_page_number_format == "decimal"
    assert template.header_footer.restart_body_page_number is True


def test_builtin_template_factory_returns_fresh_instances():
    first = create_builtin_template("default")
    second = create_builtin_template("default")

    first.page_setup.margin.top_cm = 9.9

    assert second.page_setup.margin.top_cm != 9.9


def test_default_builtin_template_defines_generic_heading_style():
    template = create_builtin_template("default")

    assert "heading" in template.styles
    assert template.styles["heading"].font_cn == "宋体"
    assert template.styles["heading"].size_display == "小四"
    assert template.styles["heading"].bold is True
    assert template.styles["heading"].first_line_indent_chars == 0


def test_library_default_template_repairs_legacy_heading_style_strings():
    template = load_template(ROOT / "templates" / "default.json")

    assert template.styles["heading"].font_cn == "宋体"
    assert template.styles["heading"].size_display == "小四"


def test_load_template_normalizes_legacy_heading_style_mojibake(tmp_path):
    target = tmp_path / "legacy_heading.json"
    target.write_text(
        json.dumps(
            {
                "styles": {
                    "heading": {
                        "font_cn": "瀹嬩綋",
                        "size_display": "灏忓洓",
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    template = load_template(target)

    assert template.styles["heading"].font_cn == "宋体"
    assert template.styles["heading"].size_display == "小四"


def test_report_builtin_template_exposes_explicit_continuous_page_number_plan():
    template = create_builtin_template("report_default")

    phases = template.header_footer.page_number_plan.phases
    assert [phase.phase_id for phase in phases] == ["main"]
    assert phases[0].selectors == ["all_numbered_content"]
    assert phases[0].number_format == "decimal"
    assert phases[0].start_mode == "restart"
    assert phases[0].start_value == 1


def test_thesis_builtin_toc_style_syncs_into_word_toc_styles():
    template = create_builtin_template("thesis_gbt")
    doc = Document()

    changed = sync_toc_styles(doc, template.styles)

    assert changed == 4
