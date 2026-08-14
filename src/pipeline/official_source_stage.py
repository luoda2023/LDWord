"""Pipeline stage for conservatively formatting an existing official DOCX."""

from __future__ import annotations

from dataclasses import dataclass

from src.shared.engine.official_source_formatting import (
    OfficialSourceFormattingResult,
    format_existing_official_document,
)

from .tracker import ChangeTracker


@dataclass(frozen=True, slots=True)
class OfficialSourceStageOutcome:
    result: OfficialSourceFormattingResult | None
    error: str = ""


def execute_official_source_stage(
    document,
    *,
    document_type_id: str,
    tracker: ChangeTracker,
) -> OfficialSourceStageOutcome:
    """Format, audit, and classify the source-formatting stage outcome."""

    try:
        result = format_existing_official_document(
            document,
            document_type_id=document_type_id,
        )
    except Exception as exc:  # noqa: BLE001 - stage converts failures to evidence
        return OfficialSourceStageOutcome(
            result=None,
            error=f"official_source_formatting_failed:{type(exc).__name__}:{exc}",
        )

    warning_summary = ",".join(result.warnings)
    tracker.record(
        rule_name="official_source_formatting",
        target=document_type_id or "official",
        section="input_to_delivery",
        change_type="format",
        before="existing DOCX layout",
        after=(
            f"master={result.master_id}; layout={result.layout_family}; "
            f"roles={len(result.roles)}; paragraphs={result.formatted_paragraph_count}"
            + (f"; warnings={warning_summary}" if warning_summary else "")
        ),
        paragraph_index=-1,
        success=True,
    )
    return OfficialSourceStageOutcome(result=result)


__all__ = ["OfficialSourceStageOutcome", "execute_official_source_stage"]
