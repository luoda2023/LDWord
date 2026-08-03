"""Markdown semantics and release guardrails for exam-owned DOCX output.

The exam terminal assembler owns final Word layout, so generic pipeline modules
cannot safely run after it.  This module supplies the missing content compiler
boundary: exam fields are parsed through the shared Markdown IR before the
exam renderer writes native Word runs and tables.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
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
class ExamMarkdownContentFinding:
    """One field-level semantic finding discovered before Word rendering."""

    path: str
    kind: str
    message: str
    severity: str = "warning"


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

_EXAM_INLINE_ANSWER_BLANK_RE = re.compile(r"(?<![\\_])_{4,}(?!_)")
_RECOVERABLE_INLINE_ERROR_CODES = frozenset({"inline_nesting_invalid"})
_RECOVERABLE_INLINE_MARKER_RE = re.compile(r"(?<!\\)(?:\*{1,3}|_{1,3}|~{2})")
_LONG_LATIN_WORD_RE = re.compile(r"[A-Za-z]{5,}")


def compile_exam_markdown(
    value: object,
    *,
    field_path: str,
) -> DocumentFragment:
    """Compile one exam-owned text field through the shared Markdown parser."""

    fragment, _findings = compile_exam_markdown_with_findings(
        value,
        field_path=field_path,
    )
    return fragment


def compile_exam_markdown_with_findings(
    value: object,
    *,
    field_path: str,
) -> tuple[DocumentFragment, tuple[ExamMarkdownContentFinding, ...]]:
    """Compile an exam field, degrading presentation-only syntax when safe.

    Long ASCII underscore runs are an established exam authoring convention for
    answer blanks.  CommonMark may pair several such runs as nested emphasis, so
    normalize them to visually equivalent full-width underscores before parsing.
    If unsupported nested emphasis remains, remove only the presentation markers
    and retain the field content as a reviewable plain-text rendering.
    """

    text = str(value or "").strip()
    if not text:
        return DocumentFragment(blocks=()), ()
    try:
        return parse_markdown_content(text, source_path=field_path), ()
    except MarkdownImportError as exc:
        diagnostic = exc.diagnostic
        if diagnostic.code in _RECOVERABLE_INLINE_ERROR_CODES:
            normalized = _normalize_exam_inline_answer_blanks(text)
            if normalized != text:
                try:
                    fragment = parse_markdown_content(
                        normalized,
                        source_path=field_path,
                    )
                except MarkdownImportError:
                    pass
                else:
                    return fragment, ()
            fallback = _strip_recoverable_inline_markers(normalized)
            try:
                fragment = parse_markdown_content(fallback, source_path=field_path)
            except MarkdownImportError:
                pass
            else:
                return fragment, (
                    ExamMarkdownContentFinding(
                        path=field_path,
                        kind="inline_format_degraded",
                        message=(
                            "Unsupported nested inline formatting was rendered as "
                            "plain text; document delivery can continue."
                        ),
                    ),
                )
        raise ExamMarkdownContentError(
            "exam_markdown_invalid:"
            f"{field_path}:{diagnostic.code}:{diagnostic.message}"
        ) from exc


def inspect_exam_markdown_payload(
    payload: Mapping[str, object] | object,
) -> tuple[ExamMarkdownContentFinding, ...]:
    """Compile every Word-visible exam field before execution begins."""

    if not isinstance(payload, Mapping):
        return (
            ExamMarkdownContentFinding(
                path="payload",
                kind="markdown_payload_invalid",
                message="Exam payload must be an object.",
                severity="error",
            ),
        )
    findings: list[ExamMarkdownContentFinding] = []
    sections = payload.get("sections")
    if not isinstance(sections, Sequence) or isinstance(sections, (str, bytes)):
        return ()
    for section_index, section in enumerate(sections):
        if not isinstance(section, Mapping):
            continue
        questions = section.get("questions")
        if not isinstance(questions, Sequence) or isinstance(
            questions,
            (str, bytes),
        ):
            continue
        for question_index, question in enumerate(questions):
            if not isinstance(question, Mapping):
                continue
            prefix = f"sections.{section_index}.questions.{question_index}"
            for field_name, field_value in _exam_question_markdown_fields(question):
                path = f"{prefix}.{field_name}"
                try:
                    _fragment, field_findings = compile_exam_markdown_with_findings(
                        field_value,
                        field_path=path,
                    )
                except ExamMarkdownContentError as exc:
                    findings.append(
                        ExamMarkdownContentFinding(
                            path=path,
                            kind="markdown_semantic_invalid",
                            message=str(exc),
                            severity="error",
                        )
                    )
                else:
                    findings.extend(field_findings)
    findings.extend(_inspect_unexpected_foreign_text(payload))
    return tuple(findings)


def _inspect_unexpected_foreign_text(
    payload: Mapping[str, object],
) -> tuple[ExamMarkdownContentFinding, ...]:
    """Flag likely foreign-language contamination in a Chinese exam.

    Pinyin syllables are normally short, while accidental model leakage tends
    to contain several longer Latin words in one field. This remains a review
    warning so candidate Word files are still delivered.
    """

    subject = str(payload.get("subject") or "").strip()
    if "语文" not in subject:
        return ()
    findings: list[ExamMarkdownContentFinding] = []
    sections = payload.get("sections")
    if not isinstance(sections, Sequence) or isinstance(sections, (str, bytes)):
        return ()
    for section_index, section in enumerate(sections):
        if not isinstance(section, Mapping):
            continue
        questions = section.get("questions")
        if not isinstance(questions, Sequence) or isinstance(
            questions,
            (str, bytes),
        ):
            continue
        for question_index, question in enumerate(questions):
            if not isinstance(question, Mapping):
                continue
            prefix = f"sections.{section_index}.questions.{question_index}"
            for field_name, field_value in _exam_question_markdown_fields(question):
                if field_name not in {"lead_in", "stem"} and not field_name.startswith(
                    "options."
                ):
                    continue
                long_words = _LONG_LATIN_WORD_RE.findall(str(field_value or ""))
                if len(long_words) < 2:
                    continue
                findings.append(
                    ExamMarkdownContentFinding(
                        path=f"{prefix}.{field_name}",
                        kind="unexpected_foreign_text_in_chinese_exam",
                        message=(
                            "Chinese-language exam content contains multiple long "
                            "Latin words; delivery can continue as a review candidate."
                        ),
                    )
                )
    return tuple(findings)


def _exam_question_markdown_fields(
    question: Mapping[str, object],
) -> tuple[tuple[str, object], ...]:
    fields: list[tuple[str, object]] = []
    for field_name in (
        "lead_in",
        "stem",
        "answer",
        "analysis",
        "knowledge_points",
    ):
        value = question.get(field_name)
        if str(value or "").strip():
            fields.append((field_name, value))
    options = question.get("options") or question.get("choices")
    if isinstance(options, Mapping):
        for option_index, (key, value) in enumerate(options.items()):
            option = f"{str(key).strip()}. {str(value).strip()}".strip()
            if option:
                fields.append((f"options.{option_index}", option))
    elif isinstance(options, Sequence) and not isinstance(options, (str, bytes)):
        fields.extend(
            (f"options.{option_index}", option)
            for option_index, option in enumerate(options)
            if str(option or "").strip()
        )
    elif str(options or "").strip():
        fields.append(("options.0", options))
    return tuple(fields)


def _normalize_exam_inline_answer_blanks(text: str) -> str:
    return _EXAM_INLINE_ANSWER_BLANK_RE.sub(
        lambda match: "＿" * len(match.group(0)),
        str(text or ""),
    )


def _strip_recoverable_inline_markers(text: str) -> str:
    cleaned = _RECOVERABLE_INLINE_MARKER_RE.sub("", str(text or ""))
    return re.sub(r"\\([*_~`])", r"\1", cleaned)


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
