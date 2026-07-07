from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_boundary_guarded_completion_audit import (  # noqa: E402
    build_scene_boundary_guarded_completion_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the N2.380 boundary guarded-completion audit.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    parser.add_argument("--subject", default="", help="Filter by subject id.")
    args = parser.parse_args(argv)

    report = build_scene_boundary_guarded_completion_audit_report(
        subject_id=args.subject,
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
    lines = [
        "# Scene Boundary Guarded Completion Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Subjects: {counts['ready_subject_count']}/{counts['subject_count']} guarded",
        f"- Retained gaps: {counts['retained_gap_count']}",
        f"- External contracts: {counts['external_contract_count']}",
        f"- Boundary capabilities: {counts['boundary_capability_count']}",
        f"- Excluded core claims: {counts['excluded_core_claim_count']}",
        f"- Issues: {counts['issue_count']}",
        "",
        "| Subject | Status | Readiness | Maturity | Gaps | Contracts | Capabilities | Claims | Issues |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(f"{row.subject_type}:{row.subject_id}"),
                    _escape_markdown(row.status),
                    _escape_markdown(row.readiness_level),
                    _escape_markdown(row.maturity_status),
                    str(len(row.remaining_gap_ids)),
                    str(len(row.external_handoff_contract_ids)),
                    str(len(row.boundary_capability_ids)),
                    str(len(row.excluded_core_claims)),
                    _escape_markdown(_join_values(row.issue_ids) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Subject Details", ""])
    for row in report.rows:
        lines.append(f"### {row.subject_type}:{row.subject_id}")
        lines.append(f"- Retained gaps: {_join_values(row.remaining_gap_ids) or '-'}")
        lines.append(
            f"- Boundary capabilities: {_join_values(row.boundary_capability_ids) or '-'}"
        )
        lines.append(
            f"- External contracts: {_join_values(row.external_handoff_contract_ids) or '-'}"
        )
        lines.append(f"- Target plugins: {_join_values(row.target_plugin_ids) or '-'}")
        lines.append(
            f"- Excluded core claims: {_join_values(row.excluded_core_claims) or '-'}"
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
            lines.append(f"- `{issue.subject_id}` / `{issue.kind}`: {issue.message}")
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
