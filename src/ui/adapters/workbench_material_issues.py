from __future__ import annotations

import json
from pathlib import Path

from src.config.material_batch import (
    MaterialBatchSelection,
    build_material_batch_items,
)
from src.config.material_context import MaterialExecutionContext
from src.config.material_schema_registry import (
    evaluate_material_requirements,
    missing_material_schema_ids,
    recommend_material_schema_replacement,
    resolve_material_schema_ids,
)
from src.config.materials import AssetItem
from src.services.production_runtime.material_preflight import (
    asset_cached_path as _asset_cached_path,
)
from src.ui.adapters.workbench_execution_gate import (
    ExecutionGateAction,
    ExecutionGateDecision,
    decide_execution_gate,
    decide_execution_gate_for_policy,
)
from src.ui.adapters.workbench_issue_models import (
    MaterialReadinessIssueGroups,
    WorkbenchIssueItem,
)


def material_schema_readiness_reasons(scene) -> list[str]:
    """Return material schema problems visible before execution."""

    missing_ids = _missing_scene_material_schema_ids(scene)
    if not missing_ids:
        return []
    return ["资料 Schema 未注册：" + ", ".join(missing_ids)]


def material_readiness_reasons(
    scene,
    material_context: MaterialExecutionContext | None = None,
) -> list[str]:
    """Return material schema, field, and asset problems visible before execution."""

    return material_readiness_issue_groups(scene, material_context).to_reasons()


def material_readiness_issue_items(
    scene,
    material_context: MaterialExecutionContext | None = None,
) -> list[WorkbenchIssueItem]:
    """Return structured Workbench issue items for material readiness."""

    groups = material_readiness_issue_groups(scene, material_context)
    gate_decision = _material_readiness_gate_decision(scene, groups)
    blocking = not gate_decision.can_run
    severity = "error" if blocking else "warning"
    items: list[WorkbenchIssueItem] = []
    if groups.field_keys:
        items.append(
            WorkbenchIssueItem(
                issue_id="material.fields.missing",
                category="material_field",
                severity=severity,
                title="资料字段缺失",
                summary=", ".join(groups.field_keys),
                details=tuple("字段：" + key for key in groups.field_keys),
                source_notes=groups.source_notes,
                repair_target_type="field",
                repair_target_key=groups.field_keys[0],
                blocking=blocking,
            )
        )
    if groups.asset_roles:
        items.append(
            WorkbenchIssueItem(
                issue_id="material.assets.missing",
                category="material_asset",
                severity=severity,
                title="资料资产缺失",
                summary=", ".join(groups.asset_roles),
                details=tuple("资产：" + role for role in groups.asset_roles),
                source_notes=groups.source_notes,
                repair_target_type="asset",
                repair_target_key=groups.asset_roles[0],
                blocking=blocking,
            )
        )
    if groups.schema_ids:
        details: list[str] = []
        if groups.recommendation_schema_id:
            recommendation = "推荐替换：" + groups.recommendation_schema_id
            if groups.recommendation_reasons:
                recommendation += "（" + "; ".join(groups.recommendation_reasons) + "）"
            details.append(recommendation)
        items.append(
            WorkbenchIssueItem(
                issue_id="material.schema.unregistered",
                category="material_schema",
                severity=severity,
                title="资料 Schema 未注册",
                summary=", ".join(groups.schema_ids),
                details=tuple(details),
                source_notes=groups.source_notes,
                repair_target_type="schema",
                repair_target_key=groups.schema_ids[0],
                blocking=blocking,
            )
        )
    if groups.incompatible_schema_ids:
        items.append(
            WorkbenchIssueItem(
                issue_id="material.schema.incompatible",
                category="material_schema",
                severity=severity,
                title="资料包 Schema 不兼容",
                summary=", ".join(groups.incompatible_schema_ids),
                details=(
                    "请切换到与当前方案匹配的资料包，或新建当前方案资料包。",
                ),
                source_notes=groups.source_notes,
                repair_target_type="material_package",
                repair_target_key=groups.incompatible_schema_ids[0],
                blocking=blocking,
            )
        )
    return items


def material_readiness_gate_decision(
    scene,
    material_context: MaterialExecutionContext | None = None,
) -> ExecutionGateDecision:
    """Return the authoritative warn/block decision for material readiness."""

    groups = material_readiness_issue_groups(scene, material_context)
    return _material_readiness_gate_decision(scene, groups)


def material_batch_readiness_gate_decision(
    scene,
    selection: MaterialBatchSelection | None,
) -> ExecutionGateDecision:
    """Aggregate the authoritative material gate for every selected profile.

    Batch execution must not infer readiness from the profile currently shown
    in the editor.  Each selected profile owns a distinct execution context,
    so this projection builds those contexts and preserves their profile
    identity in every reason.
    """

    if not isinstance(selection, MaterialBatchSelection):
        return ExecutionGateDecision()
    selected_ids = [
        str(profile_id or "").strip()
        for profile_id in selection.profile_ids
        if str(profile_id or "").strip()
    ]
    if not selected_ids:
        return ExecutionGateDecision()

    items = build_material_batch_items(
        selection.archive,
        profile_ids=selected_ids,
        # Readiness does not own output naming.  A safe fixed template avoids
        # coupling this material gate to a user output-template error, which is
        # validated by the batch/output preflight instead.
        output_dir_template="{profile_id}",
        base_context=selection.base_context,
    )
    warnings: list[str] = []
    blockers: list[str] = []
    confirmations: list[str] = []
    primary_action: ExecutionGateAction | None = None
    for item in items:
        decision = material_readiness_gate_decision(scene, item.context)
        label = str(item.profile_name or item.profile_id or "资料项").strip()
        warnings.extend(f"{label}：{reason}" for reason in decision.warning_reasons)
        blockers.extend(f"{label}：{reason}" for reason in decision.blocking_reasons)
        confirmations.extend(
            f"{label}：{reason}" for reason in decision.confirmation_reasons
        )
        if primary_action is None and decision.primary_action is not None:
            primary_action = decision.primary_action
    return decide_execution_gate(
        warning_reasons=warnings,
        blocking_reasons=blockers,
        confirmation_reasons=confirmations,
        primary_action=primary_action,
    )


def _material_readiness_gate_decision(
    scene,
    groups: MaterialReadinessIssueGroups,
) -> ExecutionGateDecision:
    profile = getattr(scene, "input_source_profile", None)
    return decide_execution_gate_for_policy(
        groups.to_reasons(),
        failure_policy=getattr(profile, "failure_policy", "warn"),
        primary_action=_material_gate_action(groups),
    )


def _material_gate_action(
    groups: MaterialReadinessIssueGroups,
) -> ExecutionGateAction | None:
    if groups.incompatible_schema_ids:
        return ExecutionGateAction(
            "更换资料包",
            "material_package",
            groups.incompatible_schema_ids[0],
        )
    if groups.field_keys:
        return ExecutionGateAction("补充资料", "field", groups.field_keys[0])
    if groups.asset_roles:
        return ExecutionGateAction("补充资料", "asset", groups.asset_roles[0])
    if groups.schema_ids:
        return ExecutionGateAction("修复资料配置", "schema", groups.schema_ids[0])
    return None


def material_asset_comparison_issue_items(
    material_context: MaterialExecutionContext | None = None,
) -> list[WorkbenchIssueItem]:
    """Return Workbench issues for manually flagged question-figure comparisons."""

    context = (
        material_context
        if isinstance(material_context, MaterialExecutionContext)
        else MaterialExecutionContext()
    )
    items: list[WorkbenchIssueItem] = []
    for index, asset_item in enumerate(list(context.asset_items or []), start=1):
        if not isinstance(asset_item, AssetItem):
            continue
        metadata = _asset_metadata(asset_item)
        if _clean_text(metadata.get("comparison_issue_status")).lower() != "flagged":
            continue
        question_target = _question_figure_target_value(metadata) or str(index)
        display_name = (
            _clean_text(metadata.get("comparison_issue_display_name"))
            or _clean_text(metadata.get("comparison_issue_reference"))
            or _clean_text(asset_item.label)
            or Path(str(asset_item.path or "")).name
            or _clean_text(asset_item.item_id)
        )
        issue_kind = _clean_text(metadata.get("comparison_issue_kind")) or "题图对比"
        summary = (
            _clean_text(metadata.get("comparison_issue_summary"))
            or f"题{question_target} {issue_kind}: {display_name}"
        )
        details = [
            f"题号：{question_target}",
            f"标注类型：{_clean_text(metadata.get('comparison_issue_type')) or 'manual_compare'}",
            f"对比类型：{issue_kind}",
            f"对比对象：{display_name}",
        ]
        reference = _clean_text(metadata.get("comparison_issue_reference"))
        if reference and reference != display_name:
            details.append("对比引用：" + reference)
        marked_at = _clean_text(metadata.get("comparison_issue_marked_at"))
        if marked_at:
            details.append("标注时间：" + marked_at)
        region_summary = _clean_text(metadata.get("comparison_issue_region_summary"))
        if region_summary:
            details.append("差异区域：" + region_summary)
        target_key = _question_figure_item_repair_target_key(asset_item, question_target)
        issue_id = (
            "material.asset_comparison."
            f"{_issue_token(asset_item.item_id or question_target)}."
            f"{_issue_token(display_name)}"
        )
        items.append(
            WorkbenchIssueItem(
                issue_id=issue_id,
                category="material_asset_comparison",
                severity="warning",
                title="题图对比问题",
                summary=summary,
                details=tuple(details),
                source_notes=("asset_items.metadata.comparison_issue_*",),
                repair_target_type="question_figure_item",
                repair_target_key=target_key,
                repair_context=tuple(
                    pair
                    for pair in (
                        ("profile_id", _clean_text(context.profile_id)),
                        ("profile_name", _clean_text(context.profile_name)),
                    )
                    if pair[1]
                ),
                blocking=False,
                owner="workbench",
            )
        )
    return items


def material_readiness_issue_groups(
    scene,
    material_context: MaterialExecutionContext | None = None,
) -> MaterialReadinessIssueGroups:
    """Return structured material schema, field, asset, and source issue groups."""

    missing_schema_ids = _missing_scene_material_schema_ids(scene)
    schema_recommendation = _material_schema_recommendation(scene, missing_schema_ids)
    profile = getattr(scene, "input_source_profile", None)
    if profile is None:
        return MaterialReadinessIssueGroups(
            schema_ids=missing_schema_ids,
            source_notes=_material_source_notes(
                missing_schema_ids=missing_schema_ids,
                recommendation_schema_id=(
                    schema_recommendation.schema_id if schema_recommendation is not None else ""
                ),
            ),
            recommendation_schema_id=(
                schema_recommendation.schema_id if schema_recommendation is not None else ""
            ),
            recommendation_reasons=(
                schema_recommendation.reasons if schema_recommendation is not None else ()
            ),
        )
    schema_ids = _scene_material_schema_ids(scene)
    extra_fields = list(getattr(profile, "required_material_fields", []) or [])
    extra_roles = list(getattr(profile, "required_image_roles", []) or [])
    if not schema_ids and not extra_fields and not extra_roles:
        return MaterialReadinessIssueGroups(
            schema_ids=missing_schema_ids,
            source_notes=_material_source_notes(
                missing_schema_ids=missing_schema_ids,
                recommendation_schema_id=(
                    schema_recommendation.schema_id if schema_recommendation is not None else ""
                ),
            ),
            recommendation_schema_id=(
                schema_recommendation.schema_id if schema_recommendation is not None else ""
            ),
            recommendation_reasons=(
                schema_recommendation.reasons if schema_recommendation is not None else ()
            ),
        )

    context = (
        material_context
        if isinstance(material_context, MaterialExecutionContext)
        else MaterialExecutionContext()
    )
    incompatible_schema_ids = _incompatible_context_schema_ids(
        schema_ids,
        context,
    )
    schema_id = schema_ids[0] if schema_ids else ""
    check = evaluate_material_requirements(
        schema_id=schema_id,
        schema_ids=schema_ids,
        entity_data=context.resolved_entity_data(),
        asset_roles=_material_context_asset_roles(context),
        extra_required_fields=extra_fields,
        extra_required_asset_roles=extra_roles,
    )
    removed_fields = {
        str(key)
        for key, scope in dict(getattr(context, "field_scopes", {}) or {}).items()
        if str(scope) == "removed"
    }
    missing_field_keys = tuple(
        key for key in check.missing_field_keys if key not in removed_fields
    )
    missing_asset_roles = _unique_texts(
        [
            *check.missing_asset_roles,
            *(
                context.missing_required_asset_roles()
                if isinstance(context, MaterialExecutionContext)
                else []
            ),
        ]
    )
    issue_groups = MaterialReadinessIssueGroups(
        schema_ids=missing_schema_ids,
        incompatible_schema_ids=incompatible_schema_ids,
        field_keys=missing_field_keys,
        asset_roles=tuple(missing_asset_roles),
        source_notes=_material_source_notes(
            missing_schema_ids=missing_schema_ids,
            schema_ids=schema_ids,
            schema_labels=check.requirements.schema_labels,
            extra_fields=extra_fields,
            extra_roles=extra_roles,
            material_context=context,
            include_context=bool(
                incompatible_schema_ids
                or missing_field_keys
                or missing_asset_roles
            ),
            package_schema_ids=tuple(
                getattr(context, "material_schema_ids", ()) or ()
            ),
            package_schema_missing=(
                incompatible_schema_ids == ("未声明",)
            ),
            recommendation_schema_id=(
                schema_recommendation.schema_id if schema_recommendation is not None else ""
            ),
        ),
        recommendation_schema_id=(
            schema_recommendation.schema_id if schema_recommendation is not None else ""
        ),
        recommendation_reasons=(
            schema_recommendation.reasons if schema_recommendation is not None else ()
        ),
    )
    if not issue_groups.has_issues:
        return MaterialReadinessIssueGroups()
    return issue_groups


def _missing_scene_material_schema_ids(scene) -> tuple[str, ...]:
    return missing_material_schema_ids(_scene_material_schema_ids(scene))


def _scene_material_schema_ids(scene) -> tuple[str, ...]:
    profile = getattr(scene, "input_source_profile", None)
    if profile is None:
        return ()
    schema_ids = resolve_material_schema_ids(
        str(getattr(profile, "material_schema_id", "") or ""),
        list(getattr(profile, "material_schema_ids", []) or []),
    )
    return schema_ids


def _material_context_asset_roles(context: MaterialExecutionContext) -> list[str]:
    return _unique_texts(
        [
            str(getattr(item, "role", "") or "")
            for item in list(getattr(context, "asset_items", []) or [])
            if str(getattr(item, "path", "") or "").strip()
        ]
    )


def _incompatible_context_schema_ids(
    scene_schema_ids: tuple[str, ...],
    context: MaterialExecutionContext,
) -> tuple[str, ...]:
    """Return package schemas which cannot be used by the active scene."""

    expected = {
        str(schema_id or "").strip()
        for schema_id in scene_schema_ids
        if str(schema_id or "").strip()
    }
    if not expected:
        return ()
    package_schema_ids = tuple(
        dict.fromkeys(
            str(schema_id or "").strip()
            for schema_id in tuple(context.material_schema_ids or ())
            if str(schema_id or "").strip()
        )
    )
    if not package_schema_ids:
        owns_package_identity = bool(
            str(context.package_id or "").strip()
            or str(context.archive_id or "").strip()
        )
        return ("未声明",) if owns_package_identity else ()
    return tuple(
        schema_id
        for schema_id in package_schema_ids
        if schema_id not in expected
    )


def _asset_metadata(item: object) -> dict[str, str]:
    metadata = getattr(item, "metadata", {})
    if not isinstance(metadata, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in metadata.items()
        if str(key or "").strip() and str(value or "").strip()
    }


def _asset_render_path(item: AssetItem) -> str:
    raw_path = str(getattr(item, "path", "") or "").strip()
    if raw_path:
        return raw_path
    return _asset_cached_path(_asset_metadata(item))


def _looks_like_remote_asset_path(value: object) -> bool:
    text = str(value or "").strip().lower()
    return text.startswith(("http://", "https://", "asset://", "lark://"))


def _question_figure_target_value(metadata: dict[str, str]) -> str:
    return (
        str(metadata.get("question_index") or metadata.get("questionIndex") or "").strip()
        or str(metadata.get("question_id") or metadata.get("questionId") or "").strip()
        or str(metadata.get("question_no") or metadata.get("questionNo") or "").strip()
        or str(metadata.get("number") or metadata.get("no") or "").strip()
    )


def _question_figure_item_repair_target_key(
    item: AssetItem,
    question_target: str,
) -> str:
    metadata = _asset_metadata(item)
    render_path = _asset_render_path(item)
    target: dict[str, object] = {
        "role": "question_figure",
        "item_id": str(getattr(item, "item_id", "") or ""),
        "question_index": str(question_target or ""),
        "path": render_path,
        "metadata": metadata,
    }
    cache_path = _asset_cached_path(metadata)
    if cache_path and not _looks_like_remote_asset_path(render_path):
        target["cache_path"] = cache_path
    asset_id = (
        str(metadata.get("asset_id") or "").strip()
        or str(metadata.get("assetId") or "").strip()
    )
    if asset_id:
        target["asset_id"] = asset_id
    return json.dumps(target, ensure_ascii=False, separators=(",", ":"))


def _material_schema_recommendation(scene, missing_schema_ids: tuple[str, ...]):
    if not missing_schema_ids:
        return None
    schema_ids = _scene_material_schema_ids(scene)
    return recommend_material_schema_replacement(
        missing_schema_ids,
        family_hints=(
            str(getattr(scene, "category", "") or ""),
            str(getattr(scene, "scene_id", "") or ""),
        ),
        existing_schema_ids=tuple(
            schema_id for schema_id in schema_ids if schema_id not in missing_schema_ids
        ),
    )


def _material_source_notes(
    *,
    missing_schema_ids: tuple[str, ...] = (),
    schema_ids: tuple[str, ...] = (),
    schema_labels: tuple[str, ...] = (),
    extra_fields: list[str] | None = None,
    extra_roles: list[str] | None = None,
    material_context: MaterialExecutionContext | None = None,
    include_context: bool = False,
    package_schema_ids: tuple[str, ...] = (),
    package_schema_missing: bool = False,
    recommendation_schema_id: str = "",
) -> tuple[str, ...]:
    notes: list[str] = []
    if missing_schema_ids:
        notes.append("未注册 Schema：" + ", ".join(missing_schema_ids))
    if recommendation_schema_id:
        notes.append("推荐 Schema：" + recommendation_schema_id)
    if schema_ids:
        schema_notes: list[str] = []
        for index, schema_id in enumerate(schema_ids):
            label = schema_labels[index] if index < len(schema_labels) else ""
            if label and label != schema_id:
                schema_notes.append(f"{label} ({schema_id})")
            else:
                schema_notes.append(schema_id)
        notes.append("Schema：" + ", ".join(schema_notes))
    normalized_fields = _unique_texts(list(extra_fields or []))
    if normalized_fields:
        notes.append("方案字段：" + ", ".join(normalized_fields))
    normalized_roles = _unique_texts(list(extra_roles or []))
    if normalized_roles:
        notes.append("方案资产：" + ", ".join(normalized_roles))
    if include_context:
        context = (
            material_context
            if isinstance(material_context, MaterialExecutionContext)
            else MaterialExecutionContext()
        )
        profile_label = str(context.profile_name or context.profile_id or "").strip()
        if profile_label:
            notes.append("当前资料：" + profile_label)
        elif context.is_empty():
            notes.append("当前资料：未配置")
    normalized_package_schema_ids = _unique_texts(list(package_schema_ids))
    if normalized_package_schema_ids:
        notes.append("资料包 Schema：" + ", ".join(normalized_package_schema_ids))
    elif package_schema_missing:
        notes.append("资料包 Schema：未声明")
    return tuple(_unique_texts(notes))


def _unique_texts(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _issue_token(value: str) -> str:
    token = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_"
        for char in str(value or "").strip().lower()
    ).strip("_")
    return token or "item"


def _clean_text(value) -> str:
    return str(value or "").strip()
