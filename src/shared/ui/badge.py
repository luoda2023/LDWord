"""Shared badge primitive."""

from __future__ import annotations

from src.qt_api import QLabel, QVBoxLayout, QWidget, Qt

from src.shared.ui.theme import bind_theme, get_theme


class Badge(QWidget):
    """Compact capsule text badge."""

    def __init__(self, text: str = "", *, parent=None):
        super().__init__(parent)
        self._text = text
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel(text)
        self._label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._label)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._label.setStyleSheet(
            f"""
            background: {t.bg_selected};
            color: {t.text_secondary};
            border: 1px solid {t.border_light};
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
