"""
Collapsible section widget.
"""

from __future__ import annotations

from src.qt_api import QSizePolicy, QToolButton, QVBoxLayout, QWidget, Qt

from src.shared.ui.layout_sync import refresh_layout_chain, refresh_layout_chain_later, updates_suspended
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.icons.catalog import get_icon


class CollapsibleSection(QWidget):
    """Collapsible panel with a themed header button."""

    def __init__(self, title: str = '', *, expanded: bool = False, parent=None):
        super().__init__(parent)
        self._expanded = expanded
        self._title = title

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._toggle_btn = QToolButton()
        self._toggle_btn.setText(f' {title}')
        self._toggle_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._toggle_btn.setArrowType(Qt.NoArrow)
        self._toggle_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(expanded)
        self._toggle_btn.clicked.connect(self._on_toggle)
        self._layout.addWidget(self._toggle_btn)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._layout.addWidget(self._content)

        if not expanded:
            self._content.setMaximumHeight(0)
            self._content.setVisible(False)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._content_layout.setContentsMargins(t.collapsible_content_indent, t.collapsible_content_padding_y, 0, t.collapsible_content_padding_y)
        self._content_layout.setSpacing(t.spacing_xs)
        self._toggle_btn.setStyleSheet(
            f"""
            QToolButton {{
                border: none;
                background: {t.bg_window};
                border-radius: {t.radius_sm}px;
                font-size: {t.font_size_md}px;
                font-weight: bold;
                padding-left: {t.collapsible_toggle_padding_x}px;
                text-align: left;
                color: {t.text_primary};
                min-height: {t.collapsible_toggle_height}px;
                max-height: {t.collapsible_toggle_height}px;
            }}
            QToolButton:hover {{
                background: {t.bg_hover};
            }}
            """
        )
        self._update_icon()

    def _update_icon(self) -> None:
        t = get_theme()
        icon_name = 'chevron-down' if self._expanded else 'chevron-right'
        self._toggle_btn.setIcon(get_icon(icon_name, 16, t.text_primary))

    def add_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def _on_toggle(self, checked: bool) -> None:
        self._expanded = checked
        with updates_suspended(self, self._content):
            self._update_icon()
            if checked:
                self._content.setVisible(True)
                self._content.setMaximumHeight(16777215)
            else:
                self._content.setMaximumHeight(0)
                self._content.setVisible(False)
            refresh_layout_chain(self)
        refresh_layout_chain_later(self)

    @property
    def is_expanded(self) -> bool:
        return self._expanded
