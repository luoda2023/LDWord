"""
Shared flow section container.
"""

from __future__ import annotations

from src.qt_api import QToolButton, QVBoxLayout, QWidget, Signal, Qt

from src.shared.ui.card import Card
from src.shared.ui.theme import bind_theme, get_theme


class FlowSection(Card):
    """Card-based section with a collapsible content area."""

    expanded_changed = Signal(bool)

    def __init__(self, title: str, *, expanded: bool = True, parent=None):
        super().__init__(parent=parent)
        self._expanded = bool(expanded)
        self._title = title

        self._toggle_button = QToolButton(self)
        self._toggle_button.setText(title)
        self._toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._toggle_button.setCheckable(True)
        self._toggle_button.setChecked(self._expanded)
        self._toggle_button.clicked.connect(self.set_expanded)
        super().add_widget(self._toggle_button)

        self._content = QWidget(self)
        self._inner_content_layout = QVBoxLayout(self._content)
        self._inner_content_layout.setContentsMargins(0, 0, 0, 0)
        super().add_widget(self._content)

        self.set_expanded(self._expanded)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        Card._apply_theme(self)
        if not hasattr(self, "_toggle_button") or not hasattr(self, "_inner_content_layout"):
            return
        t = get_theme()
        self._inner_content_layout.setSpacing(t.spacing_sm)
        self._toggle_button.setStyleSheet(
            f"""
            QToolButton {{
                border: none;
                background: transparent;
                font-size: {t.font_size_lg}px;
                font-weight: {t.font_weight_bold};
                color: {t.text_primary};
                text-align: left;
                padding: 0;
            }}
            """
        )
        self._toggle_button.setArrowType(Qt.DownArrow if self._expanded else Qt.RightArrow)

    def set_expanded(self, expanded: bool) -> None:
        new_state = bool(expanded)
        if new_state == self._expanded:
            return
        self._expanded = new_state
        self._toggle_button.setChecked(self._expanded)
        self._toggle_button.setArrowType(Qt.DownArrow if self._expanded else Qt.RightArrow)
        self._content.setVisible(self._expanded)
        self.expanded_changed.emit(self._expanded)

    def is_expanded(self) -> bool:
        return self._expanded

    def add_widget(self, widget: QWidget) -> None:
        self._inner_content_layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._inner_content_layout.addLayout(layout)
