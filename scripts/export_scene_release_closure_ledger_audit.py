from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.export_scene_audit import (  # noqa: E402
    run_registered_scene_audit_export,
)


def main(argv: list[str] | None = None) -> int:
    return run_registered_scene_audit_export(
        "scene_release_closure_ledger_audit",
        argv,
        description="Export the N2.390 scene release-closure ledger audit.",
        markdown_formatter=_report_markdown,
    )


def _report_markdown(report) -> str:
    payload = report.to_payload()
    counts = payload["counts"]
    lines = [
        "# Scene Release Closure Ledger Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Stages ready: {counts['ready_stage_count']}/{counts['stage_count']}",
        f"- Ordered stages: {counts['stage_order_count']}",
        (
            f"- Upstream dependencies: "
            f"{counts['upstream_dependency_ready_count']}/"
            f"{counts['upstream_dependency_count']}"
        ),
        f"- Release gate bindings: {counts['release_gate_check_count']}",
        f"- Dashboard cards: {counts['dashboard_card_count']}",
        f"- Drilldown items: {counts['drilldown_item_count']}",
        f"- Summary projections: {counts['summary_projection_count']}",
        f"- Export scripts: {counts['export_script_count']}",
        f"- Workflow tests: {counts['workflow_test_count']}",
        f"- Closure docs: {counts['closure_doc_count']}",
        f"- Issues: {counts['issue_count']}",
        "",
        "| Order | Stage | N2 | Status | Upstream | Evidence | Supplemental |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.order),
                    _escape_markdown(row.stage_id),
                    _escape_markdown(row.n2_id),
                    _escape_markdown(row.status),
                    _escape_markdown(_join_values(row.upstream_stage_ids) or "-"),
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
            lines.append(f"- `{issue.stage_id}` / `{issue.kind}`: {issue.message}")
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
