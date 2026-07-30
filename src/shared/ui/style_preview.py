"""
Style preview widget.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.qt_api import QColor, QFont, QFontMetricsF, QLabel, QPainter, QPen, QRectF, Qt

from src.shared.ui.style_presentation_envelope import StylePresentationEnvelope
from src.shared.ui.theme import bind_theme, get_theme


DEFAULT_SAMPLE_TEXT = "样式预览示例 AaBbCc 123"


def _envelope_preview_detail(
    presentation: StylePresentationEnvelope,
) -> str:
    detail = presentation.preview_detail()
    if (
        presentation.kind == "section_paragraph"
        and "有效样式" in presentation.summary
        and detail
        and not detail.startswith("不同：")
    ):
        return f"不同：{detail}"
    return detail


@dataclass(frozen=True, slots=True)
class StylePreviewProjection:
    """Shared compact projection for a paragraph-style preview widget."""

    sample_text: str = DEFAULT_SAMPLE_TEXT
    source_label: str = ""
    detail: str = ""
    font_cn: str = ""
    font_en: str = ""
    size_pt: float = 12.0
    bold: bool = False
    italic: bool = False
    alignment: str = "center"
    line_spacing: float = 1.5
    left_indent_pt: float = 0.0
    right_indent_pt: float = 0.0
    first_indent_pt: float = 0.0
    hanging_indent_pt: float = 0.0
    space_before_pt: float = 0.0
    space_after_pt: float = 0.0

    @classmethod
    def from_object(cls, projection) -> "StylePreviewProjection":
        """Build from a domain projection with compatible attributes."""

        if projection is None:
            return cls()
        return cls(
            sample_text=str(getattr(projection, "sample_text", "") or DEFAULT_SAMPLE_TEXT),
            source_label=str(getattr(projection, "source_label", "") or ""),
            detail=str(getattr(projection, "detail", "") or ""),
            font_cn=str(getattr(projection, "font_cn", "") or ""),
            font_en=str(getattr(projection, "font_en", "") or ""),
            size_pt=_safe_float(getattr(projection, "size_pt", 12.0), 12.0),
            bold=bool(getattr(projection, "bold", False)),
            italic=bool(getattr(projection, "italic", False)),
            alignment=str(getattr(projection, "alignment", "center") or "center"),
            line_spacing=_safe_float(
                getattr(projection, "line_spacing", None)
                if hasattr(projection, "line_spacing")
                else getattr(projection, "line_spacing_value", 1.5),
                1.5,
            ),
            left_indent_pt=_safe_float(
                getattr(projection, "left_indent_pt", 0.0),
                0.0,
            ),
            right_indent_pt=_safe_float(
                getattr(projection, "right_indent_pt", 0.0),
                0.0,
            ),
            first_indent_pt=_safe_float(
                getattr(projection, "first_indent_pt", 0.0),
                0.0,
            ),
            hanging_indent_pt=_safe_float(
                getattr(projection, "hanging_indent_pt", 0.0),
                0.0,
            ),
            space_before_pt=_safe_float(
                getattr(projection, "space_before_pt", 0.0),
                0.0,
            ),
            space_after_pt=_safe_float(
                getattr(projection, "space_after_pt", 0.0),
                0.0,
            ),
        )

    def tooltip_text(self) -> str:
        if self.source_label and self.detail:
            return f"{self.source_label}：{self.detail}"
        return self.source_label or self.detail


class StylePreview(QLabel):
    """Preview label for typography settings."""

    SAMPLE_TEXT = DEFAULT_SAMPLE_TEXT

    def __init__(self, parent=None):
        super().__init__(parent)
        self._alignment_value = "center"
        self._line_spacing = 1.5
        self._left_indent_pt = 0.0
        self._right_indent_pt = 0.0
        self._first_indent_pt = 0.0
        self._hanging_indent_pt = 0.0
        self._space_before_pt = 0.0
        self._space_after_pt = 0.0
        self.setText(self.SAMPLE_TEXT)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        self.setMinimumHeight(t.style_preview_min_height)
        self.setStyleSheet("")
        self.update()

    def update_preview(
        self,
        *,
        font_cn: str = '',
        font_en: str = '',
        size_pt: float = 12,
        bold: bool = False,
        italic: bool = False,
        alignment: str = "center",
        line_spacing: float = 1.5,
        sample_text: str = "",
        left_indent_pt: float = 0.0,
        right_indent_pt: float = 0.0,
        first_indent_pt: float = 0.0,
        hanging_indent_pt: float = 0.0,
        space_before_pt: float = 0.0,
        space_after_pt: float = 0.0,
    ):
        self.setText(sample_text or self.SAMPLE_TEXT)
        alignment_value = str(alignment or "center").strip().lower()
        self._alignment_value = alignment_value
        self._line_spacing = _safe_float(line_spacing, 1.5)
        self._left_indent_pt = _safe_float(left_indent_pt, 0.0)
        self._right_indent_pt = _safe_float(right_indent_pt, 0.0)
        self._first_indent_pt = _safe_float(first_indent_pt, 0.0)
        self._hanging_indent_pt = _safe_float(hanging_indent_pt, 0.0)
        self._space_before_pt = _safe_float(space_before_pt, 0.0)
        self._space_after_pt = _safe_float(space_after_pt, 0.0)
        if alignment_value == "left":
            self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        elif alignment_value == "right":
            self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        elif alignment_value == "justify":
            self.setAlignment(Qt.AlignJustify | Qt.AlignVCenter)
        else:
            self.setAlignment(Qt.AlignCenter)
        font = QFont()
        if font_cn:
            font.setFamily(font_cn)
        elif font_en:
            font.setFamily(font_en)
        font.setPointSizeF(size_pt)
        font.setBold(bold)
        font.setItalic(italic)
        self.setFont(font)
        self.update()

    def apply_projection(
        self,
        projection: StylePreviewProjection | None,
        *,
        empty_text: str = DEFAULT_SAMPLE_TEXT,
    ) -> None:
        if projection is None:
            self.setText(empty_text)
            self.setEnabled(False)
            self.setToolTip("")
            self.setProperty("style_preview_source_label", "")
            self.setProperty("style_preview_detail", "")
            return

        self.setEnabled(True)
        self.update_preview(
            font_cn=projection.font_cn,
            font_en=projection.font_en,
            size_pt=projection.size_pt,
            bold=projection.bold,
            italic=projection.italic,
            alignment=projection.alignment,
            line_spacing=projection.line_spacing,
            sample_text=projection.sample_text,
            left_indent_pt=projection.left_indent_pt,
            right_indent_pt=projection.right_indent_pt,
            first_indent_pt=projection.first_indent_pt,
            hanging_indent_pt=projection.hanging_indent_pt,
            space_before_pt=projection.space_before_pt,
            space_after_pt=projection.space_after_pt,
        )
        self.setToolTip(projection.tooltip_text())
        self.setProperty("style_preview_source_label", projection.source_label)
        self.setProperty("style_preview_detail", projection.detail)

    def apply_envelope(
        self,
        envelope: StylePresentationEnvelope | object | None,
        projection: StylePreviewProjection | object | None = None,
        *,
        empty_text: str = DEFAULT_SAMPLE_TEXT,
    ) -> None:
        presentation = StylePresentationEnvelope.from_object(envelope)
        if projection is None and presentation.is_empty():
            self.apply_projection(None, empty_text=empty_text)
            self.setProperty("style_presentation_kind", "")
            self.setProperty("style_presentation_title", "")
            self.setProperty("style_presentation_variant_key", "")
            self.setProperty("style_presentation_source_label", "")
            self.setProperty("style_presentation_summary", "")
            self.setProperty("style_presentation_detail", "")
            self.setProperty("style_presentation_action_label", "")
            return

        preview_projection = (
            StylePreviewProjection.from_object(projection)
            if projection is not None
            else StylePreviewProjection(
                sample_text=presentation.preview_sample_text(fallback=empty_text),
                source_label=presentation.preview_source_label(),
                detail=_envelope_preview_detail(presentation),
            )
        )
        self.apply_projection(preview_projection, empty_text=empty_text)
        self.setToolTip(presentation.tooltip_text())
        self.setProperty("style_presentation_kind", presentation.kind)
        self.setProperty("style_presentation_title", presentation.display_title())
        self.setProperty(
            "style_presentation_variant_key",
            str(getattr(projection, "variant_key", "") or ""),
        )
        self.setProperty("style_presentation_source_label", presentation.source_label)
        self.setProperty("style_presentation_summary", presentation.summary)
        self.setProperty("style_presentation_detail", presentation.detail)
        self.setProperty("style_presentation_action_label", presentation.action_label)

    def paintEvent(self, event) -> None:
        t = get_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(0.5, 0.5, float(self.width()) - 1.0, float(self.height()) - 1.0)
        painter.setPen(QPen(QColor(t.border), 1))
        painter.setBrush(QColor(t.bg_input))
        painter.drawRoundedRect(rect, float(t.radius_sm), float(t.radius_sm))

        painter.setFont(self.font())
        text_color = QColor(t.text_primary if self.isEnabled() else t.text_hint)
        painter.setPen(text_color)

        padding = float(t.style_preview_padding)
        content = rect.adjusted(padding, padding, -padding, -padding)
        lines = _preview_lines(self.text())
        metrics = QFontMetricsF(self.font())
        line_height = self._preview_line_height(metrics)
        y = content.top() + _pt_to_px(self._space_before_pt) + metrics.ascent()
        max_bottom = content.bottom() - _pt_to_px(self._space_after_pt)

        for index, line in enumerate(lines):
            if y - metrics.ascent() > max_bottom:
                break
            first_line = index == 0
            line_rect = self._line_rect(content, first_line=first_line)
            if line_rect.width() <= 4:
                continue
            text = metrics.elidedText(line, Qt.ElideRight, int(line_rect.width()))
            x = self._text_x(metrics, line_rect, text)
            painter.drawText(float(x), float(y), text)
            y += line_height

    def _line_rect(self, content: QRectF, *, first_line: bool) -> QRectF:
        left = content.left() + _pt_to_px(self._left_indent_pt)
        right = content.right() - _pt_to_px(self._right_indent_pt)
        if first_line:
            left += _pt_to_px(self._first_indent_pt)
        elif self._hanging_indent_pt > 0:
            left += _pt_to_px(self._hanging_indent_pt)
        if right <= left:
            right = left + 1
        return QRectF(left, content.top(), right - left, content.height())

    def _text_x(self, metrics: QFontMetricsF, line_rect: QRectF, text: str) -> float:
        text_width = metrics.horizontalAdvance(text)
        if self._alignment_value == "right":
            return line_rect.right() - text_width
        if self._alignment_value == "center":
            return line_rect.left() + max(0.0, (line_rect.width() - text_width) / 2.0)
        return line_rect.left()

    def _preview_line_height(self, metrics: QFontMetricsF) -> float:
        raw = max(0.0, float(self._line_spacing))
        if raw <= 0:
            return metrics.height()
        if raw <= 5:
            return max(metrics.height(), metrics.height() * raw)
        return max(metrics.height(), _pt_to_px(raw))


def _pt_to_px(value: float) -> float:
    return max(0.0, float(value or 0.0) * 96.0 / 72.0)


def _safe_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _preview_lines(text: str) -> list[str]:
    cleaned = " ".join(str(text or DEFAULT_SAMPLE_TEXT).strip().split())
    if "：" in cleaned:
        head, tail = cleaned.split("：", 1)
        return [head, tail] if tail else [head]
    if ":" in cleaned:
        head, tail = cleaned.split(":", 1)
        return [head, tail] if tail else [head]
    return [cleaned]


__all__ = ["DEFAULT_SAMPLE_TEXT", "StylePreview", "StylePreviewProjection"]
