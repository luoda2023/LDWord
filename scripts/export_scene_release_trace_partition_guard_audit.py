from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_release_trace_partition_guard_audit import (  # noqa: E402
    build_scene_release_trace_partition_guard_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the N2.387 release-trace partition guard audit.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    args = parser.parse_args(argv)

    report = build_scene_release_trace_partition_guard_audit_report(
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
