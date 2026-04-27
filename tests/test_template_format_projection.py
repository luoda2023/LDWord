import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.builtin_templates import create_builtin_template
from src.config.template import TemplateConfig
from src.ui.panels.template_format import (
    TEMPLATE_PREVIEW_SPECS,
    build_template_preview_groups,
)


def test_preview_specs_cover_all_template_config_fields_except_identity_fields():
    covered = {field_name for spec in TEMPLATE_PREVIEW_SPECS for field_name in spec.field_names}
    expected = {
        "page_setup",
        "section",
        "styles",
        "heading_numbering",
        "heading_model",
        "table",
        "header_footer",
        "toc",
        "reference_style",
        "caption",
    }

    assert covered == expected


def test_preview_groups_expose_real_grouped_summaries_for_builtin_thesis_template():
    groups = build_template_preview_groups(create_builtin_template("thesis_gbt"))
    group_map = {group.group_id: group for group in groups}

    assert len(groups) == len(TEMPLATE_PREVIEW_SPECS)
    assert "3.8" in group_map["page"].summary
    assert "宋体" in group_map["style"].summary
    assert "页码" in group_map["header_footer"].summary
    assert "目录" in group_map["toc"].summary
    assert "智能布局" in group_map["table"].summary
    assert "悬挂" in group_map["reference"].summary
    assert "章节编号" in group_map["caption"].summary


def test_table_preview_summary_includes_table_behavior_flags():
    cfg = create_builtin_template("thesis_gbt")
    default_groups = build_template_preview_groups(cfg)
    default_group_map = {group.group_id: group for group in default_groups}

    assert "不首行加粗" in default_group_map["table"].summary
    assert "不跨页重复表头" in default_group_map["table"].summary
    assert "\u5b57\u5f62\u5e38\u89c4" in default_group_map["table"].summary

    cfg.table.bold = True
    cfg.table.italic = True
    cfg.table.first_row_bold = True
    cfg.table.repeat_header = True
    enabled_groups = build_template_preview_groups(cfg)
    enabled_group_map = {group.group_id: group for group in enabled_groups}

    assert "\u5b57\u5f62\u52a0\u7c97\u3001\u659c\u4f53" in enabled_group_map["table"].summary
    assert "首行加粗" in enabled_group_map["table"].summary
    assert "跨页重复表头" in enabled_group_map["table"].summary
