from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "config_library"
DEFAULT_TARGET = ROOT / "build" / "release_config_library"
BUILTIN_BUCKETS = ("plans", "templates", "masters", "material_packages")
PRODUCT_WORKBENCH_ROOT = "template_workbench"
FORBIDDEN_PARTS = {"user", "content_artifacts"}
WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")
UNC_PATH_RE = re.compile(r"^\\\\[^\\/]+[\\/]")


def _iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _iter_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_strings(item)


def _contains_absolute_host_path(path: Path) -> bool:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        values = _iter_strings(payload)
    elif path.suffix.lower() in {".md", ".txt", ".yaml", ".yml"}:
        values = path.read_text(encoding="utf-8").splitlines()
    else:
        return False
    return any(
        WINDOWS_ABSOLUTE_PATH_RE.match(value.strip())
        or UNC_PATH_RE.match(value.strip())
        for value in values
    )


def _copy_tree(source: Path, target: Path) -> None:
    if not source.is_dir():
        return
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        destination = target / relative
        if path.is_symlink():
            raise ValueError(f"release_config_symlink_forbidden:{path}")
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)


def _validate_staged_tree(target: Path) -> tuple[int, int]:
    files = sorted(path for path in target.rglob("*") if path.is_file())
    if not files:
        raise ValueError("release_config_empty")
    for path in files:
        relative = path.relative_to(target)
        lowered_parts = {part.casefold() for part in relative.parts}
        forbidden = lowered_parts & FORBIDDEN_PARTS
        if forbidden:
            raise ValueError(
                f"release_config_forbidden_path:{relative.as_posix()}:{sorted(forbidden)}"
            )
        if _contains_absolute_host_path(path):
            raise ValueError(f"release_config_absolute_host_path:{relative.as_posix()}")
    return len(files), sum(path.stat().st_size for path in files)


def stage_release_config_library(source: Path, target: Path) -> tuple[int, int]:
    source = Path(source).resolve()
    target = Path(target).resolve()
    if not source.is_dir():
        raise ValueError(f"release_config_source_missing:{source}")
    if target.name != "release_config_library" or target == source:
        raise ValueError(f"release_config_unsafe_target:{target}")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    for bucket_name in BUILTIN_BUCKETS:
        bucket = source / bucket_name
        if not bucket.is_dir():
            continue
        for mode_root in sorted(path for path in bucket.iterdir() if path.is_dir()):
            _copy_tree(
                mode_root / "builtin",
                target / bucket_name / mode_root.name / "builtin",
            )

    _copy_tree(
        source / PRODUCT_WORKBENCH_ROOT,
        target / PRODUCT_WORKBENCH_ROOT,
    )
    return _validate_staged_tree(target)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage immutable config resources for the Windows product package."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args()
    count, size = stage_release_config_library(args.source, args.target)
    print(f"Release config staged: {count} files, {size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
