"""Stable, serializable identity for one referenced configuration resource."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class ResourceRef:
    """Identify both the source artifact and the object used for execution.

    ``revision`` mirrors ``effective_revision``.  The effective revision hashes
    the supplied runtime value when present, while ``source_revision`` records
    referenced file bytes independently when a source path exists.
    ``frozen_path`` and ``frozen_revision`` identify a session-owned immutable
    copy when execution must keep consuming source bytes after the snapshot.
    """

    kind: str = ""
    mode_id: str = ""
    resource_id: str = ""
    source_type: str = ""
    path: str = ""
    revision: str = ""
    source_revision: str = ""
    effective_revision: str = ""
    frozen_path: str = ""
    frozen_revision: str = ""
    status: str = "ok"
    requested_id: str = ""
    effective_id: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


__all__ = ["ResourceRef"]
