from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_non_subject_release_trace_attribution_audit import (  # noqa: E402
    build_scene_non_subject_release_trace_attribution_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the N2.386 non-subject release-trace attribution audit.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    args = parser.parse_args(argv)

    report = build_scene_non_subject_release_trace_attribution_audit_report(
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
        "# Scene Non-Subject Release Trace Attribution Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Attributed traces: {counts['attributed_trace_count']}/{counts['trace_count']}",
        f"- Dashboard projection traces: {counts['dashboard_projection_trace_count']}",
        f"- Registry-only profile traces: {counts['registry_only_profile_trace_count']}",
        f"- Plugin/manual pack traces: {counts['plugin_manual_pack_trace_count']}",
        f"- Generic not-applicable traces: {counts['generic_not_applicable_trace_count']}",
        f"- Unattributed traces: {counts['unattributed_trace_count']}",
        f"- Issues: {counts['issue_count']}",
        "",
        "| Trace | Exception | Attribution | Scope | Status | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.trace_id),
                    _escape_markdown(row.terminal_exception_id),
                    _escape_markdown(row.attribution_kind),
                    _escape_markdown(f"{row.scope_type}:{row.scope_id}"),
                    _escape_markdown(row.status),
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
            lines.append(f"- `{issue.trace_id}` / `{issue.kind}`: {issue.message}")
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
