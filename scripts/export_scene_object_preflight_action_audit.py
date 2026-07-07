from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_object_preflight_action_audit import (  # noqa: E402
    build_scene_object_preflight_action_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the N2.172 ObjectPreflight action-closure audit.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    parser.add_argument("--target", default="", help="Filter by preflight target id.")
    parser.add_argument("--family", default="", help="Filter by scene family id.")
    args = parser.parse_args(argv)

    report = build_scene_object_preflight_action_audit_report(
        target_id=args.target,
        family_id=args.family,
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
        "target": payload["target_filter"] or "all",
        "family": payload["family_filter"] or "all",
    }
    lines = [
        "# Scene ObjectPreflight Action Audit",
        "",
        f"- Status: {payload['status']}",
        (
            f"- Targets: {counts['ready_target_count']} ready / "
            f"{counts['target_count']} visible"
        ),
        (
            f"- Families: {counts['ready_family_count']} ready / "
            f"{counts['family_count']} visible"
        ),
        (
            f"- Actions: {counts['blockable_target_count']} blockable / "
            f"{counts['skippable_target_count']} skippable / "
            f"{counts['manual_confirmation_target_count']} manual-confirmation"
        ),
        f"- Filters: {_join_pairs(filters)}",
        "",
        "## Target Rows",
        "",
        "| Target | Status | Surfaces | Fixtures | Behaviors | Block families | Skip modules |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.target_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.target_id),
                    _escape_markdown(row.status),
                    _escape_markdown(", ".join(row.word_risk_surface_ids) or "-"),
                    _escape_markdown(", ".join(row.fixture_ids) or "-"),
                    _escape_markdown(", ".join(row.action_behavior_ids) or "-"),
                    _escape_markdown(", ".join(row.block_policy_family_ids) or "-"),
                    _escape_markdown(", ".join(row.skip_module_ids) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Family Rows",
            "",
            "| Family | Status | Mode | Recommended targets | Actual targets | Fixtures |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.family_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.family_id),
                    _escape_markdown(row.status),
                    _escape_markdown(row.preservation_mode),
                    _escape_markdown(", ".join(row.recommended_scan_targets) or "-"),
                    _escape_markdown(", ".join(row.actual_scan_targets) or "-"),
                    _escape_markdown(", ".join(row.fixture_ids) or "-"),
                ]
            )
            + " |"
        )
    if report.issues:
        lines.extend(["", "## Blocking Issues", ""])
        for issue in report.issues:
            lines.append(
                f"- `{issue.scope_type}:{issue.scope_id}` / "
                f"`{issue.kind}`: {issue.message}"
            )
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in report.warnings:
            lines.append(
                f"- `{warning.scope_type}:{warning.scope_id}` / "
                f"`{warning.kind}`: {warning.message}"
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


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
