"""Canonical, UI-independent evidence for one DOCX object preflight."""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, is_dataclass
from hashlib import sha256
import json
from pathlib import Path

from src.shared.files.content_hash import file_content_revision
from src.shared.engine.object_preflight import (
    ObjectPreflightFinding,
    ObjectPreflightResult,
    inspect_docx_package,
    object_preflight_module_skips,
    refine_section_format_module_skips,
)


@dataclass(frozen=True, slots=True)
class ObjectPreflightEvidence:
    """Deeply immutable receipt for one canonical object-preflight payload.

    ``payload_json`` is the immutable source of truth. ``payload`` and
    ``to_payload`` deserialize a fresh value on every access so callers cannot
    mutate evidence retained by this receipt.
    """

    applicable: bool
    scene_id: str
    source_path: str
    source_revision: str
    context_revision: str
    evidence_digest: str
    canonical_key: str
    payload_json: str

    @property
    def payload(self) -> dict[str, object]:
        return self.to_payload()

    @property
    def blocked(self) -> bool:
        return bool(self.to_payload().get("blocked", False))

    def to_payload(self) -> dict[str, object]:
        payload = json.loads(self.payload_json)
        if not isinstance(payload, dict):  # defensive invariant for manual construction
            raise ValueError("object_preflight_evidence_payload_not_object")
        return payload

    def to_dict(self) -> dict[str, object]:
        return {
            "applicable": self.applicable,
            "scene_id": self.scene_id,
            "source_path": self.source_path,
            "source_revision": self.source_revision,
            "context_revision": self.context_revision,
            "evidence_digest": self.evidence_digest,
            "canonical_key": self.canonical_key,
            "payload": self.to_payload(),
        }


def object_preflight_evidence_applicable(
    scene,
    source_path: str | Path | None,
) -> bool:
    """Return whether a source must produce object-preflight evidence."""

    normalized_path = _canonical_source_path(source_path)
    compliance = getattr(scene, "compliance_profile", None)
    policy = getattr(compliance, "object_preflight", None)
    return bool(
        normalized_path
        and Path(normalized_path).suffix.lower() == ".docx"
        and policy is not None
        and bool(getattr(policy, "enabled", True))
    )


def build_object_preflight_evidence(
    scene,
    source_path: str | Path | None,
) -> ObjectPreflightEvidence:
    """Inspect one source and bind the exact result to a stable digest.

    The source is hashed immediately before and after the package inspection.
    A read failure or revision change replaces scan findings with one blocking
    safety finding, because the inspection can no longer describe a stable
    source.
    """

    scene_id = str(getattr(scene, "scene_id", "") or "").strip()
    normalized_path = _canonical_source_path(source_path)
    if not object_preflight_evidence_applicable(scene, normalized_path):
        return _not_applicable_evidence(
            scene_id=scene_id,
            source_path=normalized_path,
        )

    compliance = getattr(scene, "compliance_profile", None)
    policy = copy.deepcopy(getattr(compliance, "object_preflight"))
    strict_mode = bool(getattr(scene, "strict_mode", True))
    failure_policy = str(
        getattr(compliance, "failure_policy", "") or ""
    ).strip()
    path = Path(normalized_path)
    context_revision = _context_revision(
        scene_id=scene_id,
        source_path=normalized_path,
        strict_mode=strict_mode,
        failure_policy=failure_policy,
        policy=policy,
    )

    revision_before = _read_source_revision(path)
    inspection_read_failed = False
    try:
        result = inspect_docx_package(path, policy)
    except OSError:
        inspection_read_failed = True
        result = ObjectPreflightResult(
            source_path=normalized_path,
            findings=[
                ObjectPreflightFinding(
                    kind="object_preflight_inspection_failed",
                    location=normalized_path,
                    message=(
                        "Object preflight could not inspect a valid DOCX "
                        "package (source_unreadable)."
                    ),
                    severity="error",
                )
            ],
            inspection_status="source_unreadable",
            inspection_error="source_unreadable",
        )
    revision_after = _read_source_revision(path)
    module_skips = refine_section_format_module_skips(
        object_preflight_module_skips(result.findings, policy)
    )

    payload = _canonical_payload(
        source_path=normalized_path,
        source_revision=revision_after,
        policy=policy,
        result=result,
        module_skips=module_skips,
        strict_mode=strict_mode,
        failure_policy=failure_policy,
    )
    if inspection_read_failed or not revision_before or not revision_after:
        payload = _blocked_source_finding_payload(
            payload,
            kind="source_read_failed_during_preflight",
            source_path=normalized_path,
            message=(
                "The source document could not be read consistently while "
                "object preflight was running. Recheck file access before "
                "execution."
            ),
        )
    elif revision_before != revision_after:
        payload = _blocked_source_finding_payload(
            payload,
            kind="source_changed_during_preflight",
            source_path=normalized_path,
            message=(
                "The source document changed while object preflight was "
                "running. Recheck the document before execution."
            ),
        )

    return _evidence_from_payload(
        scene_id=scene_id,
        source_path=normalized_path,
        context_revision=context_revision,
        payload=payload,
    )


def object_preflight_evidence_is_current(
    evidence: ObjectPreflightEvidence,
    scene,
    source_path: str | Path | None,
) -> bool:
    """Cheaply validate a cached UI receipt without repeating package inspection."""

    if not isinstance(evidence, ObjectPreflightEvidence):
        return False
    if not evidence.applicable or evidence.blocked or not evidence.source_revision:
        return False
    normalized_path = _canonical_source_path(source_path)
    if not normalized_path or normalized_path != evidence.source_path:
        return False
    compliance = getattr(scene, "compliance_profile", None)
    policy = getattr(compliance, "object_preflight", None)
    if policy is None or not bool(getattr(policy, "enabled", True)):
        return False
    current_context_revision = _context_revision(
        scene_id=str(getattr(scene, "scene_id", "") or "").strip(),
        source_path=normalized_path,
        strict_mode=bool(getattr(scene, "strict_mode", True)),
        failure_policy=str(
            getattr(compliance, "failure_policy", "") or ""
        ).strip(),
        policy=policy,
    )
    if current_context_revision != evidence.context_revision:
        return False
    return _read_source_revision(Path(normalized_path)) == evidence.source_revision


def _canonical_payload(
    *,
    source_path: str,
    source_revision: str,
    policy,
    result: ObjectPreflightResult,
    module_skips: dict[str, dict[str, object]],
    strict_mode: bool,
    failure_policy: str,
) -> dict[str, object]:
    blocking_findings = list(result.blocking_findings)
    skip_modules_by_finding = {
        str(kind): _string_list(modules)
        for kind, modules in dict(
            getattr(policy, "skip_modules_by_finding", {}) or {}
        ).items()
    }
    return {
        "enabled": True,
        "source_path": source_path,
        "source_revision": source_revision,
        "inspection_status": str(result.inspection_status or ""),
        "inspection_error": str(result.inspection_error or ""),
        "preservation_mode": str(
            getattr(policy, "preservation_mode", "") or ""
        ),
        "scan_targets": _string_list(getattr(policy, "scan_targets", []) or []),
        "block_on": _string_list(getattr(policy, "block_on", []) or []),
        "skip_high_risk_modules": bool(
            getattr(policy, "skip_high_risk_modules", True)
        ),
        "skip_modules_by_finding": skip_modules_by_finding,
        "findings_count": len(result.findings),
        "findings": [asdict(finding) for finding in result.findings],
        "blocking_findings_count": len(blocking_findings),
        "blocked": (
            not result.inspection_succeeded
            or (
                bool(blocking_findings)
                and (strict_mode or failure_policy == "block")
            )
        ),
        "module_skips_count": len(module_skips),
        "module_skips": list(module_skips.values()),
    }


def _blocked_source_finding_payload(
    payload: dict[str, object],
    *,
    kind: str,
    source_path: str,
    message: str,
) -> dict[str, object]:
    return {
        **payload,
        "findings_count": 1,
        "findings": [
            {
                "kind": kind,
                "location": source_path,
                "message": message,
                "severity": "error",
            }
        ],
        "blocking_findings_count": 1,
        "blocked": True,
        "module_skips_count": 0,
        "module_skips": [],
    }


def _evidence_from_payload(
    *,
    scene_id: str,
    source_path: str,
    context_revision: str,
    payload: dict[str, object],
) -> ObjectPreflightEvidence:
    canonical_key = json.dumps(
        {
            "doc_path": source_path,
            "scene_id": scene_id,
            "object_preflight": payload,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    evidence_digest = "sha256:" + sha256(canonical_key.encode("utf-8")).hexdigest()
    payload_json = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return ObjectPreflightEvidence(
        applicable=True,
        scene_id=scene_id,
        source_path=source_path,
        source_revision=str(payload.get("source_revision") or "").strip(),
        context_revision=context_revision,
        evidence_digest=evidence_digest,
        canonical_key=canonical_key,
        payload_json=payload_json,
    )


def _not_applicable_evidence(
    *,
    scene_id: str,
    source_path: str,
) -> ObjectPreflightEvidence:
    return ObjectPreflightEvidence(
        applicable=False,
        scene_id=scene_id,
        source_path=source_path,
        source_revision="",
        context_revision="",
        evidence_digest="",
        canonical_key="",
        payload_json="{}",
    )


def _canonical_source_path(source_path: str | Path | None) -> str:
    raw_path = str(source_path or "").strip()
    if not raw_path:
        return ""
    path = Path(raw_path).expanduser()
    try:
        return str(path.resolve(strict=False))
    except (OSError, RuntimeError):
        return str(path)


def _read_source_revision(path: Path) -> str:
    try:
        return str(file_content_revision(path) or "").strip()
    except OSError:
        return ""


def _context_revision(
    *,
    scene_id: str,
    source_path: str,
    strict_mode: bool,
    failure_policy: str,
    policy,
) -> str:
    if is_dataclass(policy):
        policy_payload = asdict(policy)
    elif hasattr(policy, "__dict__"):
        policy_payload = dict(policy.__dict__)
    else:
        policy_payload = repr(policy)
    encoded = json.dumps(
        {
            "scene_id": scene_id,
            "source_path": source_path,
            "strict_mode": strict_mode,
            "failure_policy": failure_policy,
            "policy": policy_payload,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def _string_list(values) -> list[str]:
    return [
        str(item or "").strip()
        for item in list(values or [])
        if str(item or "").strip()
    ]


__all__ = [
    "ObjectPreflightEvidence",
    "build_object_preflight_evidence",
    "object_preflight_evidence_applicable",
    "object_preflight_evidence_is_current",
]
