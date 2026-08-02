import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.builtin_templates import create_builtin_template
from src.config.special_title_rules import special_title_selector
from src.config.template import PageNumberPhaseConfig, TemplateConfig
from src.ui.adapters.heading_numbering_adapter import HeadingNumberingAdapter


def test_heading_numbering_adapter_detects_heading_style_changes_as_unsaved():
    template = TemplateConfig()
    adapter = HeadingNumberingAdapter()
    adapter.set_template(template)
    adapter.capture_snapshot()

    assert adapter.has_unsaved_changes is False

    adapter.set_heading_style_field(1, "font_cn", "黑体")

    assert adapter.has_unsaved_changes is True


def test_heading_numbering_adapter_detects_non_numbered_lists_as_unsaved():
    template = TemplateConfig()
    adapter = HeadingNumberingAdapter()
    adapter.set_template(template)
    adapter.capture_snapshot()

    assert adapter.has_unsaved_changes is False

    adapter.set_non_numbered_texts(["摘要", "结论"])

    assert adapter.has_unsaved_changes is True

    adapter.restore_snapshot()
    assert adapter.has_unsaved_changes is False

    adapter.set_non_numbered_prefixes(["附录", "附件", "补充材料"])

    assert adapter.has_unsaved_changes is True


def test_heading_numbering_adapter_preview_skips_non_numbered_titles():
    template = create_builtin_template("thesis_gbt")
    adapter = HeadingNumberingAdapter()
    adapter.set_template(template)
    adapter.set_non_numbered_texts(["摘要"])
    adapter.set_non_numbered_prefixes(["附录"])

    assert adapter.preview_heading_text(1, "摘要") == "摘要"
    assert adapter.preview_heading_text(1, "附录A 数据") == "附录A 数据"
    assert adapter.preview_heading_text(1, "绪论") != "绪论"


def test_heading_numbering_adapter_keeps_scope_references_in_sync_with_literal_rules():
    template = TemplateConfig()
    adapter = HeadingNumberingAdapter()
    adapter.set_template(template)
    old_selector = special_title_selector("exact", "摘要")
    template.header_footer.header.hidden_selectors = [old_selector]
    template.header_footer.footer.hidden_selectors = [old_selector]
    template.header_footer.page_number_plan.phases = [
        PageNumberPhaseConfig(phase_id="special", selectors=[old_selector])
    ]
    adapter.capture_snapshot()

    adapter.set_non_numbered_texts(["内容摘要", "目录", "参考文献", "缩略语表"])

    renamed_selector = special_title_selector("exact", "内容摘要")
    assert template.header_footer.header.hidden_selectors == [renamed_selector]
    assert template.header_footer.footer.hidden_selectors == [renamed_selector]
    assert template.header_footer.page_number_plan.phases[0].selectors == [
        renamed_selector
    ]
    assert adapter.has_unsaved_changes is True

    adapter.restore_snapshot()

    assert template.header_footer.header.hidden_selectors == [old_selector]
    assert template.header_footer.footer.hidden_selectors == [old_selector]
    assert template.header_footer.page_number_plan.phases[0].selectors == [
        old_selector
    ]
    assert adapter.has_unsaved_changes is False

    adapter.set_non_numbered_texts(["目录", "参考文献", "缩略语表"])

    assert old_selector not in template.header_footer.header.hidden_selectors
    assert old_selector not in template.header_footer.footer.hidden_selectors
    assert old_selector not in template.header_footer.page_number_plan.phases[0].selectors


def test_heading_numbering_adapter_non_numbered_style_mode_materializes_custom_style():
    template = create_builtin_template("thesis_gbt")
    adapter = HeadingNumberingAdapter()
    adapter.set_template(template)

    adapter.set_non_numbered_heading_style_mode("custom")

    assert adapter.get_non_numbered_heading_style_mode() == "custom"
    assert adapter.has_non_numbered_heading_style_override() is True

    adapter.set_non_numbered_heading_style_field("font_cn", "黑体")

    assert adapter.get_non_numbered_heading_style().font_cn == "黑体"
