from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QColor, QLabel, QPixmap, QPoint, QSize, Qt, QWidget
from src.shared.ui.preview_dialog import (
    ImagePreviewDialog,
    PixmapPreviewContent,
    PreviewDialog,
    PreviewShellDialog,
    PreviewItem,
    TextPreviewDialog,
    load_preview_pixmap,
)
from src.shared.ui.theme import get_theme
from src.ui.panels.assets.image_preview_presenter import ImagePreviewPresenterMixin


def _app():
    return QApplication.instance() or QApplication([])


def test_shared_preview_shell_owns_zoom_fit_and_stable_close_position():
    app = _app()
    pixmap = QPixmap(800, 600)
    pixmap.fill(QColor("white"))
    dialog = PreviewDialog(PixmapPreviewContent(pixmap), title="测试预览")
    try:
        dialog.resize(640, 520)
        dialog.show()
        app.processEvents()

        assert dialog.property("previewShell") is True
        assert dialog.content.natural_size == QSize(800, 600)
        assert dialog._toolbar_layout.indexOf(dialog._close_btn) == (
            dialog._toolbar_layout.count() - 1
        )
        assert dialog._zoom_label.minimumWidth() >= 88
        assert dialog.viewport.mode == "fit"

        dialog.viewport.actual_size()
        assert dialog.zoom == 1.0
        assert dialog.viewport.mode == "actual"
        dialog.viewport.toggle_fit_actual()
        assert dialog.viewport.mode == "fit"
    finally:
        dialog.close()
        app.processEvents()


def test_shared_preview_shell_uses_active_theme_tokens():
    app = _app()
    pixmap = QPixmap(320, 180)
    pixmap.fill(QColor("white"))
    dialog = PreviewDialog(PixmapPreviewContent(pixmap), title="测试预览")
    try:
        dialog.show()
        app.processEvents()

        theme = get_theme()
        stylesheet = dialog.styleSheet()
        assert dialog.testAttribute(Qt.WA_TranslucentBackground)
        assert dialog._surface._background == QColor(theme.bg_window)
        assert dialog._surface._border_color == QColor(theme.border)
        assert dialog._surface._radius == theme.shell_radius
        assert "background: transparent;" in stylesheet
        assert f"background: {theme.bg_card};" in stylesheet
        assert f"color: {theme.text_primary};" in stylesheet
        assert f"border-color: {theme.border_focus};" in stylesheet
    finally:
        dialog.close()
        app.processEvents()


def test_text_preview_reuses_shell_without_visual_preview_controls():
    app = _app()
    dialog = TextPreviewDialog(
        "MIT License\n\nPermission is hereby granted...",
        title="本软件许可",
    )
    try:
        dialog.show()
        app.processEvents()

        assert isinstance(dialog, PreviewShellDialog)
        assert dialog.property("previewShell") is True
        assert dialog.viewer.isReadOnly() is True
        assert dialog.viewer.toPlainText().startswith("MIT License")
        assert dialog.viewer.verticalScrollBarPolicy() != Qt.ScrollBarAlwaysOff
        assert not hasattr(dialog, "viewport")
        assert not hasattr(dialog, "_zoom_label")
        assert dialog._toolbar_layout.count() == 1
        assert dialog._toolbar_layout.indexOf(dialog._close_btn) == 0
    finally:
        dialog.close()
        app.processEvents()


def test_transparent_material_image_uses_white_document_backing():
    _app()
    pixmap = QPixmap(120, 80)
    pixmap.fill(Qt.transparent)

    content = PixmapPreviewContent(pixmap)

    assert pixmap.hasAlphaChannel() is True
    assert "background: #FFFFFF" in content.widget.styleSheet()


def test_wheel_zoom_snaps_at_actual_size_and_requires_one_extra_notch():
    _app()
    pixmap = QPixmap(800, 600)
    pixmap.fill(QColor("white"))
    dialog = PreviewDialog(PixmapPreviewContent(pixmap), title="测试预览")
    pointer = QPoint(100, 80)
    try:
        dialog.viewport.set_zoom(0.95)
        dialog.viewport.zoom_at_pointer(120, pointer)
        assert dialog.zoom == pytest.approx(1.0)
        assert dialog.viewport.mode == "actual"

        dialog.viewport.zoom_at_pointer(120, pointer)
        assert dialog.zoom == pytest.approx(1.0)

        dialog.viewport.zoom_at_pointer(120, pointer)
        assert dialog.zoom == pytest.approx(1.15)
        assert dialog.viewport.mode == "custom"
    finally:
        dialog.close()


def test_wheel_zoom_snap_works_from_above_and_releases_on_reverse():
    _app()
    pixmap = QPixmap(800, 600)
    pixmap.fill(QColor("white"))
    dialog = PreviewDialog(PixmapPreviewContent(pixmap), title="测试预览")
    pointer = QPoint(100, 80)
    try:
        dialog.viewport.set_zoom(1.05)
        dialog.viewport.zoom_at_pointer(-120, pointer)
        assert dialog.zoom == pytest.approx(1.0)

        dialog.viewport.zoom_at_pointer(120, pointer)
        assert dialog.zoom == pytest.approx(1.15)
    finally:
        dialog.close()


def test_fine_grained_wheel_input_accumulates_before_leaving_actual_size():
    _app()
    pixmap = QPixmap(800, 600)
    pixmap.fill(QColor("white"))
    dialog = PreviewDialog(PixmapPreviewContent(pixmap), title="测试预览")
    pointer = QPoint(100, 80)
    try:
        dialog.viewport.set_zoom(0.99)
        dialog.viewport.zoom_at_pointer(30, pointer)
        assert dialog.zoom == pytest.approx(1.0)

        for _ in range(4):
            dialog.viewport.zoom_at_pointer(30, pointer)
        assert dialog.zoom == pytest.approx(1.0)

        dialog.viewport.zoom_at_pointer(30, pointer)
        assert dialog.zoom > 1.0
    finally:
        dialog.close()


def test_toolbar_zoom_snaps_to_actual_size_without_sticky_hold():
    _app()
    pixmap = QPixmap(800, 600)
    pixmap.fill(QColor("white"))
    dialog = PreviewDialog(PixmapPreviewContent(pixmap), title="测试预览")
    try:
        dialog.viewport.set_zoom(0.95)
        dialog.viewport.zoom_by(1.15)
        assert dialog.zoom == pytest.approx(1.0)
        assert dialog.viewport.mode == "actual"

        dialog.viewport.zoom_by(1.15)
        assert dialog.zoom == pytest.approx(1.15)
    finally:
        dialog.close()


def test_image_preview_loads_metadata_pages_and_comparison(tmp_path):
    app = _app()
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    compare = tmp_path / "compare.png"
    Image.new("RGB", (320, 180), "white").save(first)
    Image.new("RGB", (640, 360), "blue").save(second)
    Image.new("RGB", (200, 100), "red").save(compare)

    compare_item = PreviewItem.from_path(
        compare,
        display_name="参考图",
        metadata={"reference": str(compare), "kind_label": "题图对比"},
    )
    dialog = ImagePreviewDialog(
        (
            PreviewItem.from_path(first, display_name="第一页"),
            PreviewItem.from_path(second, display_name="第二页"),
        ),
        compare_items=(compare_item,),
        allow_issue_marking=True,
    )
    issues: list[tuple[object, object]] = []
    dialog.issue_requested.connect(lambda item, region: issues.append((item, region)))
    try:
        dialog.show()
        app.processEvents()

        assert "320 × 180 px" in dialog._subtitle_label.text()
        assert dialog._previous_btn.isEnabled() is False
        assert dialog._next_btn.isEnabled() is True

        dialog.set_current_index(1)
        app.processEvents()
        assert dialog.current_item.path == second
        assert dialog.content.natural_size == QSize(640, 360)
        assert dialog._previous_btn.isEnabled() is True

        assert dialog.show_selected_comparison() is True
        assert dialog.comparison_size() == QSize(200, 100)
        dialog._compare_viewport.set_zoom(1.5)
        assert dialog.zoom == 1.5
        dialog._emit_issue_request()
        assert issues and issues[0][0] == compare_item
        assert issues[0][1]["image_width"] == 640
    finally:
        dialog.close()
        app.processEvents()


def test_image_loader_reports_missing_file_without_throwing(tmp_path):
    pixmap, image_format, error = load_preview_pixmap(
        PreviewItem.from_path(tmp_path / "missing.png")
    )

    assert pixmap.isNull()
    assert image_format == ""
    assert error == "文件不存在"


def test_assets_presenter_opens_shared_preview_instead_of_local_dialog(tmp_path):
    app = _app()
    path = tmp_path / "asset.png"
    Image.new("RGB", (120, 80), "white").save(path)

    class _Host(ImagePreviewPresenterMixin, QWidget):
        def __init__(self):
            super().__init__()
            self._image_preview_dialog = None
            self._current_image_preview_path = ""
            self._current_image_preview_display_name = ""
            self._current_image_preview_compare_options = []
            self._current_image_preview_question_figure_row = -1
            self._image_assets_status_label = QLabel(self)

    host = _Host()
    try:
        host._set_current_image_preview_path(str(path), display_name="LOGO")

        assert host._open_current_image_preview_dialog() is True
        app.processEvents()
        dialog = host._image_preview_dialog
        assert isinstance(dialog, ImagePreviewDialog)
        assert dialog.property("previewShell") is True
        assert dialog.windowTitle() == "图片资料预览"

        dialog.close()
        app.processEvents()
        assert host._image_preview_dialog is None
    finally:
        host.close()
