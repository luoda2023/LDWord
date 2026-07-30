"""Shared form projection for official-document material fields.

The projection is the only UI-facing interpretation of an official document
contract.  DOCX placeholder scans are intentionally not consulted here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.config.official_document_profiles import (
    OfficialDocumentMaterialBinding,
    get_official_document_assembly_contract,
)


@dataclass(frozen=True, slots=True)
class OfficialMaterialFieldSpec:
    field_key: str
    label: str
    editor_kind: str = "single_line"
    group: str = "core"
    source_scope: str = "task"
    order: int = 0


@dataclass(frozen=True, slots=True)
class OfficialMaterialFieldProjection:
    spec: OfficialMaterialFieldSpec
    binding: OfficialDocumentMaterialBinding
    requirement: str
    value: str = ""
    visible: bool = True

    @property
    def field_key(self) -> str:
        return self.spec.field_key

    @property
    def label(self) -> str:
        return self.spec.label

    @property
    def placeholder_id(self) -> str:
        return self.binding.placeholder_id

    @property
    def required(self) -> bool:
        return self.requirement == "required"


@dataclass(frozen=True, slots=True)
class OfficialMaterialFormProjection:
    profile_id: str
    fields: tuple[OfficialMaterialFieldProjection, ...] = ()
    schema_ids: tuple[str, ...] = ()

    @property
    def field_keys(self) -> tuple[str, ...]:
        return tuple(field.field_key for field in self.fields)

    @property
    def visible_field_keys(self) -> tuple[str, ...]:
        return tuple(field.field_key for field in self.fields if field.visible)

    @property
    def required_field_keys(self) -> tuple[str, ...]:
        return tuple(field.field_key for field in self.fields if field.required)

    @property
    def missing_required_field_keys(self) -> tuple[str, ...]:
        return tuple(
            field.field_key
            for field in self.fields
            if field.required and not field.value.strip()
        )


OFFICIAL_MATERIAL_FIELD_SPECS: tuple[OfficialMaterialFieldSpec, ...] = (
    OfficialMaterialFieldSpec("title", "标题", "single_line", "core", "task", 10),
    OfficialMaterialFieldSpec("body", "正文", "multiline", "core", "task", 20),
    OfficialMaterialFieldSpec(
        "organization",
        "发文机关",
        "single_line",
        "core",
        "organization_default",
        30,
    ),
    OfficialMaterialFieldSpec(
        "document_no",
        "发文字号",
        "single_line",
        "core",
        "task",
        40,
    ),
    OfficialMaterialFieldSpec(
        "security_level",
        "密级和保密期限",
        "single_line",
        "routing",
        "task",
        42,
    ),
    OfficialMaterialFieldSpec(
        "urgency",
        "紧急程度",
        "single_line",
        "routing",
        "task",
        44,
    ),
    OfficialMaterialFieldSpec(
        "signer",
        "签发人",
        "single_line",
        "routing",
        "task",
        46,
    ),
    OfficialMaterialFieldSpec(
        "issue_date",
        "成文日期",
        "date",
        "core",
        "task",
        50,
    ),
    OfficialMaterialFieldSpec(
        "recipient",
        "主送机关",
        "multi_value",
        "routing",
        "task",
        60,
    ),
    OfficialMaterialFieldSpec(
        "attachment_note",
        "附件说明",
        "attachment_list",
        "closing",
        "task",
        70,
    ),
    OfficialMaterialFieldSpec(
        "issuer",
        "落款机关",
        "single_line",
        "closing",
        "organization_default",
        80,
    ),
    OfficialMaterialFieldSpec(
        "meeting_date",
        "会议时间",
        "date",
        "meeting",
        "task",
        90,
    ),
    OfficialMaterialFieldSpec(
        "participants",
        "参会人员",
        "multi_value",
        "meeting",
        "task",
        100,
    ),
    OfficialMaterialFieldSpec(
        "copy_scope",
        "抄送范围",
        "multi_value",
        "imprint",
        "task",
        110,
    ),
    OfficialMaterialFieldSpec(
        "printing_org",
        "印发机关",
        "single_line",
        "imprint",
        "organization_default",
        120,
    ),
    OfficialMaterialFieldSpec(
        "printing_date",
        "印发日期",
        "date",
        "imprint",
        "generated",
        130,
    ),
)

_FIELD_SPEC_BY_KEY = {
    spec.field_key: spec for spec in OFFICIAL_MATERIAL_FIELD_SPECS
}

OFFICIAL_MATERIAL_GROUP_LABELS: dict[str, str] = {
    "core": "当前必填",
    "routing": "行文对象",
    "closing": "末尾与附件",
    "meeting": "会议资料",
    "imprint": "版记与高级",
    "archive": "归档资料",
}


def official_material_field_label(field_key: object) -> str:
    key = str(field_key or "").strip()
    spec = _FIELD_SPEC_BY_KEY.get(key)
    return spec.label if spec is not None else key


def build_official_material_form_projection(
    profile_id: str,
    values: Mapping[str, object] | None = None,
    *,
    expanded_groups: tuple[str, ...] | list[str] | set[str] = (),
) -> OfficialMaterialFormProjection:
    """Project one profile contract into stable, grouped form fields."""

    normalized_profile_id = str(profile_id or "").strip() or "notice"
    contract = get_official_document_assembly_contract(normalized_profile_id)
    if contract is None:
        return OfficialMaterialFormProjection(profile_id=normalized_profile_id)

    value_map = {
        str(key): str(value or "")
        for key, value in dict(values or {}).items()
        if str(key or "").strip()
    }
    expanded = {str(group or "").strip() for group in expanded_groups}
    fields: list[OfficialMaterialFieldProjection] = []
    for binding in contract.field_bindings:
        requirement = binding.resolved_requirement
        if requirement == "forbidden":
            continue
        spec = _FIELD_SPEC_BY_KEY.get(
            binding.field_key,
            OfficialMaterialFieldSpec(
                field_key=binding.field_key,
                label=binding.field_key,
                order=1000 + len(fields),
            ),
        )
        value = str(value_map.get(binding.field_key, "") or "")
        visible = _field_visible(
            spec,
            requirement=requirement,
            value=value,
            expanded_groups=expanded,
        )
        fields.append(
            OfficialMaterialFieldProjection(
                spec=spec,
                binding=binding,
                requirement=requirement,
                value=value,
                visible=visible,
            )
        )
    fields.sort(key=lambda field: (field.spec.order, field.field_key))
    return OfficialMaterialFormProjection(
        profile_id=contract.profile_id,
        fields=tuple(fields),
        schema_ids=contract.material_schema_ids,
    )


def _field_visible(
    spec: OfficialMaterialFieldSpec,
    *,
    requirement: str,
    value: str,
    expanded_groups: set[str],
) -> bool:
    if requirement == "required" or value.strip():
        return True
    if spec.group in {"core", "meeting"}:
        return True
    if spec.group in {"routing", "closing"}:
        return "optional" in expanded_groups or spec.group in expanded_groups
    if spec.group in {"imprint", "archive"}:
        return "advanced" in expanded_groups or spec.group in expanded_groups
    return spec.group in expanded_groups


__all__ = [
    "OFFICIAL_MATERIAL_FIELD_SPECS",
    "OFFICIAL_MATERIAL_GROUP_LABELS",
    "OfficialMaterialFieldProjection",
    "OfficialMaterialFieldSpec",
    "OfficialMaterialFormProjection",
    "build_official_material_form_projection",
    "official_material_field_label",
]
