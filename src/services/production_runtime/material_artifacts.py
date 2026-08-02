"""Publish material manifests and delivery packages for the current runtime."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.application.materials import ExecutionMaterialSnapshot
from src.config.atomic_io import atomic_write_text
from src.services.execution_session.support import file_sha256
from src.services.material_delivery import (
    DeliveryPackageBuildRequest,
    DeliveryPackageReceipt,
    build_material_delivery_package,
    capture_delivery_package_source_receipt,
)


@dataclass(frozen=True, slots=True)
class MaterialArtifactOutcome:
    material_manifest_paths: dict[str, str] = field(default_factory=dict)
    material_package_paths: dict[str, str] = field(default_factory=dict)
    material_package_receipt: dict[str, object] = field(default_factory=dict)


def publish_material_artifacts(
    *,
    input_path: Path,
    output_dir: Path,
    config,
    material_snapshot: ExecutionMaterialSnapshot | None,
    output_paths: dict[str, str],
    report_paths: list[str] | tuple[str, ...] = (),
    compare_paths: dict[str, str] | None = None,
    intermediate_paths: dict[str, str] | None = None,
) -> MaterialArtifactOutcome:
    """Publish enabled material artifacts from frozen runtime facts."""

    manifest_enabled = _artifact_enabled(config, "material_manifest")
    package_enabled = _artifact_enabled(config, "material_package")
    if not manifest_enabled and not package_enabled:
        return MaterialArtifactOutcome()

    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / f"{input_path.stem}_material_manifest.json"
    payload = _material_manifest_payload(
        config=config,
        material_snapshot=material_snapshot,
        output_paths=output_paths,
        report_paths=report_paths,
        compare_paths=compare_paths or {},
        intermediate_paths=intermediate_paths or {},
    )
    atomic_write_text(
        manifest_path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    manifest_paths = {"material": str(manifest_path)}
    if not package_enabled:
        return MaterialArtifactOutcome(material_manifest_paths=manifest_paths)

    source_paths = [
        manifest_path,
        *_existing_paths(output_paths.values()),
        *_existing_paths((compare_paths or {}).values()),
        *_existing_paths(report_paths),
        *_existing_paths((intermediate_paths or {}).values()),
        *_snapshot_resource_paths(material_snapshot),
    ]
    receipts = tuple(
        capture_delivery_package_source_receipt(path)
        for path in _unique_paths(source_paths)
    )
    receipt = build_material_delivery_package(
        DeliveryPackageBuildRequest(
            input_path=Path(input_path).expanduser().resolve(),
            output_dir=output_dir,
            manifest_path=manifest_path,
            source_receipts=receipts,
        )
    )
    return MaterialArtifactOutcome(
        material_manifest_paths=manifest_paths,
        material_package_paths=receipt.to_path_map(),
        material_package_receipt=_receipt_payload(receipt),
    )


def material_artifact_payload(**kwargs) -> dict[str, object]:
    """Project published material artifacts onto terminal payload fields."""

    outcome = publish_material_artifacts(**kwargs)
    if not outcome.material_manifest_paths:
        return {}
    payload: dict[str, object] = {
        "material_manifest_paths": outcome.material_manifest_paths,
    }
    if outcome.material_package_paths:
        payload["material_package_paths"] = outcome.material_package_paths
        payload["material_package_receipt"] = outcome.material_package_receipt
    return payload


def _artifact_enabled(config, artifact_name: str) -> bool:
    output = getattr(config, "output", None)
    if bool(getattr(output, artifact_name, False)):
        return True
    return any(
        bool(getattr(getattr(preset, "artifacts", None), artifact_name, False))
        for preset in list(getattr(config, "delivery_presets", ()) or ())
    )


def _material_manifest_payload(
    *,
    config,
    material_snapshot: ExecutionMaterialSnapshot | None,
    output_paths: dict[str, str],
    report_paths: list[str] | tuple[str, ...],
    compare_paths: dict[str, str],
    intermediate_paths: dict[str, str],
) -> dict[str, object]:
    input_profile = getattr(config, "input_source_profile", None)
    compliance = getattr(config, "compliance_profile", None)
    fields = _snapshot_fields(material_snapshot)
    assets = _snapshot_assets(material_snapshot)
    schema_id = (
        material_snapshot.material_contract_id
        if material_snapshot is not None
        else str(getattr(input_profile, "material_schema_id", "") or "")
    )
    schema_ids = list(
        dict.fromkeys(
            item
            for item in (
                schema_id,
                *list(getattr(input_profile, "material_schema_ids", ()) or ()),
            )
            if item
        )
    )
    required_fields = list(
        getattr(input_profile, "required_material_fields", ()) or ()
    )
    required_roles = list(getattr(input_profile, "required_image_roles", ()) or ())
    present_fields = {str(item["key"]) for item in fields}
    present_roles = {str(item["role"]) for item in assets}
    missing_fields = [key for key in required_fields if key not in present_fields]
    missing_roles = [role for role in required_roles if role not in present_roles]
    return {
        "kind": "material_attachment_manifest",
        "schema_version": 1,
        "visibility": "local_diagnostic",
        "status": "complete" if not missing_fields and not missing_roles else "incomplete",
        "material_schema": {
            "schema_id": schema_id,
            "schema_ids": schema_ids,
            "label": schema_id,
            "labels": schema_ids,
            "family": str(getattr(config, "mode_id", "") or ""),
            "required_field_keys": required_fields,
            "required_asset_roles": required_roles,
        },
        "material_profile": {
            "archive_id": (
                material_snapshot.package_ref.package_id
                if material_snapshot is not None
                else ""
            ),
            "profile_id": (
                material_snapshot.package_ref.package_id
                if material_snapshot is not None
                else ""
            ),
            "profile_name": (
                material_snapshot.package_display_name
                if material_snapshot is not None
                else ""
            ),
        },
        "input_contract": {
            "accepted_formats": list(
                getattr(input_profile, "accepted_formats", ()) or ()
            ),
            "structured_formats": list(
                getattr(input_profile, "structured_formats", ()) or ()
            ),
            "failure_policy": str(
                getattr(input_profile, "failure_policy", "") or ""
            ),
        },
        "compliance": {
            "profile_id": str(getattr(compliance, "profile_id", "") or ""),
            "rule_family": str(getattr(compliance, "rule_family", "") or ""),
            "count_profile_id": str(
                getattr(compliance, "count_profile_id", "") or ""
            ),
        },
        "fields": fields,
        "asset_roles": _asset_role_summary(assets, required_roles),
        "asset_items": assets,
        "missing": {
            "schema_ids": [] if schema_id or not schema_ids else schema_ids,
            "field_keys": missing_fields,
            "asset_roles": missing_roles,
        },
        "summary": {
            "field_count": len(fields),
            "asset_count": len(assets),
            "output_count": len(output_paths),
        },
        "execution": {
            "snapshot_id": material_snapshot.snapshot_id if material_snapshot else "",
            "run_id": material_snapshot.run_id if material_snapshot else "",
        },
        "delivery": {
            "output_paths": dict(output_paths),
            "compare_paths": dict(compare_paths),
            "report_paths": list(report_paths),
            "intermediate_paths": dict(intermediate_paths),
        },
    }


def _snapshot_fields(
    snapshot: ExecutionMaterialSnapshot | None,
) -> list[dict[str, object]]:
    if snapshot is None:
        return []
    values = dict(snapshot.package_field_values)
    for group in snapshot.groups:
        values.update(group.field_values)
    for record in snapshot.records:
        values.update(record.field_values)
    return [
        {
            "key": key,
            "label": key,
            "required": False,
            "present": bool(str(value or "")),
        }
        for key, value in sorted(values.items())
    ]


def _snapshot_assets(
    snapshot: ExecutionMaterialSnapshot | None,
) -> list[dict[str, object]]:
    if snapshot is None:
        return []
    assets: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for record in snapshot.records:
        for role, resources in record.resources.items():
            for resource in resources:
                identity = (role, resource.object_ref.object_id)
                if identity in seen:
                    continue
                seen.add(identity)
                path = Path(resource.source_path)
                assets.append(
                    {
                        "item_id": resource.object_ref.object_id,
                        "role": role,
                        "archive_dir": role,
                        "path": str(path),
                        "content_sha256": file_sha256(path),
                        "byte_size": path.stat().st_size,
                    }
                )
    return assets


def _asset_role_summary(
    assets: list[dict[str, object]],
    required_roles: list[str],
) -> list[dict[str, object]]:
    roles = {str(item["role"]) for item in assets}
    return [
        {
            "role": role,
            "required": role in required_roles,
            "present": role in roles,
        }
        for role in sorted(roles | set(required_roles))
    ]


def _snapshot_resource_paths(
    snapshot: ExecutionMaterialSnapshot | None,
) -> list[Path]:
    if snapshot is None:
        return []
    return [
        Path(resource.source_path)
        for record in snapshot.records
        for resources in record.resources.values()
        for resource in resources
    ]


def _existing_paths(values) -> list[Path]:
    return [
        path
        for value in values
        if str(value or "").strip()
        for path in (Path(str(value)).expanduser().resolve(),)
        if path.is_file()
    ]


def _unique_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        resolved = path.expanduser().resolve()
        identity = str(resolved).casefold()
        if identity not in seen:
            seen.add(identity)
            unique.append(resolved)
    return unique


def _receipt_payload(receipt: DeliveryPackageReceipt) -> dict[str, object]:
    return {
        "status": receipt.status,
        "copied_file_count": receipt.copied_file_count,
        "missing_reference_count": receipt.missing_reference_count,
        **receipt.to_path_map(),
    }


__all__ = [
    "MaterialArtifactOutcome",
    "material_artifact_payload",
    "publish_material_artifacts",
]
