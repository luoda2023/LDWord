from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_request_cell_fixture_registry import (  # noqa: E402
    build_scene_request_cell_registry_browser,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export the global scene request-cell registry browser as JSON "
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
    parser.add_argument("--pack", default="", help="Filter by coverage pack id.")
    parser.add_argument(
        "--coverage-level",
        default="",
        help="Filter by request-cell coverage level.",
    )
    parser.add_argument("--family", default="", help="Filter by planned family id.")
    parser.add_argument(
        "--query",
        default="",
        help="Case-insensitive search over request, ids, fixtures, gates, and notes.",
    )
    args = parser.parse_args(argv)

    browser = build_scene_request_cell_registry_browser(
        pack_id=args.pack,
        coverage_level=args.coverage_level,
        family_id=args.family,
        query=args.query,
    )
    if args.format == "json":
        content = json.dumps(browser.to_payload(), ensure_ascii=False, indent=2)
    else:
        content = _browser_markdown(browser)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content + "\n", encoding="utf-8")
    else:
        print(content)
    return 0


def _browser_markdown(browser) -> str:
    filters = {
        "pack": browser.pack_filter or "all",
        "coverage": browser.coverage_filter or "all",
        "family": browser.family_filter or "all",
        "query": browser.query or "all",
    }
    coverage_counts = ", ".join(
        f"{level}={count}" for level, count in browser.coverage_level_counts
    )
    lines = [
        "# Scene Request-Cell Registry",
        "",
        f"- Total cells: {browser.total_count}",
        f"- Visible cells: {browser.visible_count}",
        f"- Filters: {_join_pairs(filters)}",
        f"- Coverage levels: {coverage_counts}",
        "",
        "| Sample | Coverage | Status | Packs | Families | Fixtures | Gates | Request |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in browser.items:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown(item.sample_id),
                    _escape_markdown(item.coverage_label),
                    _escape_markdown(item.status_label),
                    _escape_markdown(", ".join(item.expected_pack_ids) or "-"),
                    _escape_markdown(", ".join(item.expected_family_ids) or "-"),
                    _escape_markdown(", ".join(item.fixture_ids) or "-"),
                    _escape_markdown(", ".join(item.manual_gate_ids) or "-"),
                    _escape_markdown(item.request_text),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _join_pairs(values: dict[str, str]) -> str:
    return ", ".join(f"{key}={value}" for key, value in values.items())


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
