"""User-owned fields for Assistant-authored official-document plans."""

from __future__ import annotations

from dataclasses import dataclass

from src.assistant.contracts.document_plan import DocumentPlan
from src.assistant.application.official_plan_binding import (
    OFFICIAL_DELIVERY_FORMAL,
    OFFICIAL_DELIVERY_INTERNAL_REVIEW,
    OFFICIAL_DELIVERY_MEETING_ARCHIVE,
    official_delivery_profile_for_plan,
)
from src.config.library import get_template_entry
from src.config.master_library import MasterSpec, get_master
from src.config.official_document_profiles import (
    get_official_document_assembly_contract,
    get_official_document_profile,
)

OFFICIAL_PLAN_FIELD_VALUES_KEY = "official_field_values"
_USER_OWNED_REQUIRED_FIELDS = ("recipient", "signer")


@dataclass(frozen=True, slots=True)
class OfficialFormatBinding:
    """Validated user-owned layout and delivery selection."""

    master: MasterSpec
    template_id: str
    delivery_profile: str


@dataclass(frozen=True, slots=True)
class OfficialPlanEditValues:
    document_type_id: str
    organization: str = ""
    content_requirements: str = ""
    title: str = ""
    recipient: str = ""
    signer: str = ""
    document_no: str = ""
    issue_date: str = ""
    attachment_note: str = ""
    copy_scope: str = ""
    issuer: str = ""
    printing_org: str = ""
    printing_date: str = ""
    security_level: str = ""
    urgency: str = ""
    meeting_date: str = ""
    participants: str = ""
    output_root: str = ""
    master_id: str = ""
    template_id: str = ""
    delivery_profile: str = OFFICIAL_DELIVERY_FORMAL

    @classmethod
    def from_plan(cls, plan: DocumentPlan) -> OfficialPlanEditValues:
        stored = official_plan_field_values(plan)
        document_type_id = (
            str(plan.production_contract.document_type_id or "").strip()
            or str(stored.get("document_type") or "").strip()
        )
        return cls(
            document_type_id=document_type_id,
            organization=stored.get("organization", ""),
            content_requirements=str(
                plan.scene_ref.get("official_content_requirements") or ""
            ).strip(),
            title=stored.get("title", ""),
            recipient=stored.get("recipient", ""),
            signer=stored.get("signer", ""),
            document_no=stored.get("document_no", ""),
            issue_date=stored.get("issue_date", ""),
            attachment_note=stored.get("attachment_note", ""),
            copy_scope=stored.get("copy_scope", ""),
            issuer=stored.get("issuer", ""),
            printing_org=stored.get("printing_org", ""),
            printing_date=stored.get("printing_date", ""),
            security_level=stored.get("security_level", ""),
            urgency=stored.get("urgency", ""),
            meeting_date=stored.get("meeting_date", ""),
            participants=stored.get("participants", ""),
            output_root=str(plan.output_policy.output_root or ""),
            master_id=str(plan.production_contract.master_id or "").strip(),
            template_id=str(plan.template_ref.get("id") or "").strip(),
            delivery_profile=official_delivery_profile_for_plan(plan),
        )

    def authoritative_fields(self) -> dict[str, str]:
        """Return only fields applicable to the selected document type."""

        contract = get_official_document_assembly_contract(self.document_type_id)
        applicable = (
            set(contract.applicable_material_field_keys)
            if contract is not None
            else set()
        )
        values = {
            "document_type": self.document_type_id,
            "organization": self.organization,
            "title": self.title,
            "recipient": self.recipient,
            "signer": self.signer,
            "document_no": self.document_no,
            "issue_date": self.issue_date,
            "attachment_note": self.attachment_note,
            "copy_scope": self.copy_scope,
            "issuer": self.issuer,
            "printing_org": self.printing_org,
            "printing_date": self.printing_date,
            "security_level": self.security_level,
            "urgency": self.urgency,
            "meeting_date": self.meeting_date,
            "participants": self.participants,
        }
        if (
            "issuer" in applicable
            and not str(values["issuer"] or "").strip()
            and str(values["organization"] or "").strip()
        ):
            values["issuer"] = values["organization"]
        return {
            key: str(value or "").strip()
            for key, value in values.items()
            if str(value or "").strip()
            and (key == "document_type" or key in applicable)
        }


def official_plan_field_values(plan: DocumentPlan) -> dict[str, str]:
    raw = plan.scene_ref.get(OFFICIAL_PLAN_FIELD_VALUES_KEY)
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): str(value or "").strip()
        for key, value in raw.items()
        if str(key).strip() and str(value or "").strip()
    }


def official_plan_missing_user_fields(plan: DocumentPlan) -> tuple[str, ...]:
    """Return fields that must be user-owned before model drafting starts."""

    if (
        plan.production_contract.terminal_assembler != "official"
        or not plan.generation_required
    ):
        return ()
    values = OfficialPlanEditValues.from_plan(plan)
    missing: list[str] = []
    if not values.document_type_id:
        missing.append("document_type")
    if not values.organization:
        missing.append("organization")
    if not values.content_requirements:
        missing.append("content_requirements")
    contract = get_official_document_assembly_contract(values.document_type_id)
    if contract is not None:
        required_fields = {
            binding.field_key
            for binding in contract.field_bindings
            if binding.required and binding.applicable
        }
        for field_key in _USER_OWNED_REQUIRED_FIELDS:
            if field_key not in required_fields:
                continue
            if not str(getattr(values, field_key, "") or "").strip():
                missing.append(field_key)
    return tuple(missing)


def validate_official_plan_edit_values(
    values: OfficialPlanEditValues,
) -> None:
    if not isinstance(values, OfficialPlanEditValues):
        raise TypeError("official_plan_edit_values_invalid")
    if get_official_document_profile(values.document_type_id) is None:
        raise ValueError("official_plan_document_type_required")
    if not str(values.organization or "").strip():
        raise ValueError("official_plan_organization_required")
    if not str(values.content_requirements or "").strip():
        raise ValueError("official_plan_content_requirements_required")
    contract = get_official_document_assembly_contract(values.document_type_id)
    if contract is not None:
        required_fields = {
            binding.field_key
            for binding in contract.field_bindings
            if binding.required and binding.applicable
        }
        if "recipient" in required_fields and not values.recipient.strip():
            raise ValueError("official_plan_recipient_required")
        if "signer" in required_fields and not values.signer.strip():
            raise ValueError("official_plan_signer_required")
    resolve_official_format_binding(values)


def resolve_official_format_binding(
    values: OfficialPlanEditValues,
) -> OfficialFormatBinding:
    """Validate one type/master/template/delivery selection as a unit."""

    contract = get_official_document_assembly_contract(values.document_type_id)
    if contract is None:
        raise ValueError("official_plan_document_type_required")
    master_id = str(values.master_id or contract.master_id or "").strip()
    try:
        master = get_master(master_id, "official")
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("official_plan_master_unavailable") from exc
    if master is None:
        raise ValueError("official_plan_master_unavailable")
    supported = tuple(master.supported_assembly_types or ())
    if supported and values.document_type_id not in supported:
        raise ValueError("official_plan_master_incompatible")

    template_id = (
        str(values.template_id or "").strip()
        or str(master.template_config_id or "").strip()
    )
    compatible_templates = tuple(master.compatible_template_config_ids or ())
    if compatible_templates and template_id not in compatible_templates:
        raise ValueError("official_plan_template_incompatible")
    try:
        template = get_template_entry(template_id, mode_id="official")
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("official_plan_template_unavailable") from exc
    if template is None or not bool(getattr(template, "is_available", True)):
        raise ValueError("official_plan_template_unavailable")

    delivery_profile = str(values.delivery_profile or "").strip()
    if delivery_profile not in {
        OFFICIAL_DELIVERY_FORMAL,
        OFFICIAL_DELIVERY_INTERNAL_REVIEW,
        OFFICIAL_DELIVERY_MEETING_ARCHIVE,
    }:
        raise ValueError("official_plan_delivery_invalid")
    return OfficialFormatBinding(
        master=master,
        template_id=template_id,
        delivery_profile=delivery_profile,
    )


def compose_official_plan_intent(values: OfficialPlanEditValues) -> str:
    validate_official_plan_edit_values(values)
    profile = get_official_document_profile(values.document_type_id)
    parts = [
        f"起草一份{profile.label}",
        f"发文机关：{values.organization.strip()}",
        f"内容要求：{values.content_requirements.strip()}",
    ]
    labels = (
        ("title", "标题", values.title),
        ("recipient", "主送机关", values.recipient),
        ("signer", "签发人", values.signer),
        ("document_no", "发文字号", values.document_no),
        ("issue_date", "成文日期", values.issue_date),
        ("attachment_note", "附件说明", values.attachment_note),
        ("copy_scope", "抄送机关", values.copy_scope),
        ("issuer", "落款机关", values.issuer),
        ("printing_org", "印发机关", values.printing_org),
        ("printing_date", "印发日期", values.printing_date),
        ("security_level", "密级", values.security_level),
        ("urgency", "紧急程度", values.urgency),
        ("meeting_date", "会议时间", values.meeting_date),
        ("participants", "参会人员", values.participants),
    )
    authoritative = values.authoritative_fields()
    parts.extend(
        f"{label}：{str(value).strip()}"
        for key, label, value in labels
        if key in authoritative
    )
    return "；".join(parts)


__all__ = [
    "OFFICIAL_PLAN_FIELD_VALUES_KEY",
    "OfficialFormatBinding",
    "OfficialPlanEditValues",
    "compose_official_plan_intent",
    "official_plan_field_values",
    "official_plan_missing_user_fields",
    "resolve_official_format_binding",
    "validate_official_plan_edit_values",
]
