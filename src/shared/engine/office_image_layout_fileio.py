"""Small filesystem primitives shared by the Office layout parent and child."""

from __future__ import annotations

import json
import os
from hashlib import sha256
from pathlib import Path
from typing import Mapping


def atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    """Replace one JSON receipt atomically within its destination directory."""

    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def safe_file_sha256(path: Path) -> str:
    """Return a file digest, or an empty value when the file is unavailable."""

    try:
        digest = sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ""


def safe_file_size(path: Path) -> int:
    """Return a file size, or -1 when the file is unavailable."""

    try:
        return path.stat().st_size
    except OSError:
        return -1


__all__ = ["atomic_write_json", "safe_file_sha256", "safe_file_size"]
