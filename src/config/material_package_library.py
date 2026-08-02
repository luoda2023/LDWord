"""Product-facing facade for the canonical material-package repository."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from src.app_paths import config_library_data_root
from src.application.materials.contracts import get_package_material_contract
from src.domain.materials import (
    MaterialPackage,
    clone_material_package,
    generate_package_id,
)
from src.infrastructure.materials.repository import (
    MaterialPackageEntry as RepositoryEntry,
)
from src.infrastructure.materials.repository import (
    MaterialPackageRepository,
    MaterialPackageSnapshot,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_MATERIAL_PACKAGE_LIBRARY_DIR = (
    PROJECT_ROOT / "config_library" / "material_packages"
)
MATERIAL_PACKAGE_LIBRARY_DIR = config_library_data_root() / "material_packages"
PACKAGE_FILE_NAME = "package.json"
_SEEDED_LIBRARY_ROOTS: set[Path] = set()

# Defaults are explicit product configuration.  Missing defaults never fall
# back to the first package because that would silently change task identity.
DEFAULT_MATERIAL_PACKAGE_IDENTITIES: dict[str, str] = {
    "custom": "pkg_d47a4d51a9fd408195db973db06b6036",
    "exam": "pkg_f952ac3781c84e8faf87648c2d75aeb0",
    "thesis": "pkg_0a796fdc9c5a45a79a36215ad512e647",
    "official": "pkg_8af8fddc57b34616ada5893c43aa20fa",
}


@dataclass(frozen=True, slots=True)
class MaterialPackageLibraryEntry:
    package_id: str
    name: str
    path: Path
    mode_id: str
    source_type: str
    material_contract_id: str = ""
    revision: str = ""
    load_error: str = ""

    @property
    def qualified_id(self) -> str:
        """Package IDs are globally unique; source is display metadata only."""

        return self.package_id

    @property
    def is_available(self) -> bool:
        return not self.load_error

    @property
    def display_name(self) -> str:
        return self.name if self.is_available else f"{self.name}（不可用）"


@dataclass(frozen=True, slots=True)
class MaterialPackagePublicationReceipt:
    entry: MaterialPackageLibraryEntry
    snapshot: MaterialPackageSnapshot


def material_package_repository() -> MaterialPackageRepository:
    ensure_material_package_library()
    return MaterialPackageRepository(
        MATERIAL_PACKAGE_LIBRARY_DIR,
        contract_provider=get_package_material_contract,
    )


def ensure_material_package_library() -> None:
    """Mirror packaged built-ins to runtime storage without touching user data."""

    runtime_root = MATERIAL_PACKAGE_LIBRARY_DIR.expanduser().resolve()
    if runtime_root in _SEEDED_LIBRARY_ROOTS:
        return
    runtime_root.mkdir(parents=True, exist_ok=True)
    canonical_root = CANONICAL_MATERIAL_PACKAGE_LIBRARY_DIR.resolve()
    canonical_bundles: dict[tuple[str, str], Path] = {}
    for source in canonical_root.glob("*/builtin/*"):
        if source.is_dir() and (source / PACKAGE_FILE_NAME).is_file():
            canonical_bundles[(source.parent.parent.name, source.name)] = source

    for mode_dir in runtime_root.iterdir():
        builtin_dir = mode_dir / "builtin"
        if not mode_dir.is_dir() or not builtin_dir.is_dir():
            continue
        for candidate in builtin_dir.iterdir():
            if (
                candidate.is_dir()
                and (candidate / PACKAGE_FILE_NAME).is_file()
                and (mode_dir.name, candidate.name) not in canonical_bundles
            ):
                _remove_managed_builtin(candidate, runtime_root)

    for (mode_id, _package_id), source in canonical_bundles.items():
        target = runtime_root / mode_id / "builtin" / source.name
        shutil.copytree(source, target, dirs_exist_ok=True)
    _SEEDED_LIBRARY_ROOTS.add(runtime_root)


def _remove_managed_builtin(candidate: Path, runtime_root: Path) -> None:
    resolved_root = runtime_root.resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise OSError("material_package_builtin_cleanup_escape") from exc
    if candidate.is_symlink():
        raise OSError("material_package_builtin_cleanup_link_rejected")
    shutil.rmtree(candidate)


def material_package_user_dir(mode_id: str | None) -> Path:
    return MATERIAL_PACKAGE_LIBRARY_DIR / _mode(mode_id) / "user"


def material_package_builtin_dir(mode_id: str | None) -> Path:
    return MATERIAL_PACKAGE_LIBRARY_DIR / _mode(mode_id) / "builtin"


def material_package_library_watch_dirs(mode_id: str | None) -> tuple[Path, ...]:
    ensure_material_package_library()
    return tuple(
        path
        for path in (
            material_package_builtin_dir(mode_id),
            material_package_user_dir(mode_id),
        )
        if path.is_dir()
    )


def list_material_package_entries(
    *,
    mode_id: str | None,
) -> tuple[MaterialPackageLibraryEntry, ...]:
    return tuple(
        _entry(item)
        for item in material_package_repository().list_entries(
            work_mode_id=_mode(mode_id)
        )
    )


def get_material_package_entry(
    identity: str,
    *,
    mode_id: str | None,
) -> MaterialPackageLibraryEntry | None:
    package_id = str(identity or "").strip()
    if not package_id:
        return None
    return next(
        (
            item
            for item in list_material_package_entries(mode_id=mode_id)
            if item.package_id == package_id
        ),
        None,
    )


def default_material_package_entry(
    *,
    mode_id: str | None,
    entries: tuple[MaterialPackageLibraryEntry, ...] | None = None,
) -> MaterialPackageLibraryEntry | None:
    mode = _mode(mode_id)
    package_id = DEFAULT_MATERIAL_PACKAGE_IDENTITIES.get(mode, "")
    if not package_id:
        return None
    candidates = entries or list_material_package_entries(mode_id=mode)
    return next(
        (
            item
            for item in candidates
            if item.package_id == package_id and item.is_available
        ),
        None,
    )


def load_material_package_entry(
    entry: MaterialPackageLibraryEntry,
) -> MaterialPackageSnapshot:
    if not entry.is_available:
        raise ValueError(entry.load_error or "material_package_unavailable")
    snapshot = material_package_repository().load(
        work_mode_id=entry.mode_id,
        source_type=entry.source_type,
        package_id=entry.package_id,
    )
    if snapshot.ref.revision != entry.revision:
        raise RuntimeError(
            "material_package_entry_revision_changed:"
            f"{entry.revision}:{snapshot.ref.revision}"
        )
    return snapshot


def create_material_package_in_library_with_receipt(
    package: MaterialPackage,
) -> MaterialPackagePublicationReceipt:
    snapshot = material_package_repository().create_user(package)
    return MaterialPackagePublicationReceipt(
        entry=_entry_from_snapshot(snapshot),
        snapshot=snapshot,
    )


def create_material_package_in_library(
    package: MaterialPackage,
) -> MaterialPackageLibraryEntry:
    return create_material_package_in_library_with_receipt(package).entry


def save_material_package_entry(
    package: MaterialPackage,
    entry: MaterialPackageLibraryEntry,
) -> MaterialPackageLibraryEntry:
    if package.package_id != entry.package_id:
        raise ValueError("material_package_entry_identity_changed")
    snapshot = material_package_repository().save_user(
        package,
        expected_revision=entry.revision,
    )
    return _entry_from_snapshot(snapshot)


def duplicate_material_package_entry_with_receipt(
    source: MaterialPackageSnapshot,
    *,
    name: str,
) -> MaterialPackagePublicationReceipt:
    duplicate = clone_material_package(
        source.package,
        package_id=generate_package_id(),
        display_name=name,
    )
    snapshot = material_package_repository().duplicate_to_user(source, duplicate)
    return MaterialPackagePublicationReceipt(
        entry=_entry_from_snapshot(snapshot),
        snapshot=snapshot,
    )


def duplicate_material_package_entry(
    source: MaterialPackageSnapshot,
    *,
    name: str,
) -> MaterialPackageLibraryEntry:
    return duplicate_material_package_entry_with_receipt(source, name=name).entry


def delete_material_package_entry(entry: MaterialPackageLibraryEntry) -> None:
    if entry.source_type != "user":
        raise PermissionError("builtin_material_package_is_read_only")
    material_package_repository().delete_user(
        work_mode_id=entry.mode_id,
        package_id=entry.package_id,
        expected_revision=entry.revision,
    )


def _entry(item: RepositoryEntry) -> MaterialPackageLibraryEntry:
    return MaterialPackageLibraryEntry(
        package_id=item.package_id,
        name=item.display_name,
        path=item.bundle_path / PACKAGE_FILE_NAME,
        mode_id=item.work_mode_id,
        source_type=item.source_type,
        material_contract_id=item.material_contract_id,
        revision=item.revision,
        load_error=item.load_error,
    )


def _entry_from_snapshot(
    snapshot: MaterialPackageSnapshot,
) -> MaterialPackageLibraryEntry:
    return MaterialPackageLibraryEntry(
        package_id=snapshot.package.package_id,
        name=snapshot.package.display_name,
        path=snapshot.bundle_path / PACKAGE_FILE_NAME,
        mode_id=snapshot.package.work_mode_id,
        source_type=snapshot.source_type,
        material_contract_id=snapshot.package.material_contract_id,
        revision=snapshot.ref.revision,
    )


def _mode(value: str | None) -> str:
    mode = str(value or "").strip()
    if not mode:
        raise ValueError("material_package_work_mode_id_required")
    return mode


__all__ = [
    "CANONICAL_MATERIAL_PACKAGE_LIBRARY_DIR",
    "DEFAULT_MATERIAL_PACKAGE_IDENTITIES",
    "MATERIAL_PACKAGE_LIBRARY_DIR",
    "MaterialPackageLibraryEntry",
    "MaterialPackagePublicationReceipt",
    "create_material_package_in_library",
    "create_material_package_in_library_with_receipt",
    "default_material_package_entry",
    "delete_material_package_entry",
    "duplicate_material_package_entry",
    "duplicate_material_package_entry_with_receipt",
    "ensure_material_package_library",
    "get_material_package_entry",
    "list_material_package_entries",
    "load_material_package_entry",
    "material_package_builtin_dir",
    "material_package_library_watch_dirs",
    "material_package_repository",
    "material_package_user_dir",
    "save_material_package_entry",
]
