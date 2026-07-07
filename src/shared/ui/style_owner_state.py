"""Shared view state for paragraph-style owners."""

from __future__ import annotations

from dataclasses import dataclass

from src.config.template import StyleConfig
from src.shared.ui.paragraph_style_surface import StyleControlSurfaceState


@dataclass(frozen=True, slots=True)
class StyleOwnerViewState:
    """UI-facing state shared by style surfaces and owner controls."""

    surface_state: StyleControlSurfaceState
    hint: str = ""
    action_enabled: bool = False
    source_status: str = ""
    scope_status: str = ""
    edit_status: str = ""


def template_body_style_owner_state(style: StyleConfig | None) -> StyleOwnerViewState:
    """Return shared state for the template body-style editor."""

    if style is None:
        readonly_reason = "未选择模板"
        return StyleOwnerViewState(
            surface_state=StyleControlSurfaceState(
                owner_kind="template_body_style",
                active_label="正文排版",
                source_label=readonly_reason,
                editable=False,
                style=None,
                readonly_reason=readonly_reason,
            ),
            hint=readonly_reason,
            action_enabled=False,
            source_status=readonly_reason,
            scope_status="无可编辑范围",
            edit_status="先选择模板",
        )

    return StyleOwnerViewState(
        surface_state=StyleControlSurfaceState(
            owner_kind="template_body_style",
            active_label="正文排版",
            source_label="模板默认样式",
            editable=True,
            style=style,
        ),
        hint="模板默认样式",
        action_enabled=True,
        source_status="模板默认样式",
        scope_status="模板全局",
        edit_status="可编辑",
    )


def scene_section_style_owner_state(
    *,
    style: StyleConfig | None,
    projection=None,
    variant_label: str = "",
    section_enabled: bool = False,
    overridden: bool = False,
) -> StyleOwnerViewState:
    """Return shared state for a scene section-style override editor."""

    label = str(variant_label or "")
    readonly_reason = ""
    if projection is not None:
        active_label = str(getattr(projection, "label", "") or label)
        source_label = str(getattr(projection, "status_value", "") or "")
        detail = str(getattr(projection, "status_detail", "") or "")
        hint = str(getattr(projection, "editor_hint", "") or detail)
        editable = bool(getattr(projection, "editable", False) and style is not None)
        action_enabled = bool(getattr(projection, "overridden", False))
        readonly_reason = "" if editable else hint
    else:
        active_label = label
        source_label = ""
        detail = ""
        editable = False
        action_enabled = False
        if not label:
            hint = "暂无可编辑分区。"
            readonly_reason = hint
        elif not section_enabled:
            hint = f"「{label}」暂不可编辑。"
            readonly_reason = hint
        elif not overridden:
            hint = "跟随模板 · 开启独立样式后可编辑"
            readonly_reason = f"{label}：跟随模板。开启独立样式后可编辑。"
        else:
            hint = "正在编辑"
            readonly_reason = hint

    source_status = source_label or ("未选择分区" if not label else active_label)
    if not label:
        scope_status = "无可编辑分区"
        edit_status = "暂无可编辑分区"
    elif not section_enabled:
        scope_status = "暂不可编辑"
        edit_status = "不可编辑"
    elif editable:
        scope_status = "仅当前场景"
        edit_status = "可编辑"
    elif not overridden:
        scope_status = "来自模板"
        edit_status = "开启独立样式后可编辑"
    else:
        scope_status = "仅当前场景"
        edit_status = "不可编辑"

    return StyleOwnerViewState(
        surface_state=StyleControlSurfaceState(
            owner_kind="scene_section_style",
            active_label=active_label,
            source_label=source_label,
            detail=detail,
            editable=editable,
            style=style,
            readonly_reason=readonly_reason,
        ),
        hint=hint,
        action_enabled=action_enabled,
        source_status=source_status,
        scope_status=scope_status,
        edit_status=edit_status,
    )


__all__ = [
    "StyleOwnerViewState",
    "scene_section_style_owner_state",
    "template_body_style_owner_state",
]
