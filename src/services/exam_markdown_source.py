"""Parse an exam Markdown source as a standalone production input.

The parsed source is merged into the execution configuration by the production
runner.  It is not a mutable material context and never alters a package.
"""

from __future__ import annotations

from pathlib import Path

from src.shared.engine.exam_question_schema import (
    ExamMarkdownImportResult,
    parse_exam_markdown_file,
)


def is_exam_markdown_source_path(source_path: str | Path) -> bool:
    return Path(str(source_path or "").strip()).suffix.lower() in {
        ".md",
        ".markdown",
    }


def load_exam_markdown_source(
    source_path: str | Path,
) -> ExamMarkdownImportResult:
    """Parse one applicable exam Markdown source."""

    path = Path(str(source_path or "").strip())
    if not is_exam_markdown_source_path(path):
        raise ValueError("exam_markdown_source_not_applicable")
    return parse_exam_markdown_file(path)


__all__ = [
    "is_exam_markdown_source_path",
    "load_exam_markdown_source",
]
