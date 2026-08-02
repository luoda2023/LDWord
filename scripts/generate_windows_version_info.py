"""Generate the PyInstaller Windows version resource from app metadata."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.app_meta import (
    APP_DISPLAY_NAME,
    APP_FILE_VERSION,
    APP_PACKAGE_NAME,
    APP_SEMVER,
)


def render_windows_version_info() -> str:
    version = tuple(APP_FILE_VERSION)
    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version!r},
    prodvers={version!r},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'Alavette'),
          StringStruct('FileDescription', '{APP_DISPLAY_NAME} desktop application'),
          StringStruct('FileVersion', '{APP_SEMVER}'),
          StringStruct('InternalName', '{APP_PACKAGE_NAME}'),
          StringStruct('LegalCopyright', 'Copyright (c) 2026 Alavette contributors'),
          StringStruct('OriginalFilename', '{APP_PACKAGE_NAME}.exe'),
          StringStruct('ProductName', '{APP_DISPLAY_NAME}'),
          StringStruct('ProductVersion', '{APP_SEMVER}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def write_windows_version_info(path: Path) -> Path:
    output = path.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_windows_version_info(), encoding="utf-8")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "build" / "windows_version_info.txt",
    )
    args = parser.parse_args(argv)
    print(write_windows_version_info(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
