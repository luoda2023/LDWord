from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_matrix_dashboard import (  # noqa: E402
    build_scene_matrix_dashboard,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export the N2.159 global scene-matrix dashboard as JSON or "
            "Markdown."
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
    parser.add_argument(
        "--family",
        default="",
        help="Filter by planned scene family id.",
    )
    parser.add_argument(
        "--readiness",
        default="",
        help="Filter by product-readiness level.",
    )
    parser.add_argument(
        "--boundary",
        default="",
        help="Filter by boundary signal id.",
    )
    parser.add_argument("--status", default="", help="Filter by row status.")
    args = parser.parse_args(argv)

    report = build_scene_matrix_dashboard(
        pack_id=args.pack,
        family_id=args.family,
        readiness_level=args.readiness,
        boundary_signal=args.boundary,
        status=args.status,
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
        "# Scene Matrix Dashboard",
        "",
        f"- Status: {payload['status']}",
        f"- Visible packs: {payload['visible_count']} / {payload['total_count']}",
        f"- Request cells: {counts['request_cell_count']}",
        f"- Families: {counts['family_count']}",
        f"- DOCX fixtures: {counts['sample_fixture_count']}",
        f"- Control contracts: {counts['control_contract_count']}",
        f"- Word risk surfaces: {counts['word_risk_surface_count']}",
        f"- Product readiness subjects: {counts['product_readiness_subject_count']}",
        "",
        "## Dashboard Cards",
        "",
    ]
    for card in report.cards:
        lines.append(
            f"- `{card.card_id}`: {card.value} - {card.detail} "
            f"({card.variant})"
        )
    lines.extend(
        [
            "",
            "## Matrix Rows",
            "",
            (
                "| Pack | Status | Readiness | Cells | Families | Boundaries | "
                "Axes | Workflows | Word Risks | Fixtures | Sources |"
            ),
            "| --- | --- | --- | ---: | ---: | --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.pack_id),
                    _escape_markdown(row.status),
                    _escape_markdown(row.product_readiness_level),
                    str(row.request_cell_count),
                    str(row.family_count),
                    _escape_markdown(_join_values(row.boundary_signal_ids)),
                    _escape_markdown(_join_values(row.capability_axis_ids)),
                    _escape_markdown(_join_values(row.workflow_archetype_ids)),
                    _escape_markdown(_join_values(row.word_risk_surface_ids)),
                    str(row.sample_fixture_count),
                    _escape_markdown(_join_values(row.drilldown_source_ids)),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Lenses", ""])
    for lens in report.lenses:
        lines.append(
            f"- `{lens.lens_id}`: {lens.question} "
            f"[{_join_values(lens.source_ids)}]"
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
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
