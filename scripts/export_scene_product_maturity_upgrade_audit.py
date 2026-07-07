from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_product_maturity_upgrade_audit import (  # noqa: E402
    build_scene_product_maturity_upgrade_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export the N2.169 product maturity upgrade audit as JSON or "
            "Markdown."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    parser.add_argument("--subject-type", default="", help="Filter by pack/family.")
    parser.add_argument("--readiness", default="", help="Filter by readiness level.")
    parser.add_argument("--domain", default="", help="Filter by upgrade gap domain.")
    parser.add_argument("--query", default="", help="Free-text row filter.")
    args = parser.parse_args(argv)

    report = build_scene_product_maturity_upgrade_audit_report(
        subject_type=args.subject_type,
        readiness_level=args.readiness,
        domain_id=args.domain,
        query=args.query,
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
    filters = {
        "subject_type": payload["subject_type_filter"] or "all",
        "readiness": payload["readiness_filter"] or "all",
        "domain": payload["domain_filter"] or "all",
        "query": payload["query"] or "all",
    }
    lines = [
        "# Scene Product Maturity Upgrade Audit",
        "",
        f"- Status: {payload['status']}",
        (
            f"- Subjects: {counts['subject_count']} visible / "
            f"{counts['total_subject_count']} total"
        ),
        (
            f"- Green/L5: {counts['green_subject_count']} / "
            f"{counts['subject_count']}"
        ),
        (
            f"- L5 blockers: {counts['l5_blocked_subject_count']} subjects / "
            f"{counts['gap_count']} gaps / {counts['gap_domain_count']} domains"
        ),
        (
            f"- Static closed but not Green/L5: "
            f"{counts['static_closed_not_green_count']}"
        ),
        f"- Filters: {_join_pairs(filters)}",
        "",
        "## Subject Rows",
        "",
        (
            "| Subject | Type | Current | Next | Status | Packs | Families | "
            "Gaps | Domains |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.subject_id),
                    _escape_markdown(row.subject_type),
                    _escape_markdown(row.current_readiness_level),
                    _escape_markdown(row.next_upgrade_goal),
                    _escape_markdown(row.status),
                    _escape_markdown(", ".join(row.pack_ids) or "-"),
                    _escape_markdown(", ".join(row.family_ids) or "-"),
                    str(row.l5_blocker_count),
                    _escape_markdown(", ".join(row.gap_domain_ids) or "-"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Gap Domains", ""])
    for item in counts["gap_domain_counts"]:
        lines.append(f"- `{item['domain_id']}`: {item['count']}")
    if report.issues:
        lines.extend(["", "## Blocking Issues", ""])
        for issue in report.issues:
            lines.append(
                f"- `{issue.scope_type}:{issue.scope_id}` / "
                f"`{issue.kind}`: {issue.message}"
            )
    lines.extend(["", "## Source Evidence", ""])
    for evidence in report.source_evidence:
        lines.append(
            f"- `{evidence.source_id}`: {evidence.status} "
            f"({evidence.source_path}; markers={', '.join(evidence.markers)})"
        )
    return "\n".join(lines)


def _join_pairs(values: dict[str, str]) -> str:
    return ", ".join(f"{key}={value}" for key, value in values.items())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
