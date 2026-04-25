from __future__ import annotations

from pathlib import Path

from src.qt_api import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
    QColor,
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.rounded_surface import RoundedSurfaceFrame
from src.shared.ui.theme import bind_theme, get_theme


class QuickExecutionDropArea(RoundedSurfaceFrame):
    """Three-state document picker used by quick execution."""

    file_selected = Signal(str)
    file_cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(70)
        self.setAutoFillBackground(False)
        self.setObjectName("wb_v2_drop_area")
        self._file_path = ""
        self._hovering = False

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(1, 1, 1, 1)
        self._layout.setSpacing(0)

        self._idle_container = QWidget(self)
        self._idle_container.setObjectName("wb_v2_drop_idle")
        idle_layout = QHBoxLayout(self._idle_container)
        idle_layout.setContentsMargins(16, 16, 16, 16)
        idle_layout.setSpacing(8)

        self._idle_icon = QLabel("W", self._idle_container)
        self._idle_icon.setFixedSize(36, 36)
        self._idle_icon.setAlignment(Qt.AlignCenter)
        self._idle_icon.setObjectName("wb_v2_drop_idle_icon")
        idle_layout.addWidget(self._idle_icon)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        self._hint_title = QLabel(self._idle_container)
        self._hint_title.setObjectName("wb_v2_drop_title")

        self._hint_label = QLabel("或点击右侧按钮从本地选择", self._idle_container)
        self._hint_label.setObjectName("wb_v2_drop_hint")

        text_col.addWidget(self._hint_title)
        text_col.addWidget(self._hint_label)
        idle_layout.addLayout(text_col, 1)

        self._browse_btn = QPushButton("浏览选择", self._idle_container)
        self._browse_btn.setCursor(Qt.PointingHandCursor)
        self._browse_btn.setObjectName("wb_v2_drop_browse")
        self._browse_btn.clicked.connect(self._pick_file)
        idle_layout.addWidget(self._browse_btn, 0, Qt.AlignVCenter)

        self._selected_container = QWidget(self)
        selected_layout = QHBoxLayout(self._selected_container)
        selected_layout.setContentsMargins(16, 16, 16, 16)
        selected_layout.setSpacing(8)

        self._file_icon = QLabel("W", self._selected_container)
        self._file_icon.setFixedSize(36, 36)
        self._file_icon.setAlignment(Qt.AlignCenter)
        self._file_name_label = QLabel("", self._selected_container)
        self._file_name_label.setObjectName("wb_v2_drop_filename")
        self._file_path_label = QLabel("", self._selected_container)
        self._file_path_label.setObjectName("wb_v2_drop_filepath")
        self._file_path_label.setWordWrap(False)

        name_col = QVBoxLayout()
        name_col.setContentsMargins(0, 0, 0, 0)
        name_col.setSpacing(2)
        name_col.addWidget(self._file_name_label)
        name_col.addWidget(self._file_path_label)

        self._change_btn = QPushButton("浏览选择", self._selected_container)
        self._change_btn.setCursor(Qt.PointingHandCursor)
        self._change_btn.setObjectName("wb_v2_drop_change")
        self._change_btn.clicked.connect(self._pick_file)

        self._clear_btn = QPushButton("✕", self._selected_container)
        self._clear_btn.setFixedSize(28, 28)
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.setObjectName("wb_v2_drop_clear")
        self._clear_btn.clicked.connect(self.clear)

        selected_layout.addWidget(self._file_icon)
        selected_layout.addLayout(name_col, 1)
        selected_layout.addWidget(self._clear_btn)
        selected_layout.addWidget(self._change_btn)

        self._selected_container.hide()

        self._layout.addWidget(self._idle_container)
        self._layout.addWidget(self._selected_container)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(".docx"):
                    event.acceptProposedAction()
                    self._hovering = True
                    self._refresh_style()
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._hovering = False
        self._refresh_style()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._hovering = False
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".docx"):
                self.set_file(path)
                return
        self._refresh_style()

    def file_path(self) -> str:
        return self._file_path

    def set_file(self, path: str) -> None:
        self._file_path = str(path or "")
        file_path = Path(self._file_path)
        metrics = self._file_name_label.fontMetrics()
        max_width = max(200, self.width() - 120)

        file_name = file_path.name
        self._file_name_label.setText(metrics.elidedText(file_name, Qt.ElideMiddle, max_width))
        self._file_name_label.setToolTip(file_name)

        parent_str = str(file_path.parent)
        self._file_path_label.setText(metrics.elidedText(parent_str, Qt.ElideMiddle, max_width))
        self._file_path_label.setToolTip(parent_str)

        self._idle_container.hide()
        self._selected_container.show()
        self._refresh_style()
        self.file_selected.emit(self._file_path)

    def clear(self) -> None:
        self._file_path = ""
        self._selected_container.hide()
        self._idle_container.show()
        self._refresh_style()
        self.file_cleared.emit()

    def _apply_theme(self) -> None:
        from src.ui.icons.catalog import get_icon

        theme = get_theme()
        primary = QColor(theme.primary)
        border_inset = int(max(1, theme.border_width_md))
        self._layout.setContentsMargins(border_inset, border_inset, border_inset, border_inset)

        hint_icon_bg = f"rgba({primary.red()}, {primary.green()}, {primary.blue()}, 0.06)"
        self._idle_icon.setStyleSheet(
            f"font-size: 16px; color: {theme.text_hint}; font-weight: bold; "
            f"background: {hint_icon_bg}; border-radius: 6px;"
        )

        self._hint_title.setStyleSheet(
            f"font-size: {theme.font_size_md}px; font-weight: {theme.font_weight_emphasis}; "
            f"color: {theme.text_primary}; background: transparent;"
        )
        self._hint_label.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {theme.text_hint}; background: transparent;"
        )
        apply_button_variant(self._browse_btn, "secondary")

        self._file_icon.setStyleSheet(
            f"font-size: 16px; color: #ffffff; font-weight: bold; "
            f"background: {theme.primary}; border-radius: 6px;"
        )
        self._file_name_label.setStyleSheet(
            f"font-size: {theme.font_size_md}px; font-weight: {theme.font_weight_emphasis}; "
            f"color: {theme.text_primary}; background: transparent;"
        )
        self._file_path_label.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {theme.text_hint}; background: transparent;"
        )
        apply_button_variant(self._change_btn, "secondary")
        self._clear_btn.setStyleSheet(
            f"""
            QPushButton#wb_v2_drop_clear {{
                background: transparent;
                border: none;
                color: {theme.text_hint};
                font-size: 14px;
                border-radius: 14px;
            }}
            QPushButton#wb_v2_drop_clear:hover {{
                background: {theme.bg_hover};
                color: {theme.text_primary};
            }}
            """
        )
        self._refresh_style()

    @staticmethod
    def _build_title_text(title: str, suffix: str = "") -> str:
        return f"{title}（{suffix}）" if suffix else title

    def _refresh_style(self) -> None:
        theme = get_theme()
        primary = QColor(theme.primary)

        if self._file_path:
            file_bg = QColor(primary)
            file_bg.setAlphaF(0.02)
            surface_bg = file_bg.name(QColor.HexArgb)
            border_color = theme.primary
        elif self._hovering:
            hover_bg = QColor(primary)
            hover_bg.setAlphaF(0.06)
            surface_bg = hover_bg.name(QColor.HexArgb)
            border_color = theme.primary
            self._hint_title.setText(self._build_title_text("松开以加载文件"))
            self._hint_label.setText("文件将被立即载入")
        else:
            surface_bg = theme.bg_card
            border_color = theme.border
            self._hint_title.setText(
                self._build_title_text("拖拽文件至此处", "支持格式：.docx")
            )
            self._hint_label.setText("或点击右侧按钮从本地选择")

        self.configure_surface(
            background=surface_bg,
            radius=theme.radius_sm,
            border_color=border_color,
            border_width=1.0,
        )
        self.update()

    def _pick_file(self) -> None:
        file_path, _selected = QFileDialog.getOpenFileName(
            self,
            "选择文档",
            "",
            "Word Documents (*.docx);;All Files (*)",
        )
        cleaned = str(file_path or "").strip()
        if cleaned:
            self.set_file(cleaned)


__all__ = ["QuickExecutionDropArea"]
