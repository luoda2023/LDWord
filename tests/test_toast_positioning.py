import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QWidget
from src.shared.ui.theme import get_theme, theme_rgba
from src.shared.ui.toast import Toast, _TOAST_ICON_MAP


def _app():
    return QApplication.instance() or QApplication([])


def _clear_toasts() -> None:
    for toast in list(Toast._toasts):
        toast.close()
    Toast._toasts.clear()


def test_toast_uses_real_icons_for_every_status_variant():
    _app()

    assert _TOAST_ICON_MAP == {
        "info": "info",
        "success": "circle-check",
        "warning": "alert-triangle",
        "error": "circle-x",
    }

    for variant in _TOAST_ICON_MAP:
        toast = Toast("status", variant)
        try:
            pixmap = toast._icon_label.pixmap()
            assert toast._icon_label.text() == ""
            assert pixmap is not None
            assert not pixmap.isNull()
        finally:
            toast.close()


def test_toast_positions_inside_active_window_bottom_right():
    app = _app()
    _clear_toasts()
    host = QWidget()
    host.setGeometry(120, 80, 900, 600)
    host.show()
    app.processEvents()
    host.activateWindow()
    app.processEvents()

    toast = Toast("已删除资料包: 未命名资料包 副本", "success", duration=60_000)
    Toast._toasts.append(toast)

    try:
        toast.show_toast()
        app.processEvents()

        anchor = host.geometry()
        toast_rect = toast.geometry()
        assert toast_rect.left() >= anchor.left()
        assert toast_rect.top() >= anchor.top()
        assert toast_rect.right() <= anchor.right()
        assert toast_rect.bottom() <= anchor.bottom()
        assert abs((anchor.right() - Toast._edge_margin) - toast_rect.right()) <= 2
        expected_bottom = (
            anchor.bottom()
            - Toast._edge_margin
            - Toast._bottom_reserved_margin
        )
        assert abs(expected_bottom - toast_rect.bottom()) <= 2
    finally:
        toast.close()
        _clear_toasts()
        host.close()


def test_toast_wraps_long_messages_and_stacks_without_overlap():
    app = _app()
    _clear_toasts()
    host = QWidget()
    host.setGeometry(120, 80, 900, 600)
    host.show()
    app.processEvents()
    host.activateWindow()
    app.processEvents()

    first = Toast("已复制提示词", "success", duration=60_000)
    second = Toast(
        "已打开母版文件夹: user_default_exam_copy_15.docx，文件夹路径较长时也要保持独立底色",
        "success",
        duration=60_000,
    )
    Toast._toasts.extend([first, second])

    try:
        first.show_toast()
        second.show_toast()
        app.processEvents()

        first_rect = first.geometry()
        second_rect = second.geometry()
        assert second._message_label.wordWrap()
        assert second_rect.width() <= Toast._max_width
        assert second_rect.bottom() <= first_rect.top() - Toast._stack_gap + 2
    finally:
        first.close()
        second.close()
        _clear_toasts()
        host.close()


def test_toast_keeps_short_message_on_one_line_and_uses_glass_surface():
    app = _app()
    _clear_toasts()
    host = QWidget()
    host.setGeometry(120, 80, 900, 600)
    host.show()
    app.processEvents()
    host.activateWindow()
    app.processEvents()

    toast = Toast("已删除方案: 公文基础方案 副本", "success", duration=60_000)
    Toast._toasts.append(toast)

    try:
        toast.show_toast()
        app.processEvents()

        text_width = toast._message_label.fontMetrics().horizontalAdvance(
            toast._message_label.text()
        )
        surface_style = toast.styleSheet()
        assert not toast._message_label.wordWrap()
        assert toast._message_label.width() >= text_width
        assert f"background: {theme_rgba(get_theme().bg_card, 0.82)}" in surface_style
        assert "border: none" in surface_style
    finally:
        toast.close()
        _clear_toasts()
        host.close()
