"""Single-owner integrity checks for execution-controlling configuration."""

from __future__ import annotations

from collections.abc import Mapping

from src.config.execution_failure_policy import execution_failure_policy_issue
from src.config.material_schema_registry import (
    missing_material_schema_ids,
    resolve_material_schema_ids,
)
from src.config.plugin_manual_gate import plugin_manual_gate_execution_issue
from src.shared.engine.count_engine import count_profile_registry_issue
from src.shared.engine.journal_rule_source_governance import (
    journal_rule_source_governance_execution_issues,
)


def delivery_preset_identity_issues(config: object) -> tuple[str, ...]:
    """Return lossless identity errors for one delivery-preset collection.

    SceneWorkspace and ResolvedConfig own ``default_delivery_preset_id``.  An
    explicit zero-preset configuration has no artifact authorization and must
    therefore keep the default empty.  Once presets exist, exactly one known,
    non-empty ID must be selected.  Lightweight projections without that
    field are not required to invent a default, but any presets they expose
    still cannot reuse or omit an ID.
    """

    owns_default = hasattr(config, "default_delivery_preset_id")
    owns_presets = hasattr(config, "delivery_presets")
    if not owns_default and not owns_presets:
        return ()

    presets = list(getattr(config, "delivery_presets", ()) or ())
    issues: list[str] = []
    known_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    for index, preset in enumerate(presets):
        preset_id = str(getattr(preset, "preset_id", "") or "").strip()
        if not preset_id:
            issues.append(f"delivery_preset_id_empty:{index}")
            continue
        if preset_id in known_ids:
            duplicate_ids.add(preset_id)
        known_ids.add(preset_id)
    issues.extend(
        f"duplicate_delivery_preset_id:{preset_id}"
        for preset_id in sorted(duplicate_ids)
    )

    if owns_default:
        default_id = str(
            getattr(config, "default_delivery_preset_id", "") or ""
        ).strip()
        if presets and not default_id:
            issues.append("default_delivery_preset_id_empty")
        elif default_id and default_id not in known_ids:
            issues.append(f"default_delivery_preset_id_unknown:{default_id}")
    return tuple(issues)


def delivery_preset_identity_issue(config: object) -> str:
    """Return the first delivery identity error from the single owner."""

    issues = delivery_preset_identity_issues(config)
    return issues[0] if issues else ""


def execution_config_integrity_issues(
    config: object,
    *,
    entity_data: Mapping[str, object] | None = None,
) -> tuple[str, ...]:
    """Return registry/value-domain errors that must always block execution."""

    issues = list(delivery_preset_identity_issues(config))
    input_profile = getattr(config, "input_source_profile", None)
    schema_ids = resolve_material_schema_ids(
        str(getattr(input_profile, "material_schema_id", "") or ""),
        list(getattr(input_profile, "material_schema_ids", ()) or ()),
    )
    missing_schema_ids = missing_material_schema_ids(schema_ids)
    if missing_schema_ids:
        issues.append(
            "unknown_material_schema:" + ",".join(missing_schema_ids)
        )

    compliance_profile = getattr(config, "compliance_profile", None)
    count_profile_issue = count_profile_registry_issue(
        str(getattr(compliance_profile, "count_profile_id", "") or "")
    )
    if count_profile_issue:
        issues.append(count_profile_issue)

    issues.extend(
        journal_rule_source_governance_execution_issues(
            config,
            entity_data=entity_data,
        )
    )

    policy_owners = (
        (
            "input_source_profile.failure_policy",
            getattr(input_profile, "failure_policy", "warn"),
        ),
        (
            "compliance_profile.failure_policy",
            getattr(compliance_profile, "failure_policy", "warn"),
        ),
    )
    for field_path, value in policy_owners:
        policy_issue = execution_failure_policy_issue(value)
        if policy_issue:
            issues.append(f"{field_path}:{policy_issue}")

    manual_gate_issue = plugin_manual_gate_execution_issue(config)
    if manual_gate_issue:
        issues.append(manual_gate_issue)
    return tuple(issues)


def execution_config_integrity_issue(
    config: object,
    *,
    entity_data: Mapping[str, object] | None = None,
) -> str:
    """Return the first blocking issue for one execution configuration."""

    issues = execution_config_integrity_issues(
        config,
        entity_data=entity_data,
    )
    return issues[0] if issues else ""


__all__ = [
    "delivery_preset_identity_issue",
    "delivery_preset_identity_issues",
    "execution_config_integrity_issue",
    "execution_config_integrity_issues",
]
