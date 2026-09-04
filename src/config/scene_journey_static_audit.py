"""Explicit development/release audit for scene journey evidence.

Unlike the product runtime projection, this entry intentionally constructs
the full fixture and business-capability audits, including repository source
marker scans.  Product execution code must not import this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.scene_business_capability_matrix_audit import (
    SCENE_BUSINESS_CAPABILITY_MATRIX_AUDIT_ID,
    build_scene_business_capability_matrix_audit_report,
)
from src.config.scene_user_journey_fixture_audit import (
    SCENE_USER_JOURNEY_FIXTURE_AUDIT_SOURCE_ID,
    build_scene_user_journey_fixture_audit_report,
)


STATIC_AUDIT_EVIDENCE_SCOPE = "static_audit"


@dataclass(frozen=True, slots=True)
class SceneJourneyStaticAuditEvidence:
    """Small truthful summary of the two full development audits."""

    journey_audit_status: str
    capability_audit_status: str
    journey_path_count: int
    capability_count: int
    issue_count: int
    warning_count: int
    source_evidence_count: int
    missing_source_evidence_count: int
    evidence_scope: str = STATIC_AUDIT_EVIDENCE_SCOPE
    source_scan_performed: bool = True
    audit_ids: tuple[str, ...] = (
        SCENE_USER_JOURNEY_FIXTURE_AUDIT_SOURCE_ID,
        SCENE_BUSINESS_CAPABILITY_MATRIX_AUDIT_ID,
    )

    @property
    def status(self) -> str:
        if self.journey_audit_status == self.capability_audit_status == "passed":
            return "passed"
        return "failed"

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "evidence_scope": self.evidence_scope,
            "source_scan_performed": self.source_scan_performed,
            "audit_ids": list(self.audit_ids),
            "journey_audit_status": self.journey_audit_status,
            "capability_audit_status": self.capability_audit_status,
            "journey_path_count": self.journey_path_count,
            "capability_count": self.capability_count,
            "issue_count": self.issue_count,
            "warning_count": self.warning_count,
            "source_evidence_count": self.source_evidence_count,
            "missing_source_evidence_count": self.missing_source_evidence_count,
        }


def build_scene_journey_static_audit_evidence(
    *,
    project_root: Path | str | None = None,
) -> SceneJourneyStaticAuditEvidence:
    """Run real fixture, capability, and source-marker audits explicitly."""

    journey_report = build_scene_user_journey_fixture_audit_report(
        project_root=project_root
    )
    capability_report = build_scene_business_capability_matrix_audit_report(
        project_root=project_root
    )
    source_evidence = (
        *journey_report.source_evidence,
        *capability_report.source_evidence,
    )
    return SceneJourneyStaticAuditEvidence(
        journey_audit_status=journey_report.status,
        capability_audit_status=capability_report.status,
        journey_path_count=journey_report.path_count,
        capability_count=capability_report.capability_count,
        issue_count=journey_report.issue_count + capability_report.issue_count,
        warning_count=(
            journey_report.warning_count + capability_report.warning_count
        ),
        source_evidence_count=len(source_evidence),
        missing_source_evidence_count=sum(
            1 for evidence in source_evidence if evidence.status != "ready"
        ),
    )


__all__ = [
    "STATIC_AUDIT_EVIDENCE_SCOPE",
    "SceneJourneyStaticAuditEvidence",
    "build_scene_journey_static_audit_evidence",
]
