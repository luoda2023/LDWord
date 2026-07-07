from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_retained_gap_exit_criteria_audit import (  # noqa: E402
    build_scene_retained_gap_exit_criteria_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the retained-gap exit criteria audit.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    args = parser.parse_args(argv)

    report = build_scene_retained_gap_exit_criteria_audit_report(
        project_root=ROOT
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
