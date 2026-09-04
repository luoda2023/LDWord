"""Durable envelope for an already-bound execution material snapshot."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from src.application.materials import (
    ExecutionMaterialSnapshot,
    execution_material_snapshot_from_payload,
    execution_material_snapshot_to_payload,
)
from src.assistant.contracts.serialization import payload_sha256, plain_data


MATERIAL_EXECUTION_ENVELOPE_SCHEMA_VERSION = "material-execution-envelope-v1"


@dataclass(frozen=True, slots=True)
class MaterialExecutionEnvelope:
    snapshot: Mapping[str, object] | None
    digest: str
    schema_version: str = MATERIAL_EXECUTION_ENVELOPE_SCHEMA_VERSION

    @classmethod
    def capture(
        cls,
        snapshot: ExecutionMaterialSnapshot | None,
    ) -> "MaterialExecutionEnvelope":
        if snapshot is not None and not isinstance(
            snapshot,
            ExecutionMaterialSnapshot,
        ):
            raise TypeError("execution_material_snapshot_type_invalid")
        payload = (
            dict(plain_data(execution_material_snapshot_to_payload(snapshot)))
            if snapshot is not None
            else None
        )
        return cls(
            snapshot=payload,
            digest=_snapshot_digest(payload),
        )

    def __post_init__(self) -> None:
        if self.schema_version != MATERIAL_EXECUTION_ENVELOPE_SCHEMA_VERSION:
            raise ValueError("Unsupported material execution envelope schema")
        payload = (
            dict(plain_data(self.snapshot))
            if isinstance(self.snapshot, Mapping)
            else None
        )
        if self.digest != _snapshot_digest(payload):
            raise ValueError("Material execution envelope digest mismatch")
        object.__setattr__(self, "snapshot", payload)

    def restore(self) -> ExecutionMaterialSnapshot | None:
        if self.snapshot is None:
            return None
        return execution_material_snapshot_from_payload(self.snapshot)

    def reference(self) -> dict[str, object]:
        snapshot = self.restore()
        return {
            "schema_version": self.schema_version,
            "digest": self.digest,
            "snapshot_id": snapshot.snapshot_id if snapshot else "",
            "package_id": (
                snapshot.package_ref.package_id if snapshot else ""
            ),
            "record_count": len(snapshot.records) if snapshot else 0,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "digest": self.digest,
            "snapshot": (
                dict(self.snapshot) if self.snapshot is not None else None
            ),
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
    ) -> "MaterialExecutionEnvelope":
        snapshot = value.get("snapshot")
        return cls(
            schema_version=str(value.get("schema_version") or ""),
            digest=str(value.get("digest") or ""),
            snapshot=dict(snapshot) if isinstance(snapshot, Mapping) else None,
        )


def material_snapshot_digest(
    snapshot: ExecutionMaterialSnapshot | None,
) -> str:
    return MaterialExecutionEnvelope.capture(snapshot).digest


def _snapshot_digest(snapshot: Mapping[str, object] | None) -> str:
    return payload_sha256(
        {
            "schema_version": MATERIAL_EXECUTION_ENVELOPE_SCHEMA_VERSION,
            "snapshot": dict(snapshot) if snapshot is not None else None,
        }
    )


__all__ = [
    "MATERIAL_EXECUTION_ENVELOPE_SCHEMA_VERSION",
    "MaterialExecutionEnvelope",
    "material_snapshot_digest",
]
