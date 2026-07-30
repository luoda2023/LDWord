"""Shared restore/save actions for editable detail-card headers."""

from __future__ import annotations

from src.qt_api import QHBoxLayout, QPushButton, QSize, QWidget, Signal, Qt
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.sizing import resolved_control_height
from src.shared.ui.template_summary_card import apply_detail_summary_action_button
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.icons.catalog import get_icon


class PersistenceActions(QWidget):
    """One top-level restore/save control with shared visuals and state."""

    restore_requested = Signal()
    save_requested = Signal()

    def __init__(
        self,
        *,
        object_name_prefix: str = "persistence",
        compact: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._compact = bool(compact)
        self.setObjectName(f"{object_name_prefix}_actions")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.restore_button = QPushButton("恢复", self)
        self.restore_button.setObjectName(f"{object_name_prefix}_restore_btn")
        self.restore_button.setCursor(Qt.PointingHandCursor)
        self.restore_button.setIconSize(QSize(16, 16))
        self.restore_button.clicked.connect(self.restore_requested.emit)
        layout.addWidget(self.restore_button)

        self.save_button = QPushButton("保存", self)
        self.save_button.setObjectName(f"{object_name_prefix}_save_btn")
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.setIconSize(QSize(16, 16))
        self.save_button.clicked.connect(self.save_requested.emit)
        layout.addWidget(self.save_button)

        self.set_states(restore_enabled=False, save_enabled=False)
        bind_theme(self, self.apply_theme)

    def set_states(self, *, restore_enabled: bool, save_enabled: bool) -> None:
        self.restore_button.setEnabled(bool(restore_enabled))
        self.save_button.setEnabled(bool(save_enabled))
        self.apply_theme()

    def apply_theme(self) -> None:
        theme = get_theme()
        if self._compact:
            height = resolved_control_height(theme, "md")
            for button, variant in (
                (self.restore_button, "ghost-primary"),
                (self.save_button, "primary"),
            ):
                button.setFixedHeight(height)
                button.setStyleSheet(
                    build_button_stylesheet(
                        theme,
                        min_height=height,
                        padding_x=12,
                        padding_y=2,
                        font_size=theme.font_size_sm,
                    )
                )
                apply_button_variant(button, variant)
        else:
            apply_detail_summary_action_button(self.restore_button, "ghost-primary")
            apply_detail_summary_action_button(self.save_button, "primary")
        restore_color = (
            theme.primary if self.restore_button.isEnabled() else theme.text_disabled
        )
        save_color = (
            theme.text_on_primary if self.save_button.isEnabled() else theme.text_disabled
        )
        self.restore_button.setIcon(get_icon("refresh-ccw", 16, restore_color))
        self.save_button.setIcon(get_icon("save", 16, save_color))


__all__ = ["PersistenceActions"]
