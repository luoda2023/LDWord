from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_boundary_maturity_release_envelope_audit import (  # noqa: E402
    build_scene_boundary_maturity_release_envelope_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the N2.392 boundary maturity release-envelope audit.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    args = parser.parse_args(argv)

    report = build_scene_boundary_maturity_release_envelope_audit_report(
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
