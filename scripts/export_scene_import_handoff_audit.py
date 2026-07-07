from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_import_handoff_audit import (  # noqa: E402
    build_scene_import_handoff_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the N2.163 import handoff audit.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    parser.add_argument("--handoff", default="", help="Filter by handoff id.")
    parser.add_argument("--target-pack", default="", help="Filter by target pack id.")
    args = parser.parse_args(argv)

    report = build_scene_import_handoff_audit_report(
        handoff_id=args.handoff,
        target_pack_id=args.target_pack,
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
        "# Scene Import Handoff Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Handoffs: {counts['handoff_count']}",
        f"- Ready: {counts['ready_handoff_count']}",
        f"- Target packs: {counts['target_pack_count']}",
        f"- Fallback strategies: {counts['fallback_strategy_count']}",
        f"- Issues: {counts['issue_count']}",
        "",
        (
            "| Handoff | Source | Target | Route | Gate | Decision | "
            "Fallback | Fields | Issues |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.handoff_id),
                    _escape_markdown(row.source_pack_id),
                    _escape_markdown(
                        f"{row.target_pack_id}/{row.target_family_id}"
                    ),
                    _escape_markdown(row.selected_route_id or row.route_id),
                    _escape_markdown(row.plugin_gate_id),
                    _escape_markdown(row.required_decision_state),
                    _escape_markdown(row.fallback_strategy),
                    _escape_markdown(_join_values(row.required_report_fields)),
                    _escape_markdown(_join_values(row.issue_ids) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Source Evidence", ""])
    for evidence in report.source_evidence:
        lines.append(
            "- "
            f"`{evidence.evidence_id}`: {evidence.status} "
            f"({evidence.source_path}; markers={_join_values(evidence.markers)})"
        )
    if report.issues:
        lines.extend(["", "## Issues", ""])
        for issue in report.issues:
            lines.append(f"- `{issue.handoff_id}` / `{issue.kind}`: {issue.message}")
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
