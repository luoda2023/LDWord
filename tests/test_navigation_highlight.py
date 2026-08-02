import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QLineEdit
from src.shared.ui.navigation_highlight import NavigationHighlighter


def _app():
    return QApplication.instance() or QApplication([])


def test_navigation_highlighter_moves_single_highlight_between_widgets():
    app = _app()
    first = QLineEdit()
    second = QLineEdit()
    first.setStyleSheet("color: red;")
    second.setStyleSheet("color: blue;")
    highlighter = NavigationHighlighter()

    try:
        highlighter.highlight(first, "body.font_cn")

        assert highlighter.current_widget is first
        assert first.property("navigation_field_highlight") is True
        assert first.property("navigation_field_display_label") == "body.font_cn"
        assert first.property("navigation_field_raw_label") == "body.font_cn"
        assert first.property("navigation_field_diagnostic_label") == ""
        assert first.toolTip() == "当前执行问题定位：body.font_cn"
        assert "border: 2px solid" in first.styleSheet()

        highlighter.highlight(
            second,
            "scene.document_scope.selected_roles",
            display_label="自选区域",
        )

        assert highlighter.current_widget is second
        assert first.property("navigation_field_highlight") is False
        assert first.property("navigation_field_raw_label") == ""
        assert first.styleSheet() == "color: red;"
        assert first.toolTip() == ""
        assert second.property("navigation_field_highlight") is True
        assert second.property("navigation_field_display_label") == (
            "自选区域"
        )
        assert second.property("navigation_field_raw_label") == (
            "scene.document_scope.selected_roles"
        )
        assert second.property("navigation_field_diagnostic_label") == (
            "scene.document_scope.selected_roles"
        )
        assert second.toolTip() == "当前执行问题定位：自选区域"

        highlighter.clear()

        assert highlighter.current_widget is None
        assert second.property("navigation_field_highlight") is False
        assert second.property("navigation_field_raw_label") == ""
        assert second.styleSheet() == "color: blue;"
        assert second.toolTip() == ""
    finally:
        first.close()
        second.close()
        app.processEvents()
