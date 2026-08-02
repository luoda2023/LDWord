"""Build deterministic Office broker child commands for every runtime."""

from __future__ import annotations

import sys
from pathlib import Path

OFFICE_IMAGE_LAYOUT_CHILD_FLAG = "--office-image-layout-child"
OFFICE_LAYOUT_PROBE_CHILD_FLAG = "--office-layout-probe-child"
MATHTYPE_OFFICE_CHILD_FLAG = "--mathtype-office-child"


def build_office_broker_child_command(
    *,
    module_name: str,
    frozen_flag: str,
    request_path: str | Path,
    executable: str | None = None,
    frozen: bool | None = None,
) -> list[str]:
    """Return a child command without importing Qt or sharing Office state."""

    module = str(module_name or "").strip()
    flag = str(frozen_flag or "").strip()
    if not module or not flag.startswith("--"):
        raise ValueError("module_name and an internal --flag are required")
    runtime = str(executable or sys.executable)
    request = str(Path(request_path))
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
    if is_frozen:
        return [runtime, flag, request]
    return [runtime, "-m", module, "--child-request", request]


__all__ = [
    "MATHTYPE_OFFICE_CHILD_FLAG",
    "OFFICE_IMAGE_LAYOUT_CHILD_FLAG",
    "OFFICE_LAYOUT_PROBE_CHILD_FLAG",
    "build_office_broker_child_command",
]
