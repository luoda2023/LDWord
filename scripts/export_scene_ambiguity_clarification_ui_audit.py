from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_ambiguity_clarification_ui_audit import (  # noqa: E402
    build_scene_ambiguity_clarification_ui_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the N2.174 ambiguity clarification UI audit.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    parser.add_argument("--boundary", default="", help="Filter by boundary id.")
    parser.add_argument("--pack", default="", help="Filter by pack id.")
    args = parser.parse_args(argv)

    report = build_scene_ambiguity_clarification_ui_audit_report(
        boundary_id=args.boundary,
        pack_id=args.pack,
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
        "# Scene Ambiguity Clarification UI Audit",
        "",
        f"- Status: {payload['status']}",
        (
            f"- Clarifications: {counts['ready_clarification_count']} ready / "
            f"{counts['clarification_count']} visible"
        ),
        f"- Candidate routes: {counts['candidate_route_count']}",
        f"- Candidate packs: {counts['candidate_pack_count']}",
        f"- Fixture backed: {counts['fixture_backed_count']}",
        "",
        (
            "| Clarification | Status | Prompt | Candidate routes | "
            "Candidate packs | UI surfaces | Decision fields | Anchor |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.clarification_id),
                    _escape_markdown(row.status),
                    _escape_markdown(row.clarification_prompt),
                    _escape_markdown(_join_values(row.candidate_route_ids) or "-"),
                    _escape_markdown(_join_values(row.candidate_pack_ids) or "-"),
                    _escape_markdown(_join_values(row.ui_surface_ids) or "-"),
                    _escape_markdown(_join_values(row.decision_record_fields) or "-"),
                    _escape_markdown(row.report_anchor_id),
                ]
            )
            + " |"
        )
    if report.issues:
        lines.extend(["", "## Blocking Issues", ""])
        for issue in report.issues:
            lines.append(
                f"- `{issue.scope_type}:{issue.scope_id}` / "
                f"`{issue.kind}`: {issue.message}"
            )
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in report.warnings:
            lines.append(
                f"- `{warning.scope_type}:{warning.scope_id}` / "
                f"`{warning.kind}`: {warning.message}"
            )
    lines.extend(["", "## Source Evidence", ""])
    for evidence in report.source_evidence:
        lines.append(
            f"- `{evidence.source_id}`: {evidence.status} "
            f"({evidence.source_path}; markers={_join_values(evidence.markers)})"
        )
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
