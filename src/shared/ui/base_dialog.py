"""
Shared themed base dialog.
"""

from __future__ import annotations

from src.qt_api import (
    QDialog,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPoint,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QColor,
    QMouseEvent,
    Qt,
)

from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.dialog_style import (
    build_dialog_icon_container_stylesheet,
    build_dialog_message_stylesheet,
)
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.theme import get_theme


_ICON_MAP = {
    "info": ("info", "info"),
    "success": ("circle-check", "success"),
    "warning": ("circle-alert", "warning"),
    "error": ("circle-x", "error"),
    "question": ("circle-help", "info"),
    "input": ("pencil-line", "primary"),
}


class BaseDialog(QDialog):
    """Frameless themed dialog with shared layout and button/input helpers."""

    def __init__(
        self,
        title: str = "",
        icon_style: str = "info",
        parent=None,
        *,
        show_close: bool = True,
    ):
        super().__init__(parent)
        self._t = get_theme()
        self._drag_pos: QPoint | None = None
        self._icon_style = icon_style

        t = self._t
        self.setWindowTitle(title or "Lark Formatter")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(460)
        self.setMaximumWidth(600)

        self._content_card = QWidget(self)
        self._content_card.setObjectName("dialog_content_card")
        self._content_card.setAttribute(Qt.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        shadow_margin = t.shadow_blur_xl
        outer.setContentsMargins(shadow_margin, shadow_margin - 16, shadow_margin, shadow_margin + 10)
        outer.addWidget(self._content_card)

        self._bg_card = QWidget(self)
        self._bg_card.setObjectName("dialog_bg")
        self._bg_card.setAttribute(Qt.WA_StyledBackground, True)
        self._bg_card.show()

        shadow = QGraphicsDropShadowEffect(self._bg_card)
        shadow.setBlurRadius(t.shadow_blur_xl)
        shadow.setColor(QColor(0, 0, 0, t.shadow_color_dialog_alpha))
        shadow.setOffset(0, t.shadow_offset_y_lg)
        self._bg_card.setGraphicsEffect(shadow)

        self._bg_card.lower()
        self._content_card.raise_()

        card_layout = QVBoxLayout(self._content_card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(t.spacing_xxl, t.spacing_xxl, t.spacing_xxl, t.spacing_lg)
        top_layout.setSpacing(t.spacing_lg)

        icon_name, fg_token = _ICON_MAP.get(icon_style, ("info", "info"))
        icon_bg = getattr(t, fg_token, t.info)

        from src.ui.icons.catalog import get_icon

        icon = get_icon(icon_name, size=t.dialog_icon_size, color=t.text_on_primary)
        icon_container = QWidget()
        icon_container.setFixedSize(t.dialog_icon_container_size, t.dialog_icon_container_size)
        icon_container.setStyleSheet(build_dialog_icon_container_stylesheet(t, icon_bg))

        icon_inner = QHBoxLayout(icon_container)
        icon_inner.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(t.dialog_icon_size, t.dialog_icon_size))
        icon_label.setFixedSize(t.dialog_icon_size, t.dialog_icon_size)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_inner.addWidget(icon_label, 0, Qt.AlignCenter)
        top_layout.addWidget(icon_container)

        title_label = QLabel(title)
        title_label.setObjectName("dialog_title")
        top_layout.addWidget(title_label)
        top_layout.addStretch()

        if show_close:
            close_icon = get_icon("x", size=18, color=t.text_hint)
            close_btn = QPushButton()
            close_btn.setIcon(close_icon)
            close_btn.setObjectName("dialog_close")
            close_btn.setFixedSize(t.dialog_close_button_size, t.dialog_close_button_size)
            close_btn.setCursor(Qt.PointingHandCursor)
            close_btn.clicked.connect(self.reject)
            top_layout.addWidget(close_btn)

        card_layout.addWidget(top_bar)

        content_wrapper = QWidget()
        self.content_layout = QVBoxLayout(content_wrapper)
        self.content_layout.setContentsMargins(t.spacing_xxl, 0, t.spacing_xxl, 0)
        self.content_layout.setSpacing(t.spacing_lg)
        card_layout.addWidget(content_wrapper)

        btn_wrapper = QWidget()
        self._btn_layout = QHBoxLayout(btn_wrapper)
        self._btn_layout.setContentsMargins(t.spacing_xxl, t.spacing_lg, t.spacing_xxl, t.spacing_xxl)
        self._btn_layout.setSpacing(t.spacing_md)
        self._btn_layout.addStretch()
        card_layout.addWidget(btn_wrapper)

        self._apply_style()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_bg_card") and hasattr(self, "_content_card"):
            self._bg_card.setGeometry(self._content_card.geometry())

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None

    def add_primary_button(self, text: str, *, destructive: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setMinimumWidth(104)
        btn.setFixedHeight(self._t.control_height_md)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setDefault(True)
        apply_button_variant(btn, "danger" if destructive else "primary")
        self._btn_layout.addWidget(btn)
        return btn

    def add_secondary_button(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setMinimumWidth(104)
        btn.setFixedHeight(self._t.control_height_md)
        btn.setCursor(Qt.PointingHandCursor)
        apply_button_variant(btn, "secondary")
        self._btn_layout.addWidget(btn)
        return btn

    def add_text_input(self, *, placeholder: str = "", default: str = "") -> QLineEdit:
        line_edit = QLineEdit()
        line_edit.setText(default)
        if placeholder:
            line_edit.setPlaceholderText(placeholder)
        line_edit.setFixedHeight(self._t.control_height_md)
        line_edit.setStyleSheet(build_text_input_stylesheet(self._t))
        self.content_layout.addWidget(line_edit)
        return line_edit

    def add_message(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(build_dialog_message_stylesheet(self._t))
        self.content_layout.addWidget(label)
        return label

    def _apply_style(self):
        t = self._t
        self.setStyleSheet(
            f"""
            #dialog_bg, #dialog_content_card {{
                background: {t.bg_card};
                border: 1px solid {t.border_light};
                border-radius: {t.radius_xl}px;
            }}
            #dialog_title {{
                color: {t.text_primary};
                font-size: {t.font_size_xl}px;
                font-weight: 600;
                font-family: {t.font_family};
            }}
            #dialog_close {{
                background: transparent;
                border: none;
                border-radius: {t.radius_xl}px;
            }}
            #dialog_close:hover {{
                background: {t.bg_hover};
            }}

            {build_button_stylesheet(t, '#dialog_content_card QPushButton')}
            """
        )
