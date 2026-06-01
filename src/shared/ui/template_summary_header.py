"""Header primitive for template detail summary cards."""

from __future__ import annotations

from src.qt_api import QHBoxLayout, QLabel, QSizePolicy, QWidget, Qt
from src.shared.ui.theme import bind_theme, get_theme


class TemplateSummaryHeader(QWidget):
    """Large title row used by the first summary card in template details."""

    ICON_SIZE = 28
    TITLE_FONT_SIZE = 20
    ICON_TITLE_GAP = 10
    TITLE_CONTROL_GAP = 12
    ACTION_GAP = 12
    BOTTOM_MARGIN = 14

    def __init__(self, title: str, icon_name: str, *, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._controls: list[QWidget] = []
        self._actions: list[QWidget] = []

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, self.BOTTOM_MARGIN)
        self._layout.setSpacing(0)

        self._icon = QLabel(self)
        self._icon.setFixedSize(self.ICON_SIZE, self.ICON_SIZE)
        self._icon.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._layout.addWidget(self._icon, 0, Qt.AlignVCenter)

        self._layout.addSpacing(self.ICON_TITLE_GAP)

        self._title = QLabel(title, self)
        self._title.setObjectName("tpl_summary_header_title")
        self._title.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self._layout.addWidget(self._title, 0, Qt.AlignVCenter)

        self._layout.addSpacing(self.TITLE_CONTROL_GAP)
        self._control_insert_index = self._layout.count()
        self._layout.addStretch(1)

        self._actions_layout = QHBoxLayout()
        self._actions_layout.setContentsMargins(0, 0, 0, 0)
        self._actions_layout.setSpacing(self.ACTION_GAP)
        self._layout.addLayout(self._actions_layout)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    @property
    def title_label(self) -> QLabel:
        return self._title

    @property
    def icon_label(self) -> QLabel:
        return self._icon

    def add_control(self, widget: QWidget) -> None:
        self._controls.append(widget)
        self._layout.insertWidget(self._control_insert_index, widget, 0, Qt.AlignVCenter)
        self._control_insert_index += 1
        self._layout.insertSpacing(self._control_insert_index, self.TITLE_CONTROL_GAP)
        self._control_insert_index += 1

    def add_action(self, widget: QWidget) -> None:
        self._actions.append(widget)
        self._actions_layout.addWidget(widget, 0, Qt.AlignVCenter)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._title.setStyleSheet(
            f"font-size: {self.TITLE_FONT_SIZE}px; "
            f"font-weight: {theme.font_weight_emphasis}; "
            f"color: {theme.primary}; "
            f"background: transparent;"
        )
        try:
            from src.ui.icons.catalog import get_icon

            self._icon.setPixmap(
                get_icon(self._icon_name, self.ICON_SIZE, theme.primary).pixmap(
                    self.ICON_SIZE, self.ICON_SIZE
                )
            )
        except Exception:
            self._icon.clear()


__all__ = ["TemplateSummaryHeader"]
