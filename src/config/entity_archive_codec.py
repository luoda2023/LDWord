"""JSON codec and package-relative path rules for material archives."""

from __future__ import annotations

import copy
from dataclasses import replace
import json
from pathlib import Path
from typing import Any

from src.config.attachment_materials import AttachmentBinding
from src.config.atomic_io import atomic_write_text
from src.config.content_artifacts import ContentMaterialBinding
from src.config.entity_archive_validation import (
    first_payload_difference,
    validate_entity_archive_wire_payload,
)
from src.config.entity_artifact_gateway import (
    ContentArtifactRepository,
    default_content_artifact_repository,
)
from src.config.entity_models import (
    ENTITY_PACKAGE_VERSION,
    AssetBinding,
    EntityArchive,
    EntityProfile,
    normalize_asset_binding,
)
from src.config.library import CONFIG_LIBRARY_ROOT


def load_entity_archive(
    path: str | Path,
    *,
    content_artifact_repository: ContentArtifactRepository | None = None,
) -> EntityArchive:
    """从 JSON 文件加载实体档案。"""
    source = Path(path)
    data = json.loads(
        source.read_text(encoding="utf-8"),
        parse_constant=_reject_json_constant,
    )
    if not isinstance(data, dict):
        raise ValueError("material_package_root_type_invalid:object_required")

    raw_version = data.get("version", 0)
    if type(raw_version) is not int:
        raise ValueError("material_package_version_invalid")
    if raw_version != ENTITY_PACKAGE_VERSION:
        raise ValueError(
            f"material_package_version_unsupported:{raw_version}"
        )

    validate_entity_archive_wire_payload(data)
    package_kind = data["kind"]
    if package_kind != "alavette.material_package":
        raise ValueError(f"material_package_kind_invalid:{package_kind}")
    _validate_package_id(data["package_id"])

    profiles: list[EntityProfile] = []
    for profile_index, raw_profile in enumerate(data["profiles"]):
        profile_data = copy.deepcopy(raw_profile)
        _resolve_profile_asset_paths(profile_data, source.parent)
        profile = EntityProfile(**profile_data)
        canonical_profile = _profile_payload(profile, source.parent)
        difference = first_payload_difference(raw_profile, canonical_profile)
        if difference:
            raise ValueError(
                "material_package_profile_not_canonical:"
                f"{profile_index}:{difference}"
            )
        profiles.append(profile)
    archive = EntityArchive(
        archive_id=data["archive_id"],
        archive_name=data["archive_name"],
        profiles=profiles,
        kind=package_kind,
        version=raw_version,
        mode_id=data["mode_id"],
        package_id=data["package_id"],
        material_schema_ids=list(data["material_schema_ids"]),
        source_path=str(source.resolve()),
    )
    vendored_root = source.parent / "content_artifacts" / "sha256"
    content_bindings = tuple(
        binding
        for profile in archive.profiles
        for binding in profile.content_bindings.values()
    )
    if vendored_root.is_dir() and content_bindings:
        repository = content_artifact_repository or default_content_artifact_repository(
            CONFIG_LIBRARY_ROOT / "content_artifacts"
        )
        for binding in content_bindings:
            repository.install_vendored(
                vendored_root / binding.artifact_ref.artifact_id
            )
    return archive

def save_entity_archive(archive: EntityArchive, path: str | Path) -> None:
    """保存实体档案到 JSON 文件。"""
    target = Path(path)
    payload = _archive_payload(archive, target)
    _validate_archive_payload_for_save(payload, target)
    atomic_write_text(
        target,
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )


def _archive_payload(archive: EntityArchive, target: Path) -> dict[str, object]:
    return {
        "kind": archive.kind,
        "version": _archive_version(archive),
        "mode_id": archive.mode_id,
        "package_id": _archive_package_id(archive, target),
        "material_schema_ids": list(archive.material_schema_ids),
        "archive_id": archive.archive_id,
        "archive_name": archive.archive_name,
        "profiles": [
            _profile_payload(profile, target.parent)
            for profile in archive.profiles
        ],
    }


def _archive_version(archive: EntityArchive) -> int:
    version = archive.version
    if type(version) is not int:
        raise ValueError("material_package_version_invalid")
    if version != ENTITY_PACKAGE_VERSION:
        raise ValueError(f"material_package_version_unsupported:{version}")
    return version


def _archive_package_id(archive: EntityArchive, target: Path) -> object:
    if archive.package_id != "":
        return archive.package_id
    if archive.archive_id != "":
        return archive.archive_id
    return target.stem


def _validate_archive_payload_for_save(
    payload: dict[str, object],
    target: Path,
) -> None:
    """Prove the exact payload-to-be-written satisfies the current loader."""

    validate_entity_archive_wire_payload(payload)
    if payload["kind"] != "alavette.material_package":
        raise ValueError(f"material_package_kind_invalid:{payload['kind']}")
    _validate_package_id(payload["package_id"])
    profiles = payload["profiles"]
    if not isinstance(profiles, list):
        raise AssertionError("wire validator accepted non-list profiles")
    for profile_index, raw_profile in enumerate(profiles):
        if not isinstance(raw_profile, dict):
            raise AssertionError("wire validator accepted non-object profile")
        profile_data = copy.deepcopy(raw_profile)
        _resolve_profile_asset_paths(profile_data, target.parent)
        profile = EntityProfile(**profile_data)
        canonical_profile = _profile_payload(profile, target.parent)
        difference = first_payload_difference(raw_profile, canonical_profile)
        if difference:
            raise ValueError(
                "material_package_profile_not_canonical:"
                f"{profile_index}:{difference}"
            )


def _validate_package_id(value: object) -> None:
    if type(value) is not str:
        raise ValueError("material_package_package_id_invalid")
    package_id = value.strip()
    forbidden = '<>:"/\\|?*'
    if (
        not package_id
        or package_id != value
        or package_id in {".", ".."}
        or package_id.endswith((".", " "))
        or any(char in forbidden or ord(char) < 32 for char in package_id)
    ):
        raise ValueError("material_package_package_id_invalid")


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"material_package_json_constant_invalid:{value}")


def _profile_payload(
    profile: EntityProfile,
    package_dir: Path,
) -> dict[str, object]:
    return {
        "profile_id": profile.profile_id,
        "profile_name": profile.profile_name,
        "fields": profile.fields,
        "assets_dir": _stored_package_path(profile.assets_dir, package_dir),
        "field_scopes": profile.field_scopes,
        "field_functions": profile.field_functions,
        "timeline_plans": profile.timeline_plans,
        "declared_field_keys": profile.declared_field_keys,
        "field_sources": profile.field_sources,
        "field_aliases": profile.field_aliases,
        "asset_paths": {
            role: _stored_package_path(value, package_dir)
            for role, value in profile.asset_paths.items()
        },
        "asset_bindings": {
            role: _asset_binding_payload(binding, package_dir)
            for role, binding in profile.asset_bindings.items()
        },
        "asset_metadata": profile.asset_metadata,
        "asset_token_specs": [
            {
                "token_id": spec.token_id,
                "token": spec.token,
                "label": spec.label,
                "cardinality": spec.cardinality,
                "source_kind": spec.source_kind,
                "order": spec.order,
                "required": spec.required,
                "recursive": spec.recursive,
                "min_items": spec.min_items,
                "max_items": spec.max_items,
                "order_policy": spec.order_policy,
                "naming_template": spec.naming_template,
            }
            for spec in profile.asset_token_specs
        ],
        "asset_items": [
            _asset_item_payload(item, package_dir)
            for item in profile.asset_items
        ],
        "asset_item_history": profile.asset_item_history,
        "image_material_rules": {
            rule_id: rule.to_dict()
            for rule_id, rule in profile.image_material_rules.items()
        },
        "content_bindings": {
            content_id: _content_binding_payload(binding, package_dir)
            for content_id, binding in profile.content_bindings.items()
        },
        "content_rules": [rule.to_dict() for rule in profile.content_rules],
        "attachment_role_specs": [
            spec.to_dict() for spec in profile.attachment_role_specs
        ],
        "attachment_bindings": {
            role: _attachment_binding_payload(binding, package_dir)
            for role, binding in profile.attachment_bindings.items()
        },
    }


def _resolve_profile_asset_paths(profile_data: dict[str, Any], package_dir: Path) -> None:
    profile_data["assets_dir"] = _resolved_package_path(
        profile_data.get("assets_dir", ""),
        package_dir,
    )
    profile_data["asset_paths"] = {
        str(role): _resolved_package_path(value, package_dir)
        for role, value in dict(profile_data.get("asset_paths", {}) or {}).items()
    }
    resolved_bindings: dict[str, AssetBinding] = {}
    for role, raw_binding in dict(profile_data.get("asset_bindings", {}) or {}).items():
        binding = normalize_asset_binding(str(role), raw_binding)
        binding.source_path = _resolved_package_path(binding.source_path, package_dir)
        resolved_items: list[dict[str, Any]] = []
        for raw_item in list(binding.items or []):
            item = dict(raw_item) if isinstance(raw_item, dict) else {}
            item["path"] = _resolved_package_path(item.get("path", ""), package_dir)
            if "source_path" in item:
                item["source_path"] = _resolved_package_path(
                    item.get("source_path", ""),
                    package_dir,
                )
            resolved_items.append(item)
        binding.items = resolved_items
        resolved_bindings[binding.role] = binding
    profile_data["asset_bindings"] = resolved_bindings
    items: list[dict[str, Any]] = []
    for raw in list(profile_data.get("asset_items", []) or []):
        item = dict(raw) if isinstance(raw, dict) else {}
        item["path"] = _resolved_package_path(item.get("path", ""), package_dir)
        if "source_path" in item:
            item["source_path"] = _resolved_package_path(
                item.get("source_path", ""),
                package_dir,
            )
        items.append(item)
    profile_data["asset_items"] = items
    content_bindings: dict[str, ContentMaterialBinding] = {}
    for raw_content_id, raw_binding in dict(
        profile_data.get("content_bindings", {}) or {}
    ).items():
        binding = (
            copy.deepcopy(raw_binding)
            if isinstance(raw_binding, ContentMaterialBinding)
            else ContentMaterialBinding.from_dict(
                raw_binding if isinstance(raw_binding, dict) else {}
            )
        )
        key = str(raw_content_id or binding.content_id).strip()
        if key != binding.content_id:
            raise ValueError(
                f"material_package_content_id_mismatch:{key}:{binding.content_id}"
            )
        content_bindings[binding.content_id] = binding
    profile_data["content_bindings"] = content_bindings

    attachment_bindings: dict[str, AttachmentBinding] = {}
    for raw_role, raw_binding in dict(
        profile_data.get("attachment_bindings", {}) or {}
    ).items():
        binding = (
            copy.deepcopy(raw_binding)
            if isinstance(raw_binding, AttachmentBinding)
            else AttachmentBinding.from_dict(
                raw_binding if isinstance(raw_binding, dict) else {}
            )
        )
        role = str(raw_role or binding.role).strip()
        if role != binding.role:
            raise ValueError(
                f"material_package_attachment_role_mismatch:{role}:{binding.role}"
            )
        resolved_items = tuple(
            replace(
                item,
                file_ref=replace(
                    item.file_ref,
                    source_path=_resolved_typed_package_path(
                        item.file_ref.source_path,
                        package_dir,
                        domain="attachment",
                    ),
                ),
            )
            for item in binding.items
        )
        attachment_bindings[binding.role] = replace(
            binding,
            source_path=_resolved_typed_package_path(
                binding.source_path,
                package_dir,
                domain="attachment_source",
            ),
            items=resolved_items,
        )
    profile_data["attachment_bindings"] = attachment_bindings

def _resolved_package_path(value: object, package_dir: Path) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    candidate = Path(text)
    if _is_absolute_path_text(text, candidate):
        return text
    root = package_dir.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"material_package_path_escape:{text}") from exc
    return str(resolved)

def _resolved_typed_package_path(
    value: object,
    package_dir: Path,
    *,
    domain: str,
) -> str:
    """Resolve a v3 typed path without allowing relative package escape."""

    text = str(value or "").strip()
    if not text:
        return ""
    candidate = Path(text)
    if _is_absolute_path_text(text, candidate):
        return text
    root = package_dir.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"material_package_{domain}_path_escape:{text}") from exc
    return str(resolved)

def _stored_package_path(value: object, package_dir: Path) -> str:
    if type(value) is not str:
        raise ValueError(
            f"material_package_path_type_invalid:{type(value).__name__}"
        )
    text = value.strip()
    if text != value:
        raise ValueError("material_package_path_whitespace_invalid")
    if not text:
        return ""
    candidate = Path(text)
    if not _is_absolute_path_text(text, candidate):
        root = package_dir.resolve()
        resolved = (root / candidate).resolve()
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"material_package_path_escape:{text}") from exc
    # Preserve foreign-platform absolute paths verbatim.  A POSIX path such as
    # /tmp/assets is not absolute to WindowsPath, but it must not silently turn
    # into <drive>:\\tmp\\assets during a read/save round trip.
    if not candidate.is_absolute():
        return text
    try:
        return candidate.resolve().relative_to(package_dir.resolve()).as_posix()
    except (OSError, ValueError):
        return str(candidate)

def _is_absolute_path_text(text: str, candidate: Path) -> bool:
    return (
        candidate.is_absolute()
        or text.startswith(("/", "\\\\"))
        or (len(text) >= 3 and text[1] == ":" and text[2] in {"/", "\\"})
    )

def _asset_binding_payload(binding: AssetBinding, package_dir: Path) -> dict[str, Any]:
    normalized = normalize_asset_binding(binding.role, binding)
    return {
        "role": normalized.role,
        "cardinality": normalized.cardinality,
        "source_kind": normalized.source_kind,
        "source_path": _stored_package_path(normalized.source_path, package_dir),
        "recursive": normalized.recursive,
        "order_policy": normalized.order_policy,
        "naming_template": normalized.naming_template,
        "min_items": normalized.min_items,
        "max_items": normalized.max_items,
        "items": [
            _asset_item_payload(item, package_dir)
            for item in normalized.items
        ],
        "snapshot_revision": normalized.snapshot_revision,
    }


def _asset_item_payload(
    value: object,
    package_dir: Path,
) -> dict[str, Any]:
    item = dict(value) if isinstance(value, dict) else {}
    item["path"] = _stored_package_path(item.get("path", ""), package_dir)
    if "source_path" in item:
        item["source_path"] = _stored_package_path(
            item.get("source_path", ""),
            package_dir,
        )
    return item

def _content_binding_payload(
    binding: ContentMaterialBinding,
    package_dir: Path,
) -> dict[str, object]:
    del package_dir
    return binding.to_dict()

def _attachment_binding_payload(
    binding: AttachmentBinding,
    package_dir: Path,
) -> dict[str, object]:
    payload = binding.to_dict()
    payload["source_path"] = _stored_package_path(
        binding.source_path,
        package_dir,
    )
    serialized_items: list[dict[str, object]] = []
    for item in binding.items:
        item_payload = item.to_dict()
        file_payload = dict(item_payload["file_ref"])
        file_payload["source_path"] = _stored_package_path(
            item.file_ref.source_path,
            package_dir,
        )
        item_payload["file_ref"] = file_payload
        serialized_items.append(item_payload)
    payload["items"] = serialized_items
    return payload

__all__ = [
    "load_entity_archive",
    "save_entity_archive",
]
