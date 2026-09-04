"""Shared helpers for chapter-aware sequence numbering semantics."""

from __future__ import annotations

from typing import Any


def parse_chapter_numbering_format(numbering_format: str | None) -> tuple[bool, str]:
    raw = str(numbering_format or "chapter.seq").strip().lower().replace(" ", "")
    chapter_formats = {
        "chapter.seq": ".",
        "chapter-seq": "-",
        "chapter:seq": ":",
        "chapter—seq": "—",
        "chapter–seq": "–",
        "chapter_seq": "_",
        "chapter/seq": "/",
        "chapterseq": "",
    }
    if raw in chapter_formats:
        return True, chapter_formats[raw]
    if raw in {"seq", "global"}:
        return False, ""
    return True, "."


def build_heading_chapter_ranges(
    heading_map: dict[int, int],
    total_paragraphs: int,
    *,
    doc_tree: Any | None = None,
) -> list[tuple[int, int, int]]:
    body_start, body_end = _resolve_body_bounds(doc_tree, total_paragraphs)
    if body_end <= body_start:
        return []

    h1_indices = sorted(
        index
        for index, level in heading_map.items()
        if level == 1
        and body_start <= index < body_end
        and _is_body_paragraph(doc_tree, index)
        and not _is_special_title_heading(doc_tree, index)
    )
    if not h1_indices:
        return []

    ranges: list[tuple[int, int, int]] = []
    for index, start in enumerate(h1_indices):
        end = h1_indices[index + 1] - 1 if index + 1 < len(h1_indices) else body_end - 1
        ranges.append((start, end, index + 1))
    return ranges


def resolve_chapter_number(
    para_index: int,
    chapter_ranges: list[tuple[int, int, int]],
) -> int:
    for start, end, chapter_num in chapter_ranges:
        if start <= para_index <= end:
            return chapter_num
    return 0


def _resolve_body_bounds(
    doc_tree: Any | None,
    total_paragraphs: int,
) -> tuple[int, int]:
    if doc_tree is None:
        return (0, total_paragraphs)

    getter = getattr(doc_tree, "get_section", None)
    if not callable(getter):
        return (0, total_paragraphs)

    try:
        body_section = getter("body")
    except Exception:
        return (0, total_paragraphs)

    if body_section is None:
        return (0, total_paragraphs)

    start = max(0, min(int(getattr(body_section, "start_index", 0) or 0), total_paragraphs))
    end = max(start, min(int(getattr(body_section, "end_index", total_paragraphs) or total_paragraphs), total_paragraphs))
    return (start, end)


def _is_body_paragraph(doc_tree: Any | None, para_index: int) -> bool:
    if doc_tree is None:
        return True

    getter = getattr(doc_tree, "get_section_for_paragraph", None)
    if not callable(getter):
        return True

    try:
        section_type = getter(para_index)
    except Exception:
        return False

    return str(section_type or "").strip().lower() == "body"


def _is_special_title_heading(doc_tree: Any | None, para_index: int) -> bool:
    if doc_tree is None:
        return False

    getter = getattr(doc_tree, "get_special_title_match", None)
    if not callable(getter):
        return False

    try:
        return bool(getter(para_index))
    except Exception:
        return False
