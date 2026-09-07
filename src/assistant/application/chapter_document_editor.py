# -*- coding: utf-8 -*-
"""Chapter-scoped document editing for the LDWord assistant.

Phase-A core: open an already formatted document (docx), detect its outline
(headings -> chapter ranges), let the user pick one chapter and ask the model
to improve / rewrite it, then write the revised text back into *only that
chapter's body* while preserving the surrounding layout and the chapter's own
paragraph formatting.

Scope / safety
--------------
- This module never rewrites the source file: every edit produces a new
  output docx next to it (`<stem>.revised.docx`) unless the caller passes an
  explicit ``output_path``.
- Legacy binary formats (.doc/.wps) are converted through the existing
  ``ensure_editable_docx`` service before parsing/editing.  The output is
  always .docx (OOXML), which WPS and Word both open.
- Only paragraph *text* is replaced; paragraph properties (style, numbering,
  indents, spacing, fonts) are cloned from the first original paragraph of the
  chapter body so layout survives.  Tables inside the chapter are left in
  place and their existing text is untouched, avoiding unsafe structural
  rewrites.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from src.modules.structure.heading_recognition import analyze_document_tree


@dataclass(frozen=True)
class DetectedChapter:
    """One editable chapter found in the document outline.

    A document may nest coarser grouping headings (e.g. 篇/部分 at Heading 1)
    above its real content chapters (第X章 at Heading 2).  ``level`` is that
    heading's own outline level; ``part_title`` carries the text of the nearest
    ancestor grouping heading (e.g. the 篇/部分), or ``""`` when the chapter is
    itself at the document's top level.
    """

    index: int
    title: str
    heading_para_index: int
    start_para_index: int
    end_para_index: int  # exclusive; -1 means to end of document body
    level: int
    part_title: str = ""

    @property
    def paragraph_count(self) -> int:
        if self.end_para_index < 0:
            return -1
        return max(0, self.end_para_index - self.start_para_index)


@dataclass(frozen=True)
class ChapterEditRequest:
    chapter_index: int
    revised_markdown: str  # AI-returned chapter body (plain text/markdown-ish)


@dataclass
class ChapterEditReceipt:
    source_path: str
    output_path: str
    chapter_title: str = ""
    chapter_index: int = -1
    replaced_paragraphs: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class ChapterEditError(Exception):
    message: str


@dataclass(frozen=True, slots=True)
class ChapterScore:
    """Completion / quality score for one chapter body."""

    score: int = 0  # 0..100
    grade: str = "待写"  # 待写/进行中/待完善/良好/优秀
    chars: int = 0
    paragraphs: int = 0
    subheadings: int = 0  # 识别到的 x.y 小节行数
    placeholders: int = 0  # “待补充/略/…/TBD”等占位符数量
    reasons: tuple[str, ...] = ()  # 判分依据，供 UI 展示

    def to_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "grade": self.grade,
            "chars": self.chars,
            "paragraphs": self.paragraphs,
            "subheadings": self.subheadings,
            "placeholders": self.placeholders,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class ChapterScoreRequest:
    chapter_index: int
    body_text: str
    outline_titles: tuple[str, ...] = ()  # 期望覆盖的小节/要点


def score_chapter_body(text: str) -> ChapterScore:
    """Heuristic completeness scoring for one chapter's drafted text.

    Deterministic, offline-friendly: rewards length, paragraph structure,
    subsection headings (x.y …), and penalizes placeholder markers.  The UI
    shows the breakdown so the user sees *why* a chapter is 60/100.
    """
    body = str(text or "")
    stripped = body.strip()
    if not stripped:
        return ChapterScore(score=0, grade="待写", chars=0)
    chars = len(stripped.replace("\n", "").replace("\r", "").replace(" ", "").replace("\u3000", ""))
    paragraphs = [
        ln.strip()
        for ln in body.splitlines()
        if ln.strip()
    ]
    para_count = len(paragraphs)
    sub = sum(1 for ln in paragraphs if _SUBSECTION_NUMBER_RE.match(ln))
    placeholder_markers = ("待补充", "待完善", "略。", "此处补充", "TBD", "TODO", "……", "……。")
    placeholders = sum(
        body.count(marker) for marker in placeholder_markers
    )

    reasons: list[str] = []
    score = 0
    # Content volume (max ~45)
    volume = min(45, chars / 140.0 * 45)
    score += volume
    if chars >= 300:
        reasons.append("篇幅充实")
    elif chars >= 100:
        reasons.append("篇幅适中")
    else:
        reasons.append("篇幅偏短")
    # Paragraph structure (max ~15)
    if para_count >= 4:
        score += 15
        reasons.append("段落组织良好")
    elif para_count >= 2:
        score += 8
        reasons.append("段落较少")
    else:
        reasons.append("缺少分段")
    # Subsections (max ~15)
    if sub >= 3:
        score += 15
        reasons.append(f"含 {sub} 个小节")
    elif sub >= 1:
        score += 8
        reasons.append(f"含 {sub} 个小节")
    else:
        reasons.append("无小节标题")
    # Completeness (max ~25)
    if placeholders == 0:
        score += 25
        reasons.append("无待补充占位")
    else:
        score += max(0, 25 - placeholders * 8)
        reasons.append(f"含 {placeholders} 处占位待补充")
    score = int(max(0, min(100, round(score))))

    if score >= 90:
        grade = "优秀"
    elif score >= 75:
        grade = "良好"
    elif score >= 55:
        grade = "待完善"
    else:
        grade = "待补充" if score else "待写"
    return ChapterScore(
        score=score,
        grade=grade,
        chars=chars,
        paragraphs=para_count,
        subheadings=sub,
        placeholders=placeholders,
        reasons=tuple(reasons),
    )


# --------------------------------------------------------------------------
# Outline detection
# --------------------------------------------------------------------------
_CHAPTER_UNIT_RE = re.compile(
    r"^第\s*[一二三四五六七八九十百千万〇零两0-9１-９]+\s*(章|篇|部分|部|卷|单元|节)"
)
_PART_UNITS = ("篇", "部分", "部", "卷", "单元")


def _chapter_unit(text: str) -> str:
    """Return the Chinese unit word (章/篇/部分/…) in a ``第X…`` heading, or ''."""
    match = _CHAPTER_UNIT_RE.match(str(text or "").strip())
    return match.group(1) if match else ""


def _choose_chapter_spine_level(
    body_headings: list,
) -> int | None:
    """Pick which heading level holds the real editable chapters.

    A formatted document may nest coarse grouping headings (篇/部分/卷/单元 at
    Heading 1) above its content chapters (第X章 at Heading 2).  When that
    happens, chapters live at the 章 level rather than the shallowest one, so
    the 章 are not silently dropped by a naive ``level == 1`` filter.

    Rule:
      * start from the shallowest body-heading level;
      * if that shallow layer is a coarse part layer (篇/部分/部/卷/单元) and a
        deeper level holds 第X章 headings, the spine is that 章 level;
      * otherwise the spine is the shallowest level (flat chapter case).
    """
    if not body_headings:
        return None
    units_by_level: dict[int, set[str]] = {}
    for heading in body_headings:
        units_by_level.setdefault(heading.level, set()).add(
            _chapter_unit(heading.text)
        )
    shallowest = min(units_by_level)
    top_units = units_by_level[shallowest]
    top_is_part = bool(top_units & set(_PART_UNITS))
    deeper_chapter_levels = [
        level for level in units_by_level if level > shallowest and "章" in units_by_level[level]
    ]
    if top_is_part and deeper_chapter_levels:
        return min(deeper_chapter_levels)
    return shallowest


def detect_chapter_outline(source_path: str | Path) -> tuple[DetectedChapter, ...]:
    """Detect the editable chapter outline of *source_path*.

    Uses the shared heading-recognition engine (Word styles / outline levels /
    Chinese prefixes).  When a document nests coarse grouping headings (篇/
    部分/卷/单元) above content 章, the returned chapters are the 章 leaf units
    in order, each carrying its parent ``part_title``; flat documents return
    their shallowest (usually Heading 1) chapter level as before.  Chapters are
    ordered by position in the body and each spans until the next heading at
    the same-or-shallower level (a later chapter or part boundary).
    """
    path = Path(str(source_path or "")).expanduser()
    if not path.is_file():
        raise ChapterEditError(f"文档不存在：{path}")
    from docx import Document

    docx_path = _editable_docx_path(path)
    doc = Document(str(docx_path))
    tree = analyze_document_tree(doc)
    body_headings = sorted(
        (heading for heading in tree.headings if heading.text and heading.level >= 1),
        key=lambda item: item.para_index,
    )
    if not body_headings:
        return ()
    spine = _choose_chapter_spine_level(body_headings)
    body_end = len(doc.paragraphs)
    # Boundaries are any heading at the same-or-shallower level than the spine,
    # so a later chapter *and* a coarse part boundary both end the current
    # chapter (avoiding swallowing the next 篇/部分 header into the body).
    chapter_headings = [h for h in body_headings if h.level == spine]
    chapters: list[DetectedChapter] = []
    body_cursor = 0  # walk body_headings once, tracking the active part
    current_part = ""  # persists across chapters until a new shallower header appears
    for i, heading in enumerate(chapter_headings):
        # Advance the cursor to this chapter, remembering the latest shallower
        # heading (its parent part/grouping) that precedes it.
        while body_cursor < len(body_headings) and body_headings[body_cursor].para_index < heading.para_index:
            if body_headings[body_cursor].level < spine:
                current_part = body_headings[body_cursor].text
            body_cursor += 1
        start = heading.para_index
        boundary = next(
            (
                other.para_index
                for other in body_headings
                if other.para_index > heading.para_index and other.level <= spine
            ),
            body_end,
        )
        chapters.append(
            DetectedChapter(
                index=i + 1,
                title=heading.text,
                heading_para_index=heading.para_index,
                start_para_index=start,
                end_para_index=boundary,
                level=heading.level,
                part_title=current_part,
            )
        )
    return tuple(chapters)


def chapter_body_text(
    source_path: str | Path,
    chapter: DetectedChapter,
) -> str:
    """Return the current plain text of one chapter (headings excluded)."""
    path = Path(str(source_path or "")).expanduser()
    from docx import Document

    doc = Document(str(_editable_docx_path(path)))
    lines: list[str] = []
    for para_index in range(chapter.start_para_index + 1, chapter.end_para_index):
        if para_index >= len(doc.paragraphs):
            break
        para = doc.paragraphs[para_index]
        text = (para.text or "").strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def apply_chapter_edit(
    source_path: str | Path,
    request: ChapterEditRequest,
    *,
    output_path: str | Path | None = None,
    outline: tuple[DetectedChapter, ...] | None = None,
) -> ChapterEditReceipt:
    """Rewrite one chapter's body in a copied .docx and save to output_path.

    * ``outline`` may be supplied from a prior :func:`detect_chapter_outline`
      to avoid re-scanning; otherwise it is detected here.
    * Only paragraphs strictly after the chapter heading and before the next
      chapter heading are replaced.  The heading paragraph itself is kept.
    * Each replacement paragraph clones the paragraph properties of the first
      original body paragraph so the document keeps its visual identity.
    """
    path = Path(str(source_path or "")).expanduser()
    if not path.is_file():
        raise ChapterEditError(f"文档不存在：{path}")

    from copy import deepcopy

    from docx import Document

    docx_path = _editable_docx_path(path)
    chapters = outline if outline is not None else detect_chapter_outline(docx_path)
    match = next(
        (c for c in chapters if c.index == request.chapter_index),
        None,
    )
    if match is None:
        raise ChapterEditError(
            f"找不到第 {request.chapter_index} 章（共 {len(chapters)} 章）"
        )

    doc = Document(str(docx_path))
    body_paras = doc.paragraphs
    body_count = len(body_paras)
    if match.start_para_index >= body_count:
        raise ChapterEditError("章节起始位置超出文档范围")

    # Resolve the exclusive end paragraph index for this chapter.
    end_index = match.end_para_index
    if end_index < 0 or end_index > body_count:
        end_index = body_count
    body_start = match.start_para_index + 1
    body_end = min(end_index, body_count)
    if body_start >= body_end:
        raise ChapterEditError("该章没有可替换的正文段落")

    # Preserve the source run style of the first body paragraph as the base.
    template_element = deepcopy(body_paras[body_start]._element)
    _strip_runs_keep_pPr(template_element)

    # Collect heading-styled paragraphs that belong to this chapter, in order,
    # so rewritten subsection headings (x.y ...) can be re-inserted with their
    # original heading style instead of the chapter body paragraph style.
    subheading_elements: list = []
    for para_index in range(body_start, body_end):
        para = body_paras[para_index]
        if _is_heading_paragraph(para):
            clone = deepcopy(para._element)
            _strip_runs_keep_pPr(clone)
            subheading_elements.append(clone)

    # Remove every paragraph in the chapter body (after heading, before next
    # chapter).  Paragraphs are removed bottom-up to keep indices stable.
    for para_index in range(body_end - 1, body_start - 1, -1):
        element = body_paras[para_index]._element
        parent = element.getparent()
        if parent is not None:
            parent.remove(element)

    # Insert the rewritten body after the heading paragraph.
    heading_element = doc.paragraphs[match.heading_para_index]._element
    anchor = heading_element
    inserted = 0
    for raw_line in _split_revision_lines(request.revised_markdown):
        if not raw_line.strip():
            continue
        new_element = deepcopy(template_element)
        _set_paragraph_text(new_element, raw_line.strip())
        anchor.addnext(new_element)
        anchor = new_element
        inserted += 1

    # Re-stamp subsection-heading lines using the collected heading clones.
    # A rewritten line that starts with a numeric subsection number (x.y ...) is
    # matched positionally to the next unused original heading clone so the
    # subsection keeps its real heading style.
    heading_cursor = 0
    for para_element in _inserted_paragraph_elements(heading_element):
        text = _paragraph_text(para_element)
        if not text or not _looks_like_subsection_number(text):
            continue
        if heading_cursor >= len(subheading_elements):
            break
        styled = subheading_elements[heading_cursor]
        heading_cursor += 1
        _swap_paragraph_payload(para_element, styled, text)

    output = (
        Path(str(output_path or "")).expanduser()
        if output_path is not None
        else path.with_name(f"{path.stem}.revised.docx")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output))
    return ChapterEditReceipt(
        source_path=str(path),
        output_path=str(output),
        chapter_title=match.title,
        chapter_index=match.index,
        replaced_paragraphs=inserted,
    )


# --------------------------------------------------------------------------
# internal helpers
# --------------------------------------------------------------------------
def _editable_docx_path(path: Path) -> Path:
    suffix = path.suffix.casefold()
    if suffix == ".docx":
        return path
    if suffix in {".doc", ".wps"}:
        from src.services.legacy_word_import import ensure_editable_docx

        return ensure_editable_docx(path).docx_path
    raise ChapterEditError(f"暂不支持该文档格式：{suffix}")


def _split_revision_lines(markdown: str) -> list[str]:
    """Split AI-returned chapter body into logical paragraph lines.

    ``#`` heading lines are kept as text lines (they will be inserted with the
    chapter's own body style; the chapter heading itself is not replaced).
    Blank lines delimit paragraphs.
    """
    text = str(markdown or "")
    paragraphs: list[str] = []
    buffer: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            if buffer:
                paragraphs.append("\n".join(buffer))
                buffer = []
            continue
        buffer.append(line.strip())
    if buffer:
        paragraphs.append("\n".join(buffer))
    return paragraphs or []


def _strip_runs_keep_pPr(element) -> None:
    """Remove all runs (and their inline markup) from a paragraph element,
    keeping paragraph properties (style/numbering/spacing/indents)."""
    from src.shared.engine.ooxml_ops import qn

    for child in list(element):
        tag = child.tag
        if tag == qn("w:pPr"):
            continue
        if tag in {
            qn("w:r"),
            qn("w:hyperlink"),
            qn("w:proofErr"),
            qn("w:bookmarkStart"),
            qn("w:bookmarkEnd"),
            qn("w:commentRangeStart"),
            qn("w:commentRangeEnd"),
        }:
            element.remove(child)


def _set_paragraph_text(element, text: str) -> None:
    """Set a single-run text on a paragraph element that already has pPr only."""
    from src.shared.engine.ooxml_ops import qn

    run = element.makeelement(qn("w:r"), {})
    run_text = element.makeelement(qn("w:t"), {})
    run_text.text = str(text or "")
    run.append(run_text)
    element.append(run)




_SUBSECTION_NUMBER_RE = __import__("re").compile(
    r"^\s*\d+(?:\.\d+)+[\s\u3000\u3001、．.．]"
)


def _is_heading_paragraph(para) -> bool:
    """True when the paragraph carries a Heading/标题 style or outline level."""
    from src.shared.engine.style_resolver import get_heading_level

    return get_heading_level(para) is not None


def _looks_like_subsection_number(text: str) -> bool:
    return bool(_SUBSECTION_NUMBER_RE.match(str(text or "").strip()))


def _paragraph_text(element) -> str:
    from src.shared.engine.ooxml_ops import qn

    chunks: list[str] = []
    for run in element.iter(qn("w:t")):
        if run.text:
            chunks.append(run.text)
    return "".join(chunks).strip()


def _inserted_paragraph_elements(after_element) -> list:
    """Return sibling paragraph elements that follow *after_element* until the
    document body ends (assumes no other body content interleaves)."""
    from src.shared.engine.ooxml_ops import qn

    collected: list = []
    node = after_element.getnext()
    while node is not None:
        if node.tag == qn("w:p"):
            collected.append(node)
        node = node.getnext()
    return collected


def _swap_paragraph_payload(target, styled_template, text: str) -> None:
    """Replace target paragraph element with a clone of styled_template that
    carries *text*, keeping XML siblings in place."""
    from copy import deepcopy

    from src.shared.engine.ooxml_ops import qn

    new_element = deepcopy(styled_template)
    _set_paragraph_text(new_element, text)
    parent = target.getparent()
    if parent is not None:
        parent.replace(target, new_element)



__all__ = [
    "ChapterEditError",
    "ChapterScore",
    "ChapterScoreRequest",
    "score_chapter_body",
    "ChapterEditReceipt",
    "ChapterEditRequest",
    "DetectedChapter",
    "apply_chapter_edit",
    "chapter_body_text",
    "detect_chapter_outline",
]
