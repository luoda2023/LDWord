"""Deterministic material-scope resolver with explicit ownership evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from types import MappingProxyType
from typing import Mapping

from .contract import MaterialContract
from .model import (
    MaterialDerivationSpec,
    MaterialIssue,
    MaterialObjectRef,
    MaterialPackage,
    MaterialRunSelection,
    MaterialTimelineSpec,
)


@dataclass(frozen=True, slots=True)
class ResolvedMaterialRecord:
    record_id: str
    display_name: str
    field_values: Mapping[str, str]
    field_owners: Mapping[str, str]
    resources: Mapping[str, tuple[MaterialObjectRef, ...]]
    resource_owners: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class MaterialResolution:
    record: ResolvedMaterialRecord | None = None
    issues: tuple[MaterialIssue, ...] = ()

    @property
    def ok(self) -> bool:
        return self.record is not None and not any(
            item.severity == "error" for item in self.issues
        )


class MaterialResolver:
    def __init__(
        self,
        package: MaterialPackage,
        contract: MaterialContract,
    ) -> None:
        if package.material_contract_id != contract.contract_id:
            raise ValueError(
                "material_contract_mismatch:"
                f"{package.material_contract_id}:{contract.contract_id}"
            )
        if package.work_mode_id != contract.work_mode_id:
            raise ValueError(
                "material_contract_mode_mismatch:"
                f"{package.work_mode_id}:{contract.work_mode_id}"
            )
        self._package = package
        self._contract = contract

    def resolve_record(
        self,
        record_id: str,
        *,
        selection: MaterialRunSelection | None = None,
    ) -> MaterialResolution:
        record = self._package.get_record(record_id)
        if record is None:
            return MaterialResolution(
                issues=(
                    MaterialIssue(
                        code="material.record.unknown",
                        path="selected_record_ids",
                        message=f"资料记录不存在：{record_id}",
                    ),
                )
            )
        group = (
            self._package.get_group(record.group_id)
            if record.group_id
            else None
        )
        layers = [
            ("shared", self._package.shared_scope),
            *((("group", group.scope),) if group is not None else ()),
            ("record", record.scope),
        ]
        issues: list[MaterialIssue] = []
        values: dict[str, str] = {}
        owners: dict[str, str] = {}
        resources: dict[str, tuple[MaterialObjectRef, ...]] = {}
        resource_owners: dict[str, tuple[str, ...]] = {}
        calculations: dict[
            str,
            tuple[
                str,
                MaterialDerivationSpec | MaterialTimelineSpec,
                str,
            ],
        ] = {}

        for owner, scope in layers:
            for key, value in scope.fields.items():
                field_contract = self._contract.get_field(key)
                if field_contract is None:
                    issues.append(
                        MaterialIssue(
                            code="material.field.unknown",
                            path=f"{owner}.fields.{key}",
                            message=f"资料契约未声明字段：{key}",
                        )
                    )
                    continue
                if owner not in field_contract.allowed_scopes:
                    issues.append(
                        MaterialIssue(
                            code="material.field.scope_not_allowed",
                            path=f"{owner}.fields.{key}",
                            message=f"字段 {key} 不允许位于 {owner} 作用域",
                        )
                    )
                    continue
                values[key] = value
                owners[key] = owner
            for role, binding in scope.resources.items():
                role_contract = self._contract.get_resource_role(role)
                if role_contract is None:
                    issues.append(
                        MaterialIssue(
                            code="material.resource.unknown",
                            path=f"{owner}.resources.{role}",
                            message=f"资料契约未声明资源角色：{role}",
                        )
                    )
                    continue
                if owner not in role_contract.allowed_scopes:
                    issues.append(
                        MaterialIssue(
                            code="material.resource.scope_not_allowed",
                            path=f"{owner}.resources.{role}",
                            message=f"资源 {role} 不允许位于 {owner} 作用域",
                        )
                    )
                    continue
                if binding.merge_policy != role_contract.merge_policy:
                    issues.append(
                        MaterialIssue(
                            code="material.resource.merge_policy_mismatch",
                            path=f"{owner}.resources.{role}",
                            message=(
                                f"资源 {role} 的合并策略必须为 "
                                f"{role_contract.merge_policy}"
                            ),
                        )
                    )
                    continue
                if binding.merge_policy == "append" and role in resources:
                    resources[role] = (*resources[role], *binding.items)
                    resource_owners[role] = (
                        *resource_owners[role],
                        owner,
                    )
                else:
                    resources[role] = binding.items
                    resource_owners[role] = (owner,)
            for key, specification in scope.derivations.items():
                if key in calculations:
                    issues.append(
                        MaterialIssue(
                            code="material.derivation.output_owner_conflict",
                            path=f"{owner}.derivations.{key}",
                            message=f"派生字段 {key} 在多个作用域中声明。",
                        )
                    )
                else:
                    calculations[key] = ("derivation", specification, owner)
            for key, specification in scope.timelines.items():
                if key in calculations:
                    issues.append(
                        MaterialIssue(
                            code="material.timeline.output_owner_conflict",
                            path=f"{owner}.timelines.{key}",
                            message=f"时间线字段 {key} 在多个作用域中声明。",
                        )
                    )
                else:
                    calculations[key] = ("timeline", specification, owner)

        if selection is not None:
            if selection.package_ref.package_id != self._package.package_id:
                issues.append(
                    MaterialIssue(
                        code="material.selection.package_mismatch",
                        path="package_ref.package_id",
                        message="运行选择不属于当前资料包",
                    )
                )
            for key, value in selection.runtime_field_overrides.items():
                field_contract = self._contract.get_field(key)
                if (
                    field_contract is None
                    or not field_contract.allow_run_override
                ):
                    issues.append(
                        MaterialIssue(
                            code="material.field.run_override_not_allowed",
                            path=f"runtime_field_overrides.{key}",
                            message=f"字段 {key} 不允许运行时覆盖",
                        )
                    )
                    continue
                values[key] = value
                owners[key] = "run"
            for role, binding in selection.runtime_resource_overrides.items():
                role_contract = self._contract.get_resource_role(role)
                if (
                    role_contract is None
                    or "run" not in role_contract.allowed_scopes
                ):
                    issues.append(
                        MaterialIssue(
                            code="material.resource.run_override_not_allowed",
                            path=f"runtime_resource_overrides.{role}",
                            message=f"资源 {role} 不允许运行时覆盖",
                        )
                    )
                    continue
                resources[role] = binding.items
                resource_owners[role] = ("run",)

        _resolve_calculations(
            calculations,
            contract=self._contract,
            values=values,
            owners=owners,
            issues=issues,
        )

        for field_contract in self._contract.fields:
            if field_contract.required and not values.get(field_contract.key, ""):
                issues.append(
                    MaterialIssue(
                        code="material.field.required_missing",
                        path=f"resolved.fields.{field_contract.key}",
                        message=f"缺少必填字段：{field_contract.label}",
                    )
                )
        for role_contract in self._contract.resource_roles:
            items = resources.get(role_contract.role, ())
            minimum = max(
                role_contract.min_items,
                1 if role_contract.required else 0,
            )
            if len(items) < minimum:
                issues.append(
                    MaterialIssue(
                        code="material.resource.required_missing",
                        path=f"resolved.resources.{role_contract.role}",
                        message=f"缺少必需资源：{role_contract.label}",
                    )
                )
            if (
                role_contract.max_items is not None
                and len(items) > role_contract.max_items
            ):
                issues.append(
                    MaterialIssue(
                        code="material.resource.cardinality_exceeded",
                        path=f"resolved.resources.{role_contract.role}",
                        message=(
                            f"资源 {role_contract.label} 最多允许 "
                            f"{role_contract.max_items} 项"
                        ),
                    )
                )
            if role_contract.accepted_media_types:
                for item in items:
                    if item.media_type not in role_contract.accepted_media_types:
                        issues.append(
                            MaterialIssue(
                                code="material.resource.media_type_invalid",
                                path=(
                                    "resolved.resources."
                                    f"{role_contract.role}.{item.object_id}"
                                ),
                                message=(
                                    f"资源 {role_contract.label} 不接受 "
                                    f"{item.media_type}"
                                ),
                            )
                        )
        resolved = ResolvedMaterialRecord(
            record_id=record.record_id,
            display_name=record.display_name,
            field_values=MappingProxyType(values),
            field_owners=MappingProxyType(owners),
            resources=MappingProxyType(resources),
            resource_owners=MappingProxyType(resource_owners),
        )
        return MaterialResolution(record=resolved, issues=tuple(issues))


def _resolve_calculations(
    calculations: Mapping[
        str,
        tuple[
            str,
            MaterialDerivationSpec | MaterialTimelineSpec,
            str,
        ],
    ],
    *,
    contract: MaterialContract,
    values: dict[str, str],
    owners: dict[str, str],
    issues: list[MaterialIssue],
) -> None:
    graph: dict[str, tuple[str, ...]] = {}
    valid: set[str] = set()
    for output, (kind, specification, owner) in calculations.items():
        output_contract = contract.get_field(output)
        path = f"{owner}.{kind}s.{output}"
        if output_contract is None:
            issues.append(
                MaterialIssue(
                    code=f"material.{kind}.output_field_unknown",
                    path=path,
                    message=f"资料契约未声明计算输出字段：{output}",
                )
            )
            continue
        if owner not in output_contract.allowed_scopes:
            issues.append(
                MaterialIssue(
                    code=f"material.{kind}.output_scope_not_allowed",
                    path=path,
                    message=f"计算输出字段 {output} 不允许位于 {owner} 作用域。",
                )
            )
            continue
        if output in values:
            issues.append(
                MaterialIssue(
                    code=f"material.{kind}.output_owner_conflict",
                    path=path,
                    message=f"字段 {output} 同时存在显式值和计算规则。",
                )
            )
            continue
        preset = (specification.preset_id, specification.preset_version)
        supported = (
            contract.supported_derivation_presets
            if kind == "derivation"
            else contract.supported_timeline_presets
        )
        if preset not in supported:
            issues.append(
                MaterialIssue(
                    code=f"material.{kind}.preset_unknown",
                    path=path,
                    message=(
                        f"资料契约不支持 {kind} preset："
                        f"{preset[0]} v{preset[1]}"
                    ),
                )
            )
            continue
        dependencies = _calculation_dependencies(specification)
        unknown = tuple(
            field_name
            for field_name in dependencies
            if contract.get_field(field_name) is None
        )
        if unknown:
            issues.append(
                MaterialIssue(
                    code=f"material.{kind}.input_field_unknown",
                    path=path,
                    message="计算规则引用未知字段：" + "、".join(unknown),
                )
            )
            continue
        graph[output] = tuple(
            item for item in dependencies if item in calculations
        )
        valid.add(output)

    order: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(output: str) -> None:
        if output in visited or output not in valid:
            return
        if output in visiting:
            issues.append(
                MaterialIssue(
                    code="material.calculation.cycle",
                    path=f"calculations.{output}",
                    message=f"派生值/时间线存在循环依赖：{output}",
                )
            )
            valid.clear()
            return
        visiting.add(output)
        for dependency in graph.get(output, ()):
            visit(dependency)
        visiting.discard(output)
        visited.add(output)
        order.append(output)

    for output in tuple(valid):
        visit(output)
    if not valid:
        return
    for output in order:
        if output not in valid:
            continue
        kind, specification, owner = calculations[output]
        path = f"{owner}.{kind}s.{output}"
        try:
            if isinstance(specification, MaterialDerivationSpec):
                missing = [
                    key for key in specification.input_fields if key not in values
                ]
                if missing:
                    raise ValueError(
                        "input_missing:" + ",".join(missing)
                    )
                result = _evaluate_derivation(specification, values)
            else:
                dependencies = _calculation_dependencies(specification)
                missing = [
                    key for key in dependencies if key not in values
                ]
                if missing:
                    raise ValueError(
                        "anchor_missing:" + ",".join(missing)
                    )
                result = _evaluate_timeline(specification, values)
        except ValueError as exc:
            issues.append(
                MaterialIssue(
                    code=f"material.{kind}.evaluation_failed",
                    path=path,
                    message=f"计算字段 {output} 失败：{exc}",
                )
            )
            continue
        values[output] = result
        owners[output] = f"{kind}:{owner}"


def _evaluate_derivation(
    specification: MaterialDerivationSpec,
    values: Mapping[str, str],
) -> str:
    if specification.preset_id == "copy":
        if specification.parameters or len(specification.input_fields) != 1:
            raise ValueError("copy_spec_invalid")
        return values[specification.input_fields[0]]
    if specification.preset_id == "join":
        unknown = set(specification.parameters) - {"separator"}
        if unknown:
            raise ValueError("join_parameter_unknown:" + ",".join(sorted(unknown)))
        separator = specification.parameters.get("separator", "")
        return separator.join(values[key] for key in specification.input_fields)
    raise ValueError("derivation_preset_unreachable")


def _evaluate_timeline(
    specification: MaterialTimelineSpec,
    values: Mapping[str, str],
) -> str:
    if specification.preset_id == "date_offset_days":
        if set(specification.parameters) != {"days"}:
            raise ValueError("date_offset_days_parameters_invalid")
        days_text = specification.parameters["days"]
        if (
            not days_text
            or days_text == "-"
            or any(
                not char.isascii() or (not char.isdigit() and char != "-")
                for char in days_text
            )
            or days_text.count("-") > 1
            or ("-" in days_text and not days_text.startswith("-"))
        ):
            raise ValueError("date_offset_days_value_invalid")
        try:
            anchor = date.fromisoformat(values[specification.anchor_field])
            result = anchor + timedelta(days=int(days_text))
        except (OverflowError, ValueError) as exc:
            raise ValueError("date_offset_days_anchor_invalid") from exc
        return result.isoformat()
    if specification.preset_id == "timeline_ratio":
        return _evaluate_timeline_ratio(specification, values)
    raise ValueError("timeline_preset_unreachable")


_TIMELINE_RATIO_PARAMETERS = frozenset(
    {
        "end_field",
        "ratio",
        "weekend_adjust",
        "output_format",
        "segment_id",
        "node_index",
        "node_count",
        "input_scope",
    }
)
_TIMELINE_FORMAT_TOKEN = re.compile(r"yyyy|MM|dd|M|d")


def _calculation_dependencies(
    specification: MaterialDerivationSpec | MaterialTimelineSpec,
) -> tuple[str, ...]:
    if isinstance(specification, MaterialDerivationSpec):
        return specification.input_fields
    dependencies = [specification.anchor_field]
    if specification.preset_id == "timeline_ratio":
        end_field = str(specification.parameters.get("end_field", ""))
        if end_field:
            dependencies.append(end_field)
    return tuple(dependencies)


def _evaluate_timeline_ratio(
    specification: MaterialTimelineSpec,
    values: Mapping[str, str],
) -> str:
    parameters = specification.parameters
    if set(parameters) != _TIMELINE_RATIO_PARAMETERS:
        raise ValueError("timeline_ratio_parameters_invalid")
    end_field = parameters["end_field"]
    try:
        start = _parse_timeline_date(values[specification.anchor_field])
        end = _parse_timeline_date(values[end_field])
        ratio = Decimal(parameters["ratio"])
    except (InvalidOperation, KeyError, ValueError) as exc:
        raise ValueError("timeline_ratio_input_invalid") from exc
    if end < start:
        raise ValueError("timeline_ratio_end_before_start")
    if ratio < 0 or ratio > 1:
        raise ValueError("timeline_ratio_value_invalid")
    offset = int(
        (Decimal((end - start).days) * ratio).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )
    result = _adjust_timeline_weekend(
        start + timedelta(days=offset),
        parameters["weekend_adjust"],
    )
    output_format = parameters["output_format"]
    if output_format == "auto":
        output_format = _infer_timeline_format(
            values[specification.anchor_field]
        )
    return _format_timeline_date(result, output_format)


def _parse_timeline_date(value: object) -> date:
    text = str(value or "").strip().translate(
        str.maketrans({"－": "-", "／": "/", "．": "."})
    )
    compact = re.sub(r"\s+", "", text)
    if compact.endswith("号"):
        compact = compact[:-1] + "日"
    for candidate in dict.fromkeys((text, compact)):
        for pattern in (
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y.%m.%d",
            "%d/%m/%Y",
            "%Y年%m月%d日",
            "%Y%m%d",
        ):
            try:
                return datetime.strptime(candidate, pattern).date()
            except ValueError:
                continue
    raise ValueError("timeline_date_invalid")


def _infer_timeline_format(value: object) -> str:
    text = str(value or "").strip()
    compact = re.sub(r"\s+", "", text)
    chinese = re.fullmatch(
        r"\d{4}年(\d{1,2})月(\d{1,2})(?:日|号)?",
        compact,
    )
    if chinese:
        month, day = chinese.groups()
        return (
            f"yyyy年{'MM' if len(month) == 2 else 'M'}月"
            f"{'dd' if len(day) == 2 else 'd'}日"
        )
    separated = re.fullmatch(
        r"\d{4}([-/\.])(\d{1,2})\1(\d{1,2})",
        compact,
    )
    if separated:
        separator, month, day = separated.groups()
        return (
            f"yyyy{separator}{'MM' if len(month) == 2 else 'M'}"
            f"{separator}{'dd' if len(day) == 2 else 'd'}"
        )
    return "yyyy-MM-dd"


def _format_timeline_date(value: date, pattern: str) -> str:
    if not pattern or re.search(r"[^yMd年/月日.\-]", pattern):
        raise ValueError("timeline_output_format_invalid")
    replacements = {
        "yyyy": f"{value.year:04d}",
        "MM": f"{value.month:02d}",
        "M": str(value.month),
        "dd": f"{value.day:02d}",
        "d": str(value.day),
    }
    return _TIMELINE_FORMAT_TOKEN.sub(
        lambda match: replacements[match.group(0)],
        pattern,
    )


def _adjust_timeline_weekend(value: date, policy: str) -> date:
    if policy not in {"none", "forward", "backward", "nearest"}:
        raise ValueError("timeline_weekend_adjust_invalid")
    if value.weekday() < 5 or policy == "none":
        return value
    before = value
    after = value
    while before.weekday() >= 5:
        before -= timedelta(days=1)
    while after.weekday() >= 5:
        after += timedelta(days=1)
    if policy == "forward":
        return after
    if policy == "backward":
        return before
    return before if (value - before) <= (after - value) else after


__all__ = [
    "MaterialResolution",
    "MaterialResolver",
    "ResolvedMaterialRecord",
]
