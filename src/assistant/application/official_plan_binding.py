"""Canonical binding for one Assistant-authored official-document plan.

The official document type owns the compatible built-in master.  Meeting and
archive scene-family defaults are a separate delivery choice and must not be
inferred merely because the task belongs to the official work mode.
"""

from __future__ import annotations

from dataclasses import replace

from src.assistant.contracts.document_plan import DocumentPlan
from src.assistant.contracts.task_plan import DeliveryContract
from src.config.master_library import (
    get_master,
    resolve_official_master_for_contract,
)
from src.config.official_document_profiles import (
    get_official_document_assembly_contract,
)


OFFICIAL_DELIVERY_PROFILE_KEY = "official_delivery_profile"
OFFICIAL_DELIVERY_FORMAL = "formal"
OFFICIAL_DELIVERY_INTERNAL_REVIEW = "internal_review"
OFFICIAL_DELIVERY_MEETING_ARCHIVE = "meeting_archive"

_MEETING_POLICY_FAMILY_ID = "meeting_policy_documents"
_MEETING_POLICY_PROFILE_ID = "meeting_policy_documents_default"
_MEETING_POLICY_HINTS = (
    "会议纪要",
    "制度汇编",
    "政策汇编",
    "内部传阅",
    "归档包",
    "归档清单",
    "正式归档",
    "档案归档",
)

_FORMAL_DELIVERY = DeliveryContract(
    default_preset_id="formal",
    preset_ids=("formal", "internal_review"),
    required_artifact_keys=("final_docx",),
)
_INTERNAL_REVIEW_DELIVERY = DeliveryContract(
    default_preset_id="internal_review",
    preset_ids=("formal", "internal_review"),
    required_artifact_keys=("final_docx",),
)
_MEETING_ARCHIVE_DELIVERY = DeliveryContract(
    default_preset_id="formal_minutes",
    preset_ids=(
        "internal_review",
        "formal_minutes",
        "policy_collection",
        "archive_manifest",
    ),
    required_artifact_keys=("final_docx", "material_manifest"),
)


def official_delivery_profile_for_plan(plan: DocumentPlan) -> str:
    """Return the explicit or safely inferred official delivery profile."""

    scene_ref = dict(plan.scene_ref)
    explicit = str(scene_ref.get(OFFICIAL_DELIVERY_PROFILE_KEY) or "").strip()
    if explicit in {
        OFFICIAL_DELIVERY_FORMAL,
        OFFICIAL_DELIVERY_INTERNAL_REVIEW,
        OFFICIAL_DELIVERY_MEETING_ARCHIVE,
    }:
        return explicit
    document_type_id = str(plan.production_contract.document_type_id or "").strip()
    if document_type_id == "minutes" or any(
        token in str(plan.intent or "") for token in _MEETING_POLICY_HINTS
    ):
        return OFFICIAL_DELIVERY_MEETING_ARCHIVE
    return OFFICIAL_DELIVERY_FORMAL


def bind_official_plan(
    plan: DocumentPlan,
    *,
    bump_revision: bool = False,
) -> DocumentPlan:
    """Atomically bind type, master, scene family, and delivery semantics.

    The function is intentionally idempotent.  It can therefore normalize
    plans persisted by older builds immediately before a new preflight.
    """

    production = plan.production_contract
    if production.terminal_assembler != "official":
        return plan
    document_type_id = str(production.document_type_id or "").strip()
    contract = get_official_document_assembly_contract(document_type_id)
    if contract is None:
        return plan

    requested_master_id = str(production.master_id or "").strip()
    requested_master = (
        get_master(requested_master_id, "official")
        if requested_master_id
        else None
    )
    effective_master = (
        None
        if requested_master_id and requested_master is None
        else resolve_official_master_for_contract(
            contract,
            requested=requested_master,
        )
    )
    effective_master_id = (
        str(effective_master.master_id or "").strip()
        if effective_master is not None
        else requested_master_id
    )

    delivery_profile = official_delivery_profile_for_plan(plan)
    scene_ref = dict(plan.scene_ref)
    scene_ref[OFFICIAL_DELIVERY_PROFILE_KEY] = delivery_profile
    if delivery_profile == OFFICIAL_DELIVERY_MEETING_ARCHIVE:
        scene_ref["family_id"] = _MEETING_POLICY_FAMILY_ID
        scene_ref["profile_id"] = _MEETING_POLICY_PROFILE_ID
        delivery = _MEETING_ARCHIVE_DELIVERY
        capability_ref = replace(
            plan.capability_ref,
            family_id=_MEETING_POLICY_FAMILY_ID,
            profile_id=_MEETING_POLICY_PROFILE_ID,
        )
    else:
        scene_ref.pop("family_id", None)
        scene_ref.pop("profile_id", None)
        delivery = (
            _INTERNAL_REVIEW_DELIVERY
            if delivery_profile == OFFICIAL_DELIVERY_INTERNAL_REVIEW
            else _FORMAL_DELIVERY
        )
        capability_ref = replace(
            plan.capability_ref,
            family_id="",
            profile_id="",
        )

    candidate = replace(
        plan,
        scene_ref=scene_ref,
        capability_ref=capability_ref,
        production_contract=replace(
            production,
            master_id=effective_master_id,
        ),
        delivery_contract=delivery,
    )
    if candidate.fingerprint == plan.fingerprint:
        return plan
    if bump_revision:
        candidate = replace(candidate, revision=plan.revision + 1)
    return candidate


__all__ = [
    "OFFICIAL_DELIVERY_FORMAL",
    "OFFICIAL_DELIVERY_INTERNAL_REVIEW",
    "OFFICIAL_DELIVERY_MEETING_ARCHIVE",
    "OFFICIAL_DELIVERY_PROFILE_KEY",
    "bind_official_plan",
    "official_delivery_profile_for_plan",
]
