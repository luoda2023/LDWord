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
        "scene_release_residual_explanation_audit",
        argv,
        description="Export the N2.393i release residual-explanation audit.",
        markdown_formatter=_report_markdown,
    )


def _report_markdown(report) -> str:
    payload = report.to_payload()
    counts = payload["counts"]
    lines = [
        "# Scene Release Residual Explanation Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Residual explanations covered: {counts['covered_count']}/{counts['row_count']}",
        f"- Count mismatches: {counts['mismatch_count']}",
        f"- Summary marker gaps: {counts['missing_summary_marker_count']}",
        f"- Issues: {counts['issue_count']}",
        "",
        "| Residual | Count | Governed | Marker | Status | Reason |",
        "| --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.residual_id),
                    str(row.residual_count),
                    str(row.governed_count),
                    _escape_markdown(row.summary_marker),
                    _escape_markdown(row.status),
                    _escape_markdown(row.reason),
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
            lines.append(f"- `{issue.residual_id}` / `{issue.kind}`: {issue.message}")
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
