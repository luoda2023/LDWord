"""Export local Markdown to DOCX through the project's semantic content pipeline.

The exporter walks the project's strict Markdown importer so headings, lists,
inline styles, and GFM tables keep their structure, then patches in real
images: the strict renderer emits ``bookmark``+hidden-text sentinel paragraphs
for each ``ImageBlock`` (a ``ContentImageJobDraft``), and this module replaces
those sentinels with ``python-docx`` inline pictures resolved from a caller
supplied ``resource_paths`` mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt

from src.config.content_materials import ContentInsertionRule, content_anchor_token
from src.shared.engine.docx_renderer import render_document_fragment
from src.shared.engine.markdown_importer import (
    MarkdownImportError,
    discover_markdown_resource_paths,
    parse_markdown_content,
)

# Max inline picture width in centimetres; taller images keep their aspect ratio
# and are simply capped at this width so they never overflow the page.
_MAX_IMAGE_WIDTH_CM = 15.0

# Downsample guard: images whose longest edge exceeds this many pixels are
# resized before embedding. 2000px ≈ 300 DPI across a 15 cm column, so anything
# larger adds bytes without visible quality gain on paper/PDF.
_MAX_IMAGE_EDGE_PX = 2000

# Convert large photos to JPEG (lossy, tiny) rather than carrying a huge PNG.
# A PNG must exceed this many pixels on its longest edge before we re-encode it
# as JPEG; smaller images keep their original format to preserve sharpness and
# (for PNG) alpha.
_JPEG_THRESHOLD_PX = 1600

# Page size presets, in millimetres. A3 landscape gives a wide two-column page;
# A4 portrait is the standard single-column default.
_PAGE_SIZES_MM: dict[str, tuple[float, float]] = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
}

# Image quality presets for ``PageConfig.image_quality``. Each maps to the
# downsample guard (longest-edge px), the JPEG re-encode threshold (px), and the
# JPEG quality. ``None`` for ``max_edge`` means "keep the original size".
_IMAGE_QUALITY_PRESETS: dict[str, dict[str, int | None]] = {
    "original": {"max_edge": None, "jpeg_threshold": None, "jpeg_quality": None},
    "compressed": {"max_edge": 2000, "jpeg_threshold": 1600, "jpeg_quality": 85},
    "high": {"max_edge": 1200, "jpeg_threshold": 1000, "jpeg_quality": 70},
}


@dataclass(frozen=True)
class PageConfig:
    """Page geometry for a DOCX export.

    ``paper`` selects the sheet size (``A4`` / ``A3``); ``landscape`` rotates
    it; ``columns`` is the number of text columns (1 = single column, 2 = two
    side-by-side columns). ``columns`` is clamped to a sane range so a huge
    value cannot produce a broken layout.
    """

    paper: str = "A4"
    landscape: bool = False
    columns: int = 1
    margin_top_mm: float | None = None
    margin_bottom_mm: float | None = None
    margin_left_mm: float | None = None
    margin_right_mm: float | None = None
    column_spacing_mm: float | None = None
    header_text: str | None = None
    footer_text: str | None = None
    chapter_split: bool = True
    per_chapter_header: bool = True
    image_quality: str = "compressed"
    include_cover: bool = False
    cover_title: str | None = None
    cover_subtitle: str | None = None
    cover_date: str | None = None
    footer_page_number: bool = False
    footer_page_restart: bool = False

    def __post_init__(self) -> None:
        paper = (self.paper or "A4").upper()
        if paper not in _PAGE_SIZES_MM:
            raise MarkdownDocxExportError(
                f"unsupported paper size {self.paper!r} (expected A4 or A3)"
            )
        object.__setattr__(self, "paper", paper)
        columns = max(1, min(int(self.columns or 1), 4))
        object.__setattr__(self, "columns", columns)

        # Sanitise optional numeric geometry so a stray negative or oversized
        # value cannot produce a broken layout.
        def _nonneg_mm(value: float | None, label: str) -> float | None:
            if value is None:
                return None
            try:
                value = float(value)
            except (TypeError, ValueError) as exc:
                raise MarkdownDocxExportError(
                    f"invalid {label} value {value!r} (expected millimetres)"
                ) from exc
            return max(0.0, value)

        for name in (
            "margin_top_mm",
            "margin_bottom_mm",
            "margin_left_mm",
            "margin_right_mm",
            "column_spacing_mm",
        ):
            object.__setattr__(self, name, _nonneg_mm(getattr(self, name), name))

        for name in (
            "header_text",
            "footer_text",
            "cover_title",
            "cover_subtitle",
            "cover_date",
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                value = str(value)
            object.__setattr__(self, name, value)

        quality = str(self.image_quality or "compressed").strip().lower()
        if quality not in _IMAGE_QUALITY_PRESETS:
            raise MarkdownDocxExportError(
                f"unsupported image quality {self.image_quality!r} "
                f"(expected original, compressed, or high)"
            )
        object.__setattr__(self, "image_quality", quality)

    @classmethod
    def a3_landscape_two_columns(cls) -> "PageConfig":
        """Convenience preset: A3 landscape, two columns."""

        return cls(paper="A3", landscape=True, columns=2)


class MarkdownDocxExportError(ValueError):
    """Raised when Markdown cannot be represented safely in a DOCX export."""


# A chapter heading is either a Markdown level-1 heading (``# …``) or a plain
# Chinese 「第X章 / 第X篇」 line — the same convention ``_parse_outline_blocks``
# uses for its Heading-1 block, so a body written as ``第1章 项目概述`` (without
# a leading ``#``) still splits into chapters.
_CHAPTER_SPLIT_RE = re.compile(
    r"^(?=#{1}\s|第[一二三四五六七八九十百0-9]+[章篇])",
    re.MULTILINE,
)


def _split_chapters(source: str) -> list[tuple[str, str]]:
    """Split Markdown on level-1 headings into ``(title, body)`` chapters.

    A heading may be a Markdown ``# 标题`` line or a plain Chinese ``第X章 /
    第X篇`` line (matching ``_parse_outline_blocks``).  Each returned tuple is
    ``(heading_text, full_chapter_markdown)`` where ``full_chapter_markdown``
    starts with the heading line.  Text before the first heading is emitted as
    a leading chapter with an empty title (it has no section header).
    """

    text = str(source or "").strip("\n")
    if not text:
        return []
    positions = [m.start() for m in _CHAPTER_SPLIT_RE.finditer(text)]
    if not positions:
        return [("", text)]

    chapters: list[tuple[str, str]] = []
    if positions[0] > 0:
        preamble = text[: positions[0]].strip("\n")
        if preamble:
            chapters.append(("", preamble))

    for i, start in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(text)
        body = text[start:end].strip("\n")
        first_line = body.split("\n", 1)[0]
        title = first_line.lstrip("#").strip()
        chapters.append((title, body))
    return chapters


# ---------------------------------------------------------------------------
# Part-aware export
#
# A long report may nest coarse grouping headings (篇 / 单元 / 卷 / 部分) above its
# content 章.  When that structure is present, each part becomes a new-page
# section and chapters under it are numbered 1..N *within* the part, rendered as
# an auto-generated 篇N·第M章 prefix in front of the chapter title.  A flat
# document without part headings keeps the existing per-chapter behaviour.
# ---------------------------------------------------------------------------

# Strips a leading Markdown heading run (``# `` / ``## `` …) leaving the raw text.
_HEADING_MARK_RE = re.compile(r"^\s*#+\s*")

# Matches ``第X<单位>`` with an optional leading heading run. Captures the unit word.
_UNIT_HEADING_RE = re.compile(
    r"^\s*#+\s*第\s*[一二三四五六七八九十百千万〇零两0-9１-９]+\s*(单元|部分|章|篇|部|卷|分)"
)

_PART_UNITS = ("单元", "部分", "篇", "卷")


def _heading_unit(line: str) -> str:
    """Return the unit word (单元/部分/章/篇/部/卷/分) when *line* is a numbered
    Chinese heading, else ``""``.  ``# 第X篇 …`` and bare ``第X篇 …`` both count.
    """
    match = _UNIT_HEADING_RE.match(line)
    if match:
        return match.group(1)
    # Bare 第X<unit> line without a leading ``#``.
    bare = re.match(
        r"^第\s*[一二三四五六七八九十百千万〇零两0-9１-９]+\s*(单元|部分|章|篇|部|卷|分)",
        str(line or "").strip(),
    )
    if bare:
        return bare.group(1)
    return ""


def _is_part_unit(unit: str) -> bool:
    return unit in _PART_UNITS


@dataclass(frozen=True)
class ExportChapter:
    """One renderable unit in the exported document.

    A part heading (篇) is represented as a chapter whose ``is_part`` is True;
    content 章 chapters have ``is_part`` False and carry the ``part_title`` of
    their enclosing part plus their within-part ``chapter_index``.  ``raw_title``
    is the heading text exactly as it appeared; ``body`` is the source lines under
    the heading (not including the heading line).
    """

    raw_title: str
    body: str
    is_part: bool = False
    part_title: str = ""
    part_index: int = 0
    chapter_index: int = 0

    @property
    def display_title(self) -> str:
        """The heading line to render.

        A part renders its own title; a 章 under a part renders an auto-generated
        ``第N篇·第M章 <stem>`` prefix.  A flat chapter (no part) renders unchanged.
        """
        if self.is_part:
            return self.raw_title
        if self.part_title:
            prefix = (
                f"第{_cn_number(self.part_index)}篇·"
                f"第{_cn_number(self.chapter_index)}章"
            )
            stem = _strip_numbered_prefix(self.raw_title)
            return f"{prefix} {stem}".strip() if stem else prefix
        return self.raw_title


def _strip_numbered_prefix(title: str) -> str:
    """Remove a leading Chinese/arabic 第X章/第X篇… number so the auto-generated
    篇·章 prefix is not duplicated."""
    text = _HEADING_MARK_RE.sub("", str(title or "")).strip()
    text = re.sub(
        r"^第\s*[一二三四五六七八九十百千万〇零两0-9１-９]+\s*(?:章|篇|单元|部分|卷|部|分)\s*",
        "",
        text,
    )
    return text.strip()


def _cn_number(value: int) -> str:
    """Render *value* as a Chinese numeral for the 篇/章 prefix (supports 1..99)."""
    digits = "一二三四五六七八九"
    value = max(1, int(value))
    if value <= 9:
        return digits[value - 1]
    if value <= 19:
        return "十" + (digits[value - 11] if value > 10 else "")
    tens, ones = divmod(value, 10)
    text = digits[tens - 1] + "十"
    if ones:
        text += digits[ones - 1]
    return text


def _split_part_chapters(source: str) -> list[ExportChapter]:
    """Split *source* into renderable part / chapter segments.

    Walks the markdown line by line.  A heading whose unit is a coarse part word
    (篇/单元/卷/部分) opens a new part; a ``第X章`` heading opens a content chapter
    under the current part (chapter numbers restart at 1 per part).  Other lines
    accumulate into the open chapter's body.  Content that appears before any
    heading is returned as a leading chapter with an empty title (no section
    header), matching the flat ``_split_chapters`` behaviour.

    Returns a flat list of :class:`ExportChapter` in document order; the part
    headings are emitted as part chapters (``is_part``) so the caller can place a
    page break / part header at those points.  When the document has no part
    heading, every content heading is returned as a plain chapter with ``is_part``
    False and no part prefix — identical output to ``_split_chapters``.
    """

    lines = (str(source or "")).split("\n")
    segments: list[ExportChapter] = []

    def _flush_part() -> None:
        if _pending_part is not None:
            segments.append(_pending_part)

    # Current open part heading / current open content chapter (or None).
    _pending_part: ExportChapter | None = None
    open_chapter: ExportChapter | None = None
    open_part_title = ""
    open_part_index = 0
    chapter_counter = 0
    has_any_heading = False

    preamble_lines: list[str] = []

    def _push_chapter() -> None:
        nonlocal chapter_counter
        # Commit a part heading first so ordering stays correct.
        if _pending_part is not None and open_chapter is None:
            pass

    for line in lines:
        unit = _heading_unit(line)
        if unit:
            has_any_heading = True
            text = _HEADING_MARK_RE.sub("", line).strip()
            if _is_part_unit(unit):
                # Close the current content chapter and open a new part.
                if open_chapter is not None:
                    segments.append(open_chapter)
                    open_chapter = None
                _flush_part()
                _pending_part = ExportChapter(raw_title=text, body="", is_part=True)
                open_part_title = text
                open_part_index += 1
                chapter_counter = 0
            else:
                # A content 章 heading.
                if _pending_part is not None:
                    _flush_part()
                    _pending_part = None
                if open_chapter is not None:
                    segments.append(open_chapter)
                chapter_counter += 1
                open_chapter = ExportChapter(
                    raw_title=text,
                    body="",
                    is_part=False,
                    part_title=open_part_title,
                    part_index=open_part_index,
                    chapter_index=chapter_counter,
                )
            continue
        # A body line.
        if open_chapter is not None:
            open_chapter = _with_body_line(open_chapter, line)
        elif _pending_part is not None:
            # Part headings don't carry body; fold into a leading empty chapter so
            # nothing between the title and the first chapter is lost.
            segments.append(_pending_part)
            _pending_part = None
            open_chapter = ExportChapter(
                raw_title="",
                body=line,
                is_part=False,
                part_title=open_part_title,
                part_index=open_part_index,
                chapter_index=0,
            )
        else:
            preamble_lines.append(line)

    if open_chapter is not None:
        segments.append(open_chapter)
    _flush_part()

    # Leading content before any heading is a preamble chapter (empty title).
    result: list[ExportChapter] = []
    preamble = "\n".join(preamble_lines).strip("\n")
    if preamble:
        result.append(ExportChapter(raw_title="", body=preamble, is_part=False))
    result.extend(segments)
    return result


def _with_body_line(chapter: ExportChapter, line: str) -> ExportChapter:
    return ExportChapter(
        raw_title=chapter.raw_title,
        body=(chapter.body + "\n" + line).strip("\n"),
        is_part=chapter.is_part,
        part_title=chapter.part_title,
        part_index=chapter.part_index,
        chapter_index=chapter.chapter_index,
    )


def _has_part_structure(source: str) -> bool:
    """True when *source* contains a coarse part heading that nests 章 beneath it.
    """
    segments = _split_part_chapters(source)
    return any(segment.is_part for segment in segments)


# Baseline: an A4 portrait single-column page with Word's default margins
# (top/bottom 25.4 mm, left/right 31.7 mm) holds roughly this many CJK
# characters at the typical 小四 (12 pt) body size. The estimate below scales
# this baseline by the usable page area and column count.
_BASELINE_CHARS_PER_PAGE = 700
_DEFAULT_MARGIN_TOP_MM = 25.4
_DEFAULT_MARGIN_BOTTOM_MM = 25.4
_DEFAULT_MARGIN_LEFT_MM = 31.7
_DEFAULT_MARGIN_RIGHT_MM = 31.7


def estimate_page_count(
    markdown: str,
    page_config: PageConfig | None = None,
) -> int:
    """Return a rough page estimate for ``markdown`` under ``page_config``.

    The estimate is intentionally coarse: it counts CJK characters (plus a
    weighted contribution from each line break and image reference) and scales
    a per-page baseline by usable page area and column count. It is meant for
    a pre-export preview, not an exact pagination.
    """

    config = page_config or PageConfig()
    text = str(markdown or "")

    # Count visible CJK characters (2-byte content) plus one unit per latin
    # word so mixed documents are not wildly underestimated.
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    latin_words = len(re.findall(r"[A-Za-z0-9]+", text))
    line_breaks = text.count("\n")
    # Each image reference stands in for roughly a third of a page of figure.
    image_count = len(re.findall(r"!\[[^\]]*\]\([^)]+\)", text))
    effective_chars = cjk + latin_words * 1.5 + line_breaks * 0.15 + image_count * 230

    width_mm, height_mm = _PAGE_SIZES_MM[config.paper]
    if config.landscape:
        width_mm, height_mm = max(width_mm, height_mm), min(width_mm, height_mm)

    margin_top = config.margin_top_mm if config.margin_top_mm is not None else _DEFAULT_MARGIN_TOP_MM
    margin_bottom = config.margin_bottom_mm if config.margin_bottom_mm is not None else _DEFAULT_MARGIN_BOTTOM_MM
    margin_left = config.margin_left_mm if config.margin_left_mm is not None else _DEFAULT_MARGIN_LEFT_MM
    margin_right = config.margin_right_mm if config.margin_right_mm is not None else _DEFAULT_MARGIN_RIGHT_MM

    usable_width = max(0.0, width_mm - margin_left - margin_right)
    usable_height = max(0.0, height_mm - margin_top - margin_bottom)

    # Baseline usable area for A4 portrait default margins.
    baseline_w = 210.0 - _DEFAULT_MARGIN_LEFT_MM - _DEFAULT_MARGIN_RIGHT_MM
    baseline_h = 297.0 - _DEFAULT_MARGIN_TOP_MM - _DEFAULT_MARGIN_BOTTOM_MM
    baseline_area = baseline_w * baseline_h

    area = usable_width * usable_height
    area_factor = area / baseline_area if baseline_area > 0 else 1.0
    chars_per_page = _BASELINE_CHARS_PER_PAGE * area_factor * max(1, int(config.columns or 1))
    chars_per_page = max(chars_per_page, 1.0)

    return max(1, int(round(effective_chars / chars_per_page))) if effective_chars > 0 else 0


def export_markdown_to_docx(
    markdown: str,
    output_path: str | Path,
    *,
    resource_paths: Mapping[str, str | Path] | None = None,
    page_config: PageConfig | None = None,
) -> Path:
    """Write Markdown headings, lists, inline styles, tables, and images to DOCX.

    ``resource_paths`` maps a markdown image path (relative, posix style, e.g.
    ``images/figure.png``) to the real file on disk to embed.  Any image
    referenced in the Markdown must be present in this mapping; missing images
    raise :class:`MarkdownDocxExportError` rather than silently dropping them.

    ``page_config`` sets the page geometry (paper size, orientation, column
    count). Defaults to A4 portrait single column. Long documents — hundreds
    of pages — are handled as one flat body stream; Word paginates on open, so
    the exporter itself never materialises page breaks.
    """

    source = str(markdown or "").strip()
    if not source:
        raise MarkdownDocxExportError("Markdown content is empty.")

    # Resolve image references against the provided resource paths.
    resource_paths = {str(k): Path(v) for k, v in (resource_paths or {}).items()}
    referenced = discover_markdown_resource_paths(source)
    resource_id_by_path: dict[str, str] = {}
    resolved_files: dict[str, Path] = {}
    for image_path in referenced:
        candidate = resource_paths.get(image_path)
        if candidate is None:
            # Also allow an absolute/relative direct path fallback keyed by the
            # exact normalized path so callers can pass the bare path.
            candidate = resource_paths.get(image_path.lstrip("./"))
        if candidate is None:
            raise MarkdownDocxExportError(
                f"Image resource not provided: {image_path!r}. "
                "Pass resource_paths mapping image paths to files on disk."
            )
        file_path = Path(candidate).expanduser()
        if not file_path.is_file():
            raise MarkdownDocxExportError(
                f"Image file does not exist: {file_path}"
            )
        # The strict importer requires the resource_id to be a non-empty
        # string; use the normalized image path itself so it round-trips back
        # to the resolved file below.
        resource_id_by_path[image_path] = image_path
        resolved_files[image_path] = file_path

    config = page_config or PageConfig()

    # Fold ``^^说明^^`` into the preceding image's title so captions written
    # independently of the Markdown image syntax still become figure captions.
    source = _fold_inline_caption_syntax(source)

    # Number captioned figures and rewrite ``[[图:标题]]`` cross-references in
    # the body to their real ``图 N`` labels before parsing.
    figure_numbering, source = _build_figure_numbering(source)

    target = Path(str(output_path)).expanduser()
    if target.suffix.casefold() != ".docx":
        target = target.with_suffix(".docx")
    target.parent.mkdir(parents=True, exist_ok=True)

    document = Document()
    _apply_page_config(document, config)

    # An optional cover page occupies the first section; the body chapters
    # then start in a new section so the cover stands alone.
    if config.include_cover:
        _add_cover_page(document, config)

    # Decide how to cut the body into renderable units (each becomes its own
    # section with a page break).  A document that nests coarse part headings
    # (篇/单元/卷/部分) above content 章 uses the part-aware splitter: chapters
    # under a part are numbered 1..N within the part and rendered with an
    # auto-generated 第N篇·第M章 prefix (which becomes the chapter's Heading-1 in
    # the body as well as its page header).  A flat document keeps the plain
    # per-chapter split exactly as before.
    part_segments: list[ExportChapter] | None = None
    if config.chapter_split and _has_part_structure(source):
        part_segments = _split_part_chapters(source)
        # Part headings are not rendered as their own page (no body); they only
        # reset numbering / provide the 篇 prefix carried onto each following 章.
        render_units = [
            (segment.display_title, segment.body, True)
            for segment in part_segments
            if not segment.is_part
        ]
    else:
        render_units = [
            (title, body, False)
            for title, body in (
                _split_chapters(source) if config.chapter_split else [("", source)]
            )
        ]

    def _parse_fragment(chapter_source: str):
        try:
            return parse_markdown_content(
                chapter_source,
                resource_id_by_path=resource_id_by_path,
            )
        except MarkdownImportError as exc:
            diagnostic = exc.diagnostic
            if diagnostic.code in {"resource_not_declared", "resource_manifest_mismatch"}:
                raise MarkdownDocxExportError(
                    "Image references must match the resource_paths mapping: "
                    + diagnostic.message
                ) from exc
            raise MarkdownDocxExportError(str(exc)) from exc

    all_image_jobs = []
    try:
        for index, (title, chapter_source, render_heading) in enumerate(render_units):
            if index > 0 or config.include_cover:
                # A new-page section break separates chapters (and, when a
                # cover is present, separates the body from the cover); each
                # section may carry its own header below.  Because the first
                # content chapter of each part starts its own new section, a
                # nested 篇 document also visually starts each 篇 on a new page.
                document.add_section(WD_SECTION.NEW_PAGE)
                _apply_page_config_to_section(document.sections[-1], config)

            # For a part-aware chapter, inject the generated 篇N·第M章 title as a
            # real Heading-1 line so the number is visible in the body (the bare
            # source heading is stripped by the splitter and rebuilt here).
            fragment_source = chapter_source
            if render_heading and title:
                fragment_source = f"# {title}\n\n{chapter_source}".strip()
            fragment = _parse_fragment(fragment_source)
            content_id = f"marktext_markdown_{index}"
            rule = ContentInsertionRule(
                rule_id=f"marktext-markdown-export-{index}",
                content_id=content_id,
                anchor_token=content_anchor_token(content_id),
            )
            document.add_paragraph(rule.anchor_token)
            receipt = render_document_fragment(document, fragment, rule)
            all_image_jobs.extend(receipt.image_job_drafts)

            # Independent per-chapter header (chapter title centred at the top).
            if config.per_chapter_header and title:
                section = document.sections[-1]
                # Sections after the first inherit the previous header by
                # default; unlink so this chapter's header stands alone.  With
                # a cover page, even the first chapter sits in a new section and
                # must not inherit the cover's (empty) header.
                if index > 0 or config.include_cover:
                    section.header.is_linked_to_previous = False
                _set_header_footer(section.header, title)

        _embed_images(
            document,
            all_image_jobs,
            resolved_files,
            figure_numbering,
            config.image_quality,
        )
        document.save(str(target))
        # Verify the package before claiming that export succeeded.
        Document(str(target))
    except MarkdownDocxExportError:
        target.unlink(missing_ok=True)
        raise
    except Exception as exc:  # noqa: BLE001 - export boundary
        target.unlink(missing_ok=True)
        raise MarkdownDocxExportError(f"DOCX export failed: {exc}") from exc
    return target


_FIGURE_CAPTION_RE = re.compile(r"""!\[[^\]]*\]\([^)]*?\s+["']([^"']+)["']\)""")
_FIGURE_REF_RE = re.compile(r"\[\[图:([^\]]+)\]\]")
# An image followed (same line or next line) by ``^^说明^^`` marks the
# figure caption independently of the Markdown image title, so the AI can
# annotate a picture without overloading the ``title`` attribute.
_INLINE_CAPTION_RE = re.compile(
    r"(!\[[^\]]*\]\([^)]*\))\s*(?:\n\s*)?\^\^([^^\n]+)\^\^"
)


def _fold_inline_caption_syntax(source: str) -> str:
    """Fold ``^^说明^^`` into the preceding image's ``title`` attribute.

    ``![alt](src) ^^说明^^`` (or on the following line) becomes
    ``![alt](src "说明")`` so the existing caption pipeline treats it as the
    figure caption.  Keeps the ``^^…^^`` markers out of the rendered body.
    """

    def _fold(match: "re.Match[str]") -> str:
        image_token = match.group(1)
        caption = match.group(2).strip()
        if not caption:
            return match.group(0)
        # A caption containing a double quote would break the title syntax;
        # fall back to single quotes in that case.
        quote = "'" if '"' in caption else '"'
        # Insert the title *inside* the image's parentheses, before the closing
        # ``)``, so the Markdown importer reads it as the image title.
        return image_token[:-1] + f' {quote}{caption}{quote}' + image_token[-1]

    return _INLINE_CAPTION_RE.sub(_fold, str(source or ""))


def _build_figure_numbering(source: str) -> tuple[dict[str, int], str]:
    """Number figures with captions and rewrite ``[[图:标题]]`` cross-refs.

    Scans the Markdown in document order, assigning ``图 1``, ``图 2``… to
    every image carrying a ``title`` (the caption).  A body reference written
    as ``[[图:标题]]`` is replaced with the matching ``图 N``; an unmatched
    reference is left untouched so it stays visible instead of silently
    dropping.

    Returns ``(caption_to_number, rewritten_source)``.
    """

    caption_to_number: dict[str, int] = {}
    counter = 0
    for match in _FIGURE_CAPTION_RE.finditer(str(source or "")):
        caption = match.group(1).strip()
        if not caption or caption in caption_to_number:
            continue
        counter += 1
        caption_to_number[caption] = counter

    def _substitute(match: "re.Match[str]") -> str:
        caption = match.group(1).strip()
        number = caption_to_number.get(caption)
        if number is None:
            return match.group(0)
        return f"图 {number}"

    rewritten = _FIGURE_REF_RE.sub(_substitute, str(source or ""))
    return caption_to_number, rewritten


def _add_cover_page(document: Document, config: PageConfig) -> None:
    """Write a centred cover page (title / subtitle / date) as the first section.

    The cover occupies the document's initial section; the body chapters start
    in a new section (with a page break) so the cover stands alone.
    """

    def _centred(text: str, *, size_pt: float, bold: bool = False, space_after_pt: float = 0) -> None:
        para = document.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(text)
        run.bold = bold
        run.font.size = Pt(size_pt)
        para.paragraph_format.space_after = Pt(space_after_pt)

    # Vertical padding so the title sits roughly a third of the way down.
    for _ in range(6):
        document.add_paragraph()

    title = (config.cover_title or "").strip()
    if title:
        _centred(title, size_pt=26, bold=True, space_after_pt=6)
    subtitle = (config.cover_subtitle or "").strip()
    if subtitle:
        _centred(subtitle, size_pt=16, bold=False, space_after_pt=24)
    date_text = (config.cover_date or "").strip()
    if date_text:
        _centred(date_text, size_pt=12, bold=False)


def _apply_page_config(document: Document, config: PageConfig) -> None:
    """Apply page geometry to the first section (convenience wrapper)."""

    _apply_page_config_to_section(document.sections[0], config)


def _apply_page_config_to_section(section, config: PageConfig) -> None:
    """Apply paper size, orientation, margins, columns, and header/footer.

    python-docx exposes page width/height/orientation directly; the column
    layout (``w:cols``) has no python-docx API, so it is written to the
    section's ``w:sectPr`` directly.
    """

    width_mm, height_mm = _PAGE_SIZES_MM[config.paper]
    if config.landscape:
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width = Mm(max(width_mm, height_mm))
        section.page_height = Mm(min(width_mm, height_mm))
    else:
        section.orientation = WD_ORIENT.PORTRAIT
        section.page_width = Mm(width_mm)
        section.page_height = Mm(height_mm)

    # Optional page margins (millimetres); None keeps python-docx's defaults.
    if config.margin_top_mm is not None:
        section.top_margin = Mm(config.margin_top_mm)
    if config.margin_bottom_mm is not None:
        section.bottom_margin = Mm(config.margin_bottom_mm)
    if config.margin_left_mm is not None:
        section.left_margin = Mm(config.margin_left_mm)
    if config.margin_right_mm is not None:
        section.right_margin = Mm(config.margin_right_mm)

    columns = max(1, int(config.columns or 1))
    sect_pr = section._sectPr
    if columns > 1:
        cols = sect_pr.find(qn("w:cols"))
        if cols is None:
            cols = sect_pr.makeelement(qn("w:cols"), {})
            sect_pr.append(cols)
        cols.set(qn("w:num"), str(columns))
        # Column gutter in twips (1 mm ≈ 56.6929 twips). Default 720 twips
        # (0.5 inch) when no explicit spacing is supplied.
        spacing_twips = 720
        if config.column_spacing_mm is not None:
            spacing_twips = max(0, int(round(config.column_spacing_mm * 56.6929)))
        cols.set(qn("w:space"), str(spacing_twips))
        cols.set(qn("w:equalWidth"), "1")

    # Optional header / footer text, centred on every page of the section.
    if config.header_text:
        _set_header_footer(section.header, config.header_text)
    if config.footer_text:
        _set_header_footer(section.footer, config.footer_text)
    # Optional automatic「第 X 页 共 Y 页」page-number field.
    if config.footer_page_number:
        _set_page_number_footer(section.footer)
        _apply_page_number_restart(section, restart=config.footer_page_restart)


def _set_header_footer(part, text: str) -> None:
    """Write centred header/footer text to a section's header/footer part.

    ``part`` is a ``_Header`` / ``_Footer`` object from python-docx. A single
    centred paragraph keeps the call minimal and Word-compatible; callers pass
    plain text (no field codes) so no escaping is required.
    """

    paragraph = part.paragraphs[0]
    paragraph.text = text
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER


def _set_page_number_footer(part) -> None:
    """Write a centred「第 X 页 共 Y 页」auto field to a section's footer.

    ``X`` is the PAGE field and ``Y`` the NUMPAGES field, so Word renumbers
    automatically.  Numbering restart is applied separately at the section
    level via ``_apply_page_number_restart``.
    """

    paragraph = part.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for child in list(paragraph._p):
        if child.tag != qn("w:pPr"):
            paragraph._p.remove(child)

    def _run(text: str) -> None:
        run = paragraph.add_run(text)
        run.font.size = Pt(9)

    _run("第 ")

    page_field = OxmlElement("w:fldSimple")
    page_field.set(qn("w:instr"), " PAGE ")
    page_run = OxmlElement("w:r")
    page_text = OxmlElement("w:t")
    page_text.text = "1"
    page_run.append(page_text)
    page_field.append(page_run)
    paragraph._p.append(page_field)

    _run(" 页 共 ")

    total_field = OxmlElement("w:fldSimple")
    total_field.set(qn("w:instr"), " NUMPAGES ")
    total_run = OxmlElement("w:r")
    total_text = OxmlElement("w:t")
    total_text.text = "1"
    total_run.append(total_text)
    total_field.append(total_run)
    paragraph._p.append(total_field)

    _run(" 页")


def _apply_page_number_restart(section, *, restart: bool) -> None:
    """Restart page numbering at 1 for ``section`` when ``restart`` is set."""
    if not restart:
        return
    sect_pr = section._sectPr
    pg_num_type = sect_pr.find(qn("w:pgNumType"))
    if pg_num_type is None:
        pg_num_type = OxmlElement("w:pgNumType")
        sect_pr.append(pg_num_type)
    pg_num_type.set(qn("w:start"), "1")


def _lossless_jpeg_recompress(
    file_path: Path,
    image,
    original_bytes: int,
) -> Path:
    """Re-save a JPEG with Huffman optimization and EXIF stripped.

    Uses ``quality="keep"`` so the quantisation tables (and therefore the
    decoded pixels) are unchanged — only entropy coding is re-optimised and
    metadata is dropped.  Returns ``file_path`` unchanged when the file was
    already optimised, re-encoding grew it, or saving failed.
    """

    out = file_path.with_name(f"{file_path.stem}_opt.jpg")
    try:
        try:
            image.save(
                out,
                format="JPEG",
                quality="keep",
                optimize=True,
                exif=b"",
            )
        except (OSError, ValueError):
            return file_path
        try:
            if out.stat().st_size >= original_bytes:
                out.unlink(missing_ok=True)
                return file_path
        except OSError:
            pass
        return out
    finally:
        image.close()


def _downsampled_for_embedding(
    file_path: Path,
    image_quality: str = "compressed",
) -> Path:
    """Return a copy of ``file_path`` reduced to a sane resolution for DOCX.

    ``image_quality`` selects one of ``original`` / ``compressed`` / ``high``
    (see ``_IMAGE_QUALITY_PRESETS``).  ``original`` keeps the file untouched;
    ``compressed`` downsamples oversized images; ``high`` downsamples more
    aggressively and re-encodes to a lower-quality JPEG.  JPEG files that need
    no downsampling are still re-encoded losslessly (EXIF stripped, Huffman
    optimised) when the quality preset is not ``original``.  Returns the
    original path when the image is already small, could not be opened, or
    re-encoding offers no benefit.
    """

    preset = _IMAGE_QUALITY_PRESETS.get(
        str(image_quality or "compressed").strip().lower(),
        _IMAGE_QUALITY_PRESETS["compressed"],
    )
    max_edge = preset["max_edge"]
    jpeg_threshold = preset["jpeg_threshold"]
    jpeg_quality = preset["jpeg_quality"]

    from PIL import Image

    try:
        image = Image.open(file_path)
        width, height = image.size
        longest = max(width, height)
        original_bytes = file_path.stat().st_size
        format_name = (image.format or "").upper()
        has_alpha = (
            image.mode in ("RGBA", "LA", "PA")
            or (image.mode == "P" and "transparency" in image.info)
        )
        is_jpeg = format_name == "JPEG" or file_path.suffix.casefold() in {".jpg", ".jpeg"}
    except (OSError, ValueError):
        return file_path

    # ``original`` keeps the source file verbatim (no resizing, no re-encode).
    if max_edge is None:
        image.close()
        return file_path

    # No resizing needed. JPEGs still get a lossless re-encode (EXIF stripped,
    # Huffman optimised); everything else is returned untouched.
    if longest <= max_edge:
        if is_jpeg and not has_alpha:
            return _lossless_jpeg_recompress(file_path, image, original_bytes)
        image.close()
        return file_path

    try:
        image.load()
        scale = max_edge / longest
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        resized = image.resize(new_size, Image.LANCZOS)
    finally:
        image.close()
    del image

    use_jpeg = (
        jpeg_threshold is not None
        and longest > jpeg_threshold
        and format_name in {"JPEG", "PNG", "BMP", "WEBP"}
        and not has_alpha
    )
    if not use_jpeg:
        # Downsampled but keep the original (lossless) format. A JPEG that is
        # downsampled (but below the re-encode threshold) still gets Huffman
        # optimization and EXIF stripping on the resized copy.
        suffix = file_path.suffix or ".png"
        out = file_path.with_name(f"{file_path.stem}_resized{suffix}")
        try:
            if suffix.casefold() == ".png":
                resized.save(out, format="PNG", optimize=True)
            elif suffix.casefold() in {".jpg", ".jpeg"}:
                resized.save(out, format="JPEG", quality="keep", optimize=True, exif=b"")
            else:
                resized.save(out)
            if out.stat().st_size >= original_bytes:
                out.unlink(missing_ok=True)
                return file_path
            return out
        except OSError:
            return file_path

    # Re-encode as a flattened JPEG.
    if has_alpha:
        background = Image.new("RGB", resized.size, (255, 255, 255))
        background.paste(resized, mask=resized.split()[-1])
        resized = background
    else:
        resized = resized.convert("RGB")
    out = file_path.with_name(f"{file_path.stem}_resized.jpg")
    try:
        resized.save(out, format="JPEG", quality=jpeg_quality or 85, optimize=True, exif=b"")
        if out.stat().st_size >= original_bytes:
            out.unlink(missing_ok=True)
            return file_path
        return out
    except OSError:
        return file_path


def _embed_images(
    document,
    image_jobs,
    resolved_files: Mapping[str, Path],
    figure_numbering: Mapping[str, int] | None = None,
    image_quality: str = "compressed",
) -> None:
    """Replace each image sentinel paragraph with a real inline picture."""

    if not image_jobs:
        return
    marker_to_file = {
        job.stable_marker_id: resolved_files.get(job.resource_id)
        for job in image_jobs
    }
    marker_to_caption = {
        job.stable_marker_id: (job.caption or "").strip()
        for job in image_jobs
    }
    numbering = figure_numbering or {}
    for paragraph in list(document.paragraphs):
        marker = _sentinel_marker(paragraph)
        if not marker or marker not in marker_to_file:
            continue
        file_path = marker_to_file[marker]
        if file_path is None:
            continue
        # Process images one at a time and dispose of the temporary file as
        # soon as it is embedded.  Accumulating hundreds of temp files (and the
        # decoded pixel buffers they represent) would balloon memory on
        # very long documents; cleaning up inline keeps the peak footprint
        # bounded to roughly one image at a time.
        embedded = _downsampled_for_embedding(file_path, image_quality)
        try:
            _replace_sentinel_with_picture(paragraph, embedded)
            caption = marker_to_caption.get(marker, "")
            if caption:
                number = numbering.get(caption)
                _append_caption_paragraph(document, paragraph, caption, number)
        finally:
            if embedded != file_path:
                embedded.unlink(missing_ok=True)


def _sentinel_marker(paragraph) -> str:
    """Return the hidden marker text of a sentinel paragraph, else ``""``."""

    runs = list(paragraph._p.findall(qn("w:r")))
    for run in runs:
        rpr = run.find(qn("w:rPr"))
        if rpr is not None and rpr.find(qn("w:vanish")) is not None:
            text = run.find(qn("w:t"))
            if text is not None and text.text:
                return text.text
    return ""


def _replace_sentinel_with_picture(paragraph, file_path: Path) -> None:
    """Swap a sentinel paragraph for one containing the inline picture."""

    run = paragraph.add_run()
    run.add_picture(str(file_path), width=Cm(_MAX_IMAGE_WIDTH_CM))
    # Drop the hidden sentinel run (bookmark + vanished marker text) so the
    # paragraph only carries the image.
    for child in list(paragraph._p):
        if child.tag in {qn("w:bookmarkStart"), qn("w:bookmarkEnd")}:
            continue
        if child.tag == qn("w:r"):
            rpr = child.find(qn("w:rPr"))
            if rpr is not None and rpr.find(qn("w:vanish")) is not None:
                paragraph._p.remove(child)


def _append_caption_paragraph(
    document,
    image_paragraph,
    caption: str,
    number: int | None = None,
) -> None:
    """Insert a centered caption paragraph directly after an image paragraph.

    When ``number`` is given the caption is prefixed with the figure label
    (``图 N ``) so captioned figures are numbered in document order.
    """

    label = f"图 {number}  {caption}" if number else caption
    caption_paragraph = document.add_paragraph(label)
    caption_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = caption_paragraph.runs[0]
    run.italic = True
    run.font.size = Pt(9)
    # Move the caption paragraph to sit right after the image paragraph.
    image_paragraph._p.addnext(caption_paragraph._p)


__all__ = [
    "MarkdownDocxExportError",
    "PageConfig",
    "estimate_page_count",
    "export_markdown_to_docx",
]
