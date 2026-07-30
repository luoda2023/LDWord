from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

from docx import Document

from src.config.entity import EntityProfile
from src.config.image_materials import ImageWatermarkTextSource
from src.config.material_context import MaterialExecutionContext
from src.services.material_execution.material_snapshot_builder import (
    MaterialSnapshotBuildRequest,
    build_material_snapshot,
)
from src.config.material_schema_registry import (
    evaluate_material_requirements,
    get_material_schema,
    missing_material_schema_ids,
    resolve_material_schema_ids,
)
from src.config.scene import SceneWorkspace
from src.shared.engine.run_ops import get_full_text, iter_story_paragraphs
from src.shared.engine.material_token_contract import (
    MATERIAL_TOKEN_PATTERN,
    MaterialTokenNamespace,
    try_parse_material_token,
)
from src.config.execution_failure_policy import (
    execution_failure_policy_issue,
    normalize_execution_failure_policy,
)


def material_requirement_diagnostics(
    scene: SceneWorkspace,
    material_context: MaterialExecutionContext,
    *,
    field_resolution=None,
) -> list[dict]:
    profile = getattr(scene, "input_source_profile", None)
    if profile is None:
        return []

    schema_ids = profile_material_schema_ids(profile)
    schema_id = schema_ids[0] if schema_ids else ""
    missing_schema_ids = missing_material_schema_ids(schema_ids)
    extra_fields = list(getattr(profile, "required_material_fields", []) or [])
    extra_roles = list(getattr(profile, "required_image_roles", []) or [])
    failure_policy_issue = material_failure_policy_issue(scene)
    failure_policy = material_failure_policy(scene)
    level = "error" if failure_policy == "block" else "warning"
    if field_resolution is None:
        field_resolution = material_context.resolve_material_fields()
    diagnostics: list[dict] = [
        {
            "rule_name": "material_timeline",
            "target": str(getattr(issue, "field", "") or getattr(issue, "node_id", "") or getattr(issue, "plan_id", "")),
            "section": "material",
            "change_type": f"timeline_{str(getattr(issue, 'code', '') or 'issue')}",
            "before": "",
            "after": "",
            "paragraph_index": -1,
            "success": False,
            "level": (
                "warning"
                if str(getattr(issue, "severity", "warning")) != "error"
                else level
            ),
            "plan_id": str(getattr(issue, "plan_id", "") or ""),
            "node_id": str(getattr(issue, "node_id", "") or ""),
            "reason": str(getattr(issue, "message", "") or "时间计划计算失败"),
        }
        for issue in field_resolution.timeline_issues
    ]
    if failure_policy_issue:
        diagnostics.insert(
            0,
            {
                "rule_name": "material_failure_policy",
                "target": "input_source_profile.failure_policy",
                "section": "material",
                "change_type": "preflight_invalid_material_failure_policy",
                "before": str(
                    getattr(profile, "failure_policy", "") or ""
                ).strip(),
                "after": "",
                "paragraph_index": -1,
                "success": False,
                "level": "error",
                "diagnostic_code": "material_failure_policy_invalid",
                "reason": failure_policy_issue,
            },
        )
    diagnostics.extend(
        {
            "rule_name": "material_field_function",
            "target": field_key,
            "section": "material",
            "change_type": "field_function_error",
            "before": "",
            "after": "",
            "paragraph_index": -1,
            "success": False,
            "level": level,
            "reason": message or "字段函数无法获取实时值",
        }
        for field_key, message in field_resolution.function_errors.items()
    )
    diagnostics.extend(_context_asset_diagnostics(material_context, level=level))
    diagnostics.extend(
        _frozen_material_contract_diagnostics(
            material_context,
            field_values=field_resolution.values,
            level=level,
        )
    )
    if not schema_ids and not extra_fields and not extra_roles:
        return diagnostics
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
                # Registry integrity is not a business-level missing-material
                # policy.  An unknown schema must always stop execution.
                "level": "error",
                "schema_id": schema_id,
                "schema_ids": list(schema_ids),
                "missing_schema_ids": list(missing_schema_ids),
                "reason": f"Unknown material schema id(s): {ids}",
            }
        )

    check = evaluate_material_requirements(
        schema_id=schema_id,
        schema_ids=schema_ids,
        entity_data=field_resolution.values,
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
    diagnostics.extend(
        asset_role_contract_diagnostics(
            schema_ids,
            material_context,
            level=level,
        )
    )
    return diagnostics


def _context_asset_diagnostics(
    material_context: MaterialExecutionContext,
    *,
    level: str,
) -> list[dict]:
    diagnostics: list[dict] = []
    for item in list(getattr(material_context, "asset_diagnostics", []) or []):
        if not isinstance(item, Mapping):
            continue
        code = str(item.get("code", "") or "asset_issue")
        severity = str(item.get("severity", "warning") or "warning")
        role = str(item.get("role", "") or "")
        path = str(item.get("path", "") or "")
        if code == "asset_file_missing" and role == "question_figure":
            metadata = {
                str(key): str(value)
                for key, value in dict(item.get("metadata") or {}).items()
                if str(key or "").strip() and str(value or "").strip()
            }
            evidence = SimpleNamespace(
                role=role,
                item_id=str(item.get("item_id", "") or ""),
                label=str(item.get("label", "") or ""),
                path=path,
                metadata=metadata,
            )
            question_target = question_figure_target_value(metadata) or "?"
            diagnostics.append(
                {
                    "rule_name": "material_assets",
                    "target": role,
                    "section": "material",
                    "change_type": "preflight_missing_question_figure_file",
                    "before": path,
                    "after": "",
                    "paragraph_index": -1,
                    "success": False,
                    "level": level if severity == "error" else "warning",
                    "missing_asset_items": [
                        {
                            "role": role,
                            "item_id": evidence.item_id,
                            "label": evidence.label,
                            "path": path,
                            "metadata": metadata,
                            "question_index": question_target,
                        }
                    ],
                    "repair_target_type": "question_figure_item",
                    "repair_target_key": question_figure_item_repair_target_key(
                        evidence,
                        question_target,
                    ),
                    "reason": (
                        "Missing question figure file for question "
                        f"{question_target}: {path}"
                    ),
                }
            )
            continue
        diagnostics.append(
            {
                "rule_name": "material_assets",
                "target": role or path or "asset_binding",
                "section": "material",
                "change_type": f"preflight_{code}",
                "before": path,
                "after": "",
                "paragraph_index": -1,
                "success": False,
                "level": level if severity == "error" else "warning",
                "asset_role": role,
                "asset_path": path,
                "repair_target_type": (
                    "asset_binding"
                    if code.startswith("asset_binding") or "directory" in code
                    else "asset_item"
                ),
                "repair_target_key": role or path,
                "reason": str(item.get("message", "") or code),
            }
        )
    return diagnostics


def asset_role_contract_diagnostics(
    schema_ids: tuple[str, ...] | list[str],
    material_context: MaterialExecutionContext,
    *,
    level: str = "warning",
) -> list[dict]:
    diagnostics: list[dict] = []
    specs: dict[str, object] = {}
    for schema_id in schema_ids:
        try:
            schema = get_material_schema(schema_id)
        except KeyError:
            continue
        for spec in schema.asset_roles:
            role = _normalize_material_key(spec.role)
            if role:
                specs[role] = spec

    for role, spec in specs.items():
        items = _material_role_contract_items(material_context, role)
        cardinality = str(getattr(spec, "cardinality", "single") or "single")
        min_items = max(
            int(getattr(spec, "min_items", 0) or 0),
            1 if bool(getattr(spec, "required", False)) else 0,
        )
        max_items = getattr(spec, "max_items", 1)
        if cardinality == "single" and len(items) > 1:
            diagnostics.append(
                _asset_contract_diagnostic(
                    role,
                    "preflight_asset_single_role_multiple_items",
                    level,
                    f"Single-item role {role} resolved {len(items)} files.",
                    items,
                )
            )
        if len(items) < min_items:
            diagnostics.append(
                _asset_contract_diagnostic(
                    role,
                    "preflight_asset_group_below_min_items",
                    level,
                    f"Asset role {role} requires at least {min_items} files; got {len(items)}.",
                    items,
                )
            )
        if max_items is not None and len(items) > int(max_items):
            diagnostics.append(
                _asset_contract_diagnostic(
                    role,
                    "preflight_asset_group_above_max_items",
                    level,
                    f"Asset role {role} allows at most {max_items} files; got {len(items)}.",
                    items,
                )
            )
        sequence_values = [
            getattr(item, "sequence", None)
            for item in items
            if getattr(item, "sequence", None) is not None
        ]
        if len(sequence_values) != len(set(sequence_values)):
            diagnostics.append(
                _asset_contract_diagnostic(
                    role,
                    "preflight_asset_group_sequence_conflict",
                    level,
                    f"Asset role {role} contains duplicate sequence values.",
                    items,
                )
            )
        normalized_names = [
            _material_item_normalized_name(item).casefold()
            for item in items
            if _material_item_normalized_name(item)
        ]
        if len(normalized_names) != len(set(normalized_names)):
            diagnostics.append(
                _asset_contract_diagnostic(
                    role,
                    "preflight_asset_normalized_name_conflict",
                    level,
                    f"Asset role {role} contains duplicate normalized file names.",
                    items,
                )
            )
        for item in items:
            if role == "question_figure":
                continue
            path = asset_render_path(item)
            if not path or looks_like_remote_asset_path(path) or Path(path).is_file():
                continue
            diagnostics.append(
                _asset_contract_diagnostic(
                    role,
                    "preflight_missing_asset_file",
                    level,
                    f"Missing asset file for role {role}: {path}",
                    [item],
                )
            )
    return diagnostics


def image_anchor_diagnostics(
    doc_path: str | Path,
    scene: SceneWorkspace,
    material_context: MaterialExecutionContext,
) -> list[dict]:
    if not bool(getattr(scene, "module_switches", {}).get("image_insertion", False)):
        return []
    path = Path(doc_path)
    if path.suffix.lower() != ".docx" or not path.is_file():
        return []
    try:
        document = Document(path)
    except Exception:
        return []
    level = "error" if material_failure_policy(scene) == "block" else "warning"
    diagnostics: list[dict] = []
    paragraphs = list(iter_story_paragraphs(document))
    for rule in list(material_context.image_rules or []):
        target = getattr(rule, "target", "end")
        if isinstance(target, int):
            continue
        anchor = str(target or "").strip()
        if not anchor or anchor == "end":
            continue
        role = _normalize_material_key(getattr(rule, "asset_role", ""))
        items = material_asset_items(material_context, role)
        if not items and not bool(getattr(rule, "required", False)):
            continue
        occurrences = sum(anchor in get_full_text(paragraph) for paragraph in paragraphs)
        if occurrences == 1:
            continue
        change_type = (
            "preflight_asset_anchor_missing"
            if occurrences == 0
            else "preflight_asset_anchor_ambiguous"
        )
        diagnostics.append(
            {
                "rule_name": "material_assets",
                "target": anchor,
                "section": "material",
                "change_type": change_type,
                "before": str(occurrences),
                "after": "",
                "paragraph_index": -1,
                "success": False,
                "level": level,
                "asset_role": role,
                "anchor": anchor,
                "occurrence_count": occurrences,
                "repair_target_type": "image_anchor",
                "repair_target_key": anchor,
                "reason": (
                    f"Image anchor missing for role {role}: {anchor}"
                    if occurrences == 0
                    else f"Image anchor is ambiguous for role {role}: {anchor} ({occurrences})"
                ),
            }
        )
    return diagnostics


def undeclared_image_token_diagnostics(
    doc_path: str | Path,
    scene: SceneWorkspace,
    material_context: MaterialExecutionContext,
) -> list[dict]:
    """Block strict image tokens which have no executable binding rule."""

    if not bool(getattr(scene, "module_switches", {}).get("image_insertion", False)):
        return []
    path = Path(doc_path)
    if path.suffix.lower() != ".docx" or not path.is_file():
        return []
    try:
        document = Document(path)
    except Exception:
        return []

    declared_tokens = {
        str(getattr(rule, "anchor_token", "") or "").strip()
        for rule in dict(material_context.image_material_rules or {}).values()
        if str(getattr(rule, "anchor_token", "") or "").strip()
    }
    declared_tokens.update(
        str(getattr(rule, "target", "") or "").strip()
        for rule in list(material_context.image_rules or [])
        if str(getattr(rule, "target", "") or "").strip()
    )
    document_tokens: set[str] = set()
    for paragraph in iter_story_paragraphs(document):
        text = get_full_text(paragraph)
        for match in MATERIAL_TOKEN_PATTERN.finditer(text):
            token = "{{" + match.group(1) + "}}"
            ref = try_parse_material_token(token)
            if ref is not None and ref.namespace is MaterialTokenNamespace.IMAGE:
                document_tokens.add(ref.token)

    missing_tokens = sorted(document_tokens - declared_tokens)
    if not missing_tokens:
        return []
    level = "error" if material_failure_policy(scene) == "block" else "warning"
    return [
        {
            "rule_name": "material_images",
            "target": token,
            "section": "material",
            "change_type": "preflight_image_rule_missing",
            "before": token,
            "after": "",
            "paragraph_index": -1,
            "success": False,
            "level": level,
            "material_domain": "image",
            "diagnostic_code": "image_rule_missing",
            "repair_target_type": "image_rule",
            "repair_target_key": token,
            "reason": f"Image token has no executable material rule: {token}",
        }
        for token in missing_tokens
    ]


def _asset_contract_diagnostic(
    role: str,
    change_type: str,
    level: str,
    reason: str,
    items,
) -> dict:
    return {
        "rule_name": "material_assets",
        "target": role,
        "section": "material",
        "change_type": change_type,
        "before": "",
        "after": "",
        "paragraph_index": -1,
        "success": False,
        "level": level,
        "asset_items": [
            {
                "role": role,
                "item_id": str(getattr(item, "item_id", "") or ""),
                "path": asset_render_path(item),
                "group_id": str(getattr(item, "group_id", "") or ""),
                "sequence": getattr(item, "sequence", None),
                "normalized_name": str(
                    _material_item_normalized_name(item)
                ),
                "original_relative_path": str(
                    _material_item_original_relative_path(item)
                ),
            }
            for item in items
        ],
        "repair_target_type": "asset_group" if len(items) != 1 else "asset_item",
        "repair_target_key": role,
        "reason": reason,
    }


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
    file_ref = getattr(item, "file_ref", None)
    file_ref_path = str(getattr(file_ref, "source_path", "") or "").strip()
    if file_ref_path:
        return file_ref_path
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
    roles = [
        _normalize_material_key(getattr(item, "role", ""))
        for item in list(getattr(material_context, "asset_items", []) or [])
        if str(getattr(item, "role", "") or "").strip()
        and str(getattr(item, "path", "") or "").strip()
    ]
    roles.extend(
        _normalize_material_key(role)
        for role, binding in dict(
            getattr(material_context, "attachment_bindings", {}) or {}
        ).items()
        if list(getattr(binding, "items", ()) or ())
    )
    return list(dict.fromkeys(role for role in roles if role))


def _frozen_material_contract_diagnostics(
    material_context: MaterialExecutionContext,
    *,
    field_values: Mapping[str, object],
    level: str,
) -> list[dict]:
    content_bindings = dict(
        getattr(material_context, "content_bindings", {}) or {}
    )
    content_rules = list(getattr(material_context, "content_rules", []) or [])
    attachment_bindings = dict(
        getattr(material_context, "attachment_bindings", {}) or {}
    )
    image_material_rules = dict(
        getattr(material_context, "image_material_rules", {}) or {}
    )
    if (
        not content_bindings
        and not content_rules
        and not attachment_bindings
        and not image_material_rules
    ):
        return []

    # Reuse the persisted typed contract for structural/uniqueness checks.
    # Target-DOCX token and layout planning remains exclusively in M5.
    try:
        normalized_image_rules = EntityProfile(
            image_material_rules=image_material_rules
        ).image_material_rules
    except (TypeError, ValueError) as exc:
        return [
            {
                "rule_name": "material_image_rules",
                "target": "image_material_rules",
                "section": "material",
                "change_type": "preflight_image_material_rule_contract_invalid",
                "before": "",
                "after": "",
                "paragraph_index": -1,
                "success": False,
                "level": level,
                "material_domain": "image",
                "diagnostic_code": "image_material_rule_contract_invalid",
                "reason": str(exc),
            }
        ]

    diagnostics: list[dict] = []
    enabled_watermarks = [
        rule.watermark
        for rule in normalized_image_rules.values()
        if rule.watermark.enabled
    ]
    if any(
        watermark.text_source is ImageWatermarkTextSource.FIXED_FIELD
        and not watermark.text_template.strip()
        for watermark in enabled_watermarks
    ):
        diagnostics.append(
            _image_watermark_input_diagnostic(
                code="fixed_image_watermark_text_missing",
                reason="图片水印已启用，请填写固定水印字段。",
                level=level,
            )
        )
    if any(
        watermark.text_source
        is ImageWatermarkTextSource.WORKBENCH_FREE_FIELD
        for watermark in enabled_watermarks
    ) and not str(
        getattr(material_context, "image_watermark_text", "") or ""
    ).strip():
        diagnostics.append(
            _image_watermark_input_diagnostic(
                code="runtime_image_watermark_text_missing",
                reason="图片水印选择了自由字段，请在工作台填写水印文字。",
                level=level,
            )
        )

    profile = EntityProfile(
        profile_id=str(getattr(material_context, "profile_id", "") or ""),
        profile_name=str(getattr(material_context, "profile_name", "") or ""),
        image_material_rules=normalized_image_rules,
        content_bindings=content_bindings,
        content_rules=content_rules,
        attachment_bindings=attachment_bindings,
    )
    schema_ids = tuple(
        getattr(material_context, "material_schema_ids", ()) or ()
    )
    result = build_material_snapshot(
        MaterialSnapshotBuildRequest(
            profile=profile,
            frozen_field_values=field_values,
            material_schema_id=schema_ids[0] if schema_ids else "workbench-context",
            material_schema_version="preflight-v1",
            rule_versions={"freeze": "material-snapshot-builder-v1"},
        )
    )
    diagnostics.extend(
        [
            {
                "rule_name": "material_freeze",
                "target": item.path or item.domain,
                "section": "material",
                "change_type": f"preflight_{item.code}",
                "before": "",
                "after": "",
                "paragraph_index": -1,
                "success": False,
                "level": level,
                "material_domain": item.domain,
                "diagnostic_code": item.code,
                "reason": item.message,
            }
            for item in result.diagnostics
        ]
    )
    return diagnostics


def _image_watermark_input_diagnostic(
    *,
    code: str,
    reason: str,
    level: str,
) -> dict:
    return {
        "rule_name": "material_image_watermark",
        "target": "image_watermark_text",
        "section": "material",
        "change_type": f"preflight_{code}",
        "before": "",
        "after": "",
        "paragraph_index": -1,
        "success": False,
        "level": level,
        "material_domain": "image",
        "diagnostic_code": code,
        "reason": reason,
    }


def _material_role_contract_items(
    material_context: MaterialExecutionContext,
    role: str,
) -> list:
    items = list(material_asset_items(material_context, role))
    normalized_role = _normalize_material_key(role)
    for binding_role, binding in dict(
        getattr(material_context, "attachment_bindings", {}) or {}
    ).items():
        if _normalize_material_key(binding_role) != normalized_role:
            continue
        items.extend(list(getattr(binding, "items", ()) or ()))
    return items


def _material_item_normalized_name(item: object) -> str:
    value = str(getattr(item, "normalized_name", "") or "").strip()
    if value:
        return value
    file_ref = getattr(item, "file_ref", None)
    return str(getattr(file_ref, "original_name", "") or "").strip()


def _material_item_original_relative_path(item: object) -> str:
    value = str(getattr(item, "original_relative_path", "") or "").strip()
    if value:
        return value
    return _material_item_normalized_name(item)


def material_failure_policy(scene: SceneWorkspace) -> str:
    profile = getattr(scene, "input_source_profile", None)
    try:
        return normalize_execution_failure_policy(
            getattr(profile, "failure_policy", "warn"),
        )
    except ValueError:
        return "block"


def material_failure_policy_issue(scene: SceneWorkspace) -> str:
    profile = getattr(scene, "input_source_profile", None)
    return execution_failure_policy_issue(
        getattr(profile, "failure_policy", "warn")
    )


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
    "material_failure_policy_issue",
    "material_preflight_error_text",
    "material_requirement_diagnostics",
    "missing_asset_rule_diagnostics",
    "profile_material_schema_ids",
    "question_figure_file_diagnostics",
    "undeclared_image_token_diagnostics",
]
