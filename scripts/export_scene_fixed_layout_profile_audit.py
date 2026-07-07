from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_fixed_layout_profile_audit import (  # noqa: E402
    build_scene_fixed_layout_profile_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export the N2.178 fixed-layout profile productization audit as "
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
        "--profile-channel",
        default="",
        help="Filter by fixed-layout profile channel id.",
    )
    args = parser.parse_args(argv)

    report = build_scene_fixed_layout_profile_audit_report(
        profile_channel_id=args.profile_channel,
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
        "# Fixed-Layout Profile Productization Audit",
        "",
        f"- Status: {payload['status']}",
        (
            "- Profile channels: "
            f"{counts['ready_profile_channel_count']}/"
            f"{counts['profile_channel_count']}"
        ),
        f"- Fixed-layout surfaces: {counts['fixed_layout_surface_count']}",
        f"- Word/OOXML touchpoints: {counts['word_ooxml_touchpoint_count']}",
        f"- Runtime surfaces: {counts['runtime_surface_count']}",
        f"- UI surfaces: {counts['ui_surface_count']}",
        f"- Report surfaces: {counts['report_surface_count']}",
        f"- Repair target types: {counts['repair_target_type_count']}",
        f"- Test evidence: {counts['test_evidence_count']}",
        f"- Covered packs/families: {counts['covered_pack_count']}/{counts['covered_family_count']}",
        f"- Missing source evidence: {counts['missing_source_evidence_count']}",
        "",
        "| Channel | Status | Coverage | Packs | Families | Surfaces | Runtime | UI | Tests |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(row.profile_channel_id),
                    _escape_markdown(row.status),
                    _escape_markdown(row.coverage_selector),
                    str(len(row.pack_ids)),
                    str(len(row.family_ids)),
                    _escape_markdown(_join_values(row.fixed_layout_surface_ids)),
                    _escape_markdown(_join_values(row.runtime_surface_ids)),
                    _escape_markdown(_join_values(row.ui_surface_ids)),
                    _escape_markdown(_join_values(row.test_ids)),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Source Evidence", ""])
    for evidence in report.source_evidence:
        lines.append(
            "- "
            f"`{evidence.profile_channel_id}/{evidence.evidence_id}`: "
            f"{evidence.status} ({evidence.evidence_layer}; {evidence.source_path})"
        )
    if report.issues:
        lines.extend(["", "## Issues", ""])
        for issue in report.issues:
            lines.append(
                f"- `{issue.profile_channel_id}` / `{issue.kind}`: {issue.message}"
            )
    return "\n".join(lines)


def _join_values(values) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
