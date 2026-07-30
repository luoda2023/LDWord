"""Identity and destination-collision preflight for bundle publication."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path

from src.config.entity_models import EntityArchive


@dataclass(slots=True)
class BundleTargetRegistry:
    owners: dict[str, str] = field(default_factory=dict)

    def claim(self, path: Path, *, owner: str) -> None:
        key = os.path.abspath(path).replace("\\", "/").casefold()
        previous = self.owners.get(key)
        if previous is not None:
            raise ValueError(
                "entity_bundle_target_collision:"
                f"{path}:{previous}:{owner}"
            )
        self.owners[key] = owner


def validate_bundle_identity_plan(archive: EntityArchive) -> None:
    """Validate every logical identity before the staging directory exists."""

    profile_ids: dict[str, str] = {}
    profile_segments: dict[str, str] = {}
    for profile in archive.profiles:
        profile_id = profile.profile_id
        if (
            type(profile_id) is not str
            or not profile_id.strip()
            or profile_id != profile_id.strip()
        ):
            raise ValueError("entity_bundle_profile_id_invalid")
        identity_key = profile_id.casefold()
        if identity_key in profile_ids:
            raise ValueError(f"entity_bundle_profile_id_duplicate:{profile_id}")
        profile_ids[identity_key] = profile_id
        segment = safe_segment(profile_id).casefold()
        if segment in profile_segments:
            raise ValueError(
                "entity_bundle_profile_segment_collision:"
                f"{profile_segments[segment]}:{profile_id}"
            )
        profile_segments[segment] = profile_id

        asset_roles: list[str] = []
        for role, binding in profile.asset_bindings.items():
            _validate_bundle_role(role, domain="asset_binding")
            if type(binding.role) is not str or binding.role != role:
                raise ValueError(
                    f"entity_bundle_role_identity_mismatch:{role}:{binding.role}"
                )
            asset_roles.append(role)
        for role in profile.asset_paths:
            _validate_bundle_role(role, domain="asset_path")
            asset_roles.append(role)
        _validate_safe_segment_collisions(
            asset_roles,
            domain=f"profile:{profile_id}:asset_role",
            allow_exact_repeat=True,
        )

        item_ids: list[str] = []
        for index, item in enumerate(profile.asset_items):
            if type(item) is not dict:
                raise ValueError(
                    f"entity_bundle_asset_item_invalid:{profile_id}:{index}"
                )
            item_id = item.get("item_id")
            role = item.get("role")
            if type(item_id) is not str or not item_id.strip():
                raise ValueError(
                    f"entity_bundle_asset_item_id_invalid:{profile_id}:{index}"
                )
            _validate_bundle_role(
                role,
                domain=f"asset_item:{profile_id}:{item_id}",
            )
            item_ids.append(item_id)
        _validate_safe_segment_collisions(
            item_ids,
            domain=f"profile:{profile_id}:asset_item",
        )

        attachment_roles: list[str] = []
        for role, binding in profile.attachment_bindings.items():
            _validate_bundle_role(role, domain="attachment_binding")
            if binding.role != role:
                raise ValueError(
                    f"entity_bundle_role_identity_mismatch:{role}:{binding.role}"
                )
            attachment_roles.append(role)
        _validate_safe_segment_collisions(
            attachment_roles,
            domain=f"profile:{profile_id}:attachment_role",
        )


def safe_segment(value: object) -> str:
    forbidden = '<>:"/\\|?*'
    cleaned = "".join(
        char if char not in forbidden and ord(char) >= 32 else "_"
        for char in str(value or "").strip()
    ).strip(" ._")
    return cleaned or "asset"


def _validate_bundle_role(value: object, *, domain: str) -> None:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise ValueError(f"entity_bundle_role_invalid:{domain}:{value}")


def _validate_safe_segment_collisions(
    values: list[str],
    *,
    domain: str,
    allow_exact_repeat: bool = False,
) -> None:
    seen: dict[str, str] = {}
    identities: set[str] = set()
    for value in values:
        identity = value.casefold()
        if identity in identities and not (allow_exact_repeat and value in seen.values()):
            raise ValueError(f"entity_bundle_identity_duplicate:{domain}:{value}")
        identities.add(identity)
        segment = safe_segment(value).casefold()
        previous = seen.get(segment)
        if previous is not None and previous != value:
            raise ValueError(
                f"entity_bundle_safe_segment_collision:{domain}:{previous}:{value}"
            )
        seen[segment] = value


__all__ = [
    "BundleTargetRegistry",
    "safe_segment",
    "validate_bundle_identity_plan",
]
