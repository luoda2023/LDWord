import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest
from docx import Document

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.builtin_templates import (
    builtin_template_resource_path,
    create_builtin_template,
    list_builtin_template_ids,
    list_builtin_template_resources,
)
from src.config.library import _load_template_entry_config
from src.config.loader import ConfigLoadError, load_template, save_template
from src.shared.engine.toc_style_ops import sync_toc_styles


def test_every_declared_builtin_template_id_resolves_to_a_template_config():
    for template_id in list_builtin_template_ids():
        template = create_builtin_template(template_id)

        assert template.name
        assert template.description is not None


def test_every_builtin_template_has_explicit_enabled_bindings_for_visible_levels():
    for template_id in list_builtin_template_ids():
        template = create_builtin_template(template_id)
        bindings = template.heading_numbering.level_bindings

        for level in range(1, template.heading_model.max_heading_levels + 1):
            binding = bindings.get(f"heading{level}")
            assert binding is not None, f"{template_id} missing heading{level}"
            assert binding.enabled is True, f"{template_id} disables heading{level}"


def test_thesis_template_uses_real_config_payload_instead_of_name_only_shell():
    template = create_builtin_template("thesis_gbt")

    assert template.page_setup.margin.top_cm == 3.8
    assert "body" in template.styles
    assert template.styles["body"].font_cn
    assert "heading1" in template.heading_numbering.level_bindings
    assert "toc" in template.styles
    assert "toc_title" in template.styles
    assert "toc_level1" in template.styles
    assert "toc_level2" in template.styles
    assert "toc_level3" in template.styles
    assert "toc_level6" in template.styles

    assert template.styles["toc_title"].size_pt == 16
    assert template.styles["toc_title"].bold is True
    assert template.styles["toc_title"].alignment == "center"
    assert template.styles["toc_level1"].size_pt == 14
    assert template.styles["toc_level2"].size_pt == 12
    assert template.styles["toc_level2"].left_indent_chars == 1
    assert template.styles["toc_level3"].size_pt == 10.5
    assert template.styles["toc_level3"].left_indent_chars == 2
    assert template.styles["toc_level6"].left_indent_chars == 5
    assert [phase.phase_id for phase in template.header_footer.page_number_plan.phases] == [
        "pre_numbering",
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


def test_builtin_library_load_does_not_merge_a_second_factory_source(tmp_path):
    stored = create_builtin_template("default")
    stored.name = "模式定制默认模板"
    stored.page_setup.margin.top_cm = 2.75
    stored.heading_numbering.level_bindings = {}
    target = tmp_path / "default.json"
    save_template(stored, target)

    loaded = _load_template_entry_config(target, "default", "builtin")

    assert loaded.name == "模式定制默认模板"
    assert loaded.page_setup.margin.top_cm == 2.75
    assert loaded.heading_numbering.level_bindings == {}


def test_builtin_library_load_preserves_exact_persisted_heading_bindings(tmp_path):
    stored = create_builtin_template("default")
    stored.heading_numbering.level_bindings["heading2"].enabled = False
    stored.heading_numbering.level_bindings.pop("heading4")
    target = tmp_path / "default.json"
    save_template(stored, target)

    loaded = _load_template_entry_config(target, "default", "builtin")

    assert loaded.heading_numbering.level_bindings["heading2"].enabled is False
    assert "heading4" not in loaded.heading_numbering.level_bindings


def test_default_builtin_template_defines_generic_heading_style():
    template = create_builtin_template("default")

    assert "heading" in template.styles
    assert template.styles["heading"].font_cn == "宋体"
    assert template.styles["heading"].size_display == "小四"
    assert template.styles["heading"].bold is True
    assert template.styles["heading"].first_line_indent_chars == 0


def test_canonical_default_template_contains_normalized_heading_style_strings():
    template = load_template(
        builtin_template_resource_path("default", mode_id="custom")
    )

    assert template.styles["heading"].font_cn == "宋体"
    assert template.styles["heading"].size_display == "小四"


def test_every_mode_scoped_builtin_resource_is_complete_and_loadable():
    resources = list_builtin_template_resources()

    assert len(resources) == 13
    assert any(
        mode_id == "thesis" and template_id == "thesis_custom"
        for mode_id, template_id, _path in resources
    )
    for mode_id, template_id, path in resources:
        assert path.is_file()
        template = create_builtin_template(template_id, mode_id=mode_id)
        assert set(template.heading_numbering.level_bindings) == {
            f"heading{level}" for level in range(1, 9)
        }


def test_every_builtin_json_owns_complete_output_channel_contract():
    for _mode_id, template_id, path in list_builtin_template_resources():
        payload = json.loads(path.read_text(encoding="utf-8"))
        header_footer = payload["header_footer"]
        page_plan = header_footer["page_number_plan"]

        assert "suppress_header_footer_selectors" not in header_footer, template_id
        assert "hide_on_cover" not in header_footer["header"], template_id
        assert "hide_on_cover" not in header_footer["footer"], template_id
        assert "page_number_template" not in header_footer["footer"], template_id
        assert header_footer["footer"]["content_mode"] in {"none", "fixed"}
        assert isinstance(header_footer["header"]["hidden_selectors"], list)
        assert isinstance(header_footer["footer"]["hidden_selectors"], list)
        assert {"enabled", "template", "alignment", "phases"} <= set(page_plan)
        assert payload["heading_model"]["non_numbered_title_texts"] == [
            "摘要",
            "目录",
            "参考文献",
            "缩略语表",
        ]
        assert payload["heading_model"]["non_numbered_prefixes"] == [
            "附录",
            "附件",
        ]
        assert set(payload["section"]) == {
            "boundary_mode",
            "section_break_type",
            "empty_break_policy",
            "caption_table_break_policy",
            "header_footer_link_mode",
        }
        assert set(payload["page_setup"]) >= {
            "paper_size_mode",
            "orientation_mode",
            "margin_mode",
            "paper_size_by_section",
            "orientation_by_section",
            "margin_by_section",
        }


def test_cli_default_matches_gui_custom_default_not_legacy_thesis_yaml(tmp_path):
    from src.cli_runner import _resolve_cli_resources

    legacy = tmp_path / "defaults" / "thesis.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("name: legacy-second-source\n", encoding="utf-8")

    loaded = _resolve_cli_resources(
        template_path=None,
        scene_path=None,
    ).template
    canonical = create_builtin_template("default", mode_id="custom")

    assert asdict(loaded) == asdict(canonical)
    assert loaded.name != "legacy-second-source"


def test_canonical_loader_rejects_partial_legacy_heading_payload(tmp_path):
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

    with pytest.raises(ConfigLoadError, match="缺少字段"):
        load_template(target)


def test_template_persistence_rejects_duplicate_special_title_rules(tmp_path):
    template = create_builtin_template("thesis_gbt")
    duplicate = template.heading_model.non_numbered_title_texts[0]
    template.heading_model.non_numbered_title_texts.append(duplicate)

    with pytest.raises(ValueError, match="完整标题中存在重复规则"):
        save_template(template, tmp_path / "invalid-save.json")

    payload = asdict(template)
    target = tmp_path / "invalid-load.json"
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError, match="完整标题中存在重复规则"):
        load_template(target)


def test_report_builtin_template_exposes_explicit_continuous_page_number_plan():
    template = create_builtin_template("report_default")

    phases = template.header_footer.page_number_plan.phases
    assert [phase.phase_id for phase in phases] == ["pre_numbering", "main"]
    assert phases[0].visible is False
    assert phases[1].selectors == [
        "abstract_cn",
        "abstract_en",
        "toc",
        "body",
        "references",
        "errata",
        "appendix",
        "acknowledgment",
        "resume",
    ]
    assert phases[1].number_format == "decimal"
    assert phases[1].start_mode == "restart"
    assert phases[1].start_value == 1


def test_thesis_builtin_toc_style_syncs_into_word_toc_styles():
    template = create_builtin_template("thesis_gbt")
    doc = Document()

    changed = sync_toc_styles(doc, template, max_level=3)

    assert changed == 4
    assert doc.styles["TOC Heading"].font.size.pt == template.styles["toc_title"].size_pt
    assert doc.styles["TOC 1"].font.size.pt == template.styles["toc_level1"].size_pt
    assert doc.styles["TOC 2"].font.size.pt == template.styles["toc_level2"].size_pt
    assert doc.styles["TOC 3"].font.size.pt == template.styles["toc_level3"].size_pt
