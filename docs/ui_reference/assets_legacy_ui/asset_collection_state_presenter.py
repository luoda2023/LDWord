"""Presenter mixin for current asset collection state projection."""

from __future__ import annotations

from src.config.entity import EntityProfile
from src.config.asset_resolution import resolve_profile_assets
from src.config.materials import (
    AssetInsertionRule,
)
from src.ui.panels.assets.items import _normalized_asset_metadata


class AssetCollectionStatePresenterMixin:
    """Project editor asset paths, payloads, metadata, and insertion rules."""

    def _asset_items_for_profile(self, profile: EntityProfile):
        role_specs = (
            *tuple(getattr(self, "_asset_slot_specs", ())),
            *tuple(getattr(self, "_asset_group_specs", ())),
        )
        resolution = resolve_profile_assets(profile, role_specs=role_specs)
        self._asset_resolution_diagnostics = list(resolution.diagnostics)
        return resolution.items

    def _current_asset_items(self):
        profile = EntityProfile(
            assets_dir=self._assets_picker.path().strip(),
            asset_paths=dict(self._asset_paths),
            asset_bindings=self._copy_asset_bindings(),
            asset_metadata=self._current_asset_metadata(),
            asset_items=list(self._asset_item_payloads),
        )
        role_specs = (
            *tuple(getattr(self, "_asset_slot_specs", ())),
            *tuple(getattr(self, "_asset_group_specs", ())),
        )
        resolution = resolve_profile_assets(profile, role_specs=role_specs)
        self._asset_resolution_diagnostics = list(resolution.diagnostics)
        return resolution.items

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
        available_roles = {item.role for item in asset_items if item.role and item.path}
        frontstage_specs = (
            *tuple(getattr(self, "_asset_slot_specs", ())),
            *tuple(getattr(self, "_asset_group_specs", ())),
        )
        frontstage_rules = [
            AssetInsertionRule(
                rule_id=role,
                asset_role=role,
                target=target,
                required=required,
                cardinality=cardinality,
                min_items=min_items,
                max_items=max_items,
            )
            for role, _label, target, required, cardinality, min_items, max_items in (
                (
                    spec.role,
                    spec.label,
                    spec.target,
                    spec.required,
                    "multiple" if spec in tuple(getattr(self, "_asset_group_specs", ())) else "single",
                    int(getattr(spec, "min_items", 0) or 0),
                    getattr(spec, "max_items", 1),
                )
                for spec in frontstage_specs
            )
            if role in available_roles or required
        ]
        return frontstage_rules


__all__ = ["AssetCollectionStatePresenterMixin"]
