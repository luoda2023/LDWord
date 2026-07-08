"""Shared helpers for scene source-marker evidence scans."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SceneSourceMarkerSpec = tuple[str, str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class SceneSourceMarkerResult:
    source_id: str
    source_path: str
    source_exists: bool
    markers: tuple[str, ...]
    missing_markers: tuple[str, ...]


def scan_scene_source_markers(
    project_root: Path | str | None,
    marker_specs: tuple[SceneSourceMarkerSpec, ...],
) -> tuple[SceneSourceMarkerResult, ...]:
    root = Path(project_root) if project_root is not None else Path.cwd()
    results: list[SceneSourceMarkerResult] = []
    for source_id, source_path, markers in marker_specs:
        path = Path(source_path)
        if not path.is_absolute():
            path = root / source_path
        source_exists = path.exists() and path.is_file()
        text = ""
        if source_exists:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                source_exists = False
        missing_markers = tuple(marker for marker in markers if marker not in text)
        results.append(
            SceneSourceMarkerResult(
                source_id=source_id,
                source_path=source_path,
                source_exists=source_exists,
                markers=markers,
                missing_markers=missing_markers,
            )
        )
    return tuple(results)


def scene_source_marker_issue_message(
    source_path: str,
    missing_markers: tuple[str, ...],
) -> str:
    return f"{source_path} missing markers: {', '.join(missing_markers)}"


__all__ = [
    "SceneSourceMarkerResult",
    "SceneSourceMarkerSpec",
    "scan_scene_source_markers",
    "scene_source_marker_issue_message",
]
