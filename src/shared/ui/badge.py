"""Shared badge primitive."""

from __future__ import annotations

from src.qt_api import QLabel, QVBoxLayout, QWidget, Qt

from src.shared.ui.theme import bind_theme, get_theme


class Badge(QWidget):
    """Compact capsule text badge."""

    def __init__(self, text: str = "", variant: str = "neutral", *, parent=None):
        super().__init__(parent)
        self._text = text
        self._variant = variant
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel(text)
        self._label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._label)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        variant_colors = {
            "neutral": (t.bg_selected, t.text_secondary, t.border_light),
            "info": (t.primary_light, t.primary, t.primary),
            "success": (t.success_bg, t.success, t.success),
            "warning": (t.warning_bg, t.warning, t.warning),
            "error": (t.error_bg, t.error, t.error),
            "danger": (t.error_bg, t.error, t.error),
        }
        bg, fg, border = variant_colors.get(self._variant, variant_colors["neutral"])
        self._label.setStyleSheet(
            f"""
            background: {bg};
            color: {fg};
            border: 1px solid {border};
            border-radius: {t.radius_full}px;
            padding: 0 {t.spacing_sm}px;
            """
        )
        self._label.setMinimumHeight(max(18, t.spacing_lg + 2))
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
