"""Shared zoomable preview framework for raster images and rendered widgets."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from src.qt_api import (
    QApplication,
    QColor,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPixmap,
    QPoint,
    QPushButton,
    QSize,
    QSplitter,
    Qt,
    QTextEdit,
    QTimer,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.ui.bounded_raster import (
    DEFAULT_PREVIEW_PIXEL_BUDGET,
    load_bounded_raster,
)
from src.shared.ui.icons.catalog import get_icon
from src.shared.ui.interactive_preview_scroll_area import InteractivePreviewScrollArea
from src.shared.ui.rounded_surface import RoundedSurfaceFrame
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.typography_policy import TextRole, font_for_role

_SCREEN_COVERAGE = 0.9
_DIALOG_MARGIN = 12
_TOOL_BUTTON_SIZE = 34
_MIN_DIALOG_SIZE = 480
_ZOOM_STEP_BASE = 1.15
_ACTUAL_SIZE_ZOOM = 1.0
_ACTUAL_SNAP_RELEASE_DELTA = 120


class PreviewContent:
    """Content adapter consumed by :class:`ZoomablePreviewViewport`."""

    def __init__(self, widget: QWidget, natural_size: QSize) -> None:
        self.widget = widget
        self._natural_size = QSize(natural_size)

    @property
    def natural_size(self) -> QSize:
        return QSize(self._natural_size)

    def render(self, zoom: float) -> QSize:
        raise NotImplementedError


class PixmapPreviewContent(PreviewContent):
    """Smooth raster-image content with one retained original pixmap."""

    def __init__(self, pixmap: QPixmap, *, parent=None) -> None:
        self._pixmap = QPixmap(pixmap)
        label = QLabel(parent)
        label.setObjectName("shared_preview_pixmap")
        label.setAlignment(Qt.AlignCenter)
        label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        super().__init__(label, self._pixmap.size())
        self._sync_transparency_background()
        self.render(1.0)

    @property
    def pixmap(self) -> QPixmap:
        return QPixmap(self._pixmap)

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self._pixmap = QPixmap(pixmap)
        self._natural_size = self._pixmap.size()
        self._sync_transparency_background()

    def _sync_transparency_background(self) -> None:
        # Material images such as signatures and seals are commonly transparent
        # and are ultimately placed on white document pages.  Showing their alpha
        # channel directly over a dark preview canvas can make black artwork
        # disappear, so use a paper-white backing only when alpha is present.
        background = "#FFFFFF" if self._pixmap.hasAlphaChannel() else "transparent"
        self.widget.setStyleSheet(
            f"background: {background}; border: none;"
        )

    def render(self, zoom: float) -> QSize:
        if self._pixmap.isNull():
            self.widget.clear()
            self.widget.resize(1, 1)
            return QSize(1, 1)
        size = QSize(
            max(1, round(self._pixmap.width() * zoom)),
            max(1, round(self._pixmap.height() * zoom)),
        )
        scaled = (
            self._pixmap
            if size == self._pixmap.size()
            else self._pixmap.scaled(
                size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
        self.widget.setPixmap(scaled)
        self.widget.resize(scaled.size())
        return scaled.size()


class WidgetPreviewContent(PreviewContent):
    """Zoom a vector/custom QWidget while preserving its height-for-width contract."""

    def __init__(self, widget: QWidget, natural_size: QSize) -> None:
        # A full-screen preview renderer is display-only.  Let pointer input
        # reach the scroll-area viewport so dragging the visible page pans it
        # just like dragging a raster image.
        widget.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        super().__init__(widget, natural_size)

    def render(self, zoom: float) -> QSize:
        width = max(1, round(self._natural_size.width() * zoom))
        height = (
            max(1, self.widget.heightForWidth(width))
            if self.widget.hasHeightForWidth()
            else max(1, round(self._natural_size.height() * zoom))
        )
        size = QSize(width, height)
        self.widget.setFixedSize(size)
        return size


class ZoomablePreviewViewport(QWidget):
    """One reusable fit/actual/custom zoom viewport with pointer-centered zoom."""

    zoom_changed = Signal(float, str)

    def __init__(
        self,
        content: PreviewContent,
        *,
        min_zoom: float = 0.1,
        max_zoom: float = 8.0,
        allow_fit_upscale: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("shared_preview_viewport")
        self._content = content
        self._min_zoom = max(0.01, float(min_zoom))
        self._max_zoom = max(self._min_zoom, float(max_zoom))
        self._allow_fit_upscale = bool(allow_fit_upscale)
        self._zoom = 1.0
        self._mode = "actual"
        self._rendered_size = QSize()
        self._actual_snap_direction = 0
        self._actual_snap_accumulated_delta = 0
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self.fit_to_window)
        self._anchor_timer = QTimer(self)
        self._anchor_timer.setSingleShot(True)
        self._anchor_timer.timeout.connect(self._restore_pending_anchor)
        self._pending_anchor: tuple[float, float, QPoint] | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.scroll = InteractivePreviewScrollArea(self)
        self.scroll.setObjectName("shared_preview_scroll")
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignCenter)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setWidget(content.widget)
        self.scroll.wheel_zoom_requested.connect(self.zoom_at_pointer)
        self.scroll.double_clicked.connect(self.toggle_fit_actual)
        layout.addWidget(self.scroll)
        self._apply_zoom(1.0, mode="actual")

    @property
    def content(self) -> PreviewContent:
        return self._content

    @property
    def zoom(self) -> float:
        return self._zoom

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def rendered_size(self) -> QSize:
        return QSize(self._rendered_size)

    def replace_content(self, content: PreviewContent, *, fit: bool = True) -> None:
        self._reset_actual_size_snap()
        previous = self.scroll.takeWidget()
        if previous is not None and previous is not content.widget:
            previous.hide()
            previous.setParent(None)
            previous.deleteLater()
        self._content = content
        self.scroll.setWidget(content.widget)
        if fit:
            self.schedule_fit()
        else:
            self._apply_zoom(self._zoom, mode=self._mode)

    def schedule_fit(self) -> None:
        self._fit_timer.start(0)

    def zoom_by(self, factor: float) -> None:
        self._reset_actual_size_snap()
        target = self._zoom * float(factor)
        if self._crosses_actual_size(target):
            self._apply_zoom(_ACTUAL_SIZE_ZOOM, mode="actual")
            return
        self._apply_zoom(target, mode="custom")

    def set_zoom(
        self,
        zoom: float,
        *,
        anchor: QPoint | None = None,
        mode: str = "custom",
    ) -> None:
        self._reset_actual_size_snap()
        self._apply_zoom(zoom, anchor=anchor, mode=mode)

    def actual_size(self) -> None:
        self._reset_actual_size_snap()
        self._apply_zoom(_ACTUAL_SIZE_ZOOM, mode="actual")

    def toggle_fit_actual(self) -> None:
        if self._mode == "fit":
            self.actual_size()
        else:
            self.fit_to_window()

    def fit_to_window(self) -> None:
        self._reset_actual_size_snap()
        natural = self._content.natural_size
        viewport = self.scroll.viewport().size()
        if natural.isEmpty() or viewport.width() <= 1 or viewport.height() <= 1:
            return
        zoom = min(
            max(1, viewport.width() - 20) / max(1, natural.width()),
            max(1, viewport.height() - 20) / max(1, natural.height()),
        )
        if not self._allow_fit_upscale:
            zoom = min(1.0, zoom)
        self._apply_zoom(zoom, mode="fit")

    def zoom_at_pointer(self, delta: int, position) -> None:
        if not delta:
            return
        direction = 1 if delta > 0 else -1
        if self._actual_snap_direction:
            if direction != self._actual_snap_direction:
                self._reset_actual_size_snap()
            else:
                self._actual_snap_accumulated_delta += abs(int(delta))
                if (
                    self._actual_snap_accumulated_delta
                    <= _ACTUAL_SNAP_RELEASE_DELTA
                ):
                    return
                delta = direction * (
                    self._actual_snap_accumulated_delta
                    - _ACTUAL_SNAP_RELEASE_DELTA
                )
                self._reset_actual_size_snap()

        steps = float(delta) / 120.0
        target = self._zoom * (_ZOOM_STEP_BASE**steps)
        anchor = QPoint(position)
        if self._crosses_actual_size(target):
            self._apply_zoom(_ACTUAL_SIZE_ZOOM, anchor=anchor, mode="actual")
            self._actual_snap_direction = direction
            self._actual_snap_accumulated_delta = 0
            return
        self._apply_zoom(target, anchor=anchor, mode="custom")

    def _crosses_actual_size(self, target: float) -> bool:
        return (
            self._zoom < _ACTUAL_SIZE_ZOOM <= float(target)
            or self._zoom > _ACTUAL_SIZE_ZOOM >= float(target)
        )

    def _reset_actual_size_snap(self) -> None:
        self._actual_snap_direction = 0
        self._actual_snap_accumulated_delta = 0

    def current_region(self) -> dict[str, object]:
        natural = self._content.natural_size
        viewport = self.scroll.viewport().size()
        zoom = max(self._zoom, 0.0001)
        x = round(self.scroll.horizontalScrollBar().value() / zoom)
        y = round(self.scroll.verticalScrollBar().value() / zoom)
        width = round(viewport.width() / zoom)
        height = round(viewport.height() / zoom)
        if natural.width() > 0:
            x = min(max(0, x), max(0, natural.width() - 1))
            width = max(1, min(width, natural.width() - x))
        if natural.height() > 0:
            y = min(max(0, y), max(0, natural.height() - 1))
            height = max(1, min(height, natural.height() - y))
        return {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "zoom": round(self._zoom, 4),
            "mode": self._mode,
            "image_width": natural.width(),
            "image_height": natural.height(),
        }

    def _apply_zoom(
        self,
        zoom: float,
        *,
        anchor: QPoint | None = None,
        mode: str,
    ) -> None:
        resolved = min(self._max_zoom, max(self._min_zoom, float(zoom)))
        viewport_size = self.scroll.viewport().size()
        old_size = self._content.widget.size()
        anchor = QPoint(anchor) if anchor is not None else QPoint(
            max(0, viewport_size.width() // 2),
            max(0, viewport_size.height() // 2),
        )
        old_offset_x = max(0.0, (viewport_size.width() - old_size.width()) / 2.0)
        old_offset_y = max(0.0, (viewport_size.height() - old_size.height()) / 2.0)
        hbar = self.scroll.horizontalScrollBar()
        vbar = self.scroll.verticalScrollBar()
        relative_x = (
            hbar.value() + anchor.x() - old_offset_x
        ) / max(1, old_size.width())
        relative_y = (
            vbar.value() + anchor.y() - old_offset_y
        ) / max(1, old_size.height())
        relative_x = min(1.0, max(0.0, relative_x))
        relative_y = min(1.0, max(0.0, relative_y))

        self._zoom = resolved
        self._mode = str(mode or "custom")
        self._rendered_size = self._content.render(resolved)
        self.scroll.set_pan_enabled(
            self._rendered_size.width() > viewport_size.width()
            or self._rendered_size.height() > viewport_size.height()
        )
        self._pending_anchor = (relative_x, relative_y, QPoint(anchor))
        self._anchor_timer.start(0)
        self.zoom_changed.emit(self._zoom, self._mode)

    def _restore_pending_anchor(self) -> None:
        pending = self._pending_anchor
        self._pending_anchor = None
        if pending is not None:
            self._restore_anchor(*pending)

    def _restore_anchor(self, relative_x: float, relative_y: float, anchor: QPoint) -> None:
        viewport_size = self.scroll.viewport().size()
        size = self._content.widget.size()
        offset_x = max(0.0, (viewport_size.width() - size.width()) / 2.0)
        offset_y = max(0.0, (viewport_size.height() - size.height()) / 2.0)
        self.scroll.horizontalScrollBar().setValue(
            round(relative_x * size.width() - anchor.x() + offset_x)
        )
        self.scroll.verticalScrollBar().setValue(
            round(relative_y * size.height() - anchor.y() + offset_y)
        )

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if self._mode == "fit":
            self._fit_timer.start(0)


class _PreviewHeader(QWidget):
    """Dedicated drag handle for the frameless preview window."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._fallback_drag_offset: QPoint | None = None
        self._native_move_active = False

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        self._begin_window_drag(event.globalPosition().toPoint())
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if (
            self._fallback_drag_offset is not None
            and not self._native_move_active
            and event.buttons() & Qt.LeftButton
        ):
            self._continue_window_drag(event.globalPosition().toPoint())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.LeftButton and self._fallback_drag_offset is not None:
            self._end_window_drag()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _begin_window_drag(
        self,
        global_position: QPoint,
        *,
        use_native_move: bool = True,
    ) -> None:
        window = self.window()
        self._fallback_drag_offset = (
            QPoint(global_position) - window.frameGeometry().topLeft()
        )
        handle = window.windowHandle()
        self._native_move_active = bool(
            use_native_move
            and handle is not None
            and hasattr(handle, "startSystemMove")
            and handle.startSystemMove()
        )

    def _continue_window_drag(self, global_position: QPoint) -> None:
        if self._fallback_drag_offset is not None and not self._native_move_active:
            self.window().move(
                QPoint(global_position) - self._fallback_drag_offset
            )

    def _end_window_drag(self) -> None:
        self._fallback_drag_offset = None
        self._native_move_active = False


class PreviewShellDialog(QDialog):
    """Shared frameless shell for visual previews and long-form readers."""

    def __init__(
        self,
        *,
        title: str = "预览",
        subtitle: str = "",
        preferred_size: QSize | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("shared_preview_dialog")
        self.setProperty("previewShell", True)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setWindowModality(Qt.WindowModal)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._surface = RoundedSurfaceFrame(parent=self)
        self._surface.setObjectName("shared_preview_surface")
        root.addWidget(self._surface)

        self._surface_layout = QVBoxLayout(self._surface)
        self._surface_layout.setContentsMargins(
            _DIALOG_MARGIN,
            _DIALOG_MARGIN,
            _DIALOG_MARGIN,
            _DIALOG_MARGIN,
        )
        self._surface_layout.setSpacing(10)
        self._header = _PreviewHeader(self._surface)
        self._header.setObjectName("shared_preview_header")
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(4, 0, 0, 0)
        header_layout.setSpacing(8)
        title_column = QWidget(self._header)
        title_column.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        title_layout = QVBoxLayout(title_column)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(1)
        self._title_label = QLabel(title, title_column)
        self._title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._title_label.setObjectName("shared_preview_title")
        self._subtitle_label = QLabel(subtitle, title_column)
        self._subtitle_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._subtitle_label.setObjectName("shared_preview_subtitle")
        self._subtitle_label.setVisible(bool(subtitle))
        title_layout.addWidget(self._title_label)
        title_layout.addWidget(self._subtitle_label)
        header_layout.addWidget(title_column, 1)

        self._toolbar = QWidget(self._header)
        self._toolbar.setObjectName("shared_preview_toolbar")
        self._toolbar_layout = QHBoxLayout(self._toolbar)
        self._toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self._toolbar_layout.setSpacing(6)
        header_layout.addWidget(self._toolbar, 0)
        self._close_btn = self.add_toolbar_action(
            "x",
            "关闭（Esc）",
            self.close,
            danger=True,
        )
        self._surface_layout.addWidget(self._header, 0)

        self._resize_to_screen(preferred_size or QSize(900, 700), parent)
        bind_theme(self, self._apply_theme)

    def set_title_text(self, title: str, subtitle: str = "") -> None:
        self._title_label.setText(str(title or "预览"))
        self._subtitle_label.setText(str(subtitle or ""))
        self._subtitle_label.setVisible(bool(subtitle))
        self.setWindowTitle(str(title or "预览"))

    def add_toolbar_action(
        self,
        icon_name: str,
        tooltip: str,
        callback,
        *,
        danger: bool = False,
    ) -> QPushButton:
        button = QPushButton("", self._toolbar)
        button.setFixedSize(_TOOL_BUTTON_SIZE, _TOOL_BUTTON_SIZE)
        button.setProperty("previewIcon", icon_name)
        button.setProperty("previewDanger", bool(danger))
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(callback)
        close_button = getattr(self, "_close_btn", None)
        if close_button is not None:
            close_index = self._toolbar_layout.indexOf(close_button)
            self._toolbar_layout.insertWidget(max(0, close_index), button)
        else:
            self._toolbar_layout.addWidget(button)
        return button

    def add_toolbar_widget(self, widget: QWidget) -> None:
        close_button = getattr(self, "_close_btn", None)
        close_index = (
            self._toolbar_layout.indexOf(close_button)
            if close_button is not None
            else self._toolbar_layout.count()
        )
        self._toolbar_layout.insertWidget(max(0, close_index), widget)

    def _resize_to_screen(self, requested: QSize, parent) -> None:
        screen = parent.screen() if parent is not None else QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        available_size = available.size() if available is not None else QSize(1280, 820)
        max_width = max(1, round(available_size.width() * _SCREEN_COVERAGE))
        max_height = max(1, round(available_size.height() * _SCREEN_COVERAGE))
        width = min(max_width, max(_MIN_DIALOG_SIZE, requested.width()))
        height = min(max_height, max(_MIN_DIALOG_SIZE, requested.height()))
        self.setMinimumSize(min(_MIN_DIALOG_SIZE, width), min(_MIN_DIALOG_SIZE, height))
        self.resize(width, height)
        if available is not None:
            self.move(
                available.x() + (available.width() - width) // 2,
                available.y() + (available.height() - height) // 2,
            )

    def _apply_shell_theme(self, extra_stylesheet: str = "") -> None:
        theme = get_theme()
        self._surface.configure_surface(
            background=theme.bg_window,
            radius=theme.shell_radius,
            border_color=theme.border,
            border_width=1.0,
        )
        for button in self.findChildren(QPushButton):
            icon_name = str(button.property("previewIcon") or "")
            if icon_name:
                color = (
                    theme.error
                    if button.property("previewDanger")
                    else theme.icon_primary
                )
                button.setIcon(get_icon(icon_name, 17, color))
                button.setIconSize(QSize(17, 17))
        self.setStyleSheet(
            f"""
            QDialog[previewShell="true"] {{
                background: transparent;
                border: none;
            }}
            QWidget#shared_preview_header {{
                background: {theme.bg_card};
                border: none;
                border-radius: {theme.radius_md}px;
            }}
            QLabel#shared_preview_title {{
                color: {theme.text_primary};
                font-size: {theme.font_size_lg}px;
                font-weight: 700;
            }}
            QLabel#shared_preview_subtitle,
            QLabel#shared_preview_status {{
                color: {theme.text_secondary};
                font-size: {theme.font_size_sm}px;
            }}
            QPushButton[previewIcon] {{
                background: {theme.bg_input};
                border: 1px solid {theme.border};
                border-radius: {theme.button_radius}px;
                padding: 0;
            }}
            QPushButton[previewIcon]:hover {{
                background: {theme.bg_hover};
                border-color: {theme.border_focus};
            }}
            QPushButton[previewDanger="true"]:hover {{
                background: {theme.error_bg};
                border-color: {theme.error};
            }}
            {extra_stylesheet}
            """
        )

    def _apply_theme(self) -> None:
        self._apply_shell_theme()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)


class TextPreviewDialog(PreviewShellDialog):
    """Preview-shell reader for selectable, scrollable long-form text."""

    def __init__(
        self,
        text: str,
        *,
        title: str = "文本预览",
        subtitle: str = "",
        markdown: bool = False,
        preferred_size: QSize | None = None,
        parent=None,
    ) -> None:
        super().__init__(
            title=title,
            subtitle=subtitle,
            preferred_size=preferred_size or QSize(920, 700),
            parent=parent,
        )
        self.setObjectName("shared_text_preview_dialog")
        self.viewer = QTextEdit(self._surface)
        self.viewer.setObjectName("shared_text_preview_viewer")
        self.viewer.setReadOnly(True)
        self.viewer.setAcceptRichText(False)
        self.viewer.setUndoRedoEnabled(False)
        self.viewer.setLineWrapMode(QTextEdit.WidgetWidth)
        self.viewer.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        self.viewer.setFont(font_for_role(TextRole.BODY))
        self.viewer.document().setDefaultFont(font_for_role(TextRole.BODY))
        if markdown:
            self.viewer.setMarkdown(str(text or ""))
        else:
            self.viewer.setPlainText(str(text or ""))
        cursor = self.viewer.textCursor()
        cursor.setPosition(0)
        self.viewer.setTextCursor(cursor)
        self._surface_layout.addWidget(self.viewer, 1)
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = get_theme()
        viewer = getattr(self, "viewer", None)
        if viewer is not None:
            viewer.setFont(font_for_role(TextRole.BODY))
            viewer.document().setDefaultFont(font_for_role(TextRole.BODY))
            viewer.document().setDefaultStyleSheet(
                f"""
                body, p, li, pre, code, table, th, td {{
                    font-family: 'Microsoft YaHei', 'Microsoft YaHei UI', 'Segoe UI';
                    font-size: {theme.font_size_sm}px;
                    color: {theme.text_primary};
                }}
                h1 {{ font-size: {theme.font_size_xxl}px; }}
                h2 {{ font-size: {theme.font_size_lg}px; }}
                h3 {{ font-size: {theme.font_size_md}px; }}
                """
            )
        self._apply_shell_theme(
            f"""
            QTextEdit#shared_text_preview_viewer {{
                color: {theme.text_primary};
                background: {theme.bg_card};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_md}px;
                padding: 20px 24px;
                selection-background-color: {theme.primary_light};
                selection-color: {theme.text_primary};
            }}
            QTextEdit#shared_text_preview_viewer QScrollBar:vertical {{
                background: {theme.scrollbar_track};
                width: 10px;
                margin: 4px 2px 4px 0;
            }}
            QTextEdit#shared_text_preview_viewer QScrollBar::handle:vertical {{
                background: {theme.scrollbar_thumb};
                border-radius: 4px;
                min-height: 32px;
            }}
            QTextEdit#shared_text_preview_viewer QScrollBar::handle:vertical:hover {{
                background: {theme.scrollbar_thumb_hover};
            }}
            QTextEdit#shared_text_preview_viewer QScrollBar::add-line:vertical,
            QTextEdit#shared_text_preview_viewer QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            """
        )


class PreviewDialog(PreviewShellDialog):
    """Unified frameless visual preview with toolbar, zoom and pan."""

    def __init__(
        self,
        content: PreviewContent,
        *,
        title: str = "预览",
        subtitle: str = "",
        allow_fit_upscale: bool = False,
        min_zoom: float = 0.1,
        max_zoom: float = 8.0,
        initial_view: str = "fit",
        preferred_size: QSize | None = None,
        parent=None,
    ) -> None:
        if initial_view not in {"fit", "actual"}:
            raise ValueError("initial_view must be 'fit' or 'actual'")
        self._initial_view = initial_view
        self._initial_view_pending = True
        requested = QSize(preferred_size) if preferred_size is not None else QSize(
            content.natural_size.width() + 80,
            content.natural_size.height() + 130,
        )
        super().__init__(
            title=title,
            subtitle=subtitle,
            preferred_size=requested,
            parent=parent,
        )

        self.viewport = ZoomablePreviewViewport(
            content,
            min_zoom=min_zoom,
            max_zoom=max_zoom,
            allow_fit_upscale=allow_fit_upscale,
            parent=self,
        )
        self.viewport.zoom_changed.connect(self._sync_zoom_label)

        self._zoom_out_btn = self.add_toolbar_action(
            "minus",
            "缩小（-）",
            lambda: self.viewport.zoom_by(1 / 1.15),
        )
        self._zoom_label = QLabel("100%", self._toolbar)
        self._zoom_label.setObjectName("shared_preview_zoom_label")
        self._zoom_label.setAlignment(Qt.AlignCenter)
        self._zoom_label.setMinimumWidth(88)
        self.add_toolbar_widget(self._zoom_label)
        self._zoom_in_btn = self.add_toolbar_action(
            "plus",
            "放大（+）",
            lambda: self.viewport.zoom_by(1.15),
        )
        self._actual_btn = self.add_toolbar_action(
            "square",
            "原始尺寸（0）",
            self.viewport.actual_size,
        )
        self._fit_btn = self.add_toolbar_action(
            "scan",
            "适应窗口（F）",
            self.viewport.fit_to_window,
        )
        self._splitter = QSplitter(Qt.Horizontal, self)
        self._splitter.setObjectName("shared_preview_splitter")
        self._splitter.addWidget(self.viewport)
        self._splitter.setChildrenCollapsible(False)
        self._surface_layout.addWidget(self._splitter, 1)
        self._status_label = QLabel(
            "滚轮缩放 · 拖动平移 · 双击切换适应/原始尺寸",
            self._surface,
        )
        self._status_label.setObjectName("shared_preview_status")
        self._surface_layout.addWidget(self._status_label, 0)

        self._apply_theme()

    @property
    def content(self) -> PreviewContent:
        return self.viewport.content

    @property
    def zoom(self) -> float:
        return self.viewport.zoom

    def set_status_text(self, text: str) -> None:
        self._status_label.setText(str(text or ""))
        self._status_label.setVisible(bool(text))

    def add_secondary_viewport(self, viewport: ZoomablePreviewViewport) -> None:
        if self._splitter.indexOf(viewport) < 0:
            self._splitter.addWidget(viewport)
            width = max(2, self._splitter.width())
            self._splitter.setSizes([width // 2, width - width // 2])

    def _sync_zoom_label(self, zoom: float, mode: str) -> None:
        suffix = " · 适应" if mode == "fit" else " · 原始" if mode == "actual" else ""
        self._zoom_label.setText(f"{round(zoom * 100):d}%{suffix}")

    def _apply_theme(self) -> None:
        theme = get_theme()
        is_dark = QColor(theme.bg_window).lightnessF() < 0.45
        canvas_background = "#0A0D12" if is_dark else "#E4E8EE"
        self._apply_shell_theme(
            f"""
            QLabel#shared_preview_zoom_label {{
                color: {theme.text_primary};
                font-size: {theme.font_size_sm}px;
                font-weight: {theme.font_weight_emphasis};
            }}
            QSplitter#shared_preview_splitter {{
                background: {canvas_background};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_md}px;
            }}
            QSplitter#shared_preview_splitter::handle {{
                background: {theme.border};
                width: 2px;
            }}
            QWidget#shared_preview_viewport,
            QScrollArea#shared_preview_scroll,
            QScrollArea#shared_preview_scroll > QWidget > QWidget {{
                background: {canvas_background};
                border: none;
            }}
            QLabel#shared_preview_pixmap {{
                border: none;
            }}
            """
        )

    def _apply_initial_view(self) -> None:
        if not self._initial_view_pending or not self.isVisible():
            return
        self._initial_view_pending = False
        if self._initial_view == "actual":
            self.viewport.actual_size()
        else:
            self.viewport.fit_to_window()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        if self._initial_view_pending:
            # Run after the final show-time layout.  Subclasses may add toolbar
            # controls or choose a preferred size during construction.
            QTimer.singleShot(0, self._apply_initial_view)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API
        key = event.key()
        if key in {Qt.Key_Plus, Qt.Key_Equal}:
            self.viewport.zoom_by(1.15)
            return
        if key == Qt.Key_Minus:
            self.viewport.zoom_by(1 / 1.15)
            return
        if key in {Qt.Key_0, Qt.Key_1}:
            self.viewport.actual_size()
            return
        if key == Qt.Key_F:
            self.viewport.fit_to_window()
            return
        super().keyPressEvent(event)


@dataclass(frozen=True, slots=True)
class PreviewItem:
    path: Path
    display_name: str = ""
    label: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        *,
        display_name: str = "",
        label: str = "",
        metadata: Mapping[str, object] | None = None,
    ) -> "PreviewItem":
        return cls(
            Path(path),
            str(display_name or ""),
            str(label or ""),
            dict(metadata or {}),
        )


def load_preview_pixmap(item: PreviewItem) -> tuple[QPixmap, str, str]:
    """Load one bounded image preview with EXIF orientation and an error."""

    path = Path(item.path)
    if not path.is_file():
        return QPixmap(), "", "文件不存在"
    result = load_bounded_raster(
        path,
        max_pixels=DEFAULT_PREVIEW_PIXEL_BUDGET,
    )
    return result.pixmap, result.image_format, result.error


class ImagePreviewDialog(PreviewDialog):
    """Full-featured raster preview built on the shared preview framework."""

    item_changed = Signal(int, object)
    issue_requested = Signal(object, object)

    def __init__(
        self,
        items: Sequence[PreviewItem],
        *,
        current_index: int = 0,
        compare_items: Sequence[PreviewItem] = (),
        allow_issue_marking: bool = False,
        title: str = "图片预览",
        preferred_size: QSize | None = None,
        parent=None,
    ) -> None:
        self._items = tuple(items)
        if not self._items:
            raise ValueError("ImagePreviewDialog requires at least one item")
        self._current_index = min(max(0, int(current_index)), len(self._items) - 1)
        self._compare_items = tuple(compare_items)
        self._compare_viewport: ZoomablePreviewViewport | None = None
        self._compare_content: PixmapPreviewContent | None = None
        self._syncing_compare_zoom = False
        self._dialog_title = str(title or "图片预览")
        pixmap, image_format, error = load_preview_pixmap(self.current_item)
        content = PixmapPreviewContent(pixmap)
        super().__init__(
            content,
            title=self._dialog_title,
            subtitle=self._metadata_text(pixmap, image_format, error),
            allow_fit_upscale=False,
            min_zoom=0.1,
            max_zoom=8.0,
            initial_view="fit",
            preferred_size=preferred_size,
            parent=parent,
        )
        self.setProperty("preview_semantics", "raster_image")
        self._previous_btn = self.add_toolbar_action(
            "chevron-left",
            "上一张（←）",
            lambda: self.set_current_index(self._current_index - 1),
        )
        self._next_btn = self.add_toolbar_action(
            "chevron-right",
            "下一张（→）",
            lambda: self.set_current_index(self._current_index + 1),
        )
        self._previous_btn.setVisible(len(self._items) > 1)
        self._next_btn.setVisible(len(self._items) > 1)
        self._compare_combo: StyledComboBox | None = None
        self._compare_btn: QPushButton | None = None
        self._issue_btn: QPushButton | None = None
        if self._compare_items:
            combo = StyledComboBox(self._toolbar)
            combo.setObjectName("shared_preview_compare_combo")
            combo.setMinimumWidth(170)
            combo.setMaximumWidth(240)
            combo.set_full_width_mode(True)
            for compare_item in self._compare_items:
                combo.addItem(
                    compare_item.label
                    or compare_item.display_name
                    or compare_item.path.name
                )
            self.add_toolbar_widget(combo)
            self._compare_combo = combo
            self._compare_btn = self.add_toolbar_action(
                "copy",
                "打开对比",
                self.show_selected_comparison,
            )
            if allow_issue_marking:
                self._issue_btn = self.add_toolbar_action(
                    "circle-alert",
                    "标记当前对比问题",
                    self._emit_issue_request,
                    danger=True,
                )
        self._sync_navigation()
        if error:
            self.set_status_text(f"图片加载失败：{error}")
        else:
            self.set_status_text("滚轮缩放 · 拖动平移 · 0 原始尺寸 · F 适应窗口")

    @property
    def current_item(self) -> PreviewItem:
        return self._items[self._current_index]

    @property
    def selected_compare_item(self) -> PreviewItem | None:
        combo = self._compare_combo
        if combo is None or not self._compare_items:
            return None
        index = combo.currentIndex()
        return self._compare_items[index] if 0 <= index < len(self._compare_items) else None

    def set_current_index(self, index: int) -> None:
        resolved = min(max(0, int(index)), len(self._items) - 1)
        if resolved == self._current_index:
            return
        self._current_index = resolved
        pixmap, image_format, error = load_preview_pixmap(self.current_item)
        content = PixmapPreviewContent(pixmap)
        self.viewport.replace_content(content, fit=True)
        self.set_title_text(
            self._dialog_title,
            self._metadata_text(pixmap, image_format, error),
        )
        self.set_status_text(f"图片加载失败：{error}" if error else "滚轮缩放 · 拖动平移")
        self._sync_navigation()
        self.item_changed.emit(self._current_index, self.current_item)

    def show_selected_comparison(self) -> bool:
        item = self.selected_compare_item
        if item is None:
            return False
        pixmap, _image_format, error = load_preview_pixmap(item)
        if pixmap.isNull():
            self.set_status_text(f"对比图片加载失败：{error or '无法读取'}")
            return False
        content = PixmapPreviewContent(pixmap)
        if self._compare_viewport is None:
            viewport = ZoomablePreviewViewport(
                content,
                min_zoom=0.1,
                max_zoom=8.0,
                allow_fit_upscale=False,
                parent=self,
            )
            self._compare_viewport = viewport
            self._compare_content = content
            self.add_secondary_viewport(viewport)
            self.viewport.zoom_changed.connect(self._sync_compare_zoom)
            viewport.zoom_changed.connect(self._sync_primary_zoom)
        else:
            self._compare_content = content
            self._compare_viewport.replace_content(content, fit=False)
        self._compare_viewport.setVisible(True)
        self._compare_viewport.set_zoom(
            self.viewport.zoom,
            mode=self.viewport.mode,
        )
        self.set_status_text(
            f"正在对比：{item.display_name or item.path.name} · 缩放已同步"
        )
        return True

    def comparison_size(self) -> QSize:
        return (
            self._compare_content.natural_size
            if self._compare_content is not None
            else QSize()
        )

    def _sync_compare_zoom(self, zoom: float, mode: str) -> None:
        if self._compare_viewport is None or self._syncing_compare_zoom:
            return
        self._syncing_compare_zoom = True
        try:
            self._compare_viewport.set_zoom(zoom, mode=mode)
        finally:
            self._syncing_compare_zoom = False

    def _sync_primary_zoom(self, zoom: float, mode: str) -> None:
        if self._syncing_compare_zoom:
            return
        self._syncing_compare_zoom = True
        try:
            self.viewport.set_zoom(zoom, mode=mode)
        finally:
            self._syncing_compare_zoom = False

    def _emit_issue_request(self) -> None:
        item = self.selected_compare_item
        if item is not None:
            self.issue_requested.emit(item, self.viewport.current_region())

    def _sync_navigation(self) -> None:
        self._previous_btn.setEnabled(self._current_index > 0)
        self._next_btn.setEnabled(self._current_index + 1 < len(self._items))

    def _metadata_text(self, pixmap: QPixmap, image_format: str, error: str) -> str:
        item = self.current_item
        display = item.display_name or item.path.name
        if error:
            return f"{display} · {error}"
        size_bytes = item.path.stat().st_size if item.path.is_file() else 0
        size_text = (
            f"{size_bytes / (1024 * 1024):.1f} MB"
            if size_bytes >= 1024 * 1024
            else f"{max(1, round(size_bytes / 1024))} KB"
        )
        format_text = f" · {image_format}" if image_format else ""
        return (
            f"{display} · {pixmap.width()} × {pixmap.height()} px"
            f"{format_text} · {size_text}"
        )

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.key() == Qt.Key_Left and len(self._items) > 1:
            self.set_current_index(self._current_index - 1)
            return
        if event.key() == Qt.Key_Right and len(self._items) > 1:
            self.set_current_index(self._current_index + 1)
            return
        super().keyPressEvent(event)


__all__ = [
    "ImagePreviewDialog",
    "PixmapPreviewContent",
    "PreviewContent",
    "PreviewDialog",
    "PreviewShellDialog",
    "PreviewItem",
    "TextPreviewDialog",
    "WidgetPreviewContent",
    "ZoomablePreviewViewport",
    "load_preview_pixmap",
]
