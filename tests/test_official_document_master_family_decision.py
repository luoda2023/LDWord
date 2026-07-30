import json
from pathlib import Path

from src.shared.engine.official_document_master_family_decision import (
    evaluate_official_master_family_decision,
    write_official_master_family_decision_manifest,
)
from src.shared.engine.official_document_sample_verification import (
    OfficialDocumentSampleVerificationResult,
)


def _result(
    profile_id: str,
    status: str,
    *,
    baseline_status: str = "",
    master_id: str = "",
) -> OfficialDocumentSampleVerificationResult:
    if not master_id:
        master_id = {
            "notice": "official_gbt_standard",
            "letter": "official_gbt_letter",
            "minutes": "official_gbt_minutes",
            "report": "official_gbt_upward",
            "request": "official_gbt_upward",
            "approval": "official_gbt_standard",
        }.get(profile_id, "official_gbt_standard")
    return OfficialDocumentSampleVerificationResult(
        profile_id=profile_id,
        sample_docx_path=None,
        manifest_path=Path(f"{profile_id}.json"),
        status=status,
        assembly_status="ok",
        master_id=master_id,
        baseline_status=baseline_status,
    )


def test_official_master_family_decision_defers_until_all_core_profiles_verified():
    decision = evaluate_official_master_family_decision(
        [_result("notice", "docx_verified")]
    )

    assert decision.status == "missing_verification"
    assert decision.recommendation == (
        "defer_until_all_core_profiles_have_sample_verification"
    )
    assert decision.split_candidate_profile_ids == ()
    assert "missing_sample_verification: letter" in decision.issues
    assert "missing_sample_verification: minutes" in decision.issues


def test_official_master_family_decision_blocks_when_sample_generation_fails():
    decision = evaluate_official_master_family_decision(
        [
            _result("notice", "docx_verified"),
            _result("letter", "missing_required_fields"),
            _result("minutes", "docx_verified"),
            _result("report", "docx_verified"),
            _result("request", "docx_verified"),
            _result("approval", "docx_verified"),
        ]
    )

    assert decision.status == "verification_failed"
    assert decision.recommendation == "fix_sample_generation_before_master_family_split"
    assert decision.issues == (
        "sample_verification_failed: letter=missing_required_fields",
    )


def test_official_master_family_decision_defers_without_visual_baselines():
    decision = evaluate_official_master_family_decision(
        [
            _result("notice", "docx_verified"),
            _result("letter", "renderer_unavailable"),
            _result("minutes", "visual_png_ok"),
            _result("report", "visual_png_ok"),
            _result("request", "visual_png_ok"),
            _result("approval", "visual_png_ok"),
        ]
    )

    assert decision.status == "defer_visual_baseline_required"
    assert decision.recommendation == (
        "do_not_split_master_family_until_core_profile_visual_baselines_pass"
    )
    assert decision.issues == ("visual_baseline_required_before_master_family_split",)
    assert decision.candidate_master_ids == {}


def test_official_master_family_decision_accepts_split_families_after_matching_baselines(
    tmp_path,
):
    decision = evaluate_official_master_family_decision(
        {
            "notice": _result("notice", "visual_baseline_ok", baseline_status="baseline_ok"),
            "letter": _result("letter", "visual_baseline_ok", baseline_status="baseline_ok"),
            "minutes": _result(
                "minutes",
                "visual_baseline_ok",
                baseline_status="baseline_ok",
            ),
            "report": _result(
                "report",
                "visual_baseline_ok",
                baseline_status="baseline_ok",
            ),
            "request": _result(
                "request",
                "visual_baseline_ok",
                baseline_status="baseline_ok",
            ),
            "approval": _result(
                "approval",
                "visual_baseline_ok",
                baseline_status="baseline_ok",
            ),
        }
    )
    manifest_path = write_official_master_family_decision_manifest(
        decision,
        tmp_path / "official_master_family_decision.json",
    )

    assert decision.status == "split_master_family_accepted"
    assert decision.recommendation == (
        "keep_document_types_routed_to_verified_layout_families"
    )
    assert decision.shared_master_id == "official_gbt_standard"
    assert decision.split_candidate_profile_ids == ()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["status"] == "split_master_family_accepted"
    assert payload["baseline_statuses"]["letter"] == "baseline_ok"


def test_official_master_family_decision_marks_split_candidate_on_visual_mismatch():
    decision = evaluate_official_master_family_decision(
        [
            _result("notice", "visual_baseline_ok", baseline_status="baseline_ok"),
            _result(
                "letter",
                "visual_baseline_mismatch",
                baseline_status="baseline_mismatch",
            ),
            _result("minutes", "visual_baseline_ok", baseline_status="baseline_ok"),
            _result("report", "visual_baseline_ok", baseline_status="baseline_ok"),
            _result("request", "visual_baseline_ok", baseline_status="baseline_ok"),
            _result("approval", "visual_baseline_ok", baseline_status="baseline_ok"),
        ]
    )

    assert decision.status == "split_candidate_detected"
    assert decision.recommendation == (
        "review_visual_mismatch_before_creating_split_master_files"
    )
    assert decision.split_candidate_profile_ids == ("letter",)
    assert decision.candidate_master_ids == {
        "letter": "official_gbt_letter",
    }
    assert decision.issues == ("visual_baseline_mismatch: letter",)
