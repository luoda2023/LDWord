from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.shared.engine.scene_sample_docx_builder import (  # noqa: E402
    build_scene_sample_docx_library,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate openable DOCX files for scene sample fixtures.",
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default=str(ROOT / "artifacts" / "scene_sample_fixtures"),
        help="Directory where DOCX samples and manifest.json will be written.",
    )
    args = parser.parse_args(argv)

    library = build_scene_sample_docx_library(Path(args.output_dir))
    print(json.dumps(library.to_payload(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
