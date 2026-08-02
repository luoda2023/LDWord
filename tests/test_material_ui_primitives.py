from __future__ import annotations

from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest

from src.qt_api import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPoint,
    QTextEdit,
    Qt,
    QWidget,
)
from src.shared.ui.compact_row_actions import CompactRowActions
from src.shared.ui.asset_column_guide import (
    AssetColumnGuide,
    resolve_asset_column_metrics,
)
from src.shared.ui.material_token_edit import MaterialTokenEdit
from src.shared.ui.material_name_edit import MaterialNameEdit
from src.shared.ui.material_text_views import (
    ElidedFilenameEdit,
    ElidedPathEdit,
    ElidedReadOnlyValue,
    ElidedValueEdit,
)
from src.shared.ui.path_action_semantics import PathAction, path_action_presentation
from src.shared.ui.official_field_value_edit import OfficialFieldValueEdit
from src.shared.ui.rounded_surface import RoundedSurfaceFrame
from src.shared.ui.sizing import resolved_control_height
from src.shared.ui.theme import get_theme
from src.shared.ui.timeline_node_column_guide import (
    TimelineNodeColumnGuide,
    resolve_timeline_node_column_metrics,
)
from src.shared.ui.token_column_guide import (
    TokenColumnGuide,
    resolve_token_column_metrics,
)
from src.shared.ui.token_section_header import TokenSectionHeader
from src.shared.ui.text_projection import (
    ElidedTextLabel,
    elide_filename_text,
    elide_token_parts,
)


def test_material_token_edit_copies_and_enters_inline_rename(qapp):
    edit = MaterialTokenEdit("{{@text:标题1}}")
    assert edit._expanded_popup is None
    edit.show()

    QTest.mouseClick(edit, Qt.LeftButton)
    assert QApplication.clipboard().text() == "{{@text:标题1}}"
    assert edit.isReadOnly()

    QTest.mouseDClick(edit, Qt.LeftButton)
    assert not edit.isReadOnly()


def test_projected_text_popup_is_created_only_for_actual_overflow_edit(qapp):
    edit = MaterialTokenEdit("{{@attach:" + ("超长名称" * 8) + "}}")
    name = MaterialNameEdit("普通行名称")
    edit.resize(180, 32)
    edit.show()
    name.show()
    qapp.processEvents()

    assert edit._expanded_popup is None
    assert name._expanded_popup is None

    QTest.mouseDClick(edit.displaySurface(), Qt.LeftButton)
    qapp.processEvents()

    assert edit._expanded_popup is not None
    assert edit._expanded_popup.isVisible()
    assert name._expanded_popup is None


def test_material_token_edit_freezes_affixes_and_elides_only_display(qapp):
    canonical = "{{@text:非常长的法人签名字段名称1}}"
    edit = MaterialTokenEdit(canonical)
    edit.resize(155, 32)
    edit.show()
    qapp.processEvents()

    display = edit.displayText()
    assert display.startswith("{{")
    assert display.endswith("}}")
    assert display != canonical
    assert edit.displaySurface().fontMetrics().horizontalAdvance(display) <= (
        edit.displaySurface().contentsRect().width() - 2
    )
    assert edit.text() == canonical

    QTest.mouseClick(edit, Qt.LeftButton)
    assert QApplication.clipboard().text() == canonical

    QTest.mouseDClick(edit, Qt.LeftButton)
    assert edit.lockedPrefix() == "{{@text:"
    assert edit.lockedSuffix() == "}}"
    assert edit.innerEditor().text() == "非常长的法人签名字段名称1"
    assert "{" not in edit.innerEditor().text()
    edit.innerEditor().setText("法人签名2")
    QTest.keyClick(edit.innerEditor(), Qt.Key_Return)

    assert edit.text() == "{{@text:法人签名2}}"


def test_material_token_hover_card_only_exposes_full_value_when_elided(qapp):
    canonical = "{{@attach:附件文件夹1}}"
    edit = MaterialTokenEdit(canonical)
    edit.resize(155, 32)
    edit.show()
    qapp.processEvents()

    assert edit.displayText() != canonical
    assert edit.toolTip() == canonical
    assert edit.displaySurface().toolTip() == canonical

    edit.resize(600, 32)
    qapp.processEvents()

    assert edit.displayText() == canonical
    assert edit.toolTip() == ""
    assert edit.displaySurface().toolTip() == ""


def test_material_token_overflow_uses_wide_edit_card_with_live_full_preview(qapp):
    canonical = "{{@attach:附件文件夹1}}"
    edit = MaterialTokenEdit(canonical)
    edit.resize(220, 32)
    edit.show()
    qapp.processEvents()

    QTest.mouseDClick(edit.displaySurface(), Qt.LeftButton)
    qapp.processEvents()

    assert edit.isExpandedEditing()
    assert edit._expanded_popup.isVisible()
    assert edit._expanded_popup.width() >= 420
    assert edit.innerEditor().width() > edit.width()
    assert edit.innerEditor().text() == "附件文件夹1"
    assert canonical in edit._expanded_preview.text()
    assert edit._prefix_label.isHidden()
    assert edit._suffix_label.isHidden()

    edit.setText("{{@attach:外部同步附件名称}}")
    assert "{{@attach:外部同步附件名称}}" in edit._expanded_preview.text()
    assert edit._prefix_label.isHidden()
    assert edit._suffix_label.isHidden()

    edit.innerEditor().setText("超长附件文件夹名称2")
    assert "{{@attach:超长附件文件夹名称2}}" in edit._expanded_preview.text()
    QTest.keyClick(edit.innerEditor(), Qt.Key_Return)

    assert not edit.isExpandedEditing()
    assert edit._expanded_popup.isHidden()
    assert edit.text() == "{{@attach:超长附件文件夹名称2}}"


def test_expanded_token_card_uses_a_real_translucent_rounded_surface(qapp):
    edit = MaterialTokenEdit("{{@attach:" + ("2" * 24) + "}}")
    edit.resize(220, 32)
    edit.show()
    qapp.processEvents()

    QTest.mouseDClick(edit.displaySurface(), Qt.LeftButton)
    qapp.processEvents()

    popup = edit._expanded_popup
    image = popup.grab().toImage()
    assert popup.testAttribute(Qt.WA_TranslucentBackground)
    assert popup.windowFlags() & Qt.NoDropShadowWindowHint
    assert isinstance(edit._expanded_surface, RoundedSurfaceFrame)
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(popup.width() // 2, popup.height() // 2).alpha() > 0


def test_expanded_token_card_maps_internal_and_preview_clicks_to_core(qapp):
    core = "2" * 24
    edit = MaterialTokenEdit(f"{{{{@attach:{core}}}}}")
    edit.resize(220, 32)
    edit.show()
    qapp.processEvents()

    QTest.mouseDClick(edit.displaySurface(), Qt.LeftButton)
    qapp.processEvents()
    editor = edit.innerEditor()

    editor_click = QPoint(editor.width() // 3, editor.height() // 2)
    expected = editor.cursorPositionAt(editor_click)
    editor.selectAll()
    QTest.mouseClick(editor, Qt.LeftButton, pos=editor_click)
    assert editor.cursorPosition() == expected
    assert not editor.selectedText()
    assert edit.isExpandedEditing()

    preview = edit._expanded_preview
    preview_position = edit._expanded_preview_core_start + 5
    preview_cursor = QTextCursor(preview.document())
    preview_cursor.setPosition(preview_position)
    preview_click = preview.cursorRect(preview_cursor).center()
    editor.selectAll()
    QTest.mouseClick(preview.viewport(), Qt.LeftButton, pos=preview_click)
    assert editor.cursorPosition() == 5
    assert not editor.selectedText()
    assert edit.isExpandedEditing()

    suffix_cursor = QTextCursor(preview.document())
    suffix_cursor.setPosition(len(preview.text()) - 1)
    editor.selectAll()
    QTest.mouseClick(
        preview.viewport(),
        Qt.LeftButton,
        pos=preview.cursorRect(suffix_cursor).center(),
    )
    assert editor.cursorPosition() == len(core)
    assert not editor.selectedText()


def test_native_expanded_popup_dismissal_commits_exactly_once(qapp):
    edit = MaterialTokenEdit("{{@attach:" + ("2" * 24) + "}}")
    edit.resize(220, 32)
    edit.show()
    completions: list[str] = []
    edit.editingFinished.connect(lambda: completions.append(edit.text()))
    qapp.processEvents()

    QTest.mouseDClick(edit.displaySurface(), Qt.LeftButton)
    qapp.processEvents()
    assert "点击卡片外完成修改" in edit._expanded_hint.text()
    assert "Enter" not in edit._expanded_hint.text()
    assert "Esc" not in edit._expanded_hint.text()

    edit.innerEditor().setText("已修改的附件名称")
    edit._expanded_popup.hide()
    qapp.processEvents()

    assert not edit.isInlineEditing()
    assert edit.text() == "{{@attach:已修改的附件名称}}"
    assert completions == ["{{@attach:已修改的附件名称}}"]


def test_expanded_token_card_keeps_inside_clicks_and_commits_outside(qapp):
    host = QWidget()
    layout = QHBoxLayout(host)
    edit = MaterialTokenEdit("{{@attach:附件文件夹1}}")
    edit.setFixedWidth(220)
    outside = QLabel("其他区域", host)
    layout.addWidget(edit)
    layout.addWidget(outside)
    completions: list[str] = []
    edit.editingFinished.connect(lambda: completions.append(edit.text()))
    host.show()
    qapp.processEvents()

    QTest.mouseDClick(edit.displaySurface(), Qt.LeftButton)
    qapp.processEvents()
    assert edit.isExpandedEditing()

    QTest.mouseClick(edit._expanded_preview, Qt.LeftButton)
    assert edit.isExpandedEditing()
    assert completions == []

    edit.innerEditor().setText("合同附件文件夹2")
    QTest.mouseClick(outside, Qt.LeftButton)
    qapp.processEvents()

    assert not edit.isInlineEditing()
    assert edit.text() == "{{@attach:合同附件文件夹2}}"
    assert completions == ["{{@attach:合同附件文件夹2}}"]


def test_expanded_token_card_escape_restores_complete_snapshot(qapp):
    canonical = "{{@attach:附件文件夹1}}"
    edit = MaterialTokenEdit(canonical)
    edit.resize(220, 32)
    edit.show()
    qapp.processEvents()

    QTest.mouseDClick(edit.displaySurface(), Qt.LeftButton)
    edit.innerEditor().setText("临时附件名称")
    QTest.keyClick(edit.innerEditor(), Qt.Key_Escape)

    assert not edit.isExpandedEditing()
    assert edit.text() == canonical


def test_content_token_freezes_namespace_as_well_as_braces(qapp):
    edit = MaterialTokenEdit("{{@file:项目背景与总体技术路线1}}")
    edit.show()
    QTest.mouseDClick(edit, Qt.LeftButton)

    assert edit.lockedPrefix() == "{{@file:"
    assert edit.innerEditor().text() == "项目背景与总体技术路线1"
    assert edit.lockedSuffix() == "}}"

    edit.innerEditor().setText("安全评估1")
    QTest.keyClick(edit.innerEditor(), Qt.Key_Return)
    assert edit.text() == "{{@file:安全评估1}}"


def test_material_token_projection_reserves_paint_space_for_closing_braces(qapp):
    canonical = "{{@file:" + ("0" * 40) + "22222}}"
    edit = MaterialTokenEdit(canonical)
    edit.resize(455, 32)
    edit.show()
    qapp.processEvents()

    surface = edit.displaySurface()
    rendered = edit.displayText()
    assert rendered.endswith("}}")
    assert surface.fontMetrics().horizontalAdvance(rendered) <= (
        surface.contentsRect().width() - 2
    )
    assert edit.text() == canonical


def test_material_token_composite_editor_keeps_internal_clicks_in_session(qapp):
    core = ("0" * 28) + "22222"
    host = QWidget()
    layout = QHBoxLayout(host)
    edit = MaterialTokenEdit("{{@file:" + core + "}}")
    outside = QLabel("outside", host)
    layout.addWidget(edit)
    layout.addWidget(outside)
    host.resize(720, 90)
    host.show()
    qapp.processEvents()

    completions: list[str] = []
    edit.editingFinished.connect(lambda: completions.append(edit.text()))
    QTest.mouseDClick(edit.displaySurface(), Qt.LeftButton)
    qapp.processEvents()

    editor = edit.innerEditor()
    prefix = edit.findChild(QLabel, "projected_text_locked_prefix")
    suffix = edit.findChild(QLabel, "projected_text_locked_suffix")
    assert prefix is not None and suffix is not None
    assert edit.isInlineEditing()

    QTest.mouseClick(
        editor,
        Qt.LeftButton,
        pos=QPoint(editor.width() // 2, editor.height() // 2),
    )
    assert edit.isInlineEditing()
    assert editor.hasFocus()
    assert not editor.selectedText()
    assert 0 < editor.cursorPosition() < len(core)

    editor.selectAll()
    QTest.mouseClick(prefix, Qt.LeftButton, pos=prefix.rect().center())
    assert edit.isInlineEditing()
    assert editor.hasFocus()
    assert editor.cursorPosition() == 0
    assert not editor.selectedText()

    editor.selectAll()
    QTest.mouseClick(suffix, Qt.LeftButton, pos=suffix.rect().center())
    assert edit.isInlineEditing()
    assert editor.hasFocus()
    assert editor.cursorPosition() == len(core)
    assert not editor.selectedText()

    editor.selectAll()
    QTest.mouseClick(
        edit,
        Qt.LeftButton,
        pos=QPoint(edit.width() - 2, edit.height() // 2),
    )
    assert edit.isInlineEditing()
    assert editor.hasFocus()
    assert editor.cursorPosition() == len(core)
    assert not editor.selectedText()
    assert completions == []

    QTest.mouseClick(outside, Qt.LeftButton, pos=outside.rect().center())
    qapp.processEvents()
    assert not edit.isInlineEditing()
    assert completions == ["{{@file:" + core + "}}"]


def test_plain_and_filename_projection_keep_canonical_values(qapp):
    name = ElidedTextLabel("ISO9001质量管理体系认证证书")
    name.resize(90, 32)
    name.show()
    qapp.processEvents()
    assert name.text() == "ISO9001质量管理体系认证证书"
    assert name.renderedText() != name.text()
    assert "…" in name.renderedText()

    metrics = name.fontMetrics()
    filename = "项目总体技术实施方案最终修订版.docx"
    projected = elide_filename_text(filename, metrics, 115)
    assert projected.endswith(".docx")
    assert "…" in projected

    token = elide_token_parts("{{", "非常长的字段名称1", "}}", metrics, 80)
    assert token.startswith("{{") and token.endswith("}}")
    assert "…" in token


def test_direct_value_projection_keeps_live_qlineedit_semantics_and_escape(qapp):
    edit = ElidedValueEdit("原始字段内容")
    changes: list[str] = []
    edit.textChanged.connect(changes.append)
    edit.show()

    assert not edit.isReadOnly()

    QTest.mouseClick(edit, Qt.LeftButton)
    edit.innerEditor().setText("正在填写的完整字段内容")

    assert edit.text() == "正在填写的完整字段内容"
    assert changes[-1] == "正在填写的完整字段内容"

    QTest.keyClick(edit.innerEditor(), Qt.Key_Escape)
    assert edit.text() == "原始字段内容"
    assert changes[-1] == "原始字段内容"
    assert not edit.isReadOnly()


def test_official_single_line_field_elides_only_its_idle_projection(qapp):
    canonical = "这是一个远远超过当前字段列宽度的完整字段内容"
    edit = OfficialFieldValueEdit(click_copy_double_edit=True)
    edit.setText(canonical)
    edit.resize(118, 32)
    edit.show()
    qapp.processEvents()

    assert edit.text() == canonical
    assert edit.displayText() != canonical
    assert "…" in edit.displayText()
    assert edit.displaySurface().accessibleName() == canonical

    QTest.mouseClick(edit.displaySurface(), Qt.LeftButton)
    assert QApplication.clipboard().text() == canonical


def test_name_path_filename_and_timeline_value_share_semantic_projection(qapp):
    cases = (
        (
            MaterialNameEdit("ISO9001质量管理体系认证证书（年度复审完整版）"),
            "ISO9001质量管理体系认证证书（年度复审完整版）",
            lambda display: display.endswith("…"),
        ),
        (
            ElidedPathEdit(
                r"C:\投标资料\某大型综合项目\资质证书\ISO9001质量管理体系认证证书.pdf"
            ),
            r"C:\投标资料\某大型综合项目\资质证书\ISO9001质量管理体系认证证书.pdf",
            lambda display: "…" in display and display.endswith(".pdf"),
        ),
        (
            ElidedFilenameEdit("项目总体技术实施方案最终修订定稿版.docx"),
            "项目总体技术实施方案最终修订定稿版.docx",
            lambda display: "…" in display and display.endswith(".docx"),
        ),
        (
            ElidedReadOnlyValue("2026年07月13日至2027年12月31日（顺延后结果）"),
            "2026年07月13日至2027年12月31日（顺延后结果）",
            lambda display: display.endswith("…"),
        ),
    )

    for control, canonical, display_assertion in cases:
        control.resize(132, 32)
        control.show()
        qapp.processEvents()

        assert control.text() == canonical
        assert display_assertion(control.displayText())
        QTest.mouseClick(control, Qt.LeftButton)
        assert QApplication.clipboard().text() == canonical


def test_copy_only_display_surface_emits_one_semantic_activation(qapp):
    control = ElidedReadOnlyValue("完整时间结果")
    copies: list[str] = []
    control.copied.connect(copies.append)
    control.show()

    QTest.mouseClick(control.displaySurface(), Qt.LeftButton)

    assert QApplication.clipboard().text() == "完整时间结果"
    assert copies == ["完整时间结果"]


def test_material_name_edit_shares_copy_double_click_and_escape_contract(qapp):
    edit = MaterialNameEdit("ISO9001质量管理体系认证证书")
    edit.show()

    assert get_theme().bg_input in edit.displaySurface().styleSheet()
    assert (
        f"border: 1px solid {get_theme().border}"
        in edit.displaySurface().styleSheet()
    )

    QTest.mouseClick(edit, Qt.LeftButton)
    assert QApplication.clipboard().text() == "ISO9001质量管理体系认证证书"
    assert edit.isReadOnly()

    QTest.mouseDClick(edit, Qt.LeftButton)
    assert not edit.isReadOnly()
    assert get_theme().border_focus in edit._editor_frame.styleSheet()
    edit.setText("临时名称")
    QTest.keyClick(edit, Qt.Key_Escape)

    assert edit.text() == "ISO9001质量管理体系认证证书"
    assert edit.isReadOnly()


def test_material_name_edit_has_no_hover_popup_and_outside_click_finishes(qapp):
    host = QWidget()
    layout = QHBoxLayout(host)
    edit = MaterialNameEdit("公章")
    outside = QLabel("其他区域", host)
    layout.addWidget(edit)
    layout.addWidget(outside)
    completed: list[str] = []
    edit.editingFinished.connect(lambda: completed.append(edit.text()))
    host.show()
    qapp.processEvents()

    assert edit.toolTip() == ""
    QTest.mouseDClick(edit, Qt.LeftButton)
    assert edit.isInlineEditing()
    assert not edit.isReadOnly()

    # QLabel does not accept focus, so this specifically covers the original
    # sticky-edit regression rather than relying on ordinary focus transfer.
    QTest.mouseClick(outside, Qt.LeftButton)
    qapp.processEvents()

    assert not edit.isInlineEditing()
    assert edit.isReadOnly()
    assert completed == ["公章"]


def test_double_click_cancels_pending_single_click_copy_feedback(qapp):
    edit = MaterialNameEdit("公章")
    copies: list[str] = []
    edit.copied.connect(copies.append)
    edit.show()

    # Model the real sequence: the first click releases before Qt recognizes
    # the following double-click event.
    QTest.mouseClick(edit, Qt.LeftButton)
    assert QApplication.clipboard().text() == "公章"
    assert copies == []
    QTest.mouseDClick(edit, Qt.LeftButton)
    QTest.qWait(qapp.doubleClickInterval() + 20)

    assert edit.isInlineEditing()
    assert copies == []


def test_path_action_semantics_keep_choosing_and_revealing_distinct():
    assert path_action_presentation(PathAction.CHOOSE_IMAGE).icon_name == "image"
    assert (
        path_action_presentation(PathAction.CHOOSE_DIRECTORY).icon_name
        == "folder-output"
    )
    assert (
        path_action_presentation(PathAction.REVEAL_IN_FOLDER).icon_name
        == "folder-open"
    )
    assert path_action_presentation(PathAction.OPEN_FILE).icon_name == (
        "square-arrow-out-up-right"
    )


def test_compact_row_actions_own_one_shared_size_contract(qapp):
    actions = CompactRowActions()
    first = actions.add_action("add", icon_name="plus", tooltip="新增")
    second = actions.add_action(
        "remove",
        icon_name="trash-2",
        tooltip="删除",
        variant="ghost-danger",
    )
    theme = get_theme()

    assert first.width() == theme.compact_action_size
    assert first.height() == theme.compact_action_size
    assert second.iconSize().width() == theme.compact_action_icon_size
    assert actions.width() == (
        theme.compact_action_size * 2 + theme.compact_action_gap
    )

    first.hide()
    actions.sync_visibility()

    assert actions.width() == theme.compact_action_size


def test_collapsed_multiline_official_field_hides_stray_scrollbars(qapp):
    edit = OfficialFieldValueEdit(editor_kind="multiline", read_only=True)
    editor = edit.findChild(QTextEdit)

    assert editor is not None
    assert editor.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert editor.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff


def test_official_field_value_editor_uses_shared_outside_dismissal(qapp):
    host = QWidget()
    layout = QHBoxLayout(host)
    edit = OfficialFieldValueEdit(click_copy_double_edit=True)
    outside = QLabel("其他区域", host)
    layout.addWidget(edit)
    layout.addWidget(outside)
    line_edit = edit.findChild(QLineEdit)
    host.show()
    qapp.processEvents()

    assert line_edit is not None
    QTest.mouseDClick(line_edit, Qt.LeftButton)
    assert edit.isEditing()

    QTest.mouseClick(outside, Qt.LeftButton)
    qapp.processEvents()

    assert not edit.isEditing()
    assert line_edit.isReadOnly()


def test_multiline_official_field_uses_viewport_for_copy_edit_interaction(qapp):
    host = QWidget()
    layout = QHBoxLayout(host)
    edit = OfficialFieldValueEdit(
        editor_kind="multiline",
        click_copy_double_edit=True,
    )
    outside = QLabel("其他区域", host)
    layout.addWidget(edit)
    layout.addWidget(outside)
    text_edit = edit.findChild(QTextEdit)
    host.show()
    qapp.processEvents()

    assert text_edit is not None
    QTest.mouseDClick(text_edit.viewport(), Qt.LeftButton)
    assert edit.isEditing()
    assert not text_edit.isReadOnly()

    QTest.mouseClick(outside, Qt.LeftButton)
    qapp.processEvents()

    assert not edit.isEditing()
    assert text_edit.isReadOnly()


def test_token_section_header_reuses_title_count_hint_and_actions(qapp):
    header = TokenSectionHeader(
        "固定字段",
        hint="长期复用",
        add_text="＋ 新增固定字段",
    )

    assert header.title_label.text() == "固定字段"
    assert header.hint_label.text() == "长期复用"
    assert header.add_button.text() == "＋ 新增固定字段"
    assert header.undo_button.isHidden()
    assert header.icon_label.isHidden()
    assert get_theme().text_primary in header.title_label.styleSheet()
    assert header.height() == resolved_control_height(get_theme(), "md")
    assert header.add_button.height() == resolved_control_height(get_theme(), "md")


def test_token_column_guide_uses_quiet_shared_geometry_and_collapses_narrow(qapp):
    guide = TokenColumnGuide()
    guide.resize(960, 32)
    guide.show()
    qapp.processEvents()

    wide = guide.metrics()
    assert wide.guide_visible is True
    assert guide.index_label.text() == "序号"
    assert guide.token_label.text() == "占位符"
    assert guide.value_label.text() == "字段内容"
    assert guide.actions_label.text() == "操作"
    assert guide.index_label.width() == wide.index_width
    assert guide.token_label.width() == wide.token_width
    assert guide.actions_label.width() == wide.actions_width
    assert get_theme().text_hint in guide.token_label.styleSheet()

    guide.resize(620, 32)
    qapp.processEvents()
    narrow = guide.metrics()
    assert narrow.guide_visible is False
    assert guide.maximumHeight() == 0
    assert guide.token_label.isHidden()
    assert narrow.token_width < wide.token_width

    assert resolve_token_column_metrics(960) == wide


def test_timeline_node_column_guide_keeps_time_node_columns_aligned(qapp):
    guide = TimelineNodeColumnGuide()
    guide.resize(1200, 32)
    guide.show()
    qapp.processEvents()

    wide = guide.metrics()
    assert wide.guide_visible is True
    assert guide.index_label.text() == "序号"
    assert guide.token_label.text() == "时间字段"
    assert guide.position_label.text() == "位置（%）"
    assert guide.result_label.text() == "日期结果"
    assert guide.index_label.width() == wide.index_width
    assert guide.position_label.width() == wide.position_width
    assert guide.token_label.width() > guide.position_label.width()
    assert wide.token_stretch == 3
    assert wide.result_stretch == 2
    assert get_theme().text_hint in guide.result_label.styleSheet()

    guide.resize(620, 32)
    qapp.processEvents()
    narrow = guide.metrics()
    assert narrow.guide_visible is False
    assert guide.maximumHeight() == 0
    assert guide.result_label.isHidden()
    assert narrow.position_width < wide.position_width
    assert resolve_timeline_node_column_metrics(1200) == wide


def test_asset_column_guide_keeps_navigation_after_source_column_collapses(qapp):
    guide = AssetColumnGuide(source_text="图片来源", action_count=5)
    guide.resize(1100, 32)
    guide.show()
    qapp.processEvents()

    wide = guide.metrics()
    assert wide.guide_visible is True
    assert wide.source_visible is True
    assert guide.name_label.text() == "名称"
    assert guide.token_label.width() == wide.token_width
    assert guide.name_label.width() == wide.name_width
    assert guide.actions_label.width() == wide.actions_width

    guide.resize(700, 32)
    qapp.processEvents()
    medium = guide.metrics()
    assert medium.source_visible is True
    assert not guide.source_label.isHidden()

    narrow = guide._sync_metrics(660, force=True)
    assert narrow.guide_visible is True
    assert narrow.source_visible is False
    assert guide.maximumHeight() == 32
    assert guide.source_label.isHidden()
    assert not guide.name_label.isHidden()
    assert resolve_asset_column_metrics(660, action_count=5) == narrow

    compact = resolve_asset_column_metrics(620, action_count=5)
    assert compact.guide_visible is False
