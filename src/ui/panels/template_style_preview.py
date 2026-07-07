from __future__ import annotations

from dataclasses import dataclass

from src.config.heading_style_semantics import resolve_heading_style, resolve_non_numbered_heading_style
from src.config.style_semantics import (
    CM_TO_PT,
    normalize_line_spacing_type,
    resolve_spacing_render_pt,
    resolve_line_spacing_value,
)
from src.config.table_style_presets import color_palette, color_variant
from src.config.template import StyleConfig, TemplateConfig
from src.qt_api import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QGraphicsDropShadowEffect,
    QPainter,
    QPen,
    QRectF,
    QSize,
    QSizePolicy,
    Qt,
    QWidget,
)
from src.shared.ui.style_preview_utils import (
    preview_alignment_flags,
    resolve_preview_indents_pt,
    resolve_preview_size_pt,
)
from src.shared.ui.style_presentation_envelope import StylePresentationEnvelope
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.adapters.heading_numbering_adapter import HeadingNumberingAdapter
from src.ui.panels.template_format import build_template_page_presentation_envelope

@dataclass(frozen=True)
class _PreviewParagraph:
    style_key: str
    text: str


@dataclass(frozen=True, slots=True)
class _PreviewHeaderFooterState:
    header_text: str
    header_alignment: str
    header_border: bool
    footer_text: str
    footer_alignment: str


_PREVIEW_TABLE_STYLE_KEY = "table_preview"
_PREVIEW_TABLE_ROWS: tuple[tuple[str, str, str], ...] = (
    ("指标", "数值", "说明"),
    ("样本 A", "1.23", "有效"),
    ("样本 B", "2.35", "稳定"),
)


_PAPER_DIMENSIONS_CM: dict[str, tuple[float, float]] = {
    "A4": (21.0, 29.7),
    "A3": (29.7, 42.0),
    "B5": (17.6, 25.0),
    "LETTER": (21.59, 27.94),
    "LEGAL": (21.59, 35.56),
    "16K": (18.4, 26.0),
}

_PREVIEW_HEADING_TITLES = {
    1: "绪论",
    2: "研究背景",
    3: "国内外研究现状",
}

_PREVIEW_BODY_TEXT = (
    "本文示例用于预览正文样式，包括中文、English、数字 123 与括号（示例）等混排效果。"
)

_PREVIEW_BODY_TEXT_SHORT = "此段用于观察标题后的段前、段后、行距与首行缩进。"
_PREVIEW_NON_NUMBERED_TITLE = "摘要"
_PREVIEW_NON_NUMBERED_BODY = "此处用于预览非编号标题样式，不应显示标题编号。"


def _paper_dimensions_cm(paper_size: str) -> tuple[float, float]:
    return _PAPER_DIMENSIONS_CM.get(str(paper_size or "").upper(), _PAPER_DIMENSIONS_CM["A4"])


def _resolve_preview_style(cfg: TemplateConfig, style_key: str) -> StyleConfig:
    if style_key == "non_numbered_heading":
        return resolve_non_numbered_heading_style(cfg, include_body_fallback=True) or StyleConfig()
    if style_key.startswith("heading"):
        suffix = style_key.removeprefix("heading")
        level = int(suffix) if suffix.isdigit() else 1
        style = resolve_heading_style(cfg, level, include_body_fallback=True)
        return style or StyleConfig()
    direct = cfg.styles.get(style_key)
    if direct is not None:
        return direct
    return cfg.styles.get("body") or cfg.styles.get("normal") or StyleConfig()


def _roman_sample(value: int, *, lower: bool = False) -> str:
    value = max(1, min(3999, int(value or 1)))
    pairs = (
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    result = []
    for amount, glyph in pairs:
        while value >= amount:
            result.append(glyph)
            value -= amount
    text = "".join(result)
    return text.lower() if lower else text


def _page_number_preview_text(header_footer) -> str:
    if not bool(getattr(header_footer, "page_number_enabled", True)):
        return ""
    phases = list(getattr(getattr(header_footer, "page_number_plan", None), "phases", []) or [])
    visible_phases = [phase for phase in phases if bool(getattr(phase, "visible", True))]
    phase = visible_phases[0] if visible_phases else None
    number_format = str(getattr(phase, "number_format", "decimal") if phase is not None else "decimal")
    start_value = max(1, int(getattr(phase, "start_value", 1) if phase is not None else 1))
    if number_format == "upperRoman":
        sample = _roman_sample(start_value)
    elif number_format == "lowerRoman":
        sample = _roman_sample(start_value, lower=True)
    else:
        sample = str(start_value)
    return f"- {sample} -"


def _footer_preview_text(header_footer) -> str:
    if not bool(getattr(getattr(header_footer, "footer", None), "enabled", True)):
        return ""
    mode = str(getattr(getattr(header_footer, "footer", None), "content_mode", "page_number") or "page_number")
    footer_text = str(getattr(header_footer, "footer_text", "") or "").strip()
    page_number_text = _page_number_preview_text(header_footer)
    if mode == "none":
        return ""
    if mode == "fixed":
        return footer_text
    if mode == "page_number_with_text":
        return " ".join(part for part in (page_number_text, footer_text) if part)
    return page_number_text


def _preview_footer_alignment_flags(alignment: str | None):
    value = str(alignment or "center").strip().lower()
    if value == "left":
        return Qt.AlignLeft | Qt.AlignTop
    if value == "right":
        return Qt.AlignRight | Qt.AlignTop
    return Qt.AlignHCenter | Qt.AlignTop


def _preview_header_alignment_flags(alignment: str | None):
    value = str(alignment or "center").strip().lower()
    if value == "left":
        return Qt.AlignLeft | Qt.AlignBottom
    if value == "right":
        return Qt.AlignRight | Qt.AlignBottom
    return Qt.AlignHCenter | Qt.AlignBottom


def _resolve_preview_header_footer(cfg: TemplateConfig) -> _PreviewHeaderFooterState:
    header_footer = cfg.header_footer
    header_enabled = bool(getattr(getattr(header_footer, "header", None), "enabled", True))
    mode = str(getattr(header_footer, "header_mode", "styleref") or "styleref")
    if not header_enabled or mode == "none":
        header_text = ""
    elif mode == "fixed":
        header_text = str(getattr(header_footer, "header_text", "") or "").strip()
    else:
        level = max(1, int(getattr(header_footer, "styleref_level", 1) or 1))
        title = _PREVIEW_HEADING_TITLES.get(level, f"{level}级标题")
        header_text = title if level <= 1 else f"{level}级 · {title}"

    return _PreviewHeaderFooterState(
        header_text=header_text,
        header_alignment=str(getattr(header_footer, "header_alignment", "center") or "center"),
        header_border=header_enabled and bool(getattr(header_footer, "header_border", True)) and mode != "none",
        footer_text=_footer_preview_text(header_footer),
        footer_alignment=str(getattr(header_footer, "footer_alignment", "center") or "center"),
    )


def _build_preview_heading_text(adapter: HeadingNumberingAdapter, level: int, title: str) -> str:
    return adapter.preview_heading_text(level, title)


def _build_template_preview_paragraphs(cfg: TemplateConfig) -> list[_PreviewParagraph]:
    adapter = HeadingNumberingAdapter()
    adapter.set_template(cfg)

    max_levels = max(1, min(adapter.max_levels, 3))
    paragraphs: list[_PreviewParagraph] = []
    paragraphs.append(
        _PreviewParagraph(
            style_key="heading1",
            text=_build_preview_heading_text(adapter, 1, _PREVIEW_HEADING_TITLES[1]),
        )
    )
    paragraphs.append(_PreviewParagraph(style_key="body", text=_PREVIEW_BODY_TEXT))

    if max_levels >= 2:
        paragraphs.append(
            _PreviewParagraph(
                style_key="heading2",
                text=_build_preview_heading_text(adapter, 2, _PREVIEW_HEADING_TITLES[2]),
            )
        )
        paragraphs.append(_PreviewParagraph(style_key="body", text=_PREVIEW_BODY_TEXT_SHORT))

    if max_levels >= 3:
        paragraphs.append(
            _PreviewParagraph(
                style_key="heading3",
                text=_build_preview_heading_text(adapter, 3, _PREVIEW_HEADING_TITLES[3]),
            )
        )

    paragraphs.append(_PreviewParagraph(style_key=_PREVIEW_TABLE_STYLE_KEY, text=""))

    paragraphs.append(
        _PreviewParagraph(
            style_key="non_numbered_heading",
            text=_PREVIEW_NON_NUMBERED_TITLE,
        )
    )
    paragraphs.append(_PreviewParagraph(style_key="body", text=_PREVIEW_NON_NUMBERED_BODY))
    return paragraphs


def _fit_rect_with_aspect(bounds: QRectF, aspect_width: float, aspect_height: float) -> QRectF:
    if bounds.width() <= 0 or bounds.height() <= 0 or aspect_width <= 0 or aspect_height <= 0:
        return QRectF(bounds)

    scale = min(bounds.width() / aspect_width, bounds.height() / aspect_height)
    width = aspect_width * scale
    height = aspect_height * scale
    x = bounds.x() + (bounds.width() - width) / 2.0
    y = bounds.y() + (bounds.height() - height) / 2.0
    return QRectF(x, y, width, height)


def _content_rect_from_page(page_rect: QRectF, cfg: TemplateConfig) -> QRectF:
    paper_w_cm, paper_h_cm = _paper_dimensions_cm(cfg.page_setup.paper_size)
    if page_rect.width() <= 0 or page_rect.height() <= 0 or paper_w_cm <= 0 or paper_h_cm <= 0:
        return QRectF(page_rect)

    page = cfg.page_setup
    scale_x = page_rect.width() / paper_w_cm
    scale_y = page_rect.height() / paper_h_cm

    left = min(page_rect.width() * 0.45, (max(page.margin.left_cm, 0.0) + max(page.gutter_cm, 0.0)) * scale_x)
    right = min(page_rect.width() * 0.45, max(page.margin.right_cm, 0.0) * scale_x)
    top = min(page_rect.height() * 0.35, max(page.margin.top_cm, 0.0) * scale_y)
    bottom = min(page_rect.height() * 0.35, max(page.margin.bottom_cm, 0.0) * scale_y)

    content_rect = page_rect.adjusted(left, top, -right, -bottom)
    if content_rect.width() < 24 or content_rect.height() < 24:
        return page_rect.adjusted(
            page_rect.width() * 0.18,
            page_rect.height() * 0.14,
            -page_rect.width() * 0.18,
            -page_rect.height() * 0.14,
        )
    return content_rect


def _line_height_px(style: StyleConfig, font_height: float, pt_to_px: float) -> float:
    kind = normalize_line_spacing_type(style.line_spacing_type)
    if kind == "exact":
        return max(font_height + 1.0, resolve_line_spacing_value(kind, style.line_spacing_pt) * pt_to_px)
    return max(font_height + 1.0, font_height * resolve_line_spacing_value(kind, style.line_spacing_pt))


def _table_cell_alignment_flags(alignment: str | None):
    value = str(alignment or "").strip().lower()
    if value == "center":
        return Qt.AlignVCenter | Qt.AlignHCenter
    if value == "right":
        return Qt.AlignVCenter | Qt.AlignRight
    return Qt.AlignVCenter | Qt.AlignLeft


def _table_line_spacing_factor(line_spacing_mode: str | None) -> float:
    value = str(line_spacing_mode or "").strip().lower()
    if value == "one_half":
        return 1.5
    if value == "double":
        return 2.0
    return 1.0


def _table_block_x(bounds: QRectF, table_width: float, alignment: str | None, layout_mode: str | None) -> float:
    value = str(alignment or "").strip().lower()
    width = min(max(0.0, table_width), bounds.width())
    if value == "right":
        return bounds.right() - width
    if value == "center":
        return bounds.left() + (bounds.width() - width) / 2.0
    if value == "left":
        return bounds.left()

    # Preview fallback for "不调整": keep the old layout-derived visual position.
    if str(layout_mode or "").strip().lower() in {"smart", "compact"}:
        return bounds.left() + (bounds.width() - width) / 2.0
    return bounds.left()


# ═══════════════════════════════════════════════════════════════════════
#  Style Preview  (miniature page)
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class _CachedLineLayout:
    """Pre-computed layout for a single text line."""
    x: float
    y: float
    width: float
    height: float
    text: str
    font: QFont
    is_heading: bool
    style_key: str = "body"


@dataclass
class _CachedTableLayout:
    """Pre-computed layout for the sample table in the style preview."""
    rect: QRectF
    rows: tuple[tuple[str, str, str], ...]
    font: QFont
    header_font: QFont
    cell_padding: float
    table_alignment: str | None
    cell_alignment: str | None
    border_mode: str
    color_accent: str
    color_light: str
    color_soft: str
    color_header_text: str
    color_variant_key: str
    border_width: float
    outer_width: float
    header_rule_width: float
    first_row_bold: bool


@dataclass
class _CachedPageLayout:
    """Pre-computed page layout cached between refresh() and paintEvent()."""
    page_rect: QRectF
    content_rect: QRectF
    scale: float
    paragraphs: list[_PreviewParagraph]
    line_layouts: list[_CachedLineLayout]
    table_layouts: list[_CachedTableLayout]
    header_y: float
    footer_y: float


# Luminance threshold: below this, we consider the theme "dark"
_DARK_THEME_LUMINANCE_THRESHOLD = 0.45


def _is_dark_theme(theme) -> bool:
    """Check if current theme is dark based on bg_window luminance."""
    bg = theme.bg_window
    if not bg.startswith("#") or len(bg) < 7:
        return False
    r, g, b = int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return luminance < _DARK_THEME_LUMINANCE_THRESHOLD


class TemplateStylePreview(QWidget):
    """Render a single-page preview driven by the active template config.

    Design principles:
    - All decorative elements (labels, badges, shadows, crop marks) scale
      proportionally with the page via a unified ``page_scale`` factor.
    - Layout is pre-computed in ``refresh()`` and cached; ``paintEvent()``
      only performs pure drawing from the cache.
    - Margin annotations use dimension-line style (arrows + centered text)
      inside the margin bands for clear visual association.
    - Content area boundary uses crop marks (L-shaped corners) instead of
      a full dashed rectangle.
    """

    _DEFAULT_WIDTH = 760
    _SIDE_PADDING = 20.0
    _TOP_PADDING = 12.0
    _BOTTOM_PADDING = 24.0
    _PAGE_CORNER_RADIUS = 6.0
    _REFERENCE_PAGE_WIDTH = 520.0  # baseline for page_scale = 1.0
    _MIN_TEXT_PT_TO_PX = 0.62

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tpl_style_preview")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._current_cfg: TemplateConfig | None = None
        self._cached_layout: _CachedPageLayout | None = None
        self._presentation_envelope = StylePresentationEnvelope.from_template_page()

        # Shadow effect — same pattern as Card / SurfaceCard
        self._shadow = QGraphicsDropShadowEffect(self)
        self.setGraphicsEffect(self._shadow)

        self._sync_presentation_properties()
        self._sync_preview_height(self._DEFAULT_WIDTH)
        self._apply_shadow_theme()
        bind_theme(self, self._apply_theme)

    def refresh(self, cfg: TemplateConfig) -> None:
        self._current_cfg = cfg
        self._presentation_envelope = build_template_page_presentation_envelope(cfg)
        self._sync_presentation_properties()
        self._sync_preview_height(self.width() or self._DEFAULT_WIDTH)
        self._rebuild_cache()
        self.update()

    @property
    def presentation_envelope(self) -> StylePresentationEnvelope:
        return self._presentation_envelope

    def apply_presentation_envelope(
        self,
        envelope: StylePresentationEnvelope | object | None,
    ) -> None:
        self._presentation_envelope = StylePresentationEnvelope.from_object(
            envelope,
            kind="template_page",
            title="样式预览",
        )
        self._sync_presentation_properties()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        paper_w_cm, paper_h_cm = self._current_paper_dimensions()
        usable_width = max(120.0, float(width) - self._SIDE_PADDING * 2.0)
        page_height = usable_width * (paper_h_cm / paper_w_cm)
        # Extra space for QGraphicsDropShadowEffect blur + offset
        shadow_extra = 12
        return int(round(page_height + self._TOP_PADDING + self._BOTTOM_PADDING + shadow_extra))

    def sizeHint(self) -> QSize:
        return QSize(self._DEFAULT_WIDTH, self.heightForWidth(self._DEFAULT_WIDTH))

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        self._apply_shadow_theme()
        self.update()

    def _apply_shadow_theme(self) -> None:
        """Sync shadow effect with theme tokens — same as Card._apply_theme."""
        t = get_theme()
        self._shadow.setBlurRadius(t.shadow_blur_md)
        self._shadow.setColor(QColor(0, 0, 0, 15))
        self._shadow.setOffset(0, t.shadow_offset_y)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_preview_height(self.width())
        self._rebuild_cache()

    # ── Helpers ────────────────────────────────────────────────────────

    def _sync_presentation_properties(self) -> None:
        envelope = self._presentation_envelope
        self.setProperty("style_presentation_kind", envelope.kind)
        self.setProperty("style_presentation_title", envelope.title)
        self.setProperty("style_presentation_source_label", envelope.source_label)
        self.setProperty("style_presentation_summary", envelope.summary)
        self.setProperty("style_presentation_detail", envelope.detail)
        self.setProperty("style_presentation_action_label", envelope.action_label)
        self.setToolTip(envelope.tooltip_text())

    @staticmethod
    def _with_alpha(color_value: str, alpha: int) -> QColor:
        color = QColor(color_value)
        color.setAlpha(max(0, min(alpha, 255)))
        return color

    def _sync_preview_height(self, width: int) -> None:
        effective_width = max(320, int(width) if width else self._DEFAULT_WIDTH)
        desired_height = self.heightForWidth(effective_width)
        if desired_height > 0 and self.minimumHeight() != desired_height:
            self.setMinimumHeight(desired_height)
            self.updateGeometry()

    def _current_paper_dimensions(self) -> tuple[float, float]:
        if self._current_cfg is not None:
            w, h = _paper_dimensions_cm(self._current_cfg.page_setup.paper_size)
            if self._current_cfg.page_setup.orientation == "landscape":
                return (h, w)
            return (w, h)
        return _paper_dimensions_cm("A4")

    def _page_rect(self) -> QRectF:
        paper_w_cm, paper_h_cm = self._current_paper_dimensions()
        available_rect = QRectF(
            self._SIDE_PADDING,
            self._TOP_PADDING,
            max(120.0, self.width() - self._SIDE_PADDING * 2.0),
            max(120.0, self.height() - self._TOP_PADDING - self._BOTTOM_PADDING),
        )
        return _fit_rect_with_aspect(available_rect, paper_w_cm, paper_h_cm)

    def _compute_scale(self, page_rect: QRectF) -> float:
        return max(0.4, min(2.0, page_rect.width() / self._REFERENCE_PAGE_WIDTH))

    # ── Layout cache ──────────────────────────────────────────────────

    def _rebuild_cache(self) -> None:
        """Pre-compute all layout data.  Called from refresh() / resizeEvent()."""
        if self._current_cfg is None:
            self._cached_layout = None
            return

        cfg = self._current_cfg
        page_rect = self._page_rect()
        content_rect = _content_rect_from_page(page_rect, cfg)
        scale = self._compute_scale(page_rect)

        paper_w_cm, paper_h_cm = _paper_dimensions_cm(cfg.page_setup.paper_size)
        scale_y = page_rect.height() / paper_h_cm if paper_h_cm > 0 else 0.0
        header_y = page_rect.top() + max(cfg.page_setup.header_distance_cm, 0.0) * scale_y
        footer_y = page_rect.bottom() - max(cfg.page_setup.footer_distance_cm, 0.0) * scale_y

        paragraphs = _build_template_preview_paragraphs(cfg)
        line_layouts, table_layouts = self._compute_preview_content_layouts(
            page_rect, content_rect, cfg, paragraphs,
        )

        self._cached_layout = _CachedPageLayout(
            page_rect=page_rect,
            content_rect=content_rect,
            scale=scale,
            paragraphs=paragraphs,
            line_layouts=line_layouts,
            table_layouts=table_layouts,
            header_y=header_y,
            footer_y=footer_y,
        )

    def _compute_preview_content_layouts(
        self,
        page_rect: QRectF,
        content_rect: QRectF,
        cfg: TemplateConfig,
        paragraphs: list[_PreviewParagraph],
    ) -> tuple[list[_CachedLineLayout], list[_CachedTableLayout]]:
        """Pre-compute text and sample-table geometry."""
        paper_w_cm, _ = _paper_dimensions_cm(cfg.page_setup.paper_size)
        pt_to_px = page_rect.width() / (paper_w_cm * CM_TO_PT) if paper_w_cm > 0 else 1.0
        font_pt_to_px = max(pt_to_px, self._MIN_TEXT_PT_TO_PX)
        text_rect = content_rect.adjusted(4.0, 6.0, -4.0, -6.0)
        y = text_rect.y()

        result: list[_CachedLineLayout] = []
        tables: list[_CachedTableLayout] = []
        for paragraph in paragraphs:
            if paragraph.style_key == _PREVIEW_TABLE_STYLE_KEY:
                table_layout = self._compute_sample_table_layout(text_rect, cfg, y, pt_to_px)
                if table_layout is not None:
                    tables.append(table_layout)
                    y = table_layout.rect.bottom() + max(5.0, 6.0 * pt_to_px)
                if y >= text_rect.bottom():
                    break
                continue

            style = _resolve_preview_style(cfg, paragraph.style_key)

            font = QFont()
            # Use setFamilies for CJK/Latin font fallback:
            # English font first → Latin chars use font_en;
            # CJK chars fall back to font_cn automatically.
            families = [f for f in [style.font_en, style.font_cn] if f]
            if not families:
                families = [self.font().family()]
            try:
                font.setFamilies(families)
            except AttributeError:
                font.setFamily(families[-1])  # fallback for older Qt
            size_pt = resolve_preview_size_pt(style)
            font.setPixelSize(max(9, int(round(size_pt * font_pt_to_px))))
            font.setBold(bool(style.bold))
            font.setItalic(bool(style.italic))

            # Use top-level QFontMetricsF for font measurement
            metrics = QFontMetricsF(font)
            line_height = _line_height_px(style, float(metrics.height()), pt_to_px)
            y += resolve_spacing_render_pt(
                style.space_before_pt,
                getattr(style, "space_before_unit", "pt"),
                line_height_pt=line_height / max(pt_to_px, 0.0001),
            ) * pt_to_px

            indents_pt = resolve_preview_indents_pt(style, size_pt=size_pt)
            left_indent_px = indents_pt["left_pt"] * pt_to_px
            right_indent_px = indents_pt["right_pt"] * pt_to_px
            first_indent_px = indents_pt["first_pt"] * pt_to_px
            hanging_indent_px = indents_pt["hanging_pt"] * pt_to_px

            base_x = text_rect.left() + left_indent_px
            first_width = max(60.0, text_rect.right() - right_indent_px - (base_x + first_indent_px))
            regular_width = max(60.0, text_rect.right() - right_indent_px - (base_x + hanging_indent_px))
            lines = self._wrap_preview_text(metrics, paragraph.text, first_width, regular_width)

            is_heading = paragraph.style_key.startswith("heading")
            for index, line_text in enumerate(lines):
                draw_x = base_x + (first_indent_px if index == 0 else hanging_indent_px)
                draw_width = first_width if index == 0 else regular_width
                if y + line_height > text_rect.bottom():
                    break
                result.append(_CachedLineLayout(
                    x=draw_x, y=y, width=draw_width, height=line_height,
                    text=line_text, font=font, is_heading=is_heading,
                    style_key=paragraph.style_key,
                ))
                y += line_height

            y += resolve_spacing_render_pt(
                style.space_after_pt,
                getattr(style, "space_after_unit", "pt"),
                line_height_pt=line_height / max(pt_to_px, 0.0001),
            ) * pt_to_px
            if y >= text_rect.bottom():
                break

        return result, tables

    def _compute_sample_table_layout(
        self,
        text_rect: QRectF,
        cfg: TemplateConfig,
        y: float,
        pt_to_px: float,
    ) -> _CachedTableLayout | None:
        table_cfg = cfg.table
        font = QFont()
        families = [f for f in [table_cfg.font_en, table_cfg.font_cn] if f]
        if not families:
            families = [self.font().family()]
        try:
            font.setFamilies(families)
        except AttributeError:
            font.setFamily(families[-1])
        font.setPixelSize(max(7, int(round(float(table_cfg.size_pt or 10.5) * pt_to_px))))
        font.setBold(bool(getattr(table_cfg, "bold", False)))
        font.setItalic(bool(getattr(table_cfg, "italic", False)))

        border_mode = str(getattr(table_cfg, "border_mode", "") or "three_line").lower()
        palette = color_palette(getattr(table_cfg, "color_table_accent", "blue"))
        variant = color_variant(getattr(table_cfg, "color_table_variant", "header_grid"))

        header_font = QFont(font)
        header_has_fill = border_mode == "color_table" and variant.header_fill
        header_font.setBold(bool(getattr(table_cfg, "bold", False)) or bool(getattr(table_cfg, "first_row_bold", False)) or header_has_fill)

        line_spacing_factor = _table_line_spacing_factor(getattr(table_cfg, "line_spacing_mode", "single"))
        metrics = QFontMetricsF(font)
        row_h = max(float(metrics.height()) * line_spacing_factor + 8.0 * pt_to_px, 12.0)
        table_h = row_h * len(_PREVIEW_TABLE_ROWS)
        border_width = max(0.7, float(getattr(table_cfg, "border_width_pt", 0.5) or 0.5) * pt_to_px)
        outer_width = max(0.9, float(getattr(table_cfg, "three_line_header_width_pt", 1.0) or 1.0) * pt_to_px)
        header_rule_width = max(0.7, float(getattr(table_cfg, "three_line_bottom_width_pt", 0.5) or 0.5) * pt_to_px)
        stroke_inset = max(border_width, outer_width, header_rule_width) / 2.0 + 0.6
        table_bounds = text_rect.adjusted(stroke_inset, 0.0, -stroke_inset, 0.0)
        if table_bounds.width() < 80.0:
            table_bounds = QRectF(text_rect)

        layout_mode = str(getattr(table_cfg, "layout_mode", "") or "").strip().lower()
        table_w = min(table_bounds.width() * 0.82, max(180.0 * pt_to_px, table_bounds.width() * 0.58))
        if layout_mode == "full":
            table_w = table_bounds.width()
        table_alignment = getattr(table_cfg, "table_alignment", "center")
        x = _table_block_x(table_bounds, table_w, table_alignment, layout_mode)

        rect = QRectF(x, y + max(2.0, 4.0 * pt_to_px), table_w, table_h)
        if rect.bottom() > text_rect.bottom():
            return None

        return _CachedTableLayout(
            rect=rect,
            rows=_PREVIEW_TABLE_ROWS,
            font=font,
            header_font=header_font,
            cell_padding=max(4.0, 5.0 * pt_to_px),
            table_alignment=table_alignment,
            cell_alignment=getattr(table_cfg, "cell_alignment", None),
            border_mode=border_mode,
            color_accent=f"#{palette.accent}",
            color_light=f"#{palette.accent_light}",
            color_soft=f"#{palette.accent_soft}",
            color_header_text=f"#{palette.header_text}",
            color_variant_key=variant.key,
            border_width=border_width,
            outer_width=outer_width,
            header_rule_width=header_rule_width,
            first_row_bold=bool(getattr(table_cfg, "first_row_bold", False)),
        )


    # ── Drawing ───────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        layout = self._cached_layout
        if layout is None:
            return

        # Shadow is handled by QGraphicsDropShadowEffect (no manual drawing)
        self._draw_page_paper(painter, layout)
        self._draw_margin_bands(painter, layout)
        self._draw_crop_marks(painter, layout)
        self._draw_header_footer_guides(painter, layout)
        self._draw_dimension_labels(painter, layout)
        self._draw_paper_badge(painter, layout)
        self._draw_text_content(painter, layout)
        self._draw_table_content(painter, layout)

    def _draw_page_paper(self, painter: QPainter, layout: _CachedPageLayout) -> None:
        """White page rectangle with subtle border."""
        theme = get_theme()
        page_color = "#F0F1F3" if _is_dark_theme(theme) else "#FFFFFF"
        painter.setPen(QPen(self._with_alpha(theme.border, 100), 1))
        painter.setBrush(QBrush(QColor(page_color)))
        painter.drawRoundedRect(layout.page_rect, self._PAGE_CORNER_RADIUS, self._PAGE_CORNER_RADIUS)

    def _draw_margin_bands(self, painter: QPainter, layout: _CachedPageLayout) -> None:
        """Soft-colored bands indicating margin areas."""
        theme = get_theme()
        page_rect = layout.page_rect
        content_rect = layout.content_rect

        # Slightly different alphas for top/bottom vs left/right for layering
        margin_fill_tb = self._with_alpha(theme.primary, 16)
        margin_fill_lr = self._with_alpha(theme.primary, 12)

        bands = [
            (QRectF(page_rect.left(), page_rect.top(), page_rect.width(),
                    max(0.0, content_rect.top() - page_rect.top())), margin_fill_tb),
            (QRectF(page_rect.left(), content_rect.bottom(), page_rect.width(),
                    max(0.0, page_rect.bottom() - content_rect.bottom())), margin_fill_tb),
            (QRectF(page_rect.left(), content_rect.top(),
                    max(0.0, content_rect.left() - page_rect.left()), content_rect.height()), margin_fill_lr),
            (QRectF(content_rect.right(), content_rect.top(),
                    max(0.0, page_rect.right() - content_rect.right()), content_rect.height()), margin_fill_lr),
        ]
        painter.setPen(Qt.NoPen)
        for band, fill in bands:
            if band.width() > 0 and band.height() > 0:
                painter.fillRect(band, fill)

    def _draw_crop_marks(self, painter: QPainter, layout: _CachedPageLayout) -> None:
        """L-shaped corner marks at the four corners of the content area."""
        theme = get_theme()
        s = layout.scale
        mark_len = max(6, int(16 * s))
        pen = QPen(self._with_alpha(theme.text_secondary, 90), max(1, int(1 * s)))
        painter.setPen(pen)
        cr = layout.content_rect

        # Top-left
        painter.drawLine(int(cr.left()), int(cr.top()), int(cr.left() + mark_len), int(cr.top()))
        painter.drawLine(int(cr.left()), int(cr.top()), int(cr.left()), int(cr.top() + mark_len))
        # Top-right
        painter.drawLine(int(cr.right()), int(cr.top()), int(cr.right() - mark_len), int(cr.top()))
        painter.drawLine(int(cr.right()), int(cr.top()), int(cr.right()), int(cr.top() + mark_len))
        # Bottom-left
        painter.drawLine(int(cr.left()), int(cr.bottom()), int(cr.left() + mark_len), int(cr.bottom()))
        painter.drawLine(int(cr.left()), int(cr.bottom()), int(cr.left()), int(cr.bottom() - mark_len))
        # Bottom-right
        painter.drawLine(int(cr.right()), int(cr.bottom()), int(cr.right() - mark_len), int(cr.bottom()))
        painter.drawLine(int(cr.right()), int(cr.bottom()), int(cr.right()), int(cr.bottom() - mark_len))

    def _draw_header_footer_guides(self, painter: QPainter, layout: _CachedPageLayout) -> None:
        """Simulated header/footer content at the guide line positions."""
        theme = get_theme()
        s = layout.scale
        page_rect = layout.page_rect
        cr = layout.content_rect

        cfg = self._current_cfg
        if cfg is None:
            return

        preview_state = _resolve_preview_header_footer(cfg)

        # ── Header area ──
        header_font = QFont(self.font())
        paper_w_cm, _ = _paper_dimensions_cm(cfg.page_setup.paper_size)
        pt_to_px = page_rect.width() / (paper_w_cm * CM_TO_PT) if paper_w_cm > 0 else 1.0
        header_typography = getattr(getattr(cfg.header_footer, "header", None), "typography", None)
        footer_typography = getattr(getattr(cfg.header_footer, "footer", None), "typography", None)
        size_pt = float(getattr(header_typography, "size_pt", None) or 9.0)
        header_size = max(8, int(round(size_pt * pt_to_px)))
        header_font.setPixelSize(header_size)
        header_font.setBold(bool(getattr(header_typography, "bold", False)))
        header_font.setItalic(bool(getattr(header_typography, "italic", False)))
        family = str(
            getattr(header_typography, "font_cn", None)
            or getattr(header_typography, "font_en", None)
            or ""
        ).strip()
        if family:
            header_font.setFamily(family)
        footer_font = QFont(self.font())
        footer_size_pt = float(getattr(footer_typography, "size_pt", None) or size_pt)
        footer_size = max(8, int(round(footer_size_pt * pt_to_px)))
        footer_font.setPixelSize(footer_size)
        footer_font.setBold(bool(getattr(footer_typography, "bold", False)))
        footer_font.setItalic(bool(getattr(footer_typography, "italic", False)))
        footer_family = str(
            getattr(footer_typography, "font_cn", None)
            or getattr(footer_typography, "font_en", None)
            or ""
        ).strip()
        if footer_family:
            footer_font.setFamily(footer_family)
        painter.setFont(header_font)

        header_text_color = self._with_alpha(theme.text_hint, 140)
        header_line_color = self._with_alpha(theme.text_hint, 80)

        if preview_state.header_text:
            header_text_rect = QRectF(
                cr.left(), layout.header_y - header_size - 2,
                cr.width(), header_size + 2,
            )
            painter.setPen(header_text_color)
            painter.drawText(
                header_text_rect,
                _preview_header_alignment_flags(preview_state.header_alignment),
                preview_state.header_text,
            )

        if preview_state.header_border:
            painter.setPen(QPen(header_line_color, 1))
            painter.drawLine(
                int(cr.left()), int(layout.header_y),
                int(cr.right()), int(layout.header_y),
            )

        # ── Footer area ──
        if preview_state.footer_text:
            footer_text_rect = QRectF(
                cr.left(), layout.footer_y + 2,
                cr.width(), footer_size + 2,
            )
            painter.setPen(header_text_color)
            painter.setFont(footer_font)
            painter.drawText(
                footer_text_rect,
                _preview_footer_alignment_flags(preview_state.footer_alignment),
                preview_state.footer_text,
            )

        # ── Distance annotations — reuse the same dimension-line style ──
        label_font = QFont(self.font())
        label_size = max(9, int(11 * s))
        label_font.setPixelSize(label_size)
        painter.setFont(label_font)
        metrics = painter.fontMetrics()

        pen_color = self._with_alpha(theme.text_secondary, 100)
        line_pen = QPen(pen_color, 1)
        arrow_size = max(2, int(3 * s))
        text_bg = self._with_alpha(
            "#FFFFFF" if not _is_dark_theme(theme) else theme.bg_card, 200,
        )
        # x position: right side of content area, inset to avoid crop marks
        dim_x = cr.right() - max(16, int(20 * s))

        # Header distance: page_top → header_y
        h_dist = cfg.page_setup.header_distance_cm
        h_span = layout.header_y - page_rect.top()
        if h_span > arrow_size * 6:
            self._draw_v_dimension(
                painter, line_pen, pen_color, text_bg,
                page_rect.top() + arrow_size + 2, layout.header_y - 1,
                dim_x,
                f"{h_dist:g}cm", label_font, metrics, arrow_size,
            )

        # Footer distance: footer_y → page_bottom
        f_dist = cfg.page_setup.footer_distance_cm
        f_span = page_rect.bottom() - layout.footer_y
        if f_span > arrow_size * 6:
            self._draw_v_dimension(
                painter, line_pen, pen_color, text_bg,
                layout.footer_y + 1, page_rect.bottom() - arrow_size - 2,
                dim_x,
                f"{f_dist:g}cm", label_font, metrics, arrow_size,
            )

    def _draw_dimension_labels(self, painter: QPainter, layout: _CachedPageLayout) -> None:
        """Dimension-line style annotations inside each margin band."""
        cfg = self._current_cfg
        if cfg is None:
            return

        theme = get_theme()
        s = layout.scale
        page_rect = layout.page_rect
        cr = layout.content_rect

        label_font = QFont(self.font())
        label_size = max(9, int(11 * s))
        label_font.setPixelSize(label_size)
        painter.setFont(label_font)
        metrics = painter.fontMetrics()

        pen_color = self._with_alpha(theme.text_secondary, 100)
        line_pen = QPen(pen_color, 1)
        arrow_size = max(2, int(3 * s))
        text_bg = self._with_alpha(
            "#FFFFFF" if not _is_dark_theme(theme) else theme.bg_card, 200,
        )

        margin = cfg.page_setup.margin
        gutter = cfg.page_setup.gutter_cm

        # ── Left margin ──
        left_band_w = max(0.0, cr.left() - page_rect.left())
        if left_band_w > 24 * s:
            left_total = margin.left_cm + gutter
            if gutter > 0:
                label = f"{margin.left_cm:g}+{gutter:g}cm"
            else:
                label = f"{left_total:g}cm"
            self._draw_h_dimension(
                painter, line_pen, pen_color, text_bg,
                page_rect.left() + arrow_size + 2, cr.left() - arrow_size - 2,
                cr.top() + cr.height() * 0.06,
                label, label_font, metrics, arrow_size,
            )

        # ── Right margin ──
        right_band_w = max(0.0, page_rect.right() - cr.right())
        if right_band_w > 24 * s:
            label = f"{margin.right_cm:g}cm"
            self._draw_h_dimension(
                painter, line_pen, pen_color, text_bg,
                cr.right() + arrow_size + 2, page_rect.right() - arrow_size - 2,
                cr.top() + cr.height() * 0.06,
                label, label_font, metrics, arrow_size,
            )

        # ── Top margin ──
        top_band_h = max(0.0, cr.top() - page_rect.top())
        if top_band_h > 20 * s:
            label = f"{margin.top_cm:g}cm"
            self._draw_v_dimension(
                painter, line_pen, pen_color, text_bg,
                page_rect.top() + arrow_size + 2, cr.top() - arrow_size - 2,
                page_rect.left() + page_rect.width() * 0.18,
                label, label_font, metrics, arrow_size,
            )

        # ── Bottom margin ──
        bottom_band_h = max(0.0, page_rect.bottom() - cr.bottom())
        if bottom_band_h > 20 * s:
            label = f"{margin.bottom_cm:g}cm"
            self._draw_v_dimension(
                painter, line_pen, pen_color, text_bg,
                cr.bottom() + arrow_size + 2, page_rect.bottom() - arrow_size - 2,
                page_rect.left() + page_rect.width() * 0.18,
                label, label_font, metrics, arrow_size,
            )

    def _draw_h_dimension(
        self, painter: QPainter,
        line_pen: QPen, text_color: QColor, text_bg: QColor,
        x1: float, x2: float, y_center: float,
        label: str, font: QFont, metrics, arrow_size: int,
    ) -> None:
        """Horizontal dimension line with centered label."""
        painter.setPen(line_pen)
        painter.setFont(font)
        text_w = metrics.horizontalAdvance(label)
        text_h = metrics.height()
        mid_x = (x1 + x2) / 2.0
        gap = text_w / 2.0 + 4

        span = x2 - x1
        if span > text_w + arrow_size * 6:
            # Full: line — text — line with arrows
            painter.drawLine(int(x1), int(y_center), int(mid_x - gap), int(y_center))
            painter.drawLine(int(mid_x + gap), int(y_center), int(x2), int(y_center))
            self._draw_arrowhead_h(painter, line_pen, int(x1), int(y_center), arrow_size, pointing_left=True)
            self._draw_arrowhead_h(painter, line_pen, int(x2), int(y_center), arrow_size, pointing_left=False)
        elif span > arrow_size * 4:
            # Compact: just end ticks
            tick = max(2, arrow_size)
            painter.drawLine(int(x1), int(y_center - tick), int(x1), int(y_center + tick))
            painter.drawLine(int(x2), int(y_center - tick), int(x2), int(y_center + tick))
            painter.drawLine(int(x1), int(y_center), int(x2), int(y_center))

        # Text with background pill
        text_rect = QRectF(mid_x - text_w / 2.0 - 3, y_center - text_h / 2.0, text_w + 6, text_h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(text_bg))
        painter.drawRoundedRect(text_rect, 3, 3)
        painter.setPen(text_color)
        painter.drawText(text_rect, Qt.AlignCenter, label)

    def _draw_v_dimension(
        self, painter: QPainter,
        line_pen: QPen, text_color: QColor, text_bg: QColor,
        y1: float, y2: float, x_center: float,
        label: str, font: QFont, metrics, arrow_size: int,
    ) -> None:
        """Vertical dimension line with centered label."""
        painter.setPen(line_pen)
        painter.setFont(font)
        text_w = metrics.horizontalAdvance(label)
        text_h = metrics.height()
        mid_y = (y1 + y2) / 2.0
        gap = text_h / 2.0 + 3

        span = y2 - y1
        if span > text_h + arrow_size * 6:
            painter.drawLine(int(x_center), int(y1), int(x_center), int(mid_y - gap))
            painter.drawLine(int(x_center), int(mid_y + gap), int(x_center), int(y2))
            self._draw_arrowhead_v(painter, line_pen, int(x_center), int(y1), arrow_size, pointing_up=True)
            self._draw_arrowhead_v(painter, line_pen, int(x_center), int(y2), arrow_size, pointing_up=False)
        elif span > arrow_size * 4:
            tick = max(2, arrow_size)
            painter.drawLine(int(x_center - tick), int(y1), int(x_center + tick), int(y1))
            painter.drawLine(int(x_center - tick), int(y2), int(x_center + tick), int(y2))
            painter.drawLine(int(x_center), int(y1), int(x_center), int(y2))

        # Text with background pill
        text_rect = QRectF(x_center - text_w / 2.0 - 3, mid_y - text_h / 2.0, text_w + 6, text_h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(text_bg))
        painter.drawRoundedRect(text_rect, 3, 3)
        painter.setPen(text_color)
        painter.drawText(text_rect, Qt.AlignCenter, label)

    @staticmethod
    def _draw_arrowhead_h(painter: QPainter, pen: QPen, x: int, y: int, size: int, *, pointing_left: bool) -> None:
        """Small filled arrowhead on a horizontal dimension line."""
        d = size if pointing_left else -size
        painter.setPen(pen)
        painter.drawLine(x, y, x + d, y - size)
        painter.drawLine(x, y, x + d, y + size)

    @staticmethod
    def _draw_arrowhead_v(painter: QPainter, pen: QPen, x: int, y: int, size: int, *, pointing_up: bool) -> None:
        """Small filled arrowhead on a vertical dimension line."""
        d = size if pointing_up else -size
        painter.setPen(pen)
        painter.drawLine(x, y, x - size, y + d)
        painter.drawLine(x, y, x + size, y + d)

    def _draw_paper_badge(self, painter: QPainter, layout: _CachedPageLayout) -> None:
        """Floating paper-size badge with white background and subtle border."""
        cfg = self._current_cfg
        if cfg is None:
            return

        theme = get_theme()
        s = layout.scale
        page_rect = layout.page_rect

        badge_w = max(40, int(68 * s))
        badge_h = max(16, int(20 * s))
        badge_font = QFont(self.font())
        badge_font.setPixelSize(max(9, int(11 * s)))
        badge_font.setBold(True)

        badge_x = page_rect.left() + max(6, int(10 * s))
        badge_y = page_rect.top() + max(4, int(8 * s))
        badge_rect = QRectF(badge_x, badge_y, badge_w, badge_h)

        # White pill with thin border + micro shadow
        shadow_r = badge_rect.adjusted(1, 1.5, 1, 1.5)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(self._with_alpha(theme.text_primary, 12)))
        painter.drawRoundedRect(shadow_r, badge_h / 2, badge_h / 2)

        page_color = "#F0F1F3" if _is_dark_theme(theme) else "#FFFFFF"
        painter.setPen(QPen(self._with_alpha(theme.border, 80), 1))
        painter.setBrush(QBrush(QColor(page_color)))
        painter.drawRoundedRect(badge_rect, badge_h / 2, badge_h / 2)

        painter.setPen(QColor(theme.primary))
        painter.setFont(badge_font)
        painter.drawText(badge_rect, Qt.AlignCenter, cfg.page_setup.paper_size.upper())

    def _draw_text_content(self, painter: QPainter, layout: _CachedPageLayout) -> None:
        """Render pre-computed text lines from cache."""
        if not layout.line_layouts:
            return

        theme = get_theme()
        content_rect = layout.content_rect
        text_rect = content_rect.adjusted(4.0, 6.0, -4.0, -6.0)

        painter.save()
        painter.setClipRect(text_rect)

        for ll in layout.line_layouts:
            painter.setFont(ll.font)
            # Unified black text — faithful to real document output
            painter.setPen(QColor(theme.text_primary))

            align = Qt.AlignLeft | Qt.AlignVCenter
            # Use the actual style_key for alignment lookup
            if self._current_cfg:
                style = _resolve_preview_style(self._current_cfg, ll.style_key)
                align = preview_alignment_flags(style.alignment)

            draw_rect = QRectF(ll.x, ll.y, ll.width, ll.height)
            painter.drawText(draw_rect, align, ll.text)

        painter.restore()

    def _draw_table_content(self, painter: QPainter, layout: _CachedPageLayout) -> None:
        """Render sample table blocks from cache."""
        if not layout.table_layouts:
            return

        content_rect = layout.content_rect.adjusted(4.0, 6.0, -4.0, -6.0)
        painter.save()
        painter.setClipRect(content_rect)
        for table in layout.table_layouts:
            self._draw_sample_table(painter, table)
        painter.restore()

    def _draw_sample_table(self, painter: QPainter, table: _CachedTableLayout) -> None:
        theme = get_theme()
        rect = table.rect
        rows = len(table.rows)
        cols = len(table.rows[0]) if rows else 0
        if rows <= 0 or cols <= 0:
            return

        row_h = rect.height() / rows
        col_w = rect.width() / cols
        border_mode = table.border_mode
        variant = color_variant(table.color_variant_key)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#FFFFFF" if not _is_dark_theme(theme) else theme.bg_card)))
        painter.drawRect(rect)

        if border_mode == "color_table":
            if variant.zebra:
                painter.setBrush(QBrush(QColor(table.color_soft)))
                for row in range(1, rows, 2):
                    painter.drawRect(QRectF(rect.left(), rect.top() + row * row_h, rect.width(), row_h))
            if variant.header_fill:
                painter.setBrush(QBrush(QColor(table.color_accent)))
                painter.drawRect(QRectF(rect.left(), rect.top(), rect.width(), row_h))

        self._draw_sample_table_borders(painter, table, row_h, col_w)
        self._draw_sample_table_text(painter, table, row_h, col_w)

    def _draw_sample_table_borders(
        self,
        painter: QPainter,
        table: _CachedTableLayout,
        row_h: float,
        col_w: float,
    ) -> None:
        rect = table.rect
        rows = len(table.rows)
        cols = len(table.rows[0]) if rows else 0
        mode = table.border_mode

        if mode == "none":
            return

        if mode == "keep":
            theme = get_theme()
            pen = QPen(QColor(theme.text_hint), max(0.7, table.border_width * 0.85))
            pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(rect)
            for row in range(1, rows):
                y = rect.top() + row * row_h
                painter.drawLine(rect.left(), y, rect.right(), y)
            for col in range(1, cols):
                x = rect.left() + col * col_w
                painter.drawLine(x, rect.top(), x, rect.bottom())
            return

        if mode == "three_line":
            painter.setPen(QPen(QColor("#111827"), table.outer_width))
            painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
            painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
            painter.setPen(QPen(QColor("#111827"), table.header_rule_width))
            painter.drawLine(rect.left(), rect.top() + row_h, rect.right(), rect.top() + row_h)
            return

        if mode == "full_grid":
            painter.setPen(QPen(QColor("#111827"), table.border_width))
            for row in range(rows + 1):
                y = rect.top() + row * row_h
                painter.drawLine(rect.left(), y, rect.right(), y)
            for col in range(cols + 1):
                x = rect.left() + col * col_w
                painter.drawLine(x, rect.top(), x, rect.bottom())
            return

        if mode == "color_table":
            variant = color_variant(table.color_variant_key)
            accent = QColor(table.color_accent)
            light = QColor(table.color_light)
            if variant.header_rule_only:
                painter.setPen(QPen(accent, table.outer_width))
                painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
                painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
                painter.setPen(QPen(accent, table.header_rule_width))
                painter.drawLine(rect.left(), rect.top() + row_h, rect.right(), rect.top() + row_h)
                return
            if variant.show_horizontal:
                painter.setPen(QPen(accent, table.border_width))
                painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
                painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
                painter.setPen(QPen(light, max(0.6, table.border_width * 0.8)))
                for row in range(1, rows):
                    y = rect.top() + row * row_h
                    painter.drawLine(rect.left(), y, rect.right(), y)
            if variant.show_vertical:
                painter.setPen(QPen(accent, table.border_width))
                painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
                painter.drawLine(rect.right(), rect.top(), rect.right(), rect.bottom())
                painter.setPen(QPen(light, max(0.6, table.border_width * 0.8)))
                for col in range(1, cols):
                    x = rect.left() + col * col_w
                    painter.drawLine(x, rect.top(), x, rect.bottom())

    def _draw_sample_table_text(
        self,
        painter: QPainter,
        table: _CachedTableLayout,
        row_h: float,
        col_w: float,
    ) -> None:
        theme = get_theme()
        rect = table.rect
        variant = color_variant(table.color_variant_key)
        for row_index, row in enumerate(table.rows):
            painter.setFont(table.header_font if row_index == 0 else table.font)
            if table.border_mode == "color_table" and row_index == 0 and variant.header_fill:
                painter.setPen(QColor(table.color_header_text))
            else:
                painter.setPen(QColor(theme.text_primary))
            for col_index, text in enumerate(row):
                cell_rect = QRectF(
                    rect.left() + col_index * col_w + table.cell_padding,
                    rect.top() + row_index * row_h,
                    max(1.0, col_w - table.cell_padding * 2.0),
                    row_h,
                )
                painter.drawText(cell_rect, _table_cell_alignment_flags(table.cell_alignment), text)


    # ── Text wrapping (O(n) character-width accumulation) ─────────────

    @staticmethod
    def _wrap_preview_text(metrics, text: str, first_width: float, regular_width: float) -> list[str]:
        clean_text = " ".join(str(text or "").split())
        if not clean_text:
            return [""]

        lines: list[str] = []
        current = ""
        current_width = 0.0
        width_limit = max(first_width, 20.0)

        for char in clean_text:
            if not current and char.isspace():
                continue

            char_w = metrics.horizontalAdvance(char)
            if current and current_width + char_w > width_limit:
                lines.append(current.rstrip())
                if char.isspace():
                    current = ""
                    current_width = 0.0
                else:
                    current = char
                    current_width = char_w
                width_limit = max(regular_width, 20.0)
                continue
            current += char
            current_width += char_w

        if current:
            lines.append(current.rstrip())
        return lines or [clean_text]



__all__ = ['TemplateStylePreview']
