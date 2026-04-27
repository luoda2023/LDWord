"""
template_panel — 模板管理面板（Master-Detail 架构）

与工作台同构：左侧导航卡片 + 右侧可切换详情面板。
信息分层:
  Layer 1: 模板概览 (主操作)
  Layer 2: 导入导出 (管理操作)
  Layer 3: 页面设置 / 排版样式 / 标题编号 (参数细节)
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path

from src.config.builtin_templates import create_builtin_template
from src.config.heading_style_semantics import resolve_heading_style, resolve_non_numbered_heading_style
from src.config.library import (
    default_template_entry,
    get_template_entry,
    is_template_library_path,
    list_scene_descriptors,
    load_template_from_library,
)
from src.config.loader import load_template, save_template
from src.config.style_semantics import (
    CM_TO_PT,
    SPECIAL_INDENT_FIRST_LINE,
    SPECIAL_INDENT_HANGING,
    config_indent_value_to_pt,
    normalize_line_spacing_type,
    resolve_spacing_render_pt,
    resolve_line_spacing_value,
    resolve_style_special_indent,
)
from src.config.table_style_presets import color_palette, color_variant
from src.config.template import StyleConfig, TemplateConfig
from src.qt_api import (
    QBrush,
    QColor,
    QFileDialog,
    QFont,
    QFontMetricsF,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPainter,
    QPen,
    QRectF,
    QPushButton,
    QSize,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui import MasterDetailShell, NavigationCard, Toast
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.card import Card
from src.shared.ui.style_preview_utils import (
    preview_alignment_flags,
    resolve_preview_indents_pt,
    resolve_preview_size_pt,
)
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.adapters.heading_numbering_adapter import HeadingNumberingAdapter
from src.ui.base_panel import BasePanel
from src.ui.panels.template_format import build_template_preview_groups
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.ui.panels.template_caption_detail import CaptionDetail
from src.ui.panels.template_elements_detail import ElementsDetail
from src.ui.panels.template_reference_detail import ReferenceDetail
from src.ui.panels.template_table_detail import TableCaptionDetail
from src.ui.panels.template_page_detail import PageSetupDetail
from src.ui.panels.template_style_detail import StyleDetail
from src.ui.panels.workbench.detail_controller import WorkbenchDetailController


# ═══════════════════════════════════════════════════════════════════════
#  Built-in template registry
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class _BuiltinTemplateOption:
    template_id: str
    name: str


# ═══════════════════════════════════════════════════════════════════════
#  Card definitions (Layer 1 → 2 → 3)
# ═══════════════════════════════════════════════════════════════════════

CARD_DEFINITIONS: dict[str, tuple[str, str]] = {
    # Layer 1: Primary
    "tpl_overview":  ("模板概览",  "scan-text"),
    # Layer 2: Management
    "tpl_io":        ("导入导出",  "folder-open"),
    # Layer 3: Core parameter details
    "tpl_page":      ("页面设置",  "ruler"),
    "tpl_style":     ("正文排版",  "type-outline"),
    "tpl_heading":   ("标题编号",  "list-ordered"),
    "tpl_table":     ("表格",  "table-2"),
    "tpl_header_footer": ("页眉与页脚", "panel-top"),
    "tpl_toc":       ("目录", "scroll-text"),
    "tpl_reference": ("参考文献", "book-open"),
    "tpl_caption":   ("题注", "image-plus"),
}

CARD_ORDER = (
    "tpl_overview",
    "tpl_io",
    "tpl_page",
    "tpl_style",
    "tpl_heading",
    "tpl_table",
    "tpl_header_footer",
    "tpl_toc",
    "tpl_reference",
    "tpl_caption",
)
FIXED_CARDS = ("tpl_overview", "tpl_io")
DETAIL_CARDS = (
    "tpl_page",
    "tpl_style",
    "tpl_heading",
    "tpl_table",
    "tpl_header_footer",
    "tpl_toc",
    "tpl_reference",
    "tpl_caption",
)


@dataclass(frozen=True)
class _PreviewParagraph:
    style_key: str
    text: str


@dataclass(frozen=True, slots=True)
class _PreviewHeaderFooterState:
    header_text: str
    header_border: bool
    footer_text: str


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


def _resolve_preview_header_footer(cfg: TemplateConfig) -> _PreviewHeaderFooterState:
    header_footer = cfg.header_footer
    mode = str(getattr(header_footer, "header_mode", "styleref") or "styleref")
    if mode == "none":
        header_text = ""
    elif mode == "fixed":
        header_text = str(getattr(header_footer, "header_text", "") or "").strip()
    else:
        level = max(1, int(getattr(header_footer, "styleref_level", 1) or 1))
        title = _PREVIEW_HEADING_TITLES.get(level, f"{level}级标题")
        header_text = title if level <= 1 else f"{level}级 · {title}"

    return _PreviewHeaderFooterState(
        header_text=header_text,
        header_border=bool(getattr(header_footer, "header_border", True)) and mode != "none",
        footer_text=_page_number_preview_text(header_footer),
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tpl_style_preview")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._current_cfg: TemplateConfig | None = None
        self._cached_layout: _CachedPageLayout | None = None

        # Shadow effect — same pattern as Card / SurfaceCard
        self._shadow = QGraphicsDropShadowEffect(self)
        self.setGraphicsEffect(self._shadow)

        self._sync_preview_height(self._DEFAULT_WIDTH)
        self._apply_shadow_theme()
        bind_theme(self, self._apply_theme)

    def refresh(self, cfg: TemplateConfig) -> None:
        self._current_cfg = cfg
        self._sync_preview_height(self.width() or self._DEFAULT_WIDTH)
        self._rebuild_cache()
        self.update()

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
        self._rebuild_cache()
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
            font.setPixelSize(max(9, int(round(size_pt * pt_to_px))))
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

        border_mode = str(getattr(table_cfg, "border_mode", "") or "three_line").lower()
        palette = color_palette(getattr(table_cfg, "color_table_accent", "blue"))
        variant = color_variant(getattr(table_cfg, "color_table_variant", "header_grid"))

        header_font = QFont(font)
        header_has_fill = border_mode == "color_table" and variant.header_fill
        header_font.setBold(bool(getattr(table_cfg, "first_row_bold", False)) or header_has_fill)

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
        size_pt = float(getattr(cfg.header_footer, "size_pt", None) or 9.0)
        header_size = max(8, int(round(size_pt * pt_to_px)))
        header_font.setPixelSize(header_size)
        family = str(
            getattr(cfg.header_footer, "font_cn", None)
            or getattr(cfg.header_footer, "font_en", None)
            or ""
        ).strip()
        if family:
            header_font.setFamily(family)
        painter.setFont(header_font)

        header_text_color = self._with_alpha(theme.text_hint, 140)
        header_line_color = self._with_alpha(theme.text_hint, 80)

        if preview_state.header_text:
            header_text_rect = QRectF(
                cr.left(), layout.header_y - header_size - 2,
                cr.width(), header_size + 2,
            )
            painter.setPen(header_text_color)
            painter.drawText(header_text_rect, Qt.AlignHCenter | Qt.AlignBottom, preview_state.header_text)

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
                cr.width(), header_size + 2,
            )
            painter.setPen(header_text_color)
            painter.setFont(header_font)
            painter.drawText(footer_text_rect, Qt.AlignHCenter | Qt.AlignTop, preview_state.footer_text)

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


class TemplateOverviewDetail(QWidget):
    """Layer 1 detail: template selector + parameter summary + edit navigation."""

    template_selected = Signal(int)      # combo index
    edit_navigate = Signal(str)          # target card_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_template = create_builtin_template("default")

        # Cached refs for O(1) theme update
        self._cached_title_labels: list[QLabel] = []
        self._cached_hint_label: QLabel | None = None
        self._cached_preview_desc: QLabel | None = None
        self._cached_sep: QFrame | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # ── Card 1: Template selector ──
        self._selector_card = Card(parent=self)
        self._build_selector()
        layout.addWidget(self._selector_card)

        # ── Card 2: Parameter overview ──
        self._overview_card = Card(parent=self)
        self._build_overview()
        layout.addWidget(self._overview_card)

        # ── Card 3: Style preview ──
        self._preview_card = Card(parent=self)
        self._build_preview()
        layout.addWidget(self._preview_card)

        layout.addStretch(1)

    def _build_selector(self) -> None:
        # Header
        hdr = self._make_card_header("file-text", "当前模板")
        self._selector_card.add_widget(hdr)

        # ComboBox
        self._combo = StyledComboBox(self)
        self._combo.currentIndexChanged.connect(self.template_selected.emit)
        self._selector_card.add_widget(self._combo)

        # Source hint
        self._source_label = QLabel("来源: 内置模板")
        self._source_label.setObjectName("tpl_source")
        self._selector_card.add_widget(self._source_label)

    def set_template_options(
        self,
        options: list[_BuiltinTemplateOption],
        *,
        current_template_id: str = "",
    ) -> None:
        self._combo.blockSignals(True)
        try:
            self._combo.clear()
            for option in options:
                self._combo.addItem(option.name, option.template_id)
            target_id = str(current_template_id or "").strip()
            matched = False
            for index in range(self._combo.count()):
                if str(self._combo.itemData(index) or "").strip() == target_id:
                    self._combo.setCurrentIndex(index)
                    matched = True
                    break
            if not matched and self._combo.count() > 0:
                self._combo.setCurrentIndex(0)
        finally:
            self._combo.blockSignals(False)

    def _build_overview(self) -> None:
        # Header
        hdr = self._make_card_header("eye", "参数概览")
        self._overview_card.add_widget(hdr)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        self._cached_sep = sep
        self._overview_card.add_widget(sep)

        # Summary rows
        self._rows: dict[str, _SummaryRow] = {}
        for group in build_template_preview_groups(self._current_template):
            row = _SummaryRow(
                group.icon_name,
                group.label,
                group.summary,
                row_key=group.group_id,
                parent=self,
            )
            row.edit_clicked.connect(lambda _, t=group.detail_card_id: self.edit_navigate.emit(t))
            self._rows[group.group_id] = row
            self._overview_card.add_widget(row)

        # Hint
        hint = QLabel('点击各参数行的"编辑"可跳转至对应设置面板')
        self._cached_hint_label = hint
        self._overview_card.add_widget(hint)

    def _build_preview(self) -> None:
        hdr = self._make_card_header("eye", "样式预览")
        self._preview_card.add_widget(hdr)

        desc = QLabel("单页预览纸张比例、页边距、页眉页脚距离，以及标题层级和正文排版在同一页面中的效果")
        desc.setWordWrap(True)
        self._cached_preview_desc = desc
        self._preview_card.add_widget(desc)

        self._preview = TemplateStylePreview(self)
        self._preview.refresh(self._current_template)
        self._preview_card.add_widget(self._preview)

    def _make_card_header(self, icon_name: str, title: str) -> QWidget:
        hdr = QWidget()
        lay = QHBoxLayout(hdr)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(6)
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(18, 18)
        lay.addWidget(icon_lbl)
        title_lbl = QLabel(title)
        self._cached_title_labels.append(title_lbl)
        lay.addWidget(title_lbl)
        lay.addStretch(1)
        # Cache icon ref
        self._header_icons = getattr(self, "_header_icons", {})
        self._header_icons[icon_name] = icon_lbl
        return hdr

    def refresh(self, cfg: TemplateConfig) -> None:
        self._current_template = cfg
        for group in build_template_preview_groups(cfg):
            row = self._rows.get(group.group_id)
            if row:
                row.set_value(group.summary)
        # Refresh preview
        self._preview.refresh(cfg)

    def set_source_text(self, text: str) -> None:
        self._source_label.setText(text)

    def apply_theme(self) -> None:
        t = get_theme()
        title_ss = (
            f"font-size: {t.font_size_lg}px; font-weight: {t.font_weight_emphasis}; "
            f"color: {t.primary}; background: transparent;"
        )
        for lbl in self._cached_title_labels:
            lbl.setStyleSheet(title_ss)
        self._source_label.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_hint};")
        if self._cached_hint_label:
            self._cached_hint_label.setStyleSheet(
                f"font-size: {t.font_size_sm - 1}px; color: {t.text_hint}; padding-top: 4px;"
            )
        if self._cached_preview_desc:
            self._cached_preview_desc.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
            )
        if self._cached_sep:
            self._cached_sep.setStyleSheet(f"background: {t.border_light}; max-height: 1px;")
        try:
            from src.ui.icons.catalog import get_icon
            for name, lbl in getattr(self, "_header_icons", {}).items():
                lbl.setPixmap(get_icon(name, 18, t.primary).pixmap(18, 18))
        except Exception:
            pass
        self._preview.apply_theme()


# ═══════════════════════════════════════════════════════════════════════
#  Summary Row widget (reusable)
# ═══════════════════════════════════════════════════════════════════════

class _SummaryRow(QWidget):
    """Single row: icon + label + value + edit link."""

    edit_clicked = Signal(str)

    def __init__(self, icon_name: str, label: str, value: str, *, row_key: str | None = None, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._label_text = label
        self._row_key = row_key or label

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(8)

        self._icon_lbl = QLabel(self)
        self._icon_lbl.setFixedSize(16, 16)
        layout.addWidget(self._icon_lbl)

        self._label = QLabel(label, self)
        self._label.setFixedWidth(72)
        layout.addWidget(self._label)

        self._value = QLabel(value, self)
        self._value.setWordWrap(False)
        self._value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self._value, 1)

        self._edit_btn = QPushButton("编辑", self)
        self._edit_btn.setFlat(True)
        self._edit_btn.setCursor(Qt.PointingHandCursor)
        self._edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self._row_key))
        layout.addWidget(self._edit_btn)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_value(self, text: str) -> None:
        self._value.setText(text)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._label.setStyleSheet(
            f"font-size: {t.font_size_sm}px; font-weight: {t.font_weight_emphasis}; "
            f"color: {t.text_secondary};"
        )
        self._value.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_primary};")
        self._edit_btn.setStyleSheet(
            f"QPushButton {{ font-size: {t.font_size_sm}px; color: {t.primary}; "
            f"border: none; background: transparent; padding: 2px 6px; }}"
            f"QPushButton:hover {{ text-decoration: underline; }}"
        )
        self._edit_btn.setMinimumHeight(22)
        self._edit_btn.setMaximumHeight(22)
        try:
            from src.ui.icons.catalog import get_icon
            self._icon_lbl.setPixmap(get_icon(self._icon_name, size=14, color=t.text_hint).pixmap(14, 14))
        except Exception:
            self._icon_lbl.setText(self._label_text[:1])



class ImportExportDetail(QWidget):
    """Layer 2 detail: import / save-as / reset."""

    import_requested = Signal()
    save_as_requested = Signal()
    reset_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        card = Card(parent=self)

        # Header
        hdr = QWidget()
        h_lay = QHBoxLayout(hdr)
        h_lay.setContentsMargins(0, 0, 0, 6)
        h_lay.setSpacing(6)
        self._hdr_icon = QLabel()
        self._hdr_icon.setFixedSize(18, 18)
        h_lay.addWidget(self._hdr_icon)
        title = QLabel("模板文件管理")
        title.setObjectName("tpl_card_title")
        h_lay.addWidget(title)
        h_lay.addStretch(1)
        card.add_widget(hdr)

        # Description
        desc = QLabel("从文件导入模板配置，或将当前模板另存为 JSON/YAML 文件以便分享和备份。")
        desc.setObjectName("tpl_io_desc")
        desc.setWordWrap(True)
        card.add_widget(desc)

        # Buttons
        btn_row = QWidget()
        btn_lay = QHBoxLayout(btn_row)
        btn_lay.setContentsMargins(0, 8, 0, 0)
        btn_lay.setSpacing(8)

        self._import_btn = QPushButton("导入模板")
        self._import_btn.setCursor(Qt.PointingHandCursor)
        apply_button_variant(self._import_btn, "primary")
        self._import_btn.clicked.connect(self.import_requested.emit)
        btn_lay.addWidget(self._import_btn, 1)

        self._export_btn = QPushButton("另存为")
        self._export_btn.setCursor(Qt.PointingHandCursor)
        apply_button_variant(self._export_btn, "secondary")
        self._export_btn.clicked.connect(self.save_as_requested.emit)
        btn_lay.addWidget(self._export_btn, 1)

        card.add_widget(btn_row)

        # Reset row
        reset_row = QWidget()
        r_lay = QHBoxLayout(reset_row)
        r_lay.setContentsMargins(0, 4, 0, 0)
        r_lay.setSpacing(8)

        self._reset_btn = QPushButton("恢复为内置默认模板")
        self._reset_btn.setCursor(Qt.PointingHandCursor)
        apply_button_variant(self._reset_btn, "secondary")
        self._reset_btn.clicked.connect(self.reset_requested.emit)
        r_lay.addWidget(self._reset_btn, 1)
        r_lay.addStretch(1)

        card.add_widget(reset_row)

        # Status
        self._status = QLabel("")
        self._status.setObjectName("tpl_io_status")
        self._status.setWordWrap(True)
        card.add_widget(self._status)

        layout.addWidget(card)
        layout.addStretch(1)

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def apply_theme(self) -> None:
        t = get_theme()
        for w in self.findChildren(QLabel, "tpl_card_title"):
            w.setStyleSheet(
                f"font-size: {t.font_size_lg}px; font-weight: {t.font_weight_emphasis}; color: {t.primary}; background: transparent;"
            )
        for w in self.findChildren(QLabel, "tpl_io_desc"):
            w.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_secondary};")
        self._status.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_secondary};")
        try:
            from src.ui.icons.catalog import get_icon
            self._hdr_icon.setPixmap(get_icon("folder-open", 18, t.primary).pixmap(18, 18))
            self._import_btn.setIcon(get_icon("folder-open", 16, t.text_on_primary))
            self._export_btn.setIcon(get_icon("download", 16, t.primary))
            self._reset_btn.setIcon(get_icon("refresh-ccw", 16, t.primary))
        except Exception:
            pass


class _PlaceholderDetail(QWidget):
    """Placeholder for future parameter editing panes."""

    def __init__(self, title: str, icon_name: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._icon_name = icon_name
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        card = Card(parent=self)

        hdr = QWidget()
        h_lay = QHBoxLayout(hdr)
        h_lay.setContentsMargins(0, 0, 0, 6)
        h_lay.setSpacing(6)
        self._hdr_icon = QLabel()
        self._hdr_icon.setFixedSize(18, 18)
        h_lay.addWidget(self._hdr_icon)
        t_lbl = QLabel(title)
        t_lbl.setObjectName("tpl_card_title")
        h_lay.addWidget(t_lbl)
        h_lay.addStretch(1)
        card.add_widget(hdr)

        desc = QLabel(f"「{title}」参数编辑面板开发中...\n后续版本将支持在此直接编辑模板参数。")
        desc.setObjectName("tpl_placeholder_desc")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        card.add_widget(desc)

        layout.addWidget(card)
        layout.addStretch(1)

    def apply_theme(self) -> None:
        t = get_theme()
        for w in self.findChildren(QLabel, "tpl_card_title"):
            w.setStyleSheet(
                f"font-size: {t.font_size_lg}px; font-weight: {t.font_weight_emphasis}; color: {t.primary}; background: transparent;"
            )
        for w in self.findChildren(QLabel, "tpl_placeholder_desc"):
            w.setStyleSheet(
                f"font-size: {t.font_size_md}px; color: {t.text_hint}; padding: 40px 20px;"
            )
        try:
            from src.ui.icons.catalog import get_icon
            self._hdr_icon.setPixmap(get_icon(self._icon_name, 18, t.primary).pixmap(18, 18))
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════
#  Main Panel (Master-Detail)
# ═══════════════════════════════════════════════════════════════════════

class TemplatePanel(BasePanel):
    """Master-detail template management panel."""

    panel_title = "模板管理"
    panel_icon = "file-text"

    def _setup_ui(self) -> None:
        self.setObjectName("TemplatePanel")
        self._current_template_id = self.bridge.current_template_id()
        self._current_template_path = self.bridge.current_template_path()
        self._current_template_source = self.bridge.current_template_source()
        self._persisted_template_snapshot = None
        self._bridge_template_echo_depth = 0

        current_template = self.bridge.current_template()
        if current_template is not None:
            self._current_template = current_template
            if not self.bridge.is_template_dirty():
                self._remember_persisted_template_state(current_template)
        else:
            scene = self.bridge.current_scene()
            scene_template_id = ""
            if scene is not None:
                scene_template_id = str(
                    getattr(scene, "template_id", "")
                    or getattr(scene, "default_template_id", "")
                    or ""
                ).strip()

            if scene_template_id:
                entry = get_template_entry(scene_template_id)
                self._current_template = load_template_from_library(scene_template_id)
                self._current_template_id = scene_template_id
                self._current_template_path = str(entry.path) if entry is not None else ""
                self._current_template_source = "library" if entry is not None else "builtin"
            else:
                default_entry = default_template_entry()
                if default_entry is not None:
                    self._current_template = load_template_from_library(default_entry.config_id)
                    self._current_template_id = default_entry.config_id
                    self._current_template_path = str(default_entry.path)
                    self._current_template_source = "library"
                else:
                    self._current_template = create_builtin_template("default")
                    self._current_template_id = "default"
                    self._current_template_source = "builtin"
            self._remember_persisted_template_state(self._current_template)

        self._shell = MasterDetailShell(
            self,
            panel_name="TemplatePanel",
            nav_object_name="tpl_navigation",
            detail_object_name="tpl_detail",
            detail_content_object_name="tpl_detail_content",
        )
        self._layout = self._shell.layout
        self._nav_rail = self._shell.nav_rail
        self._detail_scroll = self._shell.detail_scroll
        self._detail_container = self._shell.detail_container
        self._detail_layout = self._shell.detail_layout

        # ── Build detail panes ──
        self._overview_detail = TemplateOverviewDetail()
        self._io_detail = ImportExportDetail()
        self._page_detail = PageSetupDetail()
        self._style_detail = StyleDetail()
        self._heading_detail = HeadingNumberingPanel(self.bridge)
        self._table_detail = TableCaptionDetail()
        self._header_footer_detail = ElementsDetail(scope="header_footer")
        self._toc_detail = ElementsDetail(scope="toc")
        self._reference_detail = ReferenceDetail()
        self._caption_detail = CaptionDetail()

        self._detail_map: dict[str, QWidget] = {
            "tpl_overview": self._overview_detail,
            "tpl_io": self._io_detail,
            "tpl_page": self._page_detail,
            "tpl_style": self._style_detail,
            "tpl_heading": self._heading_detail,
            "tpl_table": self._table_detail,
            "tpl_header_footer": self._header_footer_detail,
            "tpl_toc": self._toc_detail,
            "tpl_reference": self._reference_detail,
            "tpl_caption": self._caption_detail,
        }
        self._details = WorkbenchDetailController(
            self._detail_container,
            self._detail_layout,
            self._detail_scroll,
        )
        self._details.register_details(self._detail_map)
        self._current_detail: QWidget | None = self._details.current_detail

        # ── Build navigation cards (Layer 1 + 2, then header, then Layer 3) ──
        self._nav_cards: dict[str, NavigationCard] = {}

        # Layer 1 + 2: Fixed cards
        for card_id in FIXED_CARDS:
            title, icon = CARD_DEFINITIONS[card_id]
            card = NavigationCard(card_id, title, icon_name=icon, parent=self._nav_rail)
            self._nav_cards[card_id] = card
            self._nav_rail.add_card(card_id, card)

        # Section header between Layer 2 and Layer 3
        self._nav_rail.add_section_header("参数编辑")

        # Layer 3: Detail cards
        for card_id in DETAIL_CARDS:
            title, icon = CARD_DEFINITIONS[card_id]
            card = NavigationCard(card_id, title, icon_name=icon, parent=self._nav_rail)
            self._nav_cards[card_id] = card
            self._nav_rail.add_card(card_id, card)

        # ── Initial state ──
        self._refresh_template_selector_options()
        self._set_detail_templates(self._current_template)
        self._overview_detail.set_source_text(self._template_source_text())
        self._overview_detail.refresh(self._current_template)
        self._refresh_subtitles()
        self._set_detail_save_enabled(self.bridge.is_template_dirty())
        if self.bridge.current_template() is None:
            self._publish_current_template(emit_signal=False)
        # Manually show initial detail (signals not yet connected)
        self._show_detail("tpl_overview")
        self._nav_rail.select_card("tpl_overview")
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _connect_signals(self) -> None:
        # Navigation
        self._nav_rail.card_selected.connect(self._show_detail)

        # Overview interactions
        self._overview_detail.template_selected.connect(self._on_template_selected)
        self._overview_detail.edit_navigate.connect(self._nav_rail.select_card)

        # Import/Export
        self._io_detail.import_requested.connect(self._on_import)
        self._io_detail.save_as_requested.connect(self._save_current_template_as)
        self._io_detail.reset_requested.connect(self._on_reset)
        self._page_detail.template_edited.connect(self._on_template_edited)
        self._page_detail.save_requested.connect(self._on_page_save_requested)
        self._style_detail.template_edited.connect(self._on_template_edited)
        self._style_detail.save_requested.connect(self._on_style_save_requested)
        self._heading_detail.template_edited.connect(self._on_template_edited)
        self._heading_detail.save_requested.connect(self._save_current_template)
        self._table_detail.template_edited.connect(self._on_template_edited)
        self._table_detail.save_requested.connect(self._save_current_template)
        self._header_footer_detail.template_edited.connect(self._on_template_edited)
        self._header_footer_detail.save_requested.connect(self._save_current_template)
        self._toc_detail.template_edited.connect(self._on_template_edited)
        self._toc_detail.save_requested.connect(self._save_current_template)
        self._reference_detail.template_edited.connect(self._on_template_edited)
        self._reference_detail.save_requested.connect(self._save_current_template)
        self._caption_detail.template_edited.connect(self._on_template_edited)
        self._caption_detail.save_requested.connect(self._save_current_template)

        # Bridge
        self.bridge.scene_changed.connect(self.on_scene_changed)
        self.bridge.template_changed.connect(self.on_template_changed)
        self.bridge.template_dirty_changed.connect(self._on_template_dirty_changed)

    # ──────────────────────────────────────────────────────
    # Detail switching
    # ──────────────────────────────────────────────────────

    def _show_detail(self, card_id: str) -> None:
        self._details.show_detail(card_id)
        self._current_detail = self._details.current_detail
        detail = self._detail_map.get(card_id)
        if detail is not None and hasattr(detail, "capture_entry_snapshot"):
            detail.capture_entry_snapshot()

    def _template_source_text(self) -> str:
        source = str(self._current_template_source or "").strip()
        path = str(self._current_template_path or "").strip()
        if source == "library" and path:
            return self._format_source_text("模板库", path)
        if source == "file" and path:
            return self._format_source_text("文件", path)
        if source == "builtin":
            return self._format_source_text("内置模板")
        if path:
            return self._format_source_text(Path(path).name)
        return self._format_source_text("当前会话")

    @staticmethod
    def _format_source_text(source_label: str, path: str = "") -> str:
        label = str(source_label or "").strip() or "当前会话"
        normalized_path = str(path or "").strip()
        if normalized_path:
            return f"来源: {label}（{Path(normalized_path).name}）"
        return f"来源: {label}"

    def _template_ids_for_selector(self) -> list[str]:
        scene = self.bridge.current_scene()
        template_ids: list[str] = []
        if scene is not None:
            template_ids.extend(str(item or "").strip() for item in getattr(scene, "compatible_template_ids", []))
            if not template_ids:
                seed = str(getattr(scene, "template_id", "") or getattr(scene, "default_template_id", "") or "").strip()
                if seed:
                    template_ids.append(seed)
        else:
            seen: set[str] = set()
            for descriptor in list_scene_descriptors():
                template_id = str(descriptor.default_template_id or "").strip()
                if not template_id or template_id in seen:
                    continue
                seen.add(template_id)
                template_ids.append(template_id)

        current_template_id = str(self._current_template_id or "").strip()
        if current_template_id and current_template_id not in template_ids:
            template_ids.insert(0, current_template_id)
        return [template_id for template_id in template_ids if template_id]

    def _template_option_label(self, template_id: str) -> str:
        target_id = str(template_id or "").strip()
        if not target_id:
            return ""

        if target_id == str(self._current_template_id or "").strip() and self._current_template is not None:
            current_name = str(getattr(self._current_template, "name", "") or "").strip()
            if current_name:
                return current_name

        entry = get_template_entry(target_id)
        if entry is not None:
            return entry.name

        try:
            return str(create_builtin_template(target_id).name or target_id)
        except Exception:
            return target_id

    def _refresh_template_selector_options(self) -> None:
        options = [
            _BuiltinTemplateOption(template_id=template_id, name=self._template_option_label(template_id))
            for template_id in self._template_ids_for_selector()
        ]
        self._overview_detail.set_template_options(options, current_template_id=self._current_template_id)

    def _parameter_details(self) -> list[QWidget]:
        return [
            self._page_detail,
            self._style_detail,
            self._heading_detail,
            self._table_detail,
            self._header_footer_detail,
            self._toc_detail,
            self._reference_detail,
            self._caption_detail,
        ]

    def _set_detail_templates(self, template: TemplateConfig) -> None:
        for detail in self._parameter_details():
            if hasattr(detail, "set_template"):
                detail.set_template(template)
            elif hasattr(detail, "on_template_changed"):
                detail.on_template_changed(template)
        if template is not None and not self.bridge.is_template_dirty():
            self._remember_persisted_template_state(template)

    def _set_detail_save_enabled(self, enabled: bool) -> None:
        for detail in self._parameter_details():
            if hasattr(detail, "set_save_enabled"):
                detail.set_save_enabled(enabled)

    def _capture_detail_snapshots(self) -> None:
        for detail in self._parameter_details():
            if hasattr(detail, "capture_entry_snapshot"):
                detail.capture_entry_snapshot()

    def _remember_persisted_template_state(self, template=None) -> None:
        target = template if template is not None else self._current_template
        self._persisted_template_snapshot = copy.deepcopy(target) if target is not None else None

    def _compute_dirty_against_persisted_snapshot(self) -> bool | None:
        if self._current_template is None:
            return False
        if self._persisted_template_snapshot is None:
            return None
        return self._current_template != self._persisted_template_snapshot

    def _sync_template_dirty_state(self, *, assume_dirty_if_unknown: bool = False) -> bool:
        dirty = self._compute_dirty_against_persisted_snapshot()
        if dirty is None:
            dirty = True if assume_dirty_if_unknown else self.bridge.is_template_dirty()
        if dirty:
            self.bridge.mark_template_dirty()
        else:
            self.bridge.clear_template_dirty()
        return dirty

    def _can_save_in_place(self) -> bool:
        path = str(self._current_template_path or "").strip()
        return bool(path)

    def _publish_current_template(self, *, emit_signal: bool = True) -> None:
        if self._current_template is None:
            return

        if emit_signal:
            self._bridge_template_echo_depth += 1
        try:
            self.bridge.set_current_template(
                self._current_template,
                config_id=self._current_template_id,
                path=self._current_template_path,
                source=self._current_template_source,
                emit_signal=emit_signal,
            )
        finally:
            if emit_signal:
                self._bridge_template_echo_depth -= 1

    def _write_current_template_to_path(
        self,
        path: str | Path,
        *,
        success_message: str,
    ) -> bool:
        if self._current_template is None:
            return False

        try:
            saved = save_template(self._current_template, path)
            self._current_template_id = saved.stem
            self._current_template_path = str(saved)
            self._current_template_source = "library" if is_template_library_path(saved) else "file"
            self._remember_persisted_template_state(self._current_template)
            success_text = success_message.format(name=saved.name)
            self._io_detail.set_status(success_text)
            self._overview_detail.set_source_text(self._template_source_text())
            self.bridge.clear_template_dirty()
            self._publish_current_template()
            self._capture_detail_snapshots()
            self._set_detail_save_enabled(False)
            Toast.show_success(success_text.replace("✅ ", ""))
            return True
        except Exception as exc:
            message = f"❌ 保存失败: {exc}"
            self._io_detail.set_status(message)
            Toast.show_error(f"保存失败: {exc}")
            return False

    def _save_current_template(self) -> bool:
        if self._current_template is None:
            return False
        if self._can_save_in_place():
            return self._write_current_template_to_path(
                self._current_template_path,
                success_message="✅ 已保存: {name}",
            )
        return self._save_current_template_as()

    def _save_current_template_as(self) -> bool:
        if self._current_template is None:
            return False

        default_name = (self._current_template.name or "template") + ".json"
        path, _ = QFileDialog.getSaveFileName(
            self, "另存为模板配置", default_name,
            "JSON (*.json);;YAML (*.yaml *.yml)",
        )
        if not path:
            return False
        return self._write_current_template_to_path(
            path,
            success_message="✅ 已另存为: {name}",
        )

    # ──────────────────────────────────────────────────────
    # Event handlers
    # ──────────────────────────────────────────────────────

    def _on_template_selected(self, index: int) -> None:
        template_id = str(self._overview_detail._combo.itemData(index) or "").strip()
        if template_id:
            entry = get_template_entry(template_id)
            if (
                template_id == str(self._current_template_id or "").strip()
                and str(self._current_template_source or "").strip() == "file"
                and str(self._current_template_path or "").strip()
            ):
                self._current_template = load_template(self._current_template_path)
            else:
                self._current_template = load_template_from_library(template_id)
            self._current_template_id = template_id
            self._current_template_path = str(entry.path) if entry is not None else self._current_template_path
            self._current_template_source = "library" if entry is not None else ("file" if self._current_template_path else "builtin")
            self._refresh_template_selector_options()
            self._set_detail_templates(self._current_template)
            self._remember_persisted_template_state(self._current_template)
            self._overview_detail.set_source_text(self._template_source_text())
            self._overview_detail.refresh(self._current_template)
            self._io_detail.set_status("")
            self._refresh_subtitles()
            self.bridge.clear_template_dirty()
            self._publish_current_template()

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "导入模板配置", "",
            "配置文件 (*.json *.yaml *.yml);;JSON (*.json);;YAML (*.yaml *.yml)",
        )
        if not path:
            return
        try:
            cfg = load_template(path)
            self._current_template = cfg
            self._current_template_id = Path(path).stem
            self._current_template_path = str(Path(path))
            self._current_template_source = "file"
            name = cfg.name or Path(path).stem
            self._refresh_template_selector_options()
            self._set_detail_templates(self._current_template)
            self._remember_persisted_template_state(self._current_template)
            self._overview_detail.set_source_text(self._format_source_text("导入文件", path))
            self._overview_detail.refresh(cfg)
            self._io_detail.set_status(f"✅ 已导入: {name}")
            self._refresh_subtitles()
            self.bridge.clear_template_dirty()
            self._publish_current_template()
        except Exception as e:
            self._io_detail.set_status(f"❌ 导入失败: {e}")

    def _on_page_save_requested(self) -> None:
        self._save_current_template()

    def _on_style_save_requested(self) -> None:
        self._save_current_template()

    def _on_reset(self) -> None:
        idx = self._overview_detail._combo.currentIndex()
        template_id = str(self._overview_detail._combo.itemData(idx) or "").strip()
        if template_id:
            entry = get_template_entry(template_id)
            self._current_template = load_template_from_library(template_id)
            self._current_template_id = template_id
            self._current_template_path = str(entry.path) if entry is not None else ""
            self._current_template_source = "library" if entry is not None else "builtin"
            self._refresh_template_selector_options()
            self._set_detail_templates(self._current_template)
            self._remember_persisted_template_state(self._current_template)
            self._overview_detail.set_source_text(self._template_source_text())
            self._overview_detail.refresh(self._current_template)
            self._io_detail.set_status("✅ 已恢复为内置默认模板")
            self._refresh_subtitles()
            self.bridge.clear_template_dirty()
            self._publish_current_template()

    def _on_template_edited(self, template: TemplateConfig) -> None:
        self._current_template = template
        self._overview_detail.refresh(template)
        self._refresh_subtitles()
        self._publish_current_template()
        self._sync_template_dirty_state(assume_dirty_if_unknown=True)

    def _on_template_dirty_changed(self, dirty: bool) -> None:
        self._overview_detail.refresh(self._current_template)
        self._refresh_subtitles()
        self._set_detail_save_enabled(bool(dirty))

    def on_scene_changed(self, _scene) -> None:
        self._refresh_template_selector_options()

    def on_template_changed(self, template: TemplateConfig) -> None:
        if self._bridge_template_echo_depth:
            return
        previous_template = self._current_template
        previous_path = self._current_template_path
        previous_source = self._current_template_source
        self._current_template = template
        self._current_template_id = self.bridge.current_template_id()
        self._current_template_path = self.bridge.current_template_path()
        self._current_template_source = self.bridge.current_template_source()
        if (
            not self.bridge.is_template_dirty()
            and (
                template is not previous_template
                or self._current_template_path != previous_path
                or self._current_template_source != previous_source
            )
        ):
            self._remember_persisted_template_state(template)
        self._refresh_template_selector_options()
        self._overview_detail.set_source_text(self._template_source_text())
        self._overview_detail.refresh(template)
        self._set_detail_templates(template)
        self._set_detail_save_enabled(self.bridge.is_template_dirty())
        self._refresh_subtitles()

    # ──────────────────────────────────────────────────────
    # Subtitle refresh
    # ──────────────────────────────────────────────────────

    def _refresh_subtitles(self) -> None:
        groups = build_template_preview_groups(self._current_template)
        subtitle_map = {group.detail_card_id: group.summary for group in groups}

        card = self._nav_cards.get("tpl_overview")
        if card:
            card.set_subtitle(self._current_template.name or "默认格式")

        for card_id in DETAIL_CARDS:
            card = self._nav_cards.get(card_id)
            if card:
                card.set_subtitle(subtitle_map.get(card_id, ""))

    # ──────────────────────────────────────────────────────
    # Theme
    # ──────────────────────────────────────────────────────

    def _apply_theme(self) -> None:
        t = get_theme()
        self._shell.apply_theme(t)

        # Propagate to details
        self._overview_detail.apply_theme()
        self._io_detail.apply_theme()
        for detail in self._parameter_details():
            if hasattr(detail, "apply_theme"):
                detail.apply_theme()
            elif hasattr(detail, "_apply_theme"):
                detail._apply_theme()
