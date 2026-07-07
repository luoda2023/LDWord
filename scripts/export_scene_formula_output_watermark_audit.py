from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_formula_output_watermark_audit import (  # noqa: E402
    build_scene_formula_output_watermark_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export the N2.168 formula/output/watermark ownership audit as "
            "JSON or Markdown."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    parser.add_argument("--capability", default="", help="Filter by capability id.")
    parser.add_argument("--family", default="", help="Filter rows by family id.")
    parser.add_argument("--pack", default="", help="Filter rows by coverage pack id.")
    args = parser.parse_args(argv)

    report = build_scene_formula_output_watermark_audit_report(
        capability_id=args.capability,
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
        "capability": payload["capability_filter"] or "all",
        "family": payload["family_filter"] or "all",
        "pack": payload["pack_filter"] or "all",
    }
    lines = [
        "# Scene Formula/Output/Watermark Audit",
        "",
        f"- Status: {payload['status']}",
        (
            f"- Capabilities: {counts['ready_capability_count']} ready / "
            f"{counts['capability_count']} visible"
        ),
        (
            f"- Families: {counts['ready_family_count']} ready / "
            f"{counts['family_count']} visible"
        ),
        (
            f"- Coverage: {counts['formula_family_count']} formula / "
            f"{counts['output_family_count']} output / "
            f"{counts['watermark_family_count']} watermark families"
        ),
        f"- Filters: {_join_pairs(filters)}",
        "",
        "## Capability Rows",
        "",
        "| Capability | Status | Owner | Families | Contracts | Consumers | Plugin Gates |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in report.capability_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.capability_id),
                    _escape_markdown(row.status),
                    _escape_markdown(row.expected_owner_layer),
                    str(len(row.family_ids)),
                    _escape_markdown(", ".join(row.control_contract_ids) or "-"),
                    _escape_markdown(", ".join(row.execution_consumers) or "-"),
                    _escape_markdown(", ".join(row.plugin_gate_ids) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Family Rows",
            "",
            "| Family | Status | Packs | Capabilities | Delivery Presets |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.family_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.family_id),
                    _escape_markdown(row.status),
                    _escape_markdown(", ".join(row.pack_ids) or "-"),
                    _escape_markdown(", ".join(row.capability_ids) or "-"),
                    _escape_markdown(", ".join(row.delivery_preset_ids) or "-"),
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
