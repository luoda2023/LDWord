"""Small same-directory atomic writers for configuration resources."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile


def atomic_write_text(path: str | Path, text: str, *, encoding: str = "utf-8") -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
            temp_path = Path(stream.name)
        os.replace(temp_path, target)
        return target
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def atomic_write_bytes(path: str | Path, payload: bytes) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
            temp_path = Path(stream.name)
        os.replace(temp_path, target)
        return target
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def atomic_write_bytes_if_absent(path: str | Path, payload: bytes) -> Path:
    """Publish complete bytes only when ``path`` is still absent.

    The temporary file is fully flushed before a hard link makes it visible at
    the target name.  Unlike :func:`atomic_write_bytes`, this operation never
    replaces a file (or symlink) created by another actor in the meantime.
    """

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
            temp_path = Path(stream.name)
        try:
            os.link(temp_path, target, follow_symlinks=False)
        except FileExistsError as exc:
            raise FileExistsError(f"atomic target already exists: {target}") from exc
        return target
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


__all__ = [
    "atomic_write_bytes",
    "atomic_write_bytes_if_absent",
    "atomic_write_text",
]
