from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import asdict, is_dataclass
from pathlib import Path

from src.config.material_context import MaterialExecutionContext
from src.config.material_schema_registry import (
    MATERIAL_SCHEMA_MAP,
    build_material_requirements,
    evaluate_material_requirements,
    missing_material_schema_ids,
)

from .material_preflight import (
    looks_like_remote_asset_path,
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


def _write_material_manifest(
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
) -> dict[str, str]:
    if not _material_manifest_artifact_enabled(config):
        return {}
    if not _material_manifest_should_write(config, material_context, material_diagnostics):
        return {}

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / f"{input_path.stem}_material_manifest.json"
    payload = _material_manifest_payload(
        input_path=input_path,
        output_dir=output_dir,
        config=config,
        material_context=material_context,
        material_diagnostics=list(material_diagnostics or []),
        output_paths=output_paths,
        compare_paths=compare_paths,
        report_paths=report_paths,
        intermediate_paths=intermediate_paths,
    )
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return {"material": str(manifest_path)}


def _write_material_package_artifacts(
    *,
    input_path: Path,
    output_dir: Path,
    config,
    material_manifest_paths: dict[str, str],
) -> dict[str, str]:
    if not _material_package_artifact_enabled(config):
        return {}
    manifests = _path_map(material_manifest_paths)
    if not manifests:
        return {}

    manifest_source = Path(manifests.get("material") or next(iter(manifests.values())))
    if not manifest_source.exists() or not manifest_source.is_file():
        return {}

    try:
        manifest_payload = json.loads(manifest_source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    package_dir = output_dir / f"{input_path.stem}_material_package"
    _reset_material_package_dir(package_dir, output_dir)
    package_dir.mkdir(parents=True, exist_ok=True)
    copied_files: list[dict[str, object]] = []
    missing_references: list[dict[str, object]] = []

    _copy_package_reference(
        manifest_source,
        package_dir=package_dir,
        category="manifest",
        target_subdir="manifest",
        copied_files=copied_files,
        missing_references=missing_references,
        preferred_name="material_manifest.json",
    )

    for asset in list(manifest_payload.get("asset_items", []) or []):
        if not isinstance(asset, dict):
            continue
        _copy_material_package_asset_reference(
            asset,
            package_dir=package_dir,
            copied_files=copied_files,
            missing_references=missing_references,
        )

    delivery = manifest_payload.get("delivery", {})
    if isinstance(delivery, dict):
        _copy_package_path_map(
            delivery.get("output_paths"),
            package_dir=package_dir,
            category="output",
            target_subdir="outputs",
            copied_files=copied_files,
            missing_references=missing_references,
        )
        _copy_package_path_map(
            delivery.get("compare_paths"),
            package_dir=package_dir,
            category="compare",
            target_subdir="compare",
            copied_files=copied_files,
            missing_references=missing_references,
        )
        _copy_package_path_map(
            delivery.get("intermediate_paths"),
            package_dir=package_dir,
            category="intermediate",
            target_subdir="intermediate",
            copied_files=copied_files,
            missing_references=missing_references,
        )
        for report_path in list(delivery.get("report_paths", []) or []):
            _copy_package_reference(
                Path(str(report_path or "")),
                package_dir=package_dir,
                category="report",
                target_subdir="reports",
                copied_files=copied_files,
                missing_references=missing_references,
            )

    package_manifest = {
        "kind": "material_delivery_package",
        "schema_version": 1,
        "input": str(input_path),
        "source_manifest": str(manifest_source),
        "status": _material_package_status(manifest_payload, missing_references),
        "material_schema": manifest_payload.get("material_schema", {}),
        "material_profile": manifest_payload.get("material_profile", {}),
        "missing": manifest_payload.get("missing", {}),
        "summary": manifest_payload.get("summary", {}),
        "files": copied_files,
        "missing_references": missing_references,
    }
    package_manifest_path = package_dir / "package_manifest.json"
    package_manifest_path.write_text(
        json.dumps(package_manifest, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    archive_report_path = package_dir / "archive_report.md"
    archive_report_path.write_text(
        _render_material_archive_report(manifest_payload, package_manifest),
        encoding="utf-8",
    )

    zip_path = output_dir / f"{input_path.stem}_material_package.zip"
    _write_package_zip(package_dir, zip_path)
    return {
        "directory": str(package_dir),
        "zip": str(zip_path),
        "report": str(archive_report_path),
        "package_manifest": str(package_manifest_path),
    }


def _copy_material_package_asset_reference(
    asset: dict[str, object],
    *,
    package_dir: Path,
    copied_files: list[dict[str, object]],
    missing_references: list[dict[str, object]],
) -> None:
    role = _normalize_manifest_key(asset.get("role", "asset")) or "asset"
    archive_subdir = _material_package_asset_subdir(asset, role)
    source = _material_package_asset_source(asset)
    if source:
        _copy_package_reference(
            source,
            package_dir=package_dir,
            category="asset",
            target_subdir=archive_subdir,
            copied_files=copied_files,
            missing_references=missing_references,
            role=role,
        )
        return
    missing_references.append(
        {
            "category": "asset",
            "key": "",
            "role": role,
            "source": _material_package_asset_source_text(asset),
            "reason": "source file missing",
        }
    )


def _material_package_asset_source(asset: dict[str, object]) -> Path | None:
    path = str(asset.get("path") or "").strip()
    path_is_remote = looks_like_remote_asset_path(path)
    if path and not path_is_remote:
        source = Path(path)
        if source.exists() and source.is_file():
            return source
    metadata = asset.get("metadata", {})
    if isinstance(metadata, dict):
        cache_path = str(metadata.get("cache_path") or "").strip()
        if cache_path and not path_is_remote:
            source = Path(cache_path)
            if source.exists() and source.is_file():
                return source
    if path:
        source = Path(path)
        if source.exists() and source.is_file():
            return source
    return None


def _material_package_asset_source_text(asset: dict[str, object]) -> str:
    path = str(asset.get("path") or "").strip()
    metadata = asset.get("metadata", {})
    if isinstance(metadata, dict):
        cache_path = str(metadata.get("cache_path") or "").strip()
        if cache_path and not looks_like_remote_asset_path(path):
            return cache_path
    return path


def _copy_package_path_map(
    value,
    *,
    package_dir: Path,
    category: str,
    target_subdir: str,
    copied_files: list[dict[str, object]],
    missing_references: list[dict[str, object]],
) -> None:
    for key, path in _path_map(value).items():
        source = Path(path)
        preferred_name = f"{_safe_package_filename(key)}_{source.name}"
        _copy_package_reference(
            source,
            package_dir=package_dir,
            category=category,
            target_subdir=target_subdir,
            copied_files=copied_files,
            missing_references=missing_references,
            key=key,
            preferred_name=preferred_name,
        )


def _material_package_asset_subdir(asset: dict[str, object], role: str) -> str:
    archive_dir = _safe_archive_dir(asset.get("archive_dir"))
    if not archive_dir:
        archive_dir = _safe_archive_dir(role) or "asset"
    return f"assets/{archive_dir}"


def _reset_material_package_dir(package_dir: Path, output_dir: Path) -> None:
    if not package_dir.exists():
        return
    try:
        resolved_package = package_dir.resolve()
        resolved_output = output_dir.resolve()
    except OSError:
        return
    if resolved_package == resolved_output:
        return
    if resolved_output not in resolved_package.parents:
        return
    shutil.rmtree(package_dir)


def _copy_package_reference(
    source: Path,
    *,
    package_dir: Path,
    category: str,
    target_subdir: str,
    copied_files: list[dict[str, object]],
    missing_references: list[dict[str, object]],
    key: str = "",
    role: str = "",
    preferred_name: str = "",
) -> None:
    source_text = str(source or "").strip()
    if not source_text or not source.exists() or not source.is_file():
        missing_references.append(
            {
                "category": category,
                "key": key,
                "role": role,
                "source": source_text,
                "reason": "source file missing",
            }
        )
        return

    target_dir = package_dir / target_subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_name = _safe_package_filename(preferred_name or source.name)
    target_path = _unique_package_path(target_dir / target_name)
    try:
        if source.resolve() != target_path.resolve():
            shutil.copy2(source, target_path)
    except OSError as exc:
        missing_references.append(
            {
                "category": category,
                "key": key,
                "role": role,
                "source": source_text,
                "reason": str(exc),
            }
        )
        return

    copied_files.append(
        {
            "category": category,
            "key": key,
            "role": role,
            "source": source_text,
            "path": _package_relative_path(target_path, package_dir),
        }
    )


def _material_package_status(
    manifest_payload: dict[str, object],
    missing_references: list[dict[str, object]],
) -> str:
    missing = manifest_payload.get("missing", {})
    if not isinstance(missing, dict):
        missing = {}
    has_missing_material = bool(
        list(missing.get("schema_ids", []) or [])
        or list(missing.get("field_keys", []) or [])
        or list(missing.get("asset_roles", []) or [])
    )
    return "incomplete" if has_missing_material or missing_references else "complete"


def _render_material_archive_report(
    manifest_payload: dict[str, object],
    package_manifest: dict[str, object],
) -> str:
    schema = manifest_payload.get("material_schema", {})
    profile = manifest_payload.get("material_profile", {})
    missing = manifest_payload.get("missing", {})
    summary = manifest_payload.get("summary", {})
    lines = [
        "# 资料交付包归档报告",
        "",
        f"- 状态: {package_manifest.get('status', 'incomplete')}",
        f"- Schema: {_report_value(schema, 'schema_id')} / {_report_value(schema, 'label')}",
        f"- 资料档案: {_report_value(profile, 'profile_name') or _report_value(profile, 'profile_id')}",
        f"- 字段: {summary.get('filled_field_count', 0)}/{summary.get('field_count', 0)} 已填写",
        f"- 材料: {summary.get('asset_item_count', 0)} 个文件",
        "",
        "## 缺失项",
        "",
    ]
    missing_schemas = list(missing.get("schema_ids", []) or []) if isinstance(missing, dict) else []
    missing_fields = list(missing.get("field_keys", []) or []) if isinstance(missing, dict) else []
    missing_assets = list(missing.get("asset_roles", []) or []) if isinstance(missing, dict) else []
    if not missing_schemas and not missing_fields and not missing_assets:
        lines.append("- 无")
    for schema_id in missing_schemas:
        lines.append(f"- Schema: {schema_id}")
    for field in missing_fields:
        lines.append(f"- 字段: {field}")
    for role in missing_assets:
        lines.append(f"- 材料: {role}")

    lines.extend(["", "## 字段清单", ""])
    fields = list(manifest_payload.get("fields", []) or [])
    if not fields:
        lines.append("- 无字段")
    for field in fields:
        if not isinstance(field, dict):
            continue
        marker = "已填" if field.get("present") else "缺失"
        required = "必填" if field.get("required") else "可选"
        lines.append(f"- {field.get('label') or field.get('key')} ({required}): {marker}")

    lines.extend(["", "## 材料清单", ""])
    roles = list(manifest_payload.get("asset_roles", []) or [])
    if not roles:
        lines.append("- 无材料")
    for role in roles:
        if not isinstance(role, dict):
            continue
        marker = "已提供" if role.get("present") else "缺失"
        required = "必填" if role.get("required") else "可选"
        lines.append(f"- {role.get('label') or role.get('role')} ({required}): {marker}")
        for item in list(role.get("items", []) or []):
            if not isinstance(item, dict):
                continue
            exists = "存在" if item.get("exists") else "路径不可用"
            lines.append(f"  - {item.get('label') or item.get('item_id')}: {exists}")

    lines.extend(["", "## 包内文件", ""])
    files = list(package_manifest.get("files", []) or [])
    if not files:
        lines.append("- 无")
    for file_item in files:
        if not isinstance(file_item, dict):
            continue
        category = str(file_item.get("category") or "")
        path = str(file_item.get("path") or "")
        lines.append(f"- [{category}] {path}")

    missing_refs = list(package_manifest.get("missing_references", []) or [])
    if missing_refs:
        lines.extend(["", "## 未复制引用", ""])
        for item in missing_refs:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- [{item.get('category', '')}] {item.get('source', '')}: {item.get('reason', '')}"
            )

    lines.append("")
    return "\n".join(lines)


def _report_value(value, key: str) -> str:
    return str(value.get(key, "") or "") if isinstance(value, dict) else ""


def _write_package_zip(package_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package_dir.rglob("*")):
            if not path.is_file():
                continue
            archive.write(path, _package_relative_path(path, package_dir))


def _package_relative_path(path: Path, package_dir: Path) -> str:
    try:
        return path.relative_to(package_dir).as_posix()
    except ValueError:
        return path.name


def _unique_package_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 2
    while True:
        candidate = parent / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _safe_package_filename(value: str) -> str:
    name = str(value or "").strip() or "file"
    for char in '<>:"\\|?*':
        name = name.replace(char, "_")
    return name.replace("/", "_")


def _material_manifest_should_write(
    config,
    material_context: MaterialExecutionContext,
    material_diagnostics: list[dict] | None,
) -> bool:
    profile = getattr(config, "input_source_profile", None)
    has_profile_requirements = bool(
        profile_material_schema_ids(profile)
        or list(getattr(profile, "required_material_fields", []) or [])
        or list(getattr(profile, "required_image_roles", []) or [])
    )
    return bool(
        has_profile_requirements
        or not material_context.is_empty()
        or list(material_diagnostics or [])
    )


def _material_manifest_payload(
    *,
    input_path: Path,
    output_dir: Path,
    config,
    material_context: MaterialExecutionContext,
    material_diagnostics: list[dict],
    output_paths: dict[str, str],
    compare_paths: dict[str, str],
    report_paths: list[str],
    intermediate_paths: dict[str, str],
) -> dict[str, object]:
    profile = getattr(config, "input_source_profile", None)
    compliance = getattr(config, "compliance_profile", None)
    schema_ids = profile_material_schema_ids(profile)
    schema_id = schema_ids[0] if schema_ids else ""
    missing_schema_ids = missing_material_schema_ids(schema_ids)
    schemas = [
        MATERIAL_SCHEMA_MAP[schema_id]
        for schema_id in schema_ids
        if schema_id in MATERIAL_SCHEMA_MAP
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
    missing_asset_roles = _unique_manifest_values(
        [
            *check.missing_asset_roles,
            *material_context.missing_required_asset_roles(),
        ]
    )
    field_specs = {
        field.key: field
        for schema in schemas
        for field in list(getattr(schema, "fields", ()) or ())
    }
    asset_specs = {
        role.role: role
        for schema in schemas
        for role in list(getattr(schema, "asset_roles", ()) or ())
    }
    field_keys = _unique_manifest_values(
        [
            *field_specs.keys(),
            *extra_fields,
            *material_context.entity_data.keys(),
        ]
    )
    asset_role_keys = _unique_manifest_values(
        [
            *asset_specs.keys(),
            *extra_roles,
            *[
                getattr(rule, "asset_role", "")
                for rule in list(getattr(material_context, "image_rules", []) or [])
            ],
            *[
                getattr(item, "role", "")
                for item in list(getattr(material_context, "asset_items", []) or [])
            ],
        ]
    )

    asset_items = list(getattr(material_context, "asset_items", []) or [])
    items_by_role: dict[str, list] = {}
    for item in asset_items:
        role = _normalize_manifest_key(getattr(item, "role", ""))
        if not role:
            continue
        items_by_role.setdefault(role, []).append(item)

    fields_payload = [
        _material_manifest_field_payload(
            key,
            field_specs.get(key),
            material_context.entity_data,
            required=key in requirements.required_field_keys,
        )
        for key in field_keys
    ]
    asset_roles_payload = [
        _material_manifest_asset_role_payload(
            role,
            asset_specs.get(role),
            items_by_role.get(role, []),
            required=role in requirements.required_asset_roles,
            missing=role in missing_asset_roles,
        )
        for role in asset_role_keys
    ]
    asset_items_payload = [
        _material_manifest_asset_item_payload(item, asset_specs.get(_normalize_manifest_key(item.role)))
        for item in asset_items
    ]
    image_rules_payload = [
        {
            "rule_id": str(getattr(rule, "rule_id", "") or ""),
            "asset_role": _normalize_manifest_key(getattr(rule, "asset_role", "")),
            "target": str(getattr(rule, "target", "") or ""),
            "width_cm": getattr(rule, "width_cm", None),
            "required": bool(getattr(rule, "required", False)),
        }
        for rule in list(getattr(material_context, "image_rules", []) or [])
    ]

    payload = {
        "kind": "material_attachment_manifest",
        "schema_version": 1,
        "input": str(input_path),
        "scene": {
            "strict_mode": bool(getattr(config, "strict_mode", True)),
            "default_delivery_preset_id": str(
                getattr(config, "default_delivery_preset_id", "") or ""
            ),
        },
        "material_profile": {
            "archive_id": str(material_context.archive_id or ""),
            "profile_id": str(material_context.profile_id or ""),
            "profile_name": str(material_context.profile_name or ""),
            "entity_assets_dir": str(material_context.entity_assets_dir or ""),
        },
        "material_schema": {
            "schema_id": schema_id,
            "schema_ids": list(requirements.schema_ids),
            "label": str(getattr(schema, "label", "") or schema_id),
            "labels": list(requirements.schema_labels),
            "family": str(getattr(schema, "family", "") or ""),
            "required_field_keys": list(requirements.required_field_keys),
            "required_asset_roles": list(requirements.required_asset_roles),
            "archive_directory_rules": [
                {
                    "role": role,
                    "archive_dir": _material_manifest_asset_archive_dir(spec, role),
                    "package_subdir": _material_manifest_asset_package_subdir(spec, role),
                }
                for role, spec in asset_specs.items()
                if _material_manifest_asset_archive_dir(spec, role)
            ],
        },
        "input_contract": {
            "accepted_formats": list(getattr(profile, "accepted_formats", []) or []),
            "structured_formats": list(getattr(profile, "structured_formats", []) or []),
            "failure_policy": str(getattr(profile, "failure_policy", "") or ""),
        },
        "compliance": {
            "profile_id": str(getattr(compliance, "profile_id", "") or ""),
            "rule_family": str(getattr(compliance, "rule_family", "") or ""),
            "count_profile_id": str(getattr(compliance, "count_profile_id", "") or ""),
        },
        "fields": fields_payload,
        "asset_roles": asset_roles_payload,
        "asset_items": asset_items_payload,
        "image_rules": image_rules_payload,
        "replacements": _plain_data(list(getattr(material_context, "replacements", []) or [])),
        "missing": {
            "schema_ids": list(missing_schema_ids),
            "field_keys": list(check.missing_field_keys),
            "asset_roles": list(missing_asset_roles),
        },
        "diagnostics": material_diagnostics,
        "delivery": {
            "output_paths": _path_map(output_paths),
            "compare_paths": _path_map(compare_paths),
            "report_paths": [str(path) for path in report_paths],
            "intermediate_paths": _path_map(intermediate_paths),
        },
        "summary": {
            "field_count": len(fields_payload),
            "filled_field_count": sum(1 for item in fields_payload if item["present"]),
            "asset_role_count": len(asset_roles_payload),
            "asset_item_count": len(asset_items_payload),
            "missing_schema_count": len(missing_schema_ids),
            "missing_field_count": len(check.missing_field_keys),
            "missing_asset_count": len(missing_asset_roles),
            "diagnostics_count": len(material_diagnostics),
        },
    }
    return payload


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
    return {
        "role": role,
        "label": str(getattr(spec, "label", "") or role),
        "required": bool(required),
        "accepted_types": list(getattr(spec, "accepted_types", ()) or ()),
        "archive_dir": _material_manifest_asset_archive_dir(spec, role),
        "package_subdir": _material_manifest_asset_package_subdir(spec, role),
        "present": bool(items),
        "missing": bool(missing),
        "items": [
            _material_manifest_asset_item_payload(item, spec)
            for item in items
        ],
    }


def _material_manifest_asset_item_payload(item, spec) -> dict[str, object]:
    path = str(getattr(item, "path", "") or "")
    role = _normalize_manifest_key(getattr(item, "role", ""))
    return {
        "item_id": str(getattr(item, "item_id", "") or ""),
        "label": str(getattr(item, "label", "") or ""),
        "role": role,
        "path": path,
        "exists": bool(path and Path(path).exists()),
        "mime_type": str(getattr(item, "mime_type", "") or ""),
        "tags": list(getattr(item, "tags", []) or []),
        "width_cm": getattr(item, "width_cm", None),
        "metadata": {
            str(key): str(value)
            for key, value in dict(getattr(item, "metadata", {}) or {}).items()
            if str(key or "").strip() and str(value or "").strip()
        },
        "kind": _material_manifest_asset_kind(item, spec),
        "archive_dir": _material_manifest_asset_archive_dir(spec, role),
        "package_subdir": _material_manifest_asset_package_subdir(spec, role),
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


def _path_map(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): str(path)
        for key, path in value.items()
        if str(key or "").strip() and str(path or "").strip()
    }


def _unique_manifest_values(values) -> tuple[str, ...]:
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


def _plain_data(value):
    if is_dataclass(value) and not isinstance(value, type):
        return _plain_data(asdict(value))
    if isinstance(value, dict):
        return {str(key): _plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_data(item) for item in value]
    return value



__all__ = [
    "_path_map",
    "_unique_manifest_values",
    "_write_material_manifest",
    "_write_material_package_artifacts",
]
