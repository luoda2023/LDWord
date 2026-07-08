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
        "scene_release_trace_partition_guard_audit",
        argv,
        description="Export the N2.387 release-trace partition guard audit.",
        markdown_formatter=_report_markdown,
    )


def _report_markdown(report) -> str:
    payload = report.to_payload()
    counts = payload["counts"]
    lines = [
        "# Scene Release Trace Partition Guard Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Partitions ready: {counts['ready_partition_count']}/{counts['partition_count']}",
        f"- Terminal traces: {counts['terminal_trace_count']}",
        f"- Partitioned traces: {counts['partitioned_trace_count']}/{counts['terminal_trace_count']}",
        f"- Subject traces: {counts['subject_trace_count']}",
        f"- Non-subject traces: {counts['non_subject_trace_count']}",
        f"- Missing traces: {counts['missing_trace_count']}",
        f"- Overlap traces: {counts['overlap_trace_count']}",
        f"- Extra traces: {counts['extra_trace_count']}",
        f"- Issues: {counts['issue_count']}",
        "",
        "| Partition | Status | Traces | Expected | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.partition_id),
                    _escape_markdown(row.status),
                    str(row.trace_count),
                    str(row.expected_trace_count),
                    _escape_markdown(_join_values(row.evidence_ids) or "-"),
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
            lines.append(f"- `{issue.partition_id}` / `{issue.kind}`: {issue.message}")
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
