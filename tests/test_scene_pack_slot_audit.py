from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent

from src.config.scene_pack_slot_audit import (
    SCENE_PACK_SLOT_IDS,
    SLOT_STATUS_BOUNDARY,
    SLOT_STATUS_GAP,
    SLOT_STATUS_NOT_APPLICABLE,
    SLOT_STATUS_OK,
    audit_scene_pack_slot_gaps,
    audit_scene_pack_slots,
    build_scene_pack_slot_summary,
    scene_pack_slot_payload,
    scene_pack_slot_result,
)


def test_scene_pack_slot_audit_covers_all_high_frequency_packs_without_gaps():
    results = {result.pack_id: result for result in audit_scene_pack_slots(ROOT)}

    assert set(results) == {
        "quick_formatting",
        "chinese_academic",
        "english_journal",
        "exam_education",
        "bidding_materials",
        "official_policy",
        "technical_long_docs",
        "application_reports",
        "contract_delivery",
        "batch_forms",
        "professional_disclosure",
        "import_ai_boundary",
    }
    assert audit_scene_pack_slot_gaps(ROOT) == ()
    for result in results.values():
        assert result.is_clean is True
        assert result.missing_slot_ids == ()
        assert tuple(slot.slot_id for slot in result.slots) == SCENE_PACK_SLOT_IDS
        assert all(slot.status != SLOT_STATUS_GAP for slot in result.slots)


def test_scene_pack_slot_audit_locks_required_slot_evidence_for_mature_packs():
    application = scene_pack_slot_result("application_reports", ROOT)
    contract = scene_pack_slot_result("contract_delivery", ROOT)
    batch = scene_pack_slot_result("batch_forms", ROOT)

    assert application.slot("request_alias").status == SLOT_STATUS_OK
    assert "project_application" in application.slot("profile_family").evidence_items
    assert "product_sales_documents" in application.slot("profile_family").evidence_items
    assert "project_application_materials_v1" in application.slot(
        "material_schema"
    ).evidence_items
    assert "application_word_limits" in application.slot("count_profile").evidence_items
    assert "project_application_rule_defaults" in application.slot(
        "rule_source"
    ).evidence_items
    assert "material_package" in application.slot("repair_route").evidence_items

    assert "contract_delivery" in contract.slot("profile_family").evidence_items
    assert "contract_parties_v1" in contract.slot("material_schema").evidence_items
    assert "contract_fields" in contract.slot("count_profile").evidence_items
    assert "review_copy" in contract.slot("delivery_preset").evidence_items
    assert contract.slot("rule_source").status == SLOT_STATUS_NOT_APPLICABLE
    assert "tests/test_material_field_consistency.py:contract_delivery" in contract.slot(
        "test_evidence"
    ).evidence_items

    assert "form_batch_documents" in batch.slot("profile_family").evidence_items
    assert "fixed_layout" in batch.slot("repair_route").evidence_items
    assert "fixed_row_height" in batch.slot("word_risk_surface").evidence_items
    assert "batch_item_inventory" in batch.slot("count_profile").evidence_items


def test_scene_pack_slot_audit_keeps_boundary_and_not_applicable_states_explicit():
    quick = scene_pack_slot_result("quick_formatting", ROOT)
    exam = scene_pack_slot_result("exam_education", ROOT)
    import_ai = scene_pack_slot_result("import_ai_boundary", ROOT)

    assert quick.slot("material_schema").status == SLOT_STATUS_NOT_APPLICABLE
    assert quick.slot("count_profile").status == SLOT_STATUS_NOT_APPLICABLE
    assert quick.slot("rule_source").status == SLOT_STATUS_NOT_APPLICABLE

    assert exam.slot("rule_source").status == SLOT_STATUS_BOUNDARY
    assert exam.slot("rule_source").evidence_items == ("exam_ai_complex_diagram_gate",)
    assert "exam_items_v1" in exam.slot("material_schema").evidence_items
    assert "student_version" in exam.slot("delivery_preset").evidence_items

    assert import_ai.slot("profile_family").status == SLOT_STATUS_BOUNDARY
    assert import_ai.slot("delivery_preset").status == SLOT_STATUS_BOUNDARY
    assert import_ai.slot("rule_source").status == SLOT_STATUS_BOUNDARY
    assert import_ai.slot("material_schema").status == SLOT_STATUS_NOT_APPLICABLE
    assert import_ai.slot("count_profile").status == SLOT_STATUS_NOT_APPLICABLE


def test_scene_pack_slot_payload_and_summary_are_audit_friendly():
    result = scene_pack_slot_result("professional_disclosure", ROOT)
    summary = build_scene_pack_slot_summary(result)
    payload = scene_pack_slot_payload("professional_disclosure", ROOT)

    assert summary.startswith("professional_disclosure: slots=11; clean")
    assert "boundary=-" in summary
    assert payload["pack_id"] == "professional_disclosure"
    assert payload["slot_count"] == len(SCENE_PACK_SLOT_IDS)
    assert payload["gap_count"] == 0
    assert payload["boundary_slot_ids"] == []
    rule_source = next(
        slot for slot in payload["slots"] if slot["slot_id"] == "rule_source"
    )
    assert rule_source["status"] == SLOT_STATUS_OK
    assert "professional_disclosure_boundary_rules" in rule_source["evidence_items"]


def test_scene_pack_slot_lookup_failures_are_explicit():
    result = scene_pack_slot_result("chinese_academic", ROOT)

    with pytest.raises(KeyError):
        scene_pack_slot_result("missing_pack", ROOT)
    with pytest.raises(KeyError):
        result.slot("missing_slot")
