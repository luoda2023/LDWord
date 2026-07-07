from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_release_residual_ratio_ledger_audit import (  # noqa: E402
    build_scene_release_residual_ratio_ledger_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the N2.393 release residual-ratio ledger audit.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    args = parser.parse_args(argv)

    report = build_scene_release_residual_ratio_ledger_audit_report(
        project_root=ROOT
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
        "# Scene Release Residual Ratio Ledger Audit",
        "",
        f"- Status: {payload['status']}",
        f"- Residual ratios published: {counts['published_ratio_count']}/{counts['ratio_count']}",
        f"- Non-full ratios: {counts['non_full_ratio_count']}",
        f"- Readiness reconciliation links: {counts['readiness_reconciliation_link_count']}",
        f"- Terminal exception links: {counts['terminal_exception_link_count']}",
        f"- Release envelope links: {counts['release_envelope_link_count']}",
        (
            f"- Retained-gap exit criteria links: "
            f"{counts['retained_gap_exit_criteria_link_count']}"
        ),
        (
            f"- Receipt alignments: "
            f"{counts['retained_gap_receipt_alignment_link_count']}/"
            f"{counts['retained_gap_exit_criteria_link_count']}"
        ),
        (
            f"- Count/delivery boundary alignments: "
            f"{counts['count_delivery_boundary_alignment_count']}/"
            f"{counts['count_delivery_boundary_link_count']}"
        ),
        (
            f"- Count/delivery receipt alignments: "
            f"{counts['count_delivery_receipt_alignment_count']}/"
            f"{counts['count_delivery_receipt_alignment_link_count']}"
        ),
        (
            f"- Maturity L5 blocker alignments: "
            f"{counts['maturity_l5_blocker_alignment_count']}"
        ),
        (
            f"- Maturity L5 receipt alignments: "
            f"{counts['maturity_l5_blocker_receipt_alignment_count']}/"
            f"{counts['maturity_l5_blocker_receipt_alignment_link_count']}"
        ),
        (
            f"- Boundary scope alignments: "
            f"{counts['boundary_scope_alignment_count']}/"
            f"{counts['boundary_scope_link_count']}"
        ),
        f"- Issues: {counts['issue_count']}",
        "",
        (
            "| Ratio | Source | Observed | Mode | Reconciliation | Envelopes | "
            "Exit criteria | Receipt alignments | Status |"
        ),
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.ratio_id),
                    _escape_markdown(row.source_id),
                    _escape_markdown(row.observed_ratio),
                    _escape_markdown(row.residual_mode),
                    str(len(row.readiness_reconciliation_row_ids)),
                    str(len(row.release_envelope_ids)),
                    str(len(row.retained_gap_exit_criteria_ids)),
                    str(len(row.retained_gap_receipt_alignment_ids)),
                    _escape_markdown(row.status),
                ]
            )
            + " |"
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
            lines.append(f"- `{issue.ratio_id}` / `{issue.kind}`: {issue.message}")
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
