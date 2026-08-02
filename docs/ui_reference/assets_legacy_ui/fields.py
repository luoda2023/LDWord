"""Text field, alias, and label helpers for the assets panel."""

from __future__ import annotations

from datetime import date
import re
from typing import Any, Mapping

from src.config.official_material_form import official_material_field_label
from src.shared.engine.material_token_contract import parse_material_token

from src.ui.panels.assets.specs import (
    COMMON_ASSET_SLOTS,
    COMMON_FIELD_DEFS,
    FIELD_SOURCE_IMPORTED_MAPPING,
    AssetSlotSpec,
)

MATERIAL_FIELD_DRAFT_PREFIX = "__material_field_draft__"


def _parse_fields_text(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
        elif ":" in line:
            key, value = line.split(":", 1)
        else:
            continue
        key = key.strip()
        if key:
            fields[key] = value.strip()
    return fields


def _duplicate_fields_text_keys(text: str) -> tuple[str, ...]:
    """Return repeated explicit field keys without silently resolving them."""

    seen: set[str] = set()
    duplicates: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _value = line.split("=", 1)
        elif ":" in line:
            key, _value = line.split(":", 1)
        else:
            continue
        key = key.strip()
        if not key:
            continue
        if key in seen and key not in duplicates:
            duplicates.append(key)
        seen.add(key)
    return tuple(duplicates)


def _format_fields_text(fields: dict[str, str]) -> str:
    return "\n".join(f"{key}={value}" for key, value in fields.items())


def _exact_field_key(text: str) -> str:
    """Normalize only the braces, never the user's exact field name."""

    raw = str(text or "").strip()
    if raw.startswith("{{") and raw.endswith("}}"):
        raw = raw[2:-2]
    key = raw.strip()
    if not key or key != raw or any(char in key for char in "{}\r\n"):
        return ""
    return key


def _field_key_from_user_text(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    for key, label, _placeholder in COMMON_FIELD_DEFS:
        if value == key or value == label or _normalized_import_key(value) == _normalized_import_key(label):
            return key
    alias = _field_alias_for_token(value)
    if alias:
        return alias
    return value if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value) else ""


def _imported_field_keys_from_sources(field_sources: dict[str, str] | None) -> set[str]:
    return {
        str(key)
        for key, source in dict(field_sources or {}).items()
        if str(key or "").strip() and str(source or "") == FIELD_SOURCE_IMPORTED_MAPPING
    }


def _field_sources_from_imported_keys(imported_keys: set[str]) -> dict[str, str]:
    return {
        str(key): FIELD_SOURCE_IMPORTED_MAPPING
        for key in imported_keys
        if str(key or "").strip()
    }


def _normalized_field_sources(field_sources: Mapping[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_key, raw_source in field_sources.items():
        key = str(raw_key or "").strip()
        source = str(raw_source or "").strip()
        if key and source:
            normalized[_field_alias_for_token(key) or key] = source
    return normalized


def _normalized_field_aliases(field_aliases: Mapping[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_token, raw_field_key in field_aliases.items():
        token = _placeholder_key(str(raw_token or ""))
        field_key = str(raw_field_key or "").strip()
        if not token or not field_key:
            continue
        normalized[token] = _field_alias_for_token(field_key) or field_key
    return normalized


def _learned_field_alias_for_token(token: str, field_aliases: Mapping[str, str]) -> str:
    key = _placeholder_key(token)
    if key in field_aliases:
        return str(field_aliases[key] or "")
    normalized_token = _normalized_import_key(key)
    for raw_alias, field_key in field_aliases.items():
        if _normalized_import_key(raw_alias) == normalized_token:
            return str(field_key or "")
    return ""


def _field_validation_hint(key: str, value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if key == "credit_code":
        normalized = text.upper()
        if re.fullmatch(r"[0-9A-Z]{18}", normalized):
            return "格式看起来正常"
        return "格式可能不对：统一社会信用代码通常是18位数字和大写字母"
    if key == "phone":
        digits = re.sub(r"\D", "", text)
        if 7 <= len(digits) <= 16 and re.fullmatch(r"\+?[0-9][0-9\s\-()]{5,24}", text):
            return "格式看起来正常"
        return "格式可能不对：电话通常为7到16位数字，可含+、-、空格"
    if key in {"bid_date", "compile_date"}:
        if _looks_like_date(text):
            return "日期格式看起来正常"
        return "格式可能不对：日期建议写成2026年6月2日或2026-06-02"
    return ""


def _looks_like_date(text: str) -> bool:
    patterns = (
        r"(\d{4})-(\d{1,2})-(\d{1,2})",
        r"(\d{4})/(\d{1,2})/(\d{1,2})",
        r"(\d{4})年(\d{1,2})月(\d{1,2})日?",
        r"(\d{4})(\d{2})(\d{2})",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, text)
        if not match:
            continue
        year, month, day = (int(part) for part in match.groups())
        try:
            date(year, month, day)
        except ValueError:
            return False
        return True
    return False


def _field_label(key: str) -> str:
    labels = {field_key: label for field_key, label, _placeholder in COMMON_FIELD_DEFS}
    if key in labels:
        return labels[key]
    return official_material_field_label(key)


def _asset_role_label(role: str, slot_specs: tuple[AssetSlotSpec, ...] | None = None) -> str:
    for spec in slot_specs or ():
        if spec.role == role:
            return spec.label
    labels = {slot_role: label for slot_role, label, _target in COMMON_ASSET_SLOTS}
    return labels.get(role, role)


def _placeholder_key(value: str) -> str:
    text = str(value or "").strip()
    try:
        return parse_material_token(text).identifier
    except (TypeError, ValueError):
        pass
    if text.startswith("{{") and text.endswith("}}"):
        text = text[2:-2]
    return text.strip()


def _field_alias_for_token(token: str) -> str:
    normalized = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", _placeholder_key(token)).lower()
    aliases = {
        "company": "company_name",
        "companyname": "company_name",
        "companycn": "company_name",
        "corpname": "company_name",
        "enterprise": "company_name",
        "enterprisename": "company_name",
        "公司": "company_name",
        "公司名称": "company_name",
        "企业名称": "company_name",
        "单位名称": "company_name",
        "creditcode": "credit_code",
        "socialcreditcode": "credit_code",
        "unifiedsocialcreditcode": "credit_code",
        "统一社会信用代码": "credit_code",
        "信用代码": "credit_code",
        "legal": "legal_person",
        "legalperson": "legal_person",
        "legalrepresentative": "legal_person",
        "法人": "legal_person",
        "法定代表人": "legal_person",
        "addr": "address",
        "address": "address",
        "公司地址": "address",
        "地址": "address",
        "contact": "contact_name",
        "contactname": "contact_name",
        "联系人": "contact_name",
        "mobile": "phone",
        "tel": "phone",
        "telephone": "phone",
        "phone": "phone",
        "联系电话": "phone",
        "电话": "phone",
        "project": "project_name",
        "projectname": "project_name",
        "项目": "project_name",
        "项目名称": "project_name",
        "bidno": "bid_number",
        "bidnumber": "bid_number",
        "tendernumber": "bid_number",
        "招标编号": "bid_number",
        "投标编号": "bid_number",
        "biddate": "bid_date",
        "tenderdate": "bid_date",
        "投标日期": "bid_date",
        "compiledate": "compile_date",
        "preparedate": "compile_date",
        "编制日期": "compile_date",
    }
    return aliases.get(normalized, "")


def _normalized_import_key(key: str) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", str(key or "")).lower()


__all__ = [
    'MATERIAL_FIELD_DRAFT_PREFIX',
    '_parse_fields_text',
    '_duplicate_fields_text_keys',
    '_format_fields_text',
    '_field_key_from_user_text',
    '_imported_field_keys_from_sources',
    '_field_sources_from_imported_keys',
    '_normalized_field_sources',
    '_normalized_field_aliases',
    '_learned_field_alias_for_token',
    '_field_validation_hint',
    '_looks_like_date',
    '_field_label',
    '_asset_role_label',
    '_placeholder_key',
    '_field_alias_for_token',
    '_normalized_import_key',
]
