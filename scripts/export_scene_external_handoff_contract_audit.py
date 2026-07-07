from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_external_handoff_contract_audit import (  # noqa: E402
    build_scene_external_handoff_contract_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the N2.379 external handoff contract audit.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    parser.add_argument("--subject", default="", help="Filter by subject id.")
    parser.add_argument("--gate", default="", help="Filter by plugin/manual gate id.")
    args = parser.parse_args(argv)

    report = build_scene_external_handoff_contract_audit_report(
        subject_id=args.subject,
        gate_id=args.gate,
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
        "# Scene External Handoff Contract Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Contracts: {counts['ready_contract_count']}/{counts['contract_count']} ready",
        f"- Target plugins: {counts['target_plugin_count']}",
        f"- Reports: {counts['report_count']}",
        f"- Status states: {counts['status_state_count']}",
        f"- Failure policies: {counts['failure_policy_count']}",
        f"- Issues: {counts['issue_count']}",
        "",
        "| Contract | Status | Subject | Gap | Gate | Target Plugin | Reports | States | Issues |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.contract_id),
                    _escape_markdown(row.status),
                    _escape_markdown(f"{row.subject_type}:{row.subject_id}"),
                    _escape_markdown(row.gap_id),
                    _escape_markdown(row.gate_id),
                    _escape_markdown(row.target_plugin_id),
                    str(len(row.required_report_ids)),
                    str(len(row.status_ids)),
                    _escape_markdown(_join_values(row.issue_ids) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Contract Details", ""])
    for row in report.rows:
        lines.append(f"### {row.contract_id}")
        lines.append(f"- Payload fields: {_join_values(row.payload_field_ids) or '-'}")
        lines.append(f"- UI surfaces: {_join_values(row.ui_surface_ids) or '-'}")
        lines.append(f"- Fixtures: {_join_values(row.fixture_ids) or '-'}")
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
            lines.append(f"- `{issue.contract_id}` / `{issue.kind}`: {issue.message}")
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
