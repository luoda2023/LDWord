"""Specialized validation passes used by the document pipeline."""

from __future__ import annotations

from pathlib import Path

from docx import Document

from src.pipeline.context import PipelineContext
from src.shared.engine.application_section_word_limits import (
    inspect_application_section_word_limits,
)
from src.shared.engine.exam_question_schema import (
    build_exam_delivery_runtime,
    exam_delivery_filename_stem,
    inspect_exam_question_schema,
)
from src.shared.engine.journal_citation_schema import inspect_journal_citations
from src.shared.engine.official_numbering_preservation import (
    inspect_official_numbering_preservation,
)
from src.shared.engine.technical_chapter_inventory import (
    inspect_technical_chapter_inventory,
)


class PipelineValidationMixin:
    def _run_exam_question_schema_validation(self, ctx: PipelineContext) -> None:
        result = inspect_exam_question_schema(self._config)
        if str(getattr(result, "status", "") or "") == "not_applicable":
            return
        ctx.exam_question_schema = result
        summary = getattr(result, "summary", None)
        after = (
            f"status={getattr(result, 'status', '') or '-'}; "
            f"sections={int(getattr(summary, 'section_count', 0) or 0)}; "
            f"questions={int(getattr(summary, 'question_count', 0) or 0)}; "
            f"errors={int(getattr(result, 'error_count', 0) or 0)}; "
            f"warnings={int(getattr(result, 'warning_count', 0) or 0)}"
        )
        self._tracker.record(
            rule_name="exam_question_schema",
            target=getattr(result, "schema_id", "") or "exam_items_v1",
            section="input",
            change_type=(
                "schema_validation_warning"
                if getattr(result, "has_issues", False)
                else "schema_validation"
            ),
            before=getattr(result, "source_key", "") or "structured source",
            after=after,
            paragraph_index=-1,
            success=True,
        )

    def _run_exam_delivery_runtime(self, ctx: PipelineContext) -> None:
        result = ctx.exam_question_schema
        if result is None:
            result = inspect_exam_question_schema(self._config)
            if str(getattr(result, "status", "") or "") == "not_applicable":
                return
            ctx.exam_question_schema = result
        runtime_output_dir = self._output_dir or Path(ctx.source_doc_dir or ".")
        runtime = build_exam_delivery_runtime(
            self._config,
            output_dir=runtime_output_dir,
            source_stem=exam_delivery_filename_stem(
                self._config,
                fallback=Path(ctx.source_doc_path or "exam").stem,
            ),
            validation=result,
            master=self._exam_master,
        )
        if str(getattr(runtime, "status", "") or "") == "not_applicable":
            return
        ctx.exam_delivery_runtime = runtime
        self._tracker.record(
            rule_name="exam_delivery_runtime",
            target=getattr(runtime, "schema_id", "") or "exam_items_v1",
            section="input_to_delivery",
            change_type=(
                "exam_delivery_runtime_blocked"
                if getattr(runtime, "status", "") == "blocked"
                else "exam_delivery_runtime"
            ),
            before=getattr(runtime, "source_key", "") or "structured source",
            after=(
                f"status={getattr(runtime, 'status', '') or '-'}; "
                f"preview={getattr(runtime, 'markdown_preview_path', '') or '-'}; "
                f"versions={int(getattr(runtime, 'version_count', 0) or 0)}"
            ),
            paragraph_index=-1,
            success=str(getattr(runtime, "status", "") or "") in {"ok", "warning"},
            failure_reason=(
                None
                if str(getattr(runtime, "status", "") or "") in {"ok", "warning"}
                else str(getattr(runtime, "skipped_reason", "") or "runtime_blocked")
            ),
        )

    def _run_journal_citation_validation(
        self, doc: Document, ctx: PipelineContext
    ) -> None:
        result = inspect_journal_citations(self._config, doc)
        if str(getattr(result, "status", "") or "") == "not_applicable":
            return
        ctx.journal_citations = result
        summary = getattr(result, "summary", None)
        after = (
            f"status={getattr(result, 'status', '') or '-'}; "
            f"references={int(getattr(summary, 'reference_count', 0) or 0)}; "
            f"citations={int(getattr(summary, 'citation_count', 0) or 0)}; "
            f"matched={int(getattr(summary, 'matched_citation_count', 0) or 0)}; "
            f"missing={int(getattr(summary, 'missing_reference_count', 0) or 0)}; "
            f"errors={int(getattr(result, 'error_count', 0) or 0)}; "
            f"warnings={int(getattr(result, 'warning_count', 0) or 0)}"
        )
        self._tracker.record(
            rule_name="journal_citations",
            target=getattr(result, "schema_id", "")
            or "journal_submission_materials_v1",
            section="input",
            change_type=(
                "citation_source_warning"
                if getattr(result, "has_issues", False)
                else "citation_source_validation"
            ),
            before=getattr(result, "source_key", "") or "BibTeX/CSL source",
            after=after,
            paragraph_index=-1,
            success=True,
        )

    def _run_official_numbering_preservation_validation(
        self,
        doc: Document,
        original_doc: Document,
        ctx: PipelineContext,
    ) -> None:
        result = inspect_official_numbering_preservation(
            self._config,
            original_doc=original_doc,
            current_doc=doc,
            heading_map=ctx.heading_map,
            tracker_records=self._tracker.get_all(),
        )
        if str(getattr(result, "status", "") or "") == "not_applicable":
            return
        ctx.official_numbering_preservation = result
        summary = getattr(result, "summary", None)
        after = (
            f"status={getattr(result, 'status', '') or '-'}; "
            f"strategy={getattr(result, 'strategy', '') or '-'}; "
            f"headings={int(getattr(summary, 'heading_count', 0) or 0)}; "
            f"changed_headings={int(getattr(summary, 'changed_heading_count', 0) or 0)}; "
            f"numbering_records={int(getattr(summary, 'heading_numbering_record_count', 0) or 0)}"
        )
        if not getattr(result, "has_issues", False):
            return
        self._tracker.record(
            rule_name="official_numbering_preservation",
            target="numbering.xml",
            section="official_policy",
            change_type="preflight_warning",
            before="official numbering preserve evidence",
            after=after,
            paragraph_index=-1,
            success=True,
        )

    def _run_technical_chapter_inventory_validation(
        self,
        doc: Document,
        ctx: PipelineContext,
    ) -> None:
        result = inspect_technical_chapter_inventory(
            self._config,
            doc,
            doc_tree=ctx.doc_tree,
            heading_map=ctx.heading_map,
        )
        if str(getattr(result, "status", "") or "") == "not_applicable":
            return
        ctx.technical_chapter_inventory = result
        summary = getattr(result, "summary", None)
        after = (
            f"status={getattr(result, 'status', '') or '-'}; "
            f"chapters={int(getattr(summary, 'chapter_count', 0) or 0)}; "
            f"headings={int(getattr(summary, 'heading_count', 0) or 0)}; "
            f"appendix={int(getattr(summary, 'appendix_count', 0) or 0)}; "
            f"tables={int(getattr(summary, 'table_count', 0) or 0)}; "
            f"figures={int(getattr(summary, 'figure_count', 0) or 0)}"
        )
        if not getattr(result, "has_issues", False):
            return
        self._tracker.record(
            rule_name="technical_chapter_inventory",
            target="chapter_inventory",
            section="technical_long_docs",
            change_type="preflight_warning",
            before="technical chapter inventory",
            after=after,
            paragraph_index=-1,
            success=True,
        )

    def _run_application_section_word_limits_validation(
        self,
        doc: Document,
        ctx: PipelineContext,
    ) -> None:
        result = inspect_application_section_word_limits(
            self._config,
            doc,
            doc_tree=ctx.doc_tree,
            heading_map=ctx.heading_map,
        )
        if str(getattr(result, "status", "") or "") == "not_applicable":
            return
        ctx.application_section_word_limits = result
        summary = getattr(result, "summary", None)
        after = (
            f"status={getattr(result, 'status', '') or '-'}; "
            f"matched_sections={int(getattr(summary, 'matched_section_count', 0) or 0)}; "
            f"exceeded={int(getattr(summary, 'exceeded_section_count', 0) or 0)}; "
            f"required_missing={int(getattr(summary, 'required_missing_count', 0) or 0)}"
        )
        if not getattr(result, "has_issues", False):
            return
        self._tracker.record(
            rule_name="application_section_word_limits",
            target="section_limits",
            section="application_reports",
            change_type="preflight_warning",
            before="application section word limit evidence",
            after=after,
            paragraph_index=-1,
            success=True,
        )


__all__ = ["PipelineValidationMixin"]
