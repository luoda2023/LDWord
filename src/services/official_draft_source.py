"""Validated structured source used by Assistant-authored official documents."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
import json
from pathlib import Path
import re
from types import MappingProxyType

from src.config.official_document_profiles import (
    get_official_document_assembly_contract,
    get_official_document_profile,
)


OFFICIAL_DRAFT_SCHEMA_ID = "official_document_draft_v1"
OFFICIAL_DRAFT_SCHEMA_VERSION = 1

_EMPTY_MODEL_VALUES = frozenset(
    {
        "",
        "null",
        "none",
        "未知",
        "未提供",
        "未明确",
        "待补",
        "待补充",
    }
)
_FIELD_ALIASES = {
    "标题": "title",
    "正文": "body",
    "发文机关": "organization",
    "文号": "document_no",
    "成文日期": "issue_date",
    "签发人": "signer",
    "主送机关": "recipient",
    "主送": "recipient",
    "抄送机关": "copy_scope",
    "抄送": "copy_scope",
    "印发机关": "printing_org",
    "印发日期": "printing_date",
    "附件说明": "attachment_note",
    "附件": "attachment_note",
    "发布人": "issuer",
    "会议时间": "meeting_date",
    "参会人员": "participants",
    "密级": "security_level",
    "紧急程度": "urgency",
    "文种": "document_type",
}
_DOCUMENT_TYPE_HINTS = (
    ("会议纪要", "minutes"),
    ("纪要", "minutes"),
    ("决议", "resolution"),
    ("决定", "decision"),
    ("命令", "order"),
    ("公报", "bulletin"),
    ("公告", "announcement"),
    ("通告", "notice_public"),
    ("意见", "opinion"),
    ("通知", "notice"),
    ("通报", "circular"),
    ("报告", "report"),
    ("请示", "request"),
    ("批复", "approval"),
    ("议案", "proposal"),
    ("函", "letter"),
)
_FIELD_LABELS = {
    "title": "公文标题",
    "body": "公文正文",
    "organization": "发文机关",
    "document_no": "发文字号",
    "issue_date": "成文日期",
    "recipient": "主送机关",
    "issuer": "发布人",
    "signer": "签发人",
    "meeting_date": "会议时间",
    "participants": "参会人员",
}


@dataclass(frozen=True, slots=True)
class OfficialDraftSource:
    document_type_id: str
    fields: Mapping[str, str]
    field_provenance: Mapping[str, str]
    missing_user_fields: tuple[str, ...] = ()
    provisional_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    intent: str = ""
    preview_docx_path: str = ""
    schema_id: str = OFFICIAL_DRAFT_SCHEMA_ID
    schema_version: int = OFFICIAL_DRAFT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_id != OFFICIAL_DRAFT_SCHEMA_ID:
            raise ValueError("official_draft_schema_id_invalid")
        if self.schema_version != OFFICIAL_DRAFT_SCHEMA_VERSION:
            raise ValueError("official_draft_schema_version_unsupported")
        if get_official_document_profile(self.document_type_id) is None:
            raise ValueError(
                f"official_draft_document_type_unknown:{self.document_type_id}"
            )
        fields = _validated_text_mapping(self.fields, "fields")
        provenance = _validated_text_mapping(
            self.field_provenance,
            "field_provenance",
        )
        contract = get_official_document_assembly_contract(
            self.document_type_id
        )
        if contract is None:
            raise ValueError(
                f"official_draft_contract_missing:{self.document_type_id}"
            )
        allowed = {
            binding.field_key for binding in contract.field_bindings
        } | {"document_type"}
        unknown = sorted(set(fields) - allowed)
        if unknown:
            raise ValueError(
                "official_draft_fields_unknown:" + ",".join(unknown)
            )
        missing = _missing_required_fields(self.document_type_id, fields)
        declared_missing = tuple(dict.fromkeys(self.missing_user_fields))
        if set(declared_missing) != set(missing):
            raise ValueError("official_draft_missing_fields_mismatch")
        for key in (*declared_missing, *self.provisional_fields):
            if key not in allowed:
                raise ValueError(f"official_draft_field_unknown:{key}")
        object.__setattr__(self, "fields", MappingProxyType(fields))
        object.__setattr__(
            self,
            "field_provenance",
            MappingProxyType(provenance),
        )
        object.__setattr__(self, "missing_user_fields", missing)
        object.__setattr__(
            self,
            "provisional_fields",
            tuple(dict.fromkeys(self.provisional_fields)),
        )
        object.__setattr__(
            self,
            "warnings",
            tuple(
                dict.fromkeys(
                    str(item).strip()
                    for item in self.warnings
                    if str(item).strip()
                )
            ),
        )

    @property
    def complete(self) -> bool:
        return not self.missing_user_fields

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "document_type_id": self.document_type_id,
            "fields": dict(self.fields),
            "field_provenance": dict(self.field_provenance),
            "missing_user_fields": list(self.missing_user_fields),
            "provisional_fields": list(self.provisional_fields),
            "warnings": list(self.warnings),
            "intent": self.intent,
            "preview_docx_path": self.preview_docx_path,
        }


def infer_official_document_type_id(text: str) -> str:
    normalized = " ".join(str(text or "").split())
    for token, profile_id in _DOCUMENT_TYPE_HINTS:
        if token in normalized:
            return profile_id
    return ""


def official_field_label(field_key: str) -> str:
    return _FIELD_LABELS.get(str(field_key or ""), str(field_key or "字段"))


def compile_official_draft_text(
    generated_text: str,
    *,
    intent: str,
    document_type_id: str = "",
    authoritative_fields: Mapping[str, object] | None = None,
    today: date | None = None,
) -> OfficialDraftSource:
    raw = _json_object(generated_text)
    raw_fields = raw.get("fields")
    if not isinstance(raw_fields, Mapping):
        raw_fields = raw
    target_type = (
        str(document_type_id or "").strip()
        or _normalize_document_type(raw.get("document_type_id"))
        or _normalize_document_type(raw_fields.get("document_type"))
        or infer_official_document_type_id(intent)
    )
    if get_official_document_profile(target_type) is None:
        raise ValueError(
            f"official_draft_document_type_unknown:{target_type or 'missing'}"
        )
    contract = get_official_document_assembly_contract(target_type)
    if contract is None:
        raise ValueError(f"official_draft_contract_missing:{target_type}")
    allowed = {
        binding.field_key for binding in contract.field_bindings
    } | {"document_type"}
    fields: dict[str, str] = {}
    provenance: dict[str, str] = {}
    for raw_key, raw_value in raw_fields.items():
        key = _FIELD_ALIASES.get(str(raw_key).strip(), str(raw_key).strip())
        if key not in allowed:
            continue
        value = _model_text(raw_value)
        if value:
            fields[key] = value
            provenance[key] = "model_draft"
    for raw_key, raw_value in dict(authoritative_fields or {}).items():
        key = _FIELD_ALIASES.get(str(raw_key).strip(), str(raw_key).strip())
        if key not in allowed:
            continue
        value = _model_text(raw_value)
        if value:
            fields[key] = value
            provenance[key] = "user_material"
    fields["document_type"] = target_type
    provenance["document_type"] = "task_contract"

    provisional: list[str] = []
    warnings: list[str] = []
    if not fields.get("issue_date"):
        current = today or date.today()
        fields["issue_date"] = (
            f"{current.year}年{current.month}月{current.day}日"
        )
        provenance["issue_date"] = "auto_default"
        provisional.append("issue_date")
        warnings.append("成文日期未在材料中明确，已暂按当天日期填写，请在执行确认前核对。")
    if not fields.get("document_no"):
        fields["document_no"] = "待编"
        provenance["document_no"] = "auto_placeholder"
        provisional.append("document_no")
        warnings.append("材料未提供发文字号，已使用“待编”，未自动虚构文号。")

    missing = _missing_required_fields(target_type, fields)
    warnings.extend(
        f"缺少{official_field_label(key)}，需由用户补充或确认自动建议。"
        for key in missing
    )
    return OfficialDraftSource(
        document_type_id=target_type,
        fields=fields,
        field_provenance=provenance,
        missing_user_fields=missing,
        provisional_fields=tuple(provisional),
        warnings=tuple(warnings),
        intent=str(intent or "").strip(),
    )


def complete_official_draft_field(
    source: OfficialDraftSource,
    *,
    field_key: str,
    value: str,
) -> OfficialDraftSource:
    key = str(field_key or "").strip()
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"official_draft_field_value_required:{key}")
    contract = get_official_document_assembly_contract(
        source.document_type_id
    )
    allowed = (
        {binding.field_key for binding in contract.field_bindings}
        if contract is not None
        else set()
    )
    if key not in allowed:
        raise ValueError(f"official_draft_field_unknown:{key}")
    fields = {**dict(source.fields), key: text}
    provenance = {
        **dict(source.field_provenance),
        key: "user_confirmed",
    }
    missing = _missing_required_fields(source.document_type_id, fields)
    warnings = tuple(
        item
        for item in source.warnings
        if f"缺少{official_field_label(key)}" not in item
    )
    provisional = tuple(
        item for item in source.provisional_fields if item != key
    )
    return replace(
        source,
        fields=fields,
        field_provenance=provenance,
        missing_user_fields=missing,
        provisional_fields=provisional,
        warnings=warnings,
    )


def load_official_draft_source(path: Path | str) -> OfficialDraftSource:
    source_path = Path(path)
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("official_draft_payload_object_required")
    return OfficialDraftSource(
        schema_id=str(payload.get("schema_id") or ""),
        schema_version=int(payload.get("schema_version") or 0),
        document_type_id=str(payload.get("document_type_id") or ""),
        fields=_mapping(payload.get("fields")),
        field_provenance=_mapping(payload.get("field_provenance")),
        missing_user_fields=_strings(payload.get("missing_user_fields")),
        provisional_fields=_strings(payload.get("provisional_fields")),
        warnings=_strings(payload.get("warnings")),
        intent=str(payload.get("intent") or ""),
        preview_docx_path=str(payload.get("preview_docx_path") or ""),
    )


def write_official_draft_source(
    path: Path | str,
    source: OfficialDraftSource,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(
        json.dumps(
            source.to_dict(),
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def _missing_required_fields(
    document_type_id: str,
    fields: Mapping[str, str],
) -> tuple[str, ...]:
    contract = get_official_document_assembly_contract(document_type_id)
    if contract is None:
        return ()
    return tuple(
        binding.field_key
        for binding in contract.field_bindings
        if binding.required and not str(fields.get(binding.field_key) or "").strip()
    )


def _json_object(text: str) -> Mapping[str, object]:
    normalized = str(text or "").strip()
    if normalized.startswith("```") and normalized.endswith("```"):
        lines = normalized.splitlines()
        if len(lines) >= 3:
            normalized = "\n".join(lines[1:-1]).strip()
    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError:
        start = normalized.find("{")
        end = normalized.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("official_draft_json_invalid")
        try:
            payload = json.loads(normalized[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("official_draft_json_invalid") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("official_draft_payload_object_required")
    return payload


def _normalize_document_type(value: object) -> str:
    text = str(value or "").strip()
    if get_official_document_profile(text) is not None:
        return text
    return infer_official_document_type_id(text)


def _model_text(value: object) -> str:
    if value is None or isinstance(value, (Mapping, list, tuple, set)):
        return ""
    text = str(value).strip()
    if text.casefold() in _EMPTY_MODEL_VALUES:
        return ""
    if "\x00" in text:
        raise ValueError("official_draft_field_contains_nul")
    if len(text) > 100_000:
        raise ValueError("official_draft_field_too_large")
    return text


def _validated_text_mapping(
    value: Mapping[str, object],
    label: str,
) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise TypeError(f"official_draft_{label}_mapping_required")
    result: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key or "").strip()
        text = str(raw_value or "").strip()
        if not key or "\x00" in text:
            raise ValueError(f"official_draft_{label}_invalid")
        result[key] = text
    return result


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("official_draft_mapping_required")
    return value


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(
        str(item).strip() for item in value if str(item or "").strip()
    )


__all__ = [
    "OFFICIAL_DRAFT_SCHEMA_ID",
    "OFFICIAL_DRAFT_SCHEMA_VERSION",
    "OfficialDraftSource",
    "compile_official_draft_text",
    "complete_official_draft_field",
    "infer_official_document_type_id",
    "load_official_draft_source",
    "official_field_label",
    "write_official_draft_source",
]
