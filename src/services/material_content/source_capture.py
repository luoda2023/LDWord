"""Bounded, stable capture of external MD/DOCX source bytes."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from src.config.content_materials import normalize_content_resource_path


DEFAULT_MAX_CONTENT_SOURCE_BYTES = 128 * 1024 * 1024
DEFAULT_MAX_CONTENT_RESOURCE_BYTES = 64 * 1024 * 1024
DEFAULT_CAPTURE_ATTEMPTS = 3

_FORMAT_BY_SUFFIX = {
    ".md": ("markdown", "text/markdown"),
    ".markdown": ("markdown", "text/markdown"),
    ".docx": (
        "docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
}


class ContentSourceCaptureError(ValueError):
    """Stable source-capture failure with a user-projectable code."""

    def __init__(self, code: str, message: str, *, path: str = "") -> None:
        self.code = str(code or "").strip()
        self.path = str(path or "").strip()
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class CapturedContentSource:
    original_name: str
    source_format: str
    media_type: str
    payload: bytes
    sha256: str
    byte_size: int

    def __post_init__(self) -> None:
        if not str(self.original_name or "").strip():
            raise ValueError("original_name must not be empty")
        if self.source_format not in {"markdown", "docx"}:
            raise ValueError("source_format must be 'markdown' or 'docx'")
        if not str(self.media_type or "").strip():
            raise ValueError("media_type must not be empty")
        if not isinstance(self.payload, bytes):
            raise TypeError("payload must be bytes")
        computed = sha256(self.payload).hexdigest()
        if self.sha256 != computed:
            raise ValueError("sha256 does not match payload")
        if self.byte_size != len(self.payload):
            raise ValueError("byte_size does not match payload")


@dataclass(frozen=True, slots=True)
class CapturedContentResource:
    relative_path: str
    payload: bytes
    sha256: str
    byte_size: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "relative_path",
            normalize_content_resource_path(self.relative_path),
        )
        if not isinstance(self.payload, bytes):
            raise TypeError("payload must be bytes")
        if self.sha256 != sha256(self.payload).hexdigest():
            raise ValueError("sha256 does not match payload")
        if self.byte_size != len(self.payload):
            raise ValueError("byte_size does not match payload")


def capture_content_source(
    source_path: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_CONTENT_SOURCE_BYTES,
    attempts: int = DEFAULT_CAPTURE_ATTEMPTS,
) -> CapturedContentSource:
    """Capture one stable source without waiting or relying on its future path."""

    path = Path(source_path).expanduser()
    if isinstance(max_bytes, bool) or int(max_bytes) < 1:
        raise ValueError("max_bytes must be a positive integer")
    if isinstance(attempts, bool) or int(attempts) < 1:
        raise ValueError("attempts must be a positive integer")
    contract = _FORMAT_BY_SUFFIX.get(path.suffix.casefold())
    if contract is None:
        raise ContentSourceCaptureError(
            "source_extension_not_allowed",
            f"unsupported content source extension: {path.suffix or '<none>'}",
            path=str(path),
        )

    payload = _capture_stable_bytes(
        path,
        max_bytes=int(max_bytes),
        attempts=int(attempts),
        domain="source",
    )
    source_format, media_type = contract
    return CapturedContentSource(
        original_name=path.name,
        source_format=source_format,
        media_type=media_type,
        payload=payload,
        sha256=sha256(payload).hexdigest(),
        byte_size=len(payload),
    )


def capture_content_resource(
    source_path: str | Path,
    *,
    relative_path: str,
    max_bytes: int = DEFAULT_MAX_CONTENT_RESOURCE_BYTES,
    attempts: int = DEFAULT_CAPTURE_ATTEMPTS,
) -> CapturedContentResource:
    if isinstance(max_bytes, bool) or int(max_bytes) < 1:
        raise ValueError("max_bytes must be a positive integer")
    if isinstance(attempts, bool) or int(attempts) < 1:
        raise ValueError("attempts must be a positive integer")
    normalized_path = normalize_content_resource_path(relative_path)
    payload = _capture_stable_bytes(
        Path(source_path).expanduser(),
        max_bytes=int(max_bytes),
        attempts=int(attempts),
        domain="resource",
    )
    return CapturedContentResource(
        relative_path=normalized_path,
        payload=payload,
        sha256=sha256(payload).hexdigest(),
        byte_size=len(payload),
    )


def _capture_stable_bytes(
    path: Path,
    *,
    max_bytes: int,
    attempts: int,
    domain: str,
) -> bytes:
    last_read_error: OSError | None = None
    for _attempt in range(attempts):
        try:
            before = path.stat()
        except FileNotFoundError as exc:
            raise ContentSourceCaptureError(
                f"{domain}_missing",
                f"content {domain} does not exist",
                path=str(path),
            ) from exc
        except OSError as exc:
            last_read_error = exc
            continue
        if not path.is_file():
            raise ContentSourceCaptureError(
                f"{domain}_not_file",
                f"content {domain} is not a regular file",
                path=str(path),
            )
        if before.st_size > max_bytes:
            raise ContentSourceCaptureError(
                f"{domain}_too_large",
                f"content {domain} exceeds the {max_bytes} byte limit",
                path=str(path),
            )
        try:
            with path.open("rb") as stream:
                payload = stream.read(max_bytes + 1)
            after = path.stat()
        except OSError as exc:
            last_read_error = exc
            continue
        if len(payload) > max_bytes:
            raise ContentSourceCaptureError(
                f"{domain}_too_large",
                f"content {domain} exceeds the {max_bytes} byte limit",
                path=str(path),
            )
        if _stat_identity(before) != _stat_identity(after) or len(payload) != after.st_size:
            continue
        return payload
    detail = f": {last_read_error}" if last_read_error is not None else ""
    raise ContentSourceCaptureError(
        f"{domain}_not_stable",
        f"content {domain} changed or could not be read consistently{detail}",
        path=str(path),
    )


def _stat_identity(value) -> tuple[int, int, int, int]:
    return (
        int(value.st_dev),
        int(value.st_ino),
        int(value.st_size),
        int(value.st_mtime_ns),
    )


__all__ = [
    "CapturedContentSource",
    "CapturedContentResource",
    "ContentSourceCaptureError",
    "DEFAULT_CAPTURE_ATTEMPTS",
    "DEFAULT_MAX_CONTENT_RESOURCE_BYTES",
    "DEFAULT_MAX_CONTENT_SOURCE_BYTES",
    "capture_content_source",
    "capture_content_resource",
]
