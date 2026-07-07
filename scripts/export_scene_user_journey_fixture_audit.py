from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_user_journey_fixture_audit import (  # noqa: E402
    build_scene_user_journey_fixture_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the N2.173 high-frequency user-journey fixture audit.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    parser.add_argument("--pack", default="", help="Filter by scene pack id.")
    parser.add_argument("--family", default="", help="Filter by scene family id.")
    parser.add_argument(
        "--journey-type",
        default="",
        help="Filter by user-journey path type.",
    )
    args = parser.parse_args(argv)

    report = build_scene_user_journey_fixture_audit_report(
        pack_id=args.pack,
        family_id=args.family,
        journey_type=args.journey_type,
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
        "journey_type": payload["journey_type_filter"] or "all",
    }
    lines = [
        "# Scene User Journey Fixture Audit",
        "",
        f"- Status: {payload['status']}",
        (
            f"- Packs: {counts['ready_pack_count']} ready / "
            f"{counts['pack_count']} visible"
        ),
        (
            f"- Families: {counts['ready_family_count']} ready / "
            f"{counts['family_count']} visible"
        ),
        (
            f"- Paths: {counts['path_count']} total / "
            f"{counts['success_path_count']} success / "
            f"{counts['degraded_path_count']} degraded / "
            f"{counts['failure_path_count']} failure / "
            f"{counts['manual_boundary_path_count']} manual / "
            f"{counts['handoff_path_count']} handoff"
        ),
        f"- Filters: {_join_pairs(filters)}",
        "",
        "## Pack Rows",
        "",
        "| Pack | Status | Paths | Types | Missing | Cells | Fixtures |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.pack_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.pack_id),
                    _escape_markdown(row.status),
                    str(row.path_count),
                    _escape_markdown(", ".join(row.path_type_ids) or "-"),
                    _escape_markdown(", ".join(row.missing_path_type_ids) or "-"),
                    str(len(row.request_cell_ids)),
                    _escape_markdown(", ".join(row.fixture_ids) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Family Rows",
            "",
            "| Family | Status | Priority | Paths | Types | Missing | Cells | Fixtures |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.family_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.family_id),
                    _escape_markdown(row.status),
                    _escape_markdown(row.priority),
                    str(row.path_count),
                    _escape_markdown(", ".join(row.path_type_ids) or "-"),
                    _escape_markdown(", ".join(row.missing_path_type_ids) or "-"),
                    str(len(row.request_cell_ids)),
                    _escape_markdown(", ".join(row.fixture_ids) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Journey Paths",
            "",
            "| Path | Type | Status | Packs | Families | Cells | Fixtures | Sources |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.path_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.path_id),
                    _escape_markdown(row.journey_type),
                    _escape_markdown(row.status),
                    _escape_markdown(", ".join(row.pack_ids) or "-"),
                    _escape_markdown(", ".join(row.family_ids) or "-"),
                    _escape_markdown(", ".join(row.request_cell_ids) or "-"),
                    _escape_markdown(", ".join(row.fixture_ids) or "-"),
                    _escape_markdown(", ".join(row.source_ids) or "-"),
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
