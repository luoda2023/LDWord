"""Build the template source recorded in execution reports."""

from __future__ import annotations

from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig


def build_style_source_report_summary(
    scene: SceneWorkspace,
    template: TemplateConfig | None,
    *,
    template_label: str = "",
) -> dict[str, object]:
    label = (
        str(template_label or "").strip()
        or str(getattr(template, "name", "") or "").strip()
        or str(getattr(scene, "template_id", "") or "").strip()
        or "当前模板"
    )
    return {
        "template_label": label,
        "summary": f"本次使用模板“{label}”。",
    }


__all__ = ["build_style_source_report_summary"]
