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
        "scene_residual_warning_governance_audit",
        argv,
        description="Export the N2.381 residual warning governance audit.",
        markdown_formatter=_report_markdown,
        configure_parser=_configure_parser,
        builder_kwargs_from_args=_builder_kwargs,
    )


def _configure_parser(parser) -> None:
    parser.add_argument("--source", default="", help="Filter by source id.")


def _builder_kwargs(args) -> dict[str, object]:
    return {"source_id": args.source}


def _report_markdown(report) -> str:
    payload = report.to_payload()
    counts = payload["counts"]
    lines = [
        "# Scene Residual Warning Governance Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Managed warnings: {counts['managed_warning_count']}/{counts['warning_count']}",
        f"- InputSource warnings: {counts['input_source_warning_count']}",
        f"- CountProfile warnings: {counts['count_profile_warning_count']}",
        f"- Dashboard projections: {counts['dashboard_projection_warning_count']}",
        f"- ObjectPreflight warnings: {counts['object_preflight_warning_count']}",
        f"- Visio fixture closures: {counts['visio_fixture_closed_count']}",
        f"- Unmanaged warnings: {counts['unmanaged_warning_count']}",
        f"- Issues: {counts['issue_count']}",
        "",
        "| Scope | Source | Warning | Status | Governance | Evidence | Issues |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(f"{row.scope_type}:{row.scope_id}"),
                    _escape_markdown(row.source_id),
                    _escape_markdown(row.warning_kind),
                    _escape_markdown(row.status),
                    _escape_markdown(row.governance_mode),
                    _escape_markdown(_join_values(row.evidence_ids) or "-"),
                    _escape_markdown(_join_values(row.issue_ids) or "-"),
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
            lines.append(f"- `{issue.scope_id}` / `{issue.kind}`: {issue.message}")
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
