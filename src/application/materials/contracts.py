"""Application adapter from the product schema registry to domain contracts."""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache

from src.config.material_schema_registry import (
    MaterialSchema,
    get_material_schema,
)
from src.domain.materials import (
    MaterialContract,
    MaterialFieldContract,
    MaterialPackage,
    MaterialResourceRoleContract,
)

PACKAGE_CONTRACT_EXTENSIONS_KEY = "material_contract_extensions"


_SCHEMA_MODE_IDS = {
    "generic_document_v1": "custom",
    "official_document_v1": "official",
    "administrative_meeting_fields_v1": "official",
    "exam_items_v1": "exam",
    "teaching_assets_v1": "exam",
    "thesis_school_rule_context_v1": "thesis",
}

_DEFAULT_CONTRACT_IDS = {
    "custom": "generic_document_v1",
    "exam": "exam_items_v1",
    "thesis": "thesis_school_rule_context_v1",
    "official": "official_document_v1",
}


def default_material_contract_id(work_mode_id: str) -> str:
    mode = str(work_mode_id or "").strip()
    try:
        return _DEFAULT_CONTRACT_IDS[mode]
    except KeyError as exc:
        raise ValueError(f"material_contract_mode_unsupported:{mode}") from exc


@cache
def get_material_contract(
    contract_id: str,
    *,
    work_mode_id: str = "",
) -> MaterialContract:
    schema = get_material_schema(contract_id)
    return material_contract_from_schema(
        schema,
        work_mode_id=(
            work_mode_id
            or _SCHEMA_MODE_IDS.get(schema.schema_id, schema.family)
        ),
    )


def get_package_material_contract(package: MaterialPackage) -> MaterialContract:
    """Return the schema contract plus package-owned UI definitions.

    Material Package V1 remains the only persisted package format.  The former
    assets editor, however, allowed users to add their own fields and material
    tokens.  Those package-local declarations live in ``metadata`` and are
    merged into the immutable schema contract at every validation, preview and
    execution boundary.
    """

    if not isinstance(package, MaterialPackage):
        raise TypeError("material_package_required")
    base = get_material_contract(
        package.material_contract_id,
        work_mode_id=package.work_mode_id,
    )
    raw = package.metadata.get(PACKAGE_CONTRACT_EXTENSIONS_KEY, {})
    if raw in ({}, None):
        if not (
            package.work_mode_id == "custom"
            and package.material_contract_id == "generic_document_v1"
        ):
            return base
        raw = {}
    if not isinstance(raw, Mapping):
        raise TypeError("material_contract_extensions_must_be_object")
    unknown = set(raw) - {
        "fields",
        "resource_roles",
        "content_policy",
        "image_policy",
    }
    if unknown:
        raise ValueError(
            "material_contract_extensions_unknown_keys:"
            + ",".join(sorted(str(item) for item in unknown))
        )

    fields = list(base.fields)
    known_fields = {item.key for item in fields}
    for index, payload in enumerate(
        _extension_items(raw.get("fields", ()), path="fields")
    ):
        value_source = str(payload.get("value_source", "fixed") or "fixed")
        if value_source not in {"fixed", "floating"}:
            raise ValueError(
                "material_contract_extensions_"
                f"fields[{index}].value_source_invalid"
            )
        field = MaterialFieldContract(
            key=_extension_text(payload, "key", path=f"fields[{index}]"),
            label=_extension_text(payload, "label", path=f"fields[{index}]"),
            required=_extension_bool(
                payload,
                "required",
                path=f"fields[{index}]",
                default=False,
            ),
            allowed_scopes=_extension_scopes(
                payload,
                path=f"fields[{index}]",
            ),
            allow_run_override=True,
        )
        if value_source == "floating" and field.allowed_scopes != ("run",):
            raise ValueError(
                "material_contract_extensions_"
                f"fields[{index}].floating_scopes_invalid"
            )
        if field.key in known_fields:
            raise ValueError(f"material_contract_extension_field_duplicate:{field.key}")
        known_fields.add(field.key)
        fields.append(field)

    # Before custom-document fields became package-owned declarations, the
    # generic schema supplied six optional starter fields.  Preserve any such
    # field (and any older ad-hoc field) that already owns data or a rule, while
    # keeping never-used starter rows out of new and empty custom packages.
    if (
        package.work_mode_id == "custom"
        and package.material_contract_id == "generic_document_v1"
    ):
        for key in _legacy_package_field_keys(package):
            if key in known_fields:
                continue
            known_fields.add(key)
            fields.append(
                MaterialFieldContract(
                    key=key,
                    label=key,
                    required=False,
                    allowed_scopes=("shared", "group", "record", "run"),
                    allow_run_override=True,
                )
            )

    raw_content_policy = raw.get("content_policy", {})
    if not isinstance(raw_content_policy, Mapping):
        raise TypeError("material_contract_extensions_content_policy_must_be_object")
    content_format_mode = str(
        raw_content_policy.get("format_mode", "target_document")
        or "target_document"
    )
    if content_format_mode not in {"target_document", "plain_text"}:
        raise ValueError(
            "material_contract_extensions_content_policy.format_mode_invalid"
        )
    content_page_break_policy = str(
        raw_content_policy.get("page_break_policy", "drop") or "drop"
    )
    if content_page_break_policy not in {"drop", "preserve_explicit"}:
        raise ValueError(
            "material_contract_extensions_content_policy.page_break_policy_invalid"
        )

    resource_roles = list(base.resource_roles)
    known_roles = {item.role for item in resource_roles}
    for index, payload in enumerate(
        _extension_items(raw.get("resource_roles", ()), path="resource_roles")
    ):
        path = f"resource_roles[{index}]"
        max_items = payload.get("max_items", 1)
        if max_items is not None and type(max_items) is not int:
            raise TypeError(f"material_contract_extensions_{path}.max_items_invalid")
        min_items = payload.get("min_items", 0)
        if type(min_items) is not int:
            raise TypeError(f"material_contract_extensions_{path}.min_items_invalid")
        media_types = payload.get("accepted_media_types", ())
        if not isinstance(media_types, (list, tuple)) or any(
            type(item) is not str for item in media_types
        ):
            raise TypeError(
                f"material_contract_extensions_{path}.accepted_media_types_invalid"
            )
        role = MaterialResourceRoleContract(
            role=_extension_text(payload, "role", path=path),
            label=_extension_text(payload, "label", path=path),
            domain=_extension_text(payload, "domain", path=path),
            required=_extension_bool(payload, "required", path=path, default=False),
            allowed_scopes=_extension_scopes(payload, path=path),
            merge_policy=_extension_text(
                payload,
                "merge_policy",
                path=path,
                default="replace",
            ),
            min_items=min_items,
            max_items=max_items,
            accepted_media_types=tuple(media_types),
        )
        if role.role in known_roles:
            raise ValueError(
                f"material_contract_extension_resource_duplicate:{role.role}"
            )
        known_roles.add(role.role)
        resource_roles.append(role)

    return MaterialContract(
        contract_id=base.contract_id,
        work_mode_id=base.work_mode_id,
        label=base.label,
        fields=tuple(fields),
        resource_roles=tuple(resource_roles),
        supported_recipes=base.supported_recipes,
        supported_derivation_presets=base.supported_derivation_presets,
        supported_timeline_presets=base.supported_timeline_presets,
    )


def package_material_field_value_source(
    package: MaterialPackage,
    key: str,
) -> str:
    """Return whether a package field is stored now or filled per run."""

    raw = package.metadata.get(PACKAGE_CONTRACT_EXTENSIONS_KEY, {})
    if not isinstance(raw, Mapping):
        return "fixed"
    fields = raw.get("fields", ())
    if not isinstance(fields, (list, tuple)):
        return "fixed"
    for item in fields:
        if not isinstance(item, Mapping) or str(item.get("key", "")) != key:
            continue
        source = str(item.get("value_source", "fixed") or "fixed")
        return source if source in {"fixed", "floating"} else "fixed"
    return "fixed"


def material_contract_from_schema(
    schema: MaterialSchema,
    *,
    work_mode_id: str,
) -> MaterialContract:
    return MaterialContract(
        contract_id=schema.schema_id,
        work_mode_id=work_mode_id,
        label=schema.label,
        fields=tuple(
            MaterialFieldContract(
                key=item.key,
                label=item.label,
                required=item.required,
                allowed_scopes=("shared", "group", "record", "run"),
                allow_run_override=True,
            )
            for item in schema.fields
        ),
        resource_roles=tuple(
            MaterialResourceRoleContract(
                role=item.role,
                label=item.label,
                domain=item.material_domain,
                required=item.required,
                allowed_scopes=("shared", "group", "record", "run"),
                merge_policy="replace",
                min_items=item.min_items,
                max_items=item.max_items,
                accepted_media_types=_accepted_media_types(item.accepted_types),
            )
            for item in schema.asset_roles
        ),
    )


def _accepted_media_types(values: tuple[str, ...]) -> tuple[str, ...]:
    if values == ("image",):
        return ()
    return tuple(
        item
        for item in values
        if "/" in item
    )


def _legacy_package_field_keys(package: MaterialPackage) -> tuple[str, ...]:
    ordered: list[str] = []

    def remember(value: object) -> None:
        key = str(value or "").strip()
        if key and key not in ordered:
            ordered.append(key)

    scopes = (
        package.shared_scope,
        *(group.scope for group in package.groups),
        *(record.scope for record in package.records),
    )
    for scope in scopes:
        for key in scope.fields:
            remember(key)
        for key in scope.provenance:
            remember(key)
        for key, specification in scope.derivations.items():
            remember(key)
            remember(specification.output_field)
            for input_field in specification.input_fields:
                remember(input_field)
        for key, specification in scope.timelines.items():
            remember(key)
            remember(specification.output_field)
            remember(specification.anchor_field)
            remember(specification.parameters.get("end_field", ""))
    return tuple(ordered)


def _extension_items(value: object, *, path: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"material_contract_extensions_{path}_must_be_array")
    result: list[Mapping[str, object]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise TypeError(
                f"material_contract_extensions_{path}[{index}]_must_be_object"
            )
        result.append(item)
    return tuple(result)


def _extension_text(
    payload: Mapping[str, object],
    key: str,
    *,
    path: str,
    default: str = "",
) -> str:
    value = payload.get(key, default)
    if type(value) is not str or not value.strip() or value != value.strip():
        raise ValueError(f"material_contract_extensions_{path}.{key}_invalid")
    return value


def _extension_bool(
    payload: Mapping[str, object],
    key: str,
    *,
    path: str,
    default: bool,
) -> bool:
    value = payload.get(key, default)
    if type(value) is not bool:
        raise TypeError(f"material_contract_extensions_{path}.{key}_invalid")
    return value


def _extension_scopes(
    payload: Mapping[str, object],
    *,
    path: str,
) -> tuple[str, ...]:
    value = payload.get("allowed_scopes", ("shared", "group", "record", "run"))
    if not isinstance(value, (list, tuple)) or any(
        type(item) is not str for item in value
    ):
        raise TypeError(
            f"material_contract_extensions_{path}.allowed_scopes_invalid"
        )
    return tuple(value)


__all__ = [
    "PACKAGE_CONTRACT_EXTENSIONS_KEY",
    "default_material_contract_id",
    "get_material_contract",
    "get_package_material_contract",
    "material_contract_from_schema",
    "package_material_field_value_source",
]
