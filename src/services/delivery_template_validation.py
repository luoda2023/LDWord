"""Delivery-template compatibility guards shared by session and runtime gates."""

from __future__ import annotations

from src.config.scene import SceneWorkspace


def unsupported_delivery_target_template_issue(
    scene: SceneWorkspace,
    *,
    primary_template_id: str = "",
) -> str:
    """Return the V1 fail-closed issue for an alternate delivery template."""

    effective_template_id = str(
        primary_template_id or getattr(scene, "template_id", "") or ""
    ).strip()
    for preset in list(getattr(scene, "delivery_presets", ()) or ()):
        target_template_id = str(
            getattr(preset, "target_template_id", "") or ""
        ).strip()
        if not target_template_id or target_template_id == effective_template_id:
            continue
        preset_id = str(getattr(preset, "preset_id", "") or "").strip()
        return (
            "delivery_target_template_not_supported:"
            f"{preset_id or 'unnamed'}:{target_template_id}"
        )
    return ""


__all__ = ["unsupported_delivery_target_template_issue"]
