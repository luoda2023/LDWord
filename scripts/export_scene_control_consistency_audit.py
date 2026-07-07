from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_control_consistency_audit import (  # noqa: E402
    build_scene_control_consistency_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export the N2.157C scene control consistency audit as JSON "
            "or Markdown."
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
    parser.add_argument(
        "--contract",
        default="",
        help="Filter by control contract id.",
    )
    args = parser.parse_args(argv)

    report = build_scene_control_consistency_audit_report(contract_id=args.contract)
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
    owner_counts = ", ".join(
        f"{item['owner_layer']}={item['count']}"
        for item in payload["owner_layer_counts"]
    )
    lines = [
        "# Scene Control Consistency Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Contracts: {payload['contract_count']}",
        f"- Issues: {payload['issue_count']}",
        f"- Owner layers: {owner_counts}",
        f"- Missing surface evidence: {payload['missing_surface_evidence_count']}",
        "",
        "| Contract | Status | Owner | Control | Units | Pair | Scene Surface | Evidence | Issues |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.contract_id),
                    _escape_markdown(row.status),
                    _escape_markdown(row.owner_layer),
                    _escape_markdown(row.canonical_control),
                    _escape_markdown(_join_values(row.unit_set) or "-"),
                    _escape_markdown(_join_values(row.paired_contract_ids) or "-"),
                    _escape_markdown(row.scene_surface or "-"),
                    str(row.evidence_location_count),
                    _escape_markdown(_join_values(row.issue_ids) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Surface Evidence", ""])
    for evidence in report.surface_evidence:
        lines.append(
            "- "
            f"`{evidence.evidence_id}`: {evidence.status} "
            f"({evidence.source_path}; markers={_join_values(evidence.markers)})"
        )
    if report.issues:
        lines.extend(["", "## Issues", ""])
        for issue in report.issues:
            lines.append(
                f"- `{issue.contract_id}` / `{issue.kind}`: {issue.message}"
            )
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
