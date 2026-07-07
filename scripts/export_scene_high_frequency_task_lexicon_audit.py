from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_high_frequency_task_lexicon_audit import (  # noqa: E402
    build_high_frequency_task_lexicon_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export the N2.161 high-frequency task lexicon audit as JSON or "
            "Markdown."
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
    parser.add_argument("--task", default="", help="Filter by task id.")
    parser.add_argument(
        "--status",
        default="",
        help="Filter by expected route status: matched, ambiguous, or unmatched.",
    )
    parser.add_argument(
        "--boundary",
        default="",
        help="Filter by boundary type.",
    )
    args = parser.parse_args(argv)

    report = build_high_frequency_task_lexicon_audit_report(
        task_id=args.task,
        expected_status=args.status,
        boundary_type=args.boundary,
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
    lines = [
        "# Scene High-Frequency Task Lexicon Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Tasks: {payload['task_count']}",
        f"- Phrases: {payload['phrase_count']}",
        f"- Request samples: {payload['request_sample_count']}",
        f"- Negative tasks: {payload['negative_task_count']}",
        f"- Ambiguous tasks: {payload['ambiguous_task_count']}",
        f"- Issues: {payload['issue_count']}",
        "",
        (
            "| Task | Status | Expected | Boundary | Layer | Phrases | Samples | "
            "Routes | Packs | Issues |"
        ),
        "| --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.task_id),
                    _escape_markdown(row.status),
                    _escape_markdown(row.expected_status),
                    _escape_markdown(row.boundary_type),
                    _escape_markdown(row.landing_layer),
                    str(row.phrase_count),
                    str(len(row.required_sample_ids)),
                    _escape_markdown(_join_values(row.expected_route_ids) or "-"),
                    _escape_markdown(_join_values(row.expected_pack_ids) or "-"),
                    _escape_markdown(_join_values(row.issue_ids) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Phrase Routing", ""])
    for row in report.rows:
        lines.append(f"### {row.task_id}")
        for phrase in row.phrase_audits:
            route_text = phrase.selected_route_id or _join_values(
                phrase.candidate_route_ids
            )
            lines.append(
                "- "
                f"{phrase.phrase}: {phrase.status}; "
                f"route={route_text or '-'}; "
                f"pack={phrase.selected_pack_id or _join_values(phrase.candidate_pack_ids) or '-'}"
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
            lines.append(f"- `{issue.task_id}` / `{issue.kind}`: {issue.message}")
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
