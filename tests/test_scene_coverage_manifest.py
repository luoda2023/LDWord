import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_coverage_manifest import (
    audit_scene_closure_validation_commands,
    audit_scene_pack_matrix_alignment,
    audit_scene_pack_completeness,
    build_scene_coverage_closure_summary,
    build_scene_coverage_summary,
    coverage_candidate_keys_for_config,
    coverage_packs_for_config,
    coverage_packs_for_family,
    coverage_packs_for_scene,
    coverage_packs_with_missing_closures,
    executable_scene_ids_in_coverage,
    get_capability_axis,
    get_scene_completeness_gate,
    get_scene_coverage_pack,
    get_word_risk_surface,
    get_workflow_archetype,
    list_capability_axes,
    list_scene_completeness_gates,
    list_scene_coverage_packs,
    list_word_risk_surfaces,
    list_workflow_archetypes,
    planned_family_ids_in_coverage,
)
from src.config.plugin_manual_gate import (
    get_plugin_manual_gate,
    list_plugin_manual_gates,
)
from src.config.scene_family_registry import list_planned_scene_families
from src.ui.panels.workbench.scene_presets import SCENE_META_MAP


def test_v12_coverage_manifest_has_required_high_frequency_packs():
    packs = {pack.pack_id: pack for pack in list_scene_coverage_packs()}

    assert set(packs) == {
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
    for pack in packs.values():
        assert pack.label
        assert pack.natural_requests
        assert pack.primary_landings
        assert pack.capability_axis_ids
        assert pack.boundary
        assert pack.implemented_closures
        if pack.missing_closures:
            assert pack.closure_tasks
            assert tuple(task.summary for task in pack.closure_tasks) == pack.missing_closures
        else:
            assert not pack.closure_tasks


def test_coverage_manifest_accounts_for_all_planned_scene_families():
    planned_ids = {family.family_id for family in list_planned_scene_families()}
    covered_ids = set(planned_family_ids_in_coverage())

    assert planned_ids <= covered_ids
    assert coverage_packs_for_family("contract_delivery")[0].pack_id == "contract_delivery"
    assert coverage_packs_for_family("thesis_cn")[0].pack_id == "chinese_academic"
    assert coverage_packs_for_family("exam_teaching")[0].pack_id == "exam_education"
    assert coverage_packs_for_family("form_batch_documents")[0].pack_id == "batch_forms"
    assert coverage_packs_for_family("regulated_disclosure_documents")[0].plugin_boundary is True


def test_coverage_manifest_accounts_for_executable_scene_entries_without_expanding_navigation():
    executable_ids = set(executable_scene_ids_in_coverage())

    assert set(SCENE_META_MAP) <= executable_ids
    assert coverage_packs_for_scene("bidding")[0].pack_id == "bidding_materials"
    assert {pack.pack_id for pack in coverage_packs_for_scene("report")} == {
        "quick_formatting",
        "application_reports",
    }
    assert coverage_packs_for_scene("journal_en") == ()


def test_coverage_manifest_resolves_runtime_config_candidates_for_shared_surfaces():
    config = SimpleNamespace(
        scene_id="official",
        category="government",
        compliance_profile=SimpleNamespace(
            rule_family="meeting_minutes",
            profile_id="meeting_minutes",
        ),
        input_source_profile=SimpleNamespace(
            material_schema_id="administrative_meeting_fields_v1",
            material_schema_ids=[],
        ),
    )

    candidate_keys = coverage_candidate_keys_for_config(config)
    pack_ids = {pack.pack_id for pack in coverage_packs_for_config(config)}

    assert "meeting_policy_documents" in candidate_keys
    assert "quick_formatting" in pack_ids
    assert "official_policy" in pack_ids


def test_coverage_manifest_declares_l3_capability_axes():
    axis_ids = {axis.axis_id for axis in list_capability_axes()}

    assert axis_ids == {
        "input_fact_source",
        "template_baseline",
        "material_schema",
        "structure_scope",
        "content_visibility",
        "count_profile",
        "object_preflight",
        "delivery_preset",
        "batch_preset",
        "plugin_boundary",
    }
    for pack in list_scene_coverage_packs():
        for axis_id in pack.capability_axis_ids:
            axis = get_capability_axis(axis_id)
            assert axis.question
            assert axis.typical_landings


def test_coverage_manifest_declares_completeness_gates_workflows_and_word_risks():
    gate_ids = {gate.gate_id for gate in list_scene_completeness_gates()}
    workflow_ids = {item.archetype_id for item in list_workflow_archetypes()}
    risk_ids = {item.surface_id for item in list_word_risk_surfaces()}

    assert gate_ids == {
        "natural_request_alias",
        "ownership_layer",
        "fact_source",
        "workflow_slots",
        "word_risk_surface",
        "ui_control_contract",
        "executable_chain",
        "report_issue_artifact",
        "test_evidence",
    }
    assert "structured_input" in workflow_ids
    assert "fixed_layout_table" in workflow_ids
    assert "plugin_manual_gate" in workflow_ids
    assert "fixed_row_height" in risk_ids
    assert "content_controls" in risk_ids
    assert "ole_embedded_vba" in risk_ids

    for pack in list_scene_coverage_packs():
        assert set(pack.completeness_gate_ids) == gate_ids
        assert pack.workflow_archetype_ids
        assert pack.word_risk_surface_ids
        for workflow_id in pack.workflow_archetype_ids:
            workflow = get_workflow_archetype(workflow_id)
            assert workflow.acceptance_signal
            assert set(workflow.capability_axis_ids) <= {
                axis.axis_id for axis in list_capability_axes()
            }
        for surface_id in pack.word_risk_surface_ids:
            surface = get_word_risk_surface(surface_id)
            assert surface.touchpoints
            assert surface.required_strategy

    assert audit_scene_pack_completeness() == ()


def test_coverage_manifest_matrix_keeps_high_frequency_boundary_lenses_visible():
    exam = get_scene_coverage_pack("exam_education")
    chinese = get_scene_coverage_pack("chinese_academic")
    journal = get_scene_coverage_pack("english_journal")
    forms = get_scene_coverage_pack("batch_forms")
    professional = get_scene_coverage_pack("professional_disclosure")
    import_ai = get_scene_coverage_pack("import_ai_boundary")

    assert "submission_archive" in chinese.workflow_archetype_ids
    assert "scope_localization" in journal.workflow_archetype_ids
    assert "object_safety" in journal.workflow_archetype_ids
    assert "structured_input" in exam.workflow_archetype_ids
    assert "content_visibility" in exam.workflow_archetype_ids
    assert "count_compliance" in exam.workflow_archetype_ids
    assert "plugin_manual_gate" in exam.workflow_archetype_ids
    assert "fixed_layout_table" in forms.workflow_archetype_ids
    assert "placeholder_residue" in forms.workflow_archetype_ids
    assert "fixed_row_height" in forms.word_risk_surface_ids
    assert "content_controls" in forms.word_risk_surface_ids
    assert "plugin_manual_gate" in professional.workflow_archetype_ids
    assert "submission_archive" in import_ai.workflow_archetype_ids
    assert "plugin_manual_gate" in import_ai.workflow_archetype_ids


def test_coverage_manifest_aligns_axes_workflows_and_word_risk_surfaces():
    assert audit_scene_pack_matrix_alignment() == ()


def test_coverage_manifest_keeps_professional_and_ai_boundaries_explicit():
    professional = get_scene_coverage_pack("professional_disclosure")
    import_ai = get_scene_coverage_pack("import_ai_boundary")
    exam = get_scene_coverage_pack("exam_education")
    journal = get_scene_coverage_pack("english_journal")

    assert professional.plugin_boundary is True
    assert "plugin_boundary" in professional.capability_axis_ids
    assert "audit" in professional.boundary
    assert import_ai.plugin_boundary is True
    assert "lossless import" in import_ai.boundary
    assert exam.plugin_boundary is True
    assert journal.plugin_boundary is True
    assert "publisher-final layout" in journal.boundary


def test_plugin_manual_gate_registry_covers_high_risk_boundary_packs():
    gates = {gate.pack_id: gate for gate in list_plugin_manual_gates()}
    exam = get_scene_coverage_pack("exam_education")

    assert {
        "english_journal",
        "exam_education",
        "professional_disclosure",
        "import_ai_boundary",
    } <= set(gates)
    assert get_plugin_manual_gate("english_journal").plugin_entry_id == (
        "journal_publisher_rule_review_plugin"
    )
    assert get_plugin_manual_gate("import_ai_boundary").plugin_entry_id == (
        "import_ai_assistant_plugin"
    )
    assert get_plugin_manual_gate(
        "import_ai_boundary"
    ).confidence_report_required is True
    assert get_plugin_manual_gate(
        "professional_disclosure"
    ).professional_review_required is True
    for pack_id, gate in gates.items():
        pack = get_scene_coverage_pack(pack_id)
        assert pack.plugin_boundary is True
        assert gate.manual_confirmation_required is True
        assert gate.blocks_core_execution_until_confirmed is True
    assert "complex diagram" in exam.boundary


def test_coverage_manifest_tracks_implemented_and_missing_closures_per_pack():
    packs_with_gaps = {pack.pack_id for pack in coverage_packs_with_missing_closures()}

    assert "quick_formatting" not in packs_with_gaps
    assert "chinese_academic" not in packs_with_gaps
    assert "contract_delivery" not in packs_with_gaps
    assert "batch_forms" not in packs_with_gaps
    assert "technical_long_docs" not in packs_with_gaps
    assert "exam_education" not in packs_with_gaps
    assert "english_journal" not in packs_with_gaps
    assert "official_policy" not in packs_with_gaps
    quick = get_scene_coverage_pack("quick_formatting")
    contract = get_scene_coverage_pack("contract_delivery")
    batch_forms = get_scene_coverage_pack("batch_forms")
    exam = get_scene_coverage_pack("exam_education")
    journal = get_scene_coverage_pack("english_journal")
    chinese = get_scene_coverage_pack("chinese_academic")
    official = get_scene_coverage_pack("official_policy")
    technical = get_scene_coverage_pack("technical_long_docs")
    application = get_scene_coverage_pack("application_reports")
    professional = get_scene_coverage_pack("professional_disclosure")

    assert any("explicit thesis_cn profile split" in item for item in chinese.implemented_closures)
    assert any("citation and formula confidence reporting" in item for item in chinese.implemented_closures)
    assert not any("explicit thesis_cn profile split" in item for item in chinese.missing_closures)
    assert not chinese.missing_closures
    assert any("output target issue queue" in item for item in quick.implemented_closures)
    assert any("filterable Workbench problem center" in item for item in quick.implemented_closures)
    assert not quick.missing_closures
    assert any("field consistency" in item for item in contract.implemented_closures)
    assert any("legal boundary" in item for item in contract.implemented_closures)
    assert any("signature placement" in item for item in contract.implemented_closures)
    assert not any("legal boundary" in item for item in contract.missing_closures)
    assert not contract.missing_closures
    assert any("w:trHeight" in item for item in batch_forms.implemented_closures)
    assert not any("w:trHeight" in item for item in batch_forms.missing_closures)
    assert any("textbox placeholder" in item for item in batch_forms.implemented_closures)
    assert any("tag/alias" in item for item in batch_forms.implemented_closures)
    assert any("VML shape" in item for item in batch_forms.implemented_closures)
    assert any("profile aliases" in item for item in batch_forms.implemented_closures)
    assert not any("profile aliases" in item for item in batch_forms.missing_closures)
    assert not any("fixed-layout mapping report" in item for item in batch_forms.missing_closures)
    assert any("per-record batch issue" in item for item in batch_forms.implemented_closures)
    assert any("batch issue center UI" in item for item in batch_forms.implemented_closures)
    assert any("profile-specific repair" in item for item in batch_forms.implemented_closures)
    assert not any("profile-specific repair" in item for item in batch_forms.missing_closures)
    assert any("question schema" in item for item in exam.implemented_closures)
    assert not any("question schema" in item for item in exam.missing_closures)
    assert any("student/teacher/answer" in item for item in exam.implemented_closures)
    assert not any("student/teacher/answer" in item for item in exam.missing_closures)
    assert any("AI quality" in item for item in exam.implemented_closures)
    assert not any("AI quality" in item for item in exam.missing_closures)
    assert any("BibTeX/CSL" in item for item in journal.implemented_closures)
    assert not any("BibTeX/CSL" in item for item in journal.missing_closures)
    assert any("submission package" in item for item in journal.implemented_closures)
    assert not any("submission package" in item for item in journal.missing_closures)
    assert any("reviewed journal rule" in item for item in journal.implemented_closures)
    assert not any("reviewed journal rule" in item for item in journal.missing_closures)
    assert any("numbering preservation" in item for item in official.implemented_closures)
    assert not any("numbering preservation" in item for item in official.missing_closures)
    assert any("policy archive" in item for item in official.implemented_closures)
    assert not any("policy archive" in item for item in official.missing_closures)
    assert any("chapter inventory" in item for item in technical.implemented_closures)
    assert not any("chapter inventory" in item for item in technical.missing_closures)
    assert any("proof/review/final/archive" in item for item in technical.implemented_closures)
    assert not any("proof/review/final/archive" in item for item in technical.missing_closures)
    assert not technical.missing_closures
    assert any("project attachment inventory" in item for item in application.implemented_closures)
    assert not any("project attachment inventory" in item for item in application.missing_closures)
    assert any("section word-limit" in item for item in application.implemented_closures)
    assert not any("section word-limit" in item for item in application.missing_closures)
    assert any("product/pre-sales" in item for item in application.implemented_closures)
    assert not any("product/pre-sales" in item for item in application.missing_closures)
    assert not application.missing_closures
    assert any("archive package presets" in item for item in professional.implemented_closures)
    assert not any("archive package presets" in item for item in professional.missing_closures)
    assert not professional.missing_closures


def test_coverage_manifest_missing_closures_have_action_metadata():
    allowed_priorities = {"P0", "P1", "P2"}
    allowed_owners = {"scene", "pipeline", "workbench", "plugin", "report"}
    allowed_phases = {"L3", "L4"}

    for pack in list_scene_coverage_packs():
        for task in pack.closure_tasks:
            assert task.summary
            assert task.priority in allowed_priorities
            assert task.owner in allowed_owners
            assert task.target_phase in allowed_phases
            assert task.validation_commands
            for command in task.validation_commands:
                assert command.startswith("python -m pytest ")
                assert "tests/" in command
                assert command.endswith(" -q")

    contract = get_scene_coverage_pack("contract_delivery")
    assert contract.closure_tasks == ()
    application = get_scene_coverage_pack("application_reports")
    assert application.closure_tasks == ()
    professional = get_scene_coverage_pack("professional_disclosure")
    assert professional.closure_tasks == ()


def test_coverage_manifest_validation_commands_have_static_trace_evidence():
    evidence_items = audit_scene_closure_validation_commands(ROOT)

    assert evidence_items == ()
    assert all(item.is_valid for item in evidence_items)
    for item in evidence_items:
        assert item.target_paths
        assert item.missing_paths == ()
        assert item.trace_hits


def test_coverage_manifest_lookup_failures_are_explicit():
    with pytest.raises(KeyError):
        get_scene_coverage_pack("missing_pack")
    with pytest.raises(KeyError):
        get_capability_axis("missing_axis")
    with pytest.raises(KeyError):
        get_scene_completeness_gate("missing_gate")


def test_coverage_manifest_summary_is_audit_friendly():
    summary = build_scene_coverage_summary(get_scene_coverage_pack("bidding_materials"))

    assert "bidding_materials" in summary
    assert "primary=bidding" in summary
    assert "scenes=bidding" in summary
    assert "families=qualification_archive_packages" in summary
    assert "axes=material_schema/object_preflight/delivery_preset/batch_preset" in summary
    assert "plugin=False" in summary
    assert "closures=" in summary


def test_bidding_materials_tracks_p1_closures_as_closed():
    pack = get_scene_coverage_pack("bidding_materials")

    assert (
        "qualification archive directory rules flow through schema, manifest, and package paths"
        in pack.implemented_closures
    )
    assert (
        "multi-company batch failure isolation is visible in batch payloads, reports, and UI summaries"
        in pack.implemented_closures
    )
    assert "qualification archive profile directory rules" not in pack.missing_closures
    assert "multi-company batch failure isolation UI" not in pack.missing_closures
    assert pack.missing_closures == ()


def test_coverage_manifest_closure_summary_is_audit_friendly():
    summary = build_scene_coverage_closure_summary(
        get_scene_coverage_pack("contract_delivery")
    )

    assert summary.startswith("contract_delivery: implemented=")
    assert "missing=" in summary
    assert "missing=0" in summary
    assert "next=-" in summary
