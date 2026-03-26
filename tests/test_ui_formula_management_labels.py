import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QLabel

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.scene.manager import load_scene_from_data
from src.ui.main_window import FormatConfigDialog, MainWindow


def _app():
    return QApplication.instance() or QApplication([])


def test_main_window_formula_management_label_and_help_copy(monkeypatch):
    _app()
    monkeypatch.setattr(MainWindow, "_load_ui_state", lambda self: {})
    monkeypatch.setattr(MainWindow, "_save_ui_state", lambda self: None)

    captured: dict[str, object] = {}

    def _fake_exec(dialog: QDialog):
        captured["title"] = dialog.windowTitle()
        captured["texts"] = [label.text() for label in dialog.findChildren(QLabel)]
        return 0

    monkeypatch.setattr(QDialog, "exec", _fake_exec)

    window = MainWindow()
    try:
        assert window._formula_management_check.text() == "公式表格管理"
        assert "总开关" not in window._formula_management_check.toolTip()

        window._show_lab_help_dialog("formula_management")

        assert captured["title"] == "公式表格管理 使用须知"
        joined = "\n".join(captured["texts"])
        assert "总开关" not in joined
        assert "已完成并通过回归测试" in joined
        assert "统一控制公式编码统一、公式转公式表格、公式表格编号、公式格式统一的启停" in joined
    finally:
        window.close()


def test_format_config_dialog_formula_pipeline_tooltip_uses_new_name():
    _app()
    dlg = FormatConfigDialog(load_scene_from_data({}))
    try:
        tooltip = dlg._pipeline_checks["formula_convert"].toolTip()
        assert tooltip == "由主界面“实验室 - 公式表格管理”控制。"

        labels = [label.text() for label in dlg.findChildren(QLabel)]
        assert all("公式表格管理（总开关）" not in text for text in labels)
    finally:
        dlg.close()
