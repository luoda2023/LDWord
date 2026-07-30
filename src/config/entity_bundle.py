"""Transactional, self-contained material-package bundle export."""

from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import os
from pathlib import Path
from shutil import copy2, rmtree
import stat as stat_module
from typing import Any
from uuid import uuid4

from src.config.asset_resolution import directory_content_revision
from src.config.attachment_materials import (
    AttachmentBinding,
    AttachmentItem,
    AttachmentSourceKind,
)
from src.config.content_materials import FileAssetRef
from src.config.entity_archive_codec import save_entity_archive
from src.config.entity_artifact_gateway import (
    ContentArtifactRepository,
    default_content_artifact_repository,
)
from src.config.entity_bundle_preflight import (
    BundleTargetRegistry as _BundleTargetRegistry,
    safe_segment as _safe_segment,
    validate_bundle_identity_plan as _validate_bundle_identity_plan,
)
from src.config.entity_models import AssetBinding, EntityArchive
from src.config.library import CONFIG_LIBRARY_ROOT
from src.config.materials import IMAGE_EXTENSIONS

def save_entity_archive_bundle(
    archive: EntityArchive,
    directory: str | Path,
    *,
    content_artifact_repository: ContentArtifactRepository | None = None,
) -> Path:
    """Export a self-contained package with directory-level rollback safety."""

    root = Path(directory).resolve()
    root.parent.mkdir(parents=True, exist_ok=True)
    transaction_id = uuid4().hex
    staging = root.parent / f".{root.name}.staging-{transaction_id}"
    backup = root.parent / f".{root.name}.backup-{transaction_id}"
    moved_original = False
    try:
        _validate_bundle_identity_plan(archive)
        staged_package = _write_entity_archive_bundle(
            archive,
            staging,
            destination_name=root.name,
            content_artifact_repository=content_artifact_repository,
        )
        if root.exists():
            root.rename(backup)
            moved_original = True
        staging.rename(root)
        if backup.exists():
            rmtree(backup, ignore_errors=True)
        return root / staged_package.name
    except Exception:
        if moved_original and not root.exists() and backup.exists():
            backup.rename(root)
        if staging.exists():
            rmtree(staging, ignore_errors=True)
        raise

def _write_entity_archive_bundle(
    archive: EntityArchive,
    root: Path,
    *,
    destination_name: str,
    content_artifact_repository: ContentArtifactRepository | None,
) -> Path:
    """Write one complete bundle into a fresh staging directory."""

    root.mkdir(parents=True, exist_ok=True)
    targets = _BundleTargetRegistry()
    bundled = copy.deepcopy(archive)
    bundled.package_id = bundled.package_id or bundled.archive_id or destination_name
    for profile_index, profile in enumerate(bundled.profiles, start=1):
        profile_segment = _safe_segment(
            profile.profile_id or profile.profile_name or f"profile_{profile_index}"
        )
        asset_root = root / "assets" / profile_segment
        bundled_bindings: dict[str, AssetBinding] = {}
        for role, binding in profile.asset_bindings.items():
            bundled_bindings[role] = _bundle_asset_binding(
                binding,
                asset_root=asset_root,
                targets=targets,
                owner_prefix=f"profile:{profile.profile_id}:binding:{role}",
            )
        profile.asset_bindings = bundled_bindings
        if profile.assets_dir:
            source_dir = Path(profile.assets_dir)
            if not source_dir.is_dir():
                raise ValueError(
                    f"entity_bundle_asset_collection_missing:{profile.assets_dir}"
                )
            collection_root = asset_root / "collection"
            for source in _iter_bundle_source_files(
                source_dir,
                domain="asset_collection",
            ):
                relative = source.relative_to(source_dir)
                target = collection_root / relative
                targets.claim(
                    target,
                    owner=(
                        f"profile:{profile.profile_id}:collection:"
                        f"{relative.as_posix()}"
                    ),
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                _copy_verified_bundle_file(
                    source,
                    target,
                    domain="asset_collection",
                )
            profile.assets_dir = str(collection_root)
            collection_revision = directory_content_revision(
                Path(profile.assets_dir)
            )
            if not collection_revision:
                raise ValueError(
                    "entity_bundle_asset_collection_unreadable:"
                    f"{profile.assets_dir}"
                )
            profile.asset_metadata.setdefault("__collection__", {})[
                "sha256"
            ] = collection_revision
        bundled_role_paths: dict[str, str] = {}
        for role, path in profile.asset_paths.items():
            binding = profile.asset_bindings.get(str(role))
            if binding is not None and binding.cardinality == "single" and binding.source_path:
                bundled_role_paths[role] = binding.source_path
                continue
            bundled_path = _copy_bundle_file(
                path,
                asset_root / "roles",
                role,
                targets=targets,
                owner=f"profile:{profile.profile_id}:asset_path:{role}",
            )
            bundled_role_paths[role] = bundled_path
            revision = _file_content_revision(Path(bundled_path))
            if revision:
                profile.asset_metadata.setdefault(role, {})["sha256"] = revision
        profile.asset_paths = bundled_role_paths
        bundled_items: list[dict[str, Any]] = []
        for index, raw in enumerate(profile.asset_items, start=1):
            item = dict(raw)
            item["path"] = _copy_bundle_file(
                item.get("path", ""),
                asset_root / "items",
                str(item.get("item_id", "") or index),
                targets=targets,
                owner=(
                    f"profile:{profile.profile_id}:asset_item:"
                    f"{item.get('item_id', index)}"
                ),
            )
            item["source_path"] = item["path"]
            revision = _file_content_revision(Path(str(item["path"] or "")))
            if revision:
                item["content_hash"] = revision
            bundled_items.append(item)
        profile.asset_items = bundled_items
        attachment_root = root / "attachments" / profile_segment
        profile.attachment_bindings = {
            role: _bundle_attachment_binding(
                binding,
                attachment_root=attachment_root,
                targets=targets,
                owner_prefix=f"profile:{profile.profile_id}:attachment:{role}",
            )
            for role, binding in profile.attachment_bindings.items()
        }
    content_bindings = tuple(
        binding
        for profile in bundled.profiles
        for binding in profile.content_bindings.values()
    )
    repository = content_artifact_repository
    if content_bindings and repository is None:
        repository = default_content_artifact_repository(
            CONFIG_LIBRARY_ROOT / "content_artifacts"
        )
    vendored_root = root / "content_artifacts" / "sha256"
    seen_artifacts: set[str] = set()
    for binding in content_bindings:
        if binding.artifact_ref.artifact_id in seen_artifacts:
            continue
        if repository is None:
            raise RuntimeError("content_artifact_repository_unavailable")
        repository.vendor(
            binding.artifact_ref,
            vendored_root,
        )
        seen_artifacts.add(binding.artifact_ref.artifact_id)
    target = root / "package.json"
    save_entity_archive(bundled, target)
    _validate_bundled_file_asset_refs(bundled)
    return target


def _validate_bundled_file_asset_refs(archive: EntityArchive) -> None:
    for profile in archive.profiles:
        for role, binding in profile.attachment_bindings.items():
            for item in binding.items:
                _validate_file_asset_ref(
                    item.file_ref,
                    domain=f"publish:{profile.profile_id}:{role}:{item.item_id}",
                )

def _copy_bundle_file(
    value: object,
    directory: Path,
    stem: str,
    *,
    targets: _BundleTargetRegistry,
    owner: str,
) -> str:
    source_text = str(value or "").strip()
    if not source_text:
        return ""
    source = Path(source_text)
    if not source.is_file():
        raise ValueError(f"entity_bundle_asset_file_missing:{source_text}")
    _assert_regular_bundle_file(source, domain="asset_file")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{_safe_segment(stem)}{source.suffix}"
    targets.claim(target, owner=owner)
    if target.exists():
        raise ValueError(f"entity_bundle_target_exists:{target}")
    _copy_verified_bundle_file(source, target, domain="asset_file")
    return str(target)

def _path_is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    reparse_flag = getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(metadata, "st_file_attributes", 0)
    is_junction = getattr(path, "is_junction", None)
    return bool(
        path.is_symlink()
        or (callable(is_junction) and is_junction())
        or (reparse_flag and attributes & reparse_flag)
    )

def _assert_regular_bundle_file(path: Path, *, domain: str) -> None:
    if _path_is_link_or_reparse(path):
        raise ValueError(f"entity_bundle_link_forbidden:{domain}:{path}")
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ValueError(f"entity_bundle_asset_unreadable:{domain}:{path}") from exc
    if not stat_module.S_ISREG(metadata.st_mode):
        raise ValueError(f"entity_bundle_regular_file_required:{domain}:{path}")

def _iter_bundle_source_files(root: Path, *, domain: str):
    if _path_is_link_or_reparse(root):
        raise ValueError(f"entity_bundle_link_forbidden:{domain}:{root}")

    def raise_walk_error(error: OSError) -> None:
        raise error

    try:
        for current, directory_names, file_names in os.walk(
            root,
            topdown=True,
            onerror=raise_walk_error,
            followlinks=False,
        ):
            current_path = Path(current)
            for name in tuple(directory_names):
                child = current_path / name
                if _path_is_link_or_reparse(child):
                    raise ValueError(
                        f"entity_bundle_link_forbidden:{domain}:{child}"
                    )
            for name in file_names:
                child = current_path / name
                _assert_regular_bundle_file(child, domain=domain)
                yield child
    except OSError as exc:
        raise ValueError(f"entity_bundle_asset_unreadable:{domain}:{root}") from exc

def _copy_verified_bundle_file(source: Path, target: Path, *, domain: str) -> None:
    _assert_regular_bundle_file(source, domain=domain)
    before = source.lstat()
    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    before_revision = _file_content_revision(source)
    try:
        copy2(source, target)
        _assert_regular_bundle_file(source, domain=domain)
        after = source.lstat()
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        )
        after_revision = _file_content_revision(source)
        target_revision = _file_content_revision(target)
        if (
            before_identity != after_identity
            or before_revision != after_revision
            or before_revision != target_revision
        ):
            raise ValueError(f"entity_bundle_source_changed:{domain}:{source}")
    except Exception:
        target.unlink(missing_ok=True)
        raise

def _file_content_revision(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"

def _bundle_asset_binding(
    binding: AssetBinding,
    *,
    asset_root: Path,
    targets: _BundleTargetRegistry,
    owner_prefix: str,
) -> AssetBinding:
    from src.config.asset_resolution import (
        asset_item_payload,
        directory_content_revision,
        file_content_revision,
        refresh_asset_binding,
    )

    source_path = Path(str(binding.source_path or ""))
    if str(binding.source_path or "").strip() and source_path.exists():
        if binding.source_kind == "directory":
            for _source in _iter_bundle_source_files(
                source_path,
                domain=f"asset_binding:{binding.role}",
            ):
                pass
        else:
            _assert_regular_bundle_file(
                source_path,
                domain=f"asset_binding:{binding.role}",
            )
    for raw_item in binding.items:
        item_path_text = str(dict(raw_item).get("path", "") or "").strip()
        item_path = Path(item_path_text)
        if item_path_text and item_path.exists():
            _assert_regular_bundle_file(
                item_path,
                domain=f"asset_binding:{binding.role}",
            )
    refreshed, resolution = refresh_asset_binding(binding)
    error_codes = sorted(
        {
            diagnostic.code
            for diagnostic in resolution.diagnostics
            if diagnostic.severity == "error"
        }
    )
    if error_codes:
        raise ValueError(
            "entity_bundle_asset_binding_invalid:"
            f"{binding.role}:{','.join(error_codes)}"
        )
    role = _safe_segment(refreshed.role)
    if refreshed.cardinality == "single":
        if not resolution.items:
            return refreshed
        item = resolution.items[0]
        copied_path = _copy_bundle_file(
            item.path,
            asset_root / "bindings",
            refreshed.role,
            targets=targets,
            owner=f"{owner_prefix}:single",
        )
        item.path = copied_path
        item.source_path = copied_path
        item.normalized_name = Path(copied_path).name
        item.content_hash = file_content_revision(Path(copied_path))
        refreshed.source_path = copied_path
        refreshed.items = [asset_item_payload(item)]
        refreshed.snapshot_revision = item.content_hash
        return refreshed

    group_dir = asset_root / "groups" / role
    group_dir.mkdir(parents=True, exist_ok=True)
    bundled_items: list[dict[str, Any]] = []
    for item in resolution.items:
        source = Path(item.path)
        if not source.is_file():
            bundled_items.append(asset_item_payload(item))
            continue
        target_name = _safe_segment(
            item.normalized_name
            or f"{role}_{int(item.sequence or len(bundled_items) + 1):03d}{source.suffix.lower()}"
        )
        if not Path(target_name).suffix:
            target_name = f"{target_name}{source.suffix.lower()}"
        target = group_dir / target_name
        targets.claim(target, owner=f"{owner_prefix}:item:{item.item_id}")
        if target.exists():
            raise ValueError(f"entity_bundle_target_exists:{target}")
        _copy_verified_bundle_file(
            source,
            target,
            domain=f"asset_binding:{refreshed.role}",
        )
        item.path = str(target)
        item.source_path = str(group_dir)
        item.normalized_name = target.name
        item.content_hash = file_content_revision(target)
        bundled_items.append(asset_item_payload(item))
    refreshed.source_path = str(group_dir)
    refreshed.items = bundled_items
    refreshed.snapshot_revision = directory_content_revision(
        group_dir,
        allowed_extensions=IMAGE_EXTENSIONS,
    )
    return refreshed

def _bundle_attachment_binding(
    binding: AttachmentBinding,
    *,
    attachment_root: Path,
    targets: _BundleTargetRegistry,
    owner_prefix: str,
) -> AttachmentBinding:
    if len(binding.items) < binding.min_items or (binding.required and not binding.items):
        raise ValueError(f"material_package_attachment_items_missing:{binding.role}")
    role_dir = attachment_root / _safe_segment(binding.role)
    bundled_items: list[AttachmentItem] = []
    for item in binding.items:
        binding.validate_item(item)
        _validate_file_asset_ref(
            item.file_ref,
            domain=f"attachment:{binding.role}:{item.item_id}",
        )
        target = (
            role_dir.joinpath(*item.relative_path.split("/"))
        ).resolve()
        _assert_within(target, role_dir, "attachment_target")
        targets.claim(target, owner=f"{owner_prefix}:item:{item.item_id}")
        if target.exists():
            raise ValueError(f"entity_bundle_target_exists:{target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        _copy_verified_bundle_file(
            Path(item.file_ref.source_path),
            target,
            domain=f"attachment:{binding.role}:{item.item_id}",
        )
        bundled_ref = replace(item.file_ref, source_path=str(target))
        _validate_file_asset_ref(
            bundled_ref,
            domain=f"bundled_attachment:{binding.role}:{item.item_id}",
        )
        bundled_items.append(replace(item, file_ref=bundled_ref))
    bundled_source_path = (
        bundled_items[0].file_ref.source_path
        if binding.source_kind is AttachmentSourceKind.SINGLE_FILE and bundled_items
        else str(role_dir.resolve())
    )
    return replace(
        binding,
        source_path=bundled_source_path,
        items=tuple(bundled_items),
    )

def _validate_file_asset_ref(file_ref: FileAssetRef, *, domain: str) -> None:
    source = Path(file_ref.source_path)
    if not source.is_file():
        raise ValueError(f"material_package_file_missing:{domain}:{file_ref.source_path}")
    _assert_regular_bundle_file(source, domain=domain)
    if source.stat().st_size != file_ref.byte_size:
        raise ValueError(f"material_package_file_size_mismatch:{domain}")
    if _raw_file_sha256(source) != file_ref.content_sha256:
        raise ValueError(f"material_package_file_hash_mismatch:{domain}")

def _raw_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _safe_bundle_filename(value: object, *, fallback: str) -> str:
    candidate = Path(str(value or "").strip()).name or Path(fallback).name
    suffix = Path(candidate).suffix
    stem = Path(candidate).stem
    safe_stem = _safe_segment(stem)
    safe_suffix = "".join(
        char for char in suffix if char.isalnum() or char in {".", "_", "-"}
    )
    return f"{safe_stem}{safe_suffix}" or "file"

def _assert_within(path: Path, root: Path, domain: str) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"material_package_{domain}_path_escape:{path}") from exc

__all__ = [
    "save_entity_archive_bundle",
]
