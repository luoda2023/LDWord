from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path

from src.config.material_context import MaterialExecutionContext
from src.config.material_schema_registry import (
    evaluate_material_requirements,
    missing_material_schema_ids,
    resolve_material_schema_ids,
)
from src.config.scene import SceneWorkspace


def material_requirement_diagnostics(
    scene: SceneWorkspace,
    material_context: MaterialExecutionContext,
) -> list[dict]:
    profile = getattr(scene, "input_source_profile", None)
    if profile is None:
        return []

    schema_ids = profile_material_schema_ids(profile)
    schema_id = schema_ids[0] if schema_ids else ""
    missing_schema_ids = missing_material_schema_ids(schema_ids)
    extra_fields = list(getattr(profile, "required_material_fields", []) or [])
    extra_roles = list(getattr(profile, "required_image_roles", []) or [])
    if not schema_ids and not extra_fields and not extra_roles:
        return []

    failure_policy = material_failure_policy(scene)
    level = "error" if failure_policy == "block" else "warning"
    diagnostics: list[dict] = []
    if missing_schema_ids:
        ids = ", ".join(missing_schema_ids)
        diagnostics.append(
            {
                "rule_name": "material_schema",
                "target": "schema_registry",
                "section": "material",
                "change_type": "preflight_unknown_material_schema",
                "before": "",
                "after": "",
                "paragraph_index": -1,
                "success": False,
                "level": level,
                "schema_id": schema_id,
                "schema_ids": list(schema_ids),
                "missing_schema_ids": list(missing_schema_ids),
                "reason": f"Unknown material schema id(s): {ids}",
            }
        )

    check = evaluate_material_requirements(
        schema_id=schema_id,
        schema_ids=schema_ids,
        entity_data=getattr(material_context, "entity_data", {}) or {},
        asset_roles=material_context_asset_roles(material_context),
        extra_required_fields=extra_fields,
        extra_required_asset_roles=extra_roles,
    )
    schema_label = (
        " + ".join(check.requirements.schema_labels)
        or check.requirements.schema_label
        or check.requirements.schema_id
    )
    if check.missing_field_keys:
        fields = ", ".join(check.missing_field_keys)
        diagnostics.append(
            {
                "rule_name": "material_schema",
                "target": "required_fields",
                "section": "material",
                "change_type": "preflight_missing_material_fields",
                "before": "",
                "after": "",
                "paragraph_index": -1,
                "success": False,
                "level": level,
                "schema_id": check.requirements.schema_id,
                "schema_ids": list(check.requirements.schema_ids),
                "schema_label": schema_label,
                "missing_field_keys": list(check.missing_field_keys),
                "reason": f"Missing required material fields for {schema_label}: {fields}",
            }
        )
    if check.missing_asset_roles:
        roles = ", ".join(check.missing_asset_roles)
        diagnostics.append(
            {
                "rule_name": "material_schema",
                "target": "required_asset_roles",
                "section": "material",
                "change_type": "preflight_missing_material_assets",
                "before": "",
                "after": "",
                "paragraph_index": -1,
                "success": False,
                "level": level,
                "schema_id": check.requirements.schema_id,
                "schema_ids": list(check.requirements.schema_ids),
                "schema_label": schema_label,
                "missing_asset_roles": list(check.missing_asset_roles),
                "reason": f"Missing required material assets for {schema_label}: {roles}",
            }
        )
    return diagnostics


def question_figure_file_diagnostics(
    material_context: MaterialExecutionContext,
) -> list[dict]:
    diagnostics: list[dict] = []
    for index, item in enumerate(material_asset_items(material_context, "question_figure"), start=1):
        comparison_diagnostic = question_figure_manual_comparison_issue_diagnostic(
            item,
            index,
        )
        if comparison_diagnostic:
            diagnostics.append(comparison_diagnostic)
        path = asset_render_path(item)
        if not path:
            continue
        if Path(path).exists():
            mismatch = question_figure_filename_mismatch(item, path, index)
            if mismatch:
                diagnostics.append(mismatch)
            continue
        metadata = {
            str(key): str(value)
            for key, value in dict(getattr(item, "metadata", {}) or {}).items()
            if str(key or "").strip() and str(value or "").strip()
        }
        question_target = question_figure_target_value(metadata) or str(index)
        target_key = question_figure_item_repair_target_key(item, question_target)
        diagnostics.append(
            {
                "rule_name": "material_assets",
                "target": "question_figure",
                "section": "material",
                "change_type": "preflight_missing_question_figure_file",
                "before": path,
                "after": "",
                "paragraph_index": -1,
                "success": False,
                "level": "warning",
                "missing_asset_items": [
                    {
                        "role": "question_figure",
                        "item_id": str(getattr(item, "item_id", "") or ""),
                        "label": str(getattr(item, "label", "") or ""),
                        "path": path,
                        "metadata": metadata,
                        "question_index": question_target,
                    }
                ],
                "repair_target_type": "question_figure_item",
                "repair_target_key": target_key,
                "reason": f"Missing question figure file for question {question_target}: {path}",
            }
        )
    return diagnostics


def question_figure_manual_comparison_issue_diagnostic(
    item,
    fallback_index: int,
) -> dict | None:
    metadata = {
        str(key): str(value)
        for key, value in dict(getattr(item, "metadata", {}) or {}).items()
        if str(key or "").strip() and str(value or "").strip()
    }
    if str(metadata.get("comparison_issue_status") or "").strip().lower() != "flagged":
        return None
    question_target = question_figure_target_value(metadata) or str(fallback_index)
    target_key = question_figure_item_repair_target_key(item, question_target)
    display_name = (
        str(metadata.get("comparison_issue_display_name") or "").strip()
        or str(metadata.get("comparison_issue_reference") or "").strip()
        or str(getattr(item, "label", "") or "").strip()
        or Path(str(getattr(item, "path", "") or "")).name
        or str(getattr(item, "item_id", "") or "").strip()
    )
    issue_kind = str(metadata.get("comparison_issue_kind") or "").strip() or "题图对比"
    comparison_item = {
        "role": "question_figure",
        "item_id": str(getattr(item, "item_id", "") or ""),
        "label": str(getattr(item, "label", "") or ""),
        "path": asset_render_path(item),
        "metadata": metadata,
        "question_index": question_target,
        "comparison_issue_type": str(
            metadata.get("comparison_issue_type") or "manual_compare"
        ),
        "comparison_issue_reference": str(
            metadata.get("comparison_issue_reference") or ""
        ),
        "comparison_issue_display_name": display_name,
        "comparison_issue_kind": issue_kind,
        "comparison_issue_marked_at": str(
            metadata.get("comparison_issue_marked_at") or ""
        ),
        "comparison_issue_summary": str(
            metadata.get("comparison_issue_summary") or ""
        ),
        "comparison_issue_region_type": str(
            metadata.get("comparison_issue_region_type") or ""
        ),
        "comparison_issue_region_summary": str(
            metadata.get("comparison_issue_region_summary") or ""
        ),
        "comparison_issue_region_json": str(
            metadata.get("comparison_issue_region_json") or ""
        ),
    }
    return {
        "rule_name": "material_assets",
        "target": "question_figure",
        "section": "material",
        "change_type": "preflight_question_figure_manual_comparison_issue",
        "before": display_name,
        "after": "",
        "paragraph_index": -1,
        "success": False,
        "level": "warning",
        "comparison_issue_items": [comparison_item],
        "repair_target_type": "question_figure_item",
        "repair_target_key": target_key,
        "reason": (
            "Manual comparison issue for question "
            f"{question_target}: {issue_kind} / {display_name}"
        ),
    }


def question_figure_filename_mismatch(item, path: str, fallback_index: int) -> dict | None:
    metadata = {
        str(key): str(value)
        for key, value in dict(getattr(item, "metadata", {}) or {}).items()
        if str(key or "").strip() and str(value or "").strip()
    }
    question_target = question_figure_target_value(metadata) or str(fallback_index)
    target_number = question_target_number(question_target)
    detected_number = question_figure_filename_question_number(path)
    if target_number is None or detected_number is None or target_number == detected_number:
        return None
    target_key = question_figure_item_repair_target_key(item, question_target)
    return {
        "rule_name": "material_assets",
        "target": "question_figure",
        "section": "material",
        "change_type": "preflight_suspicious_question_figure_mismatch",
        "before": path,
        "after": "",
        "paragraph_index": -1,
        "success": False,
        "level": "warning",
        "expected_question_index": str(target_number),
        "detected_question_index": str(detected_number),
        "suspicious_asset_items": [
            {
                "role": "question_figure",
                "item_id": str(getattr(item, "item_id", "") or ""),
                "label": str(getattr(item, "label", "") or ""),
                "path": path,
                "metadata": metadata,
                "question_index": str(question_target),
                "detected_question_index": str(detected_number),
            }
        ],
        "repair_target_type": "question_figure_item",
        "repair_target_key": target_key,
        "reason": (
            "Question figure file name looks like question "
            f"{detected_number}, but metadata targets question {target_number}: {path}"
        ),
    }


def question_figure_item_repair_target_key(item, question_target: str) -> str:
    metadata = {
        str(key): str(value)
        for key, value in dict(getattr(item, "metadata", {}) or {}).items()
        if str(key or "").strip() and str(value or "").strip()
    }
    cache_path = asset_cached_path(metadata)
    target: dict[str, str | dict[str, str]] = {
        "role": "question_figure",
        "item_id": str(getattr(item, "item_id", "") or ""),
        "question_index": str(question_target or ""),
        "path": asset_render_path(item),
        "metadata": metadata,
    }
    if cache_path:
        target["cache_path"] = cache_path
    asset_id = asset_identity_id(item)
    if asset_id:
        target["asset_id"] = asset_id
    return json.dumps(
        target,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def question_figure_target_value(metadata: Mapping[str, object]) -> str:
    metadata = dict(metadata or {})
    return (
        str(metadata.get("question_index") or metadata.get("questionIndex") or "").strip()
        or str(metadata.get("question_id") or metadata.get("questionId") or "").strip()
        or str(metadata.get("question_no") or metadata.get("questionNo") or "").strip()
        or str(metadata.get("number") or metadata.get("no") or "").strip()
    )


def question_target_number(value: object) -> int | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    if text.isdigit():
        number = int(text)
        return number if number > 0 else None
    for pattern in (
        r"^q(?:uestion)?[_\-\s]*(\d+)$",
        r"^第?[_\-\s]*(\d+)[_\-\s]*题$",
    ):
        match = re.fullmatch(pattern, text)
        if match:
            number = int(match.group(1))
            return number if number > 0 else None
    return None


def question_figure_filename_question_number(path: str) -> int | None:
    stem = Path(str(path or "")).stem.lower()
    if not stem:
        return None
    for pattern in (
        r"(?:^|[^a-z0-9])question[_\-\s]*(\d+)(?=$|[^0-9])",
        r"(?:^|[^a-z0-9])q[_\-\s]*(\d+)(?=$|[^0-9])",
        r"(?:^|[^0-9])题[_\-\s]*(\d+)(?=$|[^0-9])",
        r"第[_\-\s]*(\d+)[_\-\s]*题",
    ):
        match = re.search(pattern, stem)
        if match:
            number = int(match.group(1))
            return number if number > 0 else None
    return None


def looks_like_remote_asset_path(path: str) -> bool:
    text = str(path or "").strip().lower()
    return "://" in text or text.startswith("urn:")


def material_asset_items(
    material_context: MaterialExecutionContext,
    role: str,
) -> list:
    normalized_role = _normalize_material_key(role)
    items = []
    for item in list(getattr(material_context, "asset_items", []) or []):
        if _normalize_material_key(getattr(item, "role", "")) != normalized_role:
            continue
        path = asset_render_path(item)
        if path:
            items.append(item)
    return items


def asset_metadata(item: object) -> dict[str, object]:
    if isinstance(item, Mapping):
        metadata = item.get("metadata", {})
    else:
        metadata = getattr(item, "metadata", {})
    return dict(metadata) if isinstance(metadata, Mapping) else {}


def asset_render_path(item: object) -> str:
    raw_path = str(
        getattr(item, "path", "") if not isinstance(item, Mapping) else item.get("path") or ""
    ).strip()
    if raw_path:
        return raw_path
    return asset_cached_path(asset_metadata(item))


def asset_cached_path(metadata: Mapping[str, object]) -> str:
    for key in (
        "cache_path",
        "cachePath",
        "cached_path",
        "cachedPath",
        "local_path",
        "localPath",
        "local_cache_path",
        "localCachePath",
        "resolved_path",
        "resolvedPath",
        "download_path",
        "downloadPath",
        "asset_path",
        "assetPath",
    ):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def asset_identity_id(item: object) -> str:
    metadata = asset_metadata(item)
    return str(metadata.get("asset_id") or metadata.get("assetId") or "").strip()


def profile_material_schema_ids(profile) -> tuple[str, ...]:
    return resolve_material_schema_ids(
        str(getattr(profile, "material_schema_id", "") or ""),
        list(getattr(profile, "material_schema_ids", []) or []),
    )


def missing_asset_rule_diagnostics(missing_roles: list[str]) -> list[dict]:
    roles = tuple(
        sorted({str(role or "").strip() for role in missing_roles if str(role or "").strip()})
    )
    if not roles:
        return []
    return [
        {
            "rule_name": "material_assets",
            "target": "required_asset_roles",
            "section": "material",
            "change_type": "preflight_missing_material_assets",
            "before": "",
            "after": "",
            "paragraph_index": -1,
            "success": False,
            "level": "error",
            "missing_asset_roles": list(roles),
            "reason": "Missing required material assets: " + ", ".join(roles),
        }
    ]


def material_context_asset_roles(
    material_context: MaterialExecutionContext,
) -> list[str]:
    return [
        str(getattr(item, "role", "") or "").strip().lower().replace(" ", "_")
        for item in list(getattr(material_context, "asset_items", []) or [])
        if str(getattr(item, "role", "") or "").strip()
        and str(getattr(item, "path", "") or "").strip()
    ]


def material_failure_policy(scene: SceneWorkspace) -> str:
    profile = getattr(scene, "input_source_profile", None)
    return str(getattr(profile, "failure_policy", "warn") or "warn").strip().lower()


def material_preflight_error_text(diagnostics: list[dict]) -> str:
    reasons = [
        str(item.get("reason") or "").strip()
        for item in diagnostics
        if str(item.get("reason") or "").strip()
    ]
    return "; ".join(reasons) if reasons else "Material preflight failed"


def _normalize_material_key(value) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


__all__ = [
    "asset_cached_path",
    "asset_render_path",
    "looks_like_remote_asset_path",
    "material_asset_items",
    "material_context_asset_roles",
    "material_failure_policy",
    "material_preflight_error_text",
    "material_requirement_diagnostics",
    "missing_asset_rule_diagnostics",
    "profile_material_schema_ids",
    "question_figure_file_diagnostics",
]
