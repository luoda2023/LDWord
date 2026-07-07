from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_plugin_boundary_confirmation_audit import (  # noqa: E402
    build_scene_plugin_boundary_confirmation_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export the N2.160 plugin/manual boundary confirmation audit as "
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
        "--gate",
        default="",
        help="Filter by plugin/manual gate id.",
    )
    parser.add_argument(
        "--risk-domain",
        default="",
        help="Filter by risk domain id.",
    )
    args = parser.parse_args(argv)

    report = build_scene_plugin_boundary_confirmation_audit_report(
        gate_id=args.gate,
        risk_domain_id=args.risk_domain,
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
        "# Scene Plugin Boundary Confirmation Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Gates: {payload['gate_count']}",
        f"- Risk domains: {payload['risk_domain_count']}",
        f"- Routes: {payload['route_count']}",
        f"- Request samples: {payload['request_sample_count']}",
        f"- Manual fixtures: {payload['manual_fixture_count']}",
        f"- Issues: {payload['issue_count']}",
        "",
        (
            "| Gate | Status | Pack | Risk Domains | Routes | Request Samples | "
            "Manual Fixtures | Confidence | Professional | Issues |"
        ),
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.gate_id),
                    _escape_markdown(row.status),
                    _escape_markdown(row.pack_id),
                    _escape_markdown(_join_values(row.risk_domain_ids) or "-"),
                    str(len(row.route_ids)),
                    str(len(row.request_sample_ids)),
                    str(len(row.manual_fixture_ids)),
                    "required" if row.confidence_report_required else "optional",
                    "required" if row.professional_review_required else "optional",
                    _escape_markdown(_join_values(row.issue_ids) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Route And Sample Evidence", ""])
    for row in report.rows:
        lines.append(f"### {row.gate_id}")
        lines.append(f"- Routes: {_join_values(row.route_ids) or '-'}")
        lines.append(
            f"- Request samples: {_join_values(row.request_sample_ids) or '-'}"
        )
        lines.append(
            f"- Request cells: {_join_values(row.request_cell_sample_ids) or '-'}"
        )
        lines.append(f"- Manual fixtures: {_join_values(row.manual_fixture_ids) or '-'}")
        lines.append(f"- Report fields: {_join_values(row.report_fields) or '-'}")
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
            lines.append(f"- `{issue.gate_id}` / `{issue.kind}`: {issue.message}")
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
