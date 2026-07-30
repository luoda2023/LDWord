"""Publish material manifests and delivery-package artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath

from src.config.atomic_io import atomic_write_text
from src.config.asset_resolution import file_content_revision
from src.config.material_context import MaterialExecutionContext
from src.config.material_schema_registry import (
    MATERIAL_SCHEMA_MAP,
    build_material_requirements,
    evaluate_material_requirements,
    missing_material_schema_ids,
)
from src.reporting.material_assembly import (
    extract_attachment_bundles,
    extract_material_assembly,
)
from src.services.material_delivery import (
    DeliveryPackageBuildRequest,
    DeliveryPackageReceipt,
    build_material_delivery_package,
    capture_delivery_package_source_receipt,
)
from src.shared.engine.material_dependency_projection import (
    project_attachment_binding,
)

from .material_preflight import (
    material_context_asset_roles,
    profile_material_schema_ids,
)


def _material_manifest_artifact_enabled(config) -> bool:
    return _output_artifact_enabled(config, "material_manifest") or _output_artifact_enabled(
        config,
        "material_package",
    )


def _material_package_artifact_enabled(config) -> bool:
    return _output_artifact_enabled(config, "material_package")


def _output_artifact_enabled(config, artifact_name: str) -> bool:
    output = getattr(config, "output", None)
    if bool(getattr(output, artifact_name, False)):
        return True
    for preset in list(getattr(config, "delivery_presets", []) or []):
        artifacts = getattr(preset, "artifacts", None)
        if bool(getattr(artifacts, artifact_name, False)):
            return True
    return False


def write_material_manifest(
    *,
    input_path: Path,
    output_dir: Path,
    config,
    material_context: MaterialExecutionContext,
    material_diagnostics: list[dict] | None,
    output_paths: dict[str, str],
    compare_paths: dict[str, str],
    report_paths: list[str],
    intermediate_paths: dict[str, str],
    result: object | None = None,
) -> dict[str, str]:
    if not _material_manifest_artifact_enabled(config):
        return {}
    if not _material_manifest_should_write(
        config,
        material_context,
        material_diagnostics,
        result=result,
    ):
        return {}

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / f"{input_path.stem}_material_manifest.json"
    payload = _material_manifest_payload(
        input_path=input_path,
        config=config,
        material_context=material_context,
        material_diagnostics=list(material_diagnostics or []),
        output_paths=output_paths,
        compare_paths=compare_paths,
        report_paths=report_paths,
        intermediate_paths=intermediate_paths,
        result=result,
    )
    atomic_write_text(
        manifest_path,
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return {"material": str(manifest_path)}


def write_material_package_artifacts(
    *,
    input_path: Path,
    output_dir: Path,
    config,
    material_manifest_paths: dict[str, str],
    material_context: MaterialExecutionContext,
    output_paths: dict[str, str],
    compare_paths: dict[str, str],
    report_paths: list[str],
    intermediate_paths: dict[str, str],
    result: object | None = None,
    content_artifact_root: Path | None = None,
) -> DeliveryPackageReceipt | None:
    """UI adapter for the transaction-safe delivery package service."""

    if not _material_package_artifact_enabled(config):
        return None
    manifests = material_artifact_path_map(material_manifest_paths)
    material_manifest_path = str(manifests.get("material") or "").strip()
    if not material_manifest_path:
        return None
    manifest_path = Path(material_manifest_path)
    source_receipts = _material_package_source_receipts(
        manifest_path=manifest_path,
        material_context=material_context,
        output_paths=output_paths,
        compare_paths=compare_paths,
        report_paths=report_paths,
        intermediate_paths=intermediate_paths,
        result=result,
    )
    return build_material_delivery_package(
        DeliveryPackageBuildRequest(
            input_path=input_path,
            output_dir=output_dir,
            manifest_path=manifest_path,
            source_receipts=source_receipts,
            content_artifact_root=content_artifact_root,
        )
    )


def _material_package_source_receipts(
    *,
    manifest_path: Path,
    material_context: MaterialExecutionContext,
    output_paths: dict[str, str],
    compare_paths: dict[str, str],
    report_paths: list[str],
    intermediate_paths: dict[str, str],
    result: object | None,
):
    """Capture exact sources from live runtime facts, never from manifest JSON."""

    if not isinstance(material_context, MaterialExecutionContext):
        raise TypeError("material_context must be a MaterialExecutionContext")
    candidates: list[Path] = [manifest_path]
    for item in list(material_context.asset_items or []):
        path_text = str(getattr(item, "path", "") or "").strip()
        metadata = dict(getattr(item, "metadata", {}) or {})
        cache_text = str(metadata.get("cache_path") or "").strip()
        if path_text and not _material_path_looks_remote(path_text) and Path(
            path_text
        ).is_file():
            candidates.append(Path(path_text))
        elif cache_text and Path(cache_text).is_file():
            candidates.append(Path(cache_text))
        elif path_text and Path(path_text).is_file():
            candidates.append(Path(path_text))

    attachment_execution = (
        extract_attachment_bundles(result)
        if result is not None
        else {"status": "not_run", "receipts": {}}
    )
    if str(attachment_execution.get("status") or "") in {
        "applied",
        "partial_success",
        "failed",
    }:
        for receipt in dict(attachment_execution.get("receipts") or {}).values():
            if not isinstance(receipt, dict):
                continue
            output_directory = Path(str(receipt.get("output_directory") or ""))
            for item in list(receipt.get("files") or []):
                if not isinstance(item, dict):
                    continue
                relative = _material_package_relative_path(
                    str(item.get("relative_path") or "")
                )
                candidate = output_directory.joinpath(*relative.parts)
                if candidate.is_file():
                    candidates.append(candidate)
    else:
        for binding in dict(material_context.attachment_bindings or {}).values():
            for item in tuple(getattr(binding, "items", ()) or ()):
                source_text = str(
                    getattr(getattr(item, "file_ref", None), "source_path", "")
                    or ""
                ).strip()
                if source_text and Path(source_text).is_file():
                    candidates.append(Path(source_text))

    for path_map in (output_paths, compare_paths, intermediate_paths):
        candidates.extend(
            Path(str(value))
            for value in path_map.values()
            if str(value or "").strip() and Path(str(value)).is_file()
        )
    candidates.extend(
        Path(str(value))
        for value in report_paths
        if str(value or "").strip() and Path(str(value)).is_file()
    )

    receipts = []
    seen: set[str] = set()
    for candidate in candidates:
        receipt = capture_delivery_package_source_receipt(candidate)
        identity = str(receipt.path).casefold()
        if identity in seen:
            continue
        seen.add(identity)
        receipts.append(receipt)
    return tuple(receipts)


def _material_package_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(str(value or "").replace("\\", "/"))
    if (
        path.is_absolute()
        or not path.name
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"attachment receipt relative path is unsafe: {value}")
    return path


def _material_path_looks_remote(value: str) -> bool:
    normalized = str(value or "").strip().casefold()
    return "://" in normalized or normalized.startswith("urn:")


def material_package_path_map(value: object) -> dict[str, str]:
    if not isinstance(value, DeliveryPackageReceipt):
        return {}
    return value.to_path_map()


def material_package_receipt_payload(value: object) -> dict[str, object]:
    if not isinstance(value, DeliveryPackageReceipt):
        return {}
    return {
        "status": value.status,
        "copied_file_count": value.copied_file_count,
        "missing_reference_count": value.missing_reference_count,
        "paths": value.to_path_map(),
    }


def _safe_package_filename(value: str) -> str:
    """Normalize one manifest-derived path segment.

    Package I/O lives in the delivery service; this helper remains only for
    building manifest archive-directory hints.
    """

    name = str(value or "").strip() or "file"
    for char in '<>:"\\|?*':
        name = name.replace(char, "_")
    return name.replace("/", "_")


def _material_manifest_should_write(
    config,
    material_context: MaterialExecutionContext,
    material_diagnostics: list[dict] | None,
    *,
    result: object | None = None,
) -> bool:
    profile = getattr(config, "input_source_profile", None)
    has_profile_requirements = bool(
        profile_material_schema_ids(profile)
        or list(getattr(profile, "required_material_fields", []) or [])
        or list(getattr(profile, "required_image_roles", []) or [])
    )
    assembly_status = (
        str(extract_material_assembly(result).get("status") or "")
        if result is not None
        else ""
    )
    return bool(
        has_profile_requirements
        or not material_context.is_empty()
        or list(material_diagnostics or [])
        or assembly_status in {"applied", "failed"}
    )


@dataclass(slots=True)
class _ManifestSchemaState:
    profile: object
    compliance: object
    schema_id: str
    missing_schema_ids: list[str]
    schema: object
    requirements: object
    check: object
    field_specs: dict[str, object]
    asset_specs: dict[str, object]
    fields_payload: list[dict[str, object]]
    missing_asset_roles: list[str]


@dataclass(slots=True)
class _ManifestDomainState:
    asset_roles_payload: list[dict[str, object]]
    asset_items_payload: list[dict[str, object]]
    image_rules_payload: list[dict[str, object]]
    image_material_rules_payload: list[dict[str, object]]
    content_bindings_payload: list[dict[str, object]]
    content_rules_payload: list[dict[str, object]]
    attachment_bindings_payload: list[dict[str, object]]
    attachment_items_payload: list[dict[str, object]]
    legacy_attachment_items_payload: list[dict[str, object]]
    image_items_payload: list[dict[str, object]]
    attachment_execution: dict[str, object]
    material_domains: dict[str, object]


def _material_manifest_payload(
    *,
    input_path: Path,
    config,
    material_context: MaterialExecutionContext,
    material_diagnostics: list[dict],
    output_paths: dict[str, str],
    compare_paths: dict[str, str],
    report_paths: list[str],
    intermediate_paths: dict[str, str],
    result: object | None = None,
) -> dict[str, object]:
    schema_state = _manifest_schema_state(config, material_context)
    domain_state = _manifest_domain_state(
        material_context,
        schema_state=schema_state,
        result=result,
    )
    execution = _material_manifest_execution_payload(
        configured={
            "profile": _manifest_profile_identity(material_context),
            "schema_ids": list(schema_state.requirements.schema_ids),
            "fields": schema_state.fields_payload,
            "asset_roles": domain_state.asset_roles_payload,
            "material_domains": domain_state.material_domains,
        },
        result=result,
    )
    return _manifest_document_payload(
        input_path=input_path,
        config=config,
        material_context=material_context,
        material_diagnostics=material_diagnostics,
        output_paths=output_paths,
        compare_paths=compare_paths,
        report_paths=report_paths,
        intermediate_paths=intermediate_paths,
        schema_state=schema_state,
        domain_state=domain_state,
        execution=execution,
    )


def _manifest_schema_state(
    config,
    material_context: MaterialExecutionContext,
) -> _ManifestSchemaState:
    profile = getattr(config, "input_source_profile", None)
    compliance = getattr(config, "compliance_profile", None)
    schema_ids = profile_material_schema_ids(profile)
    schema_id = schema_ids[0] if schema_ids else ""
    missing_schema_ids = missing_material_schema_ids(schema_ids)
    schemas = [
        MATERIAL_SCHEMA_MAP[item]
        for item in schema_ids
        if item in MATERIAL_SCHEMA_MAP
    ]
    schema = MATERIAL_SCHEMA_MAP.get(schema_id)
    extra_fields = list(getattr(profile, "required_material_fields", []) or [])
    extra_roles = list(getattr(profile, "required_image_roles", []) or [])
    requirements = build_material_requirements(
        schema_id,
        schema_ids=schema_ids,
        extra_required_fields=extra_fields,
        extra_required_asset_roles=extra_roles,
    )
    check = evaluate_material_requirements(
        schema_id=schema_id,
        schema_ids=schema_ids,
        entity_data=material_context.entity_data,
        asset_roles=material_context_asset_roles(material_context),
        extra_required_fields=extra_fields,
        extra_required_asset_roles=extra_roles,
    )
    missing_asset_roles = unique_manifest_values(
        [
            *check.missing_asset_roles,
            *material_context.missing_required_asset_roles(),
        ]
    )
    field_specs = {
        field.key: field
        for item in schemas
        for field in list(getattr(item, "fields", ()) or ())
    }
    asset_specs = {
        role.role: role
        for item in schemas
        for role in list(getattr(item, "asset_roles", ()) or ())
    }
    field_keys = unique_manifest_values(
        [
            *field_specs.keys(),
            *extra_fields,
            *material_context.entity_data.keys(),
        ]
    )
    fields_payload = [
        _material_manifest_field_payload(
            key,
            field_specs.get(key),
            material_context.entity_data,
            required=key in requirements.required_field_keys,
        )
        for key in field_keys
    ]
    return _ManifestSchemaState(
        profile=profile,
        compliance=compliance,
        schema_id=schema_id,
        missing_schema_ids=missing_schema_ids,
        schema=schema,
        requirements=requirements,
        check=check,
        field_specs=field_specs,
        asset_specs=asset_specs,
        fields_payload=fields_payload,
        missing_asset_roles=missing_asset_roles,
    )


def _manifest_domain_state(
    material_context: MaterialExecutionContext,
    *,
    schema_state: _ManifestSchemaState,
    result: object | None,
) -> _ManifestDomainState:
    asset_items = list(getattr(material_context, "asset_items", []) or [])
    attachment_bindings = dict(
        getattr(material_context, "attachment_bindings", {}) or {}
    )
    image_material_rules = dict(
        getattr(material_context, "image_material_rules", {}) or {}
    )
    asset_role_keys = _manifest_asset_role_keys(
        material_context,
        schema_state=schema_state,
        image_material_rules=image_material_rules,
    )
    items_by_role = _manifest_items_by_role(asset_items, attachment_bindings)
    asset_roles_payload = [
        _material_manifest_asset_role_payload(
            role,
            schema_state.asset_specs.get(role),
            items_by_role.get(role, []),
            required=role in schema_state.requirements.required_asset_roles,
            missing=role in schema_state.missing_asset_roles,
        )
        for role in asset_role_keys
    ]
    asset_items_payload = [
        _material_manifest_asset_item_payload(
            item,
            schema_state.asset_specs.get(_normalize_manifest_key(item.role)),
        )
        for item in asset_items
    ]
    image_rules_payload = _manifest_legacy_image_rules(material_context)
    image_material_rules_payload = [
        {"contract": "image_material_rule_v1", **rule.to_dict()}
        for _rule_id, rule in sorted(
            image_material_rules.items(),
            key=lambda item: item[0].casefold(),
        )
    ]
    content_bindings_payload = [
        binding.to_dict()
        for _content_id, binding in sorted(
            dict(getattr(material_context, "content_bindings", {}) or {}).items(),
            key=lambda item: item[0].casefold(),
        )
    ]
    content_rules_payload = [
        rule.to_dict()
        for rule in list(getattr(material_context, "content_rules", []) or [])
    ]
    (
        attachment_bindings_payload,
        attachment_items_payload,
    ) = _manifest_attachment_payloads(
        attachment_bindings,
        asset_specs=schema_state.asset_specs,
        result=result,
    )
    image_items_payload = [
        item
        for item in asset_items_payload
        if item.get("material_domain") == "image"
    ]
    legacy_attachment_items_payload = [
        item
        for item in asset_items_payload
        if item.get("material_domain") == "attachment"
    ]
    attachment_execution = _manifest_attachment_execution(result)
    material_domains = {
        "content": {
            "bindings": content_bindings_payload,
            "rules": content_rules_payload,
        },
        "image": {
            "items": image_items_payload,
            "material_rules": image_material_rules_payload,
            "legacy_insertion_rules": image_rules_payload,
        },
        "attachment": {
            "bindings": attachment_bindings_payload,
            "items": [
                *attachment_items_payload,
                *legacy_attachment_items_payload,
            ],
            "execution": attachment_execution,
        },
    }
    return _ManifestDomainState(
        asset_roles_payload=asset_roles_payload,
        asset_items_payload=asset_items_payload,
        image_rules_payload=image_rules_payload,
        image_material_rules_payload=image_material_rules_payload,
        content_bindings_payload=content_bindings_payload,
        content_rules_payload=content_rules_payload,
        attachment_bindings_payload=attachment_bindings_payload,
        attachment_items_payload=attachment_items_payload,
        legacy_attachment_items_payload=legacy_attachment_items_payload,
        image_items_payload=image_items_payload,
        attachment_execution=attachment_execution,
        material_domains=material_domains,
    )


def _manifest_asset_role_keys(
    material_context: MaterialExecutionContext,
    *,
    schema_state: _ManifestSchemaState,
    image_material_rules: dict,
) -> list[str]:
    profile = schema_state.profile
    return unique_manifest_values(
        [
            *schema_state.asset_specs.keys(),
            *list(getattr(profile, "required_image_roles", []) or []),
            *[
                getattr(rule, "asset_role", "")
                for rule in list(getattr(material_context, "image_rules", []) or [])
            ],
            *[
                getattr(rule, "source_role", "")
                for rule in image_material_rules.values()
            ],
            *[
                getattr(item, "role", "")
                for item in list(getattr(material_context, "asset_items", []) or [])
            ],
            *list(
                dict(
                    getattr(material_context, "attachment_bindings", {}) or {}
                ).keys()
            ),
        ]
    )


def _manifest_items_by_role(
    asset_items: list,
    attachment_bindings: dict,
) -> dict[str, list]:
    items_by_role: dict[str, list] = {}
    for item in asset_items:
        role = _normalize_manifest_key(getattr(item, "role", ""))
        if role:
            items_by_role.setdefault(role, []).append(item)
    for role, binding in attachment_bindings.items():
        normalized_role = _normalize_manifest_key(role)
        if normalized_role:
            items_by_role.setdefault(normalized_role, []).extend(
                list(getattr(binding, "items", ()) or ())
            )
    return items_by_role


def _manifest_legacy_image_rules(
    material_context: MaterialExecutionContext,
) -> list[dict[str, object]]:
    return [
        {
            "contract": "legacy_asset_insertion_rule_v1",
            "rule_id": str(getattr(rule, "rule_id", "") or ""),
            "asset_role": _normalize_manifest_key(getattr(rule, "asset_role", "")),
            "target": str(getattr(rule, "target", "") or ""),
            "width_cm": getattr(rule, "width_cm", None),
            "required": bool(getattr(rule, "required", False)),
            "cardinality": str(
                getattr(rule, "cardinality", "single") or "single"
            ),
            "min_items": int(getattr(rule, "min_items", 0) or 0),
            "max_items": getattr(rule, "max_items", None),
            "occurrence_policy": str(
                getattr(rule, "occurrence_policy", "first") or "first"
            ),
        }
        for rule in list(getattr(material_context, "image_rules", []) or [])
    ]


def _manifest_attachment_payloads(
    attachment_bindings: dict,
    *,
    asset_specs: dict[str, object],
    result: object | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    assembly_receipt = getattr(result, "material_assembly_receipt", None)
    dependency_index = getattr(assembly_receipt, "dependency_index", None)
    bindings_payload: list[dict[str, object]] = []
    for role, binding in sorted(
        attachment_bindings.items(),
        key=lambda item: item[0].casefold(),
    ):
        archive_dir = _material_manifest_asset_archive_dir(
            asset_specs.get(role),
            role,
        )
        package_subdir = f"attachments/{archive_dir or _safe_archive_dir(role)}"
        bindings_payload.append(
            {
                **binding.to_dict(),
                "material_domain": "attachment",
                "archive_dir": archive_dir,
                "package_subdir": package_subdir,
                "projection": project_attachment_binding(
                    binding,
                    dependency_index,
                ),
            }
        )
    items_payload = [
        {
            "role": binding.role,
            **item.to_dict(),
            "material_domain": "attachment",
        }
        for binding in attachment_bindings.values()
        for item in binding.items
    ]
    return bindings_payload, items_payload


def _manifest_attachment_execution(
    result: object | None,
) -> dict[str, object]:
    if result is not None:
        return extract_attachment_bundles(result)
    return {
        "status": "not_run",
        "receipts": {},
        "errors": {},
        "binding_count": 0,
        "succeeded_binding_count": 0,
        "failed_binding_count": 0,
        "file_count": 0,
        "substituted_file_count": 0,
        "passthrough_file_count": 0,
        "field_replacement_count": 0,
        "image_job_count": 0,
    }


def _manifest_document_payload(
    *,
    input_path: Path,
    config,
    material_context: MaterialExecutionContext,
    material_diagnostics: list[dict],
    output_paths: dict[str, str],
    compare_paths: dict[str, str],
    report_paths: list[str],
    intermediate_paths: dict[str, str],
    schema_state: _ManifestSchemaState,
    domain_state: _ManifestDomainState,
    execution: dict[str, object],
) -> dict[str, object]:
    return {
        "kind": "material_attachment_manifest",
        "schema_version": 1,
        "visibility": "local_diagnostic_only",
        "external_distribution": "never",
        "input": str(input_path),
        "scene": {
            "strict_mode": bool(getattr(config, "strict_mode", True)),
            "default_delivery_preset_id": str(
                getattr(config, "default_delivery_preset_id", "") or ""
            ),
        },
        "material_profile": {
            **_manifest_profile_identity(material_context),
            "entity_assets_dir": str(material_context.entity_assets_dir or ""),
        },
        "material_schema": _manifest_schema_payload(schema_state),
        "input_contract": _manifest_input_contract(schema_state.profile),
        "compliance": _manifest_compliance_payload(schema_state.compliance),
        "fields": schema_state.fields_payload,
        "asset_roles": domain_state.asset_roles_payload,
        "asset_items": domain_state.asset_items_payload,
        "image_rules": domain_state.image_rules_payload,
        "material_domains": domain_state.material_domains,
        "execution": execution,
        "material_dependencies": _manifest_dependency_projection(execution),
        "missing": {
            "schema_ids": list(schema_state.missing_schema_ids),
            "field_keys": list(schema_state.check.missing_field_keys),
            "asset_roles": list(schema_state.missing_asset_roles),
        },
        "diagnostics": material_diagnostics,
        "delivery": _manifest_delivery_payload(
            output_paths=output_paths,
            compare_paths=compare_paths,
            report_paths=report_paths,
            intermediate_paths=intermediate_paths,
            attachment_execution=domain_state.attachment_execution,
        ),
        "summary": _manifest_summary(
            schema_state,
            domain_state,
            diagnostics_count=len(material_diagnostics),
        ),
    }


def _manifest_profile_identity(
    material_context: MaterialExecutionContext,
) -> dict[str, str]:
    return {
        "archive_id": str(material_context.archive_id or ""),
        "profile_id": str(material_context.profile_id or ""),
        "profile_name": str(material_context.profile_name or ""),
    }


def _manifest_schema_payload(
    state: _ManifestSchemaState,
) -> dict[str, object]:
    requirements = state.requirements
    return {
        "schema_id": state.schema_id,
        "schema_ids": list(requirements.schema_ids),
        "label": str(
            getattr(state.schema, "label", "") or state.schema_id
        ),
        "labels": list(requirements.schema_labels),
        "family": str(getattr(state.schema, "family", "") or ""),
        "required_field_keys": list(requirements.required_field_keys),
        "required_asset_roles": list(requirements.required_asset_roles),
        "archive_directory_rules": [
            {
                "role": role,
                "archive_dir": _material_manifest_asset_archive_dir(spec, role),
                "package_subdir": _material_manifest_asset_package_subdir(
                    spec,
                    role,
                ),
            }
            for role, spec in state.asset_specs.items()
            if _material_manifest_asset_archive_dir(spec, role)
        ],
    }


def _manifest_input_contract(profile: object) -> dict[str, object]:
    return {
        "accepted_formats": list(getattr(profile, "accepted_formats", []) or []),
        "structured_formats": list(
            getattr(profile, "structured_formats", []) or []
        ),
        "failure_policy": str(getattr(profile, "failure_policy", "") or ""),
    }


def _manifest_compliance_payload(compliance: object) -> dict[str, str]:
    return {
        "profile_id": str(getattr(compliance, "profile_id", "") or ""),
        "rule_family": str(getattr(compliance, "rule_family", "") or ""),
        "count_profile_id": str(
            getattr(compliance, "count_profile_id", "") or ""
        ),
    }


def _manifest_dependency_projection(
    execution: dict[str, object],
) -> dict[str, object]:
    applied = execution.get("applied")
    if (
        isinstance(applied, dict)
        and isinstance(applied.get("dependencies"), dict)
    ):
        return {
            **dict(applied["dependencies"]),
            "usage": dict(applied.get("dependency_usage", {})),
        }
    return {
        "status": "not_scanned",
        "occurrence_count": 0,
        "consumer_count": 0,
        "diagnostic_count": 0,
    }


def _manifest_delivery_payload(
    *,
    output_paths: dict[str, str],
    compare_paths: dict[str, str],
    report_paths: list[str],
    intermediate_paths: dict[str, str],
    attachment_execution: dict[str, object],
) -> dict[str, object]:
    return {
        "output_paths": material_artifact_path_map(output_paths),
        "compare_paths": material_artifact_path_map(compare_paths),
        "report_paths": [str(path) for path in report_paths],
        "intermediate_paths": material_artifact_path_map(intermediate_paths),
        "attachment_bundle_paths": {
            role: str(receipt.get("output_directory") or "")
            for role, receipt in dict(
                attachment_execution.get("receipts") or {}
            ).items()
            if isinstance(receipt, dict)
            and str(receipt.get("output_directory") or "").strip()
        },
    }


def _manifest_summary(
    schema: _ManifestSchemaState,
    domains: _ManifestDomainState,
    *,
    diagnostics_count: int,
) -> dict[str, int]:
    attachment_item_count = len(domains.attachment_items_payload) + len(
        domains.legacy_attachment_items_payload
    )
    attachment_execution = domains.attachment_execution
    return {
        "field_count": len(schema.fields_payload),
        "filled_field_count": sum(
            1 for item in schema.fields_payload if item["present"]
        ),
        "asset_role_count": len(domains.asset_roles_payload),
        "asset_item_count": len(domains.asset_items_payload),
        "content_binding_count": len(domains.content_bindings_payload),
        "content_rule_count": len(domains.content_rules_payload),
        "image_item_count": len(domains.image_items_payload),
        "image_rule_count": len(domains.image_rules_payload),
        "image_material_rule_count": len(domains.image_material_rules_payload),
        "attachment_binding_count": len(domains.attachment_bindings_payload),
        "attachment_item_count": attachment_item_count,
        "attachment_processed_file_count": int(
            attachment_execution.get("file_count") or 0
        ),
        "attachment_substituted_file_count": int(
            attachment_execution.get("substituted_file_count") or 0
        ),
        "attachment_field_replacement_count": int(
            attachment_execution.get("field_replacement_count") or 0
        ),
        "attachment_image_job_count": int(
            attachment_execution.get("image_job_count") or 0
        ),
        "attachment_failed_binding_count": int(
            attachment_execution.get("failed_binding_count") or 0
        ),
        "missing_schema_count": len(schema.missing_schema_ids),
        "missing_field_count": len(schema.check.missing_field_keys),
        "missing_asset_count": len(schema.missing_asset_roles),
        "diagnostics_count": diagnostics_count,
    }


def _material_manifest_execution_payload(
    *,
    configured: dict[str, object],
    result: object | None,
) -> dict[str, object]:
    """Keep configured intent and receipt-proven effects in separate domains."""

    if result is None:
        evidence: dict[str, object] = {
            "status": "not_run",
            "receipt": None,
            "error": None,
        }
    else:
        evidence = extract_material_assembly(result)
    evidence_status = str(evidence.get("status") or "not_run")
    status = evidence_status if evidence_status in {"applied", "failed"} else "configured_only"
    return {
        "contract_version": "material-execution-manifest-v1",
        "status": status,
        "configured": configured,
        "applied": evidence if status == "applied" else None,
        "failure": evidence.get("error") if status == "failed" else None,
    }


def _material_manifest_field_payload(
    key: str,
    spec,
    entity_data: dict[str, str],
    *,
    required: bool,
) -> dict[str, object]:
    value = str(entity_data.get(key, "") or "")
    return {
        "key": key,
        "label": str(getattr(spec, "label", "") or key),
        "required": bool(required),
        "present": bool(value.strip()),
        "value": value,
        "aliases": list(getattr(spec, "aliases", ()) or ()),
    }


def _material_manifest_asset_role_payload(
    role: str,
    spec,
    items: list,
    *,
    required: bool,
    missing: bool,
) -> dict[str, object]:
    typed_attachment_role = bool(items) and all(
        getattr(item, "file_ref", None) is not None for item in items
    )
    archive_dir = _material_manifest_asset_archive_dir(spec, role)
    package_subdir = (
        f"attachments/{archive_dir or _safe_archive_dir(role) or 'attachment'}"
        if typed_attachment_role
        else _material_manifest_asset_package_subdir(spec, role)
    )
    return {
        "role": role,
        "label": str(getattr(spec, "label", "") or role),
        "required": bool(required),
        "accepted_types": list(getattr(spec, "accepted_types", ()) or ()),
        "cardinality": str(getattr(spec, "cardinality", "single") or "single"),
        "source_kind": str(getattr(spec, "source_kind", "file") or "file"),
        "recursive": bool(getattr(spec, "recursive", False)),
        "min_items": int(getattr(spec, "min_items", 0) or 0),
        "max_items": getattr(spec, "max_items", 1),
        "order_policy": str(
            getattr(spec, "order_policy", "natural_path") or "natural_path"
        ),
        "naming_template": str(
            getattr(spec, "naming_template", "{role}_{sequence:03d}")
            or "{role}_{sequence:03d}"
        ),
        "archive_dir": archive_dir,
        "package_subdir": package_subdir,
        "material_domain": "attachment" if typed_attachment_role else "image",
        "present": bool(items),
        "missing": bool(missing),
        "item_count": len(items),
        "items": [
            _material_manifest_asset_item_payload(item, spec, role=role)
            for item in items
        ],
    }


def _material_manifest_asset_item_payload(
    item,
    spec,
    *,
    role: str = "",
) -> dict[str, object]:
    file_ref = getattr(item, "file_ref", None)
    typed_attachment = file_ref is not None
    path = str(
        getattr(file_ref, "source_path", "")
        if typed_attachment
        else getattr(item, "path", "")
        or ""
    )
    role = _normalize_manifest_key(role or getattr(item, "role", ""))
    original_name = str(getattr(file_ref, "original_name", "") or "")
    media_type = str(
        getattr(file_ref, "media_type", "")
        if typed_attachment
        else getattr(item, "mime_type", "")
        or ""
    )
    kind = (
        "attachment"
        if typed_attachment
        else _material_manifest_asset_kind(item, spec)
    )
    archive_dir = _material_manifest_asset_archive_dir(spec, role)
    package_subdir = (
        f"attachments/{archive_dir or _safe_archive_dir(role) or 'attachment'}"
        if typed_attachment
        else _material_manifest_asset_package_subdir(spec, role)
    )
    metadata = {
        str(key): str(value)
        for key, value in dict(getattr(item, "metadata", {}) or {}).items()
        if str(key or "").strip() and str(value or "").strip()
    }
    identity_path = Path(path) if path else Path()
    cache_path = str(metadata.get("cache_path") or "").strip()
    if (not path or not identity_path.is_file()) and cache_path:
        identity_path = Path(cache_path)
    declared_hash = str(
        getattr(file_ref, "content_sha256", "")
        if typed_attachment
        else getattr(item, "content_hash", "")
        or ""
    ).strip()
    if not declared_hash and identity_path.is_file():
        declared_hash = file_content_revision(identity_path)
    content_sha256 = declared_hash.casefold().removeprefix("sha256:")
    byte_size = (
        int(getattr(file_ref, "byte_size", 0) or 0)
        if typed_attachment
        else (
            identity_path.stat().st_size
            if identity_path.is_file()
            else None
        )
    )
    return {
        "item_id": str(getattr(item, "item_id", "") or ""),
        "label": str(getattr(item, "label", "") or ""),
        "role": role,
        "path": path,
        "exists": bool(path and Path(path).exists()),
        "mime_type": media_type,
        "tags": list(getattr(item, "tags", []) or []),
        "width_cm": getattr(item, "width_cm", None),
        "metadata": metadata,
        "group_id": str(getattr(item, "group_id", "") or ""),
        "sequence": getattr(item, "sequence", None),
        "source_path": str(
            getattr(file_ref, "source_path", "")
            if typed_attachment
            else getattr(item, "source_path", "")
            or ""
        ),
        "original_relative_path": str(
            original_name
            if typed_attachment
            else getattr(item, "original_relative_path", "")
            or ""
        ),
        "normalized_name": str(
            original_name
            if typed_attachment
            else getattr(item, "normalized_name", "")
            or ""
        ),
        "content_hash": str(
            getattr(file_ref, "content_sha256", "")
            if typed_attachment
            else getattr(item, "content_hash", "")
            or ""
        ),
        "content_sha256": content_sha256,
        "byte_size": byte_size,
        "kind": kind,
        "material_domain": "image" if kind == "image" else "attachment",
        "archive_dir": archive_dir,
        "package_subdir": package_subdir,
    }


def _material_manifest_asset_archive_dir(spec, role: str) -> str:
    configured = _safe_archive_dir(getattr(spec, "archive_dir", ""))
    if configured:
        return configured
    return _safe_archive_dir(role)


def _material_manifest_asset_package_subdir(spec, role: str) -> str:
    archive_dir = _material_manifest_asset_archive_dir(spec, role)
    return f"assets/{archive_dir}" if archive_dir else "assets/asset"


def _safe_archive_dir(value) -> str:
    text = str(value or "").strip().replace("\\", "/")
    parts: list[str] = []
    for part in text.split("/"):
        raw = part.strip()
        if not raw:
            continue
        cleaned = _safe_package_filename(raw)
        if not cleaned or cleaned in {".", ".."}:
            continue
        parts.append(cleaned)
    return "/".join(parts)


def _material_manifest_asset_kind(item, spec) -> str:
    accepted = {
        _normalize_manifest_key(value)
        for value in list(getattr(spec, "accepted_types", ()) or ())
    }
    mime_type = str(getattr(item, "mime_type", "") or "").lower()
    if "pdf" in accepted or any(value and value != "image" for value in accepted):
        return "attachment"
    if mime_type == "application/pdf":
        return "attachment"
    if mime_type.startswith("image/") or "image" in accepted:
        return "image"
    return "asset"


def material_artifact_path_map(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): str(path)
        for key, path in value.items()
        if str(key or "").strip() and str(path or "").strip()
    }


def unique_manifest_values(values) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = _normalize_manifest_key(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


def _normalize_manifest_key(value) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


__all__ = [
    "material_artifact_path_map",
    "material_package_path_map",
    "material_package_receipt_payload",
    "unique_manifest_values",
    "write_material_manifest",
    "write_material_package_artifacts",
]
