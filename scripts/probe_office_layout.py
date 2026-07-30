"""Run the isolated Word/WPS exact-layout capability probe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.shared.engine.office_layout_probe import (  # noqa: E402
    DEFAULT_PROVIDER_SPECS,
    OfficeProvider,
    probe_office_layout,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe Word/WPS pagination and Range geometry in an isolated process."
        )
    )
    parser.add_argument(
        "--provider",
        action="append",
        choices=("word", "wps", "all"),
        help="provider to probe; repeat to select both (default: all)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=45.0,
        help="hard timeout in seconds per registered provider (default: 45)",
    )
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="inspect COM registration without starting Office",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional UTF-8 JSON receipt path",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="emit compact JSON",
    )
    parser.add_argument(
        "--require-qualified",
        action="store_true",
        help="exit 2 when no provider passes every exact-layout capability",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    selected = set(args.provider or ("all",))
    if "all" in selected:
        specs = DEFAULT_PROVIDER_SPECS
    else:
        providers = {OfficeProvider(item) for item in selected}
        specs = tuple(
            spec for spec in DEFAULT_PROVIDER_SPECS if spec.provider in providers
        )

    receipt = probe_office_layout(
        timeout_seconds=args.timeout,
        provider_specs=specs,
        execute_live=not args.discover_only,
    )
    payload = json.dumps(
        receipt.to_dict(),
        ensure_ascii=False,
        indent=None if args.compact else 2,
    )
    print(payload)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(payload + "\n", encoding="utf-8")
        temporary.replace(args.output)
    if args.require_qualified and not receipt.exact_layout_ready:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
