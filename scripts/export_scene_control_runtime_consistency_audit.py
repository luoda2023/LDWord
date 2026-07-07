from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_control_runtime_consistency_audit import (  # noqa: E402
    build_scene_control_runtime_consistency_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export the N2.175 scene control runtime consistency audit as "
            "JSON or Markdown."
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
        "--runtime",
        default="",
        help="Filter by runtime control id.",
    )
    args = parser.parse_args(argv)

    report = build_scene_control_runtime_consistency_audit_report(
        runtime_id=args.runtime
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
    owner_counts = ", ".join(
        f"{item['owner_layer']}={item['count']}"
        for item in payload["owner_layer_counts"]
    )
    lines = [
        "# Scene Control Runtime Consistency Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Runtime controls: {payload['ready_runtime_control_count']}/{payload['runtime_control_count']}",
        f"- Control contract links: {payload['control_contract_link_count']}",
        f"- Shared components: {payload['shared_component_count']}",
        f"- Runtime consumers: {payload['runtime_consumer_count']}",
        f"- Missing source evidence: {payload['missing_source_evidence_count']}",
        f"- Owner layers: {owner_counts}",
        "",
        "| Runtime | Status | Contracts | Components | Scope | Semantics | Evidence | Issues |",
        "| --- | --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.runtime_id),
                    _escape_markdown(row.status),
                    _escape_markdown(_join_values(row.contract_ids)),
                    _escape_markdown(_join_values(row.shared_component_ids)),
                    _escape_markdown(row.scope),
                    _escape_markdown(_join_values(row.required_semantics)),
                    str(len(row.evidence_ids)),
                    _escape_markdown(_join_values(row.issue_ids) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Source Evidence", ""])
    for evidence in report.source_evidence:
        lines.append(
            "- "
            f"`{evidence.runtime_id}/{evidence.evidence_id}`: {evidence.status} "
            f"({evidence.evidence_layer}; {evidence.source_path})"
        )
    if report.issues:
        lines.extend(["", "## Issues", ""])
        for issue in report.issues:
            lines.append(
                f"- `{issue.runtime_id}` / `{issue.kind}`: {issue.message}"
            )
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
