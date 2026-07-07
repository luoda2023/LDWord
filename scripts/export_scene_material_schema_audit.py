from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_material_schema_audit import (  # noqa: E402
    build_scene_material_schema_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export the N2.166 horizontal MaterialSchema scene audit as JSON "
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
    parser.add_argument("--schema", default="", help="Filter rows by MaterialSchema id.")
    args = parser.parse_args(argv)

    report = build_scene_material_schema_audit_report(
        pack_id=args.pack,
        family_id=args.family,
        schema_id=args.schema,
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
        "schema": payload["schema_filter"] or "all",
    }
    lines = [
        "# Scene MaterialSchema Audit",
        "",
        f"- Status: {payload['status']}",
        (
            f"- Families: {counts['ready_material_family_count']} / "
            f"{counts['material_family_count']} material families ready"
        ),
        (
            f"- Packs: {counts['ready_material_pack_count']} / "
            f"{counts['material_pack_count']} material packs ready"
        ),
        (
            f"- Schemas: {counts['referenced_schema_count']} referenced / "
            f"{counts['schema_count']} visible"
        ),
        f"- Filters: {_join_pairs(filters)}",
        "",
        "## Family Rows",
        "",
        "| Family | Status | Packs | Schemas | Fields | Assets | Batch | Evidence |",
        "| --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in report.family_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.family_id),
                    _escape_markdown(row.status),
                    _escape_markdown(", ".join(row.pack_ids) or "-"),
                    _escape_markdown(", ".join(row.material_schema_ids) or "-"),
                    str(len(row.required_field_keys)),
                    str(len(row.required_asset_roles)),
                    _escape_markdown(", ".join(row.batch_modes) or "-"),
                    _escape_markdown(", ".join(row.report_evidence_ids[:2]) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Pack Rows",
            "",
            "| Pack | Status | Material | Families | Schemas | Fields | Assets |",
            "| --- | --- | --- | --- | --- | ---: | ---: |",
        ]
    )
    for row in report.pack_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.pack_id),
                    _escape_markdown(row.status),
                    "yes" if row.material_relevant else "no",
                    _escape_markdown(", ".join(row.planned_family_ids) or "-"),
                    _escape_markdown(", ".join(row.material_schema_ids) or "-"),
                    str(row.required_field_count),
                    str(row.required_asset_count),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Schema Registry Rows",
            "",
            "| Schema | Status | Family | Fields | Assets | Batch | Referenced By |",
            "| --- | --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for row in report.schema_rows:
        referenced = [
            *row.referenced_by_family_ids,
            *row.referenced_by_pack_ids,
            *row.referenced_by_scene_ids,
        ]
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.schema_id),
                    _escape_markdown(row.status),
                    _escape_markdown(row.family),
                    str(row.required_field_count),
                    str(row.required_asset_count),
                    _escape_markdown(row.batch_mode),
                    _escape_markdown(", ".join(referenced) or "registry-only"),
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
