"""Readonly style-source receipt row for execution results."""

from __future__ import annotations

from src.qt_api import QLabel, QHBoxLayout, QSizePolicy, QWidget, Qt
from src.shared.ui.style_presentation_envelope import StylePresentationEnvelope
from src.shared.ui.theme import bind_theme, get_theme


class StyleResultReceiptRow(QWidget):
    """Show the effective style source used by an execution result."""

    def __init__(
        self,
        parent=None,
        *,
        object_name_prefix: str = "style_result_receipt",
    ) -> None:
        super().__init__(parent)
        prefix = str(object_name_prefix or "style_result_receipt").strip()
        self._icon_name = "type-outline"
        self._default_title = "样式来源"
        self._summary_text = ""
        self.setObjectName(f"{prefix}_row")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        self._icon = QLabel(self)
        self._icon.setFixedSize(18, 18)
        layout.addWidget(self._icon, 0, Qt.AlignTop)

        self._label = QLabel(self._default_title, self)
        self._label.setObjectName(f"{prefix}_label")
        layout.addWidget(self._label, 0, Qt.AlignTop)

        self._detail = QLabel("", self)
        self._detail.setObjectName(f"{prefix}_detail")
        self._detail.setWordWrap(True)
        layout.addWidget(self._detail, 1)

        self.setVisible(False)
        bind_theme(self, self.apply_theme)
        self.apply_theme()

    @property
    def label(self) -> QLabel:
        return self._label

    @property
    def detail(self) -> QLabel:
        return self._detail

    def set_summary(self, text: str) -> None:
        summary = " ".join(str(text or "").split())
        self.apply_envelope(
            StylePresentationEnvelope.from_summary(
                summary,
                kind="execution_receipt",
                title=self._default_title,
            )
        )
        if summary and not _has_leading_title(summary, self._default_title):
            self._summary_text = summary
            self.setToolTip(summary)

    def apply_envelope(self, envelope: StylePresentationEnvelope | object | None) -> None:
        presentation = StylePresentationEnvelope.from_object(
            envelope,
            kind="execution_receipt",
            title=self._default_title,
        )
        summary = presentation.receipt_summary(title_fallback=self._default_title)
        title = presentation.display_title(self._default_title) if summary else self._default_title
        detail = presentation.display_detail(title_fallback=title)

        self._label.setText(title)
        self._summary_text = summary
        self._detail.setText(detail)
        self.setToolTip(summary)
        self.setProperty("style_presentation_kind", presentation.kind if summary else "")
        self.setProperty("style_presentation_title", title if summary else "")
        self.setVisible(bool(summary))

    def summary_text(self) -> str:
        return self._summary_text

    def apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"QWidget#{self.objectName()} {{ "
            f"background: {theme.info_bg}; "
            f"border: 1px solid {theme.border_light}; "
            f"border-radius: {theme.radius_sm}px; }}"
        )
        self._label.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; "
            f"font-weight: {theme.font_weight_emphasis}; "
            f"color: {theme.primary}; background: transparent;"
        )
        self._detail.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; "
            f"color: {theme.text_secondary}; background: transparent;"
        )
        try:
            from src.shared.ui.icons.catalog import get_icon

            self._icon.setPixmap(
                get_icon(self._icon_name, size=16, color=theme.primary).pixmap(16, 16)
            )
            self._icon.setText("")
        except Exception:
            self._icon.setText("•")


def _has_leading_title(text: str, title: str) -> bool:
    value = str(text or "").strip()
    for prefix in (f"{title}：", f"{title}:"):
        if value.startswith(prefix):
            return True
    return False


__all__ = ["StyleResultReceiptRow"]
