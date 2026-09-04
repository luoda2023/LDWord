# -*- coding: utf-8 -*-
"""Windows console-window hiding for child processes.

LDWord runs as a windowed GUI (pythonw / frozen --windowed).  Any child
console executable (powershell, taskkill, soffice, python, ...) launched
without CREATE_NO_WINDOW inherits a brand-new console window that flashes
on top of the user session during document production.  These helpers make
every such child launch silent by default.

Non-Windows hosts and existing callers that already pass an explicit
``creationflags`` keep their behavior (the flag is OR-ed in).
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Sequence
from typing import Any


def create_no_window_flag() -> int:
    """Return CREATE_NO_WINDOW on Windows, 0 elsewhere.

    CREATE_NO_WINDOW (0x08000000) prevents the child console process from
    creating a new visible console window.  It is ignored for GUI subsystems.
    """
    if os.name == "nt":
        return int(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
    return 0


def _merge_flags(creationflags: int | None, extra: int | None = None) -> int:
    base = int(creationflags or 0)
    extra = int(extra or 0)
    return base | extra


def run_hidden(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess:
    """subprocess.run() with an invisible console on Windows.

    Any caller-supplied ``creationflags`` are preserved and OR-ed with
    CREATE_NO_WINDOW so behavior stays predictable.
    """
    kwargs = dict(kwargs)
    kwargs["creationflags"] = _merge_flags(
        kwargs.pop("creationflags", None),
        create_no_window_flag(),
    )
    return subprocess.run(*args, **kwargs)


def popen_hidden(*args: Any, **kwargs: Any) -> subprocess.Popen:
    """subprocess.Popen() with an invisible console on Windows."""
    kwargs = dict(kwargs)
    kwargs["creationflags"] = _merge_flags(
        kwargs.pop("creationflags", None),
        create_no_window_flag(),
    )
    return subprocess.Popen(*args, **kwargs)


def call_hidden(*args: Any, **kwargs: Any) -> int:
    """subprocess.call() with an invisible console on Windows."""
    kwargs = dict(kwargs)
    kwargs["creationflags"] = _merge_flags(
        kwargs.pop("creationflags", None),
        create_no_window_flag(),
    )
    return subprocess.call(*args, **kwargs)


# Convenience alias kept narrow for greppability in the codebase.
no_window_creationflags = create_no_window_flag


__all__ = [
    "call_hidden",
    "create_no_window_flag",
    "no_window_creationflags",
    "popen_hidden",
    "run_hidden",
]
