"""Small content-hash primitive shared by immutable execution inputs."""

from __future__ import annotations

import hashlib
from pathlib import Path


def file_content_revision(path: str | Path) -> str:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


__all__ = ["file_content_revision"]
