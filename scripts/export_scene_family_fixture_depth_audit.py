from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_family_fixture_depth_audit import (  # noqa: E402
    build_scene_family_fixture_depth_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the N2.164 family fixture-depth audit.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    parser.add_argument("--family", default="", help="Filter by family id.")
    parser.add_argument("--priority", default="", help="Filter by priority.")
    args = parser.parse_args(argv)

    report = build_scene_family_fixture_depth_audit_report(
        family_id=args.family,
        priority=args.priority,
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
        "# Scene Family Fixture Depth Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Families: {counts['family_count']}",
        f"- P1 required: {counts['p1_family_count']}",
        f"- P1 ready: {counts['p1_ready_count']}",
        f"- Independent fixture families: {counts['independent_family_fixture_count']}",
        f"- Manual-boundary fixture families: {counts['manual_boundary_fixture_family_count']}",
        f"- Issues: {counts['issue_count']}",
        "",
        "| Family | Status | Priority | Strategy | Fixtures | Manual Fixtures | Issues |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.family_id),
                    _escape_markdown(row.status),
                    _escape_markdown(row.priority),
                    _escape_markdown(row.fixture_strategy),
                    _escape_markdown(_join_values(row.independent_fixture_ids) or "-"),
                    _escape_markdown(_join_values(row.manual_boundary_fixture_ids) or "-"),
                    _escape_markdown(_join_values(row.issue_ids) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Source Evidence", ""])
    for evidence in report.source_evidence:
        lines.append(
            "- "
            f"`{evidence.evidence_id}`: {evidence.status} "
            f"({evidence.source_path}; markers={_join_values(evidence.markers)})"
        )
    if report.issues:
        lines.extend(["", "## Issues", ""])
        for issue in report.issues:
            lines.append(f"- `{issue.family_id}` / `{issue.kind}`: {issue.message}")
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
