from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_release_projection_surface_parity_audit import (  # noqa: E402
    build_scene_release_projection_surface_parity_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export the N2.388/N2.391 release projection-surface parity audit."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    args = parser.parse_args(argv)

    report = build_scene_release_projection_surface_parity_audit_report(
        project_root=ROOT
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
        "# Scene Release Projection Surface Parity Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Projections ready: {counts['ready_projection_count']}/{counts['projection_count']}",
        f"- Release gate checks: {counts['release_gate_check_count']}",
        f"- Dashboard sources: {counts['dashboard_source_count']}",
        f"- Dashboard cards: {counts['dashboard_card_count']}",
        f"- Drilldown items: {counts['drilldown_item_count']}",
        f"- Summary projections: {counts['summary_projection_count']}",
        f"- Export scripts: {counts['export_script_count']}",
        f"- Workflow tests: {counts['workflow_test_count']}",
        f"- Closure docs: {counts['closure_doc_count']}",
        f"- Issues: {counts['issue_count']}",
        "",
        (
            "| Projection | Audit | Gate | Dashboard | Drilldown | Status | "
            "Evidence | Supplemental |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.projection_id),
                    _escape_markdown(row.audit_source_id),
                    _escape_markdown(row.release_gate_check_id),
                    _escape_markdown(row.dashboard_card_id),
                    _escape_markdown(row.drilldown_id),
                    _escape_markdown(row.status),
                    _escape_markdown(_join_values(row.evidence_ids) or "-"),
                    _escape_markdown(_supplemental_detail(row) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Source Evidence", ""])
    for evidence in report.source_evidence:
        lines.append(
            "- "
            f"`{evidence.source_id}`: {evidence.status} "
            f"({evidence.source_path}; markers={_join_values(evidence.markers)})"
        )
    if report.issues:
        lines.extend(["", "## Issues", ""])
        for issue in report.issues:
            lines.append(f"- `{issue.projection_id}` / `{issue.kind}`: {issue.message}")
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _supplemental_detail(row) -> str:
    markers = [
        f"{source}:{marker}"
        for source, marker in getattr(row, "supplemental_source_markers", ())
    ]
    docs = list(getattr(row, "supplemental_closure_doc_paths", ()))
    return _join_values((*markers, *docs))


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
