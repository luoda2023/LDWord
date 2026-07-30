"""Path-safety guard shared by bundled canonical configuration resources."""

from __future__ import annotations

import os
from pathlib import Path


def assert_non_symbolic_resource_path(
    path: Path,
    root: Path,
    *,
    resource_label: str,
) -> None:
    """Reject escapes, symlinks, and Windows junctions in a resource path."""

    candidate = Path(os.path.abspath(path))
    boundary = Path(os.path.abspath(root))
    try:
        relative = candidate.relative_to(boundary)
    except ValueError as exc:
        raise ValueError(f"canonical {resource_label} path escape: {path}") from exc

    current = boundary
    components = [boundary]
    for part in relative.parts:
        current = current / part
        components.append(current)
    for component in components:
        try:
            is_junction = getattr(component, "is_junction", None)
            attributes = getattr(
                component.stat(follow_symlinks=False),
                "st_file_attributes",
                0,
            )
            if (
                component.is_symlink()
                or (callable(is_junction) and is_junction())
                or bool(attributes & 0x400)
            ):
                raise ValueError(
                    f"symbolic canonical {resource_label} path is not allowed: "
                    f"{component}"
                )
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ValueError(
                f"canonical {resource_label} path is unreadable: {component}"
            ) from exc


__all__ = ["assert_non_symbolic_resource_path"]
