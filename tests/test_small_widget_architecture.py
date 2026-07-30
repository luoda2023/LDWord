import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.template import StyleConfig, TemplateConfig
from src.qt_api import QBoxLayout, QWidget
from src.shared.ui.card import Card
from src.shared.ui.design_system_card import DesignSystemCard
from src.shared.ui.collapsible_section import CollapsibleSection
from src.shared.ui.icon_button import IconButton
from src.shared.ui.issue_detail_section import IssueDetailSection
from src.shared.ui.module_step_list import ModuleStepItem, ModuleStepList
from src.shared.ui.override_badge import OverrideBadge
from src.shared.ui.placeholder_edit import PlaceholderEdit
from src.shared.ui.style_editing_section import StyleEditingSection
from src.shared.ui.style_management_block import (
    StyleManagementBlock,
    style_management_content_plan,
    style_management_contract,
    style_preview_slot_protocol,
)
from src.shared.ui.style_object_projection import StyleObjectProjection
from src.shared.ui.style_owner_state import template_body_style_owner_state
from src.shared.ui.style_owner_status_strip import StyleOwnerStatusStrip
from src.shared.ui.style_owner_toolbar import StyleControlOwnerToolbar, StyleOwnerOption
from src.shared.ui.style_presentation_envelope import StylePresentationEnvelope
from src.shared.ui.style_preview_surface import (
    StylePreviewSurface,
    style_preview_renderer_protocol,
)
from src.shared.ui.style_receipt_slot_frame import StyleReceiptSlotFrame
from src.shared.ui.style_result_receipt_row import StyleResultReceiptRow
from src.shared.ui.style_preview import StylePreview, StylePreviewProjection
from src.shared.ui.summary_grid import SummaryGridItem
from src.shared.ui.theme import LIGHT
from src.ui.panels.style_object_projection_builders import (
    build_execution_style_projection,
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
            source_label="模板样式",
            summary="当前有效样式",
            detail="行距、段后",
            action_label="调例外",
        )

        preview.apply_envelope(envelope)

        assert preview.text() == "参考文献：当前有效样式"
        assert preview.toolTip() == "模板样式：行距、段后"
        assert preview.property("style_preview_source_label") == "模板样式"
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
    assert envelope.action_label == "调整样式"


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
        source_label="模板样式",
        summary="当前有效样式",
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
        {"template_label": "默认格式"}
    )

    assert envelope.kind == "execution_receipt"
    assert envelope.title == "样式来源"
    assert envelope.source_label == "本次使用"
    assert envelope.summary == "本次使用模板“默认格式”。"
    assert envelope.detail == ""
    assert envelope.receipt_summary(title_fallback="样式来源") == (
        "样式来源：本次使用模板“默认格式”。"
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

        toolbar.set_hint("选择对象后可编辑")
        assert toolbar.hint_label.text() == "选择对象后可编辑"
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
        assert shell.preview.property("style_presentation_action_label") == "调整样式"
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


def test_style_management_block_named_slots_update_plan():
    _app()
    source_slot = QWidget()
    source_slot.setObjectName("test_style_source_slot")
    scope_slot = QWidget()
    scope_slot.setObjectName("test_style_scope_slot")
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
        preview_slot=preview_slot,
        receipt_slot=receipt_slot,
    )

    try:
        assert block.source_slot is source_slot
        assert block.scope_slot is scope_slot
        assert block.preview_slot is preview_slot
        assert block.effective_preview_slot is preview_slot
        assert block.receipt_slot is receipt_slot
        assert source_slot.parentWidget() is block.card
        assert scope_slot.parentWidget() is block.card
        assert preview_slot.parentWidget() is block.card
        assert receipt_slot.parentWidget() is block.card
        assert block.content_plan.sections() == (
            "source",
            "scope",
            "editor",
            "preview",
            "receipt",
        )
        assert block.property("style_management_content_plan") == (
            "source|scope|editor|preview|receipt"
        )
        assert block.property("style_management_has_source_slot") is True
        assert block.property("style_management_has_scope_slot") is True
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
            mode="readonly_review",
            preview_slot=preview_slot,
        )


def test_style_result_receipt_row_projects_readonly_style_source_summary():
    _app()
    row = StyleResultReceiptRow(object_name_prefix="test_style_receipt")
    try:
        assert row.isHidden() is True

        row.apply_envelope(
            StylePresentationEnvelope(
                kind="execution_receipt",
                title="样式来源",
                summary="本次使用模板“默认格式”。",
            )
        )

        assert row.objectName() == "test_style_receipt_row"
        assert row.isHidden() is False
        assert row.label.text() == "样式来源"
        assert row.detail.text() == (
            "本次使用模板“默认格式”。"
        )
        assert row.summary_text() == (
            "样式来源：本次使用模板“默认格式”。"
        )
        assert row.property("style_presentation_kind") == "execution_receipt"

        row.set_summary(
            "样式来源：本次使用模板“默认格式”。"
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
        assert slot.property("style_management_has_editor") is False
        assert slot.property("style_receipt_slot_surface") == "embedded"

        slot.apply_envelope(
            StylePresentationEnvelope(
                kind="execution_receipt",
                title="样式来源",
                summary="本次使用模板“默认格式”。",
            )
        )

        assert slot.isHidden() is False
        assert slot.has_receipt() is True
        assert slot.receipt_row.summary_text() == (
            "样式来源：本次使用模板“默认格式”。"
        )

        slot.set_summary("")
        assert slot.isHidden() is True
        assert slot.has_receipt() is False
    finally:
        slot.close()


def test_placeholder_edit_uses_readable_default_placeholder():
    source = (ROOT / "src/shared/ui/placeholder_edit.py").read_text(encoding="utf-8")
    init_source = inspect.getsource(PlaceholderEdit.__init__)

    assert 'DEFAULT_PLACEHOLDER_TEMPLATE = "{{占位符}}"' in source
    assert "placeholder: str = DEFAULT_PLACEHOLDER_TEMPLATE" in init_source
    assert "??" not in source
