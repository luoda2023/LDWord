"""Current-schema wire validation for persisted material timelines."""

from __future__ import annotations

from src.config.entity_archive_wire_contracts import TIMELINE_PLAN_FIELDS
from src.config.entity_wire_validation import (
    first_payload_difference,
    require_exact_fields,
    validate_exact_string_mapping,
    validate_exact_type,
)
from src.shared.engine.material_timeline import (
    TIMELINE_SCHEMA_VERSION,
    normalize_timeline_plans,
    validate_timeline_preset_payload,
)


def validate_timeline_plans(value: object, *, path: str) -> None:
    if type(value) is not dict:
        raise ValueError(f"material_package_field_type_invalid:{path}:dict")
    normalized = normalize_timeline_plans(value)
    difference = first_payload_difference(value, normalized, path=path)
    if difference:
        raise ValueError(f"material_package_timeline_not_canonical:{difference}")
    for plan_id, plan in value.items():
        plan_path = f"{path}.{plan_id}"
        if set(plan) != TIMELINE_PLAN_FIELDS:
            missing = sorted(TIMELINE_PLAN_FIELDS - set(plan))
            if missing:
                raise ValueError(
                    f"material_package_nested_fields_missing:{plan_path}:"
                    f"{','.join(missing)}"
                )
            unknown = sorted(set(plan) - TIMELINE_PLAN_FIELDS)
            raise ValueError(
                f"material_package_nested_fields_unknown:{plan_path}:"
                f"{','.join(unknown)}"
            )
        scalar_types = {
            "schema_version": int,
            "label": str,
            "enabled": bool,
            "deleted": bool,
            "number_state": str,
            "token_copied": bool,
            "segment_no": int,
            "start_value": str,
            "end_value": str,
            "output_format": str,
            "format_mode": str,
            "input_scope": str,
            "start_field": str,
            "end_field": str,
            "rounding": str,
        }
        for key, type_hint in scalar_types.items():
            validate_exact_type(type_hint, plan[key], path=f"{plan_path}.{key}")
        if plan["schema_version"] != TIMELINE_SCHEMA_VERSION:
            raise ValueError(
                f"material_package_timeline_version_unsupported:"
                f"{plan_path}:{plan['schema_version']}"
            )
        validate_exact_type(
            list[str], plan["retired_outputs"], path=f"{plan_path}.retired_outputs"
        )
        validate_exact_string_mapping(
            plan["calendar"],
            {"basis", "weekend_adjust"},
            path=f"{plan_path}.calendar",
        )
        validate_exact_string_mapping(
            plan["constraints"],
            {"bounds", "order", "same_day"},
            path=f"{plan_path}.constraints",
        )
        validate_exact_type(
            dict[str, str], plan["overrides"], path=f"{plan_path}.overrides"
        )
        try:
            validate_timeline_preset_payload(plan["preset"])
        except ValueError as exc:
            raise ValueError(f"material_package_{exc}") from exc
        _validate_timeline_nodes(plan["nodes"], path=f"{plan_path}.nodes")


def _validate_timeline_nodes(value: object, *, path: str) -> None:
    if type(value) is not list:
        raise ValueError(f"material_package_field_type_invalid:{path}:list")
    for index, node in enumerate(value):
        node_path = f"{path}[{index}]"
        if type(node) is not dict:
            raise ValueError(f"material_package_field_type_invalid:{node_path}:dict")
        require_exact_fields(
            node,
            {"node_id", "node_no", "active", "label", "rule", "outputs"},
            path=node_path,
        )
        for key, type_hint in {
            "node_id": str,
            "node_no": int,
            "active": bool,
            "label": str,
        }.items():
            validate_exact_type(type_hint, node[key], path=f"{node_path}.{key}")
        rule = node["rule"]
        if type(rule) is not dict:
            raise ValueError(f"material_package_field_type_invalid:{node_path}.rule:dict")
        operation = rule.get("operation")
        expected_rule_fields = {
            "ratio": {"operation", "value"},
            "fixed_date": {"operation", "value"},
            "add_days": {"operation", "source", "days"},
        }.get(operation)
        if expected_rule_fields is None:
            raise ValueError(
                f"material_package_timeline_operation_invalid:{node_path}.rule"
            )
        require_exact_fields(rule, expected_rule_fields, path=f"{node_path}.rule")
        validate_exact_type(str, operation, path=f"{node_path}.rule.operation")
        for key in expected_rule_fields - {"operation", "days"}:
            validate_exact_type(str, rule[key], path=f"{node_path}.rule.{key}")
        if "days" in expected_rule_fields:
            validate_exact_type(int, rule["days"], path=f"{node_path}.rule.days")
        outputs = node["outputs"]
        if type(outputs) is not list:
            raise ValueError(
                f"material_package_field_type_invalid:{node_path}.outputs:list"
            )
        for output_index, output in enumerate(outputs):
            validate_exact_string_mapping(
                output,
                {"field", "format"},
                path=f"{node_path}.outputs[{output_index}]",
            )


__all__ = ["validate_timeline_plans"]
