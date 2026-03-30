"""Pipeline execution entry point."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Callable

from docx import Document

from src.config.resolved import ResolvedConfig
from src.config.scene import FormatScopeConfig
from src.modules.base import BaseModule
from src.pipeline.context import PipelineContext
from src.pipeline.result import PipelineResult
from src.shared.engine.field_refresh import (
    document_has_toc,
    refresh_doc_fields_with_word,
)
from src.pipeline.scheduler import (
    topological_sort,
    validate_data_flow,
    validate_schema_contract,
)
from src.pipeline.tracker import ChangeTracker


class Pipeline:
    """Execute registered modules against a document."""

    def __init__(
        self,
        modules: list[BaseModule],
        config: ResolvedConfig,
        *,
        output_dir: str | None = None,
        output_suffix: str = "_new",
        progress_callback: Callable[[int, int, str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        self._config = config
        self._output_dir = Path(output_dir) if output_dir else None
        self._output_suffix = output_suffix
        self._progress_callback = progress_callback
        self._cancel_check = cancel_check
        self._tracker = ChangeTracker()

        self._modules = topological_sort(modules)

        schema_errors = validate_schema_contract(self._modules)
        if schema_errors:
            raise ValueError(
                "Pipeline schema contract validation failed:\n"
                + "\n".join(f"  - {error}" for error in schema_errors)
            )

        data_flow_errors = validate_data_flow(self._modules)
        if data_flow_errors:
            raise ValueError(
                "Pipeline data-flow validation failed:\n"
                + "\n".join(f"  - {error}" for error in data_flow_errors)
            )

    def execute(self, doc_path: str) -> PipelineResult:
        """Run the full pipeline for one .docx file."""
        if self._is_cancelled():
            return self._cancelled_result()

        path = Path(doc_path)
        if not path.exists():
            return PipelineResult(success=False, error=f"File not found: {path}")

        total_steps = len(self._modules) + 3
        step = 0

        self._emit(step, total_steps, "Loading document")
        if self._is_cancelled():
            return self._cancelled_result()

        try:
            doc = Document(str(path))
        except Exception as exc:
            return PipelineResult(success=False, error=f"Failed to open document: {exc}")

        original_doc = copy.deepcopy(doc)
        step += 1

        ctx = PipelineContext(
            source_doc_path=str(path),
            source_doc_dir=str(path.parent),
            format_scope=copy.deepcopy(
                getattr(self._config, "format_scope", None) or FormatScopeConfig()
            ),
        )

        for mod in self._modules:
            if self._is_cancelled():
                return self._cancelled_result()

            self._emit(step, total_steps, f"Running module: {mod.meta.description}")

            try:
                issues = mod.validate(doc, self._config, ctx) or []
                fatal_issues = self._record_validation_issues(mod, issues)
                if fatal_issues:
                    error = (
                        f"Module '{mod.meta.name}' validation failed: "
                        f"{fatal_issues[0].message}"
                    )
                    if self._is_strict_mode():
                        return self._failed_result(
                            error=error,
                            doc=doc,
                            original_doc=original_doc,
                            ctx=ctx,
                        )
                    step += 1
                    continue

                mod.apply(doc, self._config, self._tracker, ctx)
            except Exception as exc:
                self._tracker.record(
                    rule_name=mod.meta.name,
                    target="pipeline",
                    section="global",
                    change_type="error",
                    paragraph_index=-1,
                    success=False,
                    failure_reason=str(exc),
                )
                if self._is_strict_mode():
                    return self._failed_result(
                        error=f"Module '{mod.meta.name}' execution failed: {exc}",
                        doc=doc,
                        original_doc=original_doc,
                        ctx=ctx,
                    )

            step += 1

        if self._is_cancelled():
            return self._cancelled_result()

        self._emit(step, total_steps, "Saving output")
        output_paths = self._save_outputs(doc, path)
        step += 1

        self._emit(step, total_steps, "Completed")
        return self._build_result(
            doc=doc,
            original_doc=original_doc,
            output_paths=output_paths,
            ctx=ctx,
        )

    def _emit(self, current: int, total: int, message: str) -> None:
        if self._progress_callback:
            self._progress_callback(current, total, message)

    def _is_cancelled(self) -> bool:
        if self._cancel_check is None:
            return False
        try:
            return bool(self._cancel_check())
        except Exception:
            return False

    def _is_strict_mode(self) -> bool:
        return bool(getattr(self._config, "strict_mode", False))

    def _cancelled_result(self) -> PipelineResult:
        return PipelineResult(
            success=False,
            tracker=self._tracker,
            failed_items=self._collect_failures(),
            error="Cancelled by user.",
            cancelled=True,
        )

    def _failed_result(
        self,
        *,
        error: str,
        doc: Document | None = None,
        original_doc: Document | None = None,
        ctx: PipelineContext | None = None,
    ) -> PipelineResult:
        return PipelineResult(
            success=False,
            status="failed",
            doc=doc,
            original_doc=original_doc,
            tracker=self._tracker,
            context=ctx,
            failed_items=self._collect_failures(),
            error=error,
        )

    def _collect_failures(self) -> list[dict]:
        return [
            {
                "rule_name": record.rule_name,
                "target": record.target,
                "section": record.section,
                "change_type": record.change_type,
                "paragraph_index": record.paragraph_index,
                "reason": record.failure_reason or "",
            }
            for record in self._tracker.get_failures()
        ]

    def _record_validation_issues(self, mod: BaseModule, issues: list) -> list:
        fatal_issues = []

        for issue in issues:
            is_error = getattr(issue, "level", "") == "error"
            if is_error:
                fatal_issues.append(issue)

            self._tracker.record(
                rule_name=mod.meta.name,
                target=getattr(issue, "location", "") or "validate",
                section="global",
                change_type=f"validate_{getattr(issue, 'level', 'info')}",
                after=getattr(issue, "message", ""),
                paragraph_index=-1,
                success=not is_error,
                failure_reason=getattr(issue, "message", "") if is_error else None,
            )

        return fatal_issues

    def _build_result(
        self,
        *,
        doc: Document,
        original_doc: Document,
        output_paths: dict[str, str],
        ctx: PipelineContext | None = None,
    ) -> PipelineResult:
        failed_items = self._collect_failures()

        if not failed_items:
            return PipelineResult(
                success=True,
                status="success",
                doc=doc,
                original_doc=original_doc,
                tracker=self._tracker,
                context=ctx,
                output_paths=output_paths,
            )

        return PipelineResult(
            success=True,
            status="partial_success",
            doc=doc,
            original_doc=original_doc,
            tracker=self._tracker,
            context=ctx,
            output_paths=output_paths,
            failed_items=failed_items,
            error=f"{len(failed_items)} module operation(s) failed.",
        )

    def _save_outputs(self, doc: Document, src_path: Path) -> dict[str, str]:
        stem = src_path.stem
        suffix = src_path.suffix or ".docx"
        out_dir = self._output_dir or src_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        final_path = out_dir / f"{stem}{self._output_suffix}{suffix}"
        doc.save(str(final_path))
        self._best_effort_refresh_fields(doc, final_path)
        return {"final": str(final_path)}

    def _best_effort_refresh_fields(self, doc: Document, final_path: Path) -> None:
        if not document_has_toc(doc):
            return
        try:
            refresh_doc_fields_with_word(str(final_path), timeout_sec=30)
        except Exception:
            return
