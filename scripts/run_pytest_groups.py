"""Run pytest by functional file groups with per-group timeouts."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"


@dataclass(frozen=True, slots=True)
class PytestGroupResult:
    group: str
    files: tuple[str, ...]
    exit_code: int
    duration_seconds: float
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


def discover_test_groups() -> dict[str, tuple[Path, ...]]:
    groups: dict[str, list[Path]] = {}
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        groups.setdefault(_group_name_for(path), []).append(path)
    return {name: tuple(paths) for name, paths in sorted(groups.items())}


def _group_name_for(path: Path) -> str:
    stem = path.stem
    if not stem.startswith("test_"):
        return "misc"
    tokens = stem.removeprefix("test_").split("_")
    if not tokens or not tokens[0]:
        return "misc"
    if tokens[0].startswith("phase"):
        return "phase"
    return tokens[0]


def _gate_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONPATH", str(ROOT))
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    return env


def _tail(text: str, max_lines: int = 80) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(lines[-max_lines:])


def _run_group(
    group: str,
    files: tuple[Path, ...],
    *,
    timeout_seconds: int,
    pytest_args: tuple[str, ...],
) -> PytestGroupResult:
    relative_files = tuple(path.relative_to(ROOT).as_posix() for path in files)
    command = (
        sys.executable,
        "-m",
        "pytest",
        "-q",
        *relative_files,
        *pytest_args,
    )
    print(f"\n== {group} ({len(files)} files) ==", flush=True)
    print("$ " + " ".join(command), flush=True)

    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=_gate_env(),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
        duration = time.monotonic() - started
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - started
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        print(f"[TIMEOUT] {group} exceeded {timeout_seconds}s after {duration:.1f}s")
        if stdout:
            print(_tail(stdout))
        if stderr:
            print(_tail(stderr), file=sys.stderr)
        return PytestGroupResult(
            group=group,
            files=relative_files,
            exit_code=124,
            duration_seconds=round(duration, 2),
            timed_out=True,
        )

    output = _tail((completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else ""))
    if output:
        print(output)
    status = "PASS" if completed.returncode == 0 else "FAIL"
    print(f"[{status}] {group} in {duration:.1f}s")
    return PytestGroupResult(
        group=group,
        files=relative_files,
        exit_code=completed.returncode,
        duration_seconds=round(duration, 2),
    )


def _selected_groups(
    groups: dict[str, tuple[Path, ...]],
    selected: str,
) -> dict[str, tuple[Path, ...]]:
    if not selected:
        return groups
    names = {name.strip() for name in selected.split(",") if name.strip()}
    missing = names.difference(groups)
    if missing:
        raise SystemExit(f"Unknown pytest group(s): {', '.join(sorted(missing))}")
    return {name: groups[name] for name in sorted(names)}


def _split_groups_by_file(
    groups: dict[str, tuple[Path, ...]],
) -> dict[str, tuple[Path, ...]]:
    file_groups: dict[str, tuple[Path, ...]] = {}
    for group, files in groups.items():
        for path in files:
            file_groups[f"{group}:{path.stem}"] = (path,)
    return dict(sorted(file_groups.items()))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run tests as functional file groups with per-group timeout."
    )
    parser.add_argument("--list", action="store_true", help="List groups and exit.")
    parser.add_argument("--groups", default="", help="Comma-separated group names to run.")
    parser.add_argument(
        "--split-files",
        action="store_true",
        help="Run selected groups as one pytest process per test file.",
    )
    parser.add_argument("--timeout", type=int, default=300, help="Per-group timeout in seconds.")
    parser.add_argument(
        "--continue-on-fail",
        action="store_true",
        help="Run remaining groups after a failure or timeout.",
    )
    parser.add_argument("--summary-path", default="", help="Optional JSON result path.")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    groups = discover_test_groups()
    groups = _selected_groups(groups, args.groups)
    if args.split_files:
        groups = _split_groups_by_file(groups)

    if args.list:
        for name, files in groups.items():
            print(f"{name}: {len(files)} files")
        return 0

    pytest_args = tuple(item for item in args.pytest_args if item != "--")
    results: list[PytestGroupResult] = []
    for name, files in groups.items():
        result = _run_group(
            name,
            files,
            timeout_seconds=max(1, int(args.timeout)),
            pytest_args=pytest_args,
        )
        results.append(result)
        if not result.passed and not args.continue_on_fail:
            break

    if args.summary_path:
        target = ROOT / args.summary_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nSummary written to {target}")

    failed = [result for result in results if not result.passed]
    if failed:
        print("\nFailed groups:")
        for result in failed:
            marker = "timeout" if result.timed_out else f"exit {result.exit_code}"
            print(f"- {result.group}: {marker}, {result.duration_seconds:.1f}s")
        return 1

    print("\nAll selected pytest groups passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
