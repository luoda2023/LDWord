"""Run the baseline engineering gate for local development and CI.

The gate is intentionally small: it catches broken imports, syntax errors, and
test collection drift before the heavier domain-specific release checks run.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

BASELINE_COMMANDS: tuple[tuple[tuple[str, ...], bool], ...] = (
    (
        (
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--select",
            "E9,F63,F7,F82",
            "main.py",
            "scripts",
            "src",
            "tests",
        ),
        True,
    ),
    ((sys.executable, "-m", "compileall", "-q", "src", "main.py"), False),
    ((sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"), True),
    (
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_app_meta.py",
            "tests/test_config_management_architecture.py",
            "tests/test_heading_style_semantics.py",
        ),
        False,
    ),
)


def _run(command: tuple[str, ...], summarize_success: bool) -> int:
    print(f"\n$ {' '.join(command)}", flush=True)
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=_gate_env(),
        check=False,
        capture_output=summarize_success,
        text=summarize_success,
    )
    if summarize_success:
        _print_captured_result(completed)
    return completed.returncode


def _print_captured_result(completed: subprocess.CompletedProcess[str]) -> None:
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    if completed.returncode:
        if stdout:
            print(stdout, end="" if stdout.endswith("\n") else "\n")
        if stderr:
            print(stderr, end="" if stderr.endswith("\n") else "\n", file=sys.stderr)
        return

    lines = [line for line in stdout.splitlines() if line.strip()]
    if lines:
        print(lines[-1])
    if stderr:
        print(stderr, end="" if stderr.endswith("\n") else "\n", file=sys.stderr)


def _gate_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONPATH", str(ROOT))
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    return env


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the baseline compile, collection, and smoke-test gate."
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the commands without running them.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list:
        for command, _summarize_success in BASELINE_COMMANDS:
            print(" ".join(command))
        return 0

    for command, summarize_success in BASELINE_COMMANDS:
        exit_code = _run(command, summarize_success)
        if exit_code:
            print(f"\nEngineering gate failed with exit code {exit_code}.", file=sys.stderr)
            return exit_code

    print("\nEngineering gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
