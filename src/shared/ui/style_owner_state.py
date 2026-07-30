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


__all__ = [
    "StyleOwnerViewState",
    "template_body_style_owner_state",
]
