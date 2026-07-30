"""Reusable paged image preview for rendered document pages."""

from __future__ import annotations

from pathlib import Path

from src.qt_api import (
    QApplication,
    QHBoxLayout,
    QImageReader,
    QLabel,
    QPixmap,
    QPushButton,
    QSize,
    QSizePolicy,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.preview_dialog import ImagePreviewDialog, PreviewItem
from src.shared.ui.theme import bind_theme, get_theme


_PREVIEW_SCREEN_COVERAGE = 0.9
_PREVIEW_CHROME = 130
_PREVIEW_MIN_SIZE = 420


def _fit_document_preview_size(
    page_size: QSize,
    available_size: QSize,
) -> QSize:
    """Fit a page-shaped dialog inside 90% of one screen's work area."""

    maximum_width = max(1, round(available_size.width() * _PREVIEW_SCREEN_COVERAGE))
    maximum_height = max(1, round(available_size.height() * _PREVIEW_SCREEN_COVERAGE))
    minimum_width = min(_PREVIEW_MIN_SIZE, maximum_width)
    minimum_height = min(_PREVIEW_MIN_SIZE, maximum_height)

    if page_size.isEmpty():
        return QSize(
            max(minimum_width, min(760, maximum_width)),
            max(minimum_height, min(760, maximum_height)),
        )

    content_width = max(1, maximum_width - _PREVIEW_CHROME)
    content_height = max(1, maximum_height - _PREVIEW_CHROME)
    scale = min(
        content_width / max(1, page_size.width()),
        content_height / max(1, page_size.height()),
    )
    width = round(page_size.width() * scale) + _PREVIEW_CHROME
    height = round(page_size.height() * scale) + _PREVIEW_CHROME
    return QSize(
        min(maximum_width, max(minimum_width, width)),
        min(maximum_height, max(minimum_height, height)),
    )


class _ClickablePreviewLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API contract
        if event.button() == Qt.LeftButton and not self.pixmap().isNull():
            self.clicked.emit()
        super().mousePressEvent(event)

    def sizeHint(self) -> QSize:  # noqa: N802 - do not widen the parent scroll area
        return QSize(0, max(0, self.height()))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API contract
        return QSize(0, 0)


class _DocumentPreviewDialog(ImagePreviewDialog):
    """Document-page adapter for the application-wide image preview."""

    def __init__(
        self,
        page_paths: tuple[Path, ...],
        page_index: int,
        *,
        parent=None,
    ) -> None:
        screen = parent.screen() if parent is not None else QApplication.primaryScreen()
        available_size = (
            screen.availableGeometry().size()
            if screen is not None
            else QSize(1280, 820)
        )
        page_size = QImageReader(str(page_paths[page_index])).size()
        preferred_size = _fit_document_preview_size(page_size, available_size)
        items = tuple(
            PreviewItem.from_path(
                path,
                display_name=f"第 {index + 1} 页",
                label=f"{index + 1} / {len(page_paths)}",
            )
            for index, path in enumerate(page_paths)
        )
        super().__init__(
            items,
            current_index=page_index,
            title="文档大图预览",
            preferred_size=preferred_size,
            parent=parent,
        )
        self.setObjectName("document_page_preview_dialog")
        self.setProperty("preview_semantics", "rendered_document_page")
        self.set_status_text(
            "滚轮缩放 · 拖动平移 · 左右方向键翻页 · 0 原始尺寸 · F 适应窗口"
        )
        self._close_btn.setObjectName("document_page_preview_dialog_close")
        self._scroll = self.viewport.scroll
        self._scroll.setObjectName("document_page_preview_dialog_scroll")
        self._sync_compatibility_aliases()
        self.item_changed.connect(lambda *_args: self._sync_compatibility_aliases())

        QTimer.singleShot(0, self._sync_compatibility_aliases)

    @property
    def _zoom(self) -> float:
        return self.zoom

    def _zoom_at_pointer(self, delta: int, position) -> None:
        self.viewport.zoom_at_pointer(delta, position)

    def _sync_compatibility_aliases(self) -> None:
        content = self.content
        self._image = content.widget
        self._original_pixmap = content.pixmap
        self._base_size = self.viewport.rendered_size


class DocumentPagePreview(QWidget):
    refresh_requested = Signal()
    preview_opened = Signal()
    page_changed = Signal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("document_page_preview")
        self._page_paths: tuple[Path, ...] = ()
        self._page_index = 0
        self._original_pixmap = QPixmap()
        self._last_render_key: tuple[int, int] | None = None
        self._preview_dialog: _DocumentPreviewDialog | None = None
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._apply_pixmap)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._status = QLabel("准备生成真实 Word 预览…", self)
        self._status.setObjectName("document_page_preview_status")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._toolbar = QWidget(self)
        self._toolbar.setObjectName("document_page_preview_toolbar")
        toolbar_layout = QHBoxLayout(self._toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(6)

        self._previous_btn = QPushButton(self._toolbar)
        self._previous_btn.setObjectName("document_page_preview_previous")
        self._previous_btn.setFixedSize(32, 32)
        self._previous_btn.setToolTip("上一页")
        self._previous_btn.setAccessibleName("上一页")
        self._previous_btn.clicked.connect(self.show_previous_page)
        apply_button_variant(self._previous_btn, "secondary")
        toolbar_layout.addWidget(self._previous_btn)

        self._page_label = QLabel("0 / 0", self._toolbar)
        self._page_label.setObjectName("document_page_preview_page_label")
        self._page_label.setMinimumWidth(42)
        self._page_label.setAlignment(Qt.AlignCenter)
        toolbar_layout.addWidget(self._page_label)

        self._next_btn = QPushButton(self._toolbar)
        self._next_btn.setObjectName("document_page_preview_next")
        self._next_btn.setFixedSize(32, 32)
        self._next_btn.setToolTip("下一页")
        self._next_btn.setAccessibleName("下一页")
        self._next_btn.clicked.connect(self.show_next_page)
        apply_button_variant(self._next_btn, "secondary")
        toolbar_layout.addWidget(self._next_btn)

        self._refresh_btn = QPushButton(self._toolbar)
        self._refresh_btn.setObjectName("document_page_preview_refresh")
        self._refresh_btn.setFixedSize(32, 32)
        self._refresh_btn.setToolTip("刷新真实预览")
        self._refresh_btn.setAccessibleName("刷新真实预览")
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        apply_button_variant(self._refresh_btn, "secondary")
        toolbar_layout.addWidget(self._refresh_btn)

        self._image = _ClickablePreviewLabel("", self)
        self._image.setObjectName("document_page_preview_image")
        self._image.setAlignment(Qt.AlignCenter)
        self._image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._image.setFixedHeight(0)
        self._image.setCursor(Qt.PointingHandCursor)
        self._image.setToolTip("点击打开文档大图预览")
        self._image.clicked.connect(self.open_preview_dialog)
        self._image.setVisible(False)
        layout.addWidget(self._image)
        self._apply_theme()
        bind_theme(self, self._apply_theme)
        self._sync_controls()

    def set_loading(
        self,
        message: str = "正在通过 Microsoft Word 生成真实预览…",
        *,
        clear_pages: bool = False,
    ) -> None:
        if clear_pages:
            self._clear_pages()
        self._status.setText(message)
        self._status.setVisible(True)
        self._refresh_btn.setEnabled(False)

    def set_empty(self, message: str, *, refresh_enabled: bool = False) -> None:
        """Show a neutral empty state without presenting it as a render error."""

        self._clear_pages()
        self._status.setText(str(message or ""))
        self._status.setVisible(True)
        self._refresh_btn.setEnabled(bool(refresh_enabled))

    def set_pages(
        self,
        page_paths: tuple[Path, ...] | list[Path],
        *,
        uses_sample_data: bool = False,
        cache_hit: bool = False,
        renderer: str = "",
        preserve_current_page: bool = False,
        initial_page_index: int | None = None,
    ) -> None:
        previous_index = self._page_index
        self._page_paths = tuple(Path(path) for path in page_paths)
        if initial_page_index is not None:
            requested_index = int(initial_page_index)
        elif preserve_current_page:
            requested_index = previous_index
        else:
            requested_index = 0
        self._page_index = min(
            max(0, requested_index),
            max(0, len(self._page_paths) - 1),
        )
        del uses_sample_data, cache_hit, renderer
        self._status.clear()
        self._status.setVisible(False)
        self._refresh_btn.setEnabled(True)
        self._close_preview_dialog()
        self._load_current_page()

    def set_error(self, message: str) -> None:
        self._status.setText(f"真实 Word 预览暂不可用：{message}")
        self._status.setVisible(True)
        self._clear_pages()
        self._refresh_btn.setEnabled(True)

    def show_previous_page(self) -> None:
        if self._page_index <= 0:
            return
        self._page_index -= 1
        self._load_current_page()

    def show_next_page(self) -> None:
        if self._page_index + 1 >= len(self._page_paths):
            return
        self._page_index += 1
        self._load_current_page()

    def set_current_page(self, page_index: int) -> bool:
        """Select a rendered page while keeping the public API zero-based."""

        target = int(page_index)
        if not 0 <= target < len(self._page_paths):
            return False
        if target == self._page_index:
            return True
        self._page_index = target
        self._load_current_page()
        return True

    def page_count(self) -> int:
        return len(self._page_paths)

    def current_page_index(self) -> int:
        return self._page_index

    def toolbar_widget(self) -> QWidget:
        return self._toolbar

    def set_refresh_semantics(self, label: str) -> None:
        text = str(label or "刷新真实预览").strip() or "刷新真实预览"
        self._refresh_btn.setToolTip(text)
        self._refresh_btn.setAccessibleName(text)

    def open_preview_dialog(self) -> bool:
        if not self._page_paths or self._original_pixmap.isNull():
            return False
        dialog = self._preview_dialog
        if dialog is not None and dialog.isVisible():
            dialog.raise_()
            dialog.activateWindow()
            return True
        dialog = _DocumentPreviewDialog(
            self._page_paths,
            self._page_index,
            parent=self.window(),
        )
        dialog.finished.connect(self._clear_preview_dialog)
        self._preview_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self.preview_opened.emit()
        return True

    def _load_current_page(self) -> None:
        if not (0 <= self._page_index < len(self._page_paths)):
            self._original_pixmap = QPixmap()
            self._last_render_key = None
            self._image.clear()
            self._image.setFixedHeight(0)
            self._image.setVisible(False)
            self._sync_controls()
            return
        pixmap = QPixmap(str(self._page_paths[self._page_index]))
        if pixmap.isNull():
            self.set_error(f"无法读取第 {self._page_index + 1} 页图像")
            return
        self._original_pixmap = pixmap
        self._last_render_key = None
        self._image.setVisible(True)
        self._apply_pixmap()
        self._sync_controls()
        self.page_changed.emit(self._page_index, len(self._page_paths))

    def _clear_pages(self) -> None:
        self._page_paths = ()
        self._page_index = 0
        self._original_pixmap = QPixmap()
        self._last_render_key = None
        self._image.clear()
        self._image.setFixedHeight(0)
        self._image.setVisible(False)
        self._close_preview_dialog()
        self._sync_controls()

    def _apply_pixmap(self) -> None:
        if self._original_pixmap.isNull():
            return
        available_width = max(240, self.contentsRect().width() - 2)
        target_width = available_width
        render_key = (int(self._original_pixmap.cacheKey()), target_width)
        if render_key == self._last_render_key:
            return
        scaled = self._original_pixmap.scaledToWidth(
            target_width,
            Qt.SmoothTransformation,
        )
        self._last_render_key = render_key
        self._image.setPixmap(scaled)
        self._image.setFixedHeight(scaled.height())

    def _close_preview_dialog(self) -> None:
        dialog = self._preview_dialog
        self._preview_dialog = None
        if dialog is not None:
            dialog.close()

    def _clear_preview_dialog(self, *_args) -> None:
        self._preview_dialog = None

    def _apply_theme(self) -> None:
        theme = get_theme()
        from src.shared.ui.icons.catalog import get_icon

        self._previous_btn.setIcon(get_icon("chevron-left", 16, theme.icon_primary))
        self._next_btn.setIcon(get_icon("chevron-right", 16, theme.icon_primary))
        self._refresh_btn.setIcon(get_icon("refresh-ccw", 16, theme.icon_primary))
        for button in (
            self._previous_btn,
            self._next_btn,
            self._refresh_btn,
        ):
            button.setIconSize(QSize(16, 16))
        self.setStyleSheet(
            f"""
            QLabel#document_page_preview_image {{
                background: #ffffff;
                border: 1px solid {theme.border};
                border-radius: 2px;
            }}
            """
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._resize_timer.start(0)

    def _sync_controls(self) -> None:
        count = len(self._page_paths)
        current = self._page_index + 1 if count else 0
        self._page_label.setText(f"{current} / {count}")
        self._previous_btn.setEnabled(current > 1)
        self._next_btn.setEnabled(bool(count and current < count))


__all__ = ["DocumentPagePreview"]
