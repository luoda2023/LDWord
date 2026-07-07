import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.builtin_templates import create_builtin_template
from src.config.template import TemplateConfig
from src.ui.panels.template_format import (
    TEMPLATE_PREVIEW_SPECS,
    build_template_page_presentation_envelope,
    build_template_preview_action_text,
    build_template_preview_context,
    build_template_preview_description,
    build_template_preview_groups,
    template_preview_coverage_labels,
)
from src.ui.panels.template_summary_projection import (
    all_template_detail_summaries,
    build_template_detail_summary,
    build_template_detail_summary_items,
)
from src.ui.icons.catalog import get_icon_names


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
    assert "章节编号" in group_map["caption"].summary


def test_detail_summary_projection_covers_all_detail_tiles():
    cfg = create_builtin_template("thesis_gbt")

    expected_counts = {
        "tpl_page": 3,
        "tpl_style": 3,
        "tpl_heading": 3,
        "tpl_table": 3,
        "tpl_header_footer": 3,
        "tpl_toc": 2,
        "tpl_caption": 3,
    }

    summaries = all_template_detail_summaries(cfg)
    assert [summary.detail_card_id for summary in summaries] == list(expected_counts)

    for detail_card_id, expected_count in expected_counts.items():
        summary = build_template_detail_summary(cfg, detail_card_id)
        items = build_template_detail_summary_items(cfg, detail_card_id)

        assert summary.nav_summary
        assert len(summary.tiles) == expected_count
        assert len(items) == expected_count
        assert all(item.value for item in items)


def test_heading_detail_summary_stays_fixed_when_max_levels_change():
    cfg = create_builtin_template("thesis_gbt")
    cfg.heading_model.max_heading_levels = 8

    summary = build_template_detail_summary(cfg, "tpl_heading")

    assert [tile.key for tile in summary.tiles] == [
        "scheme",
        "level_preview",
        "special_rules",
    ]
    assert len(summary.tiles) == 3
    assert "8" in summary.tiles[0].detail
    assert summary.tiles[1].value.startswith("共")
    assert "标题" in summary.tiles[1].value
    assert "..." in summary.tiles[1].detail
    assert "展示" not in summary.tiles[1].detail
    assert "另" not in summary.tiles[1].detail
    assert summary.tiles[2].value.startswith("共")
    assert "非编号标题" in summary.tiles[2].value


def test_preview_groups_share_nav_summary_with_detail_projection():
    cfg = create_builtin_template("thesis_gbt")
    groups = build_template_preview_groups(cfg)

    for group in groups:
        detail_summary = build_template_detail_summary(cfg, group.detail_card_id)
        assert group.summary == detail_summary.nav_summary


def test_template_preview_context_uses_same_groups_for_scene_entry_and_preview_copy():
    cfg = create_builtin_template("thesis_gbt")
    groups = build_template_preview_groups(cfg)
    context = build_template_preview_context(
        cfg,
        scene_label="论文排版",
        template_label="GB/T 7713 学位论文 (thesis_gbt)",
    )

    assert context.coverage_labels == template_preview_coverage_labels(groups)
    assert context.detail_card_ids == tuple(group.detail_card_id for group in groups)
    assert context.action == build_template_preview_action_text(groups)
    assert context.action == "核对页面、正文、标题、表格、页眉页脚、目录和题注"
    assert build_template_preview_description(groups) == (
        "预览页面、正文、标题、表格、页眉页脚、目录和题注在同一页中的效果。"
    )
    assert context.detail == "场景：论文排版；模板：GB/T 7713 学位论文 (thesis_gbt)"


def test_template_page_presentation_envelope_uses_preview_groups():
    cfg = create_builtin_template("thesis_gbt")
    groups = build_template_preview_groups(cfg)
    envelope = build_template_page_presentation_envelope(cfg)

    assert envelope.kind == "template_page"
    assert envelope.title == "样式预览"
    assert envelope.source_label == "模板基线"
    assert envelope.summary == build_template_preview_description(groups)
    assert envelope.action_label == build_template_preview_action_text(groups)
    assert envelope.detail.startswith("当前模板：")


def test_template_management_icon_references_are_registered():
    registered = set(get_icon_names())
    refs: set[str] = set()
    patterns = (
        r'icon_name\s*=\s*"([a-z0-9-]+)"',
        r'get_icon\(\s*"([a-z0-9-]+)"',
        r'_make_card_header\(\s*"([a-z0-9-]+)"',
        r'_add_card_header\(\s*[^,]+,\s*"([a-z0-9-]+)"',
        r'TemplateSummaryCard\([^,\n]+,\s*"([a-z0-9-]+)"',
        r'TemplatePreviewGroupSpec\([^,\n]+,\s*[^,\n]+,\s*[^,\n]+,\s*"([a-z0-9-]+)"',
        r'"tpl_[^"]+"\s*:\s*\([^,\n]+,\s*"([a-z0-9-]+)"',
    )

    for path in (ROOT / "src/ui/panels").glob("template*.py"):
        source = path.read_text(encoding="utf-8")
        for pattern in patterns:
            refs.update(match.group(1) for match in re.finditer(pattern, source))

    assert refs - registered == set()


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
