from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_matrix_drilldown import (  # noqa: E402
    build_scene_matrix_drilldown_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export the N2.165 scene-matrix front-end drilldown registry as "
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
    parser.add_argument("--pack", default="", help="Filter rows by coverage pack id.")
    parser.add_argument("--family", default="", help="Filter rows by family id.")
    parser.add_argument("--source", default="", help="Filter by drilldown source id.")
    parser.add_argument(
        "--query",
        default="",
        help="Case-insensitive search over drilldown ids, labels, details, and evidence ids.",
    )
    args = parser.parse_args(argv)

    report = build_scene_matrix_drilldown_report(
        pack_id=args.pack,
        family_id=args.family,
        source_id=args.source,
        query=args.query,
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
        "source": payload["source_filter"] or "all",
        "query": payload["query"] or "all",
    }
    lines = [
        "# Scene Matrix Drilldown",
        "",
        f"- Status: {payload['status']}",
        f"- Drilldowns: {counts['ready_count']} / {counts['item_count']} ready",
        f"- Rows: {counts['visible_row_count']} visible / {counts['row_count']} total",
        (
            f"- Source evidence: {counts['ready_source_evidence_count']} / "
            f"{counts['source_evidence_count']} ready "
            f"({counts['missing_source_evidence_count']} missing)"
        ),
        f"- Filters: {_join_pairs(filters)}",
        "",
        "## Drilldown Index",
        "",
        "| Drilldown | Source | Status | Rows | Visible | Lenses | Route |",
        "| --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for item in report.items:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(item.drilldown_id),
                    _escape_markdown(item.source_id),
                    _escape_markdown(item.status),
                    str(item.row_count),
                    str(item.visible_count),
                    _escape_markdown(", ".join(item.lens_ids)),
                    _escape_markdown(item.route_hint),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Visible Rows", ""])
    for item in report.items:
        lines.extend(["", f"### {item.label}", ""])
        lines.extend([_escape_markdown(item.detail), ""])
        lines.append("| Row | Status | Packs | Families | Detail |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in item.visible_rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_markdown(row.row_id),
                        _escape_markdown(row.status),
                        _escape_markdown(", ".join(row.pack_ids) or "-"),
                        _escape_markdown(", ".join(row.family_ids) or "-"),
                        _escape_markdown(row.detail),
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
