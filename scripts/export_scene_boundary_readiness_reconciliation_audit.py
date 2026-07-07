from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_boundary_readiness_reconciliation_audit import (  # noqa: E402
    build_scene_boundary_readiness_reconciliation_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the N2.382 boundary readiness reconciliation audit.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    parser.add_argument("--source", default="", help="Filter by source id.")
    args = parser.parse_args(argv)

    report = build_scene_boundary_readiness_reconciliation_audit_report(
        source_id=args.source,
        project_root=ROOT,
    )
    if args.format == "json":
        content = json.dumps(report.to_payload(), ensure_ascii=False, indent=2)
    else:
        content = _report_markdown(report)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content + "\n", encoding="utf-8")
    else:
        print(content)
    return 0 if report.status == "passed" else 1


def _report_markdown(report) -> str:
    payload = report.to_payload()
    counts = payload["counts"]
    lines = [
        "# Scene Boundary Readiness Reconciliation Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Reconciled rows: {counts['reconciled_count']}/{counts['row_count']}",
        f"- Readiness deltas: {counts['readiness_delta_count']}",
        f"- Not applicable rows: {counts['not_applicable_count']}",
        f"- Static-closed boundary rows: {counts['static_closed_boundary_count']}",
        f"- Boundary-guarded maturity rows: {counts['maturity_boundary_guarded_count']}",
        f"- Boundary subjects: {counts['boundary_subject_count']}",
        f"- Unreconciled rows: {counts['unreconciled_count']}",
        f"- Issues: {counts['issue_count']}",
        "",
        "| Scope | Source | Metric | Observed | Status | Mode | Evidence | Issues |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(f"{row.scope_type}:{row.scope_id}"),
                    _escape_markdown(row.source_id),
                    _escape_markdown(row.metric_id),
                    _escape_markdown(row.observed_status),
                    _escape_markdown(row.status),
                    _escape_markdown(row.reconciliation_mode),
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
            lines.append(f"- `{issue.scope_id}` / `{issue.kind}`: {issue.message}")
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
