"""
Shared search input widget.

Single formal implementation for:
- search icon
- separator
- inline clear button
- debounced search_changed signal
- search_submitted signal
- theme refresh
"""

from __future__ import annotations

from src.qt_api import QEvent, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTimer, QWidget, Signal, Qt

from src.shared.ui.sizing import apply_size_class
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.icons.catalog import get_icon


class SearchInput(QWidget):
    search_changed = Signal(str)
    search_submitted = Signal(str)

    DEBOUNCE_MS = 300

    def __init__(self, placeholder: str = "搜索…", parent=None):
        super().__init__(parent)

        self.setObjectName(self.__class__.__name__)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFocusProxy(self)
        self._is_focused = False

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._emit_search)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._icon = QLabel(self)
        self._icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._icon, 0, Qt.AlignVCenter)

        self._separator = QFrame(self)
        self._separator.setFrameShape(QFrame.NoFrame)
        layout.addWidget(self._separator, 0, Qt.AlignVCenter)

        self._input = QLineEdit(self)
        self._input.setPlaceholderText(placeholder)
        self._input.textChanged.connect(self._on_text_changed)
        self._input.returnPressed.connect(self._on_submit)
        self._input.installEventFilter(self)
        layout.addWidget(self._input, 1)
        self.setFocusProxy(self._input)

        self._clear_btn = QPushButton(self)
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.clicked.connect(self.clear)
        self._clear_btn.hide()
        layout.addWidget(self._clear_btn, 0, Qt.AlignVCenter)

        apply_size_class(self, "md")

        bind_theme(self, self._apply_theme)
        self._apply_theme()

    @staticmethod
    def build_container_stylesheet(object_name: str, theme, *, focused: bool) -> str:
        border_color = theme.border_focus if focused else theme.border
        background = theme.bg_window if focused else theme.bg_input
        return f"""
            #{object_name} {{
                background: {background};
                border: 1px solid {border_color};
                border-radius: {theme.input_radius}px;
            }}
        """

    @staticmethod
    def build_input_stylesheet(theme) -> str:
        return f"""
            QLineEdit {{
                border: none;
                background: transparent;
                color: {theme.text_primary};
                font-size: {theme.font_size_md}px;
                padding: {theme.input_padding_y}px 0;
                selection-background-color: {theme.primary};
                selection-color: {theme.text_on_primary};
            }}
            QLineEdit::placeholder {{
                color: {theme.text_hint};
            }}
        """

    @staticmethod
    def build_clear_button_stylesheet(theme) -> str:
        return f"""
            QPushButton {{
                border: none;
                background: transparent;
            }}
            QPushButton:hover {{
                background: {theme.bg_hover};
                border-radius: {theme.input_radius}px;
            }}
        """

    @staticmethod
    def build_separator_stylesheet(theme, *, focused: bool) -> str:
        color = theme.primary if focused else theme.border
        return f"background: {color};"

    def eventFilter(self, obj, event):
        if obj is self._input:
            if event.type() == QEvent.FocusIn:
                self._is_focused = True
                self._apply_theme()
            elif event.type() == QEvent.FocusOut:
                self._is_focused = False
                self._apply_theme()
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        self._input.setFocus()
        super().mousePressEvent(event)

    def focusInEvent(self, event):
        self._input.setFocus()
        super().focusInEvent(event)

    def _apply_theme(self) -> None:
        theme = get_theme()
        layout = self.layout()
        layout.setContentsMargins(theme.input_padding_x, 0, theme.input_padding_x // 2, 0)
        layout.setSpacing(theme.spacing_xs)

        self._icon.setFixedSize(theme.input_clear_button_size, theme.input_clear_button_size)
        self._icon.setPixmap(
            get_icon("search", theme.input_icon_size, theme.primary if self._is_focused else theme.icon_secondary)
            .pixmap(theme.input_icon_size, theme.input_icon_size)
        )

        self._separator.setFixedSize(theme.input_separator_width, theme.input_separator_height)
        self._separator.setStyleSheet(self.build_separator_stylesheet(theme, focused=self._is_focused))

        self._input.setStyleSheet(self.build_input_stylesheet(theme))

        self._clear_btn.setFixedSize(theme.input_clear_button_size, theme.input_clear_button_size)
        self._clear_btn.setIcon(get_icon("x", theme.input_icon_size, theme.text_hint))
        self._clear_btn.setStyleSheet(self.build_clear_button_stylesheet(theme))

        self.setStyleSheet(
            self.build_container_stylesheet(self.objectName(), theme, focused=self._is_focused)
        )

    @property
    def text(self) -> str:
        return self._input.text()

    def set_text(self, text: str) -> None:
        self._input.setText(text)

    def set_placeholder_text(self, text: str) -> None:
        self._input.setPlaceholderText(text)

    def line_edit(self) -> QLineEdit:
        return self._input

    def clear(self) -> None:
        self._input.clear()

    def _on_text_changed(self, text: str) -> None:
        self._clear_btn.setVisible(bool(text))
        self._timer.start(self.DEBOUNCE_MS)

    def _on_submit(self) -> None:
        self._timer.stop()
        self.search_submitted.emit(self._input.text())

    def _emit_search(self) -> None:
        self.search_changed.emit(self._input.text())
