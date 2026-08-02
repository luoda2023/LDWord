"""Draft transaction behind the attachment preparation dialog."""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from pathlib import Path

from src.config.attachment_materials import AttachmentBinding
from src.config.entity import EntityProfile, clone_entity_profile
from src.services.material_attachments.preparation import (
    AttachmentPreparationReport,
    AttachmentPreparationRequirement,
    build_attachment_preparation_report,
)
from src.services.material_attachments.timeline_preparation import (
    apply_attachment_timeline_plan,
    attachment_owned_timeline_plans,
)


class AttachmentPreparationSession:
    """Own one isolated edit transaction for exactly the generation scope."""

    def __init__(
        self,
        *,
        role: str,
        binding: AttachmentBinding,
        profiles: Sequence[EntityProfile],
        current_profile_index: int = 0,
        image_token_bindings: Mapping[str, str] | None = None,
    ) -> None:
        if not profiles:
            raise ValueError("attachment_preparation_profiles_empty")
        self.role = str(role or "").strip()
        self.binding = copy.deepcopy(binding)
        self._profiles = [clone_entity_profile(profile) for profile in profiles]
        self.current_profile_index = max(
            0,
            min(int(current_profile_index), len(self._profiles) - 1),
        )
        self._base_profile = clone_entity_profile(
            self._profiles[self.current_profile_index]
        )
        self.image_token_bindings = dict(image_token_bindings or {})
        self.source_path = ""
        self.dirty = False
        self.profiles_replaced = False
        self.report = self._build_report()

    @property
    def profiles(self) -> tuple[EntityProfile, ...]:
        return tuple(self._profiles)

    def result_profiles(self) -> list[EntityProfile]:
        return [clone_entity_profile(profile) for profile in self._profiles]

    def refresh(self) -> AttachmentPreparationReport:
        self.report = self._build_report()
        return self.report

    def requirement(
        self,
        token: str,
    ) -> AttachmentPreparationRequirement | None:
        return next(
            (item for item in self.report.requirements if item.token == token),
            None,
        )

    def profile_resource_key(self, token: str, profile_index: int) -> str:
        requirement = self.requirement(token)
        if requirement is None or not 0 <= profile_index < len(requirement.profiles):
            return ""
        return str(requirement.profiles[profile_index].resource_key or "").strip()

    def field_value(self, token: str, profile_index: int) -> str:
        key = self.profile_resource_key(token, profile_index)
        if not key or not 0 <= profile_index < len(self._profiles):
            return ""
        return str(self._profiles[profile_index].fields.get(key, "") or "")

    def set_field_value(self, token: str, profile_index: int, value: str) -> bool:
        if not 0 <= profile_index < len(self._profiles):
            return False
        key = self.profile_resource_key(token, profile_index)
        if not key:
            return False
        profile = self._profiles[profile_index]
        profile.declared_field_keys = list(
            dict.fromkeys((*profile.declared_field_keys, key, *profile.fields.keys()))
        )
        cleaned = str(value or "").strip()
        if cleaned:
            profile.fields[key] = cleaned
        else:
            profile.fields.pop(key, None)
        self.dirty = True
        self.refresh()
        return True

    def set_field_values(
        self,
        token: str,
        values_by_profile: Mapping[int, str],
    ) -> bool:
        updates: list[tuple[EntityProfile, str, str]] = []
        for profile_index, value in values_by_profile.items():
            if not 0 <= int(profile_index) < len(self._profiles):
                continue
            index = int(profile_index)
            key = self.profile_resource_key(token, index)
            if key:
                updates.append((self._profiles[index], key, str(value or "").strip()))
        if not updates:
            return False
        for profile, key, value in updates:
            profile.declared_field_keys = list(
                dict.fromkeys((*profile.declared_field_keys, key, *profile.fields.keys()))
            )
            if value:
                profile.fields[key] = value
            else:
                profile.fields.pop(key, None)
        self.dirty = True
        self.refresh()
        return True

    def apply_timeline_plan(self, plan: Mapping[str, object]) -> str:
        plan_id = apply_attachment_timeline_plan(
            self._profiles,
            role=self.role,
            plan=plan,
        )
        self.dirty = True
        self.refresh()
        return plan_id

    def replace_profiles(
        self,
        profiles: Sequence[EntityProfile],
        *,
        source_path: str | Path,
    ) -> None:
        if not profiles:
            raise ValueError("attachment_preparation_import_empty")
        self._profiles = self._inherit_package_materials(profiles)
        self.current_profile_index = 0
        self.source_path = str(Path(source_path).resolve())
        self.profiles_replaced = True
        self.dirty = True
        self.refresh()

    def _build_report(self) -> AttachmentPreparationReport:
        return build_attachment_preparation_report(
            self.binding,
            self._profiles,
            image_token_bindings=self.image_token_bindings,
        )

    def _inherit_package_materials(
        self,
        imported: Sequence[EntityProfile],
    ) -> list[EntityProfile]:
        """Inherit only package dependencies, never unrelated profile domains."""

        base = self._base_profile
        image_roles = {
            str(role or "").strip()
            for role in self.image_token_bindings.values()
            if str(role or "").strip()
        }
        inherited_timeline = attachment_owned_timeline_plans(base.timeline_plans)
        existing_ids: set[str] = set()
        result: list[EntityProfile] = []
        for index, profile in enumerate(imported, start=1):
            profile_id = _unique_profile_id(profile.profile_id, index, existing_ids)
            existing_ids.add(profile_id)
            result.append(
                clone_entity_profile(
                    profile,
                    profile_id=profile_id,
                    profile_name=(
                        str(profile.profile_name or "").strip() or f"第 {index} 份"
                    ),
                    field_aliases={
                        **copy.deepcopy(base.field_aliases),
                        **copy.deepcopy(profile.field_aliases),
                    },
                    timeline_plans={
                        **copy.deepcopy(inherited_timeline),
                        **copy.deepcopy(profile.timeline_plans),
                    },
                    asset_paths=_inherit_role_mapping(
                        profile.asset_paths,
                        base.asset_paths,
                        image_roles,
                    ),
                    asset_bindings=_inherit_role_mapping(
                        profile.asset_bindings,
                        base.asset_bindings,
                        image_roles,
                    ),
                    asset_metadata=_inherit_role_mapping(
                        profile.asset_metadata,
                        base.asset_metadata,
                        image_roles,
                    ),
                    asset_items=_inherit_asset_items(
                        profile.asset_items,
                        base.asset_items,
                        image_roles,
                    ),
                    image_material_rules=_inherit_image_rules(
                        profile.image_material_rules,
                        base.image_material_rules,
                        image_roles,
                    ),
                    attachment_bindings={
                        **copy.deepcopy(profile.attachment_bindings),
                        self.role: copy.deepcopy(self.binding),
                    },
                )
            )
        return result


def _unique_profile_id(raw_id: str, index: int, existing: set[str]) -> str:
    base = str(raw_id or "").strip() or f"profile_{index}"
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def _inherit_role_mapping(current, base, roles: set[str]):
    merged = copy.deepcopy(dict(current or {}))
    for role in roles:
        if role not in merged and role in dict(base or {}):
            merged[role] = copy.deepcopy(dict(base or {})[role])
    return merged


def _inherit_asset_items(current, base, roles: set[str]) -> list[dict[str, object]]:
    items = copy.deepcopy(list(current or []))
    occupied = {
        str(dict(item).get("role", "") or "").strip()
        for item in items
        if isinstance(item, Mapping)
    }
    items.extend(
        copy.deepcopy(item)
        for item in list(base or [])
        if isinstance(item, Mapping)
        and str(dict(item).get("role", "") or "").strip() in roles - occupied
    )
    return items


def _inherit_image_rules(current, base, roles: set[str]):
    merged = copy.deepcopy(dict(current or {}))
    for rule_id, rule in dict(base or {}).items():
        role = str(getattr(rule, "source_role", "") or "").strip()
        if role in roles and rule_id not in merged:
            merged[rule_id] = copy.deepcopy(rule)
    return merged


__all__ = ["AttachmentPreparationSession"]
