"""Usage guide widgets for the About page.

Presents the two real LDWord workflows in human terms:

* Layout workflow  (workbench/scene/template/assets)
* AI long-document workflow (assistant chat)

Each step row may optionally emit a jump request to open the owning panel.
"""

from __future__ import annotations

from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.design_system_card import DesignSystemCard
from src.shared.ui.icons.catalog import get_icon
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.typography_policy import TextRole, apply_text_role


class GuideStepRow(QWidget):
    """One numbered step inside a guide flow card."""

    jumped = Signal(int)  # index of the step

    def __init__(
        self,
        *,
        index: int,
        title: str,
        detail: str,
        panel_label: str = "",
        panel_index: int = -1,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._step_index = int(index)
        self._panel_index = int(panel_index)
        self.setObjectName("usage_guide_step")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 10, 10)
        row.setSpacing(12)

        self._badge = QLabel(f"{self._step_index}", self)
        self._badge.setObjectName("usage_guide_step_badge")
        self._badge.setFixedSize(26, 26)
        self._badge.setAlignment(Qt.AlignCenter)
        row.addWidget(self._badge, 0, Qt.AlignTop)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(3)
        self._title = QLabel(title, self)
        self._title.setObjectName("usage_guide_step_title")
        apply_text_role(self._title, TextRole.NAVIGATION_TITLE_ACTIVE)
        text.addWidget(self._title)
        self._detail = QLabel(detail, self)
        self._detail.setObjectName("usage_guide_step_detail")
        self._detail.setWordWrap(True)
        self._detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        apply_text_role(self._detail, TextRole.BODY)
        text.addWidget(self._detail)
        row.addLayout(text, 1)

        if str(panel_label or "").strip() and self._panel_index >= 0:
            self._button = QPushButton(panel_label, self)
            self._button.setObjectName("usage_guide_step_action")
            self._button.setCursor(Qt.PointingHandCursor)
            apply_button_variant(self._button, "secondary")
            apply_size_class(self._button, "sm")
            self._button.clicked.connect(self._emit_jump)
            row.addWidget(self._button, 0, Qt.AlignVCenter)

        bind_theme(self, self._apply_theme)
        self._apply_theme()

    def _emit_jump(self) -> None:
        self.jumped.emit(self._panel_index)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QWidget#usage_guide_step {{
                background: {theme.bg_window};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_md}px;
            }}
            QLabel#usage_guide_step_badge {{
                background: {theme.primary};
                color: {theme.text_on_primary};
                border: none;
                border-radius: {theme.radius_sm}px;
                font-size: {theme.font_size_sm}px;
                font-weight: {theme.font_weight_bold};
            }}
            QLabel#usage_guide_step_title {{
                color: {theme.text_primary};
                background: transparent;
            }}
            QLabel#usage_guide_step_detail {{
                color: {theme.text_secondary};
                background: transparent;
            }}
            """
        )


class GuideFlowCard(DesignSystemCard):
    """A titled block that groups GuideStepRow entries under one flow."""

    panel_jumped = Signal(int)

    def __init__(
        self,
        title: str,
        description: str,
        *,
        icon_name: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent=parent)
        self.set_header(title, icon_name=icon_name or "book-open")
        if str(description or "").strip():
            self.set_description(str(description).strip())
        self._step_rows: list[GuideStepRow] = []

    def add_step(
        self,
        *,
        index: int,
        title: str,
        detail: str,
        panel_label: str = "",
        panel_index: int = -1,
    ) -> None:
        row = GuideStepRow(
            index=index,
            title=title,
            detail=detail,
            panel_label=panel_label,
            panel_index=panel_index,
            parent=self,
        )
        row.jumped.connect(self.panel_jumped.emit)
        self._step_rows.append(row)
        self.add_widget(row)


__all__ = ["GuideFlowCard", "GuideStepRow"]
