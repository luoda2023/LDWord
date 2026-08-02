from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from src.assistant.adapters.workspace_state_adapter import WorkspaceSnapshot
from src.assistant.application.official_plan_binding import (
    OFFICIAL_DELIVERY_FORMAL,
    OFFICIAL_DELIVERY_MEETING_ARCHIVE,
    OFFICIAL_DELIVERY_PROFILE_KEY,
    bind_official_plan,
)
from src.assistant.application.plan_builder import FormDocumentPlanBuilder
from src.assistant.application.preflight_presentation import (
    active_preflight_card_presentation,
    present_preflight_card,
)
from src.assistant.contracts.execution import PreflightReceipt
from src.assistant.contracts.task_plan import DeliveryContract
from src.config.execution_target import resolve_execution_target
from src.config.library import load_scene_from_library
from src.config.official_document_profiles import (
    get_official_document_assembly_contract,
    list_official_document_profiles,
)
from src.config.scene_natural_request_router import route_natural_scene_request
from src.assistant.ui.official_clarification_mixin import _OFFICIAL_TYPE_CHOICES


def _workspace() -> WorkspaceSnapshot:
    return WorkspaceSnapshot(
        mode_id="custom",
        mode_label="通用版",
        scene_id="custom",
        scene_source_type="builtin",
        template_id="default",
        template_source_type="builtin",
        input_path="",
        input_name="",
        input_exists=False,
        material_summary={},
    )


def _plan_for_label(label: str):
    return FormDocumentPlanBuilder().build(
        query=_authoring_query(label),
        workspace=_workspace(),
        turn_id=f"turn-{label}",
    )


def _authoring_query(label: str) -> str:
    if label == "报告":
        return "请起草一份向上级报送的报告"
    return f"请起草一份{label}"


def _receipt(plan, *issues: str) -> PreflightReceipt:
    return PreflightReceipt(
        preflight_id="preflight-official-binding",
        plan_id=plan.plan_id,
        plan_revision=plan.revision,
        plan_fingerprint=plan.fingerprint,
        input_hash="input-hash",
        material_snapshot_digest="material-digest",
        output_root=plan.output_policy.output_root,
        ready=not issues,
        issues=issues,
    )


def test_all_official_document_types_bind_their_contract_master_and_route():
    profiles = list_official_document_profiles()
    assert len(profiles) == 15
    assert {item["id"] for item in _OFFICIAL_TYPE_CHOICES} == {
        profile.profile_id for profile in profiles
    }

    for profile in profiles:
        route = route_natural_scene_request(_authoring_query(profile.label))
        assert route.selected_route_id == "official_policy_documents"

        plan = _plan_for_label(profile.label)
        contract = get_official_document_assembly_contract(profile.profile_id)
        assert contract is not None
        assert plan.work_mode_id == "official"
        assert plan.production_contract.terminal_assembler == "official"
        assert plan.production_contract.document_type_id == profile.profile_id
        assert plan.production_contract.master_id == contract.master_id
        if profile.profile_id == "minutes":
            assert plan.scene_ref[OFFICIAL_DELIVERY_PROFILE_KEY] == (
                OFFICIAL_DELIVERY_MEETING_ARCHIVE
            )
            assert plan.scene_ref["family_id"] == "meeting_policy_documents"
            assert plan.delivery_contract.default_preset_id == "formal_minutes"
        else:
            assert plan.scene_ref[OFFICIAL_DELIVERY_PROFILE_KEY] == (
                OFFICIAL_DELIVERY_FORMAL
            )
            assert "family_id" not in plan.scene_ref
            assert plan.delivery_contract.default_preset_id == "formal"


def test_every_official_plan_resolves_an_approved_compatible_master():
    base_scene = load_scene_from_library("official", mode_id="official")
    for profile in list_official_document_profiles():
        plan = _plan_for_label(profile.label)
        scene = deepcopy(base_scene)
        scene.master_id = plan.production_contract.master_id
        target = resolve_execution_target(
            mode_id="official",
            scene=scene,
            official_document_type_id=profile.profile_id,
        )
        assert target.issues == ()
        assert target.master_id == plan.production_contract.master_id
        assert target.master_path


def test_legacy_official_plan_is_atomically_normalized_before_retry():
    current = _plan_for_label("函")
    legacy = replace(
        current,
        capability_ref=replace(
            current.capability_ref,
            family_id="meeting_policy_documents",
            profile_id="meeting_policy_documents_default",
        ),
        scene_ref={
            **dict(current.scene_ref),
            "family_id": "meeting_policy_documents",
            "profile_id": "meeting_policy_documents_default",
            OFFICIAL_DELIVERY_PROFILE_KEY: OFFICIAL_DELIVERY_FORMAL,
        },
        production_contract=replace(
            current.production_contract,
            master_id="official_gbt_standard",
        ),
        delivery_contract=DeliveryContract(
            default_preset_id="formal_minutes",
            preset_ids=("formal_minutes",),
            required_artifact_keys=("final_docx", "material_manifest"),
        ),
    )

    normalized = bind_official_plan(legacy, bump_revision=True)

    assert normalized.revision == legacy.revision + 1
    assert normalized.production_contract.master_id == "official_gbt_letter"
    assert normalized.capability_ref.family_id == ""
    assert "family_id" not in normalized.scene_ref
    assert normalized.delivery_contract.default_preset_id == "formal"


def test_preflight_recovery_keeps_official_repairs_inside_the_conversation():
    plan = _plan_for_label("通知")
    receipt = _receipt(plan, "approved_master_missing")

    presentation = present_preflight_card(plan, receipt)

    assert presentation.interaction_type == "preflight"
    assert {item["id"] for item in presentation.actions} == {
        "retry_preflight",
        "edit_official_plan_requirements",
    }
    assert "open_workbench" not in {item["id"] for item in presentation.actions}

    projected = active_preflight_card_presentation(
        active_plan=plan.to_dict(),
        document_job={
            "status": "preflight_failed",
            "plan_id": plan.plan_id,
            "plan_revision": plan.revision,
            "preflight": receipt.to_dict(),
        },
    )
    assert projected == presentation
