from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_delivery_preset_audit import (  # noqa: E402
    build_scene_delivery_preset_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export the N2.167 horizontal DeliveryPreset scene audit as JSON "
            "or Markdown."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    parser.add_argument("--pack", default="", help="Filter rows by coverage pack id.")
    parser.add_argument("--family", default="", help="Filter rows by family id.")
    parser.add_argument("--preset", default="", help="Filter rows by delivery preset id.")
    args = parser.parse_args(argv)

    report = build_scene_delivery_preset_audit_report(
        pack_id=args.pack,
        family_id=args.family,
        preset_id=args.preset,
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
        "pack": payload["pack_filter"] or "all",
        "family": payload["family_filter"] or "all",
        "preset": payload["preset_filter"] or "all",
    }
    lines = [
        "# Scene DeliveryPreset Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Families: {counts['ready_family_count']} ready / {counts['family_count']} visible",
        (
            f"- Packs: {counts['ready_delivery_pack_count']} ready / "
            f"{counts['delivery_pack_count']} delivery packs"
        ),
        (
            f"- Presets: {counts['delivery_preset_count']} unique / "
            f"{counts['final_docx_preset_count']} final-docx family uses / "
            f"{counts['report_only_preset_count']} report-only family uses"
        ),
        f"- Filters: {_join_pairs(filters)}",
        "",
        "## Family Rows",
        "",
        (
            "| Family | Status | Packs | Planned | Actual | Default | Final | "
            "Compare | Report-only | Package | Visibility |"
        ),
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report.family_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.family_id),
                    _escape_markdown(row.status),
                    _escape_markdown(", ".join(row.pack_ids) or "-"),
                    _escape_markdown(", ".join(row.planned_delivery_preset_ids) or "-"),
                    _escape_markdown(", ".join(row.actual_delivery_preset_ids) or "-"),
                    _escape_markdown(row.default_delivery_preset_id or "-"),
                    str(row.final_docx_preset_count),
                    str(row.compare_docx_preset_count),
                    str(row.report_only_preset_count),
                    str(row.material_package_preset_count),
                    str(row.content_visibility_rule_count),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Pack Rows",
            "",
            "| Pack | Status | Delivery | Families | Executable Scenes | Presets | Defaults |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.pack_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.pack_id),
                    _escape_markdown(row.status),
                    "yes" if row.delivery_relevant else "no",
                    _escape_markdown(", ".join(row.planned_family_ids) or "-"),
                    _escape_markdown(", ".join(row.executable_scene_ids) or "-"),
                    _escape_markdown(", ".join(row.actual_delivery_preset_ids) or "-"),
                    _escape_markdown(", ".join(row.default_delivery_preset_ids) or "-"),
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
