"""Strict schema-v1 JSON codec for canonical material packages."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.domain.materials import (
    MATERIAL_PACKAGE_KIND,
    MATERIAL_PACKAGE_SCHEMA_VERSION,
    MaterialDerivationSpec,
    MaterialGroup,
    MaterialObjectRef,
    MaterialPackage,
    MaterialRecord,
    MaterialResourceBinding,
    MaterialScope,
    MaterialTimelineSpec,
)


_ROOT_KEYS = {
    "kind",
    "schema_version",
    "package_id",
    "display_name",
    "work_mode_id",
    "material_contract_id",
    "shared_scope",
    "groups",
    "records",
    "metadata",
}
_SCOPE_KEYS = {
    "fields",
    "resources",
    "derivations",
    "timelines",
    "provenance",
}
_GROUP_KEYS = {"group_id", "display_name", "scope", "metadata"}
_RECORD_KEYS = {
    "record_id",
    "display_name",
    "group_id",
    "lifecycle",
    "scope",
    "origin",
}
_RESOURCE_KEYS = {"role", "merge_policy", "items"}
_OBJECT_KEYS = {"object_id", "media_type", "original_name", "size"}
_DERIVATION_KEYS = {
    "output_field",
    "preset_id",
    "preset_version",
    "input_fields",
    "parameters",
}
_TIMELINE_KEYS = {
    "output_field",
    "preset_id",
    "preset_version",
    "anchor_field",
    "parameters",
}
MAX_PACKAGE_JSON_BYTES = 8 * 1024 * 1024


def canonical_material_package_bytes(package: MaterialPackage) -> bytes:
    payload = material_package_to_payload(package)
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def material_package_revision(package: MaterialPackage) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_material_package_bytes(package)
    ).hexdigest()


def material_package_to_payload(package: MaterialPackage) -> dict[str, Any]:
    if not isinstance(package, MaterialPackage):
        raise TypeError("material_package_type_invalid")
    return {
        "kind": package.kind,
        "schema_version": package.schema_version,
        "package_id": package.package_id,
        "display_name": package.display_name,
        "work_mode_id": package.work_mode_id,
        "material_contract_id": package.material_contract_id,
        "shared_scope": _scope_payload(package.shared_scope),
        "groups": [
            {
                "group_id": group.group_id,
                "display_name": group.display_name,
                "scope": _scope_payload(group.scope),
                "metadata": _json_value(group.metadata),
            }
            for group in package.groups
        ],
        "records": [
            {
                "record_id": record.record_id,
                "display_name": record.display_name,
                "group_id": record.group_id,
                "lifecycle": record.lifecycle,
                "scope": _scope_payload(record.scope),
                "origin": _json_value(record.origin),
            }
            for record in package.records
        ],
        "metadata": _json_value(package.metadata),
    }


def load_material_package(path: str | Path) -> MaterialPackage:
    source = Path(path)
    try:
        if source.stat().st_size > MAX_PACKAGE_JSON_BYTES:
            raise ValueError("material_package_json_too_large")
        raw = source.read_bytes()
        if len(raw) > MAX_PACKAGE_JSON_BYTES:
            raise ValueError("material_package_json_too_large")
        payload = json.loads(
            raw.decode("utf-8"),
            parse_constant=_reject_json_constant,
        )
    except UnicodeDecodeError as exc:
        raise ValueError("material_package_encoding_invalid:utf-8") from exc
    package = material_package_from_payload(payload)
    canonical_payload = material_package_to_payload(package)
    if canonical_payload != payload:
        difference = _first_difference(payload, canonical_payload)
        raise ValueError(f"material_package_not_canonical:{difference}")
    return package


def material_package_from_payload(payload: object) -> MaterialPackage:
    root = _require_object(payload, "<package>")
    _require_exact_keys(root, _ROOT_KEYS, "<package>")
    if root["kind"] != MATERIAL_PACKAGE_KIND:
        raise ValueError(f"material_package_kind_invalid:{root['kind']}")
    if (
        type(root["schema_version"]) is not int
        or root["schema_version"] != MATERIAL_PACKAGE_SCHEMA_VERSION
    ):
        raise ValueError(
            "material_package_schema_version_unsupported:"
            f"{root['schema_version']}"
        )
    for key in (
        "package_id",
        "display_name",
        "work_mode_id",
        "material_contract_id",
    ):
        _require_string(root[key], key)
    groups_raw = _require_list(root["groups"], "groups")
    records_raw = _require_list(root["records"], "records")
    groups: list[MaterialGroup] = []
    for index, raw in enumerate(groups_raw):
        item = _require_object(raw, f"groups[{index}]")
        _require_exact_keys(item, _GROUP_KEYS, f"groups[{index}]")
        _require_string(item["group_id"], f"groups[{index}].group_id")
        _require_string(item["display_name"], f"groups[{index}].display_name")
        groups.append(
            MaterialGroup(
                group_id=item["group_id"],
                display_name=item["display_name"],
                scope=_scope_from_payload(
                    item["scope"],
                    path=f"groups[{index}].scope",
                ),
                metadata=_require_json_object(
                    item["metadata"],
                    path=f"groups[{index}].metadata",
                ),
            )
        )
    records: list[MaterialRecord] = []
    for index, raw in enumerate(records_raw):
        item = _require_object(raw, f"records[{index}]")
        _require_exact_keys(item, _RECORD_KEYS, f"records[{index}]")
        for key in ("record_id", "display_name", "group_id", "lifecycle"):
            _require_string(item[key], f"records[{index}].{key}")
        records.append(
            MaterialRecord(
                record_id=item["record_id"],
                display_name=item["display_name"],
                group_id=item["group_id"],
                lifecycle=item["lifecycle"],
                scope=_scope_from_payload(
                    item["scope"],
                    path=f"records[{index}].scope",
                ),
                origin=_require_json_object(
                    item["origin"],
                    path=f"records[{index}].origin",
                ),
            )
        )
    return MaterialPackage(
        package_id=root["package_id"],
        display_name=root["display_name"],
        work_mode_id=root["work_mode_id"],
        material_contract_id=root["material_contract_id"],
        shared_scope=_scope_from_payload(
            root["shared_scope"],
            path="shared_scope",
        ),
        groups=tuple(groups),
        records=tuple(records),
        metadata=_require_json_object(root["metadata"], path="metadata"),
        kind=root["kind"],
        schema_version=root["schema_version"],
    )


def _scope_payload(scope: MaterialScope) -> dict[str, Any]:
    return {
        "fields": dict(scope.fields),
        "resources": {
            role: {
                "role": binding.role,
                "merge_policy": binding.merge_policy,
                "items": [
                    {
                        "object_id": item.object_id,
                        "media_type": item.media_type,
                        "original_name": item.original_name,
                        "size": item.size,
                    }
                    for item in binding.items
                ],
            }
            for role, binding in scope.resources.items()
        },
        "derivations": {
            key: {
                "output_field": item.output_field,
                "preset_id": item.preset_id,
                "preset_version": item.preset_version,
                "input_fields": list(item.input_fields),
                "parameters": dict(item.parameters),
            }
            for key, item in scope.derivations.items()
        },
        "timelines": {
            key: {
                "output_field": item.output_field,
                "preset_id": item.preset_id,
                "preset_version": item.preset_version,
                "anchor_field": item.anchor_field,
                "parameters": dict(item.parameters),
            }
            for key, item in scope.timelines.items()
        },
        "provenance": dict(scope.provenance),
    }


def _scope_from_payload(payload: object, *, path: str) -> MaterialScope:
    root = _require_object(payload, path)
    _require_exact_keys(root, _SCOPE_KEYS, path)
    fields = _require_text_mapping(root["fields"], path=f"{path}.fields")
    provenance = _require_text_mapping(
        root["provenance"],
        path=f"{path}.provenance",
    )
    derivations_root = _require_object(
        root["derivations"],
        f"{path}.derivations",
    )
    derivations: dict[str, MaterialDerivationSpec] = {}
    for key, raw_spec in derivations_root.items():
        _require_string(key, f"{path}.derivations.key")
        spec = _require_object(raw_spec, f"{path}.derivations.{key}")
        _require_exact_keys(
            spec,
            _DERIVATION_KEYS,
            f"{path}.derivations.{key}",
        )
        for field_name in ("output_field", "preset_id"):
            _require_string(
                spec[field_name],
                f"{path}.derivations.{key}.{field_name}",
            )
        if type(spec["preset_version"]) is not int:
            raise ValueError(
                "material_package_field_type_invalid:"
                f"{path}.derivations.{key}.preset_version:int"
            )
        inputs = _require_list(
            spec["input_fields"],
            f"{path}.derivations.{key}.input_fields",
        )
        for index, input_field in enumerate(inputs):
            _require_string(
                input_field,
                f"{path}.derivations.{key}.input_fields[{index}]",
            )
        derivations[key] = MaterialDerivationSpec(
            output_field=spec["output_field"],
            preset_id=spec["preset_id"],
            preset_version=spec["preset_version"],
            input_fields=tuple(inputs),
            parameters=_require_text_mapping(
                spec["parameters"],
                path=f"{path}.derivations.{key}.parameters",
            ),
        )
    timelines_root = _require_object(
        root["timelines"],
        f"{path}.timelines",
    )
    timelines: dict[str, MaterialTimelineSpec] = {}
    for key, raw_spec in timelines_root.items():
        _require_string(key, f"{path}.timelines.key")
        spec = _require_object(raw_spec, f"{path}.timelines.{key}")
        _require_exact_keys(
            spec,
            _TIMELINE_KEYS,
            f"{path}.timelines.{key}",
        )
        for field_name in ("output_field", "preset_id", "anchor_field"):
            _require_string(
                spec[field_name],
                f"{path}.timelines.{key}.{field_name}",
            )
        if type(spec["preset_version"]) is not int:
            raise ValueError(
                "material_package_field_type_invalid:"
                f"{path}.timelines.{key}.preset_version:int"
            )
        timelines[key] = MaterialTimelineSpec(
            output_field=spec["output_field"],
            preset_id=spec["preset_id"],
            preset_version=spec["preset_version"],
            anchor_field=spec["anchor_field"],
            parameters=_require_text_mapping(
                spec["parameters"],
                path=f"{path}.timelines.{key}.parameters",
            ),
        )
    resources_root = _require_object(
        root["resources"],
        f"{path}.resources",
    )
    resources: dict[str, MaterialResourceBinding] = {}
    for role, raw_binding in resources_root.items():
        _require_string(role, f"{path}.resources.key")
        binding = _require_object(
            raw_binding,
            f"{path}.resources.{role}",
        )
        _require_exact_keys(
            binding,
            _RESOURCE_KEYS,
            f"{path}.resources.{role}",
        )
        _require_string(
            binding["role"],
            f"{path}.resources.{role}.role",
        )
        _require_string(
            binding["merge_policy"],
            f"{path}.resources.{role}.merge_policy",
        )
        raw_items = _require_list(
            binding["items"],
            f"{path}.resources.{role}.items",
        )
        items: list[MaterialObjectRef] = []
        for index, raw_item in enumerate(raw_items):
            item = _require_object(
                raw_item,
                f"{path}.resources.{role}.items[{index}]",
            )
            _require_exact_keys(
                item,
                _OBJECT_KEYS,
                f"{path}.resources.{role}.items[{index}]",
            )
            for key in ("object_id", "media_type", "original_name"):
                _require_string(
                    item[key],
                    f"{path}.resources.{role}.items[{index}].{key}",
                )
            if type(item["size"]) is not int:
                raise ValueError(
                    "material_package_field_type_invalid:"
                    f"{path}.resources.{role}.items[{index}].size:int"
                )
            items.append(
                MaterialObjectRef(
                    object_id=item["object_id"],
                    media_type=item["media_type"],
                    original_name=item["original_name"],
                    size=item["size"],
                )
            )
        resources[role] = MaterialResourceBinding(
            role=binding["role"],
            merge_policy=binding["merge_policy"],
            items=tuple(items),
        )
    return MaterialScope(
        fields=fields,
        resources=resources,
        derivations=derivations,
        timelines=timelines,
        provenance=provenance,
    )


def _require_object(value: object, path: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise ValueError(f"material_package_field_type_invalid:{path}:object")
    return value


def _require_list(value: object, path: str) -> list[Any]:
    if type(value) is not list:
        raise ValueError(f"material_package_field_type_invalid:{path}:list")
    return value


def _require_string(value: object, path: str) -> None:
    if type(value) is not str:
        raise ValueError(f"material_package_field_type_invalid:{path}:string")


def _require_exact_keys(
    payload: Mapping[str, object],
    expected: set[str],
    path: str,
) -> None:
    missing = sorted(expected - set(payload))
    unknown = sorted(set(payload) - expected)
    if missing:
        raise ValueError(
            f"material_package_fields_missing:{path}:{','.join(missing)}"
        )
    if unknown:
        raise ValueError(
            f"material_package_fields_unknown:{path}:{','.join(unknown)}"
        )


def _require_text_mapping(
    value: object,
    *,
    path: str,
) -> dict[str, str]:
    root = _require_object(value, path)
    for key, item in root.items():
        _require_string(key, f"{path}.key")
        _require_string(item, f"{path}.{key}")
    return dict(root)


def _require_json_mapping(
    value: object,
    *,
    path: str,
) -> dict[str, dict[str, Any]]:
    root = _require_object(value, path)
    result: dict[str, dict[str, Any]] = {}
    for key, item in root.items():
        _require_string(key, f"{path}.key")
        result[key] = _require_json_object(item, path=f"{path}.{key}")
    return result


def _require_json_object(
    value: object,
    *,
    path: str,
) -> dict[str, Any]:
    root = _require_object(value, path)
    _validate_json_value(root, path=path)
    return root


def _validate_json_value(value: object, *, path: str) -> None:
    if value is None or type(value) in {str, bool, int}:
        return
    if type(value) is float:
        if value != value or value in {float("inf"), float("-inf")}:
            raise ValueError(f"material_package_json_number_invalid:{path}")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError(
                    f"material_package_json_key_invalid:{path}"
                )
            _validate_json_value(item, path=f"{path}.{key}")
        return
    raise ValueError(f"material_package_json_type_invalid:{path}")


def _json_value(value: object) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"material_package_json_constant_invalid:{value}")


def _first_difference(left: object, right: object, path: str = "<package>") -> str:
    if type(left) is not type(right):
        return f"{path}:type"
    if isinstance(left, dict):
        for key in left:
            if key not in right:
                return f"{path}.{key}:missing_from_canonical"
            difference = _first_difference(
                left[key],
                right[key],
                f"{path}.{key}",
            )
            if difference:
                return difference
        for key in right:
            if key not in left:
                return f"{path}.{key}:added_by_canonical"
        return ""
    if isinstance(left, list):
        if len(left) != len(right):
            return f"{path}:length"
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            difference = _first_difference(
                left_item,
                right_item,
                f"{path}[{index}]",
            )
            if difference:
                return difference
        return ""
    if left != right:
        return f"{path}:value"
    return ""


__all__ = [
    "canonical_material_package_bytes",
    "load_material_package",
    "material_package_from_payload",
    "material_package_revision",
    "material_package_to_payload",
]
