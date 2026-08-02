"""Verify that the release interpreter matches the reviewed constraints file."""

from __future__ import annotations

import argparse
import re
import sys
from importlib.metadata import PackageNotFoundError, requires, version
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parent.parent
LOCK_LINE = re.compile(r"^([A-Za-z0-9_.-]+)==([^;\s]+)")


def release_environment_issues(lock_path: Path) -> list[str]:
    issues: list[str] = []
    if sys.version_info[:2] != (3, 12):
        issues.append(
            "release_python_version_mismatch:"
            f"expected=3.12:actual={sys.version_info.major}.{sys.version_info.minor}"
        )
    locked: dict[str, tuple[str, str]] = {}
    for line_number, raw_line in enumerate(
        lock_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.partition("#")[0].strip()
        if not line:
            continue
        match = LOCK_LINE.fullmatch(line)
        if not match:
            issues.append(f"release_lock_invalid_line:{line_number}:{line}")
            continue
        distribution, expected = match.groups()
        normalized = canonicalize_name(distribution)
        if normalized in locked:
            issues.append(f"release_lock_duplicate_distribution:{distribution}")
            continue
        locked[normalized] = (distribution, expected)
        try:
            actual = version(distribution)
        except PackageNotFoundError:
            issues.append(f"release_dependency_missing:{distribution}=={expected}")
            continue
        if actual != expected:
            issues.append(
                "release_dependency_version_mismatch:"
                f"{distribution}:expected={expected}:actual={actual}"
            )
    issues.extend(_dependency_closure_issues(locked))
    return issues


def _dependency_closure_issues(
    locked: dict[str, tuple[str, str]],
) -> list[str]:
    """Require every selected runtime/dev/build dependency to be pinned."""

    issues: list[str] = []
    queue: list[tuple[str, tuple[str, ...]]] = [
        ("lark-formatter", ("", "dev", "build"))
    ]
    visited: set[str] = set()
    while queue:
        distribution, extras = queue.pop(0)
        normalized_distribution = canonicalize_name(distribution)
        if normalized_distribution in visited:
            continue
        visited.add(normalized_distribution)
        try:
            dependency_lines = requires(distribution) or []
        except PackageNotFoundError:
            if normalized_distribution == "lark-formatter":
                issues.append("release_project_metadata_missing:lark-formatter")
            continue
        for dependency_line in dependency_lines:
            requirement = Requirement(dependency_line)
            if requirement.marker and not any(
                requirement.marker.evaluate({"extra": extra}) for extra in extras
            ):
                continue
            normalized_dependency = canonicalize_name(requirement.name)
            if normalized_dependency not in locked:
                issues.append(
                    "release_dependency_unpinned:"
                    f"{requirement.name}:required_by={distribution}"
                )
                continue
            queue.append((requirement.name, ("",)))
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--lock",
        type=Path,
        default=ROOT / "requirements-release.lock",
    )
    args = parser.parse_args(argv)
    issues = release_environment_issues(args.lock)
    if issues:
        for issue in issues:
            print(f"[ERROR] {issue}", file=sys.stderr)
        return 1
    print("[OK] Release Python and dependency versions match the lock file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
