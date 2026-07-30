"""Central package/group/record value resolution with provenance."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass

from src.config.material_context import MaterialExecutionContext
from src.config.material_package_v6 import (
    MaterialPackageV6,
    MaterialRecord,
    MaterialValueScope,
)


@dataclass(frozen=True, slots=True)
class MaterialValueProvenance:
    scope: str
    owner_id: str
    source: str = ""
    replaced_scope: str = ""


@dataclass(frozen=True, slots=True)
class MaterialScopeIssue:
    severity: str
    code: str
    key: str
    message: str


@dataclass(frozen=True, slots=True)
class ResolvedMaterialScope:
    record_id: str
    group_id: str
    values: dict[str, str]
    aliases: dict[str, str]
    field_functions: dict[str, dict[str, str]]
    timeline_plans: dict[str, dict[str, object]]
    provenance: dict[str, MaterialValueProvenance]
    issues: tuple[MaterialScopeIssue, ...]
    context: MaterialExecutionContext

    @property
    def blocking_issues(self) -> tuple[MaterialScopeIssue, ...]:
        return tuple(item for item in self.issues if item.severity == "error")


class MaterialScopeResolver:
    """Resolve all hierarchy levels once and expose why each value won."""

    def __init__(self, package: MaterialPackageV6):
        self.package = package

    def resolve_record(
        self,
        record_id: str,
        *,
        runtime_context: MaterialExecutionContext | None = None,
    ) -> ResolvedMaterialScope:
        record = self.package.get_record(record_id)
        if record is None:
            raise KeyError(f"material_record_unknown:{record_id}")
        group = self.package.get_group(record.group_id) if record.group_id else None
        layers: list[tuple[str, str, MaterialValueScope]] = [
            ("package", self.package.package_id, self.package.shared_scope)
        ]
        if group is not None:
            layers.append(("group", group.group_id, group.values))
        layers.append(("record", record.record_id, record.values))
        values: dict[str, str] = {}
        aliases: dict[str, str] = {}
        functions: dict[str, dict[str, str]] = {}
        timelines: dict[str, dict[str, object]] = {}
        provenance: dict[str, MaterialValueProvenance] = {}
        issues: list[MaterialScopeIssue] = []
        for scope_name, owner_id, scope in layers:
            _merge_text_values(
                values,
                scope.fields,
                scope_name=scope_name,
                owner_id=owner_id,
                sources=scope.field_sources,
                override_fields=set(scope.override_fields),
                provenance=provenance,
                issues=issues,
            )
            _merge_contract(
                aliases,
                scope.field_aliases,
                contract_name="alias",
                scope_name=scope_name,
                owner_id=owner_id,
                issues=issues,
            )
            _merge_contract(
                functions,
                scope.field_functions,
                contract_name="function",
                scope_name=scope_name,
                owner_id=owner_id,
                issues=issues,
            )
            _merge_contract(
                timelines,
                scope.timeline_plans,
                contract_name="timeline",
                scope_name=scope_name,
                owner_id=owner_id,
                issues=issues,
            )

        runtime = (
            runtime_context.clone()
            if isinstance(runtime_context, MaterialExecutionContext)
            else MaterialExecutionContext()
        )
        _merge_text_values(
            values,
            runtime.entity_data,
            scope_name="runtime",
            owner_id="run-request",
            sources={},
            override_fields=set(runtime.entity_data),
            provenance=provenance,
            issues=issues,
        )
        _merge_contract(
            aliases,
            runtime.field_aliases,
            contract_name="alias",
            scope_name="runtime",
            owner_id="run-request",
            issues=issues,
        )
        _merge_contract(
            functions,
            runtime.field_functions,
            contract_name="function",
            scope_name="runtime",
            owner_id="run-request",
            issues=issues,
        )
        _merge_contract(
            timelines,
            runtime.timeline_plans,
            contract_name="timeline",
            scope_name="runtime",
            owner_id="run-request",
            issues=issues,
        )

        context = _record_context(
            self.package,
            record,
            values=values,
            aliases=aliases,
            functions=functions,
            timelines=timelines,
            runtime=runtime,
        )
        resolution = context.resolve_material_fields()
        resolved_values = {
            str(key): str(value) for key, value in resolution.values.items()
        }
        timeline_owners = _timeline_output_owners(context.timeline_plans)
        for key in resolved_values:
            if key in provenance:
                continue
            if key in timeline_owners:
                provenance[key] = MaterialValueProvenance(
                    scope="derived_timeline",
                    owner_id=timeline_owners[key],
                )
            elif key in functions:
                provenance[key] = MaterialValueProvenance(
                    scope="derived_function",
                    owner_id=key,
                )
            else:
                provenance[key] = MaterialValueProvenance(
                    scope="derived",
                    owner_id=record.record_id,
                )
        issues.extend(
            MaterialScopeIssue(
                severity="error",
                code="field_function_error",
                key=key,
                message=f"字段函数 {key}：{message}",
            )
            for key, message in sorted(resolution.function_errors.items())
        )
        issues.extend(
            MaterialScopeIssue(
                severity=str(getattr(item, "severity", "error")).lower(),
                code=str(getattr(item, "code", "timeline_issue")),
                key=str(getattr(item, "field_key", "") or ""),
                message=str(getattr(item, "message", item)),
            )
            for item in resolution.timeline_issues
        )
        frozen_context = context.clone()
        frozen_context.entity_data = dict(resolved_values)
        frozen_context.frozen_field_values = dict(resolved_values)
        frozen_context.field_values_frozen = True
        return ResolvedMaterialScope(
            record_id=record.record_id,
            group_id=record.group_id,
            values=resolved_values,
            aliases=dict(aliases),
            field_functions=copy.deepcopy(functions),
            timeline_plans=copy.deepcopy(timelines),
            provenance=provenance,
            issues=tuple(issues),
            context=frozen_context,
        )


def merge_material_value_layers(
    layers: tuple[tuple[str, str, MaterialValueScope], ...],
) -> tuple[
    dict[str, str],
    dict[str, str],
    dict[str, dict[str, str]],
    dict[str, dict[str, object]],
    dict[str, MaterialValueProvenance],
    tuple[MaterialScopeIssue, ...],
]:
    """Public pure merge primitive used by compatibility adapters."""

    values: dict[str, str] = {}
    aliases: dict[str, str] = {}
    functions: dict[str, dict[str, str]] = {}
    timelines: dict[str, dict[str, object]] = {}
    provenance: dict[str, MaterialValueProvenance] = {}
    issues: list[MaterialScopeIssue] = []
    for scope_name, owner_id, scope in layers:
        _merge_text_values(
            values,
            scope.fields,
            scope_name=scope_name,
            owner_id=owner_id,
            sources=scope.field_sources,
            override_fields=set(scope.override_fields),
            provenance=provenance,
            issues=issues,
        )
        _merge_contract(
            aliases,
            scope.field_aliases,
            contract_name="alias",
            scope_name=scope_name,
            owner_id=owner_id,
            issues=issues,
        )
        _merge_contract(
            functions,
            scope.field_functions,
            contract_name="function",
            scope_name=scope_name,
            owner_id=owner_id,
            issues=issues,
        )
        _merge_contract(
            timelines,
            scope.timeline_plans,
            contract_name="timeline",
            scope_name=scope_name,
            owner_id=owner_id,
            issues=issues,
        )
    return values, aliases, functions, timelines, provenance, tuple(issues)


def _record_context(
    package: MaterialPackageV6,
    record: MaterialRecord,
    *,
    values: Mapping[str, str],
    aliases: Mapping[str, str],
    functions: Mapping[str, dict[str, str]],
    timelines: Mapping[str, dict[str, object]],
    runtime: MaterialExecutionContext,
) -> MaterialExecutionContext:
    profile = record.profile
    return MaterialExecutionContext(
        mode_id=runtime.mode_id or package.mode_id,
        scene_id=runtime.scene_id,
        package_id=package.package_id,
        material_schema_ids=(
            tuple(runtime.material_schema_ids) or tuple(package.material_schema_ids)
        ),
        compatible_profile_ids=tuple(runtime.compatible_profile_ids),
        compatible_master_families=tuple(runtime.compatible_master_families),
        archive_id=package.package_id,
        archive_name=package.package_name,
        profile_id=record.record_id,
        profile_name=record.record_name,
        entity_data=dict(values),
        field_scopes={
            **dict(profile.field_scopes),
            **dict(runtime.field_scopes),
        },
        field_functions=copy.deepcopy(dict(functions)),
        timeline_plans=copy.deepcopy(dict(timelines)),
        field_aliases=dict(aliases),
        entity_assets_dir=profile.assets_dir or runtime.entity_assets_dir,
        images=copy.deepcopy(runtime.images),
        asset_items=copy.deepcopy(runtime.asset_items),
        asset_diagnostics=copy.deepcopy(runtime.asset_diagnostics),
        image_rules=copy.deepcopy(runtime.image_rules),
        image_material_rules={
            **copy.deepcopy(profile.image_material_rules),
            **copy.deepcopy(runtime.image_material_rules),
        },
        image_watermark_text=runtime.image_watermark_text,
        content_bindings={
            **copy.deepcopy(profile.content_bindings),
            **copy.deepcopy(runtime.content_bindings),
        },
        content_rules=[
            *copy.deepcopy(profile.content_rules),
            *copy.deepcopy(runtime.content_rules),
        ],
        attachment_bindings={
            **copy.deepcopy(profile.attachment_bindings),
            **copy.deepcopy(runtime.attachment_bindings),
        },
        exact_material_placeholders=runtime.exact_material_placeholders,
    )


def _merge_text_values(
    target: dict[str, str],
    incoming: Mapping[str, str],
    *,
    scope_name: str,
    owner_id: str,
    sources: Mapping[str, str],
    override_fields: set[str],
    provenance: dict[str, MaterialValueProvenance],
    issues: list[MaterialScopeIssue],
) -> None:
    for raw_key, raw_value in incoming.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        value = str(raw_value or "")
        previous = provenance.get(key)
        if key in target and target[key] != value:
            severity = "info" if key in override_fields else "warning"
            issues.append(
                MaterialScopeIssue(
                    severity=severity,
                    code=(
                        "scope_override_declared"
                        if key in override_fields
                        else "scope_value_shadowed"
                    ),
                    key=key,
                    message=(
                        f"{scope_name} 层的“{key}”覆盖了 "
                        f"{previous.scope if previous else 'lower'} 层值"
                    ),
                )
            )
        target[key] = value
        provenance[key] = MaterialValueProvenance(
            scope=scope_name,
            owner_id=owner_id,
            source=str(sources.get(key, "") or ""),
            replaced_scope=previous.scope if previous else "",
        )


def _merge_contract(
    target: dict,
    incoming: Mapping,
    *,
    contract_name: str,
    scope_name: str,
    owner_id: str,
    issues: list[MaterialScopeIssue],
) -> None:
    for raw_key, raw_value in incoming.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        if key in target and target[key] != raw_value:
            issues.append(
                MaterialScopeIssue(
                    severity="warning",
                    code=f"scope_{contract_name}_shadowed",
                    key=key,
                    message=(
                        f"{scope_name} 层 {owner_id} 重定义了 {contract_name}“{key}”"
                    ),
                )
            )
        target[key] = copy.deepcopy(raw_value)


def _timeline_output_owners(
    timelines: Mapping[str, dict[str, object]],
) -> dict[str, str]:
    owners: dict[str, str] = {}
    for plan_id, plan in timelines.items():
        if not bool(plan.get("enabled", True)) or bool(
            plan.get("deleted", False)
        ):
            continue
        for raw_node in list(plan.get("nodes", []) or []):
            node = dict(raw_node) if isinstance(raw_node, Mapping) else {}
            if not bool(node.get("active", True)):
                continue
            for raw_output in list(node.get("outputs", []) or []):
                output = (
                    dict(raw_output)
                    if isinstance(raw_output, Mapping)
                    else {}
                )
                key = str(output.get("field", "") or "").strip()
                if key:
                    owners.setdefault(key, str(plan_id))
    return owners


__all__ = [
    "MaterialScopeIssue",
    "MaterialScopeResolver",
    "MaterialValueProvenance",
    "ResolvedMaterialScope",
    "merge_material_value_layers",
]
