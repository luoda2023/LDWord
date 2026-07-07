"""Presenter mixin for current asset collection state projection."""

from __future__ import annotations

from src.config.entity import EntityProfile
from src.config.materials import (
    AssetInsertionRule,
    asset_items_from_role_paths,
    parse_asset_insertion_rules,
    scan_asset_collection,
)
from src.ui.panels.assets.items import (
    _asset_items_from_payloads,
    _asset_items_with_metadata,
    _normalized_asset_metadata,
)


class AssetCollectionStatePresenterMixin:
    """Project editor asset paths, payloads, metadata, and insertion rules."""

    def _asset_items_for_profile(self, profile: EntityProfile):
        scanned_items = (
            scan_asset_collection(profile.assets_dir).items
            if str(profile.assets_dir or "").strip()
            else []
        )
        return _asset_items_with_metadata(
            [
                *scanned_items,
                *_asset_items_from_payloads(profile.asset_items),
                *asset_items_from_role_paths(profile.asset_paths),
            ],
            profile.asset_metadata,
        )

    def _current_asset_items(self):
        assets_dir = self._assets_picker.path().strip()
        scanned_items = (
            scan_asset_collection(assets_dir).items
            if assets_dir
            else []
        )
        return _asset_items_with_metadata(
            [
                *scanned_items,
                *_asset_items_from_payloads(self._asset_item_payloads),
                *asset_items_from_role_paths(self._asset_paths),
            ],
            self._current_asset_metadata(),
        )

    def _current_asset_metadata(self) -> dict[str, dict[str, str]]:
        metadata = _normalized_asset_metadata(self._asset_metadata)
        for role, edit in self._asset_slot_alt_text_inputs.items():
            alt_text = edit.text().strip()
            role_metadata = dict(metadata.get(role, {}))
            if alt_text:
                role_metadata["alt_text"] = alt_text
            else:
                role_metadata.pop("alt_text", None)
            if role_metadata:
                metadata[role] = role_metadata
            else:
                metadata.pop(role, None)
        return metadata

    def _image_rules_for_asset_items(self, asset_items) -> list[AssetInsertionRule]:
        advanced_rules = parse_asset_insertion_rules(self._image_rules_edit.get_text())
        advanced_roles = {rule.asset_role for rule in advanced_rules if rule.asset_role}
        available_roles = {item.role for item in asset_items if item.role and item.path}
        frontstage_rules = [
            AssetInsertionRule(
                rule_id=role,
                asset_role=role,
                target=target,
                required=required,
            )
            for role, _label, target, required in (
                (spec.role, spec.label, spec.target, spec.required)
                for spec in self._asset_slot_specs
            )
            if (role in available_roles or required) and role not in advanced_roles
        ]
        return [*frontstage_rules, *advanced_rules]


__all__ = ["AssetCollectionStatePresenterMixin"]
