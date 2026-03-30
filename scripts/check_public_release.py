from __future__ import annotations

import argparse
import fnmatch
import re
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
REQUIRED_DOCS = [
    "README.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "requirements.txt",
]
BLOCKING_PATHS = [
    ".venv",
    "build",
    "dist",
]
BLOCKING_GLOBS = [
    "*.spec",
    "*_new.docx",
    "*_对比稿.docx",
    "*_报告.json",
    "*_报告.md",
]
WARNING_GLOBS = [
    "crash.log",
    "demo_crash.log",
    "lark_formatter.log",
]
PYQT5_IMPORT_RE = re.compile(r"^\s*(from|import)\s+PyQt5\b", re.M)


def iter_repo_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if ".agents" in path.parts or "__pycache__" in path.parts or ".pytest_cache" in path.parts:
            continue
        yield path


def scan_release_tree(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for rel in REQUIRED_DOCS:
        if not (root / rel).exists():
            errors.append(f"Missing required release file: {rel}")

    for rel in BLOCKING_PATHS:
        if (root / rel).exists():
            warnings.append(f"Local-only path present: {rel}")

    for path in iter_repo_files(root):
        rel = path.relative_to(root).as_posix()

        if path.is_file():
            for pattern in BLOCKING_GLOBS:
                if fnmatch.fnmatch(path.name, pattern):
                    warnings.append(f"Generated artifact should not be published: {rel}")
            for pattern in WARNING_GLOBS:
                if fnmatch.fnmatch(path.name, pattern):
                    warnings.append(f"Runtime log present: {rel}")

            if path.suffix == ".py":
                text = path.read_text(encoding="utf-8", errors="ignore")
                if PYQT5_IMPORT_RE.search(text):
                    errors.append(f"PyQt5 import remains in: {rel}")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan the repository for obvious blockers before a MIT-source public release.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero if any warning or error is found.",
    )
    args = parser.parse_args()

    errors, warnings = scan_release_tree(ROOT)

    print("== Public release scan ==")
    print(f"Repository: {ROOT}")
    print("Required docs checked: README.md, LICENSE, THIRD_PARTY_NOTICES.md, requirements.txt")

    if errors:
        print("\n[ERRORS]")
        for item in errors:
            print(f"- {item}")

    if warnings:
        print("\n[WARNINGS]")
        for item in warnings:
            print(f"- {item}")

    if not errors and not warnings:
        print("\n[OK] No obvious public-release blockers were found.")
        return 0

    if args.strict:
        print("\n[FAIL] Strict mode enabled: fix the findings above before publishing.")
        return 1

    print("\n[WARN] Findings detected. Review them before publishing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
