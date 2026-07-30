"""Canonical local asset resolution.

This module is intentionally Qt-free.  A role may be owned by exactly one
profile source: ``asset_bindings``, ``asset_items``, ``asset_paths``, or
``assets_dir``.  Resolution rejects ambiguous roles instead of selecting a
source by precedence.
"""

from __future__ import annotations

import copy
import hashlib
import mimetypes
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from src.config.entity_models import AssetBinding, EntityProfile
from src.config.materials import (
    IMAGE_EXTENSIONS,
    AssetItem,
    is_supported_image_path,
    normalize_asset_role,
    scan_asset_collection,
)


@dataclass(frozen=True, slots=True)
class AssetDiagnostic:
    code: str
    severity: str = "error"
    role: str = ""
    path: str = ""
    message: str = ""
    item_id: str = ""
    label: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class AssetResolution:
    items: list[AssetItem] = field(default_factory=list)
    diagnostics: list[AssetDiagnostic] = field(default_factory=list)
    bindings: dict[str, AssetBinding] = field(default_factory=dict)
    owners: dict[str, str] = field(default_factory=dict)

    def items_for_role(self, role: str) -> list[AssetItem]:
        normalized = normalize_asset_role(role)
        return [item for item in self.items if normalize_asset_role(item.role) == normalized]

    @property
    def ok(self) -> bool:
        return not any(item.severity == "error" for item in self.diagnostics)


def resolve_profile_assets(
    profile: EntityProfile,
    *,
    role_specs: Sequence[object] = (),
    force_rescan: bool = False,
) -> AssetResolution:
    """Resolve a profile after proving that every role has one source owner."""

    result = AssetResolution()
    image_roles = _image_role_names(role_specs)
    bindings_by_role = _profile_bindings_by_role(profile, result.diagnostics)
    items_by_role = _profile_items_by_role(profile, result.diagnostics)
    paths_by_role = _profile_paths_by_role(profile, result.diagnostics)
    collection_by_role = _profile_collection_by_role(profile, result.diagnostics)
    sources_by_role: dict[str, set[str]] = {}
    for source_name, role_values in (
        ("asset_bindings", bindings_by_role),
        ("asset_items", items_by_role),
        ("asset_paths", paths_by_role),
        ("assets_dir", collection_by_role),
    ):
        for role in role_values:
            sources_by_role.setdefault(role, set()).add(source_name)

    rejected_roles: set[str] = set()
    for role, source_names in sorted(sources_by_role.items()):
        if len(source_names) != 1:
            rejected_roles.add(role)
            result.diagnostics.append(
                AssetDiagnostic(
                    code="asset_source_conflict",
                    role=role,
                    message=(
                        f"asset role {role!r} has multiple owners: "
                        f"{', '.join(sorted(source_names))}"
                    ),
                )
            )
            continue
        result.owners[role] = next(iter(source_names))

    for role, bindings in bindings_by_role.items():
        if role in rejected_roles or len(bindings) != 1:
            if len(bindings) > 1:
                rejected_roles.add(role)
                result.owners.pop(role, None)
                result.diagnostics.append(
                    _duplicate_source_role_diagnostic(role, "asset_bindings")
                )
            continue
        binding = bindings[0]
        binding_resolution = resolve_asset_binding(binding, force_rescan=force_rescan)
        result.bindings[role] = binding_resolution.bindings.get(role, binding)
        result.items.extend(binding_resolution.items)
        result.diagnostics.extend(binding_resolution.diagnostics)

    for role, items in items_by_role.items():
        if role in rejected_roles:
            continue
        for item in items:
            resolved_item = _validated_profile_item(
                item,
                source_name="asset_items",
                image_role=role in image_roles,
                diagnostics=result.diagnostics,
            )
            if resolved_item is not None:
                result.items.append(resolved_item)

    for role, items in paths_by_role.items():
        if role in rejected_roles or len(items) != 1:
            if len(items) > 1:
                rejected_roles.add(role)
                result.owners.pop(role, None)
                result.diagnostics.append(
                    _duplicate_source_role_diagnostic(role, "asset_paths")
                )
            continue
        resolved_item = _validated_profile_item(
            items[0],
            source_name="asset_paths",
            image_role=role in image_roles,
            diagnostics=result.diagnostics,
        )
        if resolved_item is not None:
            result.items.append(resolved_item)

    for role, items in collection_by_role.items():
        if role in rejected_roles:
            continue
        for item in items:
            resolved_item = _validated_profile_item(
                item,
                source_name="assets_dir",
                image_role=True,
                diagnostics=result.diagnostics,
            )
            if resolved_item is None:
                continue
            resolved_item.source_path = str(profile.assets_dir)
            try:
                resolved_item.original_relative_path = (
                    Path(resolved_item.path)
                    .relative_to(Path(profile.assets_dir))
                    .as_posix()
                )
            except (OSError, ValueError):
                resolved_item.original_relative_path = Path(resolved_item.path).name
            resolved_item.normalized_name = Path(resolved_item.path).name
            result.items.append(resolved_item)

    if rejected_roles:
        result.items = [
            item
            for item in result.items
            if normalize_asset_role(item.role) not in rejected_roles
        ]
        for role in rejected_roles:
            result.bindings.pop(role, None)

    _apply_role_metadata(result.items, profile.asset_metadata)
    result.items = _stable_asset_item_order(result.items)
    result.diagnostics.extend(_duplicate_content_diagnostics(result.items))
    result.diagnostics.extend(_role_contract_diagnostics(result, role_specs))
    result.diagnostics = _dedupe_diagnostics(result.diagnostics)
    return result


def _profile_bindings_by_role(
    profile: EntityProfile,
    diagnostics: list[AssetDiagnostic],
) -> dict[str, list[AssetBinding]]:
    result: dict[str, list[AssetBinding]] = {}
    for raw_role, raw_binding in dict(profile.asset_bindings or {}).items():
        role = normalize_asset_role(raw_role)
        if not role:
            diagnostics.append(
                AssetDiagnostic(
                    code="asset_binding_role_missing",
                    message="asset_bindings contains an entry without a role",
                )
            )
            continue
        binding = copy.deepcopy(raw_binding)
        binding.role = role
        result.setdefault(role, []).append(binding)
    return result


def _profile_items_by_role(
    profile: EntityProfile,
    diagnostics: list[AssetDiagnostic],
) -> dict[str, list[AssetItem]]:
    result: dict[str, list[AssetItem]] = {}
    for raw in list(profile.asset_items or []):
        if not isinstance(raw, Mapping):
            diagnostics.append(
                AssetDiagnostic(
                    code="asset_item_invalid",
                    message="asset_items entries must be mappings",
                )
            )
            continue
        item = asset_item_from_payload(raw)
        role = normalize_asset_role(item.role)
        if not role:
            diagnostics.append(
                AssetDiagnostic(
                    code="asset_item_role_missing",
                    path=item.path,
                    message="asset_items contains an entry without a role",
                )
            )
            continue
        item.role = role
        result.setdefault(role, []).append(item)
    return result


def _profile_paths_by_role(
    profile: EntityProfile,
    diagnostics: list[AssetDiagnostic],
) -> dict[str, list[AssetItem]]:
    result: dict[str, list[AssetItem]] = {}
    for raw_role, raw_path in dict(profile.asset_paths or {}).items():
        role = normalize_asset_role(raw_role)
        path_text = str(raw_path or "").strip()
        if not role:
            diagnostics.append(
                AssetDiagnostic(
                    code="asset_path_role_missing",
                    path=path_text,
                    message="asset_paths contains an entry without a role",
                )
            )
            continue
        path = Path(path_text) if path_text else Path()
        result.setdefault(role, []).append(
            AssetItem(
                item_id=role,
                label=path.stem or role,
                role=role,
                path=path_text,
                mime_type=mimetypes.guess_type(path_text)[0] or "",
                source_path=path_text,
                original_relative_path=path.name if path_text else "",
                normalized_name=path.name if path_text else "",
            )
        )
    return result


def _profile_collection_by_role(
    profile: EntityProfile,
    diagnostics: list[AssetDiagnostic],
) -> dict[str, list[AssetItem]]:
    root_text = str(profile.assets_dir or "").strip()
    if not root_text:
        return {}
    root = Path(root_text)
    if not root.is_dir():
        diagnostics.append(
            AssetDiagnostic(
                code="asset_directory_missing",
                path=root_text,
                message="assets_dir does not identify an existing directory",
            )
        )
        return {}
    try:
        collection = scan_asset_collection(root)
    except OSError:
        diagnostics.append(
            AssetDiagnostic(
                code="asset_directory_unreadable",
                path=root_text,
                message="assets_dir cannot be read",
            )
        )
        return {}
    if not collection.items:
        diagnostics.append(
            AssetDiagnostic(
                code="asset_directory_empty",
                path=root_text,
                message="assets_dir contains no supported image files",
            )
        )
        return {}
    result: dict[str, list[AssetItem]] = {}
    for item in collection.items:
        role = normalize_asset_role(item.role)
        if not role:
            diagnostics.append(
                AssetDiagnostic(
                    code="asset_item_role_missing",
                    path=item.path,
                    message="assets_dir produced an item without a role",
                )
            )
            continue
        item.role = role
        result.setdefault(role, []).append(item)
    return result


def _duplicate_source_role_diagnostic(role: str, source_name: str) -> AssetDiagnostic:
    return AssetDiagnostic(
        code="asset_source_role_duplicate",
        role=role,
        message=f"asset role {role!r} is declared more than once in {source_name}",
    )


def _profile_item_path(item: AssetItem) -> str:
    direct = str(item.path or "").strip()
    if direct:
        return direct
    for key in (
        "cache_path",
        "cachePath",
        "cached_path",
        "cachedPath",
        "local_path",
        "localPath",
        "local_cache_path",
        "localCachePath",
        "resolved_path",
        "resolvedPath",
        "download_path",
        "downloadPath",
        "asset_path",
        "assetPath",
    ):
        value = str(item.metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def _validated_profile_item(
    item: AssetItem,
    *,
    source_name: str,
    image_role: bool,
    diagnostics: list[AssetDiagnostic],
) -> AssetItem | None:
    resolved = copy.deepcopy(item)
    resolved.role = normalize_asset_role(resolved.role)
    path_text = _profile_item_path(resolved)
    path = Path(path_text) if path_text else Path()
    if not path_text or not path.is_file():
        diagnostics.append(
            AssetDiagnostic(
                code="asset_file_missing",
                role=resolved.role,
                path=path_text,
                message=(
                    f"{source_name} for asset role {resolved.role!r} does not "
                    "identify an existing file"
                ),
                item_id=resolved.item_id,
                label=resolved.label,
                metadata=dict(resolved.metadata),
            )
        )
        return None
    if image_role and not is_supported_image_path(path):
        diagnostics.append(_unsupported_image_diagnostic(resolved.role, path_text))
        return None
    content_hash = file_content_revision(path)
    if not content_hash:
        diagnostics.append(
            AssetDiagnostic(
                code="asset_file_unreadable",
                role=resolved.role,
                path=path_text,
                message=f"{source_name} for asset role {resolved.role!r} is unreadable",
                item_id=resolved.item_id,
                label=resolved.label,
                metadata=dict(resolved.metadata),
            )
        )
        return None
    resolved.path = path_text
    resolved.source_path = resolved.source_path or path_text
    resolved.original_relative_path = resolved.original_relative_path or path.name
    resolved.normalized_name = resolved.normalized_name or path.name
    resolved.content_hash = content_hash
    return resolved


def resolve_asset_binding(
    binding: AssetBinding,
    *,
    force_rescan: bool = False,
) -> AssetResolution:
    role = normalize_asset_role(binding.role)
    normalized = copy.deepcopy(binding)
    normalized.role = role
    result = AssetResolution(bindings={role: normalized} if role else {})
    if not role:
        result.diagnostics.append(
            AssetDiagnostic(
                code="asset_binding_role_missing",
                message="图片绑定缺少角色。",
            )
        )
        return result

    if normalized.items and not force_rescan:
        result.items = _snapshot_items(normalized, result.diagnostics)
        source = Path(str(normalized.source_path or ""))
        actual_revision = (
            directory_content_revision(source, allowed_extensions=IMAGE_EXTENSIONS)
            if source.is_dir()
            else file_content_revision(source)
        )
        if (
            normalized.snapshot_revision
            and actual_revision
            and normalized.snapshot_revision != actual_revision
        ):
            result.diagnostics.append(
                AssetDiagnostic(
                    code="asset_binding_snapshot_stale",
                    severity="warning",
                    role=role,
                    path=str(source),
                    message="图片绑定目录内容已变化，请重新扫描以更新顺序和规范名称。",
                )
            )
        _append_binding_count_diagnostics(normalized, result.items, result.diagnostics)
        result.diagnostics.extend(_duplicate_content_diagnostics(result.items))
        return result

    if normalized.source_kind == "directory" or normalized.cardinality == "multiple":
        result.items = _scan_directory_binding(normalized, result.diagnostics)
    elif normalized.source_kind == "files":
        result.items = _snapshot_items(normalized, result.diagnostics)
    else:
        result.items = _resolve_single_file_binding(normalized, result.diagnostics)

    _append_binding_count_diagnostics(normalized, result.items, result.diagnostics)
    result.diagnostics.extend(_duplicate_content_diagnostics(result.items))
    return result


def refresh_asset_binding(binding: AssetBinding) -> tuple[AssetBinding, AssetResolution]:
    """Rescan a binding and return a persisted snapshot without mutating input."""

    resolution = resolve_asset_binding(binding, force_rescan=True)
    refreshed = copy.deepcopy(binding)
    refreshed.role = normalize_asset_role(binding.role)
    refreshed.items = [asset_item_payload(item) for item in resolution.items]
    source = Path(str(refreshed.source_path or ""))
    refreshed.snapshot_revision = (
        directory_content_revision(source, allowed_extensions=IMAGE_EXTENSIONS)
        if source.is_dir()
        else file_content_revision(source)
    )
    resolution.bindings[refreshed.role] = refreshed
    return refreshed, resolution


def natural_relative_path_key(value: str | Path) -> tuple[tuple[tuple[int, object], ...], ...]:
    """Return a deterministic, Unicode-normalized natural path key."""

    text = str(value or "").replace("\\", "/")
    parts = [part for part in text.split("/") if part]
    return tuple(_natural_text_key(part) for part in parts)


def asset_item_from_payload(value: Mapping[str, object]) -> AssetItem:
    metadata = value.get("metadata", {})
    if not isinstance(metadata, Mapping):
        metadata = {}
    sequence = _optional_positive_int(value.get("sequence"))
    if sequence is None:
        sequence = _sequence_from_metadata(metadata)
    width = value.get("width_cm")
    try:
        width_cm = float(width) if width not in (None, "") else None
    except (TypeError, ValueError):
        width_cm = None
    raw_tags = value.get("tags", [])
    tags = (
        [str(tag) for tag in raw_tags]
        if isinstance(raw_tags, Sequence) and not isinstance(raw_tags, (str, bytes))
        else []
    )
    return AssetItem(
        item_id=str(value.get("item_id", "") or ""),
        label=str(value.get("label", "") or ""),
        role=normalize_asset_role(value.get("role", "")),
        path=str(value.get("path", "") or ""),
        mime_type=str(value.get("mime_type", "") or ""),
        tags=tags,
        width_cm=width_cm,
        metadata={
            str(key): str(item)
            for key, item in metadata.items()
            if str(key or "").strip() and str(item or "").strip()
        },
        group_id=str(value.get("group_id", "") or ""),
        sequence=sequence,
        source_path=str(value.get("source_path", "") or ""),
        original_relative_path=str(value.get("original_relative_path", "") or ""),
        normalized_name=str(value.get("normalized_name", "") or ""),
        content_hash=str(value.get("content_hash", "") or ""),
    )


def asset_item_payload(item: AssetItem) -> dict[str, object]:
    payload: dict[str, object] = {
        "item_id": item.item_id,
        "label": item.label,
        "role": normalize_asset_role(item.role),
        "path": item.path,
        "mime_type": item.mime_type,
        "tags": list(item.tags),
        "metadata": dict(item.metadata),
        "group_id": item.group_id,
        "sequence": item.sequence,
        "source_path": item.source_path,
        "original_relative_path": item.original_relative_path,
        "normalized_name": item.normalized_name,
        "content_hash": item.content_hash,
    }
    if item.width_cm is not None:
        payload["width_cm"] = item.width_cm
    return {
        key: value
        for key, value in payload.items()
        if value not in (None, "", [], {})
    }


def asset_diagnostic_payload(diagnostic: AssetDiagnostic) -> dict[str, object]:
    """Return the lossless execution projection for one resolver diagnostic."""

    payload: dict[str, object] = {
        "code": diagnostic.code,
        "severity": diagnostic.severity,
        "role": diagnostic.role,
        "path": diagnostic.path,
        "message": diagnostic.message,
        "item_id": diagnostic.item_id,
        "label": diagnostic.label,
        "metadata": dict(diagnostic.metadata),
    }
    return {
        key: value
        for key, value in payload.items()
        if value not in (None, "", [], {})
    }


def normalize_asset_item_payloads(items: object) -> list[dict[str, object]]:
    """Return the sole lossless persisted projection for asset items."""

    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return []

    normalized: list[dict[str, object]] = []
    for value in items:
        if isinstance(value, AssetItem):
            item = copy.deepcopy(value)
        elif isinstance(value, Mapping):
            item = asset_item_from_payload(value)
            asset_id = str(
                item.metadata.get("asset_id")
                or item.metadata.get("assetId")
                or ""
            ).strip()
            if not item.role or (not item.path.strip() and not asset_id):
                continue
            if not item.label:
                item.label = Path(item.path).stem or asset_id or item.role
        else:
            continue

        payload = asset_item_payload(item)
        # These keys are the stable persisted base shape. Optional snapshot
        # identity fields remain present whenever their canonical value exists.
        payload.setdefault("item_id", item.item_id)
        payload.setdefault("label", item.label)
        payload.setdefault("role", normalize_asset_role(item.role))
        payload.setdefault("path", item.path)
        payload.setdefault("metadata", dict(item.metadata))
        normalized.append(payload)
    return normalized


def asset_sequence_value(value: object) -> int | None:
    """Return the canonical sequence with legacy metadata fallbacks."""

    if isinstance(value, Mapping):
        direct = _optional_positive_int(value.get("sequence"))
        metadata = value.get("metadata", value)
    else:
        direct = _optional_positive_int(getattr(value, "sequence", None))
        metadata = getattr(value, "metadata", {})
    if direct is not None:
        return direct
    return _sequence_from_metadata(metadata if isinstance(metadata, Mapping) else {})


def file_content_revision(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return f"sha256:{digest.hexdigest()}"


def directory_content_revision(
    directory: Path,
    *,
    allowed_extensions: Sequence[str] | set[str] | frozenset[str] | None = None,
) -> str:
    if not directory.is_dir():
        return ""
    normalized_extensions = (
        {str(item).lower() for item in allowed_extensions}
        if allowed_extensions is not None
        else None
    )
    digest = hashlib.sha256()
    try:
        paths = [
            item
            for item in directory.rglob("*")
            if item.is_file()
            and (
                normalized_extensions is None
                or item.suffix.lower() in normalized_extensions
            )
        ]
    except OSError:
        return ""
    for path in sorted(
        paths,
        key=lambda item: natural_relative_path_key(item.relative_to(directory).as_posix()),
    ):
        relative = path.relative_to(directory).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_content_revision(path).encode("ascii"))
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _resolve_single_file_binding(
    binding: AssetBinding,
    diagnostics: list[AssetDiagnostic],
) -> list[AssetItem]:
    path = Path(str(binding.source_path or "").strip())
    if not str(binding.source_path or "").strip():
        return []
    if not path.is_file():
        diagnostics.append(
            AssetDiagnostic(
                code="asset_file_missing",
                role=binding.role,
                path=str(path),
                message=f"角色 {binding.role} 绑定的图片文件不存在。",
            )
        )
        return []
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        diagnostics.append(
            AssetDiagnostic(
                code="asset_file_type_unsupported",
                role=binding.role,
                path=str(path),
                message=f"角色 {binding.role} 的文件格式不受图片链路支持。",
            )
        )
        return []
    content_hash = file_content_revision(path)
    if not content_hash:
        diagnostics.append(
            AssetDiagnostic(
                code="asset_file_unreadable",
                role=binding.role,
                path=str(path),
                message=f"角色 {binding.role} 绑定的图片文件不可读取。",
            )
        )
        return []
    return [
        AssetItem(
            item_id=binding.role,
            label=path.stem or binding.role,
            role=binding.role,
            path=str(path),
            mime_type=mimetypes.guess_type(str(path))[0] or "",
            group_id="",
            sequence=1,
            source_path=str(path),
            original_relative_path=path.name,
            normalized_name=path.name,
            content_hash=content_hash,
        )
    ]


def _scan_directory_binding(
    binding: AssetBinding,
    diagnostics: list[AssetDiagnostic],
) -> list[AssetItem]:
    root = Path(str(binding.source_path or "").strip())
    if not str(binding.source_path or "").strip():
        return []
    if not root.is_dir():
        diagnostics.append(
            AssetDiagnostic(
                code="asset_directory_missing",
                role=binding.role,
                path=str(root),
                message=f"角色 {binding.role} 绑定的图片目录不存在。",
            )
        )
        return []

    candidates: Iterable[Path] = root.rglob("*") if binding.recursive else root.iterdir()
    image_paths: list[Path] = []
    try:
        for path in candidates:
            if not path.is_file():
                continue
            if path.suffix.lower() not in IMAGE_EXTENSIONS:
                diagnostics.append(
                    AssetDiagnostic(
                        code="asset_file_type_unsupported",
                        severity="warning",
                        role=binding.role,
                        path=str(path),
                        message="图片组目录包含不受支持的文件，已跳过。",
                    )
                )
                continue
            image_paths.append(path)
    except OSError:
        diagnostics.append(
            AssetDiagnostic(
                code="asset_directory_unreadable",
                role=binding.role,
                path=str(root),
                message=f"角色 {binding.role} 绑定的图片目录不可读取。",
            )
        )
        return []

    image_paths.sort(
        key=lambda path: natural_relative_path_key(path.relative_to(root).as_posix())
    )
    if not image_paths:
        diagnostics.append(
            AssetDiagnostic(
                code="asset_directory_empty",
                role=binding.role,
                path=str(root),
                message=f"角色 {binding.role} 的图片目录没有可用图片。",
            )
        )
        return []

    readable_paths: list[tuple[Path, str]] = []
    for path in image_paths:
        content_hash = file_content_revision(path)
        if content_hash:
            readable_paths.append((path, content_hash))
            continue
        diagnostics.append(
            AssetDiagnostic(
                code="asset_file_unreadable",
                role=binding.role,
                path=str(path),
                message="图片组中的文件不可读取，已跳过。",
            )
        )

    items: list[AssetItem] = []
    normalized_names: set[str] = set()
    for sequence, (path, content_hash) in enumerate(readable_paths, start=1):
        relative = path.relative_to(root).as_posix()
        normalized_name = _normalized_asset_name(binding, path, sequence)
        if normalized_name.casefold() in normalized_names:
            diagnostics.append(
                AssetDiagnostic(
                    code="asset_normalized_name_conflict",
                    role=binding.role,
                    path=str(path),
                    message=f"规范文件名 {normalized_name} 与组内其他图片冲突。",
                )
            )
            normalized_name = _fallback_normalized_name(binding.role, path, sequence)
        normalized_names.add(normalized_name.casefold())
        items.append(
            AssetItem(
                item_id=f"{binding.role}:{sequence:03d}",
                label=path.stem,
                role=binding.role,
                path=str(path),
                mime_type=mimetypes.guess_type(str(path))[0] or "",
                group_id=binding.role,
                sequence=sequence,
                source_path=str(root),
                original_relative_path=relative,
                normalized_name=normalized_name,
                content_hash=content_hash,
            )
        )
    return items


def _snapshot_items(
    binding: AssetBinding,
    diagnostics: list[AssetDiagnostic],
) -> list[AssetItem]:
    items: list[AssetItem] = []
    for source_index, raw in enumerate(binding.items, start=1):
        item = asset_item_from_payload(raw)
        item.role = binding.role
        if item.path and not is_supported_image_path(item.path):
            diagnostics.append(_unsupported_image_diagnostic(binding.role, item.path))
            continue
        item.group_id = item.group_id or (
            binding.role if binding.cardinality == "multiple" else ""
        )
        item.sequence = item.sequence or source_index
        path = Path(item.path)
        if not item.path or not path.is_file():
            diagnostics.append(
                AssetDiagnostic(
                    code="asset_file_missing",
                    role=binding.role,
                    path=item.path,
                    message=f"角色 {binding.role} 的已保存图片条目不存在。",
                    item_id=item.item_id,
                    label=item.label,
                    metadata=dict(item.metadata),
                )
            )
            continue
        if not item.normalized_name and item.path:
            item.normalized_name = _normalized_asset_name(binding, path, item.sequence)
        if not item.original_relative_path and item.path:
            item.original_relative_path = path.name
        if not item.source_path:
            item.source_path = binding.source_path
        actual_hash = file_content_revision(path)
        if not actual_hash:
            diagnostics.append(
                AssetDiagnostic(
                    code="asset_file_unreadable",
                    role=binding.role,
                    path=str(path),
                    message="已保存的图片条目不可读取。",
                    item_id=item.item_id,
                    label=item.label,
                    metadata=dict(item.metadata),
                )
            )
            continue
        item.content_hash = actual_hash
        items.append(item)
    return _stable_asset_item_order(items)


def _image_role_names(role_specs: Sequence[object]) -> set[str]:
    roles: set[str] = set()
    for spec in role_specs:
        role = normalize_asset_role(getattr(spec, "role", ""))
        if not role:
            continue
        accepted_types = getattr(spec, "accepted_types", None)
        if accepted_types is None:
            roles.add(role)
            continue
        normalized_types = {
            str(item or "").strip().lower()
            for item in accepted_types
            if str(item or "").strip()
        }
        if normalized_types and normalized_types <= {"image"}:
            roles.add(role)
    return roles


def _unsupported_image_diagnostic(role: str, path: str) -> AssetDiagnostic:
    return AssetDiagnostic(
        code="asset_file_type_unsupported",
        role=role,
        path=str(path or ""),
        message=f"角色 {role} 的文件格式不受图片链路支持，已隔离。",
    )


def _normalized_asset_name(binding: AssetBinding, path: Path, sequence: int) -> str:
    suffix = path.suffix.lower()
    values = {
        "role": _safe_filename_segment(binding.role),
        "sequence": sequence,
        "stem": _safe_filename_segment(path.stem),
        "suffix": suffix,
    }
    try:
        rendered = str(binding.naming_template or "{role}_{sequence:03d}").format(**values)
    except (KeyError, ValueError, IndexError):
        return _fallback_normalized_name(binding.role, path, sequence)
    cleaned = _safe_filename_segment(rendered)
    if not cleaned:
        return _fallback_normalized_name(binding.role, path, sequence)
    if not Path(cleaned).suffix:
        cleaned = f"{cleaned}{suffix}"
    return cleaned


def _fallback_normalized_name(role: str, path: Path, sequence: int) -> str:
    return f"{_safe_filename_segment(role)}_{sequence:03d}{path.suffix.lower()}"


def _safe_filename_segment(value: object) -> str:
    forbidden = '<>:"/\\|?*'
    cleaned = "".join(
        char if char not in forbidden and ord(char) >= 32 else "_"
        for char in str(value or "").strip()
    ).strip(" ._")
    return cleaned or "asset"


def _append_binding_count_diagnostics(
    binding: AssetBinding,
    items: Sequence[AssetItem],
    diagnostics: list[AssetDiagnostic],
) -> None:
    count = len(items)
    if binding.cardinality == "single" and count > 1:
        diagnostics.append(
            AssetDiagnostic(
                code="asset_single_role_multiple_items",
                role=binding.role,
                message=f"单图角色 {binding.role} 解析出 {count} 张图片。",
            )
        )
    if count < max(0, int(binding.min_items or 0)):
        diagnostics.append(
            AssetDiagnostic(
                code="asset_group_below_min_items",
                role=binding.role,
                message=f"角色 {binding.role} 至少需要 {binding.min_items} 张图片，当前为 {count} 张。",
            )
        )
    if binding.max_items is not None and count > binding.max_items:
        diagnostics.append(
            AssetDiagnostic(
                code="asset_group_above_max_items",
                role=binding.role,
                message=f"角色 {binding.role} 最多允许 {binding.max_items} 张图片，当前为 {count} 张。",
            )
        )


def _role_contract_diagnostics(
    resolution: AssetResolution,
    role_specs: Sequence[object],
) -> list[AssetDiagnostic]:
    diagnostics: list[AssetDiagnostic] = []
    for spec in role_specs:
        role = normalize_asset_role(getattr(spec, "role", ""))
        if not role:
            continue
        items = resolution.items_for_role(role)
        required = bool(getattr(spec, "required", False))
        min_items = int(getattr(spec, "min_items", 1 if required else 0) or 0)
        max_items = getattr(spec, "max_items", None)
        cardinality = str(getattr(spec, "cardinality", "single") or "single")
        if required and not items:
            diagnostics.append(
                AssetDiagnostic(
                    code="asset_binding_missing",
                    role=role,
                    message=f"必需图片角色 {role} 尚未绑定。",
                )
            )
        if len(items) < min_items:
            diagnostics.append(
                AssetDiagnostic(
                    code="asset_group_below_min_items",
                    role=role,
                    message=f"角色 {role} 至少需要 {min_items} 张图片。",
                )
            )
        if max_items is not None and len(items) > int(max_items):
            diagnostics.append(
                AssetDiagnostic(
                    code="asset_group_above_max_items",
                    role=role,
                    message=f"角色 {role} 最多允许 {max_items} 张图片。",
                )
            )
        if cardinality == "single" and len(items) > 1:
            diagnostics.append(
                AssetDiagnostic(
                    code="asset_single_role_multiple_items",
                    role=role,
                    message=f"单图角色 {role} 不能同时绑定多张图片。",
                )
            )
    return _dedupe_diagnostics(diagnostics)


def _apply_role_metadata(
    items: Sequence[AssetItem],
    metadata_by_role: Mapping[str, Mapping[str, object]] | None,
) -> None:
    if not isinstance(metadata_by_role, Mapping):
        return
    normalized = {
        normalize_asset_role(role): {
            str(key): str(value)
            for key, value in dict(metadata or {}).items()
            if str(key or "").strip() and str(value or "").strip()
        }
        for role, metadata in metadata_by_role.items()
        if isinstance(metadata, Mapping)
    }
    for item in items:
        role_metadata = normalized.get(normalize_asset_role(item.role), {})
        if role_metadata:
            item.metadata = {**role_metadata, **dict(item.metadata)}


def _stable_asset_item_order(items: Sequence[AssetItem]) -> list[AssetItem]:
    return [
        item
        for source_index, item in sorted(
            enumerate(items),
            key=lambda pair: (
                normalize_asset_role(pair[1].role),
                0 if pair[1].sequence is not None else 1,
                pair[1].sequence or 0,
                natural_relative_path_key(
                    pair[1].original_relative_path
                    or pair[1].normalized_name
                    or pair[1].path
                ),
                pair[0],
            ),
        )
    ]


def _sequence_from_metadata(metadata: Mapping[str, object]) -> int | None:
    for key in (
        "sequence",
        "figure_order",
        "figureOrder",
        "image_order",
        "imageOrder",
        "sort_order",
        "sortOrder",
    ):
        value = _optional_positive_int(metadata.get(key))
        if value is not None:
            return value
    return None


def _optional_positive_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _natural_text_key(value: str) -> tuple[tuple[int, object], ...]:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    parts = re.split(r"(\d+)", normalized)
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in parts
        if part
    )


def _dedupe_diagnostics(items: Sequence[AssetDiagnostic]) -> list[AssetDiagnostic]:
    seen: set[tuple[str, str, str, str]] = set()
    result: list[AssetDiagnostic] = []
    for item in items:
        key = (item.code, item.severity, item.role, item.path)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _duplicate_content_diagnostics(items: Sequence[AssetItem]) -> list[AssetDiagnostic]:
    seen: dict[tuple[str, str], AssetItem] = {}
    diagnostics: list[AssetDiagnostic] = []
    for item in items:
        role = normalize_asset_role(item.role)
        content_hash = str(item.content_hash or "").strip()
        if not role or not content_hash:
            continue
        key = (role, content_hash)
        previous = seen.get(key)
        if previous is None:
            seen[key] = item
            continue
        diagnostics.append(
            AssetDiagnostic(
                code="asset_duplicate_content",
                severity="warning",
                role=role,
                path=item.path,
                message=(
                    f"角色 {role} 的图片 {item.original_relative_path or item.path} "
                    f"与 {previous.original_relative_path or previous.path} 内容重复。"
                ),
            )
        )
    return diagnostics


__all__ = [
    "AssetDiagnostic",
    "AssetResolution",
    "asset_diagnostic_payload",
    "asset_item_from_payload",
    "asset_item_payload",
    "asset_sequence_value",
    "directory_content_revision",
    "file_content_revision",
    "natural_relative_path_key",
    "normalize_asset_item_payloads",
    "normalize_asset_role",
    "refresh_asset_binding",
    "resolve_asset_binding",
    "resolve_profile_assets",
]
