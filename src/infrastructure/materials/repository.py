"""Mode-scoped, CAS-protected repository for schema-v1 material bundles."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import shutil
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Literal

from src.domain.materials import (
    MAX_OBJECT_SIZE,
    MaterialContract,
    MaterialObjectRef,
    MaterialPackage,
    MaterialPackageRef,
    validate_material_package_contract,
)
from src.infrastructure.materials.codec import (
    canonical_material_package_bytes,
    load_material_package,
    material_package_revision,
)

PACKAGE_FILE_NAME = "package.json"
OBJECT_DIRECTORY = Path("objects") / "sha256"
SourceType = Literal["builtin", "user"]


@dataclass(frozen=True, slots=True)
class MaterialPackageEntry:
    package_id: str
    display_name: str
    work_mode_id: str
    material_contract_id: str
    source_type: SourceType
    bundle_path: Path
    revision: str
    load_error: str = ""

    @property
    def is_available(self) -> bool:
        return not self.load_error


@dataclass(frozen=True, slots=True)
class MaterialPackageSnapshot:
    package: MaterialPackage
    ref: MaterialPackageRef
    source_type: SourceType
    bundle_path: Path


class MaterialPackageRepository:
    """Strict package repository with one format and no fallback loader."""

    def __init__(
        self,
        root: str | Path,
        *,
        contract_provider: Callable[[MaterialPackage], MaterialContract] | None = None,
    ) -> None:
        self._root = Path(root).resolve()
        self._contract_provider = contract_provider

    @property
    def root(self) -> Path:
        return self._root

    def list_entries(
        self,
        *,
        work_mode_id: str,
    ) -> tuple[MaterialPackageEntry, ...]:
        mode = _require_component(work_mode_id, "work_mode_id")
        entries: list[MaterialPackageEntry] = []
        seen_ids: dict[str, SourceType] = {}
        for source_type in ("builtin", "user"):
            directory = self._root / mode / source_type
            if not directory.is_dir():
                continue
            for package_dir in sorted(
                (
                    item
                    for item in directory.iterdir()
                    if item.is_dir()
                    and (item / PACKAGE_FILE_NAME).is_file()
                ),
                key=lambda item: item.name,
            ):
                entry = self._entry_from_bundle(
                    package_dir,
                    expected_mode=mode,
                    source_type=source_type,
                )
                identity_key = entry.package_id.casefold()
                previous = seen_ids.get(identity_key)
                if previous is not None:
                    conflict = (
                        "material_package_library_identity_duplicate:"
                        f"{entry.package_id}:{previous}:{source_type}"
                    )
                    entry = MaterialPackageEntry(
                        package_id=entry.package_id,
                        display_name=entry.display_name,
                        work_mode_id=entry.work_mode_id,
                        material_contract_id=entry.material_contract_id,
                        source_type=entry.source_type,
                        bundle_path=entry.bundle_path,
                        revision=entry.revision,
                        load_error=conflict,
                    )
                else:
                    seen_ids[identity_key] = source_type
                entries.append(entry)
        return tuple(
            sorted(
                entries,
                key=lambda item: (
                    item.display_name.casefold(),
                    item.package_id,
                    item.source_type,
                ),
            )
        )

    def load(
        self,
        *,
        work_mode_id: str,
        source_type: SourceType,
        package_id: str,
    ) -> MaterialPackageSnapshot:
        bundle = self._bundle_path(
            work_mode_id=work_mode_id,
            source_type=source_type,
            package_id=package_id,
        )
        _reject_link_or_reparse(bundle / PACKAGE_FILE_NAME)
        package = load_material_package(bundle / PACKAGE_FILE_NAME)
        if package.work_mode_id != work_mode_id:
            raise ValueError(
                "material_package_mode_scope_mismatch:"
                f"{work_mode_id}:{package.work_mode_id}"
            )
        if package.package_id != package_id:
            raise ValueError(
                "material_package_path_identity_mismatch:"
                f"{package_id}:{package.package_id}"
            )
        if self._contract_provider is not None:
            contract = self._contract_provider(package)
            contract_issues = validate_material_package_contract(
                package,
                contract,
            )
            if contract_issues:
                first = contract_issues[0]
                raise ValueError(
                    f"material_package_contract_invalid:{first.code}:{first.path}"
                )
        self._validate_objects(package, bundle)
        revision = material_package_revision(package)
        return MaterialPackageSnapshot(
            package=package,
            ref=MaterialPackageRef(
                package_id=package.package_id,
                revision=revision,
            ),
            source_type=source_type,
            bundle_path=bundle,
        )

    def create_user(self, package: MaterialPackage) -> MaterialPackageSnapshot:
        if not isinstance(package, MaterialPackage):
            raise TypeError("material_package_type_invalid")
        bundle = self._bundle_path(
            work_mode_id=package.work_mode_id,
            source_type="user",
            package_id=package.package_id,
            allow_missing=True,
        )
        lock_path = self._lock_path(package.work_mode_id, package.package_id)
        with _cross_process_lock(lock_path):
            if bundle.exists():
                raise FileExistsError(
                    f"material_package_already_exists:{package.package_id}"
                )
            bundle.parent.mkdir(parents=True, exist_ok=True)
            bundle.mkdir()
            try:
                self._validate_objects(package, bundle)
                self._publish_package_json(package, bundle)
            except BaseException:
                try:
                    shutil.rmtree(bundle)
                except OSError:
                    pass
                raise
        return self.load(
            work_mode_id=package.work_mode_id,
            source_type="user",
            package_id=package.package_id,
        )

    def save_user(
        self,
        package: MaterialPackage,
        *,
        expected_revision: str,
    ) -> MaterialPackageSnapshot:
        bundle = self._bundle_path(
            work_mode_id=package.work_mode_id,
            source_type="user",
            package_id=package.package_id,
        )
        lock_path = self._lock_path(package.work_mode_id, package.package_id)
        with _cross_process_lock(lock_path):
            current = self.load(
                work_mode_id=package.work_mode_id,
                source_type="user",
                package_id=package.package_id,
            )
            if current.ref.revision != expected_revision:
                raise RuntimeError(
                    "material_package_revision_conflict:"
                    f"{expected_revision}:{current.ref.revision}"
                )
            self._validate_objects(package, bundle)
            self._publish_package_json(package, bundle)
        return self.load(
            work_mode_id=package.work_mode_id,
            source_type="user",
            package_id=package.package_id,
        )

    def duplicate_to_user(
        self,
        source: MaterialPackageSnapshot,
        duplicate: MaterialPackage,
    ) -> MaterialPackageSnapshot:
        if duplicate.package_id == source.package.package_id:
            raise ValueError("material_package_duplicate_id_not_new")
        if duplicate.work_mode_id != source.package.work_mode_id:
            raise ValueError("material_package_duplicate_mode_mismatch")
        target_bundle = self._bundle_path(
            work_mode_id=duplicate.work_mode_id,
            source_type="user",
            package_id=duplicate.package_id,
            allow_missing=True,
        )
        lock_path = self._lock_path(
            duplicate.work_mode_id,
            duplicate.package_id,
        )
        with _cross_process_lock(lock_path):
            if target_bundle.exists():
                raise FileExistsError(
                    f"material_package_already_exists:{duplicate.package_id}"
                )
            target_bundle.parent.mkdir(parents=True, exist_ok=True)
            target_bundle.mkdir()
            try:
                object_refs = {
                    item.object_id: item
                    for scope in (
                        duplicate.shared_scope,
                        *(group.scope for group in duplicate.groups),
                        *(record.scope for record in duplicate.records),
                    )
                    for binding in scope.resources.values()
                    for item in binding.items
                }
                for object_ref in object_refs.values():
                    source_object = self.object_path(source, object_ref)
                    digest = object_ref.object_id.removeprefix("sha256:")
                    _copy_file_atomically(
                        source_object,
                        target_bundle / OBJECT_DIRECTORY / digest,
                    )
                self._validate_objects(duplicate, target_bundle)
                self._publish_package_json(duplicate, target_bundle)
            except BaseException:
                shutil.rmtree(target_bundle, ignore_errors=True)
                raise
        return self.load(
            work_mode_id=duplicate.work_mode_id,
            source_type="user",
            package_id=duplicate.package_id,
        )

    def import_object(
        self,
        *,
        work_mode_id: str,
        package_id: str,
        source_path: str | Path,
        media_type: str = "",
    ) -> MaterialObjectRef:
        source = Path(source_path)
        if not source.is_file():
            raise FileNotFoundError(f"material_object_source_missing:{source}")
        if source.stat().st_size > MAX_OBJECT_SIZE:
            raise ValueError("material_object_source_too_large")
        bundle = self._bundle_path(
            work_mode_id=work_mode_id,
            source_type="user",
            package_id=package_id,
        )
        digest, size = _hash_file(source)
        object_id = f"sha256:{digest}"
        target = bundle / OBJECT_DIRECTORY / digest
        lock_path = self._lock_path(work_mode_id, package_id)
        with _cross_process_lock(lock_path):
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                existing_digest, existing_size = _hash_file(target)
                if existing_digest != digest or existing_size != size:
                    raise ValueError(
                        f"material_object_collision:{object_id}"
                    )
            else:
                _copy_file_atomically(source, target)
        return MaterialObjectRef(
            object_id=object_id,
            media_type=(
                media_type
                or mimetypes.guess_type(source.name)[0]
                or "application/octet-stream"
            ),
            original_name=source.name,
            size=size,
        )

    def object_path(
        self,
        snapshot: MaterialPackageSnapshot,
        object_ref: MaterialObjectRef,
    ) -> Path:
        digest = object_ref.object_id.removeprefix("sha256:")
        target = _contained_path(
            snapshot.bundle_path,
            snapshot.bundle_path / OBJECT_DIRECTORY / digest,
        )
        _reject_link_or_reparse(target)
        _validate_object(target, object_ref)
        return target

    def delete_user(
        self,
        *,
        work_mode_id: str,
        package_id: str,
        expected_revision: str,
    ) -> None:
        bundle = self._bundle_path(
            work_mode_id=work_mode_id,
            source_type="user",
            package_id=package_id,
        )
        lock_path = self._lock_path(work_mode_id, package_id)
        with _cross_process_lock(lock_path):
            current = self.load(
                work_mode_id=work_mode_id,
                source_type="user",
                package_id=package_id,
            )
            if current.ref.revision != expected_revision:
                raise RuntimeError(
                    "material_package_revision_conflict:"
                    f"{expected_revision}:{current.ref.revision}"
                )
            shutil.rmtree(bundle)

    def _publish_package_json(
        self,
        package: MaterialPackage,
        bundle: Path,
    ) -> None:
        payload = canonical_material_package_bytes(package)
        _atomic_write(bundle / PACKAGE_FILE_NAME, payload)
        reloaded = load_material_package(bundle / PACKAGE_FILE_NAME)
        if reloaded != package:
            raise AssertionError("material_package_post_commit_mismatch")

    def _validate_objects(
        self,
        package: MaterialPackage,
        bundle: Path,
    ) -> None:
        for scope in (
            package.shared_scope,
            *(group.scope for group in package.groups),
            *(record.scope for record in package.records),
        ):
            for binding in scope.resources.values():
                for object_ref in binding.items:
                    digest = object_ref.object_id.removeprefix("sha256:")
                    target = _contained_path(
                        bundle,
                        bundle / OBJECT_DIRECTORY / digest,
                    )
                    _reject_link_or_reparse(target)
                    _validate_object(target, object_ref)

    def _entry_from_bundle(
        self,
        bundle: Path,
        *,
        expected_mode: str,
        source_type: SourceType,
    ) -> MaterialPackageEntry:
        fallback_id = bundle.name
        try:
            snapshot = self.load(
                work_mode_id=expected_mode,
                source_type=source_type,
                package_id=fallback_id,
            )
        except Exception as exc:
            return MaterialPackageEntry(
                package_id=fallback_id,
                display_name=fallback_id,
                work_mode_id=expected_mode,
                material_contract_id="",
                source_type=source_type,
                bundle_path=bundle,
                revision="",
                load_error=f"{type(exc).__name__}: {exc}",
            )
        return MaterialPackageEntry(
            package_id=snapshot.package.package_id,
            display_name=snapshot.package.display_name,
            work_mode_id=snapshot.package.work_mode_id,
            material_contract_id=snapshot.package.material_contract_id,
            source_type=source_type,
            bundle_path=snapshot.bundle_path,
            revision=snapshot.ref.revision,
        )

    def _bundle_path(
        self,
        *,
        work_mode_id: str,
        source_type: SourceType,
        package_id: str,
        allow_missing: bool = False,
    ) -> Path:
        mode = _require_component(work_mode_id, "work_mode_id")
        if source_type not in {"builtin", "user"}:
            raise ValueError(
                f"material_package_source_type_invalid:{source_type}"
            )
        package_component = _require_component(package_id, "package_id")
        if not package_component.startswith("pkg_"):
            raise ValueError("material_package_package_id_invalid")
        root = (self._root / mode / source_type).resolve()
        candidate = _contained_path(root, root / package_component)
        if not allow_missing and not candidate.is_dir():
            raise FileNotFoundError(
                f"material_package_bundle_missing:{candidate}"
            )
        _reject_link_or_reparse(candidate)
        return candidate

    def _lock_path(self, work_mode_id: str, package_id: str) -> Path:
        mode = _require_component(work_mode_id, "work_mode_id")
        package = _require_component(package_id, "package_id")
        return self._root / ".locks" / mode / f"{package}.lock"


def _require_component(value: object, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"material_package_{label}_invalid")
    if (
        value in {".", ".."}
        or "/" in value
        or "\\" in value
        or any(ord(char) < 32 for char in value)
        or len(value) > 64
    ):
        raise ValueError(f"material_package_{label}_invalid")
    stem = value.split(".", 1)[0].casefold()
    if stem in {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{index}" for index in range(1, 10)),
        *(f"lpt{index}" for index in range(1, 10)),
    }:
        raise ValueError(f"material_package_{label}_windows_reserved")
    return value


def _contained_path(root: Path, candidate: Path) -> Path:
    root = root.resolve()
    absolute = Path(os.path.abspath(candidate))
    try:
        absolute.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"material_package_path_outside_scope:{candidate}"
        ) from exc
    return absolute


def _reject_link_or_reparse(path: Path) -> None:
    if not path.exists():
        return
    for component in (path, *path.parents):
        if component == component.parent:
            break
        try:
            if component.is_symlink():
                raise ValueError(
                    f"material_package_path_link_or_reparse:{component}"
                )
            is_junction = getattr(component, "is_junction", None)
            if callable(is_junction) and is_junction():
                raise ValueError(
                    f"material_package_path_link_or_reparse:{component}"
                )
            attributes = getattr(
                component.stat(follow_symlinks=False),
                "st_file_attributes",
                0,
            )
            if attributes & 0x400:
                raise ValueError(
                    f"material_package_path_link_or_reparse:{component}"
                )
        except FileNotFoundError:
            continue


def _validate_object(path: Path, object_ref: MaterialObjectRef) -> None:
    if not path.is_file():
        raise FileNotFoundError(
            f"material_object_missing:{object_ref.object_id}"
        )
    digest, size = _hash_file(path)
    if size != object_ref.size:
        raise ValueError(
            f"material_object_size_mismatch:{object_ref.object_id}"
        )
    if f"sha256:{digest}" != object_ref.object_id:
        raise ValueError(
            f"material_object_hash_mismatch:{object_ref.object_id}"
        )


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _copy_file_atomically(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(source, temporary)
        with temporary.open("r+b") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _cross_process_lock(
    path: Path,
    *,
    timeout_seconds: float = 10.0,
) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    try:
        if path.stat().st_size == 0:
            stream.write(b"\0")
            stream.flush()
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                _lock_one_byte(stream)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"material_package_lock_timeout:{path}"
                    )
                time.sleep(0.05)
        try:
            yield
        finally:
            _unlock_one_byte(stream)
    finally:
        stream.close()


def _lock_one_byte(stream: BinaryIO) -> None:
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        return
    import fcntl

    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_one_byte(stream: BinaryIO) -> None:
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


__all__ = [
    "MaterialPackageEntry",
    "MaterialPackageRepository",
    "MaterialPackageSnapshot",
]
