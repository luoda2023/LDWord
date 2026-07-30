"""Run one non-publishing Word/WPS image-layout transaction from JSON."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.shared.engine.office_image_layout_contracts import (  # noqa: E402
    OfficeImageLayoutRequest,
    OfficeImageProvider,
)
from src.shared.engine.office_image_layout_coordinator import (  # noqa: E402
    run_office_image_layout,
)


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Insert prepared images into a controlled DOCX shadow. The source "
            "document is never overwritten and no final artifact is published."
        )
    )
    parser.add_argument("request", type=Path, help="OfficeImageLayoutRequest JSON")
    parser.add_argument("--provider", choices=("word", "wps"), help="override provider")
    parser.add_argument("--timeout", type=float, help="override hard child timeout")
    parser.add_argument("--output", type=Path, help="optional receipt JSON path")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    payload = json.loads(args.request.read_text(encoding="utf-8"))
    request = OfficeImageLayoutRequest.from_dict(payload)
    if args.provider:
        request = replace(request, provider=OfficeImageProvider(args.provider))
    if args.timeout is not None:
        request = replace(request, timeout_seconds=args.timeout)
    receipt = run_office_image_layout(request)
    rendered = json.dumps(
        receipt.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        indent=None if args.compact else 2,
    )
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(rendered + "\n", encoding="utf-8")
        temporary.replace(args.output)
    return 0 if receipt.succeeded else 2


if __name__ == "__main__":
    raise SystemExit(main())
