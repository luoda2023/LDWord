import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.style_difference_projection import StyleDifferenceSummaryProjection
from src.config.template import StyleConfig, TemplateConfig
from src.qt_api import QAbstractAnimation, QBoxLayout, QWidget
from src.shared.ui.card import Card
from src.shared.ui.design_system_card import DesignSystemCard
from src.shared.ui.collapsible_section import CollapsibleSection
from src.shared.ui.icon_button import IconButton
from src.shared.ui.issue_detail_section import IssueDetailSection
from src.shared.ui.module_step_list import ModuleStepItem, ModuleStepList
from src.shared.ui.override_badge import OverrideBadge
from src.shared.ui.placeholder_edit import PlaceholderEdit
from src.shared.ui.scope_zone_checklist import ScopeZoneChecklist, ScopeZoneOption
from src.shared.ui.style_comparison_strip import StyleComparisonStrip
from src.shared.ui.style_difference_summary_slot import StyleDifferenceSummarySlot
from src.shared.ui.style_editing_section import StyleEditingSection
from src.shared.ui.style_management_block import (
    StyleManagementBlock,
    style_management_content_plan,
    style_management_contract,
    style_preview_slot_protocol,
)
from src.shared.ui.style_object_projection import StyleObjectProjection
from src.shared.ui.style_owner_state import (
    scene_section_style_owner_state,
    template_body_style_owner_state,
)
from src.shared.ui.style_owner_status_strip import StyleOwnerStatusStrip
from src.shared.ui.style_owner_toolbar import StyleControlOwnerToolbar, StyleOwnerOption
from src.shared.ui.style_presentation_envelope import StylePresentationEnvelope
from src.shared.ui.style_preview_surface import (
    StylePreviewSurface,
    style_preview_renderer_protocol,
)
from src.shared.ui.style_receipt_slot_frame import StyleReceiptSlotFrame
from src.shared.ui.style_result_receipt_row import StyleResultReceiptRow
from src.shared.ui.style_policy_control_deck import (
    StylePolicyActionProjection,
    StylePolicyControlDeck,
    StylePolicyProjection,
    StylePolicyToggleProjection,
    style_policy_control_protocol,
)
from src.shared.ui.style_policy_toggle_list import (
    StylePolicyToggleList,
    StylePolicyToggleOption,
)
from src.shared.ui.style_rule_control_deck import StyleRuleControlDeck
from src.shared.ui.style_source_compact_row import StyleSourceCompactRow
from src.shared.ui.style_source_slot import StyleSourceSlot
from src.shared.ui.style_override_toggle_list import (
    StyleOverrideToggleList,
    StyleOverrideToggleOption,
)
from src.shared.ui.style_preview import StylePreview, StylePreviewProjection
from src.shared.ui.summary_grid import SummaryGridItem
from src.shared.ui.theme import LIGHT
from src.ui.panels.style_source_projection import (
    build_style_source_projection,
    build_template_style_source_projection,
)
from src.ui.panels.style_object_projection_builders import (
    build_execution_prereview_style_projection,
    build_execution_style_projection,
    build_scene_section_style_policy_projection,
    build_scene_section_style_projection,
    build_template_body_style_projection,
)
from src.config.scene import SceneWorkspace
from src.qt_api import QApplication, Qt


class RecordingPreviewSlot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.calls: list[tuple[object, object, str]] = []

    def apply_preview_projection(self, projection, *, envelope=None, empty_text: str = "") -> None:
        self.calls.append((projection, envelope, empty_text))


def _app():
    return QApplication.instance() or QApplication([])


def test_theme_exposes_small_widget_metric_tokens():
    assert LIGHT.icon_button_size > 0
    assert LIGHT.icon_button_icon_size > 0
    assert LIGHT.override_badge_height > 0
    assert LIGHT.override_badge_icon_size > 0
    assert LIGHT.module_step_item_height > 0
    assert LIGHT.module_step_status_size > 0
    assert LIGHT.collapsible_toggle_height > 0
    assert LIGHT.style_preview_min_height > 0
    assert LIGHT.card_padding_x > 0
    assert LIGHT.card_padding_y > 0


def test_issue_detail_section_exposes_reusable_title_body_tone():
    _app()
    from src.shared.ui import IssueDetailSection as ExportedIssueDetailSection

    section = IssueDetailSection("动作", "处理：去资料页补齐公司名称", tone="info")
    try:
        assert ExportedIssueDetailSection is IssueDetailSection
        assert section.title_label.text() == "动作"
        assert section.body_label.text().startswith("处理：")
        assert section.tone() == "info"

        section.set_title("证据")
        section.set_body("来源：控件边界登记")
        section.set_tone("error")

        assert section.title_label.text() == "证据"
        assert section.body_label.text() == "来源：控件边界登记"
        assert section.tone() == "error"
    finally:
        section.close()


def test_icon_button_defaults_are_tokenized():
    source = inspect.getsource(IconButton)

    assert 'ICON_SIZE = 20' not in source
    assert 'BUTTON_SIZE = 36' not in source
    assert 'icon_button_size' in source
    assert 'icon_button_icon_size' in source


def test_override_badge_restore_button_uses_shared_button_variant_helper():
    source = inspect.getsource(OverrideBadge)

    assert 'apply_button_variant' in source
    assert 'build_button_stylesheet' in source
    assert 'background:transparent' not in source.replace(' ', '')


def test_override_badge_uses_readable_copy_and_single_label_formatter():
    module_source = (ROOT / "src/shared/ui/override_badge.py").read_text(encoding="utf-8")
    source = inspect.getsource(OverrideBadge)

    assert 'ORIGINAL_VALUE_PREFIX = "原值"' in module_source
    assert 'RESTORE_BUTTON_TEXT = "恢复"' in module_source
    assert "def _format_original_label" in source
    assert "self._format_original_label(original_value)" in source
    assert "self._format_original_label(value)" in source
    assert "RESTORE_BUTTON_TEXT" in source
    assert "??" not in module_source


def test_override_badge_further_decomposes_constructor_and_theme_helpers():
    source = inspect.getsource(OverrideBadge)
    init_source = inspect.getsource(OverrideBadge.__init__)
    theme_source = inspect.getsource(OverrideBadge._apply_theme)

    assert "def _build_badge_icon" in source
    assert "def _build_original_value_label" in source
    assert "def _build_restore_button" in source
    assert "def _apply_badge_icon_theme" in source
    assert "def _apply_restore_button_theme" in source

    assert "self._build_badge_icon" in init_source
    assert "self._build_original_value_label" in init_source
    assert "self._build_restore_button" in init_source
    assert "self._apply_badge_icon_theme" in theme_source
    assert "self._apply_restore_button_theme" in theme_source

    assert "QLabel()" not in init_source
    assert "QPushButton(RESTORE_BUTTON_TEXT)" not in init_source
    assert "build_button_stylesheet(" not in theme_source


def test_module_step_widgets_bind_theme_and_use_tokenized_metrics():
    item_source = inspect.getsource(ModuleStepItem)
    list_source = inspect.getsource(ModuleStepList)

    assert 'bind_theme' in item_source or 'bind_theme' in list_source
    assert 'setFixedSize(16, 16)' not in item_source
    assert 'setFixedHeight(32)' not in item_source
    assert 'module_step_status_size' in item_source
    assert 'module_step_item_height' in item_source


def test_card_and_collapsible_section_layout_metrics_are_tokenized():
    card_source = inspect.getsource(DesignSystemCard)
    section_source = inspect.getsource(CollapsibleSection)

    assert issubclass(Card, DesignSystemCard)
    assert '20, 16, 20, 20' not in card_source
    assert 'setFixedHeight(32)' not in section_source
    assert 'card_padding_x' in card_source or 'card_padding_y' in card_source
    assert 'collapsible_toggle_height' in section_source


def test_style_preview_uses_tokenized_metrics():
    source = inspect.getsource(StylePreview)

    assert 'setMinimumHeight(60)' not in source
    assert 'padding: 12px;' not in source
    assert 'style_preview_min_height' in source


def test_style_preview_uses_readable_sample_text():
    assert StylePreview.SAMPLE_TEXT == "样式预览示例 AaBbCc 123"


def test_style_preview_tracks_paragraph_layout_parameters():
    _app()
    preview = StylePreview()

    preview.update_preview(
        sample_text="参考文献样式预览：中文、English、数字 123。",
        alignment="right",
        line_spacing=20,
        left_indent_pt=12,
        right_indent_pt=6,
        first_indent_pt=24,
        hanging_indent_pt=0,
        space_before_pt=3,
        space_after_pt=4,
    )

    assert preview.text().startswith("参考文献样式预览")
    assert preview.alignment() == (Qt.AlignRight | Qt.AlignVCenter)
    assert preview._alignment_value == "right"
    assert preview._line_spacing == 20
    assert preview._left_indent_pt == 12
    assert preview._right_indent_pt == 6
    assert preview._first_indent_pt == 24
    assert preview._space_before_pt == 3
    assert preview._space_after_pt == 4


def test_style_preview_applies_shared_projection_state():
    _app()
    preview = StylePreview()

    class DomainPreview:
        sample_text = "参考文献样式预览：中文、English、数字 123。"
        source_label = "已调整 2 项"
        detail = "不同：中文字体、行距"
        font_cn = "黑体"
        font_en = "Arial"
        size_pt = 14.0
        bold = True
        italic = True
        alignment = "right"
        line_spacing_value = 20.0
        left_indent_pt = 12.0
        right_indent_pt = 6.0
        first_indent_pt = 0.0
        hanging_indent_pt = 10.0
        space_before_pt = 3.0
        space_after_pt = 4.0

    projection = StylePreviewProjection.from_object(DomainPreview())
    preview.apply_projection(projection)

    assert preview.text().startswith("参考文献样式预览")
    assert preview.toolTip() == "已调整 2 项：不同：中文字体、行距"
    assert preview.property("style_preview_source_label") == "已调整 2 项"
    assert preview.property("style_preview_detail") == "不同：中文字体、行距"
    assert preview._alignment_value == "right"
    assert preview._line_spacing == 20.0
    assert preview._hanging_indent_pt == 10.0

    preview.apply_projection(None, empty_text="选择分区后预览样式")
    assert preview.text() == "选择分区后预览样式"
    assert preview.isEnabled() is False
    assert preview.toolTip() == ""


def test_style_presentation_envelope_normalizes_preview_metadata():
    _app()
    preview = StylePreview()

    try:
        envelope = StylePresentationEnvelope(
            kind="section_paragraph",
            title="参考文献",
            source_label="独立样式",
            summary="当前分区有效样式",
            detail="不同：行距、段后",
            action_label="调例外",
        )

        preview.apply_envelope(envelope)

        assert preview.text() == "参考文献：当前分区有效样式"
        assert preview.toolTip() == "独立样式：不同：行距、段后"
        assert preview.property("style_preview_source_label") == "独立样式"
        assert preview.property("style_preview_detail") == "不同：行距、段后"
        assert preview.property("style_presentation_kind") == "section_paragraph"
        assert preview.property("style_presentation_title") == "参考文献"
        assert preview.property("style_presentation_action_label") == "调例外"
    finally:
        preview.close()


def test_style_presentation_envelope_builds_section_paragraph_from_projection():
    class SectionPreview:
        variant_key = "references_body"
        label = "参考文献"
        source_label = "跟随模板"
        detail = "使用模板样式。"

    envelope = StylePresentationEnvelope.from_preview_projection(SectionPreview())

    assert envelope.kind == "section_paragraph"
    assert envelope.title == "参考文献"
    assert envelope.source_label == "跟随模板"
    assert envelope.summary == "跟随模板"
    assert envelope.detail == "使用模板样式。"
    assert envelope.action_label == "调例外"


def test_style_presentation_envelope_builds_template_page_metadata():
    envelope = StylePresentationEnvelope.from_template_page(
        template_label="默认格式",
        summary="页面、正文、标题、表格",
        action_label="编辑正文",
    )

    assert envelope.kind == "template_page"
    assert envelope.title == "样式预览"
    assert envelope.source_label == "模板基线"
    assert envelope.summary == "页面、正文、标题、表格"
    assert envelope.detail == "当前模板：默认格式"
    assert envelope.action_label == "编辑正文"


def test_style_preview_surface_wraps_renderer_and_envelope_metadata():
    _app()
    renderer = StylePreview()
    surface = StylePreviewSurface(
        object_name_prefix="test_style_preview_surface",
        renderer_widget=renderer,
        renderer_kind="paragraph",
    )
    envelope = StylePresentationEnvelope(
        kind="section_paragraph",
        title="参考文献",
        source_label="独立样式",
        summary="当前分区有效样式",
        detail="不同：行距、段后",
        action_label="调例外",
    )

    try:
        surface.apply_envelope(envelope)

        assert surface.objectName() == "test_style_preview_surface_surface"
        assert surface.renderer_widget is renderer
        assert surface.summary_label.text() == "当前分区有效样式"
        assert surface.detail_label.text() == "不同：行距、段后"
        assert surface.detail_label.isHidden() is False
        assert surface.property("style_preview_surface_renderer_kind") == "paragraph"
        assert style_preview_renderer_protocol(renderer) == "envelope_projection"
        assert surface.property("style_preview_surface_renderer_protocol") == (
            "envelope_projection"
        )
        assert surface.property("style_preview_surface_renderer_ready") is True
        assert surface.property("style_presentation_kind") == "section_paragraph"
        assert surface.property("style_presentation_title") == "参考文献"
        assert renderer.property("style_presentation_kind") == "section_paragraph"
        assert renderer.property("style_presentation_title") == "参考文献"
    finally:
        surface.close()


def test_style_preview_surface_can_hide_metadata_for_inline_renderer():
    _app()
    renderer = StylePreview()
    surface = StylePreviewSurface(
        object_name_prefix="test_inline_style_preview_surface",
        renderer_widget=renderer,
        renderer_kind="paragraph",
        show_metadata=False,
    )
    envelope = StylePresentationEnvelope(
        kind="section_paragraph",
        title="参考文献",
        source_label="跟随模板",
        summary="当前分区有效样式",
        detail="使用模板样式。",
    )

    try:
        surface.apply_envelope(envelope)

        assert surface.property("style_preview_surface_show_metadata") is False
        assert surface.property("style_preview_surface_renderer_protocol") == (
            "envelope_projection"
        )
        assert surface.property("style_preview_surface_renderer_ready") is True
        assert surface.summary_label.text() == "当前分区有效样式"
        assert surface.summary_label.isHidden() is True
        assert surface.detail_label.text() == "使用模板样式。"
        assert surface.detail_label.isHidden() is True
        assert renderer.property("style_presentation_title") == "参考文献"
    finally:
        surface.close()


def test_style_preview_surface_rejects_renderer_without_protocol():
    _app()
    surface = StylePreviewSurface(object_name_prefix="test_bad_renderer_surface")
    renderer = QWidget()

    try:
        assert style_preview_renderer_protocol(renderer) == "unsupported"
        with pytest.raises(TypeError, match="renderer_widget"):
            surface.set_renderer(renderer)
        assert surface.renderer_widget is None
        assert surface.property("style_preview_surface_renderer_protocol") == "none"
        assert surface.property("style_preview_surface_renderer_ready") is False
    finally:
        surface.close()


def test_style_presentation_envelope_builds_execution_receipt_from_result():
    envelope = StylePresentationEnvelope.from_execution_result(
        {
            "template_label": "默认格式",
            "section_status": "1 个分区独立设置",
        }
    )

    assert envelope.kind == "execution_receipt"
    assert envelope.title == "样式来源"
    assert envelope.source_label == "本次使用"
    assert envelope.summary == "本次按模板“默认格式”处理"
    assert envelope.detail == "1 个格式例外。"
    assert envelope.receipt_summary(title_fallback="样式来源") == (
        "样式来源：本次按模板“默认格式”处理；1 个格式例外。"
    )


def test_style_presentation_envelope_business_code_uses_named_factories():
    offenders: list[str] = []
    for folder in (ROOT / "src" / "shared", ROOT / "src" / "ui"):
        for path in folder.rglob("*.py"):
            if path.name == "style_presentation_envelope.py":
                continue
            source = path.read_text(encoding="utf-8")
            if "StylePresentationEnvelope(" in source:
                offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_style_comparison_strip_projects_template_current_and_diff():
    _app()
    strip = StyleComparisonStrip(object_name_prefix="test_style_comparison")

    class ComparisonProjection:
        template_status = "模板基线"
        current_status = "独立样式"
        difference_status = "已调整 2 项"
        detail = "不同：中文字体、行距"

    try:
        strip.apply_projection(ComparisonProjection())

        assert strip.template_label.text() == "模板基线：模板基线"
        assert strip.current_label.text() == "当前分区：独立样式"
        assert strip.difference_label.text() == "差异：已调整 2 项"
        assert strip.property("style_compare_template_status") == "模板基线"
        assert strip.property("style_compare_current_status") == "独立样式"
        assert strip.property("style_compare_difference_status") == "已调整 2 项"
        assert strip.property("style_compare_detail") == "不同：中文字体、行距"
        assert strip.toolTip() == "不同：中文字体、行距"

        strip.apply_projection(None)
        assert strip.current_label.text() == "当前分区：选择分区"
        assert strip.isEnabled() is False
    finally:
        strip.close()


def test_style_difference_summary_slot_wraps_comparison_strip_with_semantic_role():
    _app()
    slot = StyleDifferenceSummarySlot(object_name_prefix="test_style_difference")

    class ComparisonProjection:
        template_status = "模板基线"
        current_status = "独立样式"
        difference_status = "已调整 2 项"
        detail = "不同：中文字体、行距"

    try:
        assert slot.objectName() == "test_style_difference_difference_slot"
        assert slot.comparison_strip.objectName() == "test_style_difference_comparison"
        assert slot.property("style_difference_content_plan") == "difference"
        assert slot.property("style_difference_slot_surface") == "embedded"
        assert slot.property("style_difference_has_projection") is False

        slot.apply_projection(ComparisonProjection())

        assert slot.property("style_difference_has_projection") is True
        assert slot.property("style_difference_template_status") == "模板基线"
        assert slot.property("style_difference_current_status") == "独立样式"
        assert slot.property("style_difference_status") == "已调整 2 项"
        assert slot.property("style_difference_detail") == "不同：中文字体、行距"
        assert slot.comparison_strip.difference_label.text() == "差异：已调整 2 项"

        slot.apply_projection(None)
        assert slot.property("style_difference_has_projection") is False
        assert slot.comparison_strip.isEnabled() is False
    finally:
        slot.close()


def test_style_source_compact_row_projects_template_section_and_actions():
    _app()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    scene.section_styles["references_body"] = StyleConfig()
    projection = build_style_source_projection(
        scene,
        template_label="默认格式",
        template_preview_action="核对页面、正文和 OOXML 对象",
    )
    row = StyleSourceCompactRow(object_name_prefix="test_style_source")
    targets: list[str] = []
    row.navigate_requested.connect(targets.append)

    try:
        row.apply_projection(projection)

        assert row._label.text() == "样式来源"
        assert row._status.text() == "有格式例外"
        assert row._template_line.text() == "模板：默认格式，核对页面、正文和 Word 对象"
        assert row._section_line.text() == "例外：1 个格式例外：参考文献"
        assert row.summary_text() == (
            "模板：默认格式，核对页面、正文和 Word 对象；"
            "例外：1 个格式例外：参考文献"
        )
        assert row._jump_btn.text() == "看模板"
        assert row._secondary_jump_btn.text() == "调例外"
        assert row.property("style_source_view_mode") == "scene_editable"
        row.resize(900, 80)
        row.show()
        _app().processEvents()
        assert isinstance(row._actions_wrap.layout(), QBoxLayout)
        assert row._actions_wrap.layout().direction() == QBoxLayout.LeftToRight
        assert row._actions_wrap.sizeHint().height() <= max(
            row._jump_btn.sizeHint().height(),
            row._secondary_jump_btn.sizeHint().height(),
        ) + 8

        row._jump_btn.click()
        row._secondary_jump_btn.click()

        assert targets == ["tpl_overview", "scn_rules"]
    finally:
        row.close()


def test_style_source_compact_row_projects_template_baseline_without_section_action():
    _app()
    projection = build_template_style_source_projection(
        TemplateConfig(name="默认格式")
    )
    row = StyleSourceCompactRow(object_name_prefix="test_template_style_source")
    targets: list[str] = []
    row.navigate_requested.connect(targets.append)

    try:
        row.apply_projection(projection)

        assert projection.status_label == "模板基线"
        assert projection.view_mode == "template_baseline"
        assert projection.has_independent_sections is False
        assert row._label.text() == "样式来源"
        assert row._status.text() == "模板基线"
        assert row._template_line.text() == "模板：默认格式，作为样式基线"
        assert row._section_line.text() == "场景例外：默认跟随此模板"
        assert row.summary_text() == "模板：默认格式，作为样式基线；场景例外：默认跟随此模板"
        assert row._jump_btn.text() == "编辑正文"
        assert row._secondary_jump_btn.isHidden() is True
        assert row.property("style_source_view_mode") == "template_baseline"

        row._jump_btn.click()

        assert targets == ["tpl_style"]
    finally:
        row.close()


def test_style_source_compact_row_hides_actions_for_readonly_projection():
    _app()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    projection = build_style_source_projection(
        scene,
        template_label="默认格式",
        view_mode="readonly",
    )
    row = StyleSourceCompactRow(object_name_prefix="test_readonly_style_source")

    try:
        row.apply_projection(projection)

        assert row.property("style_source_view_mode") == "readonly"
        assert row._status.text() == "跟随模板"
        assert row._template_line.text() == "模板：默认格式"
        assert row._section_line.text() == "例外：无格式例外"
        assert row._jump_btn.isHidden() is True
        assert row._secondary_jump_btn.isHidden() is True
        assert row._actions_wrap.isHidden() is True
    finally:
        row.close()


def test_style_source_compact_row_omits_section_action_for_execution_review_when_following_template():
    _app()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    projection = build_style_source_projection(
        scene,
        template_label="默认格式",
        view_mode="execution_review",
    )
    row = StyleSourceCompactRow(object_name_prefix="test_execution_style_source")
    targets: list[str] = []
    row.navigate_requested.connect(targets.append)

    try:
        row.apply_projection(projection)

        assert projection.secondary_action.target_card_id == ""
        assert row.property("style_source_view_mode") == "execution_review"
        assert row._jump_btn.text() == "看模板"
        assert row._jump_btn.isHidden() is False
        assert row._secondary_jump_btn.isHidden() is True
        assert row._actions_wrap.isHidden() is False

        row._jump_btn.click()

        assert targets == ["tpl_overview"]
    finally:
        row.close()


def test_style_source_slot_wraps_compact_row_context_and_projection():
    _app()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    scene.section_styles["references_body"] = StyleConfig()
    projection = build_style_source_projection(
        scene,
        template_label="默认格式",
        view_mode="execution_review",
    )
    slot = StyleSourceSlot(
        object_name_prefix="test_style_source_scope",
        row_object_name_prefix="test_style_source_slot_row",
    )
    context = QWidget(slot)
    context.setObjectName("test_style_source_context")
    targets: list[str] = []
    slot.navigate_requested.connect(targets.append)

    try:
        slot.add_context_widget(context)
        slot.apply_projection(projection)

        row = slot.source_row
        assert isinstance(row, StyleSourceCompactRow)
        assert slot.objectName() == "test_style_source_scope_slot"
        assert context.parentWidget() is slot
        assert slot.layout().itemAt(0).widget() is context
        assert row._status.text() == "有格式例外"
        assert row.property("style_source_view_mode") == "execution_review"
        assert slot.property("style_source_slot_has_projection") is True
        assert slot.property("style_source_slot_view_mode") == "execution_review"
        assert slot.property("style_source_slot_status_label") == "有格式例外"

        row._jump_btn.click()
        row._secondary_jump_btn.click()

        assert targets == ["tpl_overview", "scn_rules"]
    finally:
        slot.close()


def test_style_control_owner_toolbar_manages_selection_hint_and_action():
    _app()
    toolbar = StyleControlOwnerToolbar(
        title="编辑样式",
        selector_label="编辑分区",
        action_label="恢复模板",
        object_name_prefix="test_owner_toolbar",
    )
    changed: list[str] = []
    clicked: list[bool] = []
    toolbar.current_key_changed.connect(changed.append)
    toolbar.action_requested.connect(lambda: clicked.append(True))

    try:
        toolbar.set_options(
            (
                StyleOwnerOption("references_body", "参考文献"),
                StyleOwnerOption("appendix_body", "附录"),
            )
        )
        assert toolbar.current_key() == "references_body"

        assert toolbar.set_current_key("appendix_body") is True
        assert toolbar.current_key() == "appendix_body"
        assert changed == []

        toolbar.selector.setCurrentIndex(0)
        assert changed == ["references_body"]

        toolbar.set_action_enabled(False)
        assert toolbar.action_button.isEnabled() is False
        toolbar.set_action_enabled(True)
        toolbar.action_button.click()
        assert clicked == [True]

        toolbar.set_hint("开启独立样式后可编辑")
        assert toolbar.hint_label.text() == "开启独立样式后可编辑"
    finally:
        toolbar.close()


def test_style_editing_section_wraps_owner_preview_and_surface():
    _app()
    source = (ROOT / "src/shared/ui/style_editing_section.py").read_text(
        encoding="utf-8"
    )
    shell = StyleEditingSection(
        object_name_prefix="test_style_editing",
        owner_options=(
            StyleOwnerOption("references_body", "参考文献"),
            StyleOwnerOption("appendix_body", "附录"),
        ),
        owner_title="编辑样式",
        selector_label="编辑分区",
        action_label="恢复模板",
        preview_object_name="test_style_editing_preview",
    )
    changed: list[str] = []
    clicked: list[bool] = []
    shell.current_key_changed.connect(changed.append)
    shell.action_requested.connect(lambda: clicked.append(True))

    try:
        assert shell.owner_toolbar is not None
        assert shell.selector.objectName() == "test_style_editing_owner_selector"
        assert shell.action_button.objectName() == "test_style_editing_owner_action"
        assert isinstance(shell.preview_surface, StylePreviewSurface)
        assert shell.preview_surface.renderer_widget is shell.preview
        assert shell.preview_surface.property("style_preview_surface_show_metadata") is False
        assert shell.preview.objectName() == "test_style_editing_preview"
        assert shell.style_surface.editor is shell.editor
        assert shell.unit_labels == (shell.editor.line_value_suffix,)

        assert shell.set_current_key("appendix_body") is True
        assert shell.current_key() == "appendix_body"
        shell.selector.setCurrentIndex(0)
        assert changed == ["references_body"]

        shell.apply_preview_projection(None, empty_text="选择分区后预览样式")
        assert shell.preview.text() == "选择分区后预览样式"
        assert shell.preview.isEnabled() is False
        assert shell.preview.property("style_presentation_kind") == ""
        assert shell.preview_surface.property("style_presentation_kind") == (
            "section_paragraph"
        )

        class SectionPreview:
            variant_key = "references_body"
            label = "参考文献"
            sample_text = "参考文献样式预览：中文、English、数字 123。"
            source_label = "跟随模板"
            detail = "使用模板样式。"
            font_cn = "宋体"
            font_en = "Times New Roman"
            size_pt = 12.0
            bold = False
            italic = False
            alignment = "justify"
            line_spacing_value = 20.0

        shell.apply_preview_projection(SectionPreview())
        assert shell.preview_surface.presentation_envelope.kind == "section_paragraph"
        assert shell.preview.property("style_presentation_kind") == "section_paragraph"
        assert shell.preview.property("style_presentation_title") == "参考文献"
        assert shell.preview.property("style_presentation_summary") == "跟随模板"
        assert shell.preview.property("style_presentation_detail") == "使用模板样式。"
        assert shell.preview.property("style_presentation_action_label") == "调例外"
        assert shell.preview_surface.property("style_presentation_kind") == (
            "section_paragraph"
        )
        assert shell.preview_surface.property("style_presentation_title") == "参考文献"
        assert "self._preview_surface.apply_preview_projection(" in source
        assert "self._preview.apply_envelope(" not in source
        assert "StylePreviewProjection.from_object" not in source

        style = StyleConfig(font_cn="宋体")
        owner_state = template_body_style_owner_state(style)
        shell.apply_owner_state(owner_state)
        assert shell.style_surface.property("style_surface_owner_kind") == (
            "template_body_style"
        )
        assert shell.owner_status.source_label.text() == "来源：模板默认样式"
        assert shell.owner_status.scope_label.text() == "影响：模板全局"
        assert shell.owner_status.edit_label.text() == "编辑：可编辑"
        assert shell.action_button.isEnabled() is owner_state.action_enabled

        shell.action_button.click()
        assert clicked == [True]
    finally:
        shell.close()


def test_style_management_block_wraps_summary_controls_preview_and_surface():
    _app()
    rule_deck = StyleRuleControlDeck(
        object_name_prefix="test_style_block_rules",
        toggle_options=(
            StylePolicyToggleOption("references_body", "参考文献", "启用独立样式"),
        ),
    )
    block = StyleManagementBlock(
        title="分区样式",
        object_name_prefix="test_style_block",
        summary_items=(
            SummaryGridItem(
                key="status",
                label="状态",
                value="跟随模板",
                detail="开启后仅影响当前场景。",
            ),
        ),
        rule_control=rule_deck,
        owner_options=(StyleOwnerOption("references_body", "参考文献"),),
        owner_title="编辑样式",
        selector_label="编辑分区",
        action_label="恢复模板",
        collapse_surface_when_readonly=True,
    )

    try:
        assert block.summary.value_for("status") == "跟随模板"
        assert block.selector.objectName() == "test_style_block_owner_selector"
        assert block.preview.objectName() == "test_style_block_preview"
        assert block.style_surface.editor is block.editor
        assert block.unit_labels == (block.editor.line_value_suffix,)
        assert block.rule_control is rule_deck
        assert rule_deck.parentWidget() is block.card

        block.apply_owner_state(template_body_style_owner_state(StyleConfig()))
        assert block.style_surface.isHidden() is False
        assert block.owner_status.property("style_owner_source_status") == (
            "模板默认样式"
        )
        assert block.owner_status.property("style_owner_scope_status") == "模板全局"

        block.apply_owner_state(
            scene_section_style_owner_state(
                style=StyleConfig(),
                variant_label="参考文献",
                section_enabled=True,
                overridden=False,
            )
        )
        assert block.style_surface.isHidden() is True
        assert block.action_button.isEnabled() is False
        assert block.owner_status.property("style_owner_source_status") == "参考文献"
        assert block.owner_status.property("style_owner_scope_status") == "来自模板"
        assert block.owner_status.property("style_owner_edit_status") == (
            "开启独立样式后可编辑"
        )
    finally:
        block.close()


def test_style_management_block_applies_unified_style_object_projection():
    _app()
    difference_slot = StyleDifferenceSummarySlot(
        object_name_prefix="test_style_object_projection_difference"
    )
    rule_deck = StyleRuleControlDeck(
        object_name_prefix="test_style_object_projection_rules"
    )
    block = StyleManagementBlock(
        title="分区样式",
        object_name_prefix="test_style_object_projection",
        mode="scene_section_rules",
        rule_control=rule_deck,
        difference_slot=difference_slot,
        owner_options=(StyleOwnerOption("references_body", "参考文献"),),
    )

    class SectionPreview:
        label = "参考文献"
        source_label = "跟随模板"
        summary = "参考文献样式预览"
        detail = "使用模板样式。"
        action_label = "调例外"
        variant_key = "references_body"
        sample_text = "参考文献：这是样式预览。"
        font_cn = "宋体"
        font_en = "Times New Roman"
        size_pt = 12
        bold = False
        italic = False
        alignment = "left"
        line_spacing_type = "multiple"
        line_spacing_value = 1.5
        left_indent_pt = 0
        right_indent_pt = 0
        first_indent_pt = 0
        hanging_indent_pt = 0
        space_before_pt = 0
        space_after_pt = 0

    class Difference:
        template_status = "模板基线"
        current_status = "跟随模板"
        difference_status = "未改字段"
        detail = "使用模板样式。"
        variant = "info"

    owner_state = scene_section_style_owner_state(
        style=StyleConfig(),
        variant_label="参考文献",
        section_enabled=True,
        overridden=False,
    )
    projection = StyleObjectProjection.from_owner_state(
        kind="scene_section_style",
        object_label="参考文献",
        owner_state=owner_state,
        summary_items=(
            SummaryGridItem(
                key="style_state",
                label="当前状态",
                value="跟随模板",
                detail="使用模板样式。",
            ),
        ),
        preview_projection=SectionPreview(),
        difference=Difference(),
        policy=StylePolicyProjection(
            kind="scene_section_style",
            title="独立样式",
            toggles=(
                StylePolicyToggleProjection(
                    key="references_body",
                    label="参考文献",
                    checked=True,
                    visible=True,
                ),
            ),
            restore_all=StylePolicyActionProjection(
                label="全部跟随模板",
                enabled=True,
                labels=("参考文献",),
            ),
        ),
        empty_preview_text="选择分区后预览样式",
    )

    try:
        block.apply_style_object_projection(projection)

        assert block.property("style_object_kind") == "scene_section_style"
        assert block.property("style_object_label") == "参考文献"
        assert block.property("style_object_source_label") == "参考文献"
        assert block.property("style_object_scope_label") == "来自模板"
        assert block.property("style_object_edit_state_label") == (
            "开启独立样式后可编辑"
        )
        assert block.summary.value_for("style_state") == "跟随模板"
        assert block.owner_status.property("style_owner_scope_status") == "来自模板"
        assert block.style_surface.isHidden() is True
        assert block.preview.property("style_presentation_source_label") == "跟随模板"
        assert block.preview.property("style_presentation_action_label") == "调例外"
        assert difference_slot.property("style_difference_template_status") == "模板基线"
        assert difference_slot.property("style_difference_current_status") == "跟随模板"
        assert block.property("style_management_rule_control_protocol") == (
            "policy_projection"
        )
        assert block.property("style_management_rule_control_ready") is True
        assert style_policy_control_protocol(rule_deck) == "policy_projection"
        assert rule_deck.property("style_policy_kind") == "scene_section_style"
        assert rule_deck.property("style_policy_title") == "独立样式"
        assert rule_deck.property("style_policy_toggle_count") == 1
        assert rule_deck.toggles["references_body"].isChecked() is True
        assert rule_deck.restore_all_button.isEnabled() is True
    finally:
        block.close()


def test_style_management_block_named_modes_project_shared_contracts():
    _app()
    template_contract = style_management_contract("template_baseline_edit")
    template_plan = style_management_content_plan("template_baseline_edit")
    assert template_contract.show_owner_toolbar is False
    assert template_contract.show_owner_status is False
    assert template_contract.show_preview is False
    assert template_contract.collapse_surface_when_readonly is False
    assert template_plan.sections() == ("source", "scope", "editor")

    scene_plan = style_management_content_plan("scene_section_rules")
    assert scene_plan.sections() == (
        "source",
        "scope",
        "rules",
        "difference",
        "editor",
        "preview",
    )
    assert scene_plan.slots() == (
        "source",
        "scope",
        "policy",
        "difference",
        "editor",
        "preview",
    )
    assert scene_plan.encoded_slots() == (
        "source|scope|policy|difference|editor|preview"
    )
    assert scene_plan.policy is True
    overview_preview_plan = style_management_content_plan("template_overview_preview")
    assert overview_preview_plan.sections() == ("preview",)
    execution_receipt_plan = style_management_content_plan("execution_receipt_review")
    assert execution_receipt_plan.sections() == ("receipt",)
    execution_prereview_contract = style_management_contract("execution_prereview")
    execution_prereview_plan = style_management_content_plan("execution_prereview")
    assert execution_prereview_contract.show_owner_toolbar is False
    assert execution_prereview_contract.show_owner_status is False
    assert execution_prereview_contract.show_preview is False
    assert execution_prereview_plan.sections() == ("source", "scope", "difference")
    readonly_review_contract = style_management_contract("readonly_review")
    readonly_review_plan = style_management_content_plan("readonly_review")
    assert readonly_review_contract.show_owner_toolbar is False
    assert readonly_review_contract.show_owner_status is True
    assert readonly_review_contract.show_preview is True
    assert readonly_review_contract.collapse_surface_when_readonly is True
    assert readonly_review_plan.sections() == (
        "source",
        "scope",
        "preview",
        "receipt",
    )

    template_block = StyleManagementBlock(
        title="正文排版",
        object_name_prefix="test_template_style_block",
        mode="template_baseline_edit",
    )
    rule_deck = StyleRuleControlDeck(
        object_name_prefix="test_scene_style_block_rules",
        toggle_options=(
            StylePolicyToggleOption("references_body", "参考文献", "启用独立样式"),
        ),
    )
    scene_block = StyleManagementBlock(
        title="分区样式",
        object_name_prefix="test_scene_style_block",
        mode="scene_section_rules",
        rule_control=rule_deck,
        difference_slot=rule_deck.difference_slot,
        owner_options=(StyleOwnerOption("references_body", "参考文献"),),
    )
    preview_slot = RecordingPreviewSlot()
    preview_block = StyleManagementBlock(
        title="样式预览",
        object_name_prefix="test_template_overview_preview",
        mode="template_overview_preview",
        preview_slot=preview_slot,
    )
    receipt_slot = QWidget()
    execution_receipt_block = StyleManagementBlock(
        title="样式回执",
        object_name_prefix="test_execution_receipt",
        mode="execution_receipt_review",
        receipt_slot=receipt_slot,
    )
    execution_prereview_block = StyleManagementBlock(
        title="执行前复核",
        object_name_prefix="test_execution_prereview",
        mode="execution_prereview",
    )
    readonly_receipt_slot = QWidget()
    readonly_review_block = StyleManagementBlock(
        title="只读复核",
        object_name_prefix="test_readonly_review",
        mode="readonly_review",
        receipt_slot=readonly_receipt_slot,
    )
    try:
        assert template_block.property("style_management_mode") == (
            "template_baseline_edit"
        )
        assert template_block.contract.mode == "template_baseline_edit"
        assert template_block.content_plan.sections() == (
            "source",
            "scope",
            "editor",
        )
        assert template_block.property("style_management_content_plan") == (
            "source|scope|editor"
        )
        assert template_block.property("style_management_slot_plan") == (
            "source|scope|editor"
        )
        assert template_block.property("style_management_has_policy") is False
        assert template_block.property("style_management_has_policy_slot") is False
        assert template_block.property("style_management_has_rules") is False
        assert template_block.property("style_management_rule_control_protocol") == "none"
        assert template_block.property("style_management_rule_control_ready") is False
        assert template_block.property("style_management_policy_control_protocol") == "none"
        assert template_block.property("style_management_policy_control_ready") is False
        assert template_block.property("style_management_has_preview") is False
        assert template_block.effective_preview_slot is None
        assert template_block.property("style_management_effective_preview_protocol") == (
            "none"
        )
        assert template_block.property("style_management_effective_preview_ready") is False
        assert template_block.owner_status is None
        assert template_block.owner_toolbar is None
        assert template_block.preview is None

        assert scene_block.property("style_management_mode") == "scene_section_rules"
        assert scene_block.contract.mode == "scene_section_rules"
        assert scene_block.content_plan.sections() == (
            "source",
            "scope",
            "rules",
            "difference",
            "editor",
            "preview",
        )
        assert scene_block.property("style_management_content_plan") == (
            "source|scope|rules|difference|editor|preview"
        )
        assert scene_block.property("style_management_slot_plan") == (
            "source|scope|policy|difference|editor|preview"
        )
        assert scene_block.property("style_management_has_rules") is True
        assert scene_block.property("style_management_has_policy") is True
        assert scene_block.property("style_management_has_policy_slot") is True
        assert scene_block.property("style_management_rule_control_protocol") == (
            "policy_projection"
        )
        assert scene_block.property("style_management_rule_control_ready") is True
        assert scene_block.property("style_management_policy_control_protocol") == (
            "policy_projection"
        )
        assert scene_block.property("style_management_policy_control_ready") is True
        assert style_policy_control_protocol(scene_block.rule_control) == (
            "policy_projection"
        )
        assert scene_block.property("style_management_has_difference") is True
        assert scene_block.property("style_management_has_difference_slot") is True
        assert scene_block.property("style_management_has_preview") is True
        assert scene_block.preview_slot is None
        assert scene_block.effective_preview_slot is (
            scene_block.editing_section.preview_surface
        )
        assert scene_block.property("style_management_preview_slot_protocol") == "none"
        assert scene_block.property("style_management_preview_slot_ready") is False
        assert scene_block.property("style_management_effective_preview_protocol") == (
            "preview_projection"
        )
        assert scene_block.property("style_management_effective_preview_ready") is True
        assert scene_block.difference_slot is rule_deck.difference_slot
        assert rule_deck.difference_slot.parentWidget() is rule_deck
        assert scene_block.owner_toolbar is not None
        assert scene_block.selector.objectName() == "test_scene_style_block_owner_selector"
        assert scene_block.action_button.text() == "恢复模板"
        assert scene_block.preview.objectName() == "test_scene_style_block_preview"

        scene_block.apply_owner_state(
            scene_section_style_owner_state(
                style=StyleConfig(),
                variant_label="参考文献",
                section_enabled=True,
                overridden=False,
            )
        )
        assert scene_block.style_surface.isHidden() is True

        assert preview_block.property("style_management_mode") == (
            "template_overview_preview"
        )
        assert preview_block.content_plan.sections() == ("preview",)
        assert preview_block.property("style_management_content_plan") == "preview"
        assert preview_block.property("style_management_has_editor") is False
        assert preview_block.property("style_management_has_preview") is True
        assert preview_block.preview_slot is preview_slot
        assert preview_block.effective_preview_slot is preview_slot
        assert preview_block.property("style_management_preview_slot_protocol") == (
            "preview_projection"
        )
        assert preview_block.property("style_management_preview_slot_ready") is True
        assert preview_block.property("style_management_effective_preview_protocol") == (
            "preview_projection"
        )
        assert preview_block.property("style_management_effective_preview_ready") is True
        assert preview_block.preview is None
        assert preview_block.layout().indexOf(preview_block.editing_section) == -1
        assert preview_block.editing_section.isHidden() is True
        assert preview_block.style_surface.isHidden() is True

        assert execution_receipt_block.property("style_management_mode") == (
            "execution_receipt_review"
        )
        assert execution_receipt_block.content_plan.sections() == ("receipt",)
        assert execution_receipt_block.property("style_management_content_plan") == (
            "receipt"
        )
        assert execution_receipt_block.property("style_management_has_editor") is False
        assert execution_receipt_block.property("style_management_has_receipt") is True
        assert execution_receipt_block.receipt_slot is receipt_slot
        assert execution_receipt_block.preview is None
        assert execution_receipt_block.layout().indexOf(
            execution_receipt_block.editing_section
        ) == -1

        assert execution_prereview_block.property("style_management_mode") == (
            "execution_prereview"
        )
        assert execution_prereview_block.content_plan.sections() == (
            "source",
            "scope",
            "difference",
        )
        assert execution_prereview_block.property(
            "style_management_content_plan"
        ) == "source|scope|difference"
        assert execution_prereview_block.property(
            "style_management_slot_plan"
        ) == "source|scope|difference"
        assert execution_prereview_block.property(
            "style_management_has_policy"
        ) is False
        assert execution_prereview_block.property(
            "style_management_has_policy_slot"
        ) is False
        assert execution_prereview_block.property(
            "style_management_has_difference"
        ) is True
        assert execution_prereview_block.property(
            "style_management_has_editor"
        ) is False
        assert execution_prereview_block.preview is None
        assert execution_prereview_block.effective_preview_slot is None
        assert execution_prereview_block.property(
            "style_management_effective_preview_protocol"
        ) == "none"
        assert execution_prereview_block.property(
            "style_management_effective_preview_ready"
        ) is False
        assert execution_prereview_block.layout().indexOf(
            execution_prereview_block.editing_section
        ) == -1

        assert readonly_review_block.property("style_management_mode") == (
            "readonly_review"
        )
        assert readonly_review_block.content_plan.sections() == (
            "source",
            "scope",
            "preview",
            "receipt",
        )
        assert readonly_review_block.property("style_management_content_plan") == (
            "source|scope|preview|receipt"
        )
        assert readonly_review_block.property("style_management_has_editor") is False
        assert readonly_review_block.property("style_management_has_preview") is True
        assert readonly_review_block.property("style_management_has_receipt") is True
        assert readonly_review_block.receipt_slot is readonly_receipt_slot
        assert readonly_review_block.effective_preview_slot is (
            readonly_review_block.editing_section.preview_surface
        )
        assert readonly_review_block.property(
            "style_management_effective_preview_protocol"
        ) == "preview_projection"
        assert readonly_review_block.property(
            "style_management_effective_preview_ready"
        ) is True
        assert readonly_review_block.owner_status is not None
        assert readonly_review_block.owner_toolbar is None
        assert readonly_review_block.preview is not None
        assert readonly_review_block.style_surface.isHidden() is True
        assert readonly_review_block.layout().indexOf(
            readonly_review_block.editing_section
        ) == -1
    finally:
        template_block.close()
        scene_block.close()
        preview_block.close()
        execution_receipt_block.close()
        execution_prereview_block.close()
        readonly_review_block.close()


def test_style_management_block_named_slots_update_plan():
    _app()
    source_slot = QWidget()
    source_slot.setObjectName("test_style_source_slot")
    scope_slot = QWidget()
    scope_slot.setObjectName("test_style_scope_slot")
    difference_slot = StyleDifferenceSummarySlot(
        object_name_prefix="test_style_difference_named_slot"
    )
    preview_slot = RecordingPreviewSlot()
    preview_slot.setObjectName("test_style_preview_slot")
    receipt_slot = QWidget()
    receipt_slot.setObjectName("test_style_receipt_slot")
    block = StyleManagementBlock(
        title="只读复核",
        object_name_prefix="test_style_review_block",
        mode="template_baseline_edit",
        source_slot=source_slot,
        scope_slot=scope_slot,
        difference_slot=difference_slot,
        preview_slot=preview_slot,
        receipt_slot=receipt_slot,
    )

    try:
        assert block.source_slot is source_slot
        assert block.scope_slot is scope_slot
        assert block.difference_slot is difference_slot
        assert block.preview_slot is preview_slot
        assert block.effective_preview_slot is preview_slot
        assert block.receipt_slot is receipt_slot
        assert source_slot.parentWidget() is block.card
        assert scope_slot.parentWidget() is block.card
        assert difference_slot.parentWidget() is block.card
        assert preview_slot.parentWidget() is block.card
        assert receipt_slot.parentWidget() is block.card
        assert block.content_plan.sections() == (
            "source",
            "scope",
            "difference",
            "editor",
            "preview",
            "receipt",
        )
        assert block.property("style_management_content_plan") == (
            "source|scope|difference|editor|preview|receipt"
        )
        assert block.property("style_management_has_source_slot") is True
        assert block.property("style_management_has_scope_slot") is True
        assert block.property("style_management_has_difference_slot") is True
        assert block.property("style_management_has_difference") is True
        assert block.property("style_management_has_preview") is True
        assert block.property("style_management_has_receipt") is True
        assert style_preview_slot_protocol(preview_slot) == "preview_projection"
        assert block.property("style_management_preview_slot_protocol") == (
            "preview_projection"
        )
        assert block.property("style_management_preview_slot_ready") is True
        assert block.property("style_management_effective_preview_protocol") == (
            "preview_projection"
        )
        assert block.property("style_management_effective_preview_ready") is True
    finally:
        block.close()


def test_style_management_block_rejects_preview_slot_without_protocol():
    _app()
    preview_slot = QWidget()

    with pytest.raises(TypeError, match="preview_slot"):
        StyleManagementBlock(
            title="无协议预览",
            object_name_prefix="test_bad_preview_slot",
            mode="template_overview_preview",
            preview_slot=preview_slot,
        )


def test_style_management_block_rejects_rule_control_without_policy_protocol():
    _app()
    rule_control = QWidget()

    assert style_policy_control_protocol(rule_control) == "unsupported"
    with pytest.raises(TypeError, match="rule_control"):
        StyleManagementBlock(
            title="无协议策略区",
            object_name_prefix="test_bad_rule_control",
            mode="scene_section_rules",
            rule_control=rule_control,
        )


def test_style_management_block_legacy_widgets_are_auditable():
    _app()
    legacy_widget = QWidget()
    legacy_widget.setObjectName("test_style_legacy_widget")
    block = StyleManagementBlock(
        title="兼容区",
        object_name_prefix="test_style_legacy_block",
        management_widgets=(legacy_widget,),
    )

    try:
        assert block.legacy_management_widgets == (legacy_widget,)
        assert legacy_widget.parentWidget() is block.card
        assert block.property("style_management_has_legacy_widgets") is True
    finally:
        block.close()


def test_style_management_block_business_code_uses_named_slots():
    offenders: list[str] = []
    for folder in (ROOT / "src" / "shared", ROOT / "src" / "ui"):
        for path in folder.rglob("*.py"):
            if path.name == "style_management_block.py":
                continue
            source = path.read_text(encoding="utf-8")
            if "management_widgets=" in source:
                offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_style_owner_status_strip_projects_owner_state():
    _app()
    strip = StyleOwnerStatusStrip(object_name_prefix="test_style_owner_status")
    try:
        strip.apply_owner_state(template_body_style_owner_state(StyleConfig()))

        assert strip.source_label.text() == "来源：模板默认样式"
        assert strip.scope_label.text() == "影响：模板全局"
        assert strip.edit_label.text() == "编辑：可编辑"
        assert strip.property("style_owner_source_status") == "模板默认样式"
        assert strip.property("style_owner_scope_status") == "模板全局"
        assert strip.property("style_owner_edit_status") == "可编辑"

        strip.apply_owner_state(
            scene_section_style_owner_state(
                style=StyleConfig(),
                variant_label="参考文献",
                section_enabled=True,
                overridden=False,
            )
        )

        assert strip.source_label.text() == "来源：参考文献"
        assert strip.scope_label.text() == "影响：来自模板"
        assert strip.edit_label.text() == "编辑：开启独立样式后可编辑"
    finally:
        strip.close()


def test_style_owner_view_state_projects_template_and_scene_states():
    style = StyleConfig(font_cn="宋体")

    template_state = template_body_style_owner_state(style)
    assert template_state.surface_state.owner_kind == "template_body_style"
    assert template_state.surface_state.active_label == "正文排版"
    assert template_state.surface_state.source_label == "模板默认样式"
    assert template_state.surface_state.editable is True
    assert template_state.surface_state.style is style
    assert template_state.source_status == "模板默认样式"
    assert template_state.scope_status == "模板全局"
    assert template_state.edit_status == "可编辑"

    empty_template_state = template_body_style_owner_state(None)
    assert empty_template_state.surface_state.editable is False
    assert empty_template_state.surface_state.readonly_reason == "未选择模板"
    assert empty_template_state.action_enabled is False
    assert empty_template_state.scope_status == "无可编辑范围"
    assert empty_template_state.edit_status == "先选择模板"

    class Projection:
        label = "参考文献"
        status_value = "已调整 2 项"
        status_detail = "不同：中文字体、行距"
        editor_hint = "正在编辑「参考文献」：中文字体、行距不同。"
        editable = True
        overridden = True

    scene_state = scene_section_style_owner_state(
        style=style,
        projection=Projection(),
        variant_label="参考文献",
        section_enabled=True,
        overridden=True,
    )
    assert scene_state.surface_state.owner_kind == "scene_section_style"
    assert scene_state.surface_state.active_label == "参考文献"
    assert scene_state.surface_state.source_label == "已调整 2 项"
    assert scene_state.surface_state.detail == "不同：中文字体、行距"
    assert scene_state.surface_state.editable is True
    assert scene_state.hint == "正在编辑「参考文献」：中文字体、行距不同。"
    assert scene_state.action_enabled is True
    assert scene_state.source_status == "已调整 2 项"
    assert scene_state.scope_status == "仅当前场景"
    assert scene_state.edit_status == "可编辑"

    follow_state = scene_section_style_owner_state(
        style=style,
        projection=None,
        variant_label="参考文献",
        section_enabled=True,
        overridden=False,
    )
    assert follow_state.surface_state.editable is False
    assert "跟随模板" in follow_state.hint
    assert follow_state.scope_status == "来自模板"
    assert follow_state.edit_status == "开启独立样式后可编辑"


def test_style_object_projection_builders_cover_template_and_scene_styles():
    template = TemplateConfig()
    body_style = StyleConfig(font_cn="宋体", line_spacing_type="multiple", line_spacing_pt=1.5)
    template.styles["body"] = body_style

    empty_template_projection = build_template_body_style_projection(None, None)
    assert empty_template_projection.kind == "template_body_style"
    assert empty_template_projection.object_label == "正文排版"
    assert empty_template_projection.summary_items[0].value == "未选择模板。"
    assert empty_template_projection.owner_state.edit_status == "先选择模板"

    template_projection = build_template_body_style_projection(template, body_style)
    assert template_projection.kind == "template_body_style"
    assert template_projection.owner_state.surface_state.style is body_style
    assert template_projection.source_label == "模板默认样式"
    assert template_projection.scope_label == "模板全局"
    assert any(item.key == "text" for item in template_projection.summary_items)

    scene = SceneWorkspace(scene_id="custom", template_id="default")
    scene.format_scope.sections["references"] = True

    follow_projection = build_scene_section_style_projection(
        scene,
        template,
        "references_body",
    )
    assert follow_projection.kind == "scene_section_style"
    assert follow_projection.object_label == "参考文献"
    assert follow_projection.source_label == "跟随模板"
    assert follow_projection.scope_label == "来自模板"
    assert follow_projection.edit_state_label == "开启独立样式后可编辑"
    assert follow_projection.owner_state.surface_state.editable is False
    assert follow_projection.preview_projection is not None
    assert follow_projection.difference is not None
    follow_summary = {item.key: item for item in follow_projection.summary_items}
    assert follow_summary["override_status"].value == "无格式例外"
    assert follow_summary["current_variant_status"].value == "参考文献 · 跟随模板"
    assert follow_summary["owner_boundary"].value == "仅当前场景"
    assert follow_projection.policy is not None
    follow_policy = follow_projection.policy
    follow_toggle = next(
        item for item in follow_policy.toggles if item.key == "references_body"
    )
    assert follow_toggle.checked is False
    assert follow_toggle.visible is True
    assert follow_policy.restore_all.enabled is False
    assert follow_policy.undo_restore_all.enabled is False

    scene.section_styles["references_body"] = StyleConfig(
        font_cn="黑体",
        line_spacing_type="multiple",
        line_spacing_pt=2,
    )
    override_projection = build_scene_section_style_projection(
        scene,
        template,
        "references_body",
    )
    assert override_projection.object_label == "参考文献"
    assert override_projection.scope_label == "仅当前场景"
    assert override_projection.edit_state_label == "可编辑"
    assert override_projection.owner_state.surface_state.editable is True
    assert override_projection.difference.changed_count > 0
    override_summary = {item.key: item for item in override_projection.summary_items}
    assert override_summary["override_status"].value == "1 个格式例外"
    assert override_summary["override_status"].detail == "参考文献"
    assert override_summary["current_variant_status"].value == "参考文献 · 已调整 2 项"
    override_toggle = next(
        item for item in override_projection.policy.toggles if item.key == "references_body"
    )
    assert override_toggle.checked is True
    assert override_projection.policy.restore_all.enabled is True
    assert override_projection.policy.restore_all.labels == ("参考文献",)

    policy_projection = build_scene_section_style_policy_projection(
        scene,
        template,
        "references_body",
        undo_restore_all_labels=("参考文献",),
    )
    assert policy_projection.kind == "scene_section_style"
    assert policy_projection.difference.difference_status == "已调整 2 项"
    assert policy_projection.undo_restore_all.enabled is True

    prereview_projection = build_execution_prereview_style_projection(
        scene,
        template,
        template_label="默认格式",
    )
    assert prereview_projection.kind == "execution_prereview_style"
    assert prereview_projection.object_label == "执行前复核"
    assert prereview_projection.source_label == "有格式例外"
    assert prereview_projection.scope_label.startswith("1 个格式例外")
    assert prereview_projection.edit_state_label == "只读"
    assert prereview_projection.source.template_label == "默认格式"
    assert prereview_projection.source.view_mode == "execution_review"
    assert prereview_projection.preview_projection is None
    assert prereview_projection.preview.is_empty() is True
    assert prereview_projection.difference is not None
    assert prereview_projection.difference.changed_section_count == 1
    assert prereview_projection.policy is None
    scene.section_styles["acknowledgment_body"] = StyleConfig(font_cn="楷体")
    expanded_prereview_projection = build_execution_prereview_style_projection(
        scene,
        template,
        template_label="默认格式",
    )
    assert expanded_prereview_projection.preview_projection is None
    assert expanded_prereview_projection.policy is None
    assert expanded_prereview_projection.difference.changed_section_count == 2

    execution_projection = build_execution_style_projection(
        style_source_summary="样式来源：本次按模板“默认格式”处理。",
        difference=StyleDifferenceSummaryProjection(
            template_status="模板基线",
            current_status="参考文献 独立样式",
            difference_status="已调整 1 项",
            detail="不同：行距",
            variant="warning",
            section_count=1,
            changed_section_count=1,
        ),
    )
    assert execution_projection.kind == "execution_style"
    assert execution_projection.object_label == "样式回执"
    assert execution_projection.source_label == "本次使用"
    assert execution_projection.scope_label == "执行结果"
    assert execution_projection.edit_state_label == "只读"
    assert execution_projection.receipt.receipt_summary(title_fallback="样式来源") == (
        "样式来源：本次按模板“默认格式”处理。"
    )
    assert execution_projection.difference.difference_status == "已调整 1 项"


def test_style_policy_toggle_list_manages_rows_signals_and_override_alias():
    _app()
    toggle_list = StylePolicyToggleList(
        title="样式策略",
        object_name_prefix="test_style_policy_list",
    )
    changed: list[tuple[str, bool]] = []
    toggle_list.toggled.connect(lambda key, checked: changed.append((key, checked)))

    try:
        toggle_list.set_options(
            (
                StylePolicyToggleOption("references_body", "参考文献"),
                StylePolicyToggleOption("appendix_body", "附录", "附录单独设置"),
            )
        )

        assert toggle_list.title_label.text() == "样式策略"
        assert set(toggle_list.toggles) == {"references_body", "appendix_body"}
        assert set(toggle_list.rows) == {"references_body", "appendix_body"}
        assert toggle_list.rows["references_body"].property(
            "style_policy_row_key"
        ) == "references_body"
        assert toggle_list.current_policy_key() == ""
        assert [label.text() for label in toggle_list.labels] == ["参考文献", "附录"]
        assert toggle_list.toggles["appendix_body"].toolTip() == "附录单独设置"
        assert issubclass(StyleOverrideToggleList, StylePolicyToggleList)
        assert issubclass(StyleOverrideToggleOption, StylePolicyToggleOption)

        assert toggle_list.set_current_policy_key("references_body") is True
        assert toggle_list.current_policy_key() == "references_body"
        assert toggle_list.property("style_policy_current_key") == "references_body"
        assert toggle_list.rows["references_body"].property(
            "style_policy_row_current"
        ) is True
        assert toggle_list.rows["appendix_body"].property(
            "style_policy_row_current"
        ) is False
        assert toggle_list.set_current_policy_key("missing") is False
        assert toggle_list.set_current_policy_key("") is True
        assert toggle_list.current_policy_key() == ""
        assert toggle_list.rows["references_body"].property(
            "style_policy_row_current"
        ) is False

        toggle_list.set_checked("references_body", True)
        assert toggle_list.toggles["references_body"].isChecked() is True
        assert changed == []
        activated: list[str] = []
        toggle_list.activated.connect(activated.append)
        assert toggle_list.activate_policy("references_body") is True
        assert toggle_list.activate_policy("missing") is False
        assert activated == ["references_body"]

        toggle_list.set_checked("references_body", False)
        toggle_list.toggles["references_body"].click()
        assert toggle_list.toggles["references_body"].isChecked() is True
        assert changed == [("references_body", True)]

        toggle_list.set_row_visible("appendix_body", False)
        assert toggle_list.rows["appendix_body"].isHidden() is True
        toggle_list.set_row_visible("appendix_body", True)
        assert toggle_list.rows["appendix_body"].isHidden() is False
    finally:
        toggle_list.close()


def test_style_policy_toggle_sync_does_not_interrupt_matching_click_animation():
    _app()
    toggle_list = StylePolicyToggleList(
        title="样式策略",
        object_name_prefix="test_style_policy_animation_list",
    )

    try:
        toggle_list.set_options((StylePolicyToggleOption("references_body", "参考文献"),))
        toggle = toggle_list.toggles["references_body"]

        toggle.click()
        assert toggle.isChecked() is True
        assert toggle._anim.state() == QAbstractAnimation.Running
        running_position = toggle.thumb_position

        toggle_list.set_checked("references_body", True)

        assert toggle._anim.state() == QAbstractAnimation.Running
        assert toggle.thumb_position == running_position
    finally:
        toggle_list.close()


def test_style_rule_control_deck_groups_toggles_comparison_and_batch_actions():
    _app()
    policy_source = inspect.getsource(StylePolicyControlDeck)
    rule_source = inspect.getsource(StyleRuleControlDeck)
    assert "apply_detail_summary_action_button" in policy_source
    assert "apply_template_summary_action_button" not in policy_source
    assert issubclass(StyleRuleControlDeck, StylePolicyControlDeck)
    assert "StylePolicyControlDeck" in rule_source

    deck = StyleRuleControlDeck(
        object_name_prefix="test_style_rule_deck",
        toggle_options=(
            StylePolicyToggleOption("references_body", "参考文献"),
            StylePolicyToggleOption("appendix_body", "附录", "附录单独设置"),
        ),
    )
    toggled: list[tuple[str, bool]] = []
    override_toggled: list[tuple[str, bool]] = []
    restored_all: list[bool] = []
    undone: list[bool] = []
    deck.policy_toggled.connect(lambda key, checked: toggled.append((key, checked)))
    deck.override_toggled.connect(
        lambda key, checked: override_toggled.append((key, checked))
    )
    deck.restore_all_requested.connect(lambda: restored_all.append(True))
    deck.undo_restore_all_requested.connect(lambda: undone.append(True))

    try:
        assert deck.objectName() == "test_style_rule_deck_rule_control_deck"
        assert deck.toggle_list.objectName() == "test_style_rule_deck_policy_list"
        assert deck.difference_slot.objectName() == (
            "test_style_rule_deck_difference_slot"
        )
        assert deck.difference_slot.property("style_difference_content_plan") == (
            "difference"
        )
        assert deck.difference_slot.comparison_strip is deck.comparison_strip
        assert deck.comparison_strip.objectName() == "test_style_rule_deck_comparison"
        assert deck.restore_all_button.objectName() == (
            "test_style_rule_deck_restore_all_template"
        )
        assert deck.undo_restore_all_button.objectName() == (
            "test_style_rule_deck_undo_restore_all_template"
        )

        deck.toggles["references_body"].click()
        assert toggled == [("references_body", True)]
        assert override_toggled == [("references_body", True)]

        deck.apply_comparison_projection(None)
        assert deck.difference_slot.property("style_difference_has_projection") is False
        assert deck.comparison_strip.property("style_compare_current_status") == (
            "选择分区"
        )

        deck.set_policy_row_visible("appendix_body", False)
        assert deck.rows["appendix_body"].isHidden() is True
        deck.set_override_row_visible("appendix_body", True)
        assert deck.rows["appendix_body"].isHidden() is False

        deck.set_restore_all_enabled(True, ("参考文献",))
        assert deck.restore_all_button.isEnabled() is True
        assert deck.restore_all_button.toolTip() == "将关闭独立样式：参考文献"
        deck.restore_all_button.click()
        assert restored_all == [True]

        deck.set_undo_restore_all_enabled(True, ("参考文献",))
        assert deck.undo_restore_all_button.isEnabled() is True
        assert deck.undo_restore_all_button.toolTip() == "恢复独立样式：参考文献"
        deck.undo_restore_all_button.click()
        assert undone == [True]
    finally:
        deck.close()


def test_style_policy_control_deck_accepts_generic_policy_copy():
    _app()
    deck = StylePolicyControlDeck(
        object_name_prefix="test_style_policy_deck",
        toggle_title="样式策略",
        restore_all_label="全部恢复策略",
        restore_all_disabled_tooltip="暂无策略可恢复",
        restore_all_enabled_tooltip="恢复全部策略",
        restore_all_enabled_labels_prefix="将恢复策略：",
        undo_restore_all_label="撤销策略恢复",
        undo_restore_all_disabled_tooltip="暂无策略撤销",
        undo_restore_all_enabled_tooltip="恢复上次策略",
        undo_restore_all_enabled_labels_prefix="还原策略：",
        toggle_options=(StylePolicyToggleOption("body", "正文"),),
    )
    toggled: list[tuple[str, bool]] = []
    deck.policy_toggled.connect(lambda key, checked: toggled.append((key, checked)))

    try:
        assert deck.objectName() == "test_style_policy_deck_policy_control_deck"
        assert deck.property("style_policy_control_deck") is True
        assert deck.toggle_list.objectName() == "test_style_policy_deck_policy_list"
        assert deck.restore_all_button.text() == "全部恢复策略"
        assert deck.undo_restore_all_button.text() == "撤销策略恢复"
        assert deck.has_policy_key("body") is True
        assert deck.has_policy_key("missing") is False
        assert deck.policy_toggle_for_key("body") is deck.toggles["body"]

        deck.toggles["body"].click()
        assert toggled == [("body", True)]

        assert deck.set_policy_checked("body", False) is True
        assert deck.toggles["body"].isChecked() is False
        assert deck.set_policy_checked("missing", True) is False

        deck.set_restore_all_enabled(True, ("正文",))
        assert deck.restore_all_button.toolTip() == "将恢复策略：正文"
        deck.set_restore_all_enabled(False)
        assert deck.restore_all_button.toolTip() == "暂无策略可恢复"

        deck.set_undo_restore_all_enabled(True, ("正文",))
        assert deck.undo_restore_all_button.toolTip() == "还原策略：正文"
        deck.set_undo_restore_all_enabled(False)
        assert deck.undo_restore_all_button.toolTip() == "暂无策略撤销"
    finally:
        deck.close()


def test_style_policy_control_deck_supports_readonly_without_internal_difference():
    _app()
    deck = StylePolicyControlDeck(
        object_name_prefix="test_readonly_style_policy",
        show_difference=False,
        read_only=True,
    )
    toggled: list[tuple[str, bool]] = []
    restored_all: list[bool] = []
    selected: list[str] = []
    deck.policy_toggled.connect(lambda key, checked: toggled.append((key, checked)))
    deck.restore_all_requested.connect(lambda: restored_all.append(True))
    deck.policy_selected.connect(selected.append)
    projection = StylePolicyProjection(
        kind="execution_prereview_policy",
        title="独立样式",
        toggles=(
            StylePolicyToggleProjection(
                key="references_body",
                label="参考文献",
                checked=True,
            ),
        ),
        restore_all=StylePolicyActionProjection(
            label="全部跟随模板",
            enabled=True,
            labels=("参考文献",),
        ),
    )

    try:
        assert deck.property("style_policy_show_difference") is False
        assert deck.property("style_policy_control_read_only") is True

        deck.apply_projection(projection)

        assert deck.difference_slot.isHidden() is True
        assert deck.toggles["references_body"].isChecked() is True
        assert deck.toggles["references_body"].isEnabled() is False
        assert deck.restore_all_button.isEnabled() is False
        assert deck.set_current_policy_key("references_body") is True
        assert deck.current_policy_key() == "references_body"
        assert deck.property("style_policy_current_key") == "references_body"
        assert deck.rows["references_body"].property(
            "style_policy_row_current"
        ) is True
        assert deck.activate_policy("references_body") is True
        assert selected == ["references_body"]

        deck.toggles["references_body"].click()
        deck.restore_all_button.click()
        assert toggled == []
        assert restored_all == []

        deck.set_read_only(False)
        assert deck.property("style_policy_control_read_only") is False
        assert deck.toggles["references_body"].isEnabled() is True
        assert deck.restore_all_button.isEnabled() is False
    finally:
        deck.close()


def test_style_policy_control_deck_applies_policy_projection():
    _app()
    deck = StylePolicyControlDeck(
        object_name_prefix="test_style_policy_projection",
        toggle_title="样式策略",
        restore_all_label="全部恢复策略",
        restore_all_disabled_tooltip="暂无策略可恢复",
        restore_all_enabled_labels_prefix="将恢复策略：",
        undo_restore_all_label="撤销策略恢复",
        undo_restore_all_disabled_tooltip="暂无策略撤销",
        undo_restore_all_enabled_labels_prefix="还原策略：",
    )
    projection = StylePolicyProjection(
        kind="scene_section_policy",
        title="分区策略",
        toggles=(
            StylePolicyToggleProjection(
                key="references_body",
                label="参考文献",
                checked=True,
                tooltip="参考文献单独设置",
            ),
            StylePolicyToggleProjection(
                key="appendix_body",
                label="附录",
                checked=False,
                visible=False,
            ),
        ),
        restore_all=StylePolicyActionProjection(
            label="全部跟随模板",
            enabled=True,
            labels=("参考文献",),
        ),
        undo_restore_all=StylePolicyActionProjection(
            label="撤销恢复",
            enabled=True,
            labels=("参考文献",),
            tooltip="撤销刚才的恢复",
        ),
    )

    try:
        deck.apply_projection(projection)

        assert deck.property("style_policy_kind") == "scene_section_policy"
        assert deck.property("style_policy_title") == "分区策略"
        assert deck.property("style_policy_toggle_count") == 2
        assert deck.property("style_policy_checked_count") == 1
        assert deck.toggle_list.title_label.text() == "分区策略"
        assert deck.toggles["references_body"].isChecked() is True
        assert deck.rows["appendix_body"].isHidden() is True
        assert deck.restore_all_button.text() == "全部跟随模板"
        assert deck.restore_all_button.isEnabled() is True
        assert deck.restore_all_button.toolTip() == "将恢复策略：参考文献"
        assert deck.undo_restore_all_button.text() == "撤销恢复"
        assert deck.undo_restore_all_button.isEnabled() is True
        assert deck.undo_restore_all_button.toolTip() == "撤销刚才的恢复"
    finally:
        deck.close()


def test_style_result_receipt_row_projects_readonly_style_source_summary():
    _app()
    row = StyleResultReceiptRow(object_name_prefix="test_style_receipt")
    try:
        assert row.isHidden() is True

        row.apply_envelope(
            StylePresentationEnvelope(
                kind="execution_receipt",
                title="样式来源",
                summary="本次按模板“默认格式”处理",
                detail="参考文献（行距）使用场景独立样式。",
            )
        )

        assert row.objectName() == "test_style_receipt_row"
        assert row.isHidden() is False
        assert row.label.text() == "样式来源"
        assert row.detail.text() == (
            "本次按模板“默认格式”处理；参考文献（行距）使用场景独立样式。"
        )
        assert row.summary_text() == (
            "样式来源：本次按模板“默认格式”处理；参考文献（行距）使用场景独立样式。"
        )
        assert row.property("style_presentation_kind") == "execution_receipt"

        row.set_summary(
            "样式来源：本次按模板“默认格式”处理；参考文献（行距）使用场景独立样式。"
        )
        assert row.summary_text().startswith("样式来源：")

        row.set_summary("")
        assert row.isHidden() is True
    finally:
        row.close()


def test_style_receipt_slot_frame_wraps_receipt_row_without_card_chrome():
    _app()
    slot = StyleReceiptSlotFrame(object_name_prefix="test_style_receipt_slot")
    try:
        assert slot.objectName() == "test_style_receipt_slot_slot"
        assert slot.isHidden() is True
        assert slot.receipt_row.objectName() == "test_style_receipt_slot_row"
        assert slot.property("style_management_mode") == "execution_receipt_review"
        assert slot.property("style_management_content_plan") == "receipt"
        assert slot.property("style_management_has_receipt") is True
        assert slot.property("style_management_has_difference") is False
        assert slot.property("style_management_has_editor") is False
        assert slot.property("style_receipt_slot_surface") == "embedded"

        slot.apply_envelope(
            StylePresentationEnvelope(
                kind="execution_receipt",
                title="样式来源",
                summary="本次按模板“默认格式”处理",
                detail="参考文献（行距）使用场景独立样式。",
            )
        )

        assert slot.isHidden() is False
        assert slot.has_receipt() is True
        assert slot.receipt_row.summary_text() == (
            "样式来源：本次按模板“默认格式”处理；参考文献（行距）使用场景独立样式。"
        )

        slot.set_summary("")
        assert slot.isHidden() is True
        assert slot.has_receipt() is False
    finally:
        slot.close()


def test_scope_zone_checklist_manages_checks_and_signals():
    _app()
    checklist = ScopeZoneChecklist(object_name_prefix="test_scope_zone_checklist")
    changed: list[tuple[str, bool]] = []
    checklist.checked_changed.connect(lambda key, checked: changed.append((key, checked)))

    try:
        checklist.set_options(
            (
                ScopeZoneOption("body", "正文"),
                ScopeZoneOption("references", "参考文献"),
                ScopeZoneOption("appendix", "附录"),
            )
        )

        assert set(checklist.checks) == {"body", "references", "appendix"}
        assert checklist.checks["references"].text() == "参考文献"
        assert checklist.checks["references"].styleSheet()

        checklist.set_checked("references", True)
        assert checklist.checks["references"].isChecked() is True
        assert changed == [("references", True)]

        checklist.checks["references"].click()
        assert checklist.checks["references"].isChecked() is False
        assert changed[-1] == ("references", False)
    finally:
        checklist.close()


def test_placeholder_edit_uses_readable_default_placeholder():
    source = (ROOT / "src/shared/ui/placeholder_edit.py").read_text(encoding="utf-8")
    init_source = inspect.getsource(PlaceholderEdit.__init__)

    assert 'DEFAULT_PLACEHOLDER_TEMPLATE = "{{占位符}}"' in source
    assert "placeholder: str = DEFAULT_PLACEHOLDER_TEMPLATE" in init_source
    assert "??" not in source
