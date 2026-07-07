from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_word_risk_closure_audit import (  # noqa: E402
    build_scene_word_risk_closure_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export the N2.157D Word/OOXML risk-surface closure audit as JSON "
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
        "--surface",
        default="",
        help="Filter by Word risk surface id.",
    )
    args = parser.parse_args(argv)

    report = build_scene_word_risk_closure_audit_report(surface_id=args.surface)
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
        "# Scene Word Risk Closure Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Surfaces: {payload['surface_count']}",
        f"- Issues: {payload['issue_count']}",
        f"- Preflight surfaces: {payload['preflight_surface_count']}",
        f"- Sample fixture links: {payload['sample_fixture_link_count']}",
        "",
        (
            "| Surface | Status | Packs | Sample Surfaces | Sample Fixtures | "
            "Preflight Targets | Evidence Layers | Evidence | Issues |"
        ),
        "| --- | --- | ---: | --- | ---: | --- | --- | ---: | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.surface_id),
                    _escape_markdown(row.status),
                    str(len(row.pack_ids)),
                    _escape_markdown(_join_values(row.sample_surface_ids) or "-"),
                    str(len(row.sample_fixture_ids)),
                    _escape_markdown(_join_values(row.preflight_targets) or "-"),
                    _escape_markdown(_join_values(row.evidence_layer_ids) or "-"),
                    str(row.source_evidence_count),
                    _escape_markdown(_join_values(row.issue_ids) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Sample Fixtures", ""])
    for row in report.rows:
        lines.append(
            "- "
            f"`{row.surface_id}`: "
            f"{_join_values(row.sample_fixture_ids) or '-'}"
        )
    lines.extend(["", "## Evidence", ""])
    for row in report.rows:
        lines.append(f"### {row.surface_id}")
        for evidence in row.source_evidence:
            lines.append(
                "- "
                f"`{evidence.evidence_id}`: {evidence.status} "
                f"[{evidence.layer}] ({evidence.source_path}; "
                f"markers={_join_values(evidence.markers)})"
            )
    if report.issues:
        lines.extend(["", "## Issues", ""])
        for issue in report.issues:
            lines.append(
                f"- `{issue.surface_id}` / `{issue.kind}`: {issue.message}"
            )
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
