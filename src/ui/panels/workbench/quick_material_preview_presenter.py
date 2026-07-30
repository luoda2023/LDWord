"""Pure projection for the material-package preview in quick execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.config.material_context import MaterialExecutionContext
from src.config.material_preview_snapshot import MaterialPreviewSnapshot
from src.config.material_schema_registry import (
    build_material_requirements,
    resolve_material_schema_ids,
)
from src.ui.adapters.workbench_execution_gate import ExecutionGateDecision
from src.ui.adapters.workbench_issue_models import MaterialReadinessIssueGroups
from src.ui.adapters.workbench_material_issues import material_readiness_issue_groups
from src.ui.panels.scene_product_summary_projection import (
    material_asset_role_display_name,
    material_field_display_name,
)


_MAX_PROJECTED_ITEMS = 8
_MAX_COMPACT_VALUE_LENGTH = 30


@dataclass(frozen=True, slots=True)
class QuickMaterialPreviewItem:
    """One field or image binding available in the current package draft."""

    key: str
    label: str
    value: str
    missing: bool = False
    kind: str = "field"

    @property
    def compact_text(self) -> str:
        value = _compact_value(self.value)
        return f"{self.label}  {value}" if value else self.label


@dataclass(frozen=True, slots=True)
class QuickMaterialPreviewProjection:
    """Immutable state for the stable, read-only preview card."""

    visible: bool = True
    package_label: str = "未选择资料包"
    package_source_text: str = ""
    package_source_tone: str = "neutral"
    profile_label: str = ""
    summary_text: str = "暂无填充内容"
    status_text: str = "未选择"
    status_tone: str = "neutral"
    items: tuple[QuickMaterialPreviewItem, ...] = ()
    hidden_item_count: int = 0
    counters: tuple[str, ...] = ()

    @property
    def can_expand(self) -> bool:
        return bool(self.items or self.hidden_item_count)

    @property
    def compact_items(self) -> tuple[QuickMaterialPreviewItem, ...]:
        return self.items[:3]

    @property
    def counter_text(self) -> str:
        return " · ".join(self.counters)


def build_quick_material_preview_projection(
    scene,
    context: MaterialExecutionContext | None,
    *,
    preview_snapshot: MaterialPreviewSnapshot | None = None,
    gate_decision: ExecutionGateDecision | None = None,
    issue_groups: MaterialReadinessIssueGroups | None = None,
) -> QuickMaterialPreviewProjection:
    """Prefer the live Assets draft and fall back to the execution snapshot."""

    del gate_decision
    material_context = (
        context
        if isinstance(context, MaterialExecutionContext)
        else MaterialExecutionContext()
    )
    snapshot = (
        preview_snapshot
        if isinstance(preview_snapshot, MaterialPreviewSnapshot)
        else MaterialPreviewSnapshot()
    )
    use_live_snapshot = not snapshot.is_empty()

    profile = getattr(scene, "input_source_profile", None)
    schema_ids = _scene_schema_ids(profile)
    extra_fields = tuple(getattr(profile, "required_material_fields", ()) or ())
    extra_roles = tuple(getattr(profile, "required_image_roles", ()) or ())
    requirements = build_material_requirements(
        schema_ids[0] if schema_ids else "",
        schema_ids=schema_ids,
        extra_required_fields=extra_fields,
        extra_required_asset_roles=extra_roles,
    )
    context_issues = (
        issue_groups
        if isinstance(issue_groups, MaterialReadinessIssueGroups)
        else material_readiness_issue_groups(scene, material_context)
    )

    if use_live_snapshot:
        values = snapshot.values()
        scopes = snapshot.scopes()
        present_roles = set(snapshot.asset_roles)
        package_label = _package_label(
            snapshot.archive_name,
            snapshot.package_id,
            snapshot.archive_id,
        )
        profile_label = _clean_label(snapshot.profile_name)
        source_text, source_tone = _source_presentation(
            snapshot.package_source_type
        )
        image_count = snapshot.image_count
        content_count = snapshot.content_count
        attachment_count = snapshot.attachment_count
        source_valid = snapshot.valid
        source_issues = snapshot.issues
        schema_issues: tuple[str, ...] = ()
    else:
        values = material_context.resolved_entity_data()
        scopes = dict(material_context.field_scopes or {})
        present_roles = {
            str(getattr(item, "role", "") or "").strip()
            for item in material_context.asset_items
            if str(getattr(item, "role", "") or "").strip()
            and str(getattr(item, "path", "") or "").strip()
        }
        package_label = _package_label(
            material_context.archive_name,
            material_context.package_id,
            material_context.archive_id,
        )
        profile_label = _clean_label(material_context.profile_name)
        source_text, source_tone = ("", "neutral")
        image_count = _asset_count(material_context)
        content_count = len(material_context.content_bindings)
        attachment_count = _attachment_count(material_context)
        source_valid = True
        source_issues = ()
        schema_issues = tuple(context_issues.schema_ids)

    has_selection = bool(
        use_live_snapshot
        or _context_has_preview_payload(material_context)
    )
    removed_fields = {
        str(key or "").strip()
        for key, scope in scopes.items()
        if str(scope or "").strip() == "removed"
    }
    floating_fields = {
        str(key or "").strip()
        for key, scope in scopes.items()
        if str(scope or "").strip() == "floating"
    }
    required_fields = tuple(
        key
        for key in _unique_texts(requirements.required_field_keys)
        if key not in removed_fields and key not in floating_fields
    )
    required_roles = _unique_texts(requirements.required_asset_roles)

    candidates: list[QuickMaterialPreviewItem] = []
    missing_count = 0
    if has_selection:
        for field_key in required_fields:
            raw_value = str(values.get(field_key, "") or "").strip()
            missing = not raw_value
            missing_count += int(missing)
            candidates.append(
                QuickMaterialPreviewItem(
                    key=field_key,
                    label=material_field_display_name(field_key),
                    value=_preview_value(raw_value),
                    missing=missing,
                )
            )
        for role in required_roles:
            missing = role not in present_roles
            missing_count += int(missing)
            candidates.append(
                QuickMaterialPreviewItem(
                    key=role,
                    label=material_asset_role_display_name(role),
                    value="未绑定" if missing else "已绑定",
                    missing=missing,
                    kind="asset",
                )
            )

        declared_keys = set(required_fields)
        for field_key, raw_value in values.items():
            key = str(field_key or "").strip()
            value = str(raw_value or "").strip()
            if (
                not key
                or not value
                or key in declared_keys
                or key in removed_fields
                or key in floating_fields
            ):
                continue
            candidates.append(
                QuickMaterialPreviewItem(
                    key=key,
                    label=material_field_display_name(key),
                    value=_preview_value(value),
                )
            )

    # Keep missing required values first, then preserve contract/editor order.
    candidates.sort(key=lambda item: (not item.missing, item.kind != "field"))
    projected_items = tuple(candidates[:_MAX_PROJECTED_ITEMS])
    hidden_item_count = max(0, len(candidates) - len(projected_items))
    required_count = len(required_fields) + len(required_roles)
    completed_count = max(0, required_count - missing_count)

    counters = tuple(
        counter
        for counter in (
            _count_label("图片", image_count),
            _count_label("内容", content_count),
            _count_label("附件", attachment_count),
        )
        if counter
    )
    summary_text = _summary_text(
        profile_label=profile_label,
        has_selection=has_selection,
        required_count=required_count,
        completed_count=completed_count,
        value_count=len([value for value in values.values() if str(value).strip()]),
        counters=counters,
    )

    if not has_selection:
        status_text, status_tone = "未选择", "neutral"
    elif not source_valid or source_issues:
        status_text, status_tone = "待修复", "error"
    elif schema_issues:
        status_text, status_tone = "规则异常", "error"
    elif missing_count:
        status_text, status_tone = f"缺 {missing_count} 项", "warning"
    elif required_count:
        status_text, status_tone = "完整", "success"
    elif values or counters:
        status_text, status_tone = "已载入", "success"
    else:
        status_text, status_tone = "暂无内容", "neutral"

    return QuickMaterialPreviewProjection(
        visible=True,
        package_label=package_label,
        package_source_text=source_text,
        package_source_tone=source_tone,
        profile_label=profile_label,
        summary_text=summary_text,
        status_text=status_text,
        status_tone=status_tone,
        items=projected_items,
        hidden_item_count=hidden_item_count,
        counters=counters,
    )


def _scene_schema_ids(profile) -> tuple[str, ...]:
    if profile is None:
        return ()
    return resolve_material_schema_ids(
        str(getattr(profile, "material_schema_id", "") or ""),
        tuple(getattr(profile, "material_schema_ids", ()) or ()),
    )


def _context_has_preview_payload(context: MaterialExecutionContext) -> bool:
    return bool(
        context.package_id
        or context.archive_id
        or context.archive_name
        or context.profile_id
        or context.profile_name
        or context.entity_data
        or context.frozen_field_values
        or context.asset_items
        or context.images
        or context.content_bindings
        or context.attachment_bindings
    )


def _package_label(archive_name: object, package_id: object, archive_id: object) -> str:
    cleaned_name = _clean_label(archive_name)
    if cleaned_name:
        return cleaned_name
    if _clean_label(package_id) or _clean_label(archive_id):
        return "未命名资料包"
    return "未选择资料包"


def _source_presentation(source_type: object) -> tuple[str, str]:
    normalized = str(source_type or "").strip().lower()
    if normalized == "builtin":
        return "内置", "neutral"
    if normalized == "user":
        return "自定", "info"
    if normalized:
        return "外部", "neutral"
    return "", "neutral"


def _summary_text(
    *,
    profile_label: str,
    has_selection: bool,
    required_count: int,
    completed_count: int,
    value_count: int,
    counters: tuple[str, ...],
) -> str:
    if not has_selection:
        return "暂无填充内容"
    parts: list[str] = []
    if profile_label:
        parts.append(profile_label)
    if required_count:
        parts.append(f"已填 {completed_count}/{required_count}")
    elif value_count:
        parts.append(f"字段 {value_count}")
    parts.extend(counters)
    return " · ".join(parts) or "暂无填充内容"


def _clean_label(value: object) -> str:
    return " ".join(str(value or "").split())


def _preview_value(value: str) -> str:
    normalized = _clean_label(value)
    if not normalized:
        return "未填写"
    if len(normalized) > 80:
        return "已填写"
    return normalized


def _compact_value(value: str) -> str:
    normalized = _clean_label(value)
    if len(normalized) <= _MAX_COMPACT_VALUE_LENGTH:
        return normalized
    return normalized[: _MAX_COMPACT_VALUE_LENGTH - 1].rstrip() + "…"


def _asset_count(context: MaterialExecutionContext) -> int:
    bound_items = sum(
        1
        for item in context.asset_items
        if str(getattr(item, "path", "") or "").strip()
    )
    return max(bound_items, len(context.images))


def _attachment_count(context: MaterialExecutionContext) -> int:
    count = 0
    for binding in context.attachment_bindings.values():
        items = tuple(getattr(binding, "items", ()) or ())
        if items:
            count += len(items)
        elif str(getattr(binding, "source_path", "") or "").strip():
            count += 1
    return count


def _count_label(label: str, count: int) -> str:
    return f"{label} {count}" if count > 0 else ""


def _unique_texts(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "QuickMaterialPreviewItem",
    "QuickMaterialPreviewProjection",
    "build_quick_material_preview_projection",
]
