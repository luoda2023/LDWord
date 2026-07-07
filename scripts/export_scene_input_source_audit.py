from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_input_source_audit import (  # noqa: E402
    build_scene_input_source_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the N2.171 InputSourceProfile scene audit as JSON or Markdown.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    parser.add_argument("--source", default="", help="Filter rows by input source id.")
    parser.add_argument("--family", default="", help="Filter rows by family id.")
    parser.add_argument("--pack", default="", help="Filter rows by coverage pack id.")
    args = parser.parse_args(argv)

    report = build_scene_input_source_audit_report(
        source_id=args.source,
        family_id=args.family,
        pack_id=args.pack,
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
        "source": payload["source_filter"] or "all",
        "family": payload["family_filter"] or "all",
        "pack": payload["pack_filter"] or "all",
    }
    lines = [
        "# Scene InputSourceProfile Audit",
        "",
        f"- Status: {payload['status']}",
        (
            f"- Families: {counts['ready_family_count']} ready / "
            f"{counts['family_count']} visible"
        ),
        (
            f"- Packs: {counts['ready_input_pack_count']} ready / "
            f"{counts['input_pack_count']} input-source packs"
        ),
        (
            f"- Sources: {counts['accepted_format_count']} accepted formats / "
            f"{counts['structured_format_count']} structured formats / "
            f"{counts['boundary_input_source_count']} boundary sources"
        ),
        (
            f"- Rendering: {counts['render_source_count']} render sources / "
            f"{counts['target_template_count']} target templates"
        ),
        f"- Filters: {_join_pairs(filters)}",
        "",
        "## Family Rows",
        "",
        "| Family | Status | Packs | Planned inputs | Actual inputs | Structured | Material | Rendering |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.family_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.family_id),
                    _escape_markdown(row.status),
                    _escape_markdown(", ".join(row.pack_ids) or "-"),
                    _escape_markdown(", ".join(row.planned_input_formats) or "-"),
                    _escape_markdown(", ".join(row.actual_accepted_formats) or "-"),
                    _escape_markdown(", ".join(row.structured_formats) or "-"),
                    _escape_markdown(", ".join(row.actual_material_schema_ids) or "-"),
                    _escape_markdown(", ".join(row.render_source_ids) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Source Rows",
            "",
            "| Source | Status | Kind | Families | Packs | Gates |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.format_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.source_id),
                    _escape_markdown(row.status),
                    _escape_markdown(row.source_kind),
                    _escape_markdown(", ".join(row.family_ids) or "-"),
                    _escape_markdown(", ".join(row.pack_ids) or "-"),
                    _escape_markdown(", ".join(row.boundary_gate_ids) or "-"),
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
