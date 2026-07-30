"""Immutable filesystem identity evidence shared by publication boundaries."""

from __future__ import annotations

from dataclasses import dataclass
import re


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class FileEvidence:
    path: str
    sha256: str
    byte_size: int

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or not self.path.strip():
            raise ValueError("path must not be empty")
        if not isinstance(self.sha256, str) or not _SHA256_RE.fullmatch(self.sha256):
            raise ValueError("sha256 must be a lowercase SHA-256")
        if (
            isinstance(self.byte_size, bool)
            or not isinstance(self.byte_size, int)
            or self.byte_size < 0
        ):
            raise ValueError("byte_size must be a non-negative integer")

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "byte_size": self.byte_size,
        }


__all__ = ["FileEvidence"]
