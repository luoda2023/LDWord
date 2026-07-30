"""Pure projection of production outputs into durable local file references."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path


def project_output_references(
    result: Mapping[str, object],
) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    output_paths = result.get("output_paths")
    if isinstance(output_paths, Mapping):
        for artifact_key, raw_path in output_paths.items():
            path = _target(raw_path)
            if not path:
                continue
            rows.append(
                {
                    "type": "file",
                    "artifact_key": str(artifact_key),
                    "title": Path(path).name,
                    "path": path,
                }
            )
    primary = str(result.get("output_path") or "").strip()
    if primary and not any(item["path"] == primary for item in rows):
        rows.insert(
            0,
            {
                "type": "file",
                "artifact_key": "primary",
                "title": Path(primary).name,
                "path": primary,
            },
        )
    return tuple(rows)


def _target(value: object) -> str:
    if isinstance(value, Mapping):
        return str(
            value.get("path")
            or value.get("file_path")
            or value.get("local_path")
            or ""
        ).strip()
    return str(value or "").strip()


__all__ = ["project_output_references"]
