"""Parse an exam Markdown source and project it onto material data.

This module owns the non-UI source interpretation shared by workbench previews and
execution-readiness checks.  It deliberately does not decide whether a scene is
an exam scene; callers retain that authoritative work-mode decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.material_context import MaterialExecutionContext
from src.shared.engine.exam_question_schema import (
    ExamMarkdownImportResult,
    exam_markdown_import_entity_data,
    parse_exam_markdown_file,
)


@dataclass(frozen=True, slots=True)
class ExamMarkdownSourceProjection:
    """One parsed source plus the material context derived from it."""

    source_path: Path
    import_result: ExamMarkdownImportResult
    material_context: MaterialExecutionContext


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


def project_exam_markdown_source(
    source_path: str | Path,
    material_context: MaterialExecutionContext,
) -> ExamMarkdownSourceProjection:
    """Parse ``source_path`` and merge its entities beneath explicit user data."""

    path = Path(str(source_path or "").strip())
    import_result = load_exam_markdown_source(path)
    projected_context = material_context.clone()
    imported_entity_data = exam_markdown_import_entity_data(import_result)
    projected_context.entity_data = {
        **imported_entity_data,
        **dict(projected_context.entity_data or {}),
    }
    # A persisted approval snapshot deliberately freezes user/material values.
    # The selected Markdown source is a separate, content-addressed production
    # input that is projected only after that snapshot is restored.  Keep the
    # frozen user values authoritative, while also making the validated source
    # payload visible to downstream schema resolution.  Without this projection
    # a correctly approved generated exam file reaches the runtime as an empty
    # material set and fails the structured-question validator.
    if projected_context.field_values_frozen:
        projected_context.frozen_field_values = {
            **imported_entity_data,
            **dict(projected_context.frozen_field_values or {}),
        }
    return ExamMarkdownSourceProjection(
        source_path=path,
        import_result=import_result,
        material_context=projected_context,
    )


__all__ = [
    "ExamMarkdownSourceProjection",
    "is_exam_markdown_source_path",
    "load_exam_markdown_source",
    "project_exam_markdown_source",
]
