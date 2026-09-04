"""Shared badge primitive."""

from __future__ import annotations

from src.qt_api import QLabel, QVBoxLayout, QWidget, Qt

from src.shared.ui.theme import bind_theme, get_theme, theme_rgba


class Badge(QWidget):
    """Compact capsule text badge with optional on-primary mode."""

    def __init__(self, text: str = "", variant: str = "neutral", *, parent=None):
        super().__init__(parent)
        self._text = text
        self._variant = variant
        self._on_primary = False  # True when displayed on primary-colored bg
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel(text)
        self._label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._label)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        if self._on_primary:
            bg = theme_rgba(t.text_on_primary, 0.20)
            fg = t.text_on_primary
        else:
            variant_colors = {
                "neutral": (t.bg_hover, t.text_hint),
                "info": (t.info_bg, t.info),
                "success": (t.success_bg, t.success),
                "warning": (t.warning_bg, t.warning),
                "error": (t.error_bg, t.error),
                "danger": (t.error_bg, t.error),
            }
            bg, fg = variant_colors.get(self._variant, variant_colors["neutral"])
        self._label.setStyleSheet(
            f"""
            background: {bg};
            color: {fg};
            border: none;
            border-radius: {t.radius_sm}px;
            padding: 1px 8px;
            font-size: {max(t.font_size_sm - 1, 11)}px;
            font-weight: {t.font_weight_medium};
            """
        )
        self._label.setMinimumHeight(max(16, t.spacing_md + 2))
        self.setVisible(bool(self._text))

    def set_text(self, text: str) -> None:
        self._text = text
        self._label.setText(text)
        self.setVisible(bool(text))

    def text(self) -> str:
        return self._text

    def set_variant(self, variant: str) -> None:
        self._variant = variant
        self._apply_theme()

    def variant(self) -> str:
        return self._variant

    def set_on_primary(self, on_primary: bool) -> None:
        """Switch to on-primary mode (white text on blue card)."""
        if self._on_primary != on_primary:
            self._on_primary = on_primary
            self._apply_theme()
