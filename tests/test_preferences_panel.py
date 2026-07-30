from __future__ import annotations

from datetime import datetime, timezone
import inspect
from pathlib import Path

from src.app_meta import APP_VERSION
from src.qt_api import QLabel, QPushButton
from src.services.problem_report import build_problem_report, sanitize_log_text
from src.shared.ui.form_row import FormRow
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import get_theme
from src.ui.bridge import PanelBridge
from src.ui.panel_registry import create_panel
from src.ui.panels import preferences_panel as preferences_panel_module
from src.ui.panels.preferences_panel import PreferencesPanel


def test_panel_registry_creates_real_preferences_panel(qapp):
    panel = create_panel("preferences", PanelBridge())
    try:
        assert isinstance(panel, PreferencesPanel)
        assert panel._nav_rail.item_count == 2
        assert panel._nav_rail.selected_card_id() == "about"
        assert panel._about_nav._title.text() == "关于软件"
        assert panel._about_nav._badge.text() == APP_VERSION
        assert panel._ai_nav._title.text() == "AI 模型"
    finally:
        panel.close()


def test_ai_preferences_use_shared_form_and_separate_new_action(qapp):
    panel = PreferencesPanel(PanelBridge())
    try:
        assert isinstance(panel._ai_profile_combo, StyledComboBox)
        assert all(
            panel._ai_profile_combo.itemData(index) != "__new__"
            for index in range(panel._ai_profile_combo.count())
        )
        assert panel._ai_new_button.text() == "新增配置"
        assert panel._ai_delete_button.property("variant") == "ghost-danger"
        assert panel._ai_content.maximumWidth() == 960
        assert panel._ai_profile_combo.accessibleName() == "当前模型配置"
        assert panel._ai_label_input.accessibleName() == "显示名称"
        assert panel._ai_url_input.accessibleName() == "API 地址"
        assert panel._ai_model_input.accessibleName() == "模型 ID"
        assert panel._ai_key_input.accessibleName() == "API Key"

        labels = {
            row.label_text
            for row in panel._ai_content.findChildren(FormRow)
        }
        assert labels == {"当前配置", "显示名称", "API 地址", "模型 ID", "API Key"}

        panel._ai_new_button.click()
        assert panel._ai_loaded_profile_id == "__new__"
        assert panel._ai_profile_combo.currentIndex() == -1
        assert panel._ai_profile_combo.display_text() == "新配置（尚未保存）"
        assert panel._ai_state_badge.text() == "未保存"
        assert panel._ai_state_badge.variant() == "warning"
    finally:
        panel.close()


def test_ai_preferences_remain_complete_at_hidpi_equivalent_width(qapp):
    panel = PreferencesPanel(PanelBridge())
    try:
        panel.resize(1289, 690)
        panel.show()
        panel.show_preferences_page("ai")
        panel._start_new_ai_profile()
        qapp.processEvents()

        viewport = panel._shell.detail_scroll.viewport()
        margins = panel._detail_layout.contentsMargins()
        available_width = viewport.width() - margins.left() - margins.right()
        assert panel._ai_content.width() <= available_width
        assert panel._ai_content.width() <= panel._ai_content.maximumWidth()

        selector = panel._ai_profile_combo.parentWidget()
        assert panel._ai_new_button.geometry().right() < selector.width()
        assert panel._ai_delete_button.geometry().right() < panel._ai_actions_row.width()
    finally:
        panel.close()


def test_ai_preferences_small_text_uses_readable_contrast(qapp):
    panel = PreferencesPanel(PanelBridge())
    try:
        theme = get_theme()
        assert f"color: {theme.text_secondary}" in panel._ai_key_status.styleSheet()
        assert f"color: {theme.text_secondary}" in panel._ai_label_input.styleSheet()
        assert f"color: {theme.text_secondary}" in panel._ai_check_button.styleSheet()

        panel._start_new_ai_profile()
        badge_style = panel._ai_state_badge._label.styleSheet()
        assert f"color: {theme.text_primary}" in badge_style
        assert f"background: {theme.warning_bg}" in badge_style
    finally:
        panel.close()


def test_preferences_panel_keeps_about_copy_plain_and_bounded(qapp):
    panel = PreferencesPanel(PanelBridge())
    try:
        labels = (label.text() for label in panel.findChildren(QLabel))
        buttons = (button.text() for button in panel.findChildren(QPushButton))
        visible_text = "\n".join((*labels, *buttons))
        assert "文档仅在本机处理，不会自动上传" in visible_text
        assert "打开日志文件" in visible_text
        assert "导出问题报告" in visible_text
        assert "本软件" in visible_text
        assert "MIT License" in visible_text
        assert "第三方组件" in visible_text
        assert "个组件" in visible_text
        assert panel._license_button.text() == ""
        assert panel._third_party_button.text() == ""
        assert "文件处理" not in visible_text
        assert "运行日志不会自动发送" not in visible_text
        assert "需要排查问题时" not in visible_text
        assert "问题报告不包含你的文档" not in visible_text
        assert "本软件自身和使用到的开源组件" not in visible_text
        assert "查看版本、处理问题和开源许可" not in visible_text
        assert "查看使用说明" not in visible_text
        assert "字体引擎" not in visible_text
        assert "Word/WPS" not in visible_text
    finally:
        panel.close()


def test_problem_report_privacy_copy_is_attached_to_the_export_action(qapp):
    panel = PreferencesPanel(PanelBridge())
    try:
        assert "不包含文档内容" in panel._export_report_button.toolTip()
        assert "本地路径会被隐藏" in (
            panel._export_report_button.accessibleDescription()
        )
    finally:
        panel.close()


def test_problem_report_hides_user_and_local_paths(tmp_path):
    home = Path(r"C:\Users\Alice")
    raw = (
        'File "C:\\Users\\Alice\\Documents\\secret.docx", line 10\n'
        "Alice opened C:/Users/Alice/Desktop/private.docx\n"
        r"\\server\private\customer.docx"
    )

    sanitized = sanitize_log_text(raw, home=home)

    assert "Alice" not in sanitized
    assert "secret.docx" not in sanitized
    assert "private.docx" not in sanitized
    assert "customer.docx" not in sanitized
    assert "<本地路径>" in sanitized
    assert "<网络路径>" in sanitized


def test_problem_report_contains_support_facts_but_not_document_path(tmp_path):
    log_path = tmp_path / "app.log"
    log_path.write_text(
        '2026-07-13 ERROR File "C:\\Users\\Alice\\secret.docx" failed\n',
        encoding="utf-8",
    )

    report = build_problem_report(
        log_path=log_path,
        created_at=datetime(2026, 7, 13, 20, 30, tzinfo=timezone.utc),
    )

    assert f"软件版本：{APP_VERSION}" in report
    assert "生成时间：2026-07-13 20:30:00 +0000" in report
    assert "不会自动发送" in report
    assert "secret.docx" not in report
    assert "C:\\Users" not in report


def test_preferences_panel_opens_the_resolved_log(qapp, tmp_path, monkeypatch):
    log_path = tmp_path / "alavette_form.log"
    log_path.write_text("example", encoding="utf-8")
    opened: list[str] = []
    monkeypatch.setattr(preferences_panel_module, "resolve_log_path", lambda: log_path)
    monkeypatch.setattr(
        preferences_panel_module.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toLocalFile()) or True,
    )

    panel = PreferencesPanel(PanelBridge())
    try:
        panel._open_log_button.click()
        assert len(opened) == 1
        assert Path(opened[0]).resolve() == log_path.resolve()
    finally:
        panel.close()


def test_preferences_panel_exports_local_problem_report(qapp, tmp_path, monkeypatch):
    log_path = tmp_path / "alavette_form.log"
    log_path.write_text(
        'ERROR File "C:\\Users\\Alice\\private.docx" failed',
        encoding="utf-8",
    )
    target = tmp_path / "support-report.txt"
    notices: list[str] = []
    monkeypatch.setattr(preferences_panel_module, "resolve_log_path", lambda: log_path)
    monkeypatch.setattr(
        preferences_panel_module.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(target), "文本文件 (*.txt)"),
    )
    monkeypatch.setattr(
        preferences_panel_module.Toast,
        "show_success",
        notices.append,
    )

    panel = PreferencesPanel(PanelBridge())
    try:
        panel._export_report_button.click()
        report = target.read_text(encoding="utf-8-sig")
        assert f"软件版本：{APP_VERSION}" in report
        assert "private.docx" not in report
        assert notices == ["问题报告已保存：support-report.txt"]
    finally:
        panel.close()


def test_problem_report_export_has_no_network_transport() -> None:
    service_source = inspect.getsource(build_problem_report)
    export_source = inspect.getsource(PreferencesPanel._export_problem_report)
    forbidden = (
        "requests.",
        "httpx.",
        "urllib.",
        "urlopen(",
        "socket.",
        "QNetwork",
        "upload",
    )

    assert "target.write_text(" in export_source
    assert all(token not in service_source for token in forbidden)
    assert all(token not in export_source for token in forbidden)
