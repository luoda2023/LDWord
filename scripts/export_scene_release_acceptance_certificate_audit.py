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
        "scene_release_acceptance_certificate_audit",
        argv,
        description="Export the N2.394 release acceptance-certificate audit.",
        markdown_formatter=_report_markdown,
    )


def _report_markdown(report) -> str:
    payload = report.to_payload()
    counts = payload["counts"]
    lines = [
        "# Scene Release Acceptance Certificate Audit",
        "",
        f"- Status: {payload['status']}",
        (
            f"- Certificates ready: "
            f"{counts['ready_certificate_count']}/{counts['certificate_count']}"
        ),
        (
            f"- Receipt certificates ready: "
            f"{counts['ready_receipt_certificate_count']}/"
            f"{counts['receipt_certificate_count']}"
        ),
        (
            f"- Requirement dimensions ready: "
            f"{counts['ready_requirement_dimension_count']}/"
            f"{counts['requirement_dimension_count']}"
        ),
        f"- Component reports: {counts['component_report_count']}",
        f"- Expected count matches: {counts['expected_count_match_count']}",
        f"- Issues: {counts['issue_count']}",
        "",
        "| Certificate | Source | Observed | Expected | Status | Summary |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.certificate_id),
                    _escape_markdown(row.source_id),
                    _escape_markdown(row.observed_ratio),
                    _escape_markdown(row.expected_ratio),
                    _escape_markdown(row.status),
                    _escape_markdown(row.summary),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Requirement Dimensions",
            "",
            "| Dimension | Observed | Status | Sources | Requirement |",
            "| --- | ---: | --- | --- | --- |",
        ]
    )
    for row in report.requirement_dimension_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.dimension_id),
                    _escape_markdown(row.observed_ratio),
                    _escape_markdown(row.status),
                    _escape_markdown(_join_values(row.source_ids)),
                    _escape_markdown(row.requirement),
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
            lines.append(
                f"- `{issue.certificate_id}` / `{issue.kind}`: {issue.message}"
            )
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
