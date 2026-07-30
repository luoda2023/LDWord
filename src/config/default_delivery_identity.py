"""Read-only projection of a scene's selected delivery preset identity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


DefaultDeliveryIdentityStatus = Literal["ok", "missing", "invalid"]


@dataclass(frozen=True, slots=True)
class DefaultDeliveryIdentity:
    """Describe the requested default without repairing or guessing it."""

    requested_id: str
    status: DefaultDeliveryIdentityStatus
    preset: object | None = None

    @property
    def is_ok(self) -> bool:
        return self.status == "ok"


def project_default_delivery_identity(config: object) -> DefaultDeliveryIdentity:
    """Resolve one unique default preset without falling back to list order.

    This projection is intentionally non-mutating.  Duplicate matches are
    invalid rather than arbitrarily selecting one; the execution integrity
    owner remains responsible for blocking malformed configurations.
    """

    requested_id = str(
        getattr(config, "default_delivery_preset_id", "") or ""
    ).strip()
    if not requested_id:
        return DefaultDeliveryIdentity(
            requested_id="",
            status="missing",
        )

    matches = tuple(
        preset
        for preset in tuple(getattr(config, "delivery_presets", ()) or ())
        if str(getattr(preset, "preset_id", "") or "").strip() == requested_id
    )
    if len(matches) != 1:
        return DefaultDeliveryIdentity(
            requested_id=requested_id,
            status="invalid",
        )
    return DefaultDeliveryIdentity(
        requested_id=requested_id,
        status="ok",
        preset=matches[0],
    )


__all__ = [
    "DefaultDeliveryIdentity",
    "DefaultDeliveryIdentityStatus",
    "project_default_delivery_identity",
]
