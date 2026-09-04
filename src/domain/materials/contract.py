"""Material requirements owned by scenes/templates rather than packages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MaterialOwnerScope = Literal["shared", "group", "record", "run"]
MaterialResourceDomain = Literal["image", "content", "attachment"]


@dataclass(frozen=True, slots=True)
class MaterialFieldContract:
    key: str
    label: str
    required: bool = False
    allowed_scopes: tuple[MaterialOwnerScope, ...] = (
        "shared",
        "group",
        "record",
    )
    allow_run_override: bool = False

    def __post_init__(self) -> None:
        _require_key(self.key, "material_field_contract_key_invalid")
        _require_text(self.label, "material_field_contract_label_invalid")
        _require_scopes(self.allowed_scopes, label=f"field:{self.key}")
        if self.allow_run_override and "run" not in self.allowed_scopes:
            raise ValueError(
                f"material_field_run_scope_missing:{self.key}"
            )


@dataclass(frozen=True, slots=True)
class MaterialResourceRoleContract:
    role: str
    label: str
    domain: MaterialResourceDomain
    required: bool = False
    allowed_scopes: tuple[MaterialOwnerScope, ...] = (
        "shared",
        "group",
        "record",
    )
    merge_policy: Literal["replace", "append"] = "replace"
    min_items: int = 0
    max_items: int | None = 1
    accepted_media_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_key(self.role, "material_resource_contract_role_invalid")
        _require_text(self.label, "material_resource_contract_label_invalid")
        if self.domain not in {"image", "content", "attachment"}:
            raise ValueError(
                f"material_resource_contract_domain_invalid:{self.domain}"
            )
        _require_scopes(self.allowed_scopes, label=f"resource:{self.role}")
        if self.merge_policy not in {"replace", "append"}:
            raise ValueError(
                "material_resource_contract_merge_invalid:"
                f"{self.role}:{self.merge_policy}"
            )
        if type(self.min_items) is not int or self.min_items < 0:
            raise ValueError(
                f"material_resource_contract_min_invalid:{self.role}"
            )
        if (
            self.max_items is not None
            and (
                type(self.max_items) is not int
                or self.max_items < self.min_items
            )
        ):
            raise ValueError(
                f"material_resource_contract_max_invalid:{self.role}"
            )
        for media_type in self.accepted_media_types:
            _require_text(
                media_type,
                f"material_resource_media_type_invalid:{self.role}",
            )


@dataclass(frozen=True, slots=True)
class MaterialContract:
    contract_id: str
    work_mode_id: str
    label: str
    fields: tuple[MaterialFieldContract, ...] = ()
    resource_roles: tuple[MaterialResourceRoleContract, ...] = ()
    supported_recipes: tuple[str, ...] = (
        "document_batch",
        "material_suite",
    )
    supported_derivation_presets: tuple[tuple[str, int], ...] = (
        ("copy", 1),
        ("join", 1),
    )
    supported_timeline_presets: tuple[tuple[str, int], ...] = (
        ("date_offset_days", 1),
        ("timeline_ratio", 1),
    )

    def __post_init__(self) -> None:
        _require_key(self.contract_id, "material_contract_id_invalid")
        _require_key(self.work_mode_id, "material_contract_mode_invalid")
        _require_text(self.label, "material_contract_label_invalid")
        field_keys: set[str] = set()
        for item in self.fields:
            if not isinstance(item, MaterialFieldContract):
                raise TypeError("material_contract_field_type_invalid")
            if item.key in field_keys:
                raise ValueError(
                    f"material_contract_field_duplicate:{item.key}"
                )
            field_keys.add(item.key)
        roles: set[str] = set()
        for item in self.resource_roles:
            if not isinstance(item, MaterialResourceRoleContract):
                raise TypeError("material_contract_resource_type_invalid")
            if item.role in roles:
                raise ValueError(
                    f"material_contract_resource_duplicate:{item.role}"
                )
            roles.add(item.role)
        recipes: set[str] = set()
        for recipe_id in self.supported_recipes:
            _require_key(recipe_id, "material_contract_recipe_invalid")
            if recipe_id in recipes:
                raise ValueError(
                    f"material_contract_recipe_duplicate:{recipe_id}"
                )
            recipes.add(recipe_id)
        _require_versioned_presets(
            self.supported_derivation_presets,
            label="derivation",
        )
        _require_versioned_presets(
            self.supported_timeline_presets,
            label="timeline",
        )

    def get_field(self, key: str) -> MaterialFieldContract | None:
        return next((item for item in self.fields if item.key == key), None)

    def get_resource_role(
        self,
        role: str,
    ) -> MaterialResourceRoleContract | None:
        return next(
            (item for item in self.resource_roles if item.role == role),
            None,
        )


def _require_scopes(
    scopes: tuple[MaterialOwnerScope, ...],
    *,
    label: str,
) -> None:
    if type(scopes) is not tuple or not scopes:
        raise ValueError(f"material_contract_scopes_invalid:{label}")
    seen: set[str] = set()
    for scope in scopes:
        if scope not in {"shared", "group", "record", "run"}:
            raise ValueError(
                f"material_contract_scope_invalid:{label}:{scope}"
            )
        if scope in seen:
            raise ValueError(
                f"material_contract_scope_duplicate:{label}:{scope}"
            )
        seen.add(scope)


def _require_key(value: object, error: str) -> None:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or any(ord(char) < 32 for char in value)
    ):
        raise ValueError(error)


def _require_versioned_presets(
    values: tuple[tuple[str, int], ...],
    *,
    label: str,
) -> None:
    if type(values) is not tuple:
        raise TypeError(f"material_contract_{label}_presets_must_be_tuple")
    seen: set[tuple[str, int]] = set()
    for item in values:
        if (
            type(item) is not tuple
            or len(item) != 2
            or type(item[1]) is not int
            or item[1] < 1
        ):
            raise ValueError(f"material_contract_{label}_preset_invalid")
        _require_key(item[0], f"material_contract_{label}_preset_invalid")
        if item in seen:
            raise ValueError(
                f"material_contract_{label}_preset_duplicate:{item[0]}:{item[1]}"
            )
        seen.add(item)


def _require_text(value: object, error: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(error)


__all__ = [
    "MaterialContract",
    "MaterialFieldContract",
    "MaterialOwnerScope",
    "MaterialResourceDomain",
    "MaterialResourceRoleContract",
]
