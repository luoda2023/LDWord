"""Deterministic preflight and approval evidence for document production."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from src.assistant.contracts.serialization import payload_sha256


@dataclass(frozen=True, slots=True)
class PreflightReceipt:
    preflight_id: str
    plan_id: str
    plan_revision: int
    plan_fingerprint: str
    input_hash: str
    material_context_digest: str
    output_root: str
    ready: bool
    issues: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    resource_fingerprints: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.preflight_id or not self.plan_id or self.plan_revision < 1:
            raise ValueError("Preflight identity and plan revision are required")
        object.__setattr__(self, "issues", tuple(str(item) for item in self.issues))
        object.__setattr__(self, "warnings", tuple(str(item) for item in self.warnings))
        object.__setattr__(
            self,
            "resource_fingerprints",
            {str(key): str(value) for key, value in self.resource_fingerprints.items()},
        )
        if self.ready and self.issues:
            raise ValueError("A ready preflight cannot contain blocking issues")

    def evidence_payload(self) -> dict[str, Any]:
        return {
            "preflight_id": self.preflight_id,
            "plan_id": self.plan_id,
            "plan_revision": self.plan_revision,
            "plan_fingerprint": self.plan_fingerprint,
            "input_hash": self.input_hash,
            "material_context_digest": self.material_context_digest,
            "output_root": self.output_root,
            "ready": self.ready,
            "issues": list(self.issues),
            "warnings": list(self.warnings),
            "resource_fingerprints": dict(self.resource_fingerprints),
        }

    @property
    def evidence_hash(self) -> str:
        return payload_sha256(self.evidence_payload())

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_kind": "assistant_preflight_receipt",
            **self.evidence_payload(),
            "evidence_hash": self.evidence_hash,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PreflightReceipt":
        receipt = cls(
            preflight_id=str(value.get("preflight_id") or ""),
            plan_id=str(value.get("plan_id") or ""),
            plan_revision=int(value.get("plan_revision") or 0),
            plan_fingerprint=str(value.get("plan_fingerprint") or ""),
            input_hash=str(value.get("input_hash") or ""),
            material_context_digest=str(
                value.get("material_context_digest") or ""
            ),
            output_root=str(value.get("output_root") or ""),
            ready=bool(value.get("ready", False)),
            issues=tuple(str(item) for item in value.get("issues", ())),
            warnings=tuple(str(item) for item in value.get("warnings", ())),
            resource_fingerprints=(
                value.get("resource_fingerprints")
                if isinstance(value.get("resource_fingerprints"), Mapping)
                else {}
            ),
        )
        declared = str(value.get("evidence_hash") or "")
        if declared and declared != receipt.evidence_hash:
            raise ValueError("Preflight evidence hash mismatch")
        return receipt


@dataclass(frozen=True, slots=True)
class ExecutionApproval:
    approval_id: str
    session_id: str
    plan_id: str
    plan_revision: int
    preflight_hash: str
    input_hash: str
    output_root: str
    overwrite_policy: str
    approved_at: str

    def __post_init__(self) -> None:
        if self.overwrite_policy not in {"deny", "replace_confirmed"}:
            raise ValueError("Unsupported output overwrite policy")
        for name in (
            "approval_id",
            "session_id",
            "plan_id",
            "preflight_hash",
            "input_hash",
            "approved_at",
        ):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"Execution approval {name} is required")
        if self.plan_revision < 1:
            raise ValueError("Execution approval plan revision must be positive")

    def authorizes(self, preflight: PreflightReceipt) -> bool:
        return bool(
            preflight.ready
            and self.plan_id == preflight.plan_id
            and self.plan_revision == preflight.plan_revision
            and self.preflight_hash == preflight.evidence_hash
            and self.input_hash == preflight.input_hash
            and self.output_root == preflight.output_root
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_kind": "execution_approval",
            "approval_id": self.approval_id,
            "session_id": self.session_id,
            "plan_id": self.plan_id,
            "plan_revision": self.plan_revision,
            "preflight_hash": self.preflight_hash,
            "input_hash": self.input_hash,
            "output_root": self.output_root,
            "overwrite_policy": self.overwrite_policy,
            "approved_at": self.approved_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExecutionApproval":
        return cls(
            approval_id=str(value.get("approval_id") or ""),
            session_id=str(value.get("session_id") or ""),
            plan_id=str(value.get("plan_id") or ""),
            plan_revision=int(value.get("plan_revision") or 0),
            preflight_hash=str(value.get("preflight_hash") or ""),
            input_hash=str(value.get("input_hash") or ""),
            output_root=str(value.get("output_root") or ""),
            overwrite_policy=str(value.get("overwrite_policy") or "deny"),
            approved_at=str(value.get("approved_at") or ""),
        )


__all__ = ["ExecutionApproval", "PreflightReceipt"]
