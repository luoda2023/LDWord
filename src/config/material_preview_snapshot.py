"""Live, read-only material-package state used by workbench previews.

The preview snapshot is intentionally separate from
``MaterialExecutionContext``.  Editing a package may update this lightweight
projection immediately, while the execution context remains a frozen payload
published only when the user starts generation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MaterialPreviewSnapshot:
    """Immutable draft projection shared between Assets and Workbench."""

    mode_id: str = ""
    package_id: str = ""
    archive_id: str = ""
    archive_name: str = ""
    package_source_type: str = ""
    profile_id: str = ""
    profile_name: str = ""
    field_values: tuple[tuple[str, str], ...] = ()
    field_scopes: tuple[tuple[str, str], ...] = ()
    asset_roles: tuple[str, ...] = ()
    image_count: int = 0
    content_count: int = 0
    attachment_count: int = 0
    valid: bool = True
    issues: tuple[str, ...] = ()
    revision: str = ""

    def is_empty(self) -> bool:
        return not any(
            (
                self.package_id,
                self.archive_id,
                self.archive_name,
                self.profile_id,
                self.profile_name,
                self.field_values,
                self.asset_roles,
                self.image_count,
                self.content_count,
                self.attachment_count,
            )
        )

    def is_compatible_with(self, *, mode_id: str) -> bool:
        current_mode = _text(mode_id)
        return not self.mode_id or not current_mode or self.mode_id == current_mode

    def values(self) -> dict[str, str]:
        return dict(self.field_values)

    def scopes(self) -> dict[str, str]:
        return dict(self.field_scopes)


def build_material_preview_snapshot(
    *,
    mode_id: object = "",
    package_id: object = "",
    archive_id: object = "",
    archive_name: object = "",
    package_source_type: object = "",
    profile_id: object = "",
    profile_name: object = "",
    field_values: Mapping[object, object] | None = None,
    field_scopes: Mapping[object, object] | None = None,
    asset_roles: Sequence[object] = (),
    image_count: int = 0,
    content_count: int = 0,
    attachment_count: int = 0,
    valid: bool = True,
    issues: Sequence[object] = (),
) -> MaterialPreviewSnapshot:
    """Normalize editor values and attach a deterministic content revision."""

    normalized_fields = tuple(
        (key, _text(value))
        for key, value in (
            (_text(raw_key), raw_value)
            for raw_key, raw_value in dict(field_values or {}).items()
        )
        if key
    )
    normalized_scopes = tuple(
        (key, value)
        for key, value in (
            (_text(raw_key), _text(raw_value))
            for raw_key, raw_value in dict(field_scopes or {}).items()
        )
        if key and value
    )
    normalized_roles = tuple(
        dict.fromkeys(role for role in (_text(item) for item in asset_roles) if role)
    )
    normalized_issues = tuple(
        dict.fromkeys(issue for issue in (_text(item) for item in issues) if issue)
    )
    payload = {
        "mode_id": _text(mode_id),
        "package_id": _text(package_id),
        "archive_id": _text(archive_id),
        "archive_name": _text(archive_name),
        "package_source_type": _text(package_source_type),
        "profile_id": _text(profile_id),
        "profile_name": _text(profile_name),
        "field_values": sorted(normalized_fields),
        "field_scopes": sorted(normalized_scopes),
        "asset_roles": sorted(normalized_roles),
        "image_count": max(0, int(image_count or 0)),
        "content_count": max(0, int(content_count or 0)),
        "attachment_count": max(0, int(attachment_count or 0)),
        "valid": bool(valid),
        "issues": list(normalized_issues),
    }
    revision = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]
    return MaterialPreviewSnapshot(
        mode_id=payload["mode_id"],
        package_id=payload["package_id"],
        archive_id=payload["archive_id"],
        archive_name=payload["archive_name"],
        package_source_type=payload["package_source_type"],
        profile_id=payload["profile_id"],
        profile_name=payload["profile_name"],
        field_values=normalized_fields,
        field_scopes=normalized_scopes,
        asset_roles=normalized_roles,
        image_count=payload["image_count"],
        content_count=payload["content_count"],
        attachment_count=payload["attachment_count"],
        valid=payload["valid"],
        issues=normalized_issues,
        revision=revision,
    )


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


__all__ = [
    "MaterialPreviewSnapshot",
    "build_material_preview_snapshot",
]
