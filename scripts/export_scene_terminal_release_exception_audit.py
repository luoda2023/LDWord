from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.export_scene_audit import (  # noqa: E402
    run_registered_scene_audit_export,
)


def main(argv: list[str] | None = None) -> int:
    return run_registered_scene_audit_export(
        "scene_terminal_release_exception_audit",
        argv,
        description="Export the N2.383 terminal release exception audit.",
        markdown_formatter=_report_markdown,
    )


def _report_markdown(report) -> str:
    payload = report.to_payload()
    counts = payload["counts"]
    lines = [
        "# Scene Terminal Release Exception Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Governed exceptions: {counts['governed_exception_count']}/{counts['exception_count']}",
        f"- Managed warnings: {counts['managed_warning_count']}",
        f"- Warning projections: {counts['warning_projection_count']}",
        f"- Readiness reconciliations: {counts['readiness_reconciliation_count']}",
        f"- Boundary-guarded maturity: {counts['boundary_guarded_maturity_count']}",
        f"- Static-closed boundaries: {counts['static_closed_boundary_count']}",
        f"- Exception traces: {counts['exception_trace_count']}",
        f"- Unique source traces: {counts['unique_source_trace_count']}",
        f"- Linked boundary subjects: {counts['linked_boundary_subject_count']}",
        f"- Ungoverned exceptions: {counts['ungoverned_exception_count']}",
        f"- Issues: {counts['issue_count']}",
        "",
        "| Exception | Kind | Observed | Governed | Traces | Status | Sources | Evidence | Issues |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.exception_id),
                    _escape_markdown(row.exception_kind),
                    str(row.observed_count),
                    str(row.governed_count),
                    str(row.trace_count),
                    _escape_markdown(row.status),
                    _escape_markdown(_join_values(row.source_ids) or "-"),
                    _escape_markdown(_join_values(row.evidence_ids) or "-"),
                    _escape_markdown(_join_values(row.issue_ids) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Source Evidence", ""])
    for evidence in report.source_evidence:
        lines.append(
            "- "
            f"`{evidence.source_id}`: {evidence.status} "
            f"({evidence.source_path}; markers={_join_values(evidence.markers)})"
        )
    if report.issues:
        lines.extend(["", "## Issues", ""])
        for issue in report.issues:
            lines.append(f"- `{issue.exception_id}` / `{issue.kind}`: {issue.message}")
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
