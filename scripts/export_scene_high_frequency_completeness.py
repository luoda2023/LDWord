from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_high_frequency_completeness_audit import (  # noqa: E402
    build_high_frequency_completeness_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export the V27 high-frequency scene completeness audit as JSON "
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
    parser.add_argument("--pack", default="", help="Filter by coverage pack id.")
    args = parser.parse_args(argv)

    report = build_high_frequency_completeness_audit_report(pack_id=args.pack)
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
    coverage_counts = ", ".join(
        f"{item['coverage_level']}={item['count']}"
        for item in payload["coverage_level_counts"]
    )
    lines = [
        "# Scene High-Frequency Completeness Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Pack filter: {payload['pack_filter'] or 'all'}",
        f"- Packs: {payload['pack_count']}",
        f"- Request cells: {counts['request_cell_count']}",
        f"- Sample fixtures: {counts['sample_fixture_count']}",
        f"- Report anchors: {counts['report_anchor_count']}",
        f"- Coverage levels: {coverage_counts}",
        "- Low matched request-cell depth: "
        + (_join_values(payload["low_matched_request_pack_ids"]) or "-"),
        "",
        "| Pack | Status | Cells | Matched | Fixtures | Report | Axes | Workflows | Word Risks | Warnings |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.pack_id),
                    _escape_markdown(row.status),
                    str(row.request_cell_count),
                    str(row.matched_request_cell_count),
                    str(row.sample_fixture_count),
                    _escape_markdown(
                        f"{row.request_cell_report_artifact_name} "
                        f"({row.request_cell_report_anchor_count})"
                    ),
                    _escape_markdown(_join_values(row.capability_axis_ids)),
                    _escape_markdown(_join_values(row.workflow_archetype_ids)),
                    _escape_markdown(_join_values(row.word_risk_surface_ids)),
                    _escape_markdown(_join_values(row.warning_ids) or "-"),
                ]
            )
            + " |"
        )
    if report.issues:
        lines.extend(["", "## Blocking Issues", ""])
        for issue in report.issues:
            lines.append(
                f"- `{issue.pack_id}` / `{issue.kind}`: {issue.message}"
            )
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in report.warnings:
            lines.append(
                f"- `{warning.pack_id}` / `{warning.kind}`: {warning.message}"
            )
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
