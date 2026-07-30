"""Small, reusable filesystem transaction primitives for delivery services."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
from uuid import uuid4


class DirectoryPublishError(RuntimeError):
    """A staged directory could not replace its final directory safely."""


def publish_staged_directory(
    staging_directory: Path,
    final_directory: Path,
    *,
    transaction_id: str = "",
) -> None:
    """Publish one sibling staging directory and restore the old final on error."""

    staging = staging_directory.resolve(strict=False)
    final = final_directory.resolve(strict=False)
    if staging == final or staging.parent != final.parent:
        raise DirectoryPublishError("staging and final directories must be siblings")
    if not staging.is_dir():
        raise DirectoryPublishError("staging directory does not exist")
    owner = final.parent
    identity = transaction_id.strip() or uuid4().hex
    backup = owner / f".{final.name}.{identity}.backup"
    moved_original = False
    published = False
    try:
        if final.exists():
            os.replace(final, backup)
            moved_original = True
        os.replace(staging, final)
        published = True
    except OSError as exc:
        if published:
            remove_owned_path(final, owner)
        if moved_original and backup.exists():
            os.replace(backup, final)
        raise DirectoryPublishError("directory_publish_failed") from exc
    finally:
        if published:
            remove_owned_path(backup, owner)


def remove_owned_path(path: Path, owner: Path) -> None:
    """Delete only a path proven to be below the declared owner directory."""

    if not path.exists():
        return
    try:
        resolved = path.resolve()
        resolved_owner = owner.resolve()
    except OSError:
        return
    if resolved == resolved_owner or resolved_owner not in resolved.parents:
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


__all__ = [
    "DirectoryPublishError",
    "publish_staged_directory",
    "remove_owned_path",
]
