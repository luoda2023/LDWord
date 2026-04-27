"""
Shared feature toggle row primitive.
"""

from __future__ import annotations

from src.qt_api import QCheckBox, QHBoxLayout, QPushButton, QWidget, Signal, Qt

from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.selection_control_style import build_checkbox_stylesheet
from src.shared.ui.theme import bind_theme, get_theme


class FeatureToggleRow(QWidget):
    """Toggle + config action row for optional module features."""

    toggled = Signal(bool)
    config_clicked = Signal()

    def __init__(self, label: str, *, checked: bool = False, parent=None):
        super().__init__(parent)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._toggle = QCheckBox(label, self)
        self._toggle.setChecked(bool(checked))
        self._toggle.toggled.connect(self._on_toggled)
        self._layout.addWidget(self._toggle, 1, Qt.AlignVCenter)

        self._config_button = QPushButton("配置", self)
        self._config_button.setCursor(Qt.PointingHandCursor)
        apply_button_variant(self._config_button, "secondary")
        self._config_button.clicked.connect(self.config_clicked.emit)
        self._layout.addWidget(self._config_button, 0, Qt.AlignVCenter)

        self._config_button.setEnabled(self._toggle.isChecked())

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._layout.setSpacing(t.spacing_sm)
        self._toggle.setStyleSheet(build_checkbox_stylesheet(t))
        # Compact link-style config button (no border, small)
        self._config_button.setStyleSheet(
            f"QPushButton {{ font-size: {t.font_size_sm}px; color: {t.primary}; "
            f"border: none; background: transparent; padding: 2px 6px; }}"
            f"QPushButton:hover {{ text-decoration: underline; }}"
            f"QPushButton:disabled {{ color: {t.text_hint}; }}"
        )
        self._config_button.setMinimumHeight(0)
        self._config_button.setMinimumHeight(24)
        self._config_button.setMaximumHeight(24)

    def _on_toggled(self, checked: bool) -> None:
        self._config_button.setEnabled(bool(checked))
        self.toggled.emit(bool(checked))

    def set_checked(self, checked: bool) -> None:
        self._toggle.setChecked(bool(checked))

    def is_checked(self) -> bool:
        return self._toggle.isChecked()

    def config_button(self) -> QPushButton:
        return self._config_button

