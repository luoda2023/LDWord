"""Layered material-package contract used by package-driven generation.

The legacy :class:`EntityArchive` contract intentionally remains available to
the document-driven batch feature.  Version 6 is the package-driven model: it
stores package values once, introduces stable groups, and persists record
lifecycle independently from a one-off run selection.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from src.config.atomic_io import atomic_write_text
from src.config.entity import EntityArchive, EntityProfile, load_entity_archive
from src.config.entity_archive_codec import (
    _profile_payload,
    _resolve_profile_asset_paths,
)
from src.config.entity_archive_validation import (
    first_payload_difference,
    validate_entity_archive_wire_payload,
)


MATERIAL_PACKAGE_VERSION = 6
MATERIAL_PACKAGE_KIND = "alavette.material_package"
MATERIAL_RECORD_STATES = frozenset({"draft", "active", "disabled", "archived"})

_ROUTE_FIELDS = (
    "产品名称",
    "product_name",
    "product",
    "产品类型",
    "product_type",
    "路线",
    "route",
)


@dataclass(slots=True)
class MaterialValueScope:
    """Values and calculations owned by one package hierarchy level."""

    fields: dict[str, str] = field(default_factory=dict)
    field_aliases: dict[str, str] = field(default_factory=dict)
    field_functions: dict[str, dict[str, str]] = field(default_factory=dict)
    timeline_plans: dict[str, dict[str, Any]] = field(default_factory=dict)
    field_sources: dict[str, str] = field(default_factory=dict)
    override_fields: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.fields = _text_mapping(self.fields)
        self.field_aliases = _text_mapping(self.field_aliases)
        self.field_functions = _nested_mapping(self.field_functions)
        self.timeline_plans = _nested_mapping(self.timeline_plans)
        self.field_sources = _text_mapping(self.field_sources)
        self.override_fields = list(
            dict.fromkeys(
                value
                for item in self.override_fields
                if (value := str(item or "").strip())
            )
        )


@dataclass(slots=True)
class MaterialGroup:
    """Stable product/route group inside one material package."""

    group_id: str
    group_name: str
    route_id: str = ""
    values: MaterialValueScope = field(default_factory=MaterialValueScope)
    source_locator: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.group_id = _required_identity(self.group_id, "group_id")
        self.group_name = str(self.group_name or "").strip() or self.group_id
        self.route_id = str(self.route_id or "").strip() or self.group_name
        self.source_locator = _json_mapping(self.source_locator)


@dataclass(slots=True)
class MaterialRecord:
    """One candidate generation record and its persisted lifecycle."""

    record_id: str
    record_name: str
    group_id: str = ""
    lifecycle_state: str = "draft"
    values: MaterialValueScope = field(default_factory=MaterialValueScope)
    profile: EntityProfile = field(default_factory=EntityProfile)
    source_locator: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.record_id = _required_identity(self.record_id, "record_id")
        self.record_name = str(self.record_name or "").strip() or self.record_id
        self.group_id = str(self.group_id or "").strip()
        state = str(self.lifecycle_state or "").strip().lower()
        if state not in MATERIAL_RECORD_STATES:
            raise ValueError(f"material_record_lifecycle_invalid:{state}")
        self.lifecycle_state = state
        self.source_locator = _json_mapping(self.source_locator)
        if not isinstance(self.profile, EntityProfile):
            raise TypeError("material record profile must be EntityProfile")
        self.profile.profile_id = self.record_id
        self.profile.profile_name = self.record_name
        if not self.values.fields and self.profile.fields:
            self.values = _scope_from_profile(self.profile)
        else:
            _apply_scope_to_profile(self.values, self.profile)


@dataclass(slots=True)
class MaterialPackageV6:
    """Hierarchical package with package, group, and record value scopes."""

    package_id: str
    package_name: str
    shared_scope: MaterialValueScope = field(default_factory=MaterialValueScope)
    groups: list[MaterialGroup] = field(default_factory=list)
    records: list[MaterialRecord] = field(default_factory=list)
    mode_id: str = ""
    material_schema_ids: list[str] = field(default_factory=list)
    kind: str = MATERIAL_PACKAGE_KIND
    version: int = MATERIAL_PACKAGE_VERSION
    source_path: str = field(default="", repr=False, compare=False)

    def __post_init__(self) -> None:
        self.package_id = _required_identity(self.package_id, "package_id")
        self.package_name = str(self.package_name or "").strip() or self.package_id
        if self.kind != MATERIAL_PACKAGE_KIND:
            raise ValueError(f"material_package_kind_invalid:{self.kind}")
        if type(self.version) is not int or self.version != MATERIAL_PACKAGE_VERSION:
            raise ValueError(f"material_package_version_unsupported:{self.version}")
        self.mode_id = str(self.mode_id or "").strip()
        self.material_schema_ids = list(
            dict.fromkeys(
                value
                for item in self.material_schema_ids
                if (value := str(item or "").strip())
            )
        )
        group_ids: set[str] = set()
        for group in self.groups:
            if group.group_id in group_ids:
                raise ValueError(f"material_package_group_duplicate:{group.group_id}")
            group_ids.add(group.group_id)
        record_ids: set[str] = set()
        for record in self.records:
            if record.record_id in record_ids:
                raise ValueError(f"material_package_record_duplicate:{record.record_id}")
            if record.group_id and record.group_id not in group_ids:
                raise ValueError(
                    f"material_package_record_group_unknown:"
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

    def active_records(self) -> list[MaterialRecord]:
        return [
            item for item in self.records if item.lifecycle_state == "active"
        ]

    def to_entity_archive(self) -> EntityArchive:
        """Return a lossless legacy execution adapter for existing consumers."""

        profiles: list[EntityProfile] = []
        for record in self.records:
            profile = copy.deepcopy(record.profile)
            group = self.get_group(record.group_id) if record.group_id else None
            scopes = [
                self.shared_scope,
                *((group.values,) if group is not None else ()),
                record.values,
            ]
            profile.fields = {
                key: value
                for scope in scopes
                for key, value in scope.fields.items()
            }
            profile.field_aliases = {
                key: value
                for scope in scopes
                for key, value in scope.field_aliases.items()
            }
            profile.field_functions = {
                key: copy.deepcopy(value)
                for scope in scopes
                for key, value in scope.field_functions.items()
            }
            profile.timeline_plans = {
                key: copy.deepcopy(value)
                for scope in scopes
                for key, value in scope.timeline_plans.items()
            }
            profile.field_sources = {
                key: value
                for scope in scopes
                for key, value in scope.field_sources.items()
            }
            profile.declared_field_keys = list(
                dict.fromkeys(
                    (*profile.declared_field_keys, *profile.fields)
                )
            )
            profiles.append(profile)
        return EntityArchive(
            archive_id=self.package_id,
            archive_name=self.package_name,
            profiles=profiles,
            mode_id=self.mode_id,
            package_id=self.package_id,
            material_schema_ids=list(self.material_schema_ids),
            source_path=self.source_path,
        )


@dataclass(frozen=True, slots=True)
class MaterialPackageMigrationReport:
    source_path: str
    target_path: str
    report_path: str
    source_version: int
    target_version: int
    group_count: int
    record_count: int
    warnings: tuple[str, ...] = ()


def material_package_v6_from_archive(
    archive: EntityArchive,
    *,
    source_path: str | Path | None = None,
) -> MaterialPackageV6:
    """Explicitly adapt a flat v5 archive to the layered v6 model."""

    groups: list[MaterialGroup] = []
    group_by_route: dict[str, str] = {}
    records: list[MaterialRecord] = []
    used_group_ids: set[str] = set()
    used_record_ids: set[str] = set()
    for index, profile in enumerate(archive.profiles, start=1):
        route = _first_value(profile.fields, _ROUTE_FIELDS)
        group_id = ""
        if route:
            route_key = route.casefold()
            group_id = group_by_route.get(route_key, "")
            if not group_id:
                group_id = _stable_identity("group", route, used_group_ids)
                used_group_ids.add(group_id)
                group_by_route[route_key] = group_id
                groups.append(
                    MaterialGroup(
                        group_id=group_id,
                        group_name=route,
                        route_id=route,
                        values=MaterialValueScope(fields={"产品名称": route}),
                    )
                )
        record_id = str(profile.profile_id or "").strip()
        if not record_id or record_id in used_record_ids:
            record_id = _stable_identity(
                "record",
                f"{profile.profile_name}:{index}",
                used_record_ids,
            )
        used_record_ids.add(record_id)
        record_name = (
            _first_value(
                profile.fields,
                ("项目名称", "project_name", "entity_name"),
            )
            or profile.profile_name
            or record_id
        )
        record_profile = copy.deepcopy(profile)
        record_profile.profile_id = record_id
        record_profile.profile_name = record_name
        records.append(
            MaterialRecord(
                record_id=record_id,
                record_name=record_name,
                group_id=group_id,
                lifecycle_state="active",
                values=_scope_from_profile(record_profile),
                profile=record_profile,
                source_locator={"legacy_profile_index": index - 1},
            )
        )
    return MaterialPackageV6(
        package_id=(
            str(archive.package_id or archive.archive_id or "").strip()
            or "material-package"
        ),
        package_name=archive.archive_name or archive.archive_id or "资料包",
        groups=groups,
        records=records,
        mode_id=archive.mode_id,
        material_schema_ids=list(archive.material_schema_ids),
        source_path=str(source_path or archive.source_path or ""),
    )


def synchronize_material_package_from_archive(
    package: MaterialPackageV6,
    archive: EntityArchive,
) -> MaterialPackageV6:
    """Apply legacy-editor profile changes without flattening shared/group data."""

    result = copy.deepcopy(package)
    existing = {item.record_id: item for item in result.records}
    refreshed: list[MaterialRecord] = []
    used_ids: set[str] = set()
    for index, profile in enumerate(archive.profiles, start=1):
        record_id = str(profile.profile_id or "").strip()
        if not record_id or record_id in used_ids:
            record_id = _stable_identity(
                "record",
                f"{profile.profile_name}:{index}",
                used_ids,
            )
        used_ids.add(record_id)
        previous = existing.get(record_id)
        record_name = (
            _first_value(
                profile.fields,
                ("项目名称", "project_name", "entity_name"),
            )
            or profile.profile_name
            or record_id
        )
        group_id = previous.group_id if previous is not None else ""
        group = result.get_group(group_id) if group_id else None
        values = _scope_from_profile(profile)
        inherited_scopes = [
            result.shared_scope,
            *((group.values,) if group is not None else ()),
        ]
        _remove_inherited_equal_values(values, inherited_scopes)
        profile_copy = copy.deepcopy(profile)
        profile_copy.profile_id = record_id
        profile_copy.profile_name = record_name
        refreshed.append(
            MaterialRecord(
                record_id=record_id,
                record_name=record_name,
                group_id=group_id,
                lifecycle_state=(
                    previous.lifecycle_state if previous is not None else "active"
                ),
                values=values,
                profile=profile_copy,
                source_locator=(
                    copy.deepcopy(previous.source_locator)
                    if previous is not None
                    else {"legacy_profile_index": index - 1}
                ),
            )
        )
    result.records = refreshed
    result.package_name = archive.archive_name or result.package_name
    result.mode_id = archive.mode_id or result.mode_id
    result.material_schema_ids = list(
        archive.material_schema_ids or result.material_schema_ids
    )
    result.source_path = archive.source_path or result.source_path
    result.__post_init__()
    return result


def save_material_package_v6(
    package: MaterialPackageV6,
    path: str | Path,
) -> None:
    target = Path(path)
    payload = _package_payload(package, target)
    _validate_package_payload(payload, target)
    atomic_write_text(
        target,
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def load_material_package_v6(path: str | Path) -> MaterialPackageV6:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("material_package_root_type_invalid:object_required")
    version = payload.get("version", 0)
    if type(version) is not int:
        raise ValueError("material_package_version_invalid")
    if version != MATERIAL_PACKAGE_VERSION:
        raise ValueError(f"material_package_version_unsupported:{version}")
    _validate_package_payload(payload, source)
    shared_scope = _scope_from_payload(payload["shared_scope"])
    groups = [
        MaterialGroup(
            group_id=item["group_id"],
            group_name=item["group_name"],
            route_id=item["route_id"],
            values=_scope_from_payload(item["values"]),
            source_locator=copy.deepcopy(item["source_locator"]),
        )
        for item in payload["groups"]
    ]
    records: list[MaterialRecord] = []
    for item in payload["records"]:
        profile_data = copy.deepcopy(item["profile"])
        _resolve_profile_asset_paths(profile_data, source.parent)
        profile = EntityProfile(**profile_data)
        canonical = _profile_payload(profile, source.parent)
        difference = first_payload_difference(item["profile"], canonical)
        if difference:
            raise ValueError(
                "material_package_record_profile_not_canonical:"
                f"{item['record_id']}:{difference}"
            )
        records.append(
            MaterialRecord(
                record_id=item["record_id"],
                record_name=item["record_name"],
                group_id=item["group_id"],
                lifecycle_state=item["lifecycle_state"],
                values=_scope_from_payload(item["values"]),
                profile=profile,
                source_locator=copy.deepcopy(item["source_locator"]),
            )
        )
    return MaterialPackageV6(
        package_id=payload["package_id"],
        package_name=payload["package_name"],
        shared_scope=shared_scope,
        groups=groups,
        records=records,
        mode_id=payload["mode_id"],
        material_schema_ids=list(payload["material_schema_ids"]),
        source_path=str(source.resolve()),
    )


def migrate_entity_archive_to_v6(
    source_path: str | Path,
    target_path: str | Path,
) -> MaterialPackageMigrationReport:
    """Migrate without replacing the source and emit a machine-readable report."""

    source = Path(source_path)
    target = Path(target_path)
    report_path = target.with_name(f"{target.stem}.migration.json")
    if target.exists():
        raise FileExistsError(f"migration target already exists: {target}")
    if report_path.exists():
        raise FileExistsError(f"migration report already exists: {report_path}")
    archive = load_entity_archive(source)
    package = material_package_v6_from_archive(archive, source_path=source)
    save_material_package_v6(package, target)
    warnings = (
        "v5 没有共享层来源信息；迁移未自动提升重复字段到资料包共享层。",
    )
    report_payload = {
        "kind": "alavette.material_package_migration_report",
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source.resolve()),
        "target_path": str(target.resolve()),
        "source_version": 5,
        "target_version": MATERIAL_PACKAGE_VERSION,
        "group_count": len(package.groups),
        "record_count": len(package.records),
        "warnings": list(warnings),
    }
    atomic_write_text(
        report_path,
        json.dumps(report_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return MaterialPackageMigrationReport(
        source_path=str(source.resolve()),
        target_path=str(target.resolve()),
        report_path=str(report_path.resolve()),
        source_version=5,
        target_version=MATERIAL_PACKAGE_VERSION,
        group_count=len(package.groups),
        record_count=len(package.records),
        warnings=warnings,
    )


def load_material_package_any(path: str | Path) -> MaterialPackageV6:
    """Load v6 directly or adapt a strict v5 package in memory."""

    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("material_package_root_type_invalid:object_required")
    version = payload.get("version", 0)
    if version == MATERIAL_PACKAGE_VERSION:
        return load_material_package_v6(source)
    if version == 5:
        return material_package_v6_from_archive(
            load_entity_archive(source),
            source_path=source,
        )
    raise ValueError(f"material_package_version_unsupported:{version}")


def _package_payload(
    package: MaterialPackageV6,
    target: Path,
) -> dict[str, object]:
    return {
        "kind": package.kind,
        "version": package.version,
        "package_id": package.package_id,
        "package_name": package.package_name,
        "mode_id": package.mode_id,
        "material_schema_ids": list(package.material_schema_ids),
        "shared_scope": _scope_payload(package.shared_scope),
        "groups": [
            {
                "group_id": item.group_id,
                "group_name": item.group_name,
                "route_id": item.route_id,
                "values": _scope_payload(item.values),
                "source_locator": copy.deepcopy(item.source_locator),
            }
            for item in package.groups
        ],
        "records": [
            {
                "record_id": item.record_id,
                "record_name": item.record_name,
                "group_id": item.group_id,
                "lifecycle_state": item.lifecycle_state,
                "values": _scope_payload(item.values),
                "source_locator": copy.deepcopy(item.source_locator),
                "profile": _profile_payload(item.profile, target.parent),
            }
            for item in package.records
        ],
    }


def _validate_package_payload(
    payload: Mapping[str, object],
    target: Path,
) -> None:
    expected_root = {
        "kind",
        "version",
        "package_id",
        "package_name",
        "mode_id",
        "material_schema_ids",
        "shared_scope",
        "groups",
        "records",
    }
    _require_exact_keys(payload, expected_root, "material_package_v6")
    if payload["kind"] != MATERIAL_PACKAGE_KIND:
        raise ValueError(f"material_package_kind_invalid:{payload['kind']}")
    if payload["version"] != MATERIAL_PACKAGE_VERSION:
        raise ValueError(
            f"material_package_version_unsupported:{payload['version']}"
        )
    _required_identity(payload["package_id"], "package_id")
    if type(payload["package_name"]) is not str:
        raise ValueError("material_package_v6_field_type_invalid:package_name")
    if type(payload["mode_id"]) is not str:
        raise ValueError("material_package_v6_field_type_invalid:mode_id")
    if type(payload["material_schema_ids"]) is not list or not all(
        type(item) is str for item in payload["material_schema_ids"]
    ):
        raise ValueError(
            "material_package_v6_field_type_invalid:material_schema_ids"
        )
    _validate_scope_payload(payload["shared_scope"], "shared_scope")
    groups = payload["groups"]
    records = payload["records"]
    if type(groups) is not list:
        raise ValueError("material_package_v6_field_type_invalid:groups")
    if type(records) is not list:
        raise ValueError("material_package_v6_field_type_invalid:records")
    group_ids: set[str] = set()
    for index, item in enumerate(groups):
        if type(item) is not dict:
            raise ValueError(
                f"material_package_v6_field_type_invalid:groups[{index}]"
            )
        _require_exact_keys(
            item,
            {"group_id", "group_name", "route_id", "values", "source_locator"},
            f"groups[{index}]",
        )
        group_id = _required_identity(item["group_id"], "group_id")
        if group_id in group_ids:
            raise ValueError(f"material_package_group_duplicate:{group_id}")
        group_ids.add(group_id)
        for key in ("group_name", "route_id"):
            if type(item[key]) is not str:
                raise ValueError(
                    f"material_package_v6_field_type_invalid:groups[{index}].{key}"
                )
        _validate_scope_payload(item["values"], f"groups[{index}].values")
        _validate_source_locator(
            item["source_locator"],
            f"groups[{index}].source_locator",
        )
    fake_profiles: list[object] = []
    record_ids: set[str] = set()
    for index, item in enumerate(records):
        if type(item) is not dict:
            raise ValueError(
                f"material_package_v6_field_type_invalid:records[{index}]"
            )
        _require_exact_keys(
            item,
            {
                "record_id",
                "record_name",
                "group_id",
                "lifecycle_state",
                "values",
                "source_locator",
                "profile",
            },
            f"records[{index}]",
        )
        record_id = _required_identity(item["record_id"], "record_id")
        if record_id in record_ids:
            raise ValueError(f"material_package_record_duplicate:{record_id}")
        record_ids.add(record_id)
        if type(item["record_name"]) is not str:
            raise ValueError(
                f"material_package_v6_field_type_invalid:records[{index}].record_name"
            )
        group_id = item["group_id"]
        if type(group_id) is not str or (group_id and group_id not in group_ids):
            raise ValueError(
                f"material_package_record_group_unknown:{record_id}:{group_id}"
            )
        if item["lifecycle_state"] not in MATERIAL_RECORD_STATES:
            raise ValueError(
                f"material_record_lifecycle_invalid:{item['lifecycle_state']}"
            )
        _validate_scope_payload(item["values"], f"records[{index}].values")
        _validate_source_locator(
            item["source_locator"],
            f"records[{index}].source_locator",
        )
        if type(item["profile"]) is not dict:
            raise ValueError(
                f"material_package_v6_field_type_invalid:records[{index}].profile"
            )
        fake_profiles.append(item["profile"])
    # Reuse the mature strict nested profile validator rather than creating a
    # second, drifting contract for assets, content and attachments.
    validate_entity_archive_wire_payload(
        {
            "kind": MATERIAL_PACKAGE_KIND,
            "version": 5,
            "mode_id": payload["mode_id"],
            "package_id": payload["package_id"],
            "material_schema_ids": payload["material_schema_ids"],
            "archive_id": payload["package_id"],
            "archive_name": payload["package_name"],
            "profiles": fake_profiles,
        }
    )
    for index, raw_profile in enumerate(fake_profiles):
        profile_data = copy.deepcopy(raw_profile)
        _resolve_profile_asset_paths(profile_data, target.parent)
        canonical = _profile_payload(EntityProfile(**profile_data), target.parent)
        difference = first_payload_difference(raw_profile, canonical)
        if difference:
            raise ValueError(
                "material_package_record_profile_not_canonical:"
                f"{index}:{difference}"
            )


_SCOPE_KEYS = {
    "fields",
    "field_aliases",
    "field_functions",
    "timeline_plans",
    "field_sources",
    "override_fields",
}


def _scope_payload(scope: MaterialValueScope) -> dict[str, object]:
    return {
        "fields": dict(scope.fields),
        "field_aliases": dict(scope.field_aliases),
        "field_functions": copy.deepcopy(scope.field_functions),
        "timeline_plans": copy.deepcopy(scope.timeline_plans),
        "field_sources": dict(scope.field_sources),
        "override_fields": list(scope.override_fields),
    }


def _scope_from_payload(payload: object) -> MaterialValueScope:
    if not isinstance(payload, Mapping):
        raise ValueError("material_package_v6_scope_invalid")
    return MaterialValueScope(
        fields=dict(payload["fields"]),
        field_aliases=dict(payload["field_aliases"]),
        field_functions=copy.deepcopy(payload["field_functions"]),
        timeline_plans=copy.deepcopy(payload["timeline_plans"]),
        field_sources=dict(payload["field_sources"]),
        override_fields=list(payload["override_fields"]),
    )


def _validate_scope_payload(payload: object, path: str) -> None:
    if type(payload) is not dict:
        raise ValueError(f"material_package_v6_field_type_invalid:{path}")
    _require_exact_keys(payload, _SCOPE_KEYS, path)
    for key in ("fields", "field_aliases", "field_sources"):
        value = payload[key]
        if type(value) is not dict or not all(
            type(item_key) is str and type(item_value) is str
            for item_key, item_value in value.items()
        ):
            raise ValueError(
                f"material_package_v6_field_type_invalid:{path}.{key}"
            )
    for key in ("field_functions", "timeline_plans"):
        if type(payload[key]) is not dict:
            raise ValueError(
                f"material_package_v6_field_type_invalid:{path}.{key}"
            )
    if type(payload["override_fields"]) is not list or not all(
        type(item) is str for item in payload["override_fields"]
    ):
        raise ValueError(
            f"material_package_v6_field_type_invalid:{path}.override_fields"
        )


def _scope_from_profile(profile: EntityProfile) -> MaterialValueScope:
    return MaterialValueScope(
        fields=dict(profile.fields),
        field_aliases=dict(profile.field_aliases),
        field_functions=copy.deepcopy(profile.field_functions),
        timeline_plans=copy.deepcopy(profile.timeline_plans),
        field_sources=dict(profile.field_sources),
    )


def _apply_scope_to_profile(
    scope: MaterialValueScope,
    profile: EntityProfile,
) -> None:
    profile.fields = dict(scope.fields)
    profile.field_aliases = dict(scope.field_aliases)
    profile.field_functions = copy.deepcopy(scope.field_functions)
    profile.timeline_plans = copy.deepcopy(scope.timeline_plans)
    profile.field_sources = dict(scope.field_sources)
    profile.declared_field_keys = list(
        dict.fromkeys((*profile.declared_field_keys, *scope.fields))
    )


def _remove_inherited_equal_values(
    scope: MaterialValueScope,
    inherited_scopes: list[MaterialValueScope],
) -> None:
    for inherited in inherited_scopes:
        for key, value in inherited.fields.items():
            if scope.fields.get(key) == value:
                scope.fields.pop(key, None)
                scope.field_sources.pop(key, None)
        for key, value in inherited.field_aliases.items():
            if scope.field_aliases.get(key) == value:
                scope.field_aliases.pop(key, None)
        for key, value in inherited.field_functions.items():
            if scope.field_functions.get(key) == value:
                scope.field_functions.pop(key, None)
        for key, value in inherited.timeline_plans.items():
            if scope.timeline_plans.get(key) == value:
                scope.timeline_plans.pop(key, None)


def _text_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key).strip(): str(item)
        for key, item in value.items()
        if str(key or "").strip()
    }


def _nested_mapping(value: object) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key).strip(): copy.deepcopy(dict(item))
        for key, item in value.items()
        if str(key or "").strip() and isinstance(item, Mapping)
    }


def _json_mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    payload = copy.deepcopy(dict(value))
    json.dumps(payload, ensure_ascii=False, allow_nan=False)
    return payload


def _validate_source_locator(value: object, path: str) -> None:
    if type(value) is not dict:
        raise ValueError(f"material_package_v6_field_type_invalid:{path}")
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"material_package_v6_source_locator_invalid:{path}"
        ) from exc


def _require_exact_keys(
    payload: Mapping[str, object],
    expected: set[str],
    path: str,
) -> None:
    missing = sorted(expected - set(payload))
    unknown = sorted(set(payload) - expected)
    if missing:
        raise ValueError(
            f"material_package_v6_fields_missing:{path}:{','.join(missing)}"
        )
    if unknown:
        raise ValueError(
            f"material_package_v6_fields_unknown:{path}:{','.join(unknown)}"
        )


def _required_identity(value: object, label: str) -> str:
    if type(value) is not str:
        raise ValueError(f"material_package_{label}_invalid")
    text = value.strip()
    forbidden = '<>:"/\\|?*'
    if (
        not text
        or text != value
        or text in {".", ".."}
        or text.endswith((".", " "))
        or any(char in forbidden or ord(char) < 32 for char in text)
    ):
        raise ValueError(f"material_package_{label}_invalid")
    return text


def _first_value(values: Mapping[str, str], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(values.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _stable_identity(prefix: str, seed: str, used: set[str]) -> str:
    slug = re.sub(r"[^0-9A-Za-z_-]+", "-", str(seed or "").strip()).strip("-")
    if not slug:
        slug = hashlib.sha1(str(seed).encode("utf-8")).hexdigest()[:10]
    candidate = f"{prefix}-{slug}"[:80]
    if candidate not in used:
        return candidate
    digest = hashlib.sha1(str(seed).encode("utf-8")).hexdigest()[:8]
    return f"{candidate[:70]}-{digest}"


__all__ = [
    "MATERIAL_PACKAGE_KIND",
    "MATERIAL_PACKAGE_VERSION",
    "MATERIAL_RECORD_STATES",
    "MaterialGroup",
    "MaterialPackageMigrationReport",
    "MaterialPackageV6",
    "MaterialRecord",
    "MaterialValueScope",
    "load_material_package_any",
    "load_material_package_v6",
    "material_package_v6_from_archive",
    "migrate_entity_archive_to_v6",
    "save_material_package_v6",
    "synchronize_material_package_from_archive",
]
