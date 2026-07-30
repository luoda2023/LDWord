import sys
import threading
import time
from types import SimpleNamespace

from PIL import Image
from PySide6.QtTest import QTest

from src.config.master_library import get_master
from src.qt_api import QApplication, QPoint, QScrollArea, QSize, QVBoxLayout, QWidget, Qt
from src.shared.engine.document_word_preview import (
    DocumentWordPreviewRequest,
    DocumentWordPreviewResult,
    PreviewDocumentBuild,
    render_document_word_preview,
)
from src.shared.engine.official_word_preview import (
    real_word_preview_enabled,
    render_official_word_preview,
)
from src.shared.engine.pdf_page_renderer import render_pdf_pages_png
from src.shared.ui.document_page_preview import (
    DocumentPagePreview,
    _fit_document_preview_size,
)
from src.ui.panels.document_word_preview_controller import (
    DocumentWordPreviewController,
)


def _app():
    return QApplication.instance() or QApplication([])


def test_real_word_preview_feature_flag_is_reversible():
    assert real_word_preview_enabled({"ALAVETTE_REAL_WORD_PREVIEW": "0"}) is False
    assert real_word_preview_enabled({"ALAVETTE_REAL_WORD_PREVIEW": "false"}) is False
    assert real_word_preview_enabled({"ALAVETTE_REAL_WORD_PREVIEW": "1"}) is True
    assert real_word_preview_enabled({"PYTEST_CURRENT_TEST": "active"}) is False


def test_document_word_preview_honors_pre_cancel_before_build(tmp_path):
    cancel_event = threading.Event()
    cancel_event.set()
    build_calls: list[object] = []
    request = DocumentWordPreviewRequest(
        provider_id="official_plan",
        variant_id="cancelled",
        cache_payload={"revision": 1},
        build_document=lambda output_dir: build_calls.append(output_dir),
    )

    result = render_document_word_preview(
        request,
        cache_root=tmp_path,
        cancel_event=cancel_event,
    )

    assert result.status == "cancelled"
    assert build_calls == []
    assert list(tmp_path.rglob("*")) == []


def test_official_word_preview_uses_real_docx_cache_without_rendering(tmp_path):
    master = get_master("official_gbt_standard", "official")
    assert master is not None

    first = render_official_word_preview(
        profile_id="notice",
        entity_data={},
        master=master,
        cache_root=tmp_path,
        attempt_render=False,
    )
    second = render_official_word_preview(
        profile_id="notice",
        entity_data={},
        master=master,
        cache_root=tmp_path,
        attempt_render=False,
    )

    assert first.status == "docx_only"
    assert first.docx_path is not None and first.docx_path.is_file()
    assert first.uses_sample_data is True
    assert first.cache_hit is False
    assert second.cache_key == first.cache_key
    assert second.cache_hit is True

    renamed = render_official_word_preview(
        profile_id="notice",
        entity_data={"organization": "第一机关"},
        field_aliases={"发文机关2": "organization"},
        master=master,
        cache_root=tmp_path,
        attempt_render=False,
    )
    assert renamed.cache_key != first.cache_key
    assert renamed.cache_hit is False


def test_pdf_page_renderer_prefers_embedded_pdfium(monkeypatch, tmp_path):
    source = tmp_path / "preview.pdf"
    source.write_bytes(b"%PDF-1.4 test fixture")

    class FakeBitmap:
        def to_pil(self):
            return Image.new("RGB", (200, 280), "white")

        def close(self):
            return None

    class FakePage:
        def render(self, *, scale):
            assert scale == 2.0
            return FakeBitmap()

        def close(self):
            return None

    class FakeDocument:
        def __init__(self, path):
            assert path == str(source)

        def __len__(self):
            return 2

        def __getitem__(self, index):
            assert index in (0, 1)
            return FakePage()

        def close(self):
            return None

    monkeypatch.setitem(
        sys.modules,
        "pypdfium2",
        SimpleNamespace(PdfDocument=FakeDocument),
    )

    pages, issues = render_pdf_pages_png(source, tmp_path)

    assert issues == ()
    assert [path.name for path in pages] == [
        "preview_page-001.png",
        "preview_page-002.png",
    ]
    assert all(path.is_file() for path in pages)


def test_document_page_preview_supports_paging_and_error_fallback(tmp_path):
    app = _app()
    pages = []
    for index, color in enumerate(((255, 255, 255), (240, 245, 255)), start=1):
        path = tmp_path / f"page_{index}.png"
        Image.new("RGB", (600, 840), color).save(path)
        pages.append(path)

    preview = DocumentPagePreview()
    try:
        preview.resize(700, 900)
        preview.show()
        preview.set_pages(pages, uses_sample_data=True, renderer="word_com")
        app.processEvents()
        assert preview.page_count() == 2
        assert preview.current_page_index() == 0
        assert preview._status.isHidden()
        assert preview._image.height() > 0
        assert preview._image.isVisible()
        assert not hasattr(preview, "_preview_viewport")
        assert not hasattr(preview, "_open_hint")
        assert preview._image.cursor().shape() == Qt.PointingHandCursor
        assert preview._previous_btn.text() == ""
        assert preview._next_btn.text() == ""
        assert preview._refresh_btn.text() == ""
        assert not preview._previous_btn.icon().isNull()
        assert not preview._next_btn.icon().isNull()
        assert not preview._refresh_btn.icon().isNull()
        assert preview._page_label.text() == "1 / 2"
        assert preview.findChild(QWidget, "document_page_preview_zoom_out") is None
        assert preview.findChild(QWidget, "document_page_preview_zoom_label") is None
        assert preview.findChild(QWidget, "document_page_preview_zoom_in") is None
        assert not hasattr(preview, "_scroll")

        QTest.mouseClick(preview._image, Qt.LeftButton)
        app.processEvents()
        dialog = preview._preview_dialog
        assert dialog is not None and dialog.isVisible()
        assert dialog.windowTitle() == "文档大图预览"
        assert dialog._close_btn.text() == ""
        assert not dialog._close_btn.icon().isNull()
        assert not dialog._image.pixmap().isNull()
        assert not hasattr(dialog, "_page_label")
        initial_zoom = dialog._zoom
        assert 0.1 <= initial_zoom <= 1.0
        assert dialog.viewport.mode == "fit"
        assert dialog.content.natural_size == QSize(600, 840)
        assert dialog._scroll.viewport().cursor().shape() == Qt.ArrowCursor

        original_position = dialog.pos()
        dialog._header._begin_window_drag(QPoint(100, 100), use_native_move=False)
        dialog._header._continue_window_drag(QPoint(130, 145))
        dialog._header._end_window_drag()
        assert dialog.pos() == original_position + QPoint(30, 45)

        pointer = dialog._scroll.viewport().rect().center()
        rendered_before_zoom = dialog._image.size()
        dialog._zoom_at_pointer(120, pointer)
        assert initial_zoom < dialog._zoom <= 8.0
        assert dialog._image.width() > rendered_before_zoom.width()
        hbar = dialog._scroll.horizontalScrollBar()
        vbar = dialog._scroll.verticalScrollBar()
        previous_scroll = (hbar.value(), vbar.value())
        dialog._scroll._start_drag(QPoint(100, 100))
        assert dialog._scroll.viewport().cursor().shape() == Qt.ClosedHandCursor
        dialog._scroll._move_drag(QPoint(70, 70))
        dialog._scroll._finish_drag()
        assert hbar.value() >= previous_scroll[0]
        assert vbar.value() >= previous_scroll[1]
        assert dialog._scroll.viewport().cursor().shape() == Qt.OpenHandCursor
        for _ in range(20):
            dialog._zoom_at_pointer(120, pointer)
        assert dialog._zoom == 8.0
        # One wheel notch is intentionally absorbed by the 100% snap point.
        for _ in range(31):
            dialog._zoom_at_pointer(-120, pointer)
        assert 0.1 <= dialog._zoom < 0.13
        assert dialog._scroll._pan_enabled is False

        dialog.close()
        preview.show_next_page()
        app.processEvents()
        assert preview.current_page_index() == 1

        preview.set_error("renderer unavailable")
        assert preview.page_count() == 0
        assert "快速结构" not in preview._status.text()
    finally:
        preview.close()


def test_document_preview_dialog_uses_screen_work_area_instead_of_parent_size(tmp_path):
    app = _app()
    page = tmp_path / "page.png"
    Image.new("RGB", (1191, 1684), "white").save(page)

    preview = DocumentPagePreview()
    try:
        preview.resize(360, 460)
        preview.show()
        preview.set_pages([page])
        app.processEvents()

        assert preview.open_preview_dialog() is True
        app.processEvents()
        dialog = preview._preview_dialog
        assert dialog is not None
        screen_geometry = preview.screen().availableGeometry()
        expected_size = _fit_document_preview_size(
            QSize(1191, 1684),
            screen_geometry.size(),
        )

        assert dialog.size() == expected_size
        assert dialog.height() > round(preview.height() * 0.9)
        assert dialog.width() <= round(screen_geometry.width() * 0.9)
        assert dialog.height() <= round(screen_geometry.height() * 0.9)
        assert abs(dialog.geometry().center().x() - screen_geometry.center().x()) <= 1
        assert abs(dialog.geometry().center().y() - screen_geometry.center().y()) <= 1
    finally:
        preview.close()


def test_document_preview_size_is_capped_for_small_high_dpi_work_areas():
    size = _fit_document_preview_size(QSize(1191, 1684), QSize(400, 300))

    assert size.width() <= 360
    assert size.height() <= 270
    assert size.width() > 0
    assert size.height() > 0


def test_document_page_preview_does_not_expand_or_recurse_in_scroll_layout(tmp_path):
    app = _app()
    page = tmp_path / "page.png"
    Image.new("RGB", (1200, 1680), "white").save(page)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    content = QWidget()
    layout = QVBoxLayout(content)
    preview = DocumentPagePreview(content)
    layout.addWidget(preview)
    scroll.setWidget(content)
    scroll.resize(1000, 700)
    try:
        preview.set_pages([page])
        scroll.show()
        observed_sizes = []
        for _ in range(30):
            app.processEvents()
            observed_sizes.append((preview.width(), preview.height()))

        assert preview.width() <= scroll.viewport().width()
        assert len(set(observed_sizes[-5:])) == 1
    finally:
        scroll.close()


def test_word_preview_controller_collapses_stale_debounced_requests(tmp_path):
    app = _app()
    page = tmp_path / "page.png"
    Image.new("RGB", (320, 480), "white").save(page)
    calls: list[str] = []

    def renderer(request, *, force=False):
        del force
        calls.append(request.variant_id)
        time.sleep(0.01)
        return DocumentWordPreviewResult(
            status="ready",
            provider_id=request.provider_id,
            variant_id=request.variant_id,
            page_paths=(page,),
        )

    controller = DocumentWordPreviewController(renderer=renderer, debounce_ms=15)
    results = []
    controller.result_ready.connect(results.append)
    try:
        def build(_output_dir):
            return PreviewDocumentBuild(status="unused")

        controller.request_preview(
            DocumentWordPreviewRequest("official", "notice", {}, build)
        )
        controller.request_preview(
            DocumentWordPreviewRequest("official", "letter", {}, build)
        )
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not results:
            app.processEvents()
            time.sleep(0.01)

        assert calls == ["letter"]
        assert [result.variant_id for result in results] == ["letter"]
    finally:
        controller.shutdown()
        controller.deleteLater()
        app.processEvents()
