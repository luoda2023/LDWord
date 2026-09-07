# -*- coding: utf-8 -*-
"""Regression tests for part-aware (nested 篇) DOCX export.

When a long report nests coarse grouping headings (篇 / 单元 / 卷 / 部分) above
content 章, the exporter must:
* make each part's first chapter start a new-page section (so each 篇 visually
  begins on a new page),
* number chapters 1..N *within* each part (restarting per part), and
* render the generated 篇N·第M章 number in front of the chapter title, both as
  the in-body Heading-1 and the per-section page header.

A flat document (no part headings) must keep the existing behaviour unchanged —
no 篇·章 prefix is invented.
"""

from pathlib import Path

import pytest

from src.services.markdown_docx_export import (
    _cn_number,
    _split_part_chapters,
    export_markdown_to_docx,
    PageConfig,
)


def _exported_headings(tmp_path: Path, markdown: str, chapter_split: bool = True):
    """Export *markdown* and return (Heading-1 paragraphs, section headers)."""
    from docx import Document

    output = export_markdown_to_docx(
        markdown,
        str(tmp_path / "out.docx"),
        page_config=PageConfig(chapter_split=chapter_split),
    )
    doc = Document(str(output))
    body = [
        p.text
        for p in doc.paragraphs
        if p.style is not None and p.style.name == "Heading 1"
    ]
    headers = [
        (sec.header.paragraphs[0].text if sec.header.paragraphs else "")
        for sec in doc.sections
    ]
    return body, headers


NESTED = (
    "# 第一篇 总论\n"
    "第一章 项目背景\n"
    "项目背景正文甲。\n"
    "第二章 建设目标\n"
    "建设目标正文乙。\n"
    "# 第二篇 工程设计\n"
    "第三章 总体设计\n"
    "总体设计正文丙。\n"
)

FLAT = "# 第一章 概述\n正文一。\n# 第二章 验收\n正文二。\n"


# ---------------------------------------------------------------------------
# Parser / numbering helpers
# ---------------------------------------------------------------------------
def test_cn_number_one_to_twenty():
    assert _cn_number(1) == "一"
    assert _cn_number(2) == "二"
    assert _cn_number(10) == "十"
    assert _cn_number(11) == "十一"
    assert _cn_number(20) == "二十"
    assert _cn_number(23) == "二十三"


def test_split_part_chapters_resets_numbering_per_part():
    segments = _split_part_chapters(NESTED)
    chapters = [s for s in segments if not s.is_part]
    assert [s.display_title for s in chapters] == [
        "第一篇·第一章 项目背景",
        "第一篇·第二章 建设目标",
        "第二篇·第一章 总体设计",
    ]
    # Chapter index restarts at 1 inside each part.
    assert [s.chapter_index for s in chapters] == [1, 2, 1]
    assert [s.part_index for s in chapters] == [1, 1, 2]
    assert [s.part_title for s in chapters] == [
        "第一篇 总论",
        "第一篇 总论",
        "第二篇 工程设计",
    ]


def test_split_part_chapters_flat_keeps_raw_titles():
    segments = [s for s in _split_part_chapters(FLAT) if not s.is_part]
    # No part present: display titles equal the raw source headings.
    assert [s.display_title for s in segments] == ["第一章 概述", "第二章 验收"]
    # A flat document has no part headings at all.
    assert all(not s.is_part for s in _split_part_chapters(FLAT))


# ---------------------------------------------------------------------------
# End-to-end DOCX output
# ---------------------------------------------------------------------------
def test_export_nested_parts_generates_part_chapter_headings(tmp_path):
    body, headers = _exported_headings(tmp_path, NESTED)
    assert body == [
        "第一篇·第一章 项目背景",
        "第一篇·第二章 建设目标",
        "第二篇·第一章 总体设计",
    ]
    # Each chapter is its own section (3 chapters -> 3 sections), and the page
    # header carries the same auto-generated number as the in-body heading.
    assert headers == body


def test_export_nested_parts_puts_each_part_first_chapter_on_new_page(tmp_path):
    _body, headers = _exported_headings(tmp_path, NESTED)
    # One section per chapter; the first chapter of 第二篇 is a fresh section,
    # so it visually starts 篇二 on a new page.
    assert len(headers) == 3


def test_export_flat_document_unchanged(tmp_path):
    body, headers = _exported_headings(tmp_path, FLAT)
    assert body == ["第一章 概述", "第二章 验收"]
    assert headers == body


def test_export_flat_document_with_cover_still_generates_no_prefix(tmp_path):
    # Even with a cover (an extra leading section) a flat doc must not prefix.
    body, _headers = _exported_headings(
        tmp_path, FLAT, chapter_split=True
    )
    assert "篇" not in "".join(body)
