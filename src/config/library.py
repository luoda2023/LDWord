"""Unified plan/template config library helpers.

The runtime library has one mode-scoped source of truth:

- ``config_library/plans/<mode>/{builtin,user}/`` for plan configs
- ``config_library/templates/<mode>/{builtin,user}/`` for format templates
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.app_paths import config_library_data_root
from src.config.atomic_io import atomic_write_bytes
from src.config.builtin_scenes import (
    canonical_scene_root,
    create_builtin_scene,
    list_builtin_scene_resources,
)
from src.config.builtin_templates import (
    canonical_template_root,
    create_builtin_template,
    list_builtin_template_resources,
)
from src.config.canonical_resource import assert_non_symbolic_resource_path
from src.config.loader import (
    ConfigLoadError,
    load_compatible_user_template,
    load_scene,
    load_template,
    save_scene,
    save_template,
)

DEFAULT_TEMPLATE_ID = "default"
DEFAULT_SCENE_ID = "custom"

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_LIBRARY_ROOT = config_library_data_root()
TEMPLATE_LIBRARY_DIR = CONFIG_LIBRARY_ROOT / "templates"
SCENE_LIBRARY_DIR = CONFIG_LIBRARY_ROOT / "plans"
_TEMPLATE_CONFIG_SUFFIXES: tuple[str, ...] = (".json", ".yaml", ".yml")
_SCENE_CONFIG_SUFFIXES: tuple[str, ...] = (".json",)
_SOURCE_BUCKETS: tuple[str, ...] = ("user", "builtin")
_EXTERNAL_CONFIG_LOAD_ERRORS: tuple[type[BaseException], ...] = (ConfigLoadError,)
_IN_PLACE_TEMPLATE_VALIDATION_DIGESTS: dict[str, str] = {}
_IN_PLACE_SCENE_VALIDATION_DIGESTS: dict[str, str] = {}
_SCENE_CREATE_LOCKS_GUARD = threading.Lock()
_SCENE_CREATE_LOCKS: dict[str, threading.RLock] = {}
_SCENE_RECOVERY_PREFIX = ".scene-recovery-"
_LIBRARY_ENSURE_SESSION: ContextVar[set[str] | None] = ContextVar(
    "config_library_ensure_session",
    default=None,
)


@dataclass(frozen=True, slots=True)
class ConfigLibraryEntry:
    kind: str
    config_id: str
    name: str
    path: Path
    mode_id: str = ""
    source_type: str = ""
    load_error: str = ""
    # Save receipts carry the exact bytes published by the writer.  Discovery
    # entries may leave this blank; it is deliberately excluded from semantic
    # entry equality so callers comparing a receipt with a later lookup retain
    # the historical contract.
    revision: str = field(default="", compare=False)
    recovery_path: Path | None = field(default=None, compare=False)

    @property
    def is_available(self) -> bool:
        return not self.load_error

    @property
    def display_name(self) -> str:
        return self.name if self.is_available else f"{self.name} (Unavailable)"


@dataclass(frozen=True, slots=True)
class SceneFileMutationReceipt:
    """One-shot evidence for a retained conditional Scene-file mutation."""

    target: Path
    recovery_dir: Path
    displaced_path: Path
    before_revision: str
    after_revision: str
    intent: str = "conditional_mutation"


@dataclass(frozen=True, slots=True)
class SceneLibraryDescriptor:
    config_id: str
    scene_id: str
    name: str
    description: str
    template_id: str
    compatible_template_ids: tuple[str, ...]
    path: Path
    load_error: str = ""
    mode_id: str = ""
    source_type: str = ""
    display_order: int = 0

    @property
    def is_available(self) -> bool:
        return not self.load_error

    @property
    def display_name(self) -> str:
        return self.name if self.is_available else f"{self.name} (Unavailable)"


class ConfigDependencyResolutionError(RuntimeError):
    """A shared-resource dependency decision cannot be made safely."""


class ConfigReferenceResolutionError(ValueError):
    """A persisted config contains a missing or cross-scope resource identity."""


class SceneTargetAlreadyExistsError(FileExistsError):
    """A create-only scene save collided with an existing user identity."""

    recovery_path: Path | None = None

    @property
    def recovery_required(self) -> bool:
        return self.recovery_path is not None


class SceneTargetRevisionChangedError(RuntimeError):
    """A user Scene changed after the caller froze its expected revision."""

    def __init__(
        self,
        message: str,
        *,
        recovery_path: str | Path | None = None,
        mutation_receipt: object | None = None,
    ) -> None:
        super().__init__(message)
        self.recovery_path = (
            Path(recovery_path) if recovery_path is not None else None
        )
        self.mutation_receipt = mutation_receipt

    @property
    def recovery_required(self) -> bool:
        return self.recovery_path is not None


def ensure_config_library() -> None:
    ensure_template_library()
    ensure_scene_library()


@contextmanager
def library_read_session() -> Iterator[None]:
    """Share successful library materialization within one bounded read flow."""

    active = _LIBRARY_ENSURE_SESSION.get()
    if active is not None:
        yield
        return
    token = _LIBRARY_ENSURE_SESSION.set(set())
    try:
        yield
    finally:
        _LIBRARY_ENSURE_SESSION.reset(token)


def ensure_template_library() -> None:
    """Materialize only the template runtime library."""

    session = _LIBRARY_ENSURE_SESSION.get()
    if session is not None and "template" in session:
        return
    _seed_template_library()
    if session is not None:
        session.add("template")


def ensure_scene_library() -> None:
    """Materialize only the plan runtime library."""

    session = _LIBRARY_ENSURE_SESSION.get()
    if session is not None and "scene" in session:
        return
    # A plan cannot be seeded or normalized before its exact template
    # identities exist.  Keep this ordering local so direct scene-library
    # callers cannot create half-resolved plans.
    ensure_template_library()
    _seed_scene_library()
    if session is not None:
        session.add("scene")


def list_template_entries(mode_id: str | None = None) -> list[ConfigLibraryEntry]:
    ensure_template_library()
    return _list_entries(
        "template",
        TEMPLATE_LIBRARY_DIR,
        load_template,
        mode_id=mode_id,
    )


def list_template_source_entries(
    mode_id: str,
    source_type: str,
) -> list[ConfigLibraryEntry]:
    """List one provenance bucket without user-over-builtin deduplication."""

    ensure_template_library()
    source = str(source_type or "").strip()
    if source not in _SOURCE_BUCKETS:
        raise ValueError(f"unsupported template source type: {source_type}")
    return _list_entries(
        "template",
        TEMPLATE_LIBRARY_DIR,
        load_template,
        mode_id=_normalize_mode_id(mode_id),
        source_type=source,
    )


def list_scene_entries(mode_id: str | None = None) -> list[ConfigLibraryEntry]:
    ensure_scene_library()
    return _list_entries(
        "scene",
        SCENE_LIBRARY_DIR,
        load_scene,
        mode_id=mode_id,
    )


def list_scene_descriptors(mode_id: str | None = None) -> list[SceneLibraryDescriptor]:
    ensure_scene_library()
    descriptors: list[SceneLibraryDescriptor] = []
    paths = list(_iter_config_files(
        SCENE_LIBRARY_DIR,
        mode_id=mode_id,
    ))
    _assert_unique_config_identities(paths, SCENE_LIBRARY_DIR, kind="plan")
    for path in paths:
        descriptor = _build_scene_descriptor_from_path(path)
        if descriptor is not None:
            descriptors.append(descriptor)
    descriptors = _dedupe_scene_descriptors(descriptors)
    descriptors.sort(
        key=lambda item: (
            1 if item.source_type == "builtin" else 0,
            item.display_order,
            item.name,
            item.config_id,
        )
    )
    return descriptors


def get_template_entry(
    template_id: str,
    mode_id: str | None = None,
) -> ConfigLibraryEntry | None:
    ensure_template_library()
    return _get_entry(
        "template",
        TEMPLATE_LIBRARY_DIR,
        template_id,
        load_template,
        mode_id=mode_id,
    )


def get_scene_entry(
    scene_id: str, mode_id: str | None = None
) -> ConfigLibraryEntry | None:
    ensure_scene_library()
    return _get_entry(
        "scene",
        SCENE_LIBRARY_DIR,
        scene_id,
        load_scene,
        mode_id=mode_id,
    )


def get_scene_descriptor(
    scene_id: str,
    mode_id: str | None = None,
) -> SceneLibraryDescriptor | None:
    path = _find_config_path(
        SCENE_LIBRARY_DIR,
        scene_id,
        mode_id=mode_id,
    )
    if path is None:
        return None
    return _build_scene_descriptor_from_path(path)


def load_template_from_library(
    template_id: str,
    mode_id: str | None = None,
):
    entry = get_template_entry(template_id, mode_id=mode_id)
    if entry is not None:
        return _load_template_entry_config(entry.path, entry.config_id, entry.source_type)
    requested = str(template_id or "").strip() or "<empty>"
    mode = _normalize_mode_id(mode_id)
    raise FileNotFoundError(
        f"template_ref_unresolved: mode={mode}; template_id={requested}"
    )


def _load_template_entry_config(
    path: Path,
    template_id: str,
    source_type: str,
):
    """Load the exact library resource without applying a second source."""

    del template_id
    if source_type == "user":
        return load_compatible_user_template(path)
    return load_template(path)


def load_scene_from_library(scene_id: str, mode_id: str | None = None):
    ensure_scene_library()
    path = _find_config_path(
        SCENE_LIBRARY_DIR,
        scene_id,
        mode_id=mode_id,
    )
    if path is not None:
        entry = ConfigLibraryEntry(
            "scene",
            path.stem,
            path.stem,
            path,
            mode_id=_mode_id_from_scoped_path(path, SCENE_LIBRARY_DIR),
            source_type=_source_type_from_scoped_path(path, SCENE_LIBRARY_DIR),
        )
        return _load_scene_entry(entry)
    requested = str(scene_id or "").strip() or "<empty>"
    mode = _normalize_mode_id(mode_id)
    raise FileNotFoundError(
        f"plan_ref_unresolved: mode={mode}; plan_id={requested}"
    )


def validate_scene_resource_ids(scene, *, mode_id: str | None = None):
    """Return a validated copy of a plan without attaching runtime paths/revisions."""

    return _normalize_scene_templates(scene, mode_id=mode_id)


def default_template_entry(mode_id: str | None = None) -> ConfigLibraryEntry | None:
    mode = _normalize_mode_id(mode_id)
    template_id = _default_template_id_for_mode(mode)
    return get_template_entry(template_id, mode_id=mode)


def default_scene_entry(mode_id: str | None = None) -> ConfigLibraryEntry | None:
    mode = _normalize_mode_id(mode_id)
    scene_id = _default_scene_id_for_mode(mode)
    return get_scene_entry(scene_id, mode_id=mode)


def default_scene_descriptor(
    mode_id: str | None = None,
) -> SceneLibraryDescriptor | None:
    mode = _normalize_mode_id(mode_id)
    scene_id = _default_scene_id_for_mode(mode)
    return get_scene_descriptor(scene_id, mode_id=mode)


def template_dependent_scene_descriptors(
    template_id: str,
    *,
    mode_id: str,
) -> tuple[SceneLibraryDescriptor, ...]:
    """Return plans whose persisted contract references one shared template."""

    target = str(template_id or "").strip()
    if not target:
        return ()
    dependents: list[SceneLibraryDescriptor] = []
    for descriptor in list_scene_descriptors(mode_id=mode_id):
        if not descriptor.is_available:
            raise ConfigDependencyResolutionError(
                "plan_dependency_unresolved:"
                f"{descriptor.config_id}:{descriptor.load_error or 'unavailable'}"
            )
        referenced = {
            str(descriptor.template_id or "").strip(),
            *(str(item or "").strip() for item in descriptor.compatible_template_ids),
        }
        if target in referenced:
            dependents.append(descriptor)
    return tuple(dependents)


def is_template_library_path(path: str | Path) -> bool:
    return bool(_source_type_from_scoped_path(Path(path), TEMPLATE_LIBRARY_DIR))


def is_scene_library_path(path: str | Path) -> bool:
    return bool(_source_type_from_scoped_path(Path(path), SCENE_LIBRARY_DIR))


def is_template_user_library_path(path: str | Path) -> bool:
    """Return whether ``path`` is an owned, non-symbolic user template file."""

    return _is_owned_user_config_path(Path(path), TEMPLATE_LIBRARY_DIR)


def is_scene_user_library_path(path: str | Path) -> bool:
    """Return whether ``path`` is an owned, non-symbolic user plan file."""

    return _is_owned_user_config_path(Path(path), SCENE_LIBRARY_DIR)


def template_source_type_for_path(path: str | Path) -> str:
    """Resolve a template resource origin from its authoritative directory."""
    candidate = Path(path)
    return _source_type_from_scoped_path(candidate, TEMPLATE_LIBRARY_DIR) or "external"


def scene_source_type_for_path(path: str | Path) -> str:
    """Resolve a plan resource origin from its authoritative directory."""
    candidate = Path(path)
    return _source_type_from_scoped_path(candidate, SCENE_LIBRARY_DIR) or "external"


def template_user_dir(mode_id: str | None = None) -> Path:
    return _mode_source_dir(TEMPLATE_LIBRARY_DIR, _normalize_mode_id(mode_id), "user")


def scene_user_dir(mode_id: str | None = None) -> Path:
    return _mode_source_dir(SCENE_LIBRARY_DIR, _normalize_mode_id(mode_id), "user")


def is_template_library_lexical_path(path: str | Path) -> bool:
    """Return whether the un-resolved path is lexically inside the template library."""

    return _is_lexically_under(Path(path), TEMPLATE_LIBRARY_DIR)


def validate_template_library_write_path(path: str | Path) -> Path:
    """Validate one template-library write target without following links."""

    return _validate_library_write_path(Path(path), TEMPLATE_LIBRARY_DIR)


def template_user_target_path(
    template_id: str,
    *,
    mode_id: str | None = None,
) -> Path:
    """Return a prepared, owned target for a user template."""

    mode = _normalize_mode_id(mode_id)
    entry_id = _require_safe_config_id(template_id)
    target_dir = _prepare_owned_library_directory(
        template_user_dir(mode),
        TEMPLATE_LIBRARY_DIR,
        mode_id=mode,
        source_type="user",
    )
    return _validate_library_write_path(
        target_dir / f"{entry_id}.json",
        TEMPLATE_LIBRARY_DIR,
    )


def scene_user_target_path(
    scene_id: str,
    *,
    mode_id: str | None = None,
) -> Path:
    """Return a prepared, owned target for a user scene."""

    mode = _normalize_mode_id(mode_id)
    entry_id = _require_config_id_for_root(
        SCENE_LIBRARY_DIR,
        scene_id,
        label="scene id",
    )
    target_dir = _prepare_owned_library_directory(
        scene_user_dir(mode),
        SCENE_LIBRARY_DIR,
        mode_id=mode,
        source_type="user",
    )
    return _validate_library_write_path(
        target_dir / f"{entry_id}.json",
        SCENE_LIBRARY_DIR,
    )


def validate_scene_library_write_path(path: str | Path) -> Path:
    """Validate one scene-library write target without following links."""

    return _validate_library_write_path(Path(path), SCENE_LIBRARY_DIR)


def template_library_watch_dirs(mode_id: str | None = None) -> list[Path]:
    return _watch_dirs(TEMPLATE_LIBRARY_DIR, mode_id=mode_id)


def scene_library_watch_dirs(mode_id: str | None = None) -> list[Path]:
    return _watch_dirs(SCENE_LIBRARY_DIR, mode_id=mode_id)


def save_template_to_library(
    template,
    template_id: str | None = None,
    *,
    mode_id: str | None = None,
) -> ConfigLibraryEntry:
    ensure_template_library()
    requested_id = str(template_id or "").strip()
    entry_id = _require_safe_config_id(
        requested_id
        or _safe_config_id(getattr(template, "name", "") or "template")
    )
    mode = _normalize_mode_id(mode_id)
    _assert_user_id_does_not_shadow_builtin(
        TEMPLATE_LIBRARY_DIR,
        entry_id,
        mode_id=mode,
        kind="template",
    )
    target = template_user_target_path(entry_id, mode_id=mode)
    save_template(template, target)
    reloaded = load_template(target)
    return ConfigLibraryEntry(
        "template",
        entry_id,
        str(getattr(reloaded, "name", "") or entry_id),
        target,
        mode_id=mode,
        source_type="user",
    )


def save_scene_to_library(
    scene,
    scene_id: str | None = None,
    *,
    mode_id: str | None = None,
    expected_absent: bool = False,
    expected_revision: str | None = None,
) -> ConfigLibraryEntry:
    """Persist a user scene.

    ``expected_absent`` is the create-only contract used when a built-in or
    external scene is forked into the user library.  The final publish is an
    atomic no-replace operation, so a target created after identity allocation
    is never overwritten.  ``expected_revision`` is the update contract: the
    writer serializes and validates the replacement first, then rechecks the
    target immediately before the atomic replace.  A mismatch is never
    overwritten.
    """

    ensure_scene_library()
    if scene_id is None:
        from src.config.scene_id_rules import safe_scene_file_stem

        fallback_id = safe_scene_file_stem(getattr(scene, "name", "") or "plan")
    else:
        # An explicit identity is a persisted contract, not a display name.
        # Preserve it verbatim so canonical validation cannot silently trim or
        # sanitize it before deciding whether it is valid.
        fallback_id = str(scene_id)
    entry_id = _require_config_id_for_root(
        SCENE_LIBRARY_DIR,
        fallback_id,
        label="scene id",
    )
    mode = _normalize_mode_id(
        mode_id
        or str(getattr(scene, "mode_id", "") or "").strip()
        or _mode_id_for_scene_id(entry_id)
    )
    _assert_user_id_does_not_shadow_builtin(
        SCENE_LIBRARY_DIR,
        entry_id,
        mode_id=mode,
        kind="plan",
    )
    canonical_target = scene_user_target_path(entry_id, mode_id=mode)
    existing_candidates = _scene_user_identity_candidates(
        canonical_target,
        scene_id=entry_id,
    )
    if len(existing_candidates) > 1:
        details = ",".join(str(candidate) for candidate in existing_candidates)
        raise ConfigReferenceResolutionError(
            "plan_id_ambiguous:"
            f" mode={mode}; id={entry_id}; candidates={details}"
        )
    if (
        expected_revision is not None
        and existing_candidates
        and existing_candidates[0].stem != entry_id
    ):
        raise ConfigReferenceResolutionError(
            "plan_update_identity_case_mismatch:"
            f" requested={entry_id}; authoritative={existing_candidates[0].stem}"
        )
    # Updates preserve the authoritative filename spelling (for example
    # ``Plan.JSON``).  Only forks/new identities synthesize the canonical
    # lowercase suffix.
    target = (
        validate_scene_library_write_path(existing_candidates[0])
        if expected_revision is not None and existing_candidates
        else canonical_target
    )
    normalized_scene = deepcopy(scene)
    _set_scene_identity(normalized_scene, entry_id)
    normalized_scene = _normalize_scene_templates(normalized_scene, mode_id=mode)
    prepared_entry = ConfigLibraryEntry(
        "scene", entry_id, entry_id, target, mode_id=mode, source_type="user"
    )
    if expected_absent and expected_revision is not None:
        raise ValueError("create-only Scene save cannot declare an expected revision")
    if expected_absent:
        reloaded, published_revision = _save_new_scene_without_replacement(
            normalized_scene,
            prepared_entry,
        )
    elif expected_revision is not None:
        reloaded, published_revision = _save_existing_scene_if_revision(
            normalized_scene,
            prepared_entry,
            expected_revision=expected_revision,
        )
    else:
        # The public API has no unsafe overwrite mode.  An absent identity is
        # created with the same no-replace contract as an explicit fork; an
        # existing identity requires the caller to freeze ``expected_revision``.
        reloaded, published_revision = _save_new_scene_without_replacement(
            normalized_scene,
            prepared_entry,
        )
    recovery_probe_fallback = (
        target.parent / f"{_scene_recovery_directory_prefix(target)}unreadable"
    )
    try:
        pending_recovery = scene_recovery_artifacts(target)
    except Exception:
        pending_recovery = (recovery_probe_fallback,)
    if pending_recovery:
        try:
            finalize_committed_scene_recovery(
                target,
                expected_revision=published_revision,
            )
        except Exception:
            pass
        try:
            pending_recovery = scene_recovery_artifacts(target)
        except Exception:
            pending_recovery = (recovery_probe_fallback,)
    return ConfigLibraryEntry(
        "scene",
        entry_id,
        str(getattr(reloaded, "name", "") or entry_id),
        target,
        mode_id=mode,
        source_type="user",
        revision=published_revision,
        recovery_path=pending_recovery[0] if pending_recovery else None,
    )


def scene_file_revision(path: str | Path) -> str:
    """Return the canonical revision for one validated Scene library path."""

    target = validate_scene_library_write_path(path)
    try:
        payload = target.read_bytes()
    except FileNotFoundError:
        return "missing"
    except (IsADirectoryError, PermissionError) as exc:
        raise OSError(f"scene target is not a readable file: {target}") from exc
    return _scene_payload_revision(payload)


def _scene_payload_revision(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _save_existing_scene_if_revision(
    scene,
    entry: ConfigLibraryEntry,
    *,
    expected_revision: str,
):
    """Replace an existing Scene without ever overwriting an unverified file.

    A plain ``revision check -> os.replace`` is not a compare-and-swap: another
    writer can win between those two operations and then be overwritten.  The
    target is instead moved into an identity-scoped recovery directory first.
    The bytes actually removed from the authoritative name are then verified,
    and the prepared replacement is published with a no-replace hard link.
    Every compensating restore uses the same no-replace rule.
    """

    target = validate_scene_library_write_path(entry.path)
    normalized_expected = str(expected_revision or "").strip()
    if not normalized_expected or normalized_expected == "missing":
        raise SceneTargetRevisionChangedError(
            f"scene_target_revision_changed: path={target}; expected={normalized_expected or '<empty>'}"
        )

    with _scene_create_lock(target, scene_id=entry.config_id):
        _assert_no_scene_recovery_artifacts(target)
        locked_candidates = _scene_user_identity_candidates(
            target,
            scene_id=entry.config_id,
        )
        if (
            len(locked_candidates) != 1
            or _lexical_path_key(locked_candidates[0])
            != _lexical_path_key(target)
        ):
            details = ",".join(str(path) for path in locked_candidates) or "<missing>"
            raise SceneTargetRevisionChangedError(
                "scene_target_identity_changed:"
                f" path={target}; candidates={details}"
            )
        actual_revision = scene_file_revision(target)
        if actual_revision != normalized_expected:
            raise SceneTargetRevisionChangedError(
                "scene_target_revision_changed:"
                f" path={target}; expected={normalized_expected}; actual={actual_revision}"
            )

        recovery_dir = _create_scene_recovery_directory(
            target,
            expected_revision=normalized_expected,
            phase="prepare_update",
        )
        replacement_path = recovery_dir / "replacement.json"
        displaced_path = recovery_dir / "displaced.json"
        preserve_recovery = False
        try:
            save_scene(scene, replacement_path)
            reloaded = _load_scene_entry(
                ConfigLibraryEntry(
                    "scene",
                    entry.config_id,
                    entry.config_id,
                    replacement_path,
                    mode_id=entry.mode_id,
                    source_type="user",
                )
            )
            published_revision = _scene_payload_revision(
                replacement_path.read_bytes()
            )
            _write_scene_recovery_manifest(
                recovery_dir,
                target=target,
                expected_revision=normalized_expected,
                replacement_revision=published_revision,
                phase="replacement_validated",
            )

            try:
                os.rename(target, displaced_path)
            except FileNotFoundError as exc:
                raise SceneTargetRevisionChangedError(
                    "scene_target_revision_changed:"
                    f" path={target}; expected={normalized_expected}; actual=missing"
                ) from exc

            try:
                displaced_revision = _scene_payload_revision(
                    displaced_path.read_bytes()
                )
            except OSError as exc:
                preserve_recovery = True
                receipt = SceneFileMutationReceipt(
                    target=target,
                    recovery_dir=recovery_dir,
                    displaced_path=displaced_path,
                    before_revision=normalized_expected,
                    after_revision="missing",
                    intent="restore_captured",
                )
                raise SceneTargetRevisionChangedError(
                    "moved Scene target is unreadable; recovery is required:"
                    f" evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                    mutation_receipt=receipt,
                ) from exc
            if displaced_revision != normalized_expected:
                preserve_recovery = True
                _write_scene_recovery_manifest(
                    recovery_dir,
                    target=target,
                    expected_revision=normalized_expected,
                    observed_revision=displaced_revision,
                    replacement_revision=published_revision,
                    phase="move_revision_conflict",
                )
                _restore_quarantined_scene_without_replacement(
                    displaced_path,
                    target,
                    recovery_dir=recovery_dir,
                    expected_revision=displaced_revision,
                )
                preserve_recovery = False
                _discard_scene_recovery_directory(recovery_dir)
                raise SceneTargetRevisionChangedError(
                    "scene_target_revision_changed_during_move:"
                    f" path={target}; expected={normalized_expected};"
                    f" actual={displaced_revision}"
                )

            try:
                os.link(replacement_path, target, follow_symlinks=False)
            except FileExistsError as exc:
                preserve_recovery = True
                _write_scene_recovery_manifest(
                    recovery_dir,
                    target=target,
                    expected_revision=normalized_expected,
                    observed_revision=scene_file_revision(target),
                    replacement_revision=published_revision,
                    phase="publish_target_recreated",
                )
                raise SceneTargetRevisionChangedError(
                    "scene_target_recreated_during_publication:"
                    f" path={target}; recovery={recovery_dir}",
                    recovery_path=recovery_dir,
                ) from exc
            except OSError as exc:
                preserve_recovery = True
                _write_scene_recovery_manifest(
                    recovery_dir,
                    target=target,
                    expected_revision=normalized_expected,
                    replacement_revision=published_revision,
                    phase="publish_failed_before_visibility",
                )
                _restore_quarantined_scene_without_replacement(
                    displaced_path,
                    target,
                    recovery_dir=recovery_dir,
                    expected_revision=normalized_expected,
                )
                preserve_recovery = False
                _discard_scene_recovery_directory(recovery_dir)
                raise OSError(
                    f"scene publication failed; original target restored: {target}"
                ) from exc

            try:
                _assert_scene_publication_is_unique(
                    target,
                    temporary_path=replacement_path,
                    scene_id=entry.config_id,
                    mode_id=entry.mode_id,
                )
            except Exception as exc:
                preserve_recovery = True
                receipt = SceneFileMutationReceipt(
                    target=target,
                    recovery_dir=recovery_dir,
                    displaced_path=displaced_path,
                    before_revision=normalized_expected,
                    after_revision=published_revision,
                    intent="published_mutation",
                )
                try:
                    _write_scene_recovery_manifest(
                        recovery_dir,
                        target=target,
                        expected_revision=normalized_expected,
                        replacement_revision=published_revision,
                        phase="update_casefold_identity_conflict",
                    )
                except (OSError, ValueError) as manifest_exc:
                    raise SceneTargetRevisionChangedError(
                        "published Scene verification failed and its recovery "
                        f"manifest could not be updated: evidence={recovery_dir}",
                        recovery_path=recovery_dir,
                        mutation_receipt=receipt,
                    ) from manifest_exc
                raise SceneTargetRevisionChangedError(
                    "scene_target_identity_changed_during_publication:"
                    f" path={target}; recovery={recovery_dir}",
                    recovery_path=recovery_dir,
                    mutation_receipt=receipt,
                ) from exc

            try:
                same_publication = os.path.samefile(replacement_path, target)
                verified_revision = scene_file_revision(target)
            except (OSError, ValueError):
                same_publication = False
                verified_revision = "unreadable"
            if not same_publication or verified_revision != published_revision:
                preserve_recovery = True
                receipt = SceneFileMutationReceipt(
                    target=target,
                    recovery_dir=recovery_dir,
                    displaced_path=displaced_path,
                    before_revision=normalized_expected,
                    after_revision=published_revision,
                    intent="published_mutation",
                )
                try:
                    _write_scene_recovery_manifest(
                        recovery_dir,
                        target=target,
                        expected_revision=normalized_expected,
                        observed_revision=verified_revision,
                        replacement_revision=published_revision,
                        phase="publication_verification_conflict",
                    )
                except (OSError, ValueError) as manifest_exc:
                    raise SceneTargetRevisionChangedError(
                        "published Scene ownership verification failed and its "
                        f"recovery manifest could not be updated: evidence={recovery_dir}",
                        recovery_path=recovery_dir,
                        mutation_receipt=receipt,
                    ) from manifest_exc
                raise SceneTargetRevisionChangedError(
                    "scene_target_changed_after_publication:"
                    f" path={target}; recovery={recovery_dir}",
                    recovery_path=recovery_dir,
                    mutation_receipt=receipt,
                )

            try:
                displaced_path.unlink()
                _discard_scene_recovery_directory(recovery_dir)
            except (OSError, ValueError):
                # The authoritative target is already verified and the caller
                # must receive its receipt.  Retain cleanup evidence instead of
                # turning a committed save into an unreceipted failure.
                preserve_recovery = True
            return reloaded, published_revision
        except BaseException:
            if displaced_path.exists() or preserve_recovery:
                preserve_recovery = True
            raise
        finally:
            if not preserve_recovery:
                _discard_scene_recovery_directory(recovery_dir, ignore_errors=True)


def replace_scene_file_if_revision(
    path: str | Path,
    *,
    expected_revision: str,
    replacement_payload: bytes | None,
    retain_recovery: bool = False,
) -> str | SceneFileMutationReceipt:
    """Conditionally replace or delete one owned user Scene file.

    ``replacement_payload=None`` is a conditional delete.  The function never
    calls ``replace`` or ``unlink`` on the authoritative pathname.  It first
    moves the current pathname into quarantine, verifies the captured bytes,
    and publishes/restores only with a no-replace hard link.
    """

    target = validate_scene_library_write_path(path)
    if retain_recovery and replacement_payload is not None:
        raise ValueError("retained Scene mutations currently support delete only")
    if scene_source_type_for_path(target) != "user":
        raise ValueError(f"not an owned user Scene path: {target}")
    normalized_expected = str(expected_revision or "").strip()
    if not normalized_expected or normalized_expected == "missing":
        raise SceneTargetRevisionChangedError(
            f"scene_target_revision_changed: path={target}; expected={normalized_expected or '<empty>'}"
        )

    with _scene_create_lock(target, scene_id=target.stem):
        _assert_no_scene_recovery_artifacts(target)
        locked_candidates = _scene_user_identity_candidates(
            target,
            scene_id=target.stem,
        )
        if (
            len(locked_candidates) != 1
            or _lexical_path_key(locked_candidates[0])
            != _lexical_path_key(target)
        ):
            details = ",".join(str(path) for path in locked_candidates) or "<missing>"
            raise SceneTargetRevisionChangedError(
                "conditional_scene_identity_changed:"
                f" path={target}; candidates={details}"
            )
        actual_revision = scene_file_revision(target)
        if actual_revision != normalized_expected:
            raise SceneTargetRevisionChangedError(
                "scene_target_revision_changed:"
                f" path={target}; expected={normalized_expected}; actual={actual_revision}"
            )

        recovery_dir = _create_scene_recovery_directory(
            target,
            expected_revision=normalized_expected,
            phase="prepare_conditional_mutation",
        )
        replacement_path = recovery_dir / "replacement.json"
        displaced_path = recovery_dir / "displaced.json"
        preserve_recovery = False
        replacement_revision = "missing"
        try:
            if replacement_payload is not None:
                atomic_write_bytes(replacement_path, bytes(replacement_payload))
                replacement_scene = load_scene(replacement_path)
                mode_id = _mode_id_from_scoped_path(target, SCENE_LIBRARY_DIR)
                _validate_scene_storage_identity(
                    replacement_scene,
                    ConfigLibraryEntry(
                        "scene",
                        target.stem,
                        target.stem,
                        replacement_path,
                        mode_id=mode_id,
                        source_type="user",
                    ),
                )
                replacement_revision = _scene_payload_revision(
                    replacement_path.read_bytes()
                )
            _write_scene_recovery_manifest(
                recovery_dir,
                target=target,
                expected_revision=normalized_expected,
                replacement_revision=replacement_revision,
                phase="conditional_replacement_validated",
            )

            try:
                os.rename(target, displaced_path)
            except FileNotFoundError as exc:
                raise SceneTargetRevisionChangedError(
                    "scene_target_revision_changed:"
                    f" path={target}; expected={normalized_expected}; actual=missing"
                ) from exc
            try:
                displaced_revision = _scene_payload_revision(
                    displaced_path.read_bytes()
                )
            except OSError as exc:
                preserve_recovery = True
                receipt = SceneFileMutationReceipt(
                    target=target,
                    recovery_dir=recovery_dir,
                    displaced_path=displaced_path,
                    before_revision=normalized_expected,
                    after_revision="missing",
                    intent="restore_captured",
                )
                raise SceneTargetRevisionChangedError(
                    "moved Scene target is unreadable; recovery is required:"
                    f" evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                    mutation_receipt=receipt,
                ) from exc
            if displaced_revision != normalized_expected:
                preserve_recovery = True
                _write_scene_recovery_manifest(
                    recovery_dir,
                    target=target,
                    expected_revision=normalized_expected,
                    observed_revision=displaced_revision,
                    replacement_revision=replacement_revision,
                    phase="conditional_move_revision_conflict",
                )
                _restore_quarantined_scene_without_replacement(
                    displaced_path,
                    target,
                    recovery_dir=recovery_dir,
                    expected_revision=displaced_revision,
                )
                preserve_recovery = False
                _discard_scene_recovery_directory(recovery_dir)
                raise SceneTargetRevisionChangedError(
                    "scene_target_revision_changed_during_conditional_mutation:"
                    f" path={target}; actual={displaced_revision}"
                )

            if replacement_payload is not None:
                try:
                    os.link(replacement_path, target, follow_symlinks=False)
                except FileExistsError as exc:
                    preserve_recovery = True
                    _write_scene_recovery_manifest(
                        recovery_dir,
                        target=target,
                        expected_revision=normalized_expected,
                        observed_revision=scene_file_revision(target),
                        replacement_revision=replacement_revision,
                        phase="conditional_publish_target_recreated",
                    )
                    raise SceneTargetRevisionChangedError(
                        "scene_target_recreated_during_conditional_mutation:"
                        f" path={target}; recovery={recovery_dir}",
                        recovery_path=recovery_dir,
                    ) from exc
                except OSError as exc:
                    preserve_recovery = True
                    _write_scene_recovery_manifest(
                        recovery_dir,
                        target=target,
                        expected_revision=normalized_expected,
                        replacement_revision=replacement_revision,
                        phase="conditional_publish_failed_before_visibility",
                    )
                    _restore_quarantined_scene_without_replacement(
                        displaced_path,
                        target,
                        recovery_dir=recovery_dir,
                        expected_revision=normalized_expected,
                    )
                    preserve_recovery = False
                    _discard_scene_recovery_directory(recovery_dir)
                    raise OSError(
                        "conditional Scene publication failed; original target "
                        f"restored: {target}"
                    ) from exc
                try:
                    owns_target = os.path.samefile(replacement_path, target)
                    current_revision = scene_file_revision(target)
                except OSError:
                    owns_target = False
                    current_revision = "unreadable"
                if not owns_target or current_revision != replacement_revision:
                    preserve_recovery = True
                    _write_scene_recovery_manifest(
                        recovery_dir,
                        target=target,
                        expected_revision=normalized_expected,
                        observed_revision=current_revision,
                        replacement_revision=replacement_revision,
                        phase="conditional_publication_verification_conflict",
                    )
                    raise SceneTargetRevisionChangedError(
                        "scene_target_changed_during_conditional_verification:"
                        f" path={target}; recovery={recovery_dir}",
                        recovery_path=recovery_dir,
                    )
                try:
                    _assert_scene_publication_is_unique(
                        target,
                        temporary_path=replacement_path,
                        scene_id=target.stem,
                        mode_id=_mode_id_from_scoped_path(
                            target,
                            SCENE_LIBRARY_DIR,
                        ),
                    )
                except Exception as exc:
                    preserve_recovery = True
                    _write_scene_recovery_manifest(
                        recovery_dir,
                        target=target,
                        expected_revision=normalized_expected,
                        replacement_revision=replacement_revision,
                        phase="conditional_casefold_identity_conflict",
                    )
                    raise SceneTargetRevisionChangedError(
                        "conditional_scene_identity_changed_during_publication:"
                        f" path={target}; recovery={recovery_dir}",
                        recovery_path=recovery_dir,
                    ) from exc

            if replacement_payload is None:
                recreated = _scene_user_identity_candidates(
                    target,
                    scene_id=target.stem,
                )
                if recreated:
                    preserve_recovery = True
                    details = ",".join(str(path) for path in recreated)
                    _write_scene_recovery_manifest(
                        recovery_dir,
                        target=target,
                        expected_revision=normalized_expected,
                        replacement_revision="missing",
                        phase="conditional_delete_identity_recreated",
                    )
                    raise SceneTargetRevisionChangedError(
                        "conditional_scene_delete_target_recreated:"
                        f" candidates={details}; recovery={recovery_dir}",
                        recovery_path=recovery_dir,
                    )

            if replacement_payload is None and retain_recovery:
                try:
                    _write_scene_recovery_manifest(
                        recovery_dir,
                        target=target,
                        expected_revision=normalized_expected,
                        observed_revision=displaced_revision,
                        replacement_revision="missing",
                        phase="conditional_delete_retained",
                    )
                except (OSError, ValueError) as exc:
                    preserve_recovery = True
                    _restore_quarantined_scene_without_replacement(
                        displaced_path,
                        target,
                        recovery_dir=recovery_dir,
                        expected_revision=normalized_expected,
                    )
                    preserve_recovery = False
                    _discard_scene_recovery_directory(recovery_dir)
                    raise OSError(
                        "retained Scene delete could not persist its transaction; "
                        f"original target restored: {target}"
                    ) from exc
                preserve_recovery = True
                return SceneFileMutationReceipt(
                    target=target,
                    recovery_dir=recovery_dir,
                    displaced_path=displaced_path,
                    before_revision=normalized_expected,
                    after_revision="missing",
                )

            try:
                displaced_path.unlink()
                _discard_scene_recovery_directory(recovery_dir)
            except (OSError, ValueError):
                preserve_recovery = True
                return SceneFileMutationReceipt(
                    target=target,
                    recovery_dir=recovery_dir,
                    displaced_path=displaced_path,
                    before_revision=normalized_expected,
                    after_revision=replacement_revision,
                )
            return replacement_revision
        except BaseException:
            if displaced_path.exists() or preserve_recovery:
                preserve_recovery = True
            raise
        finally:
            if not preserve_recovery:
                _discard_scene_recovery_directory(recovery_dir, ignore_errors=True)


def finalize_scene_file_mutation(receipt: SceneFileMutationReceipt) -> None:
    """Consume retained delete evidence after the outer UI transaction commits."""

    if receipt.intent != "conditional_mutation":
        raise ValueError("captured-occupant recovery cannot be finalized as a delete")
    target, recovery_dir, displaced_path = _validate_scene_mutation_receipt(receipt)
    with _scene_create_lock(target, scene_id=target.stem):
        if not recovery_dir.exists():
            candidates = _scene_user_identity_candidates(
                target,
                scene_id=target.stem,
            )
            if not candidates:
                return
            raise SceneTargetRevisionChangedError(
                "retained Scene delete was already rolled back; finalize refused:"
                f" target={target}"
            )
        manifest_path = recovery_dir / "manifest.json"
        if manifest_path.exists():
            manifest = _read_scene_recovery_manifest(recovery_dir)
            phase = str(manifest.get("phase", "") or "")
        elif displaced_path.exists():
            phase = "conditional_delete_retained"
        else:
            _discard_scene_recovery_directory(recovery_dir)
            return
        if phase == "delete_finalized_cleanup_pending":
            try:
                _discard_scene_recovery_directory(recovery_dir)
            except (OSError, ValueError) as exc:
                raise SceneTargetRevisionChangedError(
                    "retained Scene delete cleanup is still pending:"
                    f" evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                ) from exc
            return
        if phase not in {
            "conditional_delete_retained",
            "conditional_replacement_validated",
        }:
            raise SceneTargetRevisionChangedError(
                f"retained Scene delete has unexpected phase={phase!r}",
                recovery_path=recovery_dir,
            )
        observed = _scene_payload_revision(displaced_path.read_bytes())
        if observed != receipt.before_revision:
            raise SceneTargetRevisionChangedError(
                "retained Scene delete evidence changed before finalize:"
                f" evidence={recovery_dir}",
                recovery_path=recovery_dir,
            )
        _write_scene_recovery_manifest(
            recovery_dir,
            target=target,
            expected_revision=receipt.before_revision,
            observed_revision=observed,
            replacement_revision="missing",
            phase="delete_finalized_cleanup_pending",
        )
        try:
            displaced_path.unlink()
            _discard_scene_recovery_directory(recovery_dir)
        except (OSError, ValueError) as exc:
            raise SceneTargetRevisionChangedError(
                "retained Scene delete cleanup failed:"
                f" evidence={recovery_dir}",
                recovery_path=recovery_dir,
            ) from exc


def _rollback_published_scene_file_mutation(
    receipt: SceneFileMutationReceipt,
) -> bool:
    """Roll back one candidate whose no-replace publication may be visible.

    The replacement hard link is the ownership proof.  The authoritative name
    is moved back into the private recovery directory before it is classified,
    so a writer racing after any earlier observation is captured rather than
    unlinked.  A captured external winner is restored and reported with
    ``False``; only the exact published inode permits restoring the baseline.
    """

    target, recovery_dir, displaced_path = _validate_scene_mutation_receipt(receipt)
    replacement_path = recovery_dir / "replacement.json"
    captured_path = recovery_dir / "rollback-captured.json"
    with _scene_create_lock(target, scene_id=target.stem):
        if not recovery_dir.exists():
            candidates = _scene_user_identity_candidates(target, scene_id=target.stem)
            if (
                len(candidates) == 1
                and _lexical_path_key(candidates[0]) == _lexical_path_key(target)
            ):
                return scene_file_revision(target) == receipt.before_revision
            raise SceneTargetRevisionChangedError(
                "published Scene recovery evidence is missing before rollback:"
                f" target={target}; evidence={recovery_dir}",
                recovery_path=recovery_dir,
            )

        manifest_path = recovery_dir / "manifest.json"
        if not manifest_path.exists():
            if any(recovery_dir.iterdir()):
                raise SceneTargetRevisionChangedError(
                    f"published Scene recovery has no manifest: {recovery_dir}",
                    recovery_path=recovery_dir,
                )
            candidates = _scene_user_identity_candidates(target, scene_id=target.stem)
            if (
                len(candidates) != 1
                or _lexical_path_key(candidates[0]) != _lexical_path_key(target)
            ):
                raise SceneTargetRevisionChangedError(
                    "published Scene cleanup state is incomplete:"
                    f" evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                )
            restored_revision = scene_file_revision(target)
            _discard_scene_recovery_directory(recovery_dir)
            return restored_revision == receipt.before_revision

        manifest = _read_scene_recovery_manifest(recovery_dir)
        manifest_expected = str(manifest.get("expected_revision", "") or "").strip()
        manifest_replacement = str(
            manifest.get("replacement_revision", "") or ""
        ).strip()
        phase = str(manifest.get("phase", "") or "")
        if manifest_expected and manifest_expected != receipt.before_revision:
            raise SceneTargetRevisionChangedError(
                "published Scene receipt does not own its baseline evidence:"
                f" evidence={recovery_dir}",
                recovery_path=recovery_dir,
            )
        if (
            phase != "published_rollback_cleanup_pending"
            and manifest_replacement
            and manifest_replacement != receipt.after_revision
        ):
            raise SceneTargetRevisionChangedError(
                "published Scene receipt does not own its candidate evidence:"
                f" evidence={recovery_dir}",
                recovery_path=recovery_dir,
            )

        if phase == "published_rollback_cleanup_pending":
            restored_revision = str(
                manifest.get("replacement_revision", "") or ""
            ).strip()
            candidates = _scene_user_identity_candidates(target, scene_id=target.stem)
            if (
                len(candidates) != 1
                or _lexical_path_key(candidates[0]) != _lexical_path_key(target)
                or not restored_revision
                or scene_file_revision(target) != restored_revision
            ):
                raise SceneTargetRevisionChangedError(
                    "rolled-back published Scene changed before cleanup:"
                    f" evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                )
            try:
                _discard_scene_recovery_directory(recovery_dir)
            except (OSError, ValueError) as exc:
                raise SceneTargetRevisionChangedError(
                    "published Scene rollback cleanup is still pending:"
                    f" evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                ) from exc
            return restored_revision == receipt.before_revision

        allowed_phases = {
            "replacement_validated",
            "update_casefold_identity_conflict",
            "publication_verification_conflict",
        }
        if phase not in allowed_phases:
            raise SceneTargetRevisionChangedError(
                f"published Scene rollback has unexpected phase={phase!r}",
                recovery_path=recovery_dir,
            )
        if not displaced_path.exists() or not replacement_path.exists():
            raise SceneTargetRevisionChangedError(
                "published Scene rollback evidence is incomplete:"
                f" evidence={recovery_dir}",
                recovery_path=recovery_dir,
            )
        if (
            _scene_payload_revision(displaced_path.read_bytes())
            != receipt.before_revision
            or _scene_payload_revision(replacement_path.read_bytes())
            != receipt.after_revision
        ):
            raise SceneTargetRevisionChangedError(
                "published Scene rollback evidence changed:"
                f" evidence={recovery_dir}",
                recovery_path=recovery_dir,
            )

        candidates = _scene_user_identity_candidates(target, scene_id=target.stem)
        exact_candidates = tuple(
            candidate
            for candidate in candidates
            if _lexical_path_key(candidate) == _lexical_path_key(target)
        )
        case_variants = tuple(
            candidate
            for candidate in candidates
            if _lexical_path_key(candidate) != _lexical_path_key(target)
        )
        if case_variants or len(exact_candidates) > 1:
            details = ",".join(str(path) for path in candidates)
            raise SceneTargetRevisionChangedError(
                "published Scene identity changed before rollback:"
                f" candidates={details}; evidence={recovery_dir}",
                recovery_path=recovery_dir,
            )

        captured_revision = "missing"
        captured_is_publication = False
        if captured_path.exists():
            try:
                captured_revision = _scene_payload_revision(captured_path.read_bytes())
                captured_is_publication = (
                    os.path.samefile(captured_path, replacement_path)
                    and captured_revision == receipt.after_revision
                )
            except OSError as exc:
                raise SceneTargetRevisionChangedError(
                    "captured published Scene is unreadable during rollback:"
                    f" evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                ) from exc
        elif exact_candidates:
            try:
                os.rename(target, captured_path)
            except FileNotFoundError:
                remaining = _scene_user_identity_candidates(
                    target,
                    scene_id=target.stem,
                )
                if remaining:
                    details = ",".join(str(path) for path in remaining)
                    raise SceneTargetRevisionChangedError(
                        "published Scene target changed while rollback claimed it:"
                        f" candidates={details}; evidence={recovery_dir}",
                        recovery_path=recovery_dir,
                    )
            else:
                try:
                    captured_revision = _scene_payload_revision(
                        captured_path.read_bytes()
                    )
                    captured_is_publication = (
                        os.path.samefile(captured_path, replacement_path)
                        and captured_revision == receipt.after_revision
                    )
                except OSError as exc:
                    raise SceneTargetRevisionChangedError(
                        "claimed published Scene is unreadable during rollback:"
                        f" evidence={recovery_dir}",
                        recovery_path=recovery_dir,
                    ) from exc

        candidates_after_claim = _scene_user_identity_candidates(
            target,
            scene_id=target.stem,
        )
        if candidates_after_claim:
            already_restored_revision = ""
            if len(candidates_after_claim) == 1:
                try:
                    if os.path.samefile(target, displaced_path):
                        already_restored_revision = receipt.before_revision
                    elif captured_path.exists() and os.path.samefile(
                        target,
                        captured_path,
                    ):
                        already_restored_revision = captured_revision
                except OSError:
                    already_restored_revision = ""
            if not already_restored_revision:
                details = ",".join(str(path) for path in candidates_after_claim)
                raise SceneTargetRevisionChangedError(
                    "published Scene target was recreated during rollback:"
                    f" candidates={details}; evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                )
            restored_revision = already_restored_revision
        else:
            restore_source = (
                displaced_path
                if captured_revision == "missing" or captured_is_publication
                else captured_path
            )
            restored_revision = (
                receipt.before_revision
                if restore_source == displaced_path
                else captured_revision
            )
            _restore_quarantined_scene_without_replacement(
                restore_source,
                target,
                recovery_dir=recovery_dir,
                expected_revision=restored_revision,
                consume_quarantine=False,
            )

        try:
            _assert_scene_publication_is_unique(
                target,
                temporary_path=(
                    displaced_path
                    if restored_revision == receipt.before_revision
                    else captured_path
                ),
                scene_id=target.stem,
                mode_id=_mode_id_from_scoped_path(target, SCENE_LIBRARY_DIR),
            )
        except Exception as exc:
            raise SceneTargetRevisionChangedError(
                "rolled-back published Scene identity remains conflicted:"
                f" evidence={recovery_dir}",
                recovery_path=recovery_dir,
            ) from exc

        _write_scene_recovery_manifest(
            recovery_dir,
            target=target,
            expected_revision=receipt.before_revision,
            observed_revision=captured_revision,
            replacement_revision=restored_revision,
            phase="published_rollback_cleanup_pending",
        )
        try:
            _discard_scene_recovery_directory(recovery_dir)
        except (OSError, ValueError) as exc:
            raise SceneTargetRevisionChangedError(
                "published Scene rollback cleanup failed:"
                f" evidence={recovery_dir}",
                recovery_path=recovery_dir,
            ) from exc
        return restored_revision == receipt.before_revision


def rollback_scene_file_mutation(receipt: SceneFileMutationReceipt) -> bool:
    """Restore a retained delete without replacing an external recreation."""

    if not isinstance(receipt, SceneFileMutationReceipt):
        raise TypeError("invalid Scene file mutation receipt")
    if receipt.intent == "published_mutation":
        return _rollback_published_scene_file_mutation(receipt)
    if receipt.intent not in {"conditional_mutation", "restore_captured"}:
        raise ValueError(f"unsupported Scene mutation receipt intent: {receipt.intent}")

    target, recovery_dir, displaced_path = _validate_scene_mutation_receipt(receipt)
    with _scene_create_lock(target, scene_id=target.stem):
        if not recovery_dir.exists():
            candidates = _scene_user_identity_candidates(
                target,
                scene_id=target.stem,
            )
            if (
                len(candidates) == 1
                and _lexical_path_key(candidates[0]) == _lexical_path_key(target)
                and scene_file_revision(target) == receipt.before_revision
            ):
                return True
            raise SceneTargetRevisionChangedError(
                "retained Scene delete evidence is missing before rollback:"
                f" target={target}; evidence={recovery_dir}",
                recovery_path=recovery_dir,
            )
        manifest_path = recovery_dir / "manifest.json"
        if manifest_path.exists():
            manifest = _read_scene_recovery_manifest(recovery_dir)
            phase = str(manifest.get("phase", "") or "")
        elif displaced_path.exists():
            phase = "conditional_delete_retained"
        else:
            candidates = _scene_user_identity_candidates(
                target,
                scene_id=target.stem,
            )
            if (
                len(candidates) == 1
                and _lexical_path_key(candidates[0]) == _lexical_path_key(target)
            ):
                current_revision = scene_file_revision(target)
                _discard_scene_recovery_directory(recovery_dir)
                return current_revision == receipt.before_revision
            raise SceneTargetRevisionChangedError(
                "retained Scene delete cleanup state is incomplete:"
                f" evidence={recovery_dir}",
                recovery_path=recovery_dir,
            )
        if phase == "delete_rolled_back_cleanup_pending" and not displaced_path.exists():
            restored_revision = str(
                manifest.get("replacement_revision", "") or ""
            ).strip()
            candidates = _scene_user_identity_candidates(
                target,
                scene_id=target.stem,
            )
            if (
                len(candidates) != 1
                or _lexical_path_key(candidates[0]) != _lexical_path_key(target)
                or not restored_revision
                or scene_file_revision(target) != restored_revision
            ):
                raise SceneTargetRevisionChangedError(
                    "rolled-back Scene delete target changed before cleanup:"
                    f" evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                )
            try:
                _discard_scene_recovery_directory(recovery_dir)
            except (OSError, ValueError) as exc:
                raise SceneTargetRevisionChangedError(
                    "rolled-back Scene delete cleanup is still pending:"
                    f" evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                ) from exc
            return restored_revision == receipt.before_revision
        observed = _scene_payload_revision(displaced_path.read_bytes())
        restore_captured = receipt.intent == "restore_captured"
        if observed != receipt.before_revision and not restore_captured:
            raise SceneTargetRevisionChangedError(
                "retained Scene delete evidence changed before rollback:"
                f" evidence={recovery_dir}",
                recovery_path=recovery_dir,
            )
        candidates = _scene_user_identity_candidates(target, scene_id=target.stem)
        already_restored = False
        if len(candidates) == 1 and _lexical_path_key(candidates[0]) == _lexical_path_key(target):
            try:
                already_restored = (
                    os.path.samefile(displaced_path, target)
                    and scene_file_revision(target) == observed
                )
            except OSError:
                already_restored = False
        if phase == "delete_rolled_back_cleanup_pending":
            if not already_restored:
                raise SceneTargetRevisionChangedError(
                    "rolled-back Scene delete target changed before cleanup:"
                    f" evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                )
        elif phase in {
            "conditional_delete_retained",
            "conditional_replacement_validated",
            "replacement_validated",
        }:
            if candidates and not already_restored:
                details = ",".join(str(path) for path in candidates)
                raise SceneTargetRevisionChangedError(
                    "retained Scene delete target was recreated before rollback:"
                    f" candidates={details}; evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                )
            if not already_restored:
                _restore_quarantined_scene_without_replacement(
                    displaced_path,
                    target,
                    recovery_dir=recovery_dir,
                    expected_revision=observed,
                    consume_quarantine=False,
                )
        else:
            raise SceneTargetRevisionChangedError(
                f"retained Scene delete has unexpected phase={phase!r}",
                recovery_path=recovery_dir,
            )
        try:
            _assert_scene_publication_is_unique(
                target,
                temporary_path=displaced_path,
                scene_id=target.stem,
                mode_id=_mode_id_from_scoped_path(target, SCENE_LIBRARY_DIR),
            )
        except Exception as exc:
            raise SceneTargetRevisionChangedError(
                "retained Scene delete identity conflicted during rollback:"
                f" evidence={recovery_dir}",
                recovery_path=recovery_dir,
            ) from exc
        _write_scene_recovery_manifest(
            recovery_dir,
            target=target,
            expected_revision=receipt.before_revision,
            observed_revision=observed,
            replacement_revision=observed,
            phase="delete_rolled_back_cleanup_pending",
        )
        try:
            displaced_path.unlink()
            _discard_scene_recovery_directory(recovery_dir)
        except (OSError, ValueError) as exc:
            raise SceneTargetRevisionChangedError(
                "retained Scene delete rollback cleanup failed:"
                f" evidence={recovery_dir}",
                recovery_path=recovery_dir,
            ) from exc
        return observed == receipt.before_revision


def finalize_scene_file_cleanup(receipt: SceneFileMutationReceipt) -> None:
    """Consume cleanup evidence for one exact completed conditional mutation."""

    if receipt.intent != "conditional_mutation":
        raise ValueError("captured-occupant recovery is not committed cleanup")
    target, recovery_dir, displaced_path = _validate_scene_mutation_receipt(receipt)
    with _scene_create_lock(target, scene_id=target.stem):
        if not recovery_dir.exists():
            if receipt.after_revision == "missing":
                if _scene_user_identity_candidates(target, scene_id=target.stem):
                    raise SceneTargetRevisionChangedError(
                        f"conditionally deleted Scene was recreated: {target}"
                    )
            elif scene_file_revision(target) != receipt.after_revision:
                raise SceneTargetRevisionChangedError(
                    f"conditional Scene result changed before cleanup: {target}"
                )
            return

        manifest_path = recovery_dir / "manifest.json"
        if manifest_path.exists():
            manifest = _read_scene_recovery_manifest(recovery_dir)
            manifest_expected = str(
                manifest.get("expected_revision", "") or ""
            ).strip()
            manifest_after = str(
                manifest.get("replacement_revision", "") or ""
            ).strip()
            if manifest_expected and manifest_expected != receipt.before_revision:
                raise SceneTargetRevisionChangedError(
                    "conditional cleanup receipt does not own its evidence:"
                    f" evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                )
            if manifest_after and manifest_after != receipt.after_revision:
                raise SceneTargetRevisionChangedError(
                    "conditional cleanup result revision does not match evidence:"
                    f" evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                )

        if displaced_path.exists():
            displaced_revision = _scene_payload_revision(
                displaced_path.read_bytes()
            )
            if displaced_revision != receipt.before_revision:
                raise SceneTargetRevisionChangedError(
                    "conditional cleanup baseline evidence changed:"
                    f" evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                )

        if receipt.after_revision == "missing":
            if _scene_user_identity_candidates(target, scene_id=target.stem):
                raise SceneTargetRevisionChangedError(
                    "conditionally deleted Scene identity was recreated:"
                    f" evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                )
        else:
            candidates = _scene_user_identity_candidates(
                target,
                scene_id=target.stem,
            )
            if (
                len(candidates) != 1
                or _lexical_path_key(candidates[0]) != _lexical_path_key(target)
                or scene_file_revision(target) != receipt.after_revision
            ):
                raise SceneTargetRevisionChangedError(
                    "conditional Scene result changed before cleanup:"
                    f" evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                )
            replacement_path = recovery_dir / "replacement.json"
            if displaced_path.exists():
                try:
                    owns_target = (
                        replacement_path.exists()
                        and os.path.samefile(replacement_path, target)
                    )
                except OSError:
                    owns_target = False
                if not owns_target:
                    raise SceneTargetRevisionChangedError(
                        "conditional cleanup lacks publication inode proof:"
                        f" evidence={recovery_dir}",
                        recovery_path=recovery_dir,
                    )

        try:
            if manifest_path.exists():
                _write_scene_recovery_manifest(
                    recovery_dir,
                    target=target,
                    expected_revision=receipt.before_revision,
                    observed_revision=receipt.after_revision,
                    replacement_revision=receipt.after_revision,
                    phase="committed_cleanup_pending",
                )
            _discard_scene_recovery_directory(recovery_dir)
        except (OSError, ValueError) as exc:
            raise SceneTargetRevisionChangedError(
                "conditional Scene cleanup remains pending:"
                f" evidence={recovery_dir}",
                recovery_path=recovery_dir,
            ) from exc


def _validate_scene_mutation_receipt(
    receipt: SceneFileMutationReceipt,
) -> tuple[Path, Path, Path]:
    if not isinstance(receipt, SceneFileMutationReceipt):
        raise TypeError("invalid Scene file mutation receipt")
    target = validate_scene_library_write_path(receipt.target)
    recovery_dir = Path(receipt.recovery_dir)
    displaced_path = Path(receipt.displaced_path)
    if (
        _lexical_path_key(recovery_dir.parent) != _lexical_path_key(target.parent)
        or not recovery_dir.name.startswith(_scene_recovery_directory_prefix(target))
        or _lexical_path_key(displaced_path.parent) != _lexical_path_key(recovery_dir)
        or displaced_path.name != "displaced.json"
    ):
        raise ValueError("Scene mutation receipt path identity is invalid")
    if not recovery_dir.exists():
        return target, recovery_dir, displaced_path
    _assert_non_symbolic_library_path(recovery_dir, SCENE_LIBRARY_DIR)
    _assert_non_symbolic_library_path(displaced_path, SCENE_LIBRARY_DIR)
    return target, recovery_dir, displaced_path


def finalize_committed_scene_recovery(
    path: str | Path,
    *,
    expected_revision: str,
) -> None:
    """Garbage-collect recovery evidence for a verified successful publish."""

    target = validate_scene_library_write_path(path)
    normalized_expected = str(expected_revision or "").strip()
    if not normalized_expected or normalized_expected == "missing":
        raise ValueError(
            "committed Scene cleanup requires a frozen published revision"
        )
    with _scene_create_lock(target, scene_id=target.stem):
        if scene_file_revision(target) != normalized_expected:
            raise SceneTargetRevisionChangedError(
                f"committed Scene changed before recovery cleanup: {target}"
            )
        allowed_phases = {
            "replacement_validated",
            "create_replacement_validated",
            "conditional_replacement_validated",
            "committed_cleanup_pending",
        }
        for recovery_dir in scene_recovery_artifacts(target):
            _assert_non_symbolic_library_path(recovery_dir, SCENE_LIBRARY_DIR)
            manifest_path = recovery_dir / "manifest.json"
            replacement_path = recovery_dir / "replacement.json"
            if manifest_path.exists():
                manifest = _read_scene_recovery_manifest(recovery_dir)
                phase = str(manifest.get("phase", "") or "")
                manifest_revision = str(
                    manifest.get("replacement_revision", "") or ""
                ).strip()
                if phase not in allowed_phases or (
                    manifest_revision and manifest_revision != normalized_expected
                ):
                    raise SceneTargetRevisionChangedError(
                        "Scene recovery evidence does not belong to this receipt:"
                        f" evidence={recovery_dir}",
                        recovery_path=recovery_dir,
                    )
            elif any(recovery_dir.iterdir()):
                raise SceneTargetRevisionChangedError(
                    f"Scene recovery evidence has no manifest: {recovery_dir}",
                    recovery_path=recovery_dir,
                )
            data_evidence = tuple(
                child
                for child in recovery_dir.iterdir()
                if child.name != "manifest.json"
            )
            if data_evidence and not replacement_path.exists():
                raise SceneTargetRevisionChangedError(
                    "Scene recovery has baseline data but no publication inode proof:"
                    f" evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                )
            if replacement_path.exists():
                try:
                    owns_target = os.path.samefile(replacement_path, target)
                except OSError:
                    owns_target = False
                if (
                    not owns_target
                    or _scene_payload_revision(replacement_path.read_bytes())
                    != normalized_expected
                ):
                    raise SceneTargetRevisionChangedError(
                        "Scene recovery replacement no longer owns the target:"
                        f" evidence={recovery_dir}",
                        recovery_path=recovery_dir,
                    )
            try:
                if manifest_path.exists():
                    _write_scene_recovery_manifest(
                        recovery_dir,
                        target=target,
                        expected_revision=normalized_expected,
                        observed_revision=normalized_expected,
                        replacement_revision=normalized_expected,
                        phase="committed_cleanup_pending",
                    )
                _discard_scene_recovery_directory(recovery_dir)
            except (OSError, ValueError) as exc:
                raise SceneTargetRevisionChangedError(
                    "committed Scene recovery cleanup failed:"
                    f" evidence={recovery_dir}",
                    recovery_path=recovery_dir,
                ) from exc


def scene_recovery_artifacts(path: str | Path) -> tuple[Path, ...]:
    """Return unresolved conditional-mutation evidence for one Scene ID."""

    target = validate_scene_library_write_path(path)
    prefix = _scene_recovery_directory_prefix(target)
    try:
        candidates = tuple(
            sorted(
                candidate
                for candidate in target.parent.iterdir()
                if candidate.name.startswith(prefix)
            )
        )
    except FileNotFoundError:
        return ()
    return candidates


def _assert_no_scene_recovery_artifacts(target: Path) -> None:
    artifacts = scene_recovery_artifacts(target)
    if artifacts:
        raise SceneTargetRevisionChangedError(
            "scene_recovery_required:"
            f" path={target}; evidence={artifacts[0]}",
            recovery_path=artifacts[0],
        )


def _scene_recovery_directory_prefix(target: Path) -> str:
    identity = target.stem.casefold().encode("utf-8")
    digest = hashlib.sha256(identity).hexdigest()[:16]
    return f"{_SCENE_RECOVERY_PREFIX}{digest}-"


def _create_scene_recovery_directory(
    target: Path,
    *,
    expected_revision: str,
    phase: str,
) -> Path:
    recovery_dir = Path(
        tempfile.mkdtemp(
            prefix=_scene_recovery_directory_prefix(target),
            dir=str(target.parent),
        )
    )
    try:
        _assert_non_symbolic_library_path(recovery_dir, SCENE_LIBRARY_DIR)
        _write_scene_recovery_manifest(
            recovery_dir,
            target=target,
            expected_revision=expected_revision,
            phase=phase,
        )
    except BaseException:
        _discard_scene_recovery_directory(recovery_dir, ignore_errors=True)
        raise
    return recovery_dir


def _write_scene_recovery_manifest(
    recovery_dir: Path,
    *,
    target: Path,
    expected_revision: str,
    phase: str,
    observed_revision: str = "",
    replacement_revision: str = "",
) -> None:
    payload = json.dumps(
        {
            "version": 1,
            "target": str(target),
            "target_name": target.name,
            "scene_identity": target.stem,
            "expected_revision": str(expected_revision or ""),
            "observed_revision": str(observed_revision or ""),
            "replacement_revision": str(replacement_revision or ""),
            "phase": str(phase or ""),
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    atomic_write_bytes(recovery_dir / "manifest.json", payload)


def _read_scene_recovery_manifest(recovery_dir: Path) -> dict[str, object]:
    try:
        payload = json.loads(
            (recovery_dir / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SceneTargetRevisionChangedError(
            f"Scene recovery manifest is unreadable: {recovery_dir}",
            recovery_path=recovery_dir,
        ) from exc
    if not isinstance(payload, dict) or int(payload.get("version", 0) or 0) != 1:
        raise SceneTargetRevisionChangedError(
            f"Scene recovery manifest is invalid: {recovery_dir}",
            recovery_path=recovery_dir,
        )
    return payload


def _restore_quarantined_scene_without_replacement(
    quarantined_path: Path,
    target: Path,
    *,
    recovery_dir: Path,
    expected_revision: str,
    consume_quarantine: bool = True,
) -> None:
    """Restore captured bytes without replacing a newer target.

    A failed no-replace restore retains the quarantine as explicit evidence.
    Once the exact captured inode/revision is verified at the authoritative
    pathname, its redundant quarantine link can be removed safely; a later
    writer may replace the pathname but is never overwritten by this function.
    """

    try:
        os.link(quarantined_path, target, follow_symlinks=False)
    except FileExistsError as exc:
        raise SceneTargetRevisionChangedError(
            "scene_recovery_target_already_exists:"
            f" path={target}; evidence={recovery_dir}",
            recovery_path=recovery_dir,
        ) from exc
    try:
        restored = os.path.samefile(quarantined_path, target)
        restored_revision = scene_file_revision(target)
    except OSError:
        restored = False
        restored_revision = "unreadable"
    if not restored or restored_revision != expected_revision:
        raise SceneTargetRevisionChangedError(
            "scene_recovery_verification_failed:"
            f" path={target}; evidence={recovery_dir}",
            recovery_path=recovery_dir,
        )
    if consume_quarantine:
        quarantined_path.unlink()


def _discard_scene_recovery_directory(
    recovery_dir: Path,
    *,
    ignore_errors: bool = False,
) -> None:
    try:
        if not recovery_dir.exists():
            return
        if not recovery_dir.name.startswith(_SCENE_RECOVERY_PREFIX):
            raise OSError(f"invalid Scene recovery directory: {recovery_dir}")
        _assert_non_symbolic_library_path(recovery_dir, SCENE_LIBRARY_DIR)
        children = sorted(
            recovery_dir.iterdir(),
            key=lambda child: (child.name == "manifest.json", child.name),
        )
        for child in children:
            if child.is_dir() and not child.is_symlink():
                raise OSError(f"unexpected nested Scene recovery directory: {child}")
            child.unlink()
        recovery_dir.rmdir()
    except (OSError, ValueError):
        if not ignore_errors:
            raise


def _save_new_scene_without_replacement(scene, entry: ConfigLibraryEntry):
    """Publish one prepared JSON scene without ever replacing a target.

    Case variants of one identity are serialized inside this process.  The
    hard-link publish also gives exact-path no-replace semantics across
    processes.  A final directory review detects cross-process case-variant
    races on case-sensitive filesystems; a non-cooperating actor can still
    create a new variant after that review, which no portable filesystem API
    can prevent without a shared inter-process lock.
    """

    target = validate_scene_library_write_path(entry.path)
    with _scene_create_lock(target, scene_id=entry.config_id):
        return _save_new_scene_under_identity_lock(scene, entry, target)


def _save_new_scene_under_identity_lock(
    scene,
    entry: ConfigLibraryEntry,
    target: Path,
):
    """Run the create-only protocol while one casefolded identity is locked."""

    _assert_no_scene_recovery_artifacts(target)
    _assert_scene_user_identity_absent(
        target,
        scene_id=entry.config_id,
        mode_id=entry.mode_id,
    )

    recovery_dir = _create_scene_recovery_directory(
        target,
        expected_revision="missing",
        phase="prepare_create",
    )
    replacement_path = recovery_dir / "replacement.json"
    captured_path = recovery_dir / "captured.json"
    preserve_recovery = False
    published = False
    try:
        save_scene(scene, replacement_path)
        published_revision = _scene_payload_revision(replacement_path.read_bytes())
        # Validate the complete bytes before making them visible in the
        # authoritative directory.  ``os.link`` is the cross-platform local
        # filesystem primitive that atomically fails when ``target`` exists.
        _load_scene_entry(
            ConfigLibraryEntry(
                "scene",
                entry.config_id,
                entry.config_id,
                replacement_path,
                mode_id=entry.mode_id,
                source_type="user",
            )
        )
        _write_scene_recovery_manifest(
            recovery_dir,
            target=target,
            expected_revision="missing",
            replacement_revision=published_revision,
            phase="create_replacement_validated",
        )
        _assert_scene_user_identity_absent(
            target,
            scene_id=entry.config_id,
            mode_id=entry.mode_id,
        )
        try:
            os.link(replacement_path, target, follow_symlinks=False)
        except FileExistsError as exc:
            raise SceneTargetAlreadyExistsError(
                "scene_target_already_exists:"
                f" mode={entry.mode_id}; id={entry.config_id}; path={target}"
            ) from exc
        published = True
        try:
            _assert_scene_publication_is_unique(
                target,
                temporary_path=replacement_path,
                scene_id=entry.config_id,
                mode_id=entry.mode_id,
            )
            reloaded = _load_scene_entry(entry)
            try:
                still_owns_target = os.path.samefile(replacement_path, target)
            except OSError:
                still_owns_target = False
            if (
                not still_owns_target
                or scene_file_revision(target) != published_revision
            ):
                raise SceneTargetRevisionChangedError(
                    f"scene_target_changed_during_create_verification: path={target}"
                )
        except BaseException as publication_error:
            try:
                _withdraw_created_scene_publication(
                    target,
                    replacement_path=replacement_path,
                    captured_path=captured_path,
                    published_revision=published_revision,
                    recovery_dir=recovery_dir,
                )
                published = False
            except BaseException as cleanup_error:
                preserve_recovery = bool(
                    getattr(cleanup_error, "recovery_required", False)
                )
                if isinstance(publication_error, SceneTargetAlreadyExistsError):
                    publication_error.recovery_path = getattr(
                        cleanup_error,
                        "recovery_path",
                        None,
                    )
                    raise publication_error from cleanup_error
                raise cleanup_error from publication_error
            raise
        try:
            _discard_scene_recovery_directory(recovery_dir)
        except (OSError, ValueError):
            preserve_recovery = True
        published = False
        return reloaded, published_revision
    finally:
        if published:
            # A post-link exception that escaped before the withdrawal path
            # ran must retain the hard-link proof for explicit recovery.
            preserve_recovery = True
        if not preserve_recovery:
            _discard_scene_recovery_directory(recovery_dir, ignore_errors=True)


def _withdraw_created_scene_publication(
    target: Path,
    *,
    replacement_path: Path,
    captured_path: Path,
    published_revision: str,
    recovery_dir: Path,
) -> None:
    """Withdraw a failed create without unlinking an external replacement."""

    try:
        os.rename(target, captured_path)
    except FileNotFoundError:
        return
    try:
        captured_revision = _scene_payload_revision(captured_path.read_bytes())
        owns_capture = (
            os.path.samefile(replacement_path, captured_path)
            and captured_revision == published_revision
        )
    except OSError:
        captured_revision = "unreadable"
        owns_capture = False
    if owns_capture:
        captured_path.unlink()
        return

    _write_scene_recovery_manifest(
        recovery_dir,
        target=target,
        expected_revision="missing",
        observed_revision=captured_revision,
        replacement_revision=published_revision,
        phase="create_withdrawal_captured_external",
    )
    _restore_quarantined_scene_without_replacement(
        captured_path,
        target,
        recovery_dir=recovery_dir,
        expected_revision=captured_revision,
    )
    _discard_scene_recovery_directory(recovery_dir)
    raise SceneTargetRevisionChangedError(
        "scene_create_cleanup_captured_external_version:"
        f" path={target}"
    )


def _assert_scene_user_identity_absent(
    target: Path,
    *,
    scene_id: str,
    mode_id: str,
) -> None:
    """Fail when any JSON user scene owns the requested casefolded ID."""

    candidates = _scene_user_identity_candidates(target, scene_id=scene_id)
    if candidates:
        raise SceneTargetAlreadyExistsError(
            "scene_target_already_exists:"
            f" mode={mode_id}; id={scene_id}; existing={candidates[0]}"
        )


def _assert_scene_publication_is_unique(
    target: Path,
    *,
    temporary_path: Path,
    scene_id: str,
    mode_id: str,
) -> None:
    """Keep a create-only publish only when it is the sole casefolded owner."""

    candidates = _scene_user_identity_candidates(target, scene_id=scene_id)
    published_target = False
    if (
        len(candidates) == 1
        and _lexical_path_key(candidates[0]) == _lexical_path_key(target)
    ):
        try:
            published_target = os.path.samefile(temporary_path, candidates[0])
        except OSError:
            published_target = False
    if published_target:
        return

    details = ",".join(str(candidate) for candidate in candidates) or "<missing>"
    raise SceneTargetAlreadyExistsError(
        "scene_target_already_exists:"
        f" mode={mode_id}; id={scene_id}; candidates={details}"
    )


def _scene_user_identity_candidates(
    target: Path,
    *,
    scene_id: str,
) -> list[Path]:
    """Return all authoritative JSON case variants in the target directory."""

    requested_key = str(scene_id or "").casefold()
    return [
        candidate
        for candidate in _iter_recognized_config_files(
            target.parent,
            SCENE_LIBRARY_DIR,
        )
        if candidate.stem.casefold() == requested_key
    ]


def _scene_create_lock(target: Path, *, scene_id: str) -> threading.RLock:
    """Return the process-local lock for one directory-scoped Scene identity."""

    key = f"{_lexical_path_key(target.parent)}\0{str(scene_id or '').casefold()}"
    with _SCENE_CREATE_LOCKS_GUARD:
        lock = _SCENE_CREATE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _SCENE_CREATE_LOCKS[key] = lock
        return lock


def _seed_template_library() -> None:
    for mode_id, template_id, canonical_path in list_builtin_template_resources():
        assert_non_symbolic_resource_path(
            canonical_path,
            canonical_template_root(),
            resource_label="template",
        )
        target_dir = _prepare_owned_library_directory(
            _mode_source_dir(TEMPLATE_LIBRARY_DIR, mode_id, "builtin"),
            TEMPLATE_LIBRARY_DIR,
            mode_id=mode_id,
            source_type="builtin",
        )
        template_id = _require_safe_config_id(template_id)
        target = target_dir / f"{template_id}.json"
        _assert_non_symbolic_library_path(target, TEMPLATE_LIBRARY_DIR)
        cache_key = _builtin_pair_cache_key(canonical_path, target)
        if target.exists():
            digest = _builtin_pair_digest(canonical_path, target)
            if _IN_PLACE_TEMPLATE_VALIDATION_DIGESTS.get(cache_key) == digest:
                continue
        canonical_template = create_builtin_template(template_id, mode_id=mode_id)
        if _is_same_lexical_path(canonical_path, target):
            # The canonical resource is already the runtime target.  The
            # strict factory load above is sufficient; comparing the same
            # bytes after a second materialization cannot add evidence.
            pass
        elif not target.exists():
            save_template(canonical_template, target)
        else:
            try:
                target_matches = asdict(load_template(target)) == asdict(canonical_template)
            except ConfigLoadError:
                # Runtime builtin copies are application-owned cache.  A schema
                # expansion must replace an older canonical copy instead of
                # failing before the new builtin can be seeded.
                target_matches = False
            if not target_matches:
                save_template(canonical_template, target)
        _IN_PLACE_TEMPLATE_VALIDATION_DIGESTS[cache_key] = _builtin_pair_digest(
            canonical_path,
            target,
        )


def _seed_scene_library() -> None:
    for mode_id, scene_id, canonical_path in list_builtin_scene_resources():
        assert_non_symbolic_resource_path(
            canonical_path,
            canonical_scene_root(),
            resource_label="plan",
        )
        target_dir = _prepare_owned_library_directory(
            _mode_source_dir(SCENE_LIBRARY_DIR, mode_id, "builtin"),
            SCENE_LIBRARY_DIR,
            mode_id=mode_id,
            source_type="builtin",
        )
        scene_id = _require_config_id_for_root(
            SCENE_LIBRARY_DIR,
            scene_id,
            label="scene id",
        )
        target = target_dir / f"{scene_id}.json"
        _assert_non_symbolic_library_path(target, SCENE_LIBRARY_DIR)
        cache_key = _builtin_pair_cache_key(canonical_path, target)
        if target.exists():
            digest = _builtin_pair_digest(canonical_path, target)
            if _IN_PLACE_SCENE_VALIDATION_DIGESTS.get(cache_key) == digest:
                continue
        canonical_scene = create_builtin_scene(scene_id, mode_id=mode_id)
        if _is_same_lexical_path(canonical_path, target):
            pass
        elif not target.exists() or asdict(load_scene(target)) != asdict(
            canonical_scene
        ):
            save_scene(canonical_scene, target)
        _IN_PLACE_SCENE_VALIDATION_DIGESTS[cache_key] = _builtin_pair_digest(
            canonical_path,
            target,
        )


def _lexical_path_key(path: Path) -> str:
    """Return a stable absolute key without resolving symbolic components."""

    return os.path.normcase(os.path.abspath(path))


def _is_same_lexical_path(left: Path, right: Path) -> bool:
    return _lexical_path_key(left) == _lexical_path_key(right)


def _builtin_pair_cache_key(canonical_path: Path, target: Path) -> str:
    return f"{_lexical_path_key(canonical_path)}->{_lexical_path_key(target)}"


def _builtin_pair_digest(canonical_path: Path, target: Path) -> str:
    canonical_digest = _file_digest(canonical_path)
    target_digest = (
        canonical_digest
        if _is_same_lexical_path(canonical_path, target)
        else _file_digest(target)
    )
    return f"{canonical_digest}:{target_digest}"


def _file_digest(path: Path) -> str:
    """Hash current bytes so external edits invalidate in-process validation."""

    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ConfigLoadError(f"Built-in config is unreadable: {path}") from exc


def _load_scene_entry(entry: ConfigLibraryEntry):
    scene = load_scene(entry.path)
    _validate_scene_storage_identity(scene, entry)
    return _normalize_scene_templates(scene, mode_id=entry.mode_id)


def _validate_scene_storage_identity(scene, entry: ConfigLibraryEntry) -> None:
    """Reject path/payload identity drift instead of repairing it in memory."""

    stored_scene_id = str(getattr(scene, "scene_id", "") or "").strip()
    expected_scene_id = str(entry.config_id or "").strip()
    if stored_scene_id != expected_scene_id:
        raise ConfigReferenceResolutionError(
            "plan_storage_identity_mismatch:"
            f" path_scene_id={expected_scene_id or '<empty>'};"
            f" payload_scene_id={stored_scene_id or '<empty>'}"
        )

    expected_mode_id = str(entry.mode_id or "").strip()
    if not expected_mode_id:
        return
    stored_mode_id = str(getattr(scene, "mode_id", "") or "").strip()
    if stored_mode_id != expected_mode_id:
        raise ConfigReferenceResolutionError(
            "plan_storage_mode_mismatch:"
            f" path_mode_id={expected_mode_id};"
            f" payload_mode_id={stored_mode_id or '<empty>'}"
        )


def _set_scene_identity(scene, scene_id: str) -> None:
    normalized_id = str(scene_id or "").strip()
    if not normalized_id:
        return
    current_id = str(getattr(scene, "scene_id", "") or "").strip()
    if current_id == normalized_id:
        return
    scene.scene_id = normalized_id


def _normalize_scene_templates(scene, *, mode_id: str | None = None):
    """Validate stable plan identities without materializing runtime references."""

    normalized_scene = deepcopy(scene)
    mode = _normalize_mode_id(
        mode_id
        or str(getattr(normalized_scene, "mode_id", "") or "").strip()
        or _mode_id_for_scene_id(getattr(normalized_scene, "scene_id", ""))
    )
    requested_template_id = str(
        getattr(normalized_scene, "template_id", "") or ""
    ).strip()
    if not requested_template_id:
        raise ConfigReferenceResolutionError(
            f"plan_template_ref_missing: mode={mode}; field=template_id"
        )
    candidate_ids = [
        str(template_id or "").strip()
        for template_id in getattr(
            normalized_scene,
            "compatible_template_ids",
            [],
        )
        or []
    ]
    if requested_template_id not in candidate_ids:
        raise ConfigReferenceResolutionError(
            "plan_template_ref_incompatible:"
            f" mode={mode}; template_id={requested_template_id}"
        )
    compatible_ids = _available_scene_template_ids(
        candidate_ids,
        scene_id=str(getattr(normalized_scene, "scene_id", "") or "").strip(),
        category=str(getattr(normalized_scene, "category", "") or "").strip(),
        mode_id=mode,
    )
    normalized_scene.compatible_template_ids = compatible_ids
    # Older user-copied engineering scenes were seeded with the legacy
    # ``default`` delivery target while their primary template is
    # ``eng_document``. That combination is rejected at final DOCX delivery;
    # normalize the stale copy in memory so existing projects remain runnable
    # without rewriting user files.
    if mode == "engineering":
        primary_template_id = str(
            getattr(normalized_scene, "template_id", "") or ""
        ).strip()
        for preset in getattr(normalized_scene, "delivery_presets", ()) or ():
            target_template_id = str(
                getattr(preset, "target_template_id", "") or ""
            ).strip()
            if target_template_id == "default" and primary_template_id:
                preset.target_template_id = primary_template_id
    _set_scene_mode(normalized_scene, mode)
    _validate_scene_master_id(normalized_scene, mode_id=mode)
    return normalized_scene


def _validate_scene_master_id(scene, *, mode_id: str) -> None:
    """Resolve a plan master only to validate its stable ID and current bytes."""

    master_id = str(getattr(scene, "master_id", "") or "").strip()
    if not master_id:
        if mode_id in {"exam", "official"}:
            raise ConfigReferenceResolutionError(
                f"plan_master_ref_missing: mode={mode_id}; field=master_id"
            )
        return

    from src.config.master_library import get_master

    master = get_master(
        master_id,
        mode_id,
        exam_config=getattr(scene, "exam_paper", None),
    )
    if master is None:
        raise ConfigReferenceResolutionError(
            "plan_master_ref_unresolved:"
            f" mode={mode_id}; master_id={master_id}"
        )
    master_path = Path(getattr(master, "docx_path", ""))
    if not master_path.is_file():
        raise ConfigReferenceResolutionError(
            "plan_master_ref_unavailable:"
            f" mode={mode_id}; master_id={master_id}"
        )


def _set_scene_mode(scene, mode_id: str) -> None:
    normalized = _normalize_mode_id(mode_id)
    if not normalized:
        return
    scene.mode_id = normalized


def _available_scene_template_ids(
    template_ids,
    *,
    scene_id: str = "",
    category: str = "",
    mode_id: str = "",
) -> list[str]:
    mode = _normalize_mode_id(mode_id or _mode_id_for_scene_id(scene_id))
    del category
    normalized_ids: list[str] = []
    for template_id in template_ids:
        normalized = str(template_id or "").strip()
        if normalized and normalized not in normalized_ids:
            normalized_ids.append(normalized)
    if not normalized_ids:
        raise ConfigReferenceResolutionError(
            f"plan_template_ref_missing: mode={mode}; field=compatible_template_ids"
        )
    unresolved = [
        template_id
        for template_id in normalized_ids
        if not _template_id_is_available(template_id, mode_id=mode)
    ]
    if unresolved:
        raise ConfigReferenceResolutionError(
            "plan_template_ref_unresolved:"
            f" mode={mode}; template_ids={','.join(unresolved)}"
        )
    return normalized_ids


def _template_id_is_available(template_id: str, *, mode_id: str | None = None) -> bool:
    normalized = str(template_id or "").strip()
    if not normalized:
        return False
    path = _find_config_path(
        TEMPLATE_LIBRARY_DIR,
        normalized,
        mode_id=mode_id,
    )
    if path is None:
        return False
    try:
        source_type = _source_type_from_scoped_path(path, TEMPLATE_LIBRARY_DIR)
        if source_type == "user":
            load_compatible_user_template(path)
        else:
            load_template(path)
    except ConfigLoadError:
        return False
    return True


def _build_scene_descriptor(entry: ConfigLibraryEntry) -> SceneLibraryDescriptor | None:
    return _build_scene_descriptor_from_path(entry.path)


def _dedupe_scene_descriptors(
    descriptors: list[SceneLibraryDescriptor],
) -> list[SceneLibraryDescriptor]:
    selected: dict[tuple[str, str], SceneLibraryDescriptor] = {}
    for descriptor in descriptors:
        config_id = str(descriptor.config_id or "").strip()
        if not config_id:
            continue
        key = (str(descriptor.mode_id or "").strip(), config_id)
        previous = selected.get(key)
        if previous is None or _scene_descriptor_preference(
            descriptor
        ) < _scene_descriptor_preference(previous):
            selected[key] = descriptor
    return list(selected.values())


def _scene_descriptor_preference(descriptor: SceneLibraryDescriptor) -> tuple[int, int]:
    source_rank = {
        "user": 0,
        "builtin": 1,
        "": 2,
    }.get(str(descriptor.source_type or "").strip(), 2)
    return (source_rank, 0 if descriptor.is_available else 1)


def _build_scene_descriptor_from_path(path: Path) -> SceneLibraryDescriptor | None:
    config_id = path.stem
    path_mode_id = _mode_id_from_scoped_path(path, SCENE_LIBRARY_DIR)
    path_source_type = _source_type_from_scoped_path(path, SCENE_LIBRARY_DIR)
    mode_id = path_mode_id or _mode_id_for_scene_id(config_id)
    try:
        scene = load_scene(path)
    except _EXTERNAL_CONFIG_LOAD_ERRORS as exc:
        return _unavailable_scene_descriptor(
            path=path,
            config_id=config_id,
            mode_id=mode_id,
            source_type=path_source_type,
            error=exc,
        )

    # External bytes and explicit reference-contract failures are visible as an
    # unavailable descriptor.  Programming/registry failures remain outside
    # these catches and must stop the listing.
    try:
        _validate_scene_storage_identity(
            scene,
            ConfigLibraryEntry(
                "scene",
                config_id,
                config_id,
                path,
                mode_id=path_mode_id,
                source_type=path_source_type,
            ),
        )
        scene = _normalize_scene_templates(scene, mode_id=mode_id)
    except ConfigReferenceResolutionError as exc:
        return _unavailable_scene_descriptor(
            path=path,
            config_id=config_id,
            mode_id=mode_id,
            source_type=path_source_type,
            error=exc,
            scene=scene,
        )

    scene_id = str(getattr(scene, "scene_id", "") or config_id).strip() or config_id
    mode_id = _normalize_mode_id(
        path_mode_id
        or str(getattr(scene, "mode_id", "") or "").strip()
        or _mode_id_for_scene_id(scene_id)
    )
    name = (
        str(getattr(scene, "name", "") or config_id).strip()
        or config_id
    )
    description = str(getattr(scene, "description", "") or "").strip()
    template_id = str(getattr(scene, "template_id", "") or "").strip()

    compatible_template_ids = tuple(
        item
        for item in (
            str(template_id or "").strip()
            for template_id in getattr(scene, "compatible_template_ids", [])
        )
        if item
    )
    return SceneLibraryDescriptor(
        config_id=config_id,
        scene_id=scene_id,
        name=name,
        description=description,
        template_id=template_id,
        compatible_template_ids=compatible_template_ids,
        path=path,
        mode_id=mode_id,
        source_type=path_source_type,
        display_order=int(getattr(scene, "display_order", 0) or 0),
    )


def _unavailable_scene_descriptor(
    *,
    path: Path,
    config_id: str,
    mode_id: str,
    source_type: str,
    error: BaseException,
    scene=None,
) -> SceneLibraryDescriptor:
    name = str(
        getattr(scene, "name", "")
        or config_id
    ).strip() or config_id
    description = str(getattr(scene, "description", "") or "").strip()
    template_id = str(getattr(scene, "template_id", "") or "").strip()
    compatible_template_ids = tuple(
        template_id
        for template_id in (
            str(item or "").strip()
            for item in (getattr(scene, "compatible_template_ids", ()) or ())
        )
        if template_id
    )
    return SceneLibraryDescriptor(
        config_id=config_id,
        scene_id=config_id,
        name=name,
        description=description,
        template_id=template_id,
        compatible_template_ids=compatible_template_ids,
        path=path,
        load_error=f"{type(error).__name__}: {error}",
        mode_id=mode_id,
        source_type=source_type,
        display_order=int(getattr(scene, "display_order", 0) or 0),
    )


def _assert_unique_config_identities(
    paths: list[Path],
    root: Path,
    *,
    kind: str,
) -> None:
    """Reject duplicate stable IDs instead of applying source precedence."""

    grouped: dict[tuple[str, str], list[Path]] = {}
    for path in paths:
        config_id = _require_config_id_for_root(root, path.stem)
        key = (_mode_id_from_scoped_path(path, root), config_id.casefold())
        grouped.setdefault(key, []).append(path)
    for (mode_id, _identity_key), candidates in grouped.items():
        if len(candidates) < 2:
            continue
        config_id = candidates[0].stem
        sources = ",".join(
            sorted(
                f"{_source_type_from_scoped_path(path, root)}:{path.suffix.lower()}"
                for path in candidates
            )
        )
        raise ConfigReferenceResolutionError(
            f"{kind}_id_ambiguous:"
            f" mode={mode_id}; id={config_id}; candidates={sources}"
        )


def _assert_user_id_does_not_shadow_builtin(
    root: Path,
    config_id: str,
    *,
    mode_id: str,
    kind: str,
) -> None:
    builtin_dir = _mode_source_dir(root, mode_id, "builtin")
    _assert_non_symbolic_library_path(builtin_dir, root)
    requested_key = str(config_id or "").casefold()
    collisions: list[Path] = []
    if builtin_dir.exists():
        collisions.extend(
            path
            for path in _iter_recognized_config_files(builtin_dir, root)
            if path.stem.casefold() == requested_key
        )
    if not collisions:
        return
    for path in collisions:
        _assert_non_symbolic_library_path(path, root)
    raise ConfigReferenceResolutionError(
        f"{kind}_id_shadowed:"
        f" mode={mode_id}; id={config_id}; sources=user,builtin"
    )


def _list_entries(
    kind: str,
    directory: Path,
    loader,
    *,
    mode_id: str | None = None,
    source_type: str | None = None,
) -> list[ConfigLibraryEntry]:
    entries: list[ConfigLibraryEntry] = []
    paths = list(_iter_config_files(
        directory,
        mode_id=mode_id,
        source_type=source_type,
    ))
    _assert_unique_config_identities(paths, directory, kind=kind)
    for path in paths:
        config_id = path.stem
        load_error = ""
        resolved_source_type = _source_type_from_scoped_path(path, directory)
        try:
            cfg = _load_discovered_config(
                kind,
                path,
                resolved_source_type,
                loader,
            )
        except _EXTERNAL_CONFIG_LOAD_ERRORS as exc:
            cfg = None
            load_error = f"{type(exc).__name__}: {exc}"
        name = str(getattr(cfg, "name", "") or config_id).strip() or config_id
        entries.append(
            ConfigLibraryEntry(
                kind,
                config_id,
                name,
                path,
                mode_id=_mode_id_from_scoped_path(path, directory),
                source_type=resolved_source_type,
                load_error=load_error,
            )
        )
    entries.sort(
        key=lambda item: (
            item.mode_id,
            0 if item.source_type == "user" else 1,
            item.name,
            item.config_id,
        )
    )
    return entries


def _get_entry(
    kind: str,
    directory: Path,
    config_id: str,
    loader,
    *,
    mode_id: str | None = None,
) -> ConfigLibraryEntry | None:
    target_id = str(config_id or "").strip()
    if not target_id:
        return None
    path = _find_config_path(
        directory,
        target_id,
        mode_id=mode_id,
    )
    if path is None:
        return None
    resolved_id = path.stem
    load_error = ""
    resolved_source_type = _source_type_from_scoped_path(path, directory)
    try:
        cfg = _load_discovered_config(
            kind,
            path,
            resolved_source_type,
            loader,
        )
    except _EXTERNAL_CONFIG_LOAD_ERRORS as exc:
        cfg = None
        load_error = f"{type(exc).__name__}: {exc}"
    name = str(getattr(cfg, "name", "") or resolved_id).strip() or resolved_id
    return ConfigLibraryEntry(
        kind,
        resolved_id,
        name,
        path,
        mode_id=_mode_id_from_scoped_path(path, directory),
        source_type=resolved_source_type,
        load_error=load_error,
    )


def _load_discovered_config(kind: str, path: Path, source_type: str, loader):
    if kind == "template" and source_type == "user":
        return load_compatible_user_template(path)
    return loader(path)


def _find_config_path(
    directory: Path,
    config_id: str,
    *,
    mode_id: str | None = None,
) -> Path | None:
    target_id = str(config_id or "").strip()
    if not target_id:
        return None
    target_id = _require_config_id_for_root(directory, target_id)
    mode = str(mode_id or "").strip()
    candidates = [
        path
        for path in _iter_config_files(
            directory,
            mode_id=mode or None,
        )
        if path.stem.casefold() == target_id.casefold()
    ]

    if len(candidates) > 1:
        details = ",".join(
            sorted(
                f"{_mode_id_from_scoped_path(path, directory)}:"
                f"{_source_type_from_scoped_path(path, directory)}:"
                f"{path.suffix.lower()}"
                for path in candidates
            )
        )
        raise ConfigReferenceResolutionError(
            "config_id_ambiguous:"
            f" id={target_id}; candidates={details}"
        )
    return candidates[0] if candidates else None


def _iter_config_files(
    directory: Path,
    *,
    mode_id: str | None = None,
    source_type: str | None = None,
):
    files: list[Path] = []
    mode = str(mode_id or "").strip()
    if mode:
        source = str(source_type or "").strip()
        search_dirs = (
            [_mode_source_dir(directory, mode, source)]
            if source in _SOURCE_BUCKETS
            else _mode_source_dirs(directory, mode)
        )
        for folder in search_dirs:
            _assert_non_symbolic_library_path(folder, directory)
            if folder.exists():
                files.extend(_iter_recognized_config_files(folder, directory))
    elif directory.exists():
        # Only runtime config slots are discoverable.  Authoring workspaces,
        # provenance bundles, inboxes, and import reports may also contain JSON,
        # but they are not authoritative templates/plans.
        _assert_non_symbolic_library_path(directory, directory)
        for mode_dir in sorted(directory.iterdir()):
            if _path_is_link_or_reparse(mode_dir):
                raise ValueError(f"symbolic library path is not allowed: {mode_dir}")
            if not mode_dir.is_dir():
                continue
            for bucket in _SOURCE_BUCKETS:
                folder = mode_dir / bucket
                if not folder.exists():
                    continue
                _assert_non_symbolic_library_path(folder, directory)
                files.extend(_iter_recognized_config_files(folder, directory))

    seen: set[Path] = set()
    unique_files: list[Path] = []
    for path in files:
        resolved = path.resolve() if path.exists() else path
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_files.append(path)
    return unique_files


def _iter_recognized_config_files(folder: Path, root: Path):
    """Yield authoritative config suffixes without filesystem case assumptions."""

    suffixes = set(_config_suffixes_for_root(root))
    for path in sorted(folder.iterdir()):
        if path.suffix.casefold() not in suffixes:
            continue
        _assert_non_symbolic_library_path(path, root)
        yield path


def _mode_source_dirs(directory: Path, mode_id: str) -> list[Path]:
    mode = _normalize_mode_id(mode_id)
    return [_mode_source_dir(directory, mode, bucket) for bucket in _SOURCE_BUCKETS]


def _mode_source_dir(directory: Path, mode_id: str, source_type: str) -> Path:
    mode = _require_safe_config_id(
        _normalize_mode_id(mode_id),
        label="work mode id",
    )
    source = str(source_type or "").strip()
    if source not in _SOURCE_BUCKETS:
        raise ValueError(f"unsupported config source type: {source_type}")
    return directory / mode / source


def _watch_dirs(directory: Path, *, mode_id: str | None = None) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    _assert_non_symbolic_library_path(directory, directory)
    mode = str(mode_id or "").strip()
    dirs = [directory]
    if mode:
        for folder in _mode_source_dirs(directory, mode):
            _assert_non_symbolic_library_path(folder, directory)
            dirs.append(folder)
    else:
        for child in directory.iterdir():
            if _path_is_link_or_reparse(child):
                raise ValueError(f"symbolic library path is not allowed: {child}")
            if not child.is_dir():
                continue
            dirs.append(child)
            for bucket in _SOURCE_BUCKETS:
                bucket_dir = child / bucket
                if bucket_dir.is_dir():
                    _assert_non_symbolic_library_path(bucket_dir, directory)
                    dirs.append(bucket_dir)
    return dirs


def _is_scene_library_root(root: Path) -> bool:
    return os.path.normcase(os.path.abspath(root)) == os.path.normcase(
        os.path.abspath(SCENE_LIBRARY_DIR)
    )


def _config_suffixes_for_root(root: Path) -> tuple[str, ...]:
    """Return the authoritative formats for one runtime library.

    Plans have a single persisted runtime representation.  Template YAML
    support remains unchanged until its separate import/authoring contract is
    migrated.
    """

    if _is_scene_library_root(root):
        return _SCENE_CONFIG_SUFFIXES
    return _TEMPLATE_CONFIG_SUFFIXES


def _mode_id_from_scoped_path(path: Path, root: Path) -> str:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return ""
    if (
        len(rel.parts) == 3
        and rel.parts[1] in _SOURCE_BUCKETS
        and path.suffix.lower() in _config_suffixes_for_root(root)
    ):
        return rel.parts[0]
    return ""


def _source_type_from_scoped_path(path: Path, root: Path) -> str:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return ""
    if (
        len(rel.parts) == 3
        and rel.parts[1] in _SOURCE_BUCKETS
        and path.suffix.lower() in _config_suffixes_for_root(root)
    ):
        return rel.parts[1]
    return ""


def _normalize_mode_id(mode_id: str | None) -> str:
    requested = str(mode_id or "").strip()
    if requested:
        from src.config.work_mode import get_work_mode

        mode = get_work_mode(requested)
        if mode is not None:
            return mode.mode_id
        raise ValueError(f"unknown work mode: {requested}")
    from src.config.work_mode import default_work_mode

    return default_work_mode().mode_id


def _mode_id_for_scene_id(scene_id: str) -> str:
    from src.config.work_mode import work_mode_for_scene_id

    return work_mode_for_scene_id(str(scene_id or "").strip()).mode_id


def _default_scene_id_for_mode(mode_id: str | None = None) -> str:
    from src.config.work_mode import default_work_mode, get_work_mode

    requested = str(mode_id or "").strip()
    mode = get_work_mode(requested) if requested else default_work_mode()
    if mode is None:
        raise ValueError(f"unknown work mode: {requested}")
    return str(mode.default_scene_id or DEFAULT_SCENE_ID).strip()


def _default_template_id_for_mode(mode_id: str | None = None) -> str:
    from src.config.work_mode import default_work_mode, get_work_mode

    requested = str(mode_id or "").strip()
    mode = get_work_mode(requested) if requested else default_work_mode()
    if mode is None:
        raise ValueError(f"unknown work mode: {requested}")
    return str(mode.default_template_id or DEFAULT_TEMPLATE_ID).strip()


def _is_under_directory(path: str | Path, directory: Path) -> bool:
    candidate = Path(path)
    try:
        candidate_resolved = candidate.resolve()
        directory_resolved = directory.resolve()
    except OSError:
        return False
    return (
        directory_resolved == candidate_resolved
        or directory_resolved in candidate_resolved.parents
    )


def _prepare_owned_library_directory(
    directory: Path,
    root: Path,
    *,
    mode_id: str,
    source_type: str,
) -> Path:
    expected = _mode_source_dir(root, mode_id, source_type)
    if _lexical_path_key(directory) != _lexical_path_key(expected):
        raise ValueError(f"config library directory ownership mismatch: {directory}")
    _assert_non_symbolic_library_path(directory, root)
    directory.mkdir(parents=True, exist_ok=True)
    _assert_non_symbolic_library_path(directory, root)
    return directory


def _assert_non_symbolic_library_path(path: Path, root: Path) -> None:
    candidate = Path(os.path.abspath(path))
    boundary = Path(os.path.abspath(root))
    try:
        relative = candidate.relative_to(boundary)
    except ValueError as exc:
        raise ValueError(f"config library path escape: {path}") from exc

    current = boundary
    components = [current]
    for part in relative.parts:
        current = current / part
        components.append(current)
    for component in components:
        if _path_is_link_or_reparse(component):
            raise ValueError(f"symbolic library path is not allowed: {component}")


def _path_is_link_or_reparse(path: Path) -> bool:
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
        raise ValueError(f"config library path is unreadable: {path}") from exc


def _is_owned_user_config_path(path: Path, root: Path) -> bool:
    candidate = Path(path)
    if candidate.suffix.lower() not in _config_suffixes_for_root(root):
        return False
    try:
        candidate_absolute = Path(os.path.abspath(candidate))
        root_absolute = Path(os.path.abspath(root))
        relative = candidate_absolute.relative_to(root_absolute)
        if len(relative.parts) != 3 or relative.parts[1] != "user":
            return False
        _require_safe_config_id(relative.parts[0], label="work mode id")
        _require_config_id_for_root(root, candidate.stem)
        _assert_non_symbolic_library_path(candidate_absolute, root_absolute)
        resolved_relative = candidate_absolute.resolve(strict=True).relative_to(
            root_absolute.resolve(strict=True)
        )
    except (OSError, RuntimeError, ValueError):
        return False
    return resolved_relative == relative and candidate_absolute.is_file()


def _validate_library_write_path(path: Path, root: Path) -> Path:
    candidate = Path(os.path.abspath(path))
    boundary = Path(os.path.abspath(root))
    try:
        relative = candidate.relative_to(boundary)
    except ValueError as exc:
        raise ValueError(f"config library write path escape: {path}") from exc
    if (
        len(relative.parts) != 3
        or relative.parts[1] not in _SOURCE_BUCKETS
        or candidate.suffix.lower() not in _config_suffixes_for_root(root)
    ):
        raise ValueError(f"invalid config library write path: {path}")
    _require_safe_config_id(relative.parts[0], label="work mode id")
    _require_config_id_for_root(root, candidate.stem)
    _assert_non_symbolic_library_path(candidate, boundary)
    return candidate


def _is_lexically_under(path: Path, root: Path) -> bool:
    try:
        Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(root)))
    except ValueError:
        return False
    return True


def _require_safe_config_id(value: object, *, label: str = "config id") -> str:
    normalized = str(value or "").strip()
    if (
        not normalized
        or normalized != _safe_config_id(normalized)
        or any(ord(character) < 32 for character in normalized)
    ):
        raise ValueError(f"invalid {label}: {value!r}")
    reserved = {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{index}" for index in range(1, 10)),
        *(f"lpt{index}" for index in range(1, 10)),
    }
    if normalized.split(".", 1)[0].casefold() in reserved:
        raise ValueError(f"invalid {label}: {value!r}")
    return normalized


def _require_config_id_for_root(
    root: Path,
    value: object,
    *,
    label: str = "config id",
) -> str:
    """Apply the resource-kind identity contract without changing templates."""

    if _is_scene_library_root(root):
        from src.config.scene_id_rules import require_canonical_scene_id

        return require_canonical_scene_id(value, label=label)
    return _require_safe_config_id(value, label=label)


def _safe_config_id(value: str) -> str:
    forbidden = '<>:"/\\|?*'
    cleaned = "".join(
        ch if ch not in forbidden else "_" for ch in str(value or "").strip()
    )
    cleaned = cleaned.strip(" ._")
    return cleaned or "config"


__all__ = [
    "CONFIG_LIBRARY_ROOT",
    "ConfigDependencyResolutionError",
    "ConfigLibraryEntry",
    "ConfigReferenceResolutionError",
    "DEFAULT_SCENE_ID",
    "DEFAULT_TEMPLATE_ID",
    "SCENE_LIBRARY_DIR",
    "SceneFileMutationReceipt",
    "SceneLibraryDescriptor",
    "SceneTargetAlreadyExistsError",
    "SceneTargetRevisionChangedError",
    "TEMPLATE_LIBRARY_DIR",
    "default_scene_descriptor",
    "default_scene_entry",
    "default_template_entry",
    "ensure_config_library",
    "ensure_scene_library",
    "ensure_template_library",
    "finalize_committed_scene_recovery",
    "finalize_scene_file_cleanup",
    "finalize_scene_file_mutation",
    "get_scene_descriptor",
    "get_scene_entry",
    "get_template_entry",
    "is_scene_library_path",
    "is_scene_user_library_path",
    "is_template_library_path",
    "is_template_library_lexical_path",
    "is_template_user_library_path",
    "list_scene_descriptors",
    "list_scene_entries",
    "list_template_entries",
    "list_template_source_entries",
    "load_scene_from_library",
    "load_template_from_library",
    "replace_scene_file_if_revision",
    "rollback_scene_file_mutation",
    "save_scene_to_library",
    "scene_file_revision",
    "scene_recovery_artifacts",
    "save_template_to_library",
    "scene_library_watch_dirs",
    "scene_user_dir",
    "scene_user_target_path",
    "template_library_watch_dirs",
    "template_user_target_path",
    "template_dependent_scene_descriptors",
    "template_user_dir",
    "validate_scene_library_write_path",
    "validate_template_library_write_path",
]
