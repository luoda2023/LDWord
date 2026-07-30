"""Assistant artifact references; Form execution results remain authoritative."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AssistantArtifactRef:
    artifact_id: str
    kind: str
    display_name: str
    local_path_ref: str = ""
    mime_type: str = ""
    origin: str = "tool"
    execution_result_ref: str = ""
    integrity_hash: str = ""

    def __post_init__(self) -> None:
        if self.origin not in {"model", "tool", "production"}:
            raise ValueError(f"Unsupported artifact origin: {self.origin!r}")
        if not self.artifact_id or not self.kind or not self.display_name:
            raise ValueError("Artifact identity, kind and display name are required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_kind": "assistant_artifact_ref",
            "artifact_id": self.artifact_id,
            "kind": self.kind,
            "display_name": self.display_name,
            "local_path_ref": self.local_path_ref,
            "mime_type": self.mime_type,
            "origin": self.origin,
            "execution_result_ref": self.execution_result_ref,
            "integrity_hash": self.integrity_hash,
        }


__all__ = ["AssistantArtifactRef"]
