"""Official-document type profiles for planning and master contracts.

These profiles describe document-type assembly expectations only. They do not
replace the existing official scene runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping


@dataclass(frozen=True, slots=True)
class OfficialDocumentTypeProfile:
    profile_id: str
    label: str
    category: str
    required_placeholders: tuple[str, ...] = ("official_title", "official_body")
    optional_placeholders: tuple[str, ...] = ()
    boundaries: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OfficialDocumentMaterialBinding:
    material_schema_id: str
    field_key: str
    placeholder_id: str
    required: bool = False
    requirement: str = ""

    @property
    def resolved_requirement(self) -> str:
        value = str(self.requirement or "").strip().lower()
        if value in {"required", "optional", "conditional", "forbidden"}:
            return value
        return "required" if self.required else "optional"

    @property
    def applicable(self) -> bool:
        return self.resolved_requirement != "forbidden"


@dataclass(frozen=True, slots=True)
class OfficialDocumentAssemblyContract:
    profile_id: str
    master_id: str
    material_schema_ids: tuple[str, ...]
    field_bindings: tuple[OfficialDocumentMaterialBinding, ...]
    delivery_versions: tuple[str, ...]
    boundaries: tuple[str, ...] = ()

    @property
    def placeholder_ids(self) -> tuple[str, ...]:
        return tuple(binding.placeholder_id for binding in self.field_bindings)

    @property
    def material_field_keys(self) -> tuple[str, ...]:
        """Return every field registered by the contract, including forbidden ones.

        A forbidden field is still a known field. Keeping it in this inventory lets
        import and compatibility layers distinguish "known but not applicable" from
        genuinely unknown user data.
        """
        return tuple(binding.field_key for binding in self.field_bindings)

    @property
    def applicable_material_field_keys(self) -> tuple[str, ...]:
        """Return fields that the selected document profile may consume."""
        return tuple(
            binding.field_key
            for binding in self.field_bindings
            if binding.applicable
        )


@dataclass(frozen=True, slots=True)
class OfficialDocumentPlanEntryDecision:
    profile_id: str
    entry_kind: str
    plan_id: str = ""
    rationale: str = ""


_COMMON_OPTIONAL_PLACEHOLDERS = (
    "official_security_level",
    "official_urgency",
    "official_organization",
    "official_document_no",
    "official_recipient",
    "official_attachment_note",
    "official_issuer",
    "official_issue_date",
    "official_copy_scope",
    "official_printing_org",
    "official_printing_date",
    "official_signer",
)

_RELEASE_BOUNDARIES = (
    "does not certify official release validity",
    "does not verify seal legality",
    "does not replace archive-office approval",
)

_OFFICIAL_GBT_MASTER_ID = "official_gbt_standard"
_OFFICIAL_MASTER_BY_PROFILE_ID = {
    "order": "official_gbt_order",
    "report": "official_gbt_upward",
    "request": "official_gbt_upward",
    "proposal": "official_gbt_upward",
    "letter": "official_gbt_letter",
    "minutes": "official_gbt_minutes",
}

_COMMON_MATERIAL_SCHEMA_IDS = ("official_document_v1",)
_MEETING_MATERIAL_SCHEMA_IDS = (
    "official_document_v1",
    "administrative_meeting_fields_v1",
)

_DELIVERY_VERSIONS = (
    "official_docx",
    "internal_review_docx",
    "archive_manifest",
    "review_pdf",
)

_COMMON_FIELD_BINDINGS = (
    OfficialDocumentMaterialBinding(
        "official_document_v1",
        "title",
        "official_title",
        required=True,
    ),
    OfficialDocumentMaterialBinding(
        "official_document_v1",
        "body",
        "official_body",
        required=True,
    ),
    OfficialDocumentMaterialBinding(
        "official_document_v1",
        "organization",
        "official_organization",
        required=True,
    ),
    OfficialDocumentMaterialBinding(
        "official_document_v1",
        "document_no",
        "official_document_no",
        required=True,
    ),
    OfficialDocumentMaterialBinding(
        "official_document_v1",
        "recipient",
        "official_recipient",
    ),
    OfficialDocumentMaterialBinding(
        "official_document_v1",
        "attachment_note",
        "official_attachment_note",
    ),
    OfficialDocumentMaterialBinding(
        "official_document_v1",
        "issuer",
        "official_issuer",
    ),
    OfficialDocumentMaterialBinding(
        "official_document_v1",
        "issue_date",
        "official_issue_date",
        required=True,
    ),
    OfficialDocumentMaterialBinding(
        "official_document_v1",
        "copy_scope",
        "official_copy_scope",
    ),
    OfficialDocumentMaterialBinding(
        "official_document_v1",
        "printing_org",
        "official_printing_org",
    ),
    OfficialDocumentMaterialBinding(
        "official_document_v1",
        "printing_date",
        "official_printing_date",
    ),
    OfficialDocumentMaterialBinding(
        "official_document_v1",
        "security_level",
        "official_security_level",
    ),
    OfficialDocumentMaterialBinding(
        "official_document_v1",
        "urgency",
        "official_urgency",
    ),
    OfficialDocumentMaterialBinding(
        "official_document_v1",
        "signer",
        "official_signer",
    ),
)

_MEETING_FIELD_BINDINGS = (
    OfficialDocumentMaterialBinding(
        "administrative_meeting_fields_v1",
        "meeting_date",
        "official_meeting_time",
    ),
    OfficialDocumentMaterialBinding(
        "administrative_meeting_fields_v1",
        "participants",
        "official_meeting_attendees",
    ),
)


_RECIPIENT_REQUIRED_PROFILES: frozenset[str] = frozenset(
    {
        "report",
        "request",
        "approval",
        "proposal",
        "letter",
    }
)

_DOCUMENT_NO_CONDITIONAL_PROFILES = frozenset(
    {
        "bulletin",
        "announcement",
        "notice_public",
    }
)

_RECIPIENT_FORBIDDEN_PROFILES = frozenset(
    {
        "order",
        "bulletin",
        "announcement",
        "notice_public",
        "minutes",
    }
)

_ATTACHMENT_FORBIDDEN_PROFILES = frozenset({"order", "minutes"})

_SIGNER_REQUIRED_PROFILES = frozenset({"order", "report", "request", "proposal"})

_SIGNER_FORBIDDEN_PROFILES = frozenset(
    {
        "resolution",
        "decision",
        "bulletin",
        "announcement",
        "notice_public",
        "opinion",
        "notice",
        "circular",
        "approval",
        "letter",
        "minutes",
    }
)


def _profile_binding_requirement(profile_id: str, field_key: str) -> str:
    """Return the explicit form/runtime policy for one profile field."""

    if field_key == "recipient":
        if profile_id in _RECIPIENT_REQUIRED_PROFILES:
            return "required"
        if profile_id in _RECIPIENT_FORBIDDEN_PROFILES:
            return "forbidden"
        return "optional"
    if (
        field_key == "document_no"
        and profile_id in _DOCUMENT_NO_CONDITIONAL_PROFILES
    ):
        return "conditional"
    if field_key == "attachment_note":
        return (
            "forbidden"
            if profile_id in _ATTACHMENT_FORBIDDEN_PROFILES
            else "conditional"
        )
    if field_key == "issuer" and profile_id == "order":
        return "forbidden"
    if field_key == "copy_scope" and profile_id == "order":
        return "forbidden"
    if field_key == "copy_scope":
        return "conditional"
    if field_key == "signer":
        if profile_id in _SIGNER_REQUIRED_PROFILES:
            return "required"
        if profile_id in _SIGNER_FORBIDDEN_PROFILES:
            return "forbidden"
        return "conditional"
    if field_key in {"security_level", "urgency"}:
        return "forbidden" if profile_id == "order" else "optional"
    if field_key in {"printing_org", "printing_date"} and profile_id in {
        "letter",
        "order",
    }:
        return "forbidden"
    if field_key == "meeting_date":
        return "optional" if profile_id == "minutes" else "forbidden"
    if field_key == "participants":
        return "optional" if profile_id == "minutes" else "forbidden"
    return ""


def _field_bindings_for_profile(
    profile: OfficialDocumentTypeProfile,
) -> tuple[OfficialDocumentMaterialBinding, ...]:
    bindings = (
        (*_COMMON_FIELD_BINDINGS, *_MEETING_FIELD_BINDINGS)
        if profile.category == "meeting"
        else _COMMON_FIELD_BINDINGS
    )
    resolved: list[OfficialDocumentMaterialBinding] = []
    for binding in bindings:
        requirement = _profile_binding_requirement(
            profile.profile_id,
            binding.field_key,
        )
        if not requirement:
            requirement = binding.resolved_requirement
        resolved.append(
            replace(
                binding,
                required=requirement == "required",
                requirement=requirement,
            )
        )
    return tuple(resolved)


OFFICIAL_DOCUMENT_TYPE_PROFILES: tuple[OfficialDocumentTypeProfile, ...] = (
    OfficialDocumentTypeProfile(
        profile_id="resolution",
        label="决议",
        category="decision",
        optional_placeholders=_COMMON_OPTIONAL_PLACEHOLDERS,
        boundaries=_RELEASE_BOUNDARIES,
    ),
    OfficialDocumentTypeProfile(
        profile_id="decision",
        label="决定",
        category="decision",
        optional_placeholders=_COMMON_OPTIONAL_PLACEHOLDERS,
        boundaries=_RELEASE_BOUNDARIES,
    ),
    OfficialDocumentTypeProfile(
        profile_id="order",
        label="命令（令）",
        category="directive",
        optional_placeholders=_COMMON_OPTIONAL_PLACEHOLDERS,
        boundaries=_RELEASE_BOUNDARIES,
    ),
    OfficialDocumentTypeProfile(
        profile_id="bulletin",
        label="公报",
        category="announcement",
        optional_placeholders=_COMMON_OPTIONAL_PLACEHOLDERS,
        boundaries=_RELEASE_BOUNDARIES,
    ),
    OfficialDocumentTypeProfile(
        profile_id="announcement",
        label="公告",
        category="announcement",
        optional_placeholders=_COMMON_OPTIONAL_PLACEHOLDERS,
        boundaries=_RELEASE_BOUNDARIES,
    ),
    OfficialDocumentTypeProfile(
        profile_id="notice_public",
        label="通告",
        category="announcement",
        optional_placeholders=_COMMON_OPTIONAL_PLACEHOLDERS,
        boundaries=_RELEASE_BOUNDARIES,
    ),
    OfficialDocumentTypeProfile(
        profile_id="opinion",
        label="意见",
        category="advisory",
        optional_placeholders=_COMMON_OPTIONAL_PLACEHOLDERS,
        boundaries=_RELEASE_BOUNDARIES,
    ),
    OfficialDocumentTypeProfile(
        profile_id="notice",
        label="通知",
        category="notice",
        optional_placeholders=_COMMON_OPTIONAL_PLACEHOLDERS,
        boundaries=_RELEASE_BOUNDARIES,
    ),
    OfficialDocumentTypeProfile(
        profile_id="circular",
        label="通报",
        category="notice",
        optional_placeholders=_COMMON_OPTIONAL_PLACEHOLDERS,
        boundaries=_RELEASE_BOUNDARIES,
    ),
    OfficialDocumentTypeProfile(
        profile_id="report",
        label="报告",
        category="upward",
        optional_placeholders=_COMMON_OPTIONAL_PLACEHOLDERS,
        boundaries=_RELEASE_BOUNDARIES,
    ),
    OfficialDocumentTypeProfile(
        profile_id="request",
        label="请示",
        category="upward",
        optional_placeholders=_COMMON_OPTIONAL_PLACEHOLDERS,
        boundaries=_RELEASE_BOUNDARIES,
    ),
    OfficialDocumentTypeProfile(
        profile_id="approval",
        label="批复",
        category="reply",
        optional_placeholders=_COMMON_OPTIONAL_PLACEHOLDERS,
        boundaries=_RELEASE_BOUNDARIES,
    ),
    OfficialDocumentTypeProfile(
        profile_id="proposal",
        label="议案",
        category="proposal",
        optional_placeholders=_COMMON_OPTIONAL_PLACEHOLDERS,
        boundaries=_RELEASE_BOUNDARIES,
    ),
    OfficialDocumentTypeProfile(
        profile_id="letter",
        label="函",
        category="letter",
        optional_placeholders=_COMMON_OPTIONAL_PLACEHOLDERS,
        boundaries=_RELEASE_BOUNDARIES,
    ),
    OfficialDocumentTypeProfile(
        profile_id="minutes",
        label="纪要",
        category="meeting",
        optional_placeholders=(
            *_COMMON_OPTIONAL_PLACEHOLDERS,
            "official_meeting_time",
            "official_meeting_attendees",
        ),
        boundaries=_RELEASE_BOUNDARIES,
    ),
)

_PROFILE_BY_ID = {
    profile.profile_id: profile for profile in OFFICIAL_DOCUMENT_TYPE_PROFILES
}

# These high-frequency types are task attributes.  They must not be exposed
# as six near-identical processing plans.
COMMON_OFFICIAL_DOCUMENT_TYPE_IDS: tuple[str, ...] = (
    "notice",
    "letter",
    "minutes",
    "report",
    "request",
    "approval",
)

OFFICIAL_BASE_PLAN_ID = "official"

OFFICIAL_PLAN_ENTRY_BUILTIN = "builtin_plan"
OFFICIAL_PLAN_ENTRY_CANDIDATE = "plan_candidate"
OFFICIAL_PLAN_ENTRY_PROFILE_ONLY = "profile_only"

_OFFICIAL_DOCUMENT_PLAN_ENTRY_DECISIONS = (
    OfficialDocumentPlanEntryDecision(
        profile_id="notice",
        entry_kind=OFFICIAL_PLAN_ENTRY_BUILTIN,
        plan_id="official",
        rationale="default official entry with notice-compatible common fields",
    ),
    OfficialDocumentPlanEntryDecision(
        profile_id="letter",
        entry_kind=OFFICIAL_PLAN_ENTRY_PROFILE_ONLY,
        rationale="document type selected independently from the base plan",
    ),
    OfficialDocumentPlanEntryDecision(
        profile_id="minutes",
        entry_kind=OFFICIAL_PLAN_ENTRY_PROFILE_ONLY,
        rationale="meeting fields belong to the document-type contract",
    ),
    OfficialDocumentPlanEntryDecision(
        profile_id="report",
        entry_kind=OFFICIAL_PLAN_ENTRY_PROFILE_ONLY,
        rationale="document type selected independently from the base plan",
    ),
    OfficialDocumentPlanEntryDecision(
        profile_id="request",
        entry_kind=OFFICIAL_PLAN_ENTRY_PROFILE_ONLY,
        rationale="document type selected independently from the base plan",
    ),
    OfficialDocumentPlanEntryDecision(
        profile_id="approval",
        entry_kind=OFFICIAL_PLAN_ENTRY_PROFILE_ONLY,
        rationale="document type selected independently from the base plan",
    ),
    OfficialDocumentPlanEntryDecision(
        profile_id="resolution",
        entry_kind=OFFICIAL_PLAN_ENTRY_PROFILE_ONLY,
        rationale="keep as profile until layout or material fields differ",
    ),
    OfficialDocumentPlanEntryDecision(
        profile_id="decision",
        entry_kind=OFFICIAL_PLAN_ENTRY_PROFILE_ONLY,
        rationale="keep as profile until layout or material fields differ",
    ),
    OfficialDocumentPlanEntryDecision(
        profile_id="order",
        entry_kind=OFFICIAL_PLAN_ENTRY_PROFILE_ONLY,
        rationale="keep as profile until layout or material fields differ",
    ),
    OfficialDocumentPlanEntryDecision(
        profile_id="bulletin",
        entry_kind=OFFICIAL_PLAN_ENTRY_PROFILE_ONLY,
        rationale="keep as profile until layout or material fields differ",
    ),
    OfficialDocumentPlanEntryDecision(
        profile_id="announcement",
        entry_kind=OFFICIAL_PLAN_ENTRY_PROFILE_ONLY,
        rationale="keep as profile until layout or material fields differ",
    ),
    OfficialDocumentPlanEntryDecision(
        profile_id="notice_public",
        entry_kind=OFFICIAL_PLAN_ENTRY_PROFILE_ONLY,
        rationale="keep as profile until layout or material fields differ",
    ),
    OfficialDocumentPlanEntryDecision(
        profile_id="opinion",
        entry_kind=OFFICIAL_PLAN_ENTRY_PROFILE_ONLY,
        rationale="keep as profile until layout or material fields differ",
    ),
    OfficialDocumentPlanEntryDecision(
        profile_id="circular",
        entry_kind=OFFICIAL_PLAN_ENTRY_PROFILE_ONLY,
        rationale="covered by common official fields until a distinct package appears",
    ),
    OfficialDocumentPlanEntryDecision(
        profile_id="proposal",
        entry_kind=OFFICIAL_PLAN_ENTRY_PROFILE_ONLY,
        rationale="keep as profile until layout or material fields differ",
    ),
)

_PLAN_ENTRY_DECISION_BY_PROFILE_ID = {
    decision.profile_id: decision
    for decision in _OFFICIAL_DOCUMENT_PLAN_ENTRY_DECISIONS
}


def list_official_document_profiles() -> tuple[OfficialDocumentTypeProfile, ...]:
    return OFFICIAL_DOCUMENT_TYPE_PROFILES


def list_common_official_document_profiles() -> tuple[OfficialDocumentTypeProfile, ...]:
    """Return the six task document types shown on the primary workbench."""

    return tuple(
        _PROFILE_BY_ID[profile_id]
        for profile_id in COMMON_OFFICIAL_DOCUMENT_TYPE_IDS
    )


def get_official_document_profile(
    profile_id: str,
) -> OfficialDocumentTypeProfile | None:
    return _PROFILE_BY_ID.get(str(profile_id or "").strip())


def resolve_official_batch_document_type_id(
    resolved_entity_data: Mapping[str, object] | None,
    item_metadata: Mapping[str, object] | None = None,
) -> str:
    """Resolve one batch item's document type without hiding unknown values.

    The resolved execution context owns the effective field value. Import
    metadata is evidence and therefore only fills an empty context value. The
    caller remains responsible for rejecting missing or unknown profile ids.
    """

    entity_data = (
        resolved_entity_data
        if isinstance(resolved_entity_data, Mapping)
        else {}
    )
    metadata = item_metadata if isinstance(item_metadata, Mapping) else {}
    return _normalize_official_document_type_id(
        entity_data.get("document_type", "")
    ) or _normalize_official_document_type_id(
        metadata.get("official_profile_id", "")
    )


def _normalize_official_document_type_id(value: object) -> str:
    normalized = str(value or "").strip()
    if normalized.casefold().startswith("official:"):
        normalized = normalized.split(":", 1)[1].strip()
    return normalized


def list_official_document_plan_entry_decisions(
) -> tuple[OfficialDocumentPlanEntryDecision, ...]:
    return _OFFICIAL_DOCUMENT_PLAN_ENTRY_DECISIONS


def get_official_document_plan_entry_decision(
    profile_id: str,
) -> OfficialDocumentPlanEntryDecision | None:
    return _PLAN_ENTRY_DECISION_BY_PROFILE_ID.get(str(profile_id or "").strip())


def list_official_document_builtin_plan_profile_ids() -> tuple[str, ...]:
    return tuple(
        decision.profile_id
        for decision in _OFFICIAL_DOCUMENT_PLAN_ENTRY_DECISIONS
        if decision.entry_kind == OFFICIAL_PLAN_ENTRY_BUILTIN
    )


def get_official_document_assembly_contract(
    profile_id: str,
) -> OfficialDocumentAssemblyContract | None:
    profile = get_official_document_profile(profile_id)
    if profile is None:
        return None

    if profile.category == "meeting":
        schema_ids = _MEETING_MATERIAL_SCHEMA_IDS
    else:
        schema_ids = _COMMON_MATERIAL_SCHEMA_IDS
    field_bindings = _field_bindings_for_profile(profile)

    return OfficialDocumentAssemblyContract(
        profile_id=profile.profile_id,
        master_id=_OFFICIAL_MASTER_BY_PROFILE_ID.get(
            profile.profile_id,
            _OFFICIAL_GBT_MASTER_ID,
        ),
        material_schema_ids=schema_ids,
        field_bindings=field_bindings,
        delivery_versions=_DELIVERY_VERSIONS,
        boundaries=(
            *profile.boundaries,
            "material bindings are applied by the official document runtime assembly",
        ),
    )


def list_official_document_assembly_contracts(
) -> tuple[OfficialDocumentAssemblyContract, ...]:
    return tuple(
        contract
        for profile in OFFICIAL_DOCUMENT_TYPE_PROFILES
        if (contract := get_official_document_assembly_contract(profile.profile_id))
        is not None
    )


__all__ = [
    "COMMON_OFFICIAL_DOCUMENT_TYPE_IDS",
    "OFFICIAL_BASE_PLAN_ID",
    "OFFICIAL_DOCUMENT_TYPE_PROFILES",
    "OFFICIAL_PLAN_ENTRY_BUILTIN",
    "OFFICIAL_PLAN_ENTRY_CANDIDATE",
    "OFFICIAL_PLAN_ENTRY_PROFILE_ONLY",
    "OfficialDocumentAssemblyContract",
    "OfficialDocumentMaterialBinding",
    "OfficialDocumentPlanEntryDecision",
    "OfficialDocumentTypeProfile",
    "get_official_document_assembly_contract",
    "get_official_document_profile",
    "get_official_document_plan_entry_decision",
    "list_common_official_document_profiles",
    "list_official_document_assembly_contracts",
    "list_official_document_builtin_plan_profile_ids",
    "list_official_document_plan_entry_decisions",
    "list_official_document_profiles",
    "resolve_official_batch_document_type_id",
]
