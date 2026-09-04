"""Decision evidence for official-document master-family splitting."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

from src.shared.engine.official_document_sample_verification import (
    OfficialDocumentSampleVerificationResult,
)


_DEFAULT_PROFILE_IDS = (
    "notice",
    "letter",
    "minutes",
    "report",
    "request",
    "approval",
)
_SHARED_MASTER_ID = "official_gbt_standard"
_CANDIDATE_MASTER_IDS = {
    "letter": "official_gbt_letter",
    "minutes": "official_gbt_minutes",
    "report": "official_gbt_upward",
    "request": "official_gbt_upward",
}
_EXPECTED_MASTER_IDS = {
    "notice": "official_gbt_standard",
    "letter": "official_gbt_letter",
    "minutes": "official_gbt_minutes",
    "report": "official_gbt_upward",
    "request": "official_gbt_upward",
    "approval": "official_gbt_standard",
}
_STRUCTURE_ACCEPTED_STATUSES = {
    "docx_verified",
    "renderer_unavailable",
    "visual_png_ok",
    "visual_baseline_missing",
    "visual_baseline_ok",
    "visual_baseline_mismatch",
}


@dataclass(frozen=True, slots=True)
class OfficialDocumentMasterFamilyDecision:
    """Evidence-backed decision on whether official profiles need split masters."""

    status: str
    recommendation: str
    profile_ids: tuple[str, ...]
    shared_master_id: str = _SHARED_MASTER_ID
    split_candidate_profile_ids: tuple[str, ...] = ()
    candidate_master_ids: Mapping[str, str] = field(default_factory=dict)
    verification_statuses: Mapping[str, str] = field(default_factory=dict)
    baseline_statuses: Mapping[str, str] = field(default_factory=dict)
    issues: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "recommendation": self.recommendation,
            "profile_ids": list(self.profile_ids),
            "shared_master_id": self.shared_master_id,
            "split_candidate_profile_ids": list(self.split_candidate_profile_ids),
            "candidate_master_ids": dict(self.candidate_master_ids),
            "verification_statuses": dict(self.verification_statuses),
            "baseline_statuses": dict(self.baseline_statuses),
            "issues": list(self.issues),
        }


def evaluate_official_master_family_decision(
    results: Iterable[OfficialDocumentSampleVerificationResult]
    | Mapping[str, OfficialDocumentSampleVerificationResult],
    *,
    profile_ids: tuple[str, ...] = _DEFAULT_PROFILE_IDS,
    shared_master_id: str = _SHARED_MASTER_ID,
) -> OfficialDocumentMasterFamilyDecision:
    """Evaluate whether official profiles should keep sharing one master family."""

    by_profile = _result_map(results)
    required_profiles = tuple(str(profile_id or "").strip() for profile_id in profile_ids)
    verification_statuses = {
        profile_id: str(getattr(by_profile.get(profile_id), "status", "") or "")
        for profile_id in required_profiles
    }
    baseline_statuses = {
        profile_id: str(getattr(by_profile.get(profile_id), "baseline_status", "") or "")
        for profile_id in required_profiles
    }

    missing_profiles = tuple(
        profile_id for profile_id in required_profiles if by_profile.get(profile_id) is None
    )
    if missing_profiles:
        return _decision(
            "missing_verification",
            "defer_until_all_core_profiles_have_sample_verification",
            required_profiles,
            shared_master_id,
            verification_statuses,
            baseline_statuses,
            issues=tuple(
                f"missing_sample_verification: {profile_id}"
                for profile_id in missing_profiles
            ),
        )

    failed = tuple(
        profile_id
        for profile_id in required_profiles
        if verification_statuses.get(profile_id) not in _STRUCTURE_ACCEPTED_STATUSES
    )
    if failed:
        return _decision(
            "verification_failed",
            "fix_sample_generation_before_master_family_split",
            required_profiles,
            shared_master_id,
            verification_statuses,
            baseline_statuses,
            issues=tuple(
                f"sample_verification_failed: {profile_id}={verification_statuses[profile_id]}"
                for profile_id in failed
            ),
        )

    incorrectly_routed = tuple(
        profile_id
        for profile_id in required_profiles
        if str(getattr(by_profile.get(profile_id), "master_id", "") or "")
        != _EXPECTED_MASTER_IDS.get(profile_id, shared_master_id)
    )
    if incorrectly_routed:
        return _decision(
            "master_route_mismatch",
            "fix_document_type_to_layout_family_routing",
            required_profiles,
            shared_master_id,
            verification_statuses,
            baseline_statuses,
            split_candidates=incorrectly_routed,
            issues=tuple(
                "master_route_mismatch: "
                f"{profile_id}="
                f"{getattr(by_profile.get(profile_id), 'master_id', '') or '-'}; "
                f"expected={_EXPECTED_MASTER_IDS.get(profile_id, shared_master_id)}"
                for profile_id in incorrectly_routed
            ),
        )

    mismatched_profiles = tuple(
        profile_id
        for profile_id in required_profiles
        if verification_statuses.get(profile_id) == "visual_baseline_mismatch"
        or baseline_statuses.get(profile_id) == "baseline_mismatch"
    )
    if mismatched_profiles:
        return _decision(
            "split_candidate_detected",
            "review_visual_mismatch_before_creating_split_master_files",
            required_profiles,
            shared_master_id,
            verification_statuses,
            baseline_statuses,
            split_candidates=tuple(
                profile_id
                for profile_id in mismatched_profiles
                if profile_id in _CANDIDATE_MASTER_IDS
            ),
            issues=tuple(
                f"visual_baseline_mismatch: {profile_id}"
                for profile_id in mismatched_profiles
            ),
        )

    if all(
        verification_statuses.get(profile_id) == "visual_baseline_ok"
        and baseline_statuses.get(profile_id) == "baseline_ok"
        for profile_id in required_profiles
    ):
        return _decision(
            "split_master_family_accepted",
            "keep_document_types_routed_to_verified_layout_families",
            required_profiles,
            shared_master_id,
            verification_statuses,
            baseline_statuses,
        )

    return _decision(
        "defer_visual_baseline_required",
        "do_not_split_master_family_until_core_profile_visual_baselines_pass",
        required_profiles,
        shared_master_id,
        verification_statuses,
        baseline_statuses,
        issues=("visual_baseline_required_before_master_family_split",),
    )


def write_official_master_family_decision_manifest(
    decision: OfficialDocumentMasterFamilyDecision,
    path: Path | str,
) -> Path:
    """Write a decision manifest for product review and later UI surfacing."""

    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(decision.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def _decision(
    status: str,
    recommendation: str,
    profile_ids: tuple[str, ...],
    shared_master_id: str,
    verification_statuses: Mapping[str, str],
    baseline_statuses: Mapping[str, str],
    *,
    split_candidates: tuple[str, ...] = (),
    issues: tuple[str, ...] = (),
) -> OfficialDocumentMasterFamilyDecision:
    return OfficialDocumentMasterFamilyDecision(
        status=status,
        recommendation=recommendation,
        profile_ids=profile_ids,
        shared_master_id=shared_master_id,
        split_candidate_profile_ids=split_candidates,
        candidate_master_ids={
            profile_id: _CANDIDATE_MASTER_IDS.get(
                profile_id,
                _EXPECTED_MASTER_IDS.get(profile_id, shared_master_id),
            )
            for profile_id in split_candidates
        },
        verification_statuses=dict(verification_statuses),
        baseline_statuses=dict(baseline_statuses),
        issues=issues,
    )


def _result_map(
    results: Iterable[OfficialDocumentSampleVerificationResult]
    | Mapping[str, OfficialDocumentSampleVerificationResult],
) -> dict[str, OfficialDocumentSampleVerificationResult]:
    if isinstance(results, Mapping):
        iterable = results.values()
    else:
        iterable = results
    mapped: dict[str, OfficialDocumentSampleVerificationResult] = {}
    for result in iterable:
        profile_id = str(getattr(result, "profile_id", "") or "").strip()
        if profile_id:
            mapped[profile_id] = result
    return mapped


__all__ = [
    "OfficialDocumentMasterFamilyDecision",
    "evaluate_official_master_family_decision",
    "write_official_master_family_decision_manifest",
]
