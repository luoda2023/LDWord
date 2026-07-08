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
        "scene_boundary_subject_release_dossier_audit",
        argv,
        description="Export the N2.385 boundary-subject release dossier audit.",
        markdown_formatter=_report_markdown,
    )


def _report_markdown(report) -> str:
    payload = report.to_payload()
    counts = payload["counts"]
    lines = [
        "# Scene Boundary Subject Release Dossier Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Ready subjects: {counts['ready_subject_count']}/{counts['subject_count']}",
        f"- Subject traces: {counts['subject_trace_count']}",
        f"- Unique source traces: {counts['unique_source_trace_count']}",
        f"- Readiness reconciliation rows: {counts['readiness_reconciliation_row_count']}",
        f"- Terminal exception kinds: {counts['terminal_exception_count']}",
        f"- Issues: {counts['issue_count']}",
        "",
        "| Subject | Status | Traces | Readiness Rows | Exceptions | Contracts | Gaps |",
        "| --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.subject_key),
                    _escape_markdown(row.status),
                    str(row.subject_trace_count),
                    str(len(row.readiness_reconciliation_row_ids)),
                    _escape_markdown(_join_values(row.terminal_exception_ids) or "-"),
                    _escape_markdown(
                        _join_values(row.external_handoff_contract_ids) or "-"
                    ),
                    _escape_markdown(_join_values(row.retained_gap_ids) or "-"),
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
            lines.append(f"- `{issue.subject_key}` / `{issue.kind}`: {issue.message}")
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
