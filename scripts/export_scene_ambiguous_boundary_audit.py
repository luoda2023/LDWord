from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_ambiguous_boundary_audit import (  # noqa: E402
    build_scene_ambiguous_boundary_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the N2.162 ambiguous pack-pair audit.",
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

    report = build_scene_ambiguous_boundary_audit_report(
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
        "# Scene Ambiguous Boundary Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Boundaries: {counts['boundary_count']}",
        f"- Pack pairs: {counts['pack_pair_count']}",
        f"- Ambiguous samples: {counts['ambiguous_sample_count']}",
        f"- Fixture backed: {counts['fixture_backed_count']}",
        f"- Issues: {counts['issue_count']}",
        "",
        (
            "| Boundary | Phrase | Pack Pair | Routes | Packs | Coverage | "
            "Prompt | Issues |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.boundary_id),
                    _escape_markdown(row.phrase),
                    _escape_markdown(row.pack_pair_key),
                    _escape_markdown(_join_values(row.candidate_route_ids) or "-"),
                    _escape_markdown(_join_values(row.candidate_pack_ids) or "-"),
                    _escape_markdown(row.coverage_level or "-"),
                    _escape_markdown(row.disambiguation_prompt or "-"),
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
            lines.append(
                f"- `{issue.boundary_id}` / `{issue.kind}`: {issue.message}"
            )
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
