"""Markdown semantics and release guardrails for exam-owned DOCX output.

The exam terminal assembler owns final Word layout, so generic pipeline modules
cannot safely run after it.  This module supplies the missing content compiler
boundary: exam fields are parsed through the shared Markdown IR before the
exam renderer writes native Word runs and tables.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from docx.document import Document as DocumentType
from docx.text.paragraph import Paragraph

from src.config.content_materials import DocumentFragment
from src.shared.engine.markdown_importer import (
    MarkdownImportError,
    parse_markdown_content,
)

MARKDOWN_HORIZONTAL_RULE_TEXT = "\u2500" * 8


class ExamMarkdownContentError(ValueError):
    """Raised when one exam field cannot be compiled into safe semantic IR."""


@dataclass(frozen=True, slots=True)
class ExamMarkdownResidue:
    location: str
    kind: str
    text: str


_RESIDUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("fenced_code", re.compile(r"^\s*(?:`{3,}|~{3,})", re.MULTILINE)),
    (
        "table_separator",
        re.compile(
            r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?",
            re.MULTILINE,
        ),
    ),
    ("pipe_noise", re.compile(r"^\s*\|{3,}", re.MULTILINE)),
    (
        "table_row",
        re.compile(r"^\s*\|(?:[^|\r\n]*\|){2,}", re.MULTILINE),
    ),
    ("horizontal_rule", re.compile(r"^\s*(?:\*{3,}|-{3,})\s*$", re.MULTILINE)),
    (
        "strong",
        re.compile(
            r"(?<!\\)\*\*(?=\S).+?(?<=\S)(?<!\\)\*\*"
            r"|(?<![\\_])__(?=\S)(?!_).+?(?<=\S)(?<![\\_])__(?!_)"
        ),
    ),
    ("strikethrough", re.compile(r"(?<!\\)~~(?=\S).+?(?<=\S)(?<!\\)~~")),
    ("inline_code", re.compile(r"(?<!\\)`[^`\r\n]+(?<!\\)`")),
    ("image", re.compile(r"!\[[^\]\r\n]*\]\([^)\r\n]+\)")),
    ("link", re.compile(r"(?<!!)\[[^\]\r\n]+\]\([^)\r\n]+\)")),
    ("heading", re.compile(r"^\s*#{1,6}\s+\S", re.MULTILINE)),
    ("emphasis_noise", re.compile(r"^\s*(?:\*{1,2}|_{1,2}|~{1,2})\s*$", re.MULTILINE)),
    ("unclosed_strong_open", re.compile(r"(?:^|\s)\*\*(?=\S)")),
    ("unclosed_strong_close", re.compile(r"(?<=\S)\*\*(?:\s|$)")),
)


def compile_exam_markdown(
    value: object,
    *,
    field_path: str,
) -> DocumentFragment:
    """Compile one exam-owned text field through the shared Markdown parser."""

    text = str(value or "").strip()
    if not text:
        return DocumentFragment(blocks=())
    try:
        return parse_markdown_content(text, source_path=field_path)
    except MarkdownImportError as exc:
        diagnostic = exc.diagnostic
        raise ExamMarkdownContentError(
            "exam_markdown_invalid:"
            f"{field_path}:{diagnostic.code}:{diagnostic.message}"
        ) from exc


def find_exam_markdown_residue(
    document: DocumentType,
) -> tuple[ExamMarkdownResidue, ...]:
    """Return unconsumed Markdown syntax from every final Word text surface."""

    findings: list[ExamMarkdownResidue] = []
    seen_elements: set[object] = set()
    for location, paragraph in _iter_document_paragraphs(document):
        element = paragraph._p
        if element in seen_elements:
            continue
        seen_elements.add(element)
        text = str(paragraph.text or "")
        if not text.strip():
            continue
        for kind, pattern in _RESIDUE_PATTERNS:
            if pattern.search(text):
                findings.append(
                    ExamMarkdownResidue(
                        location=location,
                        kind=kind,
                        text=_excerpt(text),
                    )
                )
                break
    return tuple(findings)


def assert_no_exam_markdown_residue(document: DocumentType) -> None:
    findings = find_exam_markdown_residue(document)
    if not findings:
        return
    summary = ";".join(
        f"{item.location}:{item.kind}:{item.text}" for item in findings[:8]
    )
    raise ExamMarkdownContentError(f"exam_markdown_residue:{summary}")


def _iter_document_paragraphs(
    document: DocumentType,
) -> Iterable[tuple[str, Paragraph]]:
    yield from _iter_container_paragraphs(document, "body")
    for section_index, section in enumerate(document.sections, start=1):
        yield from _iter_container_paragraphs(
            section.header,
            f"section.{section_index}.header",
        )
        yield from _iter_container_paragraphs(
            section.first_page_header,
            f"section.{section_index}.first_page_header",
        )
        yield from _iter_container_paragraphs(
            section.footer,
            f"section.{section_index}.footer",
        )
        yield from _iter_container_paragraphs(
            section.first_page_footer,
            f"section.{section_index}.first_page_footer",
        )


def _iter_container_paragraphs(container, prefix: str):
    for index, paragraph in enumerate(getattr(container, "paragraphs", ()), start=1):
        yield f"{prefix}.paragraph.{index}", paragraph
    for table_index, table in enumerate(getattr(container, "tables", ()), start=1):
        for row_index, row in enumerate(table.rows, start=1):
            for cell_index, cell in enumerate(row.cells, start=1):
                cell_prefix = (
                    f"{prefix}.table.{table_index}.row.{row_index}.cell.{cell_index}"
                )
                yield from _iter_container_paragraphs(cell, cell_prefix)


def _excerpt(text: str, limit: int = 120) -> str:
    compact = " ".join(str(text or "").split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "\u2026"
