"""Pure receipt identity and service-owned session file primitives."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping

from src.config.resource_ref import ResourceRef


def resource_ref(
    kind: str,
    *,
    mode_id: str = "",
    resource_id: str = "",
    source_type: str = "",
    path: str = "",
    value=None,
    explicit_revision: str = "",
    explicit_source_revision: str = "",
) -> ResourceRef:
    normalized_path = str(path or "").strip()
    status = "ok"
    source_revision = ""
    if normalized_path:
        candidate = Path(normalized_path)
        if str(explicit_source_revision or "").strip():
            source_revision = str(explicit_source_revision).strip()
        elif candidate.is_file():
            source_revision = f"sha256:{file_sha256(candidate)}"
        else:
            status = "missing"
    elif value is None and resource_id:
        status = "missing"
    if value is not None:
        effective_revision = object_revision(value)
    else:
        effective_revision = (
            str(explicit_revision or "").strip() or source_revision
        )
    return ResourceRef(
        kind=kind,
        mode_id=str(mode_id or "").strip(),
        resource_id=str(resource_id or "").strip(),
        source_type=str(source_type or "").strip(),
        path=normalized_path,
        revision=effective_revision,
        source_revision=source_revision,
        effective_revision=effective_revision,
        status=status,
        requested_id=str(resource_id or "").strip(),
        effective_id=str(resource_id or "").strip(),
    )


def object_revision(value) -> str:
    if value is None:
        return ""
    if is_dataclass(value):
        payload = asdict(value)
    elif isinstance(value, Mapping):
        payload = dict(value)
    elif hasattr(value, "__dict__"):
        payload = dict(value.__dict__)
    else:
        payload = repr(value)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cleanup_frozen_path(
    path: str | Path,
    output_namespace: str | Path,
) -> None:
    namespace = Path(output_namespace).expanduser().resolve()
    resource_root = (namespace / ".execution_resources").resolve()
    candidate = Path(path).expanduser().resolve()
    if not path_is_within(candidate, resource_root):
        raise OSError("refusing to clean a resource outside the session namespace")
    if candidate.exists():
        candidate.chmod(0o666)
        candidate.unlink()
    current = candidate.parent
    while path_is_within(current, namespace):
        try:
            current.rmdir()
        except OSError:
            break
        if current == namespace:
            break
        current = current.parent


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def path_identity(path: str | Path) -> str:
    normalized = str(path or "").strip()
    if not normalized:
        return ""
    return str(Path(normalized).expanduser().resolve()).casefold()


__all__ = [
    "cleanup_frozen_path",
    "file_sha256",
    "object_revision",
    "path_identity",
    "path_is_within",
    "resource_ref",
]
