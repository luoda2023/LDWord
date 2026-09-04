"""Predictable output-root naming for Workbench document execution."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

MAX_OUTPUT_ROOT_VERSIONS = 10_000


def default_workbench_output_root(
    source_paths: Iterable[str | Path],
) -> Path:
    """Return a source-related output folder next to the selected documents."""

    sources = _normalized_sources(source_paths)
    if not sources:
        raise ValueError("workbench_output_source_required")

    first = sources[0]
    if len(sources) == 1:
        label = first.stem or "文档"
        output_parent = first.parent
    elif _same_parent(sources):
        label = first.parent.name or "批量文档"
        output_parent = first.parent.parent
    else:
        label = "批量文档"
        output_parent = first.parent
    return (output_parent / f"{label}-输出").resolve()


def resolve_workbench_output_root(
    custom_root: str | Path | None,
    source_paths: Iterable[str | Path],
) -> Path:
    """Keep a user-selected root exact, otherwise return a free default root."""

    configured = str(custom_root or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return next_available_workbench_output_root(
        default_workbench_output_root(source_paths)
    )


def next_available_workbench_output_root(
    candidate: str | Path,
    *,
    max_versions: int = MAX_OUTPUT_ROOT_VERSIONS,
) -> Path:
    """Return ``candidate`` or the first free sibling suffixed with ``(n)``."""

    root = Path(candidate).expanduser().resolve()
    if not root.exists():
        return root
    for version in range(2, max(2, int(max_versions)) + 1):
        versioned = root.with_name(f"{root.name} ({version})")
        if not versioned.exists():
            return versioned
    raise RuntimeError(f"workbench_output_root_versions_exhausted:{root}")


def _normalized_sources(
    source_paths: Iterable[str | Path],
) -> tuple[Path, ...]:
    return tuple(
        Path(value).expanduser().resolve()
        for item in source_paths
        if (value := str(item or "").strip())
    )


def _same_parent(sources: tuple[Path, ...]) -> bool:
    parent_keys = {
        os.path.normcase(os.path.normpath(str(source.parent)))
        for source in sources
    }
    return len(parent_keys) == 1


__all__ = [
    "MAX_OUTPUT_ROOT_VERSIONS",
    "default_workbench_output_root",
    "next_available_workbench_output_root",
    "resolve_workbench_output_root",
]
