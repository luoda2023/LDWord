"""Journal rule-source governance stage for the document pipeline."""

from __future__ import annotations

from src.pipeline.context import PipelineContext
from src.shared.engine.journal_rule_source_governance import (
    inspect_journal_rule_source_governance,
)
from src.shared.engine.journal_submission_package import (
    inspect_journal_submission_package,
)


class PipelineJournalGovernanceMixin:
    def _run_journal_rule_source_governance(self, ctx: PipelineContext) -> None:
        result = inspect_journal_rule_source_governance(self._config)
        if str(getattr(result, "status", "") or "") == "not_applicable":
            return
        ctx.journal_rule_source_governance = result
        summary = getattr(result, "summary", None)
        error_count = int(getattr(result, "error_count", 0) or 0)
        after = (
            f"status={getattr(result, 'status', '') or '-'}; "
            f"source={getattr(result, 'rule_source_id', '') or '-'}; "
            f"review={getattr(result, 'review_status', '') or '-'}; "
            f"count_profile={getattr(result, 'count_profile_id', '') or '-'}; "
            "matched_profiles="
            f"{int(getattr(summary, 'matched_count_profile_count', 0) or 0)}; "
            "manual="
            + ("yes" if getattr(result, "manual_confirmation_required", False) else "no")
            + "; "
            f"errors={error_count}; "
            f"warnings={int(getattr(result, 'warning_count', 0) or 0)}"
        )
        self._tracker.record(
            rule_name="journal_rule_source_governance",
            target=getattr(result, "rule_source_id", "") or "journal_rule_source",
            section="rules",
            change_type=(
                "journal_rule_source_error"
                if error_count
                else (
                    "journal_rule_source_warning"
                    if getattr(result, "has_issues", False)
                    else "journal_rule_source_governance"
                )
            ),
            before=getattr(result, "target_journal_name", "") or "reviewed registry",
            after=after,
            paragraph_index=-1,
            success=not bool(error_count),
            failure_reason=(
                "; ".join(
                    str(getattr(issue, "message", "") or "")
                    for issue in getattr(result, "issues", ()) or ()
                    if getattr(issue, "severity", "") == "error"
                )
                or None
            ),
        )

    def _run_journal_submission_package_validation(
        self,
        output_paths: dict[str, str],
        ctx: PipelineContext,
    ) -> None:
        result = inspect_journal_submission_package(
            self._config,
            output_paths=output_paths,
        )
        if str(getattr(result, "status", "") or "") == "not_applicable":
            return
        ctx.journal_submission_package = result
        summary = getattr(result, "summary", None)
        after = (
            f"status={getattr(result, 'status', '') or '-'}; "
            f"required={int(getattr(summary, 'satisfied_required_count', 0) or 0)}/"
            f"{int(getattr(summary, 'required_component_count', 0) or 0)}; "
            f"outputs={int(getattr(summary, 'output_count', 0) or 0)}; "
            f"reports={int(getattr(summary, 'report_enabled_count', 0) or 0)}; "
            f"errors={int(getattr(result, 'error_count', 0) or 0)}; "
            f"warnings={int(getattr(result, 'warning_count', 0) or 0)}"
        )
        self._tracker.record(
            rule_name="journal_submission_package",
            target="delivery_presets",
            section="delivery",
            change_type=(
                "submission_package_warning"
                if getattr(result, "has_issues", False)
                else "submission_package"
            ),
            before=getattr(result, "default_delivery_preset_id", "")
            or "delivery presets",
            after=after,
            paragraph_index=-1,
            success=True,
        )
