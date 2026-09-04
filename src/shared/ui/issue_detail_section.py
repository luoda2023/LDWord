"""Reusable title/body section for compact issue detail panes."""

from __future__ import annotations

from src.qt_api import QLabel, QVBoxLayout, QWidget

from src.shared.ui.theme import bind_theme, get_theme


class IssueDetailSection(QWidget):
    """Small themed section with one label-like title and one body label."""

    def __init__(
        self,
        title: str = "",
        body: str = "",
        *,
        tone: str = "neutral",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._tone = str(tone or "neutral").strip() or "neutral"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self.title_label = QLabel(title, self)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.body_label = QLabel(body, self)
        self.body_label.setWordWrap(True)
        layout.addWidget(self.body_label)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_title(self, text: str) -> None:
        self.title_label.setText(str(text or ""))

    def set_body(self, text: str) -> None:
        self.body_label.setText(str(text or ""))

    def set_tone(self, tone: str) -> None:
        normalized = str(tone or "neutral").strip() or "neutral"
        if normalized == self._tone:
            return
        self._tone = normalized
        self._apply_theme()

    def tone(self) -> str:
        return self._tone

    def _apply_theme(self) -> None:
        t = get_theme()
        body_color = {
            "error": t.error,
            "warning": t.warning,
            "info": t.primary,
            "success": t.success,
            "primary": t.primary,
            "neutral": t.text_secondary,
        }.get(self._tone, t.text_secondary)
        self.title_label.setStyleSheet(
            f"font-size: {t.font_size_xs}px;"
            f"font-weight: {t.font_weight_emphasis};"
            f"color: {t.text_primary};"
            "background: transparent;"
        )
        self.body_label.setStyleSheet(
            f"font-size: {t.font_size_sm}px;"
            f"color: {body_color};"
            "background: transparent;"
        )


__all__ = ["IssueDetailSection"]
