from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_boundary_subject_release_continuity_audit import (  # noqa: E402
    build_scene_boundary_subject_release_continuity_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the N2.389 boundary-subject release-continuity audit.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    args = parser.parse_args(argv)

    report = build_scene_boundary_subject_release_continuity_audit_report(
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
        "# Scene Boundary Subject Release Continuity Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Subjects ready: {counts['ready_subject_count']}/{counts['subject_count']}",
        f"- Maturity subjects: {counts['maturity_subject_count']}",
        f"- Guarded completion subjects: {counts['guarded_completion_subject_count']}",
        f"- Readiness reconciliation subjects: {counts['readiness_reconciliation_subject_count']}",
        f"- Terminal release subjects: {counts['terminal_release_subject_count']}",
        f"- Subject dossiers: {counts['subject_dossier_count']}",
        f"- Readiness rows: {counts['readiness_row_count']}",
        f"- Terminal traces: {counts['terminal_trace_count']}",
        f"- Dossier traces: {counts['dossier_trace_count']}",
        f"- Mismatches: {counts['mismatch_count']}",
        f"- Issues: {counts['issue_count']}",
        "",
        "| Subject | Status | Readiness Rows | Terminal Traces | Dossier Traces | Evidence |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.subject_key),
                    _escape_markdown(row.status),
                    str(len(row.readiness_row_ids)),
                    str(len(row.terminal_trace_ids)),
                    str(len(row.dossier_trace_ids)),
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
            lines.append(f"- `{issue.subject_key}` / `{issue.kind}`: {issue.message}")
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
