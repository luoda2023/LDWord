"""Revision-aware material editor commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.application.materials.contracts import (
    PACKAGE_CONTRACT_EXTENSIONS_KEY,
    get_package_material_contract,
)
from src.domain.materials import (
    MaterialDerivationSpec,
    MaterialGroup,
    MaterialIssue,
    MaterialPackage,
    MaterialRecord,
    MaterialResourceBinding,
    MaterialScope,
    MaterialTimelineSpec,
    clone_material_package,
    clone_material_record,
    generate_group_id,
    generate_record_id,
)
from src.infrastructure.materials.repository import (
    MaterialPackageRepository,
    MaterialPackageSnapshot,
)

OwnerScope = Literal["shared", "group", "record"]
RESOURCE_AUTHORING_SOURCES_KEY = "material_resource_authoring_sources"


@dataclass(frozen=True, slots=True)
class MaterialCommandResult:
    package: MaterialPackage | None = None
    snapshot: MaterialPackageSnapshot | None = None
    issues: tuple[MaterialIssue, ...] = ()

    @property
    def ok(self) -> bool:
        return (
            (self.package is not None or self.snapshot is not None)
            and not any(item.severity == "error" for item in self.issues)
        )


class MaterialPackageService:
    def __init__(self, repository: MaterialPackageRepository) -> None:
        self._repository = repository

    def rename_package(
        self,
        package: MaterialPackage,
        *,
        display_name: str,
    ) -> MaterialCommandResult:
        return self._construct(
            lambda: clone_material_package(
                package,
                display_name=display_name,
            )
        )

    def add_group(
        self,
        package: MaterialPackage,
        *,
        display_name: str,
    ) -> MaterialCommandResult:
        return self._construct(
            lambda: clone_material_package(
                package,
                groups=(
                    *package.groups,
                    MaterialGroup(
                        group_id=generate_group_id(),
                        display_name=display_name,
                    ),
                ),
            )
        )

    def add_record(
        self,
        package: MaterialPackage,
        *,
        display_name: str,
        group_id: str = "",
        lifecycle: str = "draft",
    ) -> MaterialCommandResult:
        return self._construct(
            lambda: clone_material_package(
                package,
                records=(
                    *package.records,
                    MaterialRecord(
                        record_id=generate_record_id(),
                        display_name=display_name,
                        group_id=group_id,
                        lifecycle=lifecycle,
                    ),
                ),
            )
        )

    def remove_group(
        self,
        package: MaterialPackage,
        *,
        group_id: str,
    ) -> MaterialCommandResult:
        if package.get_group(group_id) is None:
            return self._not_found("group", group_id)
        if any(item.group_id == group_id for item in package.records):
            return MaterialCommandResult(
                issues=(
                    MaterialIssue(
                        code="material.group.not_empty",
                        path=f"groups.{group_id}",
                        message="分组仍包含资料记录，请先移动或删除这些记录。",
                    ),
                )
            )
        return self._construct(
            lambda: clone_material_package(
                package,
                groups=tuple(
                    item for item in package.groups if item.group_id != group_id
                ),
            )
        )

    def remove_record(
        self,
        package: MaterialPackage,
        *,
        record_id: str,
    ) -> MaterialCommandResult:
        if package.get_record(record_id) is None:
            return self._not_found("record", record_id)
        return self._construct(
            lambda: clone_material_package(
                package,
                records=tuple(
                    item
                    for item in package.records
                    if item.record_id != record_id
                ),
            )
        )

    def rename_group(
        self,
        package: MaterialPackage,
        *,
        group_id: str,
        display_name: str,
    ) -> MaterialCommandResult:
        target = package.get_group(group_id)
        if target is None:
            return self._not_found("group", group_id)
        replacement = MaterialGroup(
            group_id=target.group_id,
            display_name=display_name,
            scope=target.scope,
            metadata=target.metadata,
        )
        return self._construct(
            lambda: clone_material_package(
                package,
                groups=tuple(
                    replacement if item.group_id == group_id else item
                    for item in package.groups
                ),
            )
        )

    def rename_record(
        self,
        package: MaterialPackage,
        *,
        record_id: str,
        display_name: str,
    ) -> MaterialCommandResult:
        return self._replace_record(
            package,
            record_id=record_id,
            transform=lambda record: clone_material_record(
                record,
                display_name=display_name,
            ),
        )

    def move_record(
        self,
        package: MaterialPackage,
        *,
        record_id: str,
        group_id: str,
    ) -> MaterialCommandResult:
        if group_id and package.get_group(group_id) is None:
            return self._not_found("group", group_id)
        return self._replace_record(
            package,
            record_id=record_id,
            transform=lambda record: clone_material_record(
                record,
                group_id=group_id,
            ),
        )

    def set_record_lifecycle(
        self,
        package: MaterialPackage,
        *,
        record_id: str,
        lifecycle: str,
    ) -> MaterialCommandResult:
        return self._replace_record(
            package,
            record_id=record_id,
            transform=lambda record: clone_material_record(
                record,
                lifecycle=lifecycle,
            ),
        )

    def set_field(
        self,
        package: MaterialPackage,
        *,
        owner_scope: OwnerScope,
        owner_id: str,
        key: str,
        value: str,
        provenance: str = "",
    ) -> MaterialCommandResult:
        return self._replace_scope(
            package,
            owner_scope=owner_scope,
            owner_id=owner_id,
            transform=lambda scope: _scope_with_field(
                scope,
                key=key,
                value=value,
                provenance=provenance,
            ),
        )

    def remove_field(
        self,
        package: MaterialPackage,
        *,
        owner_scope: OwnerScope,
        owner_id: str,
        key: str,
    ) -> MaterialCommandResult:
        return self._replace_scope(
            package,
            owner_scope=owner_scope,
            owner_id=owner_id,
            transform=lambda scope: _scope_without_field(scope, key=key),
        )

    def add_field_definition(
        self,
        package: MaterialPackage,
        *,
        key: str,
        label: str,
        required: bool = False,
        value_source: str = "fixed",
    ) -> MaterialCommandResult:
        def construct() -> MaterialPackage:
            if get_package_material_contract(package).get_field(key) is not None:
                raise ValueError(f"material_field_definition_duplicate:{key}")
            normalized_source = str(value_source or "fixed").strip()
            if normalized_source not in {"fixed", "floating"}:
                raise ValueError(
                    f"material_field_value_source_invalid:{normalized_source}"
                )
            extensions = _package_extensions(package)
            extensions["fields"].append(
                {
                    "key": key,
                    "label": label,
                    "required": required,
                    "allowed_scopes": (
                        ["run"]
                        if normalized_source == "floating"
                        else ["shared", "group", "record", "run"]
                    ),
                    "value_source": normalized_source,
                }
            )
            return _package_with_extensions(package, extensions)

        return self._construct(construct)

    def rename_field_definition(
        self,
        package: MaterialPackage,
        *,
        current_key: str,
        key: str,
        label: str,
    ) -> MaterialCommandResult:
        def construct() -> MaterialPackage:
            contract = get_package_material_contract(package)
            if current_key != key and contract.get_field(key) is not None:
                raise ValueError(f"material_field_definition_duplicate:{key}")
            extensions = _package_extensions(package)
            target = next(
                (
                    item
                    for item in extensions["fields"]
                    if item.get("key") == current_key
                ),
                None,
            )
            if target is None:
                raise ValueError(
                    f"material_field_definition_not_custom:{current_key}"
                )
            target["key"] = key
            target["label"] = label
            migrated = _map_package_scopes(
                package,
                lambda scope: _scope_renamed_field(
                    scope,
                    current_key=current_key,
                    key=key,
                ),
            )
            return _package_with_extensions(migrated, extensions)

        return self._construct(construct)

    def remove_field_definition(
        self,
        package: MaterialPackage,
        *,
        key: str,
    ) -> MaterialCommandResult:
        def construct() -> MaterialPackage:
            extensions = _package_extensions(package)
            retained = [
                item for item in extensions["fields"] if item.get("key") != key
            ]
            if len(retained) == len(extensions["fields"]):
                raise ValueError(f"material_field_definition_not_custom:{key}")
            extensions["fields"] = retained
            cleaned = _map_package_scopes(
                package,
                lambda scope: _scope_without_field_definition(scope, key=key),
            )
            return _package_with_extensions(cleaned, extensions)

        return self._construct(construct)

    def add_resource_role_definition(
        self,
        package: MaterialPackage,
        *,
        role: str,
        label: str,
        domain: str,
        max_items: int | None = 1,
        source_kind: str = "file",
        recursive: bool = False,
    ) -> MaterialCommandResult:
        def construct() -> MaterialPackage:
            if (
                get_package_material_contract(package).get_resource_role(role)
                is not None
            ):
                raise ValueError(f"material_resource_definition_duplicate:{role}")
            extensions = _package_extensions(package)
            extensions["resource_roles"].append(
                {
                    "role": role,
                    "label": label,
                    "domain": domain,
                    "required": False,
                    "allowed_scopes": ["shared", "group", "record", "run"],
                    "merge_policy": "replace",
                    "min_items": 0,
                    "max_items": max_items,
                    "accepted_media_types": [],
                    "source_kind": source_kind,
                    "recursive": recursive,
                }
            )
            return _package_with_extensions(package, extensions)

        return self._construct(construct)

    def rename_resource_role_definition(
        self,
        package: MaterialPackage,
        *,
        current_role: str,
        role: str,
        label: str,
    ) -> MaterialCommandResult:
        def construct() -> MaterialPackage:
            contract = get_package_material_contract(package)
            if current_role != role and contract.get_resource_role(role) is not None:
                raise ValueError(f"material_resource_definition_duplicate:{role}")
            extensions = _package_extensions(package)
            target = next(
                (
                    item
                    for item in extensions["resource_roles"]
                    if item.get("role") == current_role
                ),
                None,
            )
            if target is None:
                raise ValueError(
                    f"material_resource_definition_not_custom:{current_role}"
                )
            target["role"] = role
            target["label"] = label
            migrated = _map_package_scopes(
                package,
                lambda scope: _scope_renamed_resource(
                    scope,
                    current_role=current_role,
                    role=role,
                ),
            )
            migrated = _rename_resource_authoring_source_role(
                migrated,
                current_role=current_role,
                role=role,
            )
            return _package_with_extensions(migrated, extensions)

        return self._construct(construct)

    def remove_resource_role_definition(
        self,
        package: MaterialPackage,
        *,
        role: str,
    ) -> MaterialCommandResult:
        def construct() -> MaterialPackage:
            extensions = _package_extensions(package)
            retained = [
                item
                for item in extensions["resource_roles"]
                if item.get("role") != role
            ]
            if len(retained) == len(extensions["resource_roles"]):
                raise ValueError(f"material_resource_definition_not_custom:{role}")
            extensions["resource_roles"] = retained
            cleaned = _map_package_scopes(
                package,
                lambda scope: _scope_without_resource(scope, role),
            )
            cleaned = _without_resource_authoring_source_role(cleaned, role)
            return _package_with_extensions(cleaned, extensions)

        return self._construct(construct)

    def set_image_policy(
        self,
        package: MaterialPackage,
        *,
        adaptive: bool,
        watermark_enabled: bool,
        watermark_source: str,
        watermark_text: str,
        watermark_font: str = "宋体",
        show_single_image_name: bool | None = None,
        show_multi_image_name: bool | None = None,
        page_break_after_images: bool = False,
        show_image_name: bool | None = None,
    ) -> MaterialCommandResult:
        def construct() -> MaterialPackage:
            legacy_show_image_name = bool(show_image_name)
            extensions = _package_extensions(package)
            extensions["image_policy"] = {
                "adaptive": bool(adaptive),
                "watermark_enabled": bool(watermark_enabled),
                "watermark_source": str(watermark_source),
                "watermark_text": str(watermark_text),
                "watermark_font": str(watermark_font or "宋体").strip() or "宋体",
                "show_single_image_name": (
                    legacy_show_image_name
                    if show_single_image_name is None
                    else bool(show_single_image_name)
                ),
                "show_multi_image_name": (
                    legacy_show_image_name
                    if show_multi_image_name is None
                    else bool(show_multi_image_name)
                ),
                "page_break_after_images": bool(page_break_after_images),
            }
            return _package_with_extensions(package, extensions)

        return self._construct(construct)

    def set_content_policy(
        self,
        package: MaterialPackage,
        *,
        format_mode: str,
        page_break_policy: str = "drop",
    ) -> MaterialCommandResult:
        """Persist package-wide file-content insertion behavior."""

        def construct() -> MaterialPackage:
            normalized_mode = str(format_mode or "target_document").strip()
            if normalized_mode not in {"target_document", "plain_text"}:
                raise ValueError(
                    f"material_content_format_mode_invalid:{normalized_mode}"
                )
            normalized_breaks = str(page_break_policy or "drop").strip()
            if normalized_breaks not in {"drop", "preserve_explicit"}:
                raise ValueError(
                    "material_content_page_break_policy_invalid:"
                    f"{normalized_breaks}"
                )
            extensions = _package_extensions(package)
            extensions["content_policy"] = {
                "format_mode": normalized_mode,
                "page_break_policy": normalized_breaks,
            }
            return _package_with_extensions(package, extensions)

        return self._construct(construct)

    def bind_resource(
        self,
        package: MaterialPackage,
        *,
        owner_scope: OwnerScope,
        owner_id: str,
        binding: MaterialResourceBinding,
    ) -> MaterialCommandResult:
        return self._replace_scope(
            package,
            owner_scope=owner_scope,
            owner_id=owner_id,
            transform=lambda scope: _scope_with_resource(scope, binding),
        )

    def set_resource_authoring_source(
        self,
        package: MaterialPackage,
        *,
        owner_scope: OwnerScope,
        owner_id: str,
        role: str,
        source_path: str,
    ) -> MaterialCommandResult:
        """Persist an editor-only source path without affecting execution."""

        def construct() -> MaterialPackage:
            metadata = dict(package.metadata)
            raw_sources = metadata.get(RESOURCE_AUTHORING_SOURCES_KEY, {})
            sources = {
                str(item_role): dict(scope_sources)
                for item_role, scope_sources in dict(raw_sources or {}).items()
                if hasattr(scope_sources, "items")
            }
            role_sources = dict(sources.get(role, {}))
            scope_key = f"{owner_scope}:{owner_id}"
            normalized_path = str(source_path or "").strip()
            if normalized_path:
                role_sources[scope_key] = normalized_path
            else:
                role_sources.pop(scope_key, None)
            if role_sources:
                sources[role] = role_sources
            else:
                sources.pop(role, None)
            if sources:
                metadata[RESOURCE_AUTHORING_SOURCES_KEY] = sources
            else:
                metadata.pop(RESOURCE_AUTHORING_SOURCES_KEY, None)
            return clone_material_package(package, metadata=metadata)

        return self._construct(construct)

    def remove_resource(
        self,
        package: MaterialPackage,
        *,
        owner_scope: OwnerScope,
        owner_id: str,
        role: str,
    ) -> MaterialCommandResult:
        return self._replace_scope(
            package,
            owner_scope=owner_scope,
            owner_id=owner_id,
            transform=lambda scope: _scope_without_resource(scope, role),
        )

    def set_derivation(
        self,
        package: MaterialPackage,
        *,
        owner_scope: OwnerScope,
        owner_id: str,
        key: str,
        specification: MaterialDerivationSpec,
    ) -> MaterialCommandResult:
        return self._replace_scope(
            package,
            owner_scope=owner_scope,
            owner_id=owner_id,
            transform=lambda scope: _scope_with_mapping_item(
                scope,
                mapping_name="derivations",
                key=key,
                specification=specification,
            ),
        )

    def set_timeline(
        self,
        package: MaterialPackage,
        *,
        owner_scope: OwnerScope,
        owner_id: str,
        key: str,
        specification: MaterialTimelineSpec,
    ) -> MaterialCommandResult:
        return self._replace_scope(
            package,
            owner_scope=owner_scope,
            owner_id=owner_id,
            transform=lambda scope: _scope_with_mapping_item(
                scope,
                mapping_name="timelines",
                key=key,
                specification=specification,
            ),
        )

    def remove_derivation(
        self,
        package: MaterialPackage,
        *,
        owner_scope: OwnerScope,
        owner_id: str,
        key: str,
    ) -> MaterialCommandResult:
        return self._replace_scope(
            package,
            owner_scope=owner_scope,
            owner_id=owner_id,
            transform=lambda scope: _scope_without_mapping_item(
                scope,
                mapping_name="derivations",
                key=key,
            ),
        )

    def remove_timeline(
        self,
        package: MaterialPackage,
        *,
        owner_scope: OwnerScope,
        owner_id: str,
        key: str,
    ) -> MaterialCommandResult:
        return self._replace_scope(
            package,
            owner_scope=owner_scope,
            owner_id=owner_id,
            transform=lambda scope: _scope_without_mapping_item(
                scope,
                mapping_name="timelines",
                key=key,
            ),
        )

    def save(
        self,
        package: MaterialPackage,
        *,
        expected_revision: str,
    ) -> MaterialCommandResult:
        try:
            snapshot = self._repository.save_user(
                package,
                expected_revision=expected_revision,
            )
        except Exception as exc:
            return MaterialCommandResult(
                issues=(
                    MaterialIssue(
                        code="material.package.save_failed",
                        message=f"{type(exc).__name__}: {exc}",
                        remediation="重新加载资料包后再应用修改。",
                    ),
                )
            )
        return MaterialCommandResult(
            package=snapshot.package,
            snapshot=snapshot,
        )

    def _replace_record(
        self,
        package: MaterialPackage,
        *,
        record_id: str,
        transform,
    ) -> MaterialCommandResult:
        target = package.get_record(record_id)
        if target is None:
            return self._not_found("record", record_id)
        return self._construct(
            lambda: clone_material_package(
                package,
                records=tuple(
                    transform(item) if item.record_id == record_id else item
                    for item in package.records
                ),
            )
        )

    def _replace_scope(
        self,
        package: MaterialPackage,
        *,
        owner_scope: OwnerScope,
        owner_id: str,
        transform,
    ) -> MaterialCommandResult:
        if owner_scope == "shared":
            if owner_id:
                return MaterialCommandResult(
                    issues=(
                        MaterialIssue(
                            code="material.scope.shared_owner_id_forbidden",
                            path="owner_id",
                            message="共享作用域不接受 owner ID。",
                        ),
                    )
                )
            return self._construct(
                lambda: clone_material_package(
                    package,
                    shared_scope=transform(package.shared_scope),
                )
            )
        if owner_scope == "group":
            target = package.get_group(owner_id)
            if target is None:
                return self._not_found("group", owner_id)
            replacement = MaterialGroup(
                group_id=target.group_id,
                display_name=target.display_name,
                scope=transform(target.scope),
                metadata=target.metadata,
            )
            return self._construct(
                lambda: clone_material_package(
                    package,
                    groups=tuple(
                        replacement if item.group_id == owner_id else item
                        for item in package.groups
                    ),
                )
            )
        if owner_scope == "record":
            return self._replace_record(
                package,
                record_id=owner_id,
                transform=lambda record: clone_material_record(
                    record,
                    scope=transform(record.scope),
                ),
            )
        return MaterialCommandResult(
            issues=(
                MaterialIssue(
                    code="material.scope.unknown",
                    path="owner_scope",
                    message=f"未知资料作用域：{owner_scope}",
                ),
            )
        )

    @staticmethod
    def _construct(factory) -> MaterialCommandResult:
        try:
            package = factory()
        except Exception as exc:
            return MaterialCommandResult(
                issues=(
                    MaterialIssue(
                        code="material.package.command_invalid",
                        message=f"{type(exc).__name__}: {exc}",
                    ),
                )
            )
        return MaterialCommandResult(package=package)

    @staticmethod
    def _not_found(kind: str, identity: str) -> MaterialCommandResult:
        return MaterialCommandResult(
            issues=(
                MaterialIssue(
                    code=f"material.{kind}.unknown",
                    path=f"{kind}_id",
                    message=f"找不到 {kind}：{identity}",
                ),
            )
        )


def _scope_with_field(
    scope: MaterialScope,
    *,
    key: str,
    value: str,
    provenance: str,
) -> MaterialScope:
    fields = dict(scope.fields)
    fields[key] = value
    sources = dict(scope.provenance)
    if provenance:
        sources[key] = provenance
    else:
        sources.pop(key, None)
    return _copy_scope(scope, fields=fields, provenance=sources)


def _scope_without_field(scope: MaterialScope, *, key: str) -> MaterialScope:
    fields = dict(scope.fields)
    fields.pop(key, None)
    sources = dict(scope.provenance)
    sources.pop(key, None)
    derivations = dict(scope.derivations)
    derivations.pop(key, None)
    timelines = dict(scope.timelines)
    timelines.pop(key, None)
    return _copy_scope(
        scope,
        fields=fields,
        provenance=sources,
        derivations=derivations,
        timelines=timelines,
    )


def _scope_with_resource(
    scope: MaterialScope,
    binding: MaterialResourceBinding,
) -> MaterialScope:
    resources = dict(scope.resources)
    resources[binding.role] = binding
    return _copy_scope(scope, resources=resources)


def _scope_without_resource(
    scope: MaterialScope,
    role: str,
) -> MaterialScope:
    resources = dict(scope.resources)
    resources.pop(role, None)
    return _copy_scope(scope, resources=resources)


def _scope_with_mapping_item(
    scope: MaterialScope,
    *,
    mapping_name: Literal["derivations", "timelines"],
    key: str,
    specification: MaterialDerivationSpec | MaterialTimelineSpec,
) -> MaterialScope:
    mapping = dict(getattr(scope, mapping_name))
    mapping[key] = specification
    return _copy_scope(scope, **{mapping_name: mapping})


def _scope_without_mapping_item(
    scope: MaterialScope,
    *,
    mapping_name: Literal["derivations", "timelines"],
    key: str,
) -> MaterialScope:
    mapping = dict(getattr(scope, mapping_name))
    mapping.pop(key, None)
    return _copy_scope(scope, **{mapping_name: mapping})


def _copy_scope(scope: MaterialScope, **changes) -> MaterialScope:
    payload = {
        "fields": scope.fields,
        "resources": scope.resources,
        "derivations": scope.derivations,
        "timelines": scope.timelines,
        "provenance": scope.provenance,
    }
    payload.update(changes)
    return MaterialScope(**payload)


def _package_extensions(package: MaterialPackage) -> dict[str, object]:
    raw = package.metadata.get(PACKAGE_CONTRACT_EXTENSIONS_KEY, {})
    source = dict(raw or {})
    extensions = {
        "fields": [
            dict(item)
            for item in source.get("fields", ())
            if hasattr(item, "items")
        ],
        "resource_roles": [
            dict(item)
            for item in source.get("resource_roles", ())
            if hasattr(item, "items")
        ],
        "image_policy": dict(source.get("image_policy", {}) or {}),
    }
    if "content_policy" in source:
        extensions["content_policy"] = dict(
            source.get("content_policy", {}) or {}
        )
    return extensions


def _package_with_extensions(
    package: MaterialPackage,
    extensions: dict[str, object],
) -> MaterialPackage:
    metadata = dict(package.metadata)
    metadata[PACKAGE_CONTRACT_EXTENSIONS_KEY] = extensions
    return clone_material_package(package, metadata=metadata)


def _rename_resource_authoring_source_role(
    package: MaterialPackage,
    *,
    current_role: str,
    role: str,
) -> MaterialPackage:
    metadata = dict(package.metadata)
    raw_sources = metadata.get(RESOURCE_AUTHORING_SOURCES_KEY, {})
    sources = dict(raw_sources or {}) if hasattr(raw_sources, "items") else {}
    if current_role in sources:
        sources[role] = sources.pop(current_role)
    if sources:
        metadata[RESOURCE_AUTHORING_SOURCES_KEY] = sources
    else:
        metadata.pop(RESOURCE_AUTHORING_SOURCES_KEY, None)
    return clone_material_package(package, metadata=metadata)


def _without_resource_authoring_source_role(
    package: MaterialPackage,
    role: str,
) -> MaterialPackage:
    metadata = dict(package.metadata)
    raw_sources = metadata.get(RESOURCE_AUTHORING_SOURCES_KEY, {})
    sources = dict(raw_sources or {}) if hasattr(raw_sources, "items") else {}
    sources.pop(role, None)
    if sources:
        metadata[RESOURCE_AUTHORING_SOURCES_KEY] = sources
    else:
        metadata.pop(RESOURCE_AUTHORING_SOURCES_KEY, None)
    return clone_material_package(package, metadata=metadata)


def _map_package_scopes(package: MaterialPackage, transform) -> MaterialPackage:
    return clone_material_package(
        package,
        shared_scope=transform(package.shared_scope),
        groups=tuple(
            MaterialGroup(
                group_id=group.group_id,
                display_name=group.display_name,
                scope=transform(group.scope),
                metadata=group.metadata,
            )
            for group in package.groups
        ),
        records=tuple(
            clone_material_record(record, scope=transform(record.scope))
            for record in package.records
        ),
    )


def _scope_renamed_field(
    scope: MaterialScope,
    *,
    current_key: str,
    key: str,
) -> MaterialScope:
    fields = dict(scope.fields)
    if current_key in fields:
        fields[key] = fields.pop(current_key)
    provenance = dict(scope.provenance)
    if current_key in provenance:
        provenance[key] = provenance.pop(current_key)
    derivations: dict[str, MaterialDerivationSpec] = {}
    for output, spec in scope.derivations.items():
        renamed_output = key if output == current_key else output
        derivations[renamed_output] = MaterialDerivationSpec(
            output_field=renamed_output,
            preset_id=spec.preset_id,
            preset_version=spec.preset_version,
            input_fields=tuple(
                key if item == current_key else item
                for item in spec.input_fields
            ),
            parameters=spec.parameters,
        )
    timelines: dict[str, MaterialTimelineSpec] = {}
    for output, spec in scope.timelines.items():
        renamed_output = key if output == current_key else output
        parameters = dict(spec.parameters)
        if parameters.get("end_field") == current_key:
            parameters["end_field"] = key
        timelines[renamed_output] = MaterialTimelineSpec(
            output_field=renamed_output,
            preset_id=spec.preset_id,
            preset_version=spec.preset_version,
            anchor_field=(
                key if spec.anchor_field == current_key else spec.anchor_field
            ),
            parameters=parameters,
        )
    return _copy_scope(
        scope,
        fields=fields,
        provenance=provenance,
        derivations=derivations,
        timelines=timelines,
    )


def _scope_without_field_definition(
    scope: MaterialScope,
    *,
    key: str,
) -> MaterialScope:
    fields = dict(scope.fields)
    fields.pop(key, None)
    provenance = dict(scope.provenance)
    provenance.pop(key, None)
    derivations = {
        output: spec
        for output, spec in scope.derivations.items()
        if output != key and key not in spec.input_fields
    }
    timelines = {
        output: spec
        for output, spec in scope.timelines.items()
        if (
            output != key
            and spec.anchor_field != key
            and spec.parameters.get("end_field") != key
        )
    }
    return _copy_scope(
        scope,
        fields=fields,
        provenance=provenance,
        derivations=derivations,
        timelines=timelines,
    )


def _scope_renamed_resource(
    scope: MaterialScope,
    *,
    current_role: str,
    role: str,
) -> MaterialScope:
    resources = dict(scope.resources)
    binding = resources.pop(current_role, None)
    if binding is not None:
        resources[role] = MaterialResourceBinding(
            role=role,
            items=binding.items,
            merge_policy=binding.merge_policy,
        )
    return _copy_scope(scope, resources=resources)


__all__ = [
    "MaterialCommandResult",
    "MaterialPackageService",
]
