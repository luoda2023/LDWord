"""Single authoritative material-package domain model.

The domain deliberately contains no file-system, Qt, archive, profile, or
wire-format compatibility behavior.  Values are validated exactly as supplied;
normalization belongs to the import-draft boundary.
"""

from __future__ import annotations

import copy
import json
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from dataclasses import fields as dataclass_fields
from types import MappingProxyType
from typing import Any, Literal

MATERIAL_PACKAGE_KIND = "alavette.material_package"
MATERIAL_PACKAGE_SCHEMA_VERSION = 1
MATERIAL_RECORD_LIFECYCLES = frozenset(
    {"draft", "active", "disabled", "archived"}
)

_PACKAGE_ID_PATTERN = re.compile(r"pkg_[0-9a-f]{32}\Z")
_GROUP_ID_PATTERN = re.compile(r"grp_[0-9a-f]{32}\Z")
_RECORD_ID_PATTERN = re.compile(r"rec_[0-9a-f]{32}\Z")
_OBJECT_ID_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
MAX_DISPLAY_TEXT_LENGTH = 512
MAX_FIELD_KEY_LENGTH = 128
MAX_FIELD_VALUE_LENGTH = 1_000_000
MAX_SCOPE_FIELD_COUNT = 2048
MAX_SCOPE_RESOURCE_ROLE_COUNT = 256
MAX_RESOURCE_ITEMS_PER_ROLE = 2048
MAX_PACKAGE_GROUP_COUNT = 10_000
MAX_PACKAGE_RECORD_COUNT = 100_000
MAX_METADATA_BYTES = 65_536
MAX_OBJECT_SIZE = 1_073_741_824

MaterialLifecycle = Literal["draft", "active", "disabled", "archived"]
ResourceMergePolicy = Literal["replace", "append"]


def generate_package_id() -> str:
    return f"pkg_{uuid.uuid4().hex}"


def generate_group_id() -> str:
    return f"grp_{uuid.uuid4().hex}"


def generate_record_id() -> str:
    return f"rec_{uuid.uuid4().hex}"


@dataclass(frozen=True, slots=True)
class MaterialIssue:
    """Typed problem returned across application/UI boundaries."""

    code: str
    path: str = ""
    message: str = ""
    severity: Literal["error", "warning"] = "error"
    remediation: str = ""

    def __post_init__(self) -> None:
        _require_text(self.code, "issue.code")
        if self.path:
            _require_exact_text(self.path, "issue.path")
        if self.message:
            _require_exact_text(self.message, "issue.message")
        if self.remediation:
            _require_exact_text(self.remediation, "issue.remediation")
        if self.severity not in {"error", "warning"}:
            raise ValueError(f"material_issue_severity_invalid:{self.severity}")


@dataclass(frozen=True, slots=True)
class MaterialObjectRef:
    """One immutable object vendored into a package bundle."""

    object_id: str
    media_type: str
    original_name: str
    size: int

    def __post_init__(self) -> None:
        if type(self.object_id) is not str or not _OBJECT_ID_PATTERN.fullmatch(
            self.object_id
        ):
            raise ValueError("material_object_id_invalid")
        _require_text(self.media_type, "material_object.media_type")
        _require_text(self.original_name, "material_object.original_name")
        if len(self.original_name) > 255:
            raise ValueError("material_object_original_name_too_long")
        if type(self.size) is not int or not 0 <= self.size <= MAX_OBJECT_SIZE:
            raise ValueError("material_object_size_invalid")


@dataclass(frozen=True, slots=True)
class MaterialResourceBinding:
    """Role-keyed resources owned by one material scope."""

    role: str
    items: tuple[MaterialObjectRef, ...]
    merge_policy: ResourceMergePolicy = "replace"

    def __post_init__(self) -> None:
        _require_key(self.role, "material_resource.role")
        if self.merge_policy not in {"replace", "append"}:
            raise ValueError(
                f"material_resource_merge_policy_invalid:{self.merge_policy}"
            )
        if type(self.items) is not tuple:
            raise TypeError("material_resource_items_must_be_tuple")
        if len(self.items) > MAX_RESOURCE_ITEMS_PER_ROLE:
            raise ValueError(
                f"material_resource_items_limit_exceeded:{self.role}"
            )
        seen: set[str] = set()
        for item in self.items:
            if not isinstance(item, MaterialObjectRef):
                raise TypeError("material_resource_item_type_invalid")
            if item.object_id in seen:
                raise ValueError(
                    f"material_resource_object_duplicate:{self.role}:{item.object_id}"
                )
            seen.add(item.object_id)


@dataclass(frozen=True, slots=True)
class MaterialDerivationSpec:
    """Versioned, declarative derivation owned by one material scope."""

    output_field: str
    preset_id: str
    preset_version: int
    input_fields: tuple[str, ...]
    parameters: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_key(self.output_field, "material_derivation.output_field")
        _require_key(self.preset_id, "material_derivation.preset_id")
        if type(self.preset_version) is not int or self.preset_version < 1:
            raise ValueError("material_derivation_preset_version_invalid")
        if type(self.input_fields) is not tuple or not self.input_fields:
            raise ValueError("material_derivation_input_fields_required")
        seen: set[str] = set()
        for key in self.input_fields:
            _require_key(key, "material_derivation.input_field")
            if key in seen:
                raise ValueError(
                    f"material_derivation_input_duplicate:{key}"
                )
            seen.add(key)
        object.__setattr__(
            self,
            "parameters",
            _freeze_text_mapping(
                self.parameters,
                path="material_derivation.parameters",
            ),
        )


@dataclass(frozen=True, slots=True)
class MaterialTimelineSpec:
    """Versioned, deterministic timeline calculation."""

    output_field: str
    preset_id: str
    preset_version: int
    anchor_field: str
    parameters: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_key(self.output_field, "material_timeline.output_field")
        _require_key(self.preset_id, "material_timeline.preset_id")
        if type(self.preset_version) is not int or self.preset_version < 1:
            raise ValueError("material_timeline_preset_version_invalid")
        _require_key(self.anchor_field, "material_timeline.anchor_field")
        object.__setattr__(
            self,
            "parameters",
            _freeze_text_mapping(
                self.parameters,
                path="material_timeline.parameters",
            ),
        )


@dataclass(frozen=True, slots=True)
class MaterialScope:
    """Values and resource instances owned by exactly one hierarchy level."""

    fields: Mapping[str, str] = field(default_factory=dict)
    resources: Mapping[str, MaterialResourceBinding] = field(default_factory=dict)
    derivations: Mapping[str, MaterialDerivationSpec] = field(default_factory=dict)
    timelines: Mapping[str, MaterialTimelineSpec] = field(default_factory=dict)
    provenance: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "fields",
            _freeze_text_mapping(self.fields, path="scope.fields"),
        )
        object.__setattr__(
            self,
            "resources",
            _freeze_resource_mapping(self.resources),
        )
        object.__setattr__(
            self,
            "derivations",
            _freeze_spec_mapping(
                self.derivations,
                MaterialDerivationSpec,
                path="scope.derivations",
            ),
        )
        object.__setattr__(
            self,
            "timelines",
            _freeze_spec_mapping(
                self.timelines,
                MaterialTimelineSpec,
                path="scope.timelines",
            ),
        )
        object.__setattr__(
            self,
            "provenance",
            _freeze_text_mapping(self.provenance, path="scope.provenance"),
        )
        unknown_provenance = sorted(set(self.provenance) - set(self.fields))
        if unknown_provenance:
            raise ValueError(
                "material_scope_provenance_field_unknown:"
                + ",".join(unknown_provenance)
            )


@dataclass(frozen=True, slots=True)
class MaterialGroup:
    group_id: str
    display_name: str
    scope: MaterialScope = field(default_factory=MaterialScope)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_identity(self.group_id, _GROUP_ID_PATTERN, "group_id")
        _require_text(self.display_name, "material_group.display_name")
        if not isinstance(self.scope, MaterialScope):
            raise TypeError("material_group_scope_type_invalid")
        object.__setattr__(
            self,
            "metadata",
            _freeze_json_object(self.metadata, path="material_group.metadata"),
        )


@dataclass(frozen=True, slots=True)
class MaterialRecord:
    record_id: str
    display_name: str
    group_id: str = ""
    lifecycle: MaterialLifecycle = "draft"
    scope: MaterialScope = field(default_factory=MaterialScope)
    origin: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_identity(self.record_id, _RECORD_ID_PATTERN, "record_id")
        _require_text(self.display_name, "material_record.display_name")
        if type(self.group_id) is not str:
            raise TypeError("material_record_group_id_type_invalid")
        if self.group_id:
            _require_identity(self.group_id, _GROUP_ID_PATTERN, "group_id")
        if self.lifecycle not in MATERIAL_RECORD_LIFECYCLES:
            raise ValueError(
                f"material_record_lifecycle_invalid:{self.lifecycle}"
            )
        if not isinstance(self.scope, MaterialScope):
            raise TypeError("material_record_scope_type_invalid")
        object.__setattr__(
            self,
            "origin",
            _freeze_json_object(self.origin, path="material_record.origin"),
        )


@dataclass(frozen=True, slots=True)
class MaterialPackage:
    package_id: str
    display_name: str
    work_mode_id: str
    material_contract_id: str
    shared_scope: MaterialScope = field(default_factory=MaterialScope)
    groups: tuple[MaterialGroup, ...] = ()
    records: tuple[MaterialRecord, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    kind: str = MATERIAL_PACKAGE_KIND
    schema_version: int = MATERIAL_PACKAGE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_identity(self.package_id, _PACKAGE_ID_PATTERN, "package_id")
        _require_text(self.display_name, "material_package.display_name")
        _require_key(self.work_mode_id, "material_package.work_mode_id")
        _require_key(
            self.material_contract_id,
            "material_package.material_contract_id",
        )
        if self.kind != MATERIAL_PACKAGE_KIND:
            raise ValueError(f"material_package_kind_invalid:{self.kind}")
        if (
            type(self.schema_version) is not int
            or self.schema_version != MATERIAL_PACKAGE_SCHEMA_VERSION
        ):
            raise ValueError(
                "material_package_schema_version_unsupported:"
                f"{self.schema_version}"
            )
        if not isinstance(self.shared_scope, MaterialScope):
            raise TypeError("material_package_shared_scope_type_invalid")
        if type(self.groups) is not tuple:
            raise TypeError("material_package_groups_must_be_tuple")
        if type(self.records) is not tuple:
            raise TypeError("material_package_records_must_be_tuple")
        if len(self.groups) > MAX_PACKAGE_GROUP_COUNT:
            raise ValueError("material_package_groups_limit_exceeded")
        if len(self.records) > MAX_PACKAGE_RECORD_COUNT:
            raise ValueError("material_package_records_limit_exceeded")
        object.__setattr__(
            self,
            "metadata",
            _freeze_json_object(self.metadata, path="material_package.metadata"),
        )
        group_ids: set[str] = set()
        for group in self.groups:
            if not isinstance(group, MaterialGroup):
                raise TypeError("material_package_group_type_invalid")
            if group.group_id in group_ids:
                raise ValueError(
                    f"material_package_group_duplicate:{group.group_id}"
                )
            group_ids.add(group.group_id)
        record_ids: set[str] = set()
        for record in self.records:
            if not isinstance(record, MaterialRecord):
                raise TypeError("material_package_record_type_invalid")
            if record.record_id in record_ids:
                raise ValueError(
                    f"material_package_record_duplicate:{record.record_id}"
                )
            if record.group_id and record.group_id not in group_ids:
                raise ValueError(
                    "material_package_record_group_unknown:"
                    f"{record.record_id}:{record.group_id}"
                )
            record_ids.add(record.record_id)

    def get_group(self, group_id: str) -> MaterialGroup | None:
        return next(
            (item for item in self.groups if item.group_id == group_id),
            None,
        )

    def get_record(self, record_id: str) -> MaterialRecord | None:
        return next(
            (item for item in self.records if item.record_id == record_id),
            None,
        )

    def active_records(self) -> tuple[MaterialRecord, ...]:
        return tuple(
            item for item in self.records if item.lifecycle == "active"
        )


@dataclass(frozen=True, slots=True)
class MaterialPackageRef:
    package_id: str
    revision: str

    def __post_init__(self) -> None:
        _require_identity(self.package_id, _PACKAGE_ID_PATTERN, "package_id")
        if (
            type(self.revision) is not str
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", self.revision)
        ):
            raise ValueError("material_package_revision_invalid")


@dataclass(frozen=True, slots=True)
class MaterialRunSelection:
    package_ref: MaterialPackageRef
    selected_record_ids: tuple[str, ...]
    runtime_field_overrides: Mapping[str, str] = field(default_factory=dict)
    runtime_resource_overrides: Mapping[
        str, MaterialResourceBinding
    ] = field(default_factory=dict)
    runtime_image_watermark_text: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.package_ref, MaterialPackageRef):
            raise TypeError("material_run_package_ref_type_invalid")
        if type(self.selected_record_ids) is not tuple:
            raise TypeError("material_run_selected_record_ids_must_be_tuple")
        if type(self.runtime_image_watermark_text) is not str:
            raise TypeError("material_run_image_watermark_text_must_be_string")
        seen: set[str] = set()
        for record_id in self.selected_record_ids:
            _require_identity(record_id, _RECORD_ID_PATTERN, "record_id")
            if record_id in seen:
                raise ValueError(
                    f"material_run_record_duplicate:{record_id}"
                )
            seen.add(record_id)
        object.__setattr__(
            self,
            "runtime_field_overrides",
            _freeze_text_mapping(
                self.runtime_field_overrides,
                path="material_run.runtime_field_overrides",
            ),
        )
        object.__setattr__(
            self,
            "runtime_resource_overrides",
            _freeze_resource_mapping(self.runtime_resource_overrides),
        )


def clone_material_record(
    record: MaterialRecord,
    **changes: object,
) -> MaterialRecord:
    payload = {
        item.name: getattr(record, item.name)
        for item in dataclass_fields(MaterialRecord)
    }
    unknown = sorted(set(changes) - set(payload))
    if unknown:
        raise TypeError(f"Unknown MaterialRecord fields: {', '.join(unknown)}")
    payload.update(changes)
    return MaterialRecord(**payload)


def clone_material_package(
    package: MaterialPackage,
    **changes: object,
) -> MaterialPackage:
    payload = {
        item.name: getattr(package, item.name)
        for item in dataclass_fields(MaterialPackage)
    }
    unknown = sorted(set(changes) - set(payload))
    if unknown:
        raise TypeError(f"Unknown MaterialPackage fields: {', '.join(unknown)}")
    payload.update(changes)
    return MaterialPackage(**payload)


def _require_identity(
    value: object,
    pattern: re.Pattern[str],
    label: str,
) -> None:
    if type(value) is not str or not pattern.fullmatch(value):
        raise ValueError(f"material_package_{label}_invalid")


def _require_text(value: object, label: str) -> None:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or len(value) > MAX_DISPLAY_TEXT_LENGTH
    ):
        raise ValueError(f"{label}_invalid")


def _require_exact_text(value: object, label: str) -> None:
    if (
        type(value) is not str
        or value != value.strip()
        or len(value) > MAX_FIELD_VALUE_LENGTH
    ):
        raise ValueError(f"{label}_invalid")


def _require_key(value: object, label: str) -> None:
    _require_text(value, label)
    if (
        len(value) > MAX_FIELD_KEY_LENGTH
        or any(ord(char) < 32 for char in value)
    ):
        raise ValueError(f"{label}_invalid")


def _freeze_text_mapping(
    value: Mapping[str, str],
    *,
    path: str,
) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{path}_must_be_mapping")
    if len(value) > MAX_SCOPE_FIELD_COUNT:
        raise ValueError(f"{path}_limit_exceeded")
    result: dict[str, str] = {}
    for key, item in value.items():
        _require_key(key, f"{path}.key")
        if type(item) is not str:
            raise TypeError(f"{path}.{key}_must_be_string")
        if len(item) > MAX_FIELD_VALUE_LENGTH:
            raise ValueError(f"{path}.{key}_value_too_long")
        if key in result:
            raise ValueError(f"{path}_duplicate:{key}")
        result[key] = item
    return MappingProxyType(result)


def _freeze_resource_mapping(
    value: Mapping[str, MaterialResourceBinding],
) -> Mapping[str, MaterialResourceBinding]:
    if not isinstance(value, Mapping):
        raise TypeError("scope.resources_must_be_mapping")
    if len(value) > MAX_SCOPE_RESOURCE_ROLE_COUNT:
        raise ValueError("scope.resources_limit_exceeded")
    result: dict[str, MaterialResourceBinding] = {}
    for role, binding in value.items():
        _require_key(role, "scope.resources.role")
        if not isinstance(binding, MaterialResourceBinding):
            raise TypeError(f"scope.resources.{role}_type_invalid")
        if binding.role != role:
            raise ValueError(
                f"material_resource_role_mismatch:{role}:{binding.role}"
            )
        result[role] = binding
    return MappingProxyType(result)


def _freeze_spec_mapping(
    value: Mapping[str, object],
    expected_type: type,
    *,
    path: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{path}_must_be_mapping")
    result: dict[str, object] = {}
    for key, item in value.items():
        _require_key(key, f"{path}.key")
        if not isinstance(item, expected_type):
            raise TypeError(f"{path}_item_type_invalid:{key}")
        if item.output_field != key:
            raise ValueError(f"{path}_key_output_mismatch:{key}")
        result[key] = item
    return MappingProxyType(result)


def _freeze_json_mapping(
    value: Mapping[str, Mapping[str, Any]],
    *,
    path: str,
) -> Mapping[str, Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{path}_must_be_mapping")
    result: dict[str, Mapping[str, Any]] = {}
    for key, item in value.items():
        _require_key(key, f"{path}.key")
        if not isinstance(item, Mapping):
            raise TypeError(f"{path}.{key}_must_be_mapping")
        result[key] = _freeze_json_object(item, path=f"{path}.{key}")
    return MappingProxyType(result)


def _freeze_json_object(
    value: Mapping[str, Any],
    *,
    path: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{path}_must_be_mapping")
    copied = copy.deepcopy(dict(value))
    try:
        encoded = json.dumps(
            copied,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path}_not_json") from exc
    if len(encoded.encode("utf-8")) > MAX_METADATA_BYTES:
        raise ValueError(f"{path}_too_large")
    decoded = json.loads(encoded)
    if not isinstance(decoded, dict):
        raise TypeError(f"{path}_must_be_object")
    return MappingProxyType(decoded)
