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
        "scene_boundary_maturity_release_envelope_audit",
        argv,
        description="Export the N2.392 boundary maturity release-envelope audit.",
        markdown_formatter=_report_markdown,
    )


def _report_markdown(report) -> str:
    payload = report.to_payload()
    counts = payload["counts"]
    lines = [
        "# Scene Boundary Maturity Release Envelope Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Envelopes ready: {counts['ready_envelope_count']}/{counts['envelope_count']}",
        f"- Maturity boundary rows: {counts['maturity_boundary_count']}",
        f"- External handoffs: {counts['external_handoff_count']}",
        f"- Guarded completions: {counts['guarded_completion_count']}",
        f"- Readiness reconciliation: {counts['readiness_reconciliation_count']}",
        f"- Terminal traces: {counts['terminal_trace_count']}",
        f"- Release dossiers: {counts['release_dossier_count']}",
        f"- Subject continuity: {counts['subject_continuity_count']}",
        f"- Retained gaps: {counts['retained_gap_count']}",
        f"- Issues: {counts['issue_count']}",
        "",
        "| Envelope | Subject | Gap | Contract | Continuity | Status | Evidence |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.envelope_id),
                    _escape_markdown(f"{row.subject_type}:{row.subject_id}"),
                    _escape_markdown(row.gap_id),
                    _escape_markdown(row.external_handoff_contract_id or "-"),
                    _escape_markdown(row.subject_continuity_status or "-"),
                    _escape_markdown(row.status),
                    _escape_markdown(_join_values(row.evidence_ids) or "-"),
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
            lines.append(f"- `{issue.envelope_id}` / `{issue.kind}`: {issue.message}")
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
