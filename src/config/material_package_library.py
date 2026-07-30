"""Mode-scoped on-disk library for generic material packages."""

from __future__ import annotations

import copy
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from shutil import rmtree
import threading
from collections.abc import Iterator

from src.config.atomic_io import atomic_write_bytes
from src.config.entity import EntityArchive, load_entity_archive, save_entity_archive


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MATERIAL_PACKAGE_LIBRARY_DIR = PROJECT_ROOT / "config_library" / "material_packages"
PACKAGE_FILE_NAME = "package.json"


_TARGET_LOCKS_GUARD = threading.Lock()
_TARGET_LOCKS: dict[str, threading.RLock] = {}


def _target_lock_key(path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(Path(path)))


def _target_lock(path: str | Path) -> threading.RLock:
    key = _target_lock_key(path)
    with _TARGET_LOCKS_GUARD:
        return _TARGET_LOCKS.setdefault(key, threading.RLock())


@dataclass(frozen=True, slots=True)
class MaterialPackageLibraryEntry:
    package_id: str
    name: str
    path: Path
    mode_id: str
    source_type: str
    load_error: str = ""

    @property
    def qualified_id(self) -> str:
        return f"{self.source_type}/{self.package_id}"

    @property
    def is_available(self) -> bool:
        return not self.load_error

    @property
    def display_name(self) -> str:
        return self.name if self.is_available else f"{self.name}（不可用）"


@dataclass(frozen=True, slots=True)
class MaterialPackageFileSnapshot:
    """Exact bytes and revision of one validated user package target."""

    path: Path
    payload: bytes | None
    revision: str

    @property
    def exists(self) -> bool:
        return self.payload is not None


@dataclass(frozen=True, slots=True)
class MaterialPackagePublicationReceipt:
    """Writer-returned target identity plus an optional observed revision."""

    entry: MaterialPackageLibraryEntry
    snapshot: MaterialPackageFileSnapshot | None = None

    @property
    def revision_confirmed(self) -> bool:
        return self.snapshot is not None

    def with_snapshot(
        self,
        snapshot: MaterialPackageFileSnapshot,
    ) -> MaterialPackagePublicationReceipt:
        return MaterialPackagePublicationReceipt(entry=self.entry, snapshot=snapshot)


@contextmanager
def material_package_entry_target_lock(
    entry: MaterialPackageLibraryEntry,
) -> Iterator[Path]:
    """Serialize same-process operations for one validated user target."""

    if entry.source_type != "user":
        raise PermissionError("builtin_material_package_is_read_only")
    target = _assert_user_package_path(
        entry.path,
        mode_id=entry.mode_id,
        package_id=entry.package_id,
    )
    lock = _target_lock(target)
    with lock:
        # Revalidate after waiting: another actor may have replaced a path
        # component while this thread was blocked on the in-process lock.
        yield _assert_user_package_path(
            target,
            mode_id=entry.mode_id,
            package_id=entry.package_id,
        )


def capture_material_package_entry_snapshot(
    entry: MaterialPackageLibraryEntry,
) -> MaterialPackageFileSnapshot:
    """Read one package target through the library's path/reparse boundary."""

    with material_package_entry_target_lock(entry) as target:
        try:
            payload = target.read_bytes()
        except FileNotFoundError:
            payload = None
        # Recheck after the read so a path swapped to a reparse point while it
        # was observed cannot be accepted as a valid revision token.
        target = _assert_user_package_path(
            target,
            mode_id=entry.mode_id,
            package_id=entry.package_id,
        )
    revision = (
        "missing"
        if payload is None
        else f"sha256:{hashlib.sha256(payload).hexdigest()}"
    )
    return MaterialPackageFileSnapshot(
        path=target,
        payload=payload,
        revision=revision,
    )


def material_package_entry_matches_snapshot(
    entry: MaterialPackageLibraryEntry,
    expected: MaterialPackageFileSnapshot,
) -> bool:
    """Return whether the exact safe target still has ``expected`` revision."""

    with material_package_entry_target_lock(entry):
        current = capture_material_package_entry_snapshot(entry)
        return (
            os.path.normcase(os.path.abspath(current.path))
            == os.path.normcase(os.path.abspath(expected.path))
            and current.revision == expected.revision
        )


def restore_material_package_entry_snapshot(
    entry: MaterialPackageLibraryEntry,
    *,
    expected_current: MaterialPackageFileSnapshot,
    restore: MaterialPackageFileSnapshot,
) -> bool:
    """CAS-restore exact package bytes without deleting unrelated siblings.

    ``False`` means another writer changed the target after publication.  In
    that case this function deliberately leaves both the target and directory
    untouched.
    """

    with material_package_entry_target_lock(entry) as target:
        if not material_package_entry_matches_snapshot(entry, expected_current):
            return False
        if os.path.normcase(os.path.abspath(target)) != os.path.normcase(
            os.path.abspath(restore.path)
        ):
            raise ValueError("material_package_snapshot_path_mismatch")
        if restore.payload is not None:
            atomic_write_bytes(target, restore.payload)
            return material_package_entry_matches_snapshot(entry, restore)

        target.unlink(missing_ok=True)
        try:
            # Only remove the directory if it is now empty. Concurrent or
            # external sibling content is never recursively deleted.
            target.parent.rmdir()
        except OSError:
            pass
        return not target.exists()


def material_package_user_dir(mode_id: str | None) -> Path:
    return _mode_dir(mode_id) / "user"


def material_package_builtin_dir(mode_id: str | None) -> Path:
    return _mode_dir(mode_id) / "builtin"


def material_package_library_watch_dirs(mode_id: str | None) -> tuple[Path, ...]:
    user_dir = material_package_user_dir(mode_id)
    return tuple(
        path
        for path in (material_package_builtin_dir(mode_id), user_dir)
        if path.exists() and path.is_dir()
    )


def list_material_package_entries(
    *, mode_id: str | None
) -> tuple[MaterialPackageLibraryEntry, ...]:
    entries: list[MaterialPackageLibraryEntry] = []
    for source_type, directory in (
        ("builtin", material_package_builtin_dir(mode_id)),
        ("user", material_package_user_dir(mode_id)),
    ):
        if not directory.exists() or not directory.is_dir():
            continue
        candidates = directory.glob(f"*/{PACKAGE_FILE_NAME}")
        for path in sorted(candidates, key=lambda item: str(item).casefold()):
            entry = _entry_from_path(
                path,
                mode_id=_normalize_mode_id(mode_id),
                source_type=source_type,
            )
            entries.append(entry)
    entries.sort(
        key=lambda item: (
            item.name.casefold(),
            0 if item.source_type == "user" else 1,
            item.package_id.casefold(),
        )
    )
    return tuple(entries)


def get_material_package_entry(
    identity: str,
    *,
    mode_id: str | None,
) -> MaterialPackageLibraryEntry | None:
    target = str(identity or "").strip()
    if not target:
        return None
    entries = list_material_package_entries(mode_id=mode_id)
    if "/" in target:
        return next((item for item in entries if item.qualified_id == target), None)
    matches = [item for item in entries if item.package_id == target]
    return next((item for item in matches if item.source_type == "user"), None) or (
        matches[0] if matches else None
    )


def load_material_package_entry(entry: MaterialPackageLibraryEntry) -> EntityArchive:
    if not entry.is_available:
        raise ValueError(entry.load_error or "material_package_unavailable")
    current = _entry_from_path(
        entry.path,
        mode_id=_normalize_mode_id(entry.mode_id),
        source_type=entry.source_type,
    )
    if not current.is_available:
        raise ValueError(current.load_error or "material_package_unavailable")
    if (
        current.package_id != entry.package_id
        or current.mode_id != entry.mode_id
        or current.source_type != entry.source_type
        or os.path.normcase(os.path.abspath(current.path))
        != os.path.normcase(os.path.abspath(entry.path))
    ):
        raise ValueError("material_package_entry_identity_changed")
    return load_entity_archive(current.path)


def create_material_package_in_library_with_receipt(
    archive: EntityArchive,
    *,
    mode_id: str | None,
    requested_id: str | None = None,
) -> MaterialPackagePublicationReceipt:
    mode = _normalize_mode_id(mode_id)
    base_id = _safe_package_id(
        requested_id or archive.package_id or archive.archive_id or archive.archive_name
    )
    package_id, target = _unique_user_package_path(base_id, mode_id=mode)
    stored = copy.deepcopy(archive)
    stored.mode_id = mode
    stored.package_id = package_id
    stored.archive_id = package_id
    package_dir = target.parent
    with _target_lock(target):
        package_dir.mkdir(parents=True, exist_ok=False)
        owned_directory_stat = None
        try:
            owned_directory_stat = package_dir.stat(follow_symlinks=False)
            save_entity_archive(stored, target)
            entry = _entry_from_saved_archive(stored, target, source_type="user")
            snapshot: MaterialPackageFileSnapshot | None = None
            for attempt in range(2):
                try:
                    snapshot = capture_material_package_entry_snapshot(entry)
                    break
                except Exception:
                    if attempt == 1:
                        raise
            assert snapshot is not None
            # The identity and revision are captured before releasing the
            # creator's first target lock. A later writer therefore cannot be
            # mistaken for this creator's publication.
            return MaterialPackagePublicationReceipt(entry=entry, snapshot=snapshot)
        except BaseException as exc:
            # This function created exactly one previously absent directory.
            # It owns that directory only while its identity is unchanged.
            try:
                if owned_directory_stat is None:
                    exc.add_note(
                        "material_package_cleanup_skipped:"
                        "owned_directory_identity_unknown:"
                        f"{package_dir}"
                    )
                else:
                    current_directory_stat = package_dir.stat(follow_symlinks=False)
                    if os.path.samestat(owned_directory_stat, current_directory_stat):
                        rmtree(package_dir)
                    else:
                        exc.add_note(
                            "material_package_cleanup_skipped:"
                            "owned_directory_identity_changed:"
                            f"{package_dir}"
                        )
            except FileNotFoundError:
                pass
            except OSError as cleanup_exc:
                exc.add_note(
                    "material_package_cleanup_failed:"
                    f"{package_dir}:{cleanup_exc}"
                )
            raise


def create_material_package_in_library(
    archive: EntityArchive,
    *,
    mode_id: str | None,
    requested_id: str | None = None,
) -> MaterialPackageLibraryEntry:
    return create_material_package_in_library_with_receipt(
        archive,
        mode_id=mode_id,
        requested_id=requested_id,
    ).entry


def save_material_package_entry(
    archive: EntityArchive,
    entry: MaterialPackageLibraryEntry,
) -> MaterialPackageLibraryEntry:
    if entry.source_type != "user":
        raise PermissionError("builtin_material_package_is_read_only")
    with material_package_entry_target_lock(entry) as target:
        stored = copy.deepcopy(archive)
        stored.mode_id = entry.mode_id
        stored.package_id = entry.package_id
        stored.archive_id = entry.package_id
        save_entity_archive(stored, target)
    return _entry_from_saved_archive(stored, target, source_type="user")


def duplicate_material_package_entry(
    archive: EntityArchive,
    *,
    mode_id: str | None,
    name: str,
) -> MaterialPackageLibraryEntry:
    return duplicate_material_package_entry_with_receipt(
        archive,
        mode_id=mode_id,
        name=name,
    ).entry


def duplicate_material_package_entry_with_receipt(
    archive: EntityArchive,
    *,
    mode_id: str | None,
    name: str,
) -> MaterialPackagePublicationReceipt:
    duplicated = copy.deepcopy(archive)
    duplicated.archive_name = str(name or "").strip() or "资料包副本"
    duplicated.package_id = ""
    duplicated.archive_id = ""
    duplicated.source_path = ""
    return create_material_package_in_library_with_receipt(
        duplicated,
        mode_id=mode_id,
        requested_id=duplicated.archive_name,
    )


def delete_material_package_entry(entry: MaterialPackageLibraryEntry) -> None:
    if entry.source_type != "user":
        raise PermissionError("builtin_material_package_is_read_only")
    with material_package_entry_target_lock(entry) as target:
        package_dir = target.parent
        if package_dir.exists():
            rmtree(package_dir)


def _entry_from_path(
    path: Path,
    *,
    mode_id: str,
    source_type: str,
) -> MaterialPackageLibraryEntry:
    fallback_id = path.parent.name
    try:
        canonical_path = _assert_scoped_package_path(
            path,
            mode_id=mode_id,
            source_type=source_type,
        )
    except Exception as exc:
        return MaterialPackageLibraryEntry(
            package_id=fallback_id,
            name=fallback_id,
            path=path,
            mode_id=mode_id,
            source_type=source_type,
            load_error=str(exc),
        )
    try:
        payload = json.loads(canonical_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return MaterialPackageLibraryEntry(
            package_id=fallback_id,
            name=fallback_id,
            path=canonical_path,
            mode_id=mode_id,
            source_type=source_type,
            load_error=str(exc),
        )
    if not isinstance(payload, dict):
        return MaterialPackageLibraryEntry(
            package_id=fallback_id,
            name=fallback_id,
            path=canonical_path,
            mode_id=mode_id,
            source_type=source_type,
            load_error="material_package_payload_must_be_object",
        )
    package_id = fallback_id
    raw_name = payload.get("archive_name", "")
    name = (
        raw_name.strip()
        if type(raw_name) is str and raw_name.strip()
        else package_id
    )
    load_error = ""
    raw_package_id = payload.get("package_id")
    raw_mode_id = payload.get("mode_id")
    if type(raw_package_id) is not str or raw_package_id != fallback_id:
        load_error = (
            "material_package_path_identity_mismatch:"
            f"{fallback_id}:{raw_package_id}"
        )
    elif type(raw_mode_id) is not str or raw_mode_id != mode_id:
        load_error = (
            "material_package_mode_scope_mismatch:"
            f"{mode_id}:{raw_mode_id}"
        )
    else:
        try:
            load_entity_archive(canonical_path)
        except Exception as exc:
            load_error = str(exc)
    return MaterialPackageLibraryEntry(
        package_id=package_id,
        name=name,
        path=canonical_path,
        mode_id=mode_id,
        source_type=source_type,
        load_error=load_error,
    )


def _assert_scoped_package_path(
    path: Path,
    *,
    mode_id: str,
    source_type: str,
) -> Path:
    if source_type not in {"builtin", "user"}:
        raise ValueError(f"material_package_source_type_invalid:{source_type}")
    normalized_mode = _normalize_mode_id(mode_id)
    if normalized_mode != mode_id:
        raise ValueError(f"material_package_mode_scope_invalid:{mode_id}")
    root = Path(os.path.abspath(_mode_dir(normalized_mode) / source_type))
    candidate = Path(os.path.abspath(path))
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"material_package_path_outside_scope:{path}") from exc
    if candidate.name != PACKAGE_FILE_NAME or len(relative.parts) != 2:
        raise ValueError(f"material_package_path_invalid:{path}")
    if not relative.parts[0] or relative.parts[0] in {".", ".."}:
        raise ValueError(f"material_package_path_identity_invalid:{path}")
    for component in (candidate.parent, candidate):
        if _is_link_or_reparse(component):
            raise ValueError(f"material_package_path_link_or_reparse:{component}")
    try:
        resolved_relative = candidate.resolve(strict=False).relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"material_package_path_outside_scope:{path}") from exc
    if tuple(part.casefold() for part in resolved_relative.parts) != tuple(
        part.casefold() for part in relative.parts
    ):
        raise ValueError(f"material_package_path_identity_changed:{path}")
    return candidate


def _entry_from_saved_archive(
    archive: EntityArchive,
    path: Path,
    *,
    source_type: str,
) -> MaterialPackageLibraryEntry:
    return MaterialPackageLibraryEntry(
        package_id=str(archive.package_id or archive.archive_id or path.parent.name),
        name=str(archive.archive_name or archive.package_id or path.parent.name),
        path=path.resolve(),
        mode_id=_normalize_mode_id(archive.mode_id),
        source_type=source_type,
    )


def _unique_user_package_path(base_id: str, *, mode_id: str) -> tuple[str, Path]:
    user_dir = material_package_user_dir(mode_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, 1000):
        candidate = base_id if index == 1 else f"{base_id}_{index}"
        package_dir = user_dir / candidate
        if not package_dir.exists():
            return candidate, package_dir / PACKAGE_FILE_NAME
    candidate = f"{base_id}_1000"
    return candidate, user_dir / candidate / PACKAGE_FILE_NAME


def _assert_user_package_path(
    path: Path,
    *,
    mode_id: str,
    package_id: str,
) -> Path:
    root = Path(os.path.abspath(material_package_user_dir(mode_id)))
    candidate = Path(os.path.abspath(path))
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"material_package_path_outside_user_library:{path}") from exc
    if candidate.name != PACKAGE_FILE_NAME or len(relative.parts) != 2:
        raise ValueError(f"material_package_path_invalid:{path}")
    if relative.parts[0].casefold() != str(package_id or "").strip().casefold():
        raise ValueError(
            "material_package_path_identity_mismatch:"
            f"{package_id}:{relative.parts[0]}"
        )
    for component in (candidate.parent, candidate):
        if _is_link_or_reparse(component):
            raise ValueError(f"material_package_path_link_or_reparse:{component}")
    try:
        resolved_relative = candidate.resolve(strict=False).relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"material_package_path_outside_user_library:{path}") from exc
    if tuple(part.casefold() for part in resolved_relative.parts) != tuple(
        part.casefold() for part in relative.parts
    ):
        raise ValueError(f"material_package_path_identity_changed:{path}")
    return candidate


def _is_link_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
        attributes = getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0)
        return bool(attributes & 0x400)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ValueError(f"material_package_path_unreadable:{path}") from exc


def _mode_dir(mode_id: str | None) -> Path:
    return MATERIAL_PACKAGE_LIBRARY_DIR / _normalize_mode_id(mode_id)


def _normalize_mode_id(mode_id: str | None) -> str:
    value = str(mode_id or "").strip().lower().replace(" ", "_")
    safe = "".join(char for char in value if char.isalnum() or char in {"_", "-"})
    return safe or "custom"


def _safe_package_id(value: object) -> str:
    forbidden = '<>:"/\\|?*'
    cleaned = "".join(
        char if char not in forbidden and ord(char) >= 32 else "_"
        for char in str(value or "").strip()
    )
    cleaned = cleaned.strip(" ._")
    return cleaned or "material_package"


__all__ = [
    "MATERIAL_PACKAGE_LIBRARY_DIR",
    "MaterialPackageFileSnapshot",
    "MaterialPackageLibraryEntry",
    "MaterialPackagePublicationReceipt",
    "capture_material_package_entry_snapshot",
    "create_material_package_in_library",
    "create_material_package_in_library_with_receipt",
    "delete_material_package_entry",
    "duplicate_material_package_entry",
    "duplicate_material_package_entry_with_receipt",
    "get_material_package_entry",
    "list_material_package_entries",
    "load_material_package_entry",
    "material_package_builtin_dir",
    "material_package_library_watch_dirs",
    "material_package_user_dir",
    "material_package_entry_matches_snapshot",
    "material_package_entry_target_lock",
    "restore_material_package_entry_snapshot",
    "save_material_package_entry",
]
