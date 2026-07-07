from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_family_subscene_audit import (  # noqa: E402
    build_scene_family_subscene_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export the N2.158 scene-family subscene completeness audit as JSON "
            "or Markdown."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument(
        "--output",
        help="Optional output file. Defaults to stdout.",
    )
    parser.add_argument(
        "--family",
        default="",
        help="Filter by planned scene family id.",
    )
    args = parser.parse_args(argv)

    report = build_scene_family_subscene_audit_report(family_id=args.family)
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
    lines = [
        "# Scene Family Subscene Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Families: {payload['family_count']}",
        f"- Issues: {payload['issue_count']}",
        f"- Warnings: {payload['warning_count']}",
        f"- Family request cells: {payload['request_cell_count']}",
        f"- Direct family fixtures: {payload['direct_family_fixture_count']}",
        f"- Manual-boundary families: {payload['manual_boundary_family_count']}",
        "",
        (
            "| Family | Status | Priority | Packs | Cells | Direct | Manual | "
            "Fixtures | Defaults | Plugin Boundary | Issues | Warnings |"
        ),
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.family_id),
                    _escape_markdown(row.status),
                    _escape_markdown(row.priority),
                    str(len(row.pack_ids)),
                    str(row.request_cell_count),
                    str(row.direct_request_cell_count),
                    str(row.manual_boundary_request_cell_count),
                    str(row.sample_fixture_count),
                    _escape_markdown(row.application_default_delivery_preset_id or "-"),
                    "yes" if row.plugin_boundary_only else "no",
                    _escape_markdown(_join_values(row.issue_ids) or "-"),
                    _escape_markdown(_join_values(row.warning_ids) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Family Evidence", ""])
    for row in report.rows:
        lines.append(f"### {row.family_id}")
        lines.append(f"- packs: {_join_values(row.pack_ids) or '-'}")
        lines.append(
            f"- request cells: {_join_values(row.request_cell_sample_ids) or '-'}"
        )
        lines.append(f"- fixtures: {_join_values(row.sample_fixture_ids) or '-'}")
        lines.append(
            f"- manual boundary fixtures: "
            f"{_join_values(row.manual_boundary_fixture_ids) or '-'}"
        )
        lines.append(f"- rule sources: {_join_values(row.rule_source_ids) or '-'}")
        lines.append(f"- plugin gates: {_join_values(row.plugin_gate_ids) or '-'}")
    if report.issues:
        lines.extend(["", "## Issues", ""])
        for issue in report.issues:
            lines.append(
                f"- `{issue.family_id}` / `{issue.kind}`: {issue.message}"
            )
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in report.warnings:
            lines.append(
                f"- `{warning.family_id}` / `{warning.kind}`: {warning.message}"
            )
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
