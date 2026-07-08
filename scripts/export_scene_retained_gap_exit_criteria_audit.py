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
        "scene_retained_gap_exit_criteria_audit",
        argv,
        description="Export the retained-gap exit criteria audit.",
        markdown_formatter=_report_markdown,
    )


def _report_markdown(report) -> str:
    payload = report.to_payload()
    counts = payload["counts"]
    lines = [
        "# Scene Retained Gap Exit Criteria Audit",
        "",
        f"- Status: {payload['status']}",
        (
            f"- Release allowed: {counts['release_allowed_count']}/"
            f"{counts['criteria_count']}"
        ),
        (
            f"- Receipt alignment: {counts['external_receipt_alignment_count']}/"
            f"{counts['criteria_count']}"
        ),
        f"- External receipt targets: {counts['external_receipt_target_count']}",
        f"- Exit signals: {counts['exit_signal_count']}",
        f"- Prohibited core claims: {counts['prohibited_core_claim_count']}",
        f"- Issues: {counts['issue_count']}",
        "",
        (
            "| Criteria | Subject | Gap | Status | Boundary Capability | "
            "External Receipts | Exit Signals | Prohibited Claims | Issues |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape(row.criteria_id),
                    _escape(f"{row.subject_type}:{row.subject_id}"),
                    _escape(row.gap_id),
                    _escape(row.status),
                    _escape(_join(row.boundary_capability_ids)),
                    _escape(_join(row.external_receipt_ids)),
                    _escape(_join(row.exit_signal_ids)),
                    _escape(_join(row.prohibited_core_claim_ids)),
                    _escape(_join(row.issue_ids) or "-"),
                ]
            )
            + " |"
        )
    if report.issues:
        lines.extend(["", "## Issues", ""])
        for issue in report.issues:
            lines.append(
                f"- `{issue.criteria_id}` / `{issue.kind}`: {issue.message}"
            )
    lines.extend(["", "## Source Evidence", ""])
    for evidence in report.source_evidence:
        marker_count = len(evidence.markers)
        lines.append(
            f"- `{evidence.source_id}`: {evidence.status} "
            f"({evidence.source_path}; markers={marker_count})"
        )
    return "\n".join(lines)


def _join(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
