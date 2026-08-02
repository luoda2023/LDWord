"""Whole-package semantic validation against one material contract."""

from __future__ import annotations

from .contract import MaterialContract
from .model import MaterialIssue, MaterialPackage


def validate_material_package_contract(
    package: MaterialPackage,
    contract: MaterialContract,
) -> tuple[MaterialIssue, ...]:
    issues: list[MaterialIssue] = []
    if package.material_contract_id != contract.contract_id:
        issues.append(
            MaterialIssue(
                code="material.contract.identity_mismatch",
                path="material_contract_id",
                message="资料包契约身份与加载上下文不一致。",
            )
        )
    if package.work_mode_id != contract.work_mode_id:
        issues.append(
            MaterialIssue(
                code="material.contract.mode_mismatch",
                path="work_mode_id",
                message="资料包工作模式与资料契约不一致。",
            )
        )
    scopes = [
        ("shared", "shared_scope", package.shared_scope),
        *(
            ("group", f"groups.{group.group_id}.scope", group.scope)
            for group in package.groups
        ),
        *(
            ("record", f"records.{record.record_id}.scope", record.scope)
            for record in package.records
        ),
    ]
    for owner, path, scope in scopes:
        for key in scope.fields:
            field = contract.get_field(key)
            if field is None:
                issues.append(
                    MaterialIssue(
                        code="material.field.unknown",
                        path=f"{path}.fields.{key}",
                        message=f"资料契约未声明字段：{key}",
                    )
                )
            elif owner not in field.allowed_scopes:
                issues.append(
                    MaterialIssue(
                        code="material.field.scope_not_allowed",
                        path=f"{path}.fields.{key}",
                        message=f"字段 {key} 不允许位于 {owner} 作用域。",
                    )
                )
        for role, binding in scope.resources.items():
            resource = contract.get_resource_role(role)
            if resource is None:
                issues.append(
                    MaterialIssue(
                        code="material.resource.unknown",
                        path=f"{path}.resources.{role}",
                        message=f"资料契约未声明资源角色：{role}",
                    )
                )
                continue
            if owner not in resource.allowed_scopes:
                issues.append(
                    MaterialIssue(
                        code="material.resource.scope_not_allowed",
                        path=f"{path}.resources.{role}",
                        message=f"资源 {role} 不允许位于 {owner} 作用域。",
                    )
                )
            if binding.merge_policy != resource.merge_policy:
                issues.append(
                    MaterialIssue(
                        code="material.resource.merge_policy_mismatch",
                        path=f"{path}.resources.{role}",
                        message=f"资源 {role} 合并策略与契约不一致。",
                    )
                )
            if (
                resource.max_items is not None
                and len(binding.items) > resource.max_items
            ):
                issues.append(
                    MaterialIssue(
                        code="material.resource.cardinality_exceeded",
                        path=f"{path}.resources.{role}",
                        message=f"资源 {role} 超过契约允许数量。",
                    )
                )
            for item in binding.items:
                if (
                    resource.accepted_media_types
                    and item.media_type not in resource.accepted_media_types
                ):
                    issues.append(
                        MaterialIssue(
                            code="material.resource.media_type_invalid",
                            path=f"{path}.resources.{role}.{item.object_id}",
                            message=f"资源 {role} 不接受 {item.media_type}。",
                        )
                    )
        for key, specification in scope.derivations.items():
            _validate_calculation(
                issues,
                contract=contract,
                owner=owner,
                path=f"{path}.derivations.{key}",
                output=key,
                inputs=specification.input_fields,
                preset=(specification.preset_id, specification.preset_version),
                supported=contract.supported_derivation_presets,
            )
        for key, specification in scope.timelines.items():
            timeline_inputs = [specification.anchor_field]
            if specification.preset_id == "timeline_ratio":
                end_field = str(
                    specification.parameters.get("end_field", "")
                )
                if end_field:
                    timeline_inputs.append(end_field)
            _validate_calculation(
                issues,
                contract=contract,
                owner=owner,
                path=f"{path}.timelines.{key}",
                output=key,
                inputs=tuple(timeline_inputs),
                preset=(specification.preset_id, specification.preset_version),
                supported=contract.supported_timeline_presets,
            )
    return tuple(issues)


def _validate_calculation(
    issues: list[MaterialIssue],
    *,
    contract: MaterialContract,
    owner: str,
    path: str,
    output: str,
    inputs: tuple[str, ...],
    preset: tuple[str, int],
    supported: tuple[tuple[str, int], ...],
) -> None:
    output_field = contract.get_field(output)
    if output_field is None:
        issues.append(
            MaterialIssue(
                code="material.calculation.output_field_unknown",
                path=path,
                message=f"计算输出字段未声明：{output}",
            )
        )
    elif owner not in output_field.allowed_scopes:
        issues.append(
            MaterialIssue(
                code="material.calculation.output_scope_not_allowed",
                path=path,
                message=f"计算输出字段 {output} 不允许位于 {owner} 作用域。",
            )
        )
    unknown = [key for key in inputs if contract.get_field(key) is None]
    if unknown:
        issues.append(
            MaterialIssue(
                code="material.calculation.input_field_unknown",
                path=path,
                message="计算规则引用未知字段：" + "、".join(unknown),
            )
        )
    if preset not in supported:
        issues.append(
            MaterialIssue(
                code="material.calculation.preset_unknown",
                path=path,
                message=f"资料契约不支持 preset：{preset[0]} v{preset[1]}",
            )
        )


__all__ = ["validate_material_package_contract"]
