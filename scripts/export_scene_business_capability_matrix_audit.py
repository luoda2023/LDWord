from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_business_capability_matrix_audit import (  # noqa: E402
    build_scene_business_capability_matrix_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the N2.181 high-level business capability matrix audit.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    parser.add_argument("--capability", default="", help="Filter by capability id.")
    parser.add_argument("--group", default="", help="Filter by capability group id.")
    parser.add_argument("--priority", default="", help="Filter by priority.")
    args = parser.parse_args(argv)

    report = build_scene_business_capability_matrix_audit_report(
        capability_id=args.capability,
        group_id=args.group,
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
    filters = {
        "capability": payload["capability_filter"] or "all",
        "group": payload["group_filter"] or "all",
        "priority": payload["priority_filter"] or "all",
    }
    lines = [
        "# Business Capability Matrix Audit",
        "",
        f"- Status: {payload['status']}",
        (
            "- Capabilities: "
            f"{counts['ready_capability_count']}/"
            f"{counts['capability_count']} ready"
        ),
        (
            "- P1/P1 candidate: "
            f"{counts['high_priority_ready_count']}/"
            f"{counts['high_priority_capability_count']} ready"
        ),
        f"- Boundary capabilities: {counts['boundary_capability_count']}",
        f"- Manual-gate capabilities: {counts['manual_gate_capability_count']}",
        f"- Missing journey groups: {counts['missing_journey_group_count']}",
        f"- Absorbed external records: {counts['adopted_external_record_count']}",
        f"- Filters: {_join_pairs(filters)}",
        "",
        "| Capability | Status | Priority | Group | Packs | Families | Journeys | Missing | Boundary | Records |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.capability_id),
                    _escape_markdown(row.status),
                    _escape_markdown(row.priority),
                    _escape_markdown(row.group_id),
                    _escape_markdown(_join_values(row.pack_ids)),
                    _escape_markdown(_join_values(row.family_ids)),
                    _escape_markdown(_join_values(row.journey_type_ids)),
                    _escape_markdown(_join_values(row.missing_journey_groups)),
                    _escape_markdown(row.boundary_policy),
                    _escape_markdown(_join_values(row.adopted_external_record_ids)),
                ]
            )
            + " |"
        )
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in report.warnings:
            lines.append(
                f"- `{warning.scope_type}:{warning.scope_id}` / "
                f"`{warning.kind}`: {warning.message}"
            )
    if report.issues:
        lines.extend(["", "## Blocking Issues", ""])
        for issue in report.issues:
            lines.append(
                f"- `{issue.scope_type}:{issue.scope_id}` / "
                f"`{issue.kind}`: {issue.message}"
            )
    lines.extend(["", "## Source Evidence", ""])
    for evidence in report.source_evidence:
        lines.append(
            f"- `{evidence.source_id}`: {evidence.status} "
            f"({evidence.source_path}; markers={', '.join(evidence.markers)})"
        )
    return "\n".join(lines)


def _join_pairs(values: dict[str, str]) -> str:
    return ", ".join(f"{key}={value}" for key, value in values.items())


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip()) or "-"


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
