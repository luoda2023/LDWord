"""Helpers for syncing and applying TOC-related styles."""

from __future__ import annotations

from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from src.shared.engine.font_resolver import resolve_font
from src.shared.engine.indent_ops import apply_style_config_indents
from src.shared.engine.line_spacing_ops import apply_line_spacing, apply_paragraph_spacing, sync_spacing_ooxml
from src.shared.engine.ooxml_ops import find_or_create, qn
from src.shared.engine.style_ops import apply_style_text_format


TOC_MAX_SYNC_LEVEL = 6

LEVEL_TO_WORD_STYLE = {f"heading{level}": f"TOC {level}" for level in range(1, TOC_MAX_SYNC_LEVEL + 1)}

LEVEL_TO_STYLE_KEY = {f"heading{level}": f"toc_level{level}" for level in range(1, TOC_MAX_SYNC_LEVEL + 1)}

DEFAULT_TOC_ENTRY_STYLE_KEY = f"toc_level{TOC_MAX_SYNC_LEVEL}"

TOC_HEADING_STYLE_CANDIDATES = ["TOC Heading", "目录标题"]

ALIGNMENT_MAP = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    "distribute": WD_ALIGN_PARAGRAPH.DISTRIBUTE,
}


def resolve_toc_style_config(styles_cfg: dict, role: str):
    """Resolve an effective TOC style, falling back to shared ``styles.toc``."""
    explicit = styles_cfg.get(role)
    if explicit is not None:
        return explicit

    shared = styles_cfg.get("toc")
    if shared is not None:
        return shared

    fallback_keys = ("heading1", "heading", "body", "normal") if role == "toc_title" else ("body", "normal")
    for key in fallback_keys:
        style = styles_cfg.get(key)
        if style is not None:
            return style
    return None


def toc_heading_level(level: str | int) -> int:
    raw = str(level or "").strip().lower()
    if raw.startswith("heading"):
        raw = raw.replace("heading", "", 1)
    elif raw.startswith("toc"):
        raw = raw.replace("toc", "", 1)
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        parsed = TOC_MAX_SYNC_LEVEL
    return max(1, min(parsed, TOC_MAX_SYNC_LEVEL))


def toc_heading_key(level: str | int) -> str:
    return f"heading{toc_heading_level(level)}"


def toc_style_key_for_heading_level(level: str | int) -> str:
    return LEVEL_TO_STYLE_KEY.get(toc_heading_key(level), DEFAULT_TOC_ENTRY_STYLE_KEY)


def toc_word_style_for_heading_level(level: str | int) -> str:
    return LEVEL_TO_WORD_STYLE[toc_heading_key(level)]


def _styles_from_config_or_mapping(config_or_styles):
    return getattr(config_or_styles, "styles", config_or_styles)


def resolve_toc_title_style_config(config_or_styles):
    """Resolve the TOC title style from TOC-specific style roles."""
    return resolve_toc_style_config(_styles_from_config_or_mapping(config_or_styles), "toc_title")


def resolve_toc_entry_style_config(config_or_styles, level: str | int):
    """Resolve a TOC entry style from the matching TOC level role."""
    return resolve_toc_style_config(
        _styles_from_config_or_mapping(config_or_styles),
        toc_style_key_for_heading_level(level),
    )


def _ensure_style(doc, style_name: str):
    try:
        return doc.styles[style_name]
    except KeyError:
        return doc.styles.add_style(style_name, WD_STYLE_TYPE.PARAGRAPH)


def _normalize_toc_heading_style(doc, style, style_config) -> None:
    """Prevent TOC heading style from inheriting heading outline/numbering."""
    try:
        style.base_style = doc.styles["Normal"]
    except Exception:
        pass

    p_pr = find_or_create(style.element, "w:pPr")
    outline = p_pr.find(qn("w:outlineLvl"))
    if outline is None:
        outline = find_or_create(p_pr, "w:outlineLvl")
    outline.set(qn("w:val"), "9")
    num_pr = p_pr.find(qn("w:numPr"))
    if num_pr is not None:
        p_pr.remove(num_pr)

    pf = style.paragraph_format
    align_key = str(getattr(style_config, "alignment", "") or "center").strip().lower()
    pf.alignment = ALIGNMENT_MAP.get(align_key, WD_ALIGN_PARAGRAPH.CENTER)
    apply_paragraph_spacing(pf, style_config, style.element)
    apply_line_spacing(pf, style_config.line_spacing_type, style_config.line_spacing_pt)
    sync_spacing_ooxml(
        style.element,
        space_before_pt=style_config.space_before_pt,
        space_before_unit=getattr(style_config, "space_before_unit", "pt"),
        space_after_pt=style_config.space_after_pt,
        space_after_unit=getattr(style_config, "space_after_unit", "pt"),
        line_spacing_type=style_config.line_spacing_type,
        line_spacing_value=style_config.line_spacing_pt,
    )
    apply_style_config_indents(pf, style.element, style_config, size_pt=style_config.size_pt)

    apply_style_text_format(
        style,
        font_cn=style_config.font_cn,
        font_en=style_config.font_en,
        size_pt=style_config.size_pt,
        bold=style_config.bold,
        italic=style_config.italic,
    )


def _apply_toc_entry_style(style, style_config) -> None:
    pf = style.paragraph_format
    align_key = str(getattr(style_config, "alignment", "") or "").strip().lower()
    pf.alignment = ALIGNMENT_MAP.get(align_key, WD_ALIGN_PARAGRAPH.LEFT)
    apply_paragraph_spacing(pf, style_config, style.element)
    apply_line_spacing(pf, style_config.line_spacing_type, style_config.line_spacing_pt)
    sync_spacing_ooxml(
        style.element,
        space_before_pt=style_config.space_before_pt,
        space_before_unit=getattr(style_config, "space_before_unit", "pt"),
        space_after_pt=style_config.space_after_pt,
        space_after_unit=getattr(style_config, "space_after_unit", "pt"),
        line_spacing_type=style_config.line_spacing_type,
        line_spacing_value=style_config.line_spacing_pt,
    )
    apply_style_config_indents(pf, style.element, style_config, size_pt=style_config.size_pt)
    apply_style_text_format(
        style,
        font_cn=style_config.font_cn,
        font_en=style_config.font_en,
        size_pt=style_config.size_pt,
        bold=style_config.bold,
        italic=style_config.italic,
    )


def apply_toc_paragraph_style(para, style_config, *, is_title: bool = False) -> None:
    """Apply TOC title/entry formatting directly to an existing paragraph."""
    pf = para.paragraph_format
    if is_title:
        align_key = str(getattr(style_config, "alignment", "") or "center").strip().lower()
        pf.alignment = ALIGNMENT_MAP.get(align_key, WD_ALIGN_PARAGRAPH.CENTER)
        p_pr = find_or_create(para._element, "w:pPr")
        outline = p_pr.find(qn("w:outlineLvl"))
        if outline is None:
            outline = find_or_create(p_pr, "w:outlineLvl")
        outline.set(qn("w:val"), "9")
        num_pr = p_pr.find(qn("w:numPr"))
        if num_pr is not None:
            p_pr.remove(num_pr)
    else:
        align_key = str(getattr(style_config, "alignment", "") or "").strip().lower()
        pf.alignment = ALIGNMENT_MAP.get(align_key, WD_ALIGN_PARAGRAPH.LEFT)

    apply_paragraph_spacing(pf, style_config, para._element)
    apply_line_spacing(pf, style_config.line_spacing_type, style_config.line_spacing_pt)
    sync_spacing_ooxml(
        para._element,
        space_before_pt=style_config.space_before_pt,
        space_before_unit=getattr(style_config, "space_before_unit", "pt"),
        space_after_pt=style_config.space_after_pt,
        space_after_unit=getattr(style_config, "space_after_unit", "pt"),
        line_spacing_type=style_config.line_spacing_type,
        line_spacing_value=style_config.line_spacing_pt,
    )
    apply_style_config_indents(pf, para._element, style_config, size_pt=style_config.size_pt)

    for run in para.runs:
        if style_config.font_en:
            run.font.name = resolve_font(style_config.font_en, lang="en")
        if style_config.font_cn:
            from src.shared.engine.run_ops import set_run_east_asian_font

            set_run_east_asian_font(run, style_config.font_cn)
        if style_config.size_pt:
            run.font.size = Pt(style_config.size_pt)
        run.font.bold = bool(style_config.bold)
        run.font.italic = bool(style_config.italic)


def _sync_toc_styles_from_styles(doc, styles_cfg: dict) -> int:
    """Sync TOC heading + entry styles from config.styles definitions."""
    changed = 0

    toc_title_style = None
    for candidate in TOC_HEADING_STYLE_CANDIDATES:
        try:
            toc_title_style = doc.styles[candidate]
            break
        except KeyError:
            continue
    if toc_title_style is None:
        toc_title_style = doc.styles.add_style(TOC_HEADING_STYLE_CANDIDATES[0], WD_STYLE_TYPE.PARAGRAPH)

    toc_title_cfg = resolve_toc_style_config(styles_cfg, "toc_title")
    if toc_title_cfg is not None:
        _normalize_toc_heading_style(doc, toc_title_style, toc_title_cfg)
        changed += 1

    for level, word_style_name in LEVEL_TO_WORD_STYLE.items():
        style_config = resolve_toc_style_config(styles_cfg, toc_style_key_for_heading_level(level))
        if style_config is None:
            continue
        style = _ensure_style(doc, word_style_name)
        _apply_toc_entry_style(style, style_config)
        changed += 1

    return changed


def sync_toc_styles_from_config(doc, config, *, max_level: int = TOC_MAX_SYNC_LEVEL) -> int:
    """Sync Word TOC styles from TOC-specific roles on a full config object."""
    changed = 0

    toc_title_style = None
    for candidate in TOC_HEADING_STYLE_CANDIDATES:
        try:
            toc_title_style = doc.styles[candidate]
            break
        except KeyError:
            continue
    if toc_title_style is None:
        toc_title_style = doc.styles.add_style(TOC_HEADING_STYLE_CANDIDATES[0], WD_STYLE_TYPE.PARAGRAPH)

    styles_cfg = _styles_from_config_or_mapping(config)
    toc_title_cfg = resolve_toc_title_style_config(styles_cfg)
    if toc_title_cfg is not None:
        _normalize_toc_heading_style(doc, toc_title_style, toc_title_cfg)
        changed += 1

    levels = max(1, min(int(max_level or TOC_MAX_SYNC_LEVEL), TOC_MAX_SYNC_LEVEL))
    for level in range(1, levels + 1):
        style_config = resolve_toc_entry_style_config(styles_cfg, level)
        if style_config is None:
            continue
        style = _ensure_style(doc, toc_word_style_for_heading_level(level))
        _apply_toc_entry_style(style, style_config)
        changed += 1

    return changed


def sync_toc_styles(doc, config_or_styles, *, max_level: int = TOC_MAX_SYNC_LEVEL) -> int:
    """Sync TOC styles.

    Full template/resolved configs and raw style mappings both use the same
    TOC-specific role chain: ``toc_title`` and ``toc_levelN`` with ``toc`` as a
    compatibility fallback.
    """
    if hasattr(config_or_styles, "styles"):
        return sync_toc_styles_from_config(doc, config_or_styles, max_level=max_level)
    return _sync_toc_styles_from_styles(doc, config_or_styles)
