"""Shared owned-path and crash-recoverable multi-final publication transactions.

The public surface intentionally stays small.  ``OwnedAssemblyTransaction``
owns staging paths, serialises writers of every final, records a durable publish
journal, and either commits every final or restores the complete baseline.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import errno
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from shutil import copyfile, rmtree
import tempfile
from time import monotonic, sleep
from uuid import uuid4

from src.shared.io.file_evidence import FileEvidence
from src.shared.io.layout_shadow import is_controlled_layout_shadow


_STATE_DIRECTORY = ".lark-material-transactions"
_JOURNAL_SCHEMA = "lark.material.multi-final-publish-journal"
_JOURNAL_SCHEMA_VERSION = 1
_CLAIM_SCHEMA = "lark.material.multi-final-publish-claim"
_CLAIM_SCHEMA_VERSION = 1
_JOURNAL_STATUSES = {
    "prepared",
    "publishing",
    "commit_ready",
    "completed",
    "rolled_back",
}
_PROGRESS_STATES = {"pending", "replacing", "published"}


class TransactionViolation(RuntimeError):
    """A structured transaction contract or recovery failure."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "TRANSACTION_VIOLATION",
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": str(self),
            "details": dict(self.details),
        }


def stable_file_evidence(path: str | Path) -> FileEvidence:
    """Hash one regular non-symlink file and reject concurrent mutation."""

    raw = Path(path).expanduser()
    if raw.is_symlink():
        raise TransactionViolation(f"symbolic links are not accepted: {raw}")
    candidate = raw.resolve()
    if not candidate.is_file():
        raise TransactionViolation(f"not a regular file: {candidate}")
    before = candidate.stat()
    digest = sha256()
    with candidate.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    after = candidate.stat()
    before_identity = (
        before.st_size,
        before.st_mtime_ns,
        getattr(before, "st_ino", 0),
    )
    after_identity = (
        after.st_size,
        after.st_mtime_ns,
        getattr(after, "st_ino", 0),
    )
    if before_identity != after_identity:
        raise TransactionViolation(f"file changed while hashing: {candidate}")
    return FileEvidence(str(candidate), digest.hexdigest(), after.st_size)


def same_file_identity(left: FileEvidence, right: FileEvidence) -> bool:
    return left.sha256 == right.sha256 and left.byte_size == right.byte_size


def _canonical_path(path: Path) -> str:
    """Return one platform-stable identity for a resolved filesystem path."""

    return os.path.normcase(str(path.expanduser().resolve()))


def _identity_digest(values: list[str]) -> str:
    encoded = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return sha256(encoded).hexdigest()


def _final_set_id(final_paths: tuple[Path, ...]) -> str:
    return _identity_digest(sorted(_canonical_path(path) for path in final_paths))


def _journal_path_for(final_paths: tuple[Path, ...]) -> Path:
    ordered = sorted((_canonical_path(path), path) for path in final_paths)
    identity = _identity_digest([item[0] for item in ordered])
    return (
        ordered[0][1].parent
        / _STATE_DIRECTORY
        / "journals"
        / f"publish-{identity}.json"
    )


def _lock_path_for(final: Path) -> Path:
    return (
        final.parent
        / _STATE_DIRECTORY
        / "locks"
        / f"final-{_identity_digest([_canonical_path(final)])}.lock"
    )


def _claim_path_for(final: Path) -> Path:
    return (
        final.parent
        / _STATE_DIRECTORY
        / "claims"
        / f"final-{_identity_digest([_canonical_path(final)])}.json"
    )


def _fsync_file(path: Path) -> None:
    # Windows' ``_commit`` rejects a descriptor opened read-only even though
    # POSIX ``fsync`` accepts one.  Transaction-owned files are writable.
    with path.open("rb+") as stream:
        os.fsync(stream.fileno())


def _fsync_directory(path: Path) -> None:
    """Best-effort directory flush (not supported by every Windows filesystem)."""

    flags = os.O_RDONLY
    flags |= getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(str(path), flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            separators=(",", ": "),
        )
        + "\n"
    ).encode("utf-8")
    temporary = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_file(path)
        _fsync_directory(path.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


class _ExclusiveFileLock:
    """One-byte advisory lock whose lock file is never unlinked."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._descriptor: int | None = None
        self._backend = ""

    def acquire(self, *, deadline: float, poll_seconds: float) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(str(self.path), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if os.fstat(descriptor).st_size < 1:
                os.lseek(descriptor, 0, os.SEEK_SET)
                os.write(descriptor, b"\0")
                os.fsync(descriptor)
                _fsync_directory(self.path.parent)
            while True:
                try:
                    self._try_lock(descriptor)
                    self._descriptor = descriptor
                    return
                except OSError as exc:
                    if exc.errno not in {
                        errno.EACCES,
                        errno.EAGAIN,
                        errno.EDEADLK,
                        errno.EBUSY,
                    }:
                        raise TransactionViolation(
                            f"cannot acquire final publication lock: {self.path}: {exc}",
                            code="LOCK_ACQUIRE_FAILED",
                            details={"lock_path": str(self.path)},
                        ) from exc
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        raise TransactionViolation(
                            f"timed out waiting for final publication lock: {self.path}",
                            code="LOCK_TIMEOUT",
                            details={"lock_path": str(self.path)},
                        ) from exc
                    sleep(min(poll_seconds, remaining))
        except BaseException:
            os.close(descriptor)
            raise

    def _try_lock(self, descriptor: int) -> None:
        os.lseek(descriptor, 0, os.SEEK_SET)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            self._backend = "msvcrt"
            return
        try:
            import fcntl
        except ImportError as exc:  # pragma: no cover - exotic platform guard
            raise TransactionViolation(
                "this platform has no supported cross-process file lock",
                code="LOCK_BACKEND_UNAVAILABLE",
            ) from exc
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self._backend = "fcntl"

    def close(self) -> None:
        descriptor = self._descriptor
        self._descriptor = None
        if descriptor is None:
            return
        try:
            os.lseek(descriptor, 0, os.SEEK_SET)
            if self._backend == "msvcrt":
                import msvcrt

                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            elif self._backend == "fcntl":
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            os.close(descriptor)


@dataclass(slots=True)
class _FinalBaseline:
    path: Path
    existed: bool
    evidence: FileEvidence | None
    backup_path: Path | None
    backup_evidence: FileEvidence | None


@dataclass(frozen=True, slots=True)
class _JournalFinal:
    path: Path
    existed: bool
    baseline: FileEvidence | None
    backup_path: Path | None
    backup_evidence: FileEvidence | None
    candidate_path: Path
    candidate_evidence: FileEvidence
    progress: str


@dataclass(frozen=True, slots=True)
class _JournalRecord:
    final_set_id: str
    execution_id: str
    status: str
    work_dir: Path
    owned_paths: tuple[Path, ...]
    finals: tuple[_JournalFinal, ...]


@dataclass(frozen=True, slots=True)
class _JournalClaim:
    final_set_id: str
    execution_id: str
    journal_path: Path
    final_paths: tuple[Path, ...]


def _evidence_from_payload(
    payload: object,
    *,
    expected_path: Path,
    label: str,
) -> FileEvidence:
    if not isinstance(payload, Mapping):
        raise TransactionViolation(
            f"publish journal {label} is not an object",
            code="JOURNAL_INVALID",
        )
    try:
        evidence = FileEvidence(
            path=str(payload["path"]),
            sha256=str(payload["sha256"]),
            byte_size=payload["byte_size"],  # type: ignore[arg-type]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TransactionViolation(
            f"publish journal {label} evidence is invalid",
            code="JOURNAL_INVALID",
        ) from exc
    if Path(evidence.path).expanduser().resolve() != expected_path:
        raise TransactionViolation(
            f"publish journal {label} path does not match its owner",
            code="JOURNAL_INVALID",
        )
    return evidence


def _read_journal_payload(path: Path) -> Mapping[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TransactionViolation(
            f"cannot read publish journal: {path}",
            code="JOURNAL_INVALID",
            details={"journal_path": str(path)},
        ) from exc
    if not isinstance(payload, Mapping):
        raise TransactionViolation(
            "publish journal root is not an object",
            code="JOURNAL_INVALID",
        )
    if payload.get("schema") != _JOURNAL_SCHEMA or payload.get(
        "schema_version"
    ) != _JOURNAL_SCHEMA_VERSION:
        raise TransactionViolation(
            "publish journal identity or schema does not match",
            code="JOURNAL_INVALID",
        )
    return payload


def _journal_header(payload: Mapping[str, object]) -> tuple[str, str]:
    execution_id = payload.get("execution_id")
    status = payload.get("status")
    if not isinstance(execution_id, str) or not execution_id.strip():
        raise TransactionViolation(
            "publish journal execution_id is invalid",
            code="JOURNAL_INVALID",
        )
    if not isinstance(status, str) or status not in _JOURNAL_STATUSES:
        raise TransactionViolation(
            "publish journal status is invalid",
            code="JOURNAL_INVALID",
        )
    return execution_id, str(status)


def _journal_final_identity(
    payload: Mapping[str, object],
    *,
    expected_final_set_id: str | None,
    expected_final_paths: tuple[Path, ...] | None,
) -> tuple[tuple[Path, ...], str]:
    raw_final_paths = payload.get("final_paths")
    if (
        not isinstance(raw_final_paths, list)
        or not raw_final_paths
        or not all(isinstance(item, str) for item in raw_final_paths)
    ):
        raise TransactionViolation(
            "publish journal final_paths is invalid",
            code="JOURNAL_INVALID",
        )
    final_paths = tuple(
        Path(item).expanduser().resolve() for item in raw_final_paths
    )
    if len(set(final_paths)) != len(final_paths):
        raise TransactionViolation(
            "publish journal final set contains duplicates",
            code="JOURNAL_INVALID",
        )
    final_set_id = _final_set_id(final_paths)
    if payload.get("final_set_id") != final_set_id or (
        expected_final_set_id is not None
        and final_set_id != expected_final_set_id
    ):
        raise TransactionViolation(
            "publish journal final-set identity is invalid",
            code="JOURNAL_INVALID",
        )
    if expected_final_paths is not None and sorted(
        _canonical_path(path) for path in final_paths
    ) != sorted(_canonical_path(path) for path in expected_final_paths):
        raise TransactionViolation(
            "publish journal final set does not match its claim",
            code="JOURNAL_INVALID",
        )
    return final_paths, final_set_id


def _journal_work_dir(
    payload: Mapping[str, object],
    execution_id: str,
) -> Path:
    try:
        work_dir = Path(str(payload["work_dir"])).expanduser().resolve()
    except (KeyError, TypeError, ValueError) as exc:
        raise TransactionViolation(
            "publish journal work_dir is invalid",
            code="JOURNAL_INVALID",
        ) from exc
    if not work_dir.name.startswith(f".material-exec-{execution_id}-"):
        raise TransactionViolation(
            "publish journal work_dir is not transaction-owned",
            code="JOURNAL_INVALID",
        )
    return work_dir


def _journal_candidate(
    raw: Mapping[str, object],
) -> tuple[Path, FileEvidence]:
    payload = raw.get("candidate")
    if not isinstance(payload, Mapping):
        raise TransactionViolation(
            "publish journal candidate is invalid",
            code="JOURNAL_INVALID",
        )
    try:
        path = Path(str(payload["path"])).expanduser().resolve()
    except (KeyError, TypeError, ValueError) as exc:
        raise TransactionViolation(
            "publish journal candidate path is invalid",
            code="JOURNAL_INVALID",
        ) from exc
    evidence = _evidence_from_payload(
        payload,
        expected_path=path,
        label="candidate",
    )
    return path, evidence


def _journal_baseline(
    raw: Mapping[str, object],
    *,
    final: Path,
    existed: bool,
) -> tuple[FileEvidence | None, Path | None, FileEvidence | None]:
    if not existed:
        if any(
            raw.get(key) is not None
            for key in ("baseline", "backup_path", "backup")
        ):
            raise TransactionViolation(
                "publish journal has backup data for a new final",
                code="JOURNAL_INVALID",
            )
        return None, None, None

    baseline = _evidence_from_payload(
        raw.get("baseline"),
        expected_path=final,
        label="baseline",
    )
    raw_backup_path = raw.get("backup_path")
    if not isinstance(raw_backup_path, str) or not raw_backup_path:
        raise TransactionViolation(
            "publish journal backup path is invalid",
            code="JOURNAL_INVALID",
        )
    backup_path = Path(raw_backup_path).expanduser().resolve()
    backup = _evidence_from_payload(
        raw.get("backup"),
        expected_path=backup_path,
        label="backup",
    )
    if not same_file_identity(baseline, backup):
        raise TransactionViolation(
            "publish journal backup does not match baseline",
            code="JOURNAL_INVALID",
        )
    return baseline, backup_path, backup


def _journal_final(
    raw: object,
    *,
    expected_paths: set[Path],
    seen: set[Path],
) -> _JournalFinal:
    if not isinstance(raw, Mapping):
        raise TransactionViolation(
            "publish journal final entry is invalid",
            code="JOURNAL_INVALID",
        )
    try:
        final = Path(str(raw["path"])).expanduser().resolve()
    except (KeyError, TypeError, ValueError) as exc:
        raise TransactionViolation(
            "publish journal final path is invalid",
            code="JOURNAL_INVALID",
        ) from exc
    if final not in expected_paths or final in seen:
        raise TransactionViolation(
            "publish journal contains an unexpected final",
            code="JOURNAL_INVALID",
        )
    seen.add(final)
    existed = raw.get("existed")
    progress = raw.get("progress")
    if (
        not isinstance(existed, bool)
        or not isinstance(progress, str)
        or progress not in _PROGRESS_STATES
    ):
        raise TransactionViolation(
            "publish journal baseline state is invalid",
            code="JOURNAL_INVALID",
        )
    candidate_path, candidate = _journal_candidate(raw)
    baseline, backup_path, backup = _journal_baseline(
        raw,
        final=final,
        existed=existed,
    )
    return _JournalFinal(
        path=final,
        existed=existed,
        baseline=baseline,
        backup_path=backup_path,
        backup_evidence=backup,
        candidate_path=candidate_path,
        candidate_evidence=candidate,
        progress=str(progress),
    )


def _journal_finals(
    payload: Mapping[str, object],
    final_paths: tuple[Path, ...],
) -> tuple[_JournalFinal, ...]:
    raw_finals = payload.get("finals")
    if not isinstance(raw_finals, list) or len(raw_finals) != len(final_paths):
        raise TransactionViolation(
            "publish journal finals collection is invalid",
            code="JOURNAL_INVALID",
        )
    expected_paths = set(final_paths)
    seen: set[Path] = set()
    return tuple(
        _journal_final(raw, expected_paths=expected_paths, seen=seen)
        for raw in raw_finals
    )


def _validate_journal_progress(
    payload: Mapping[str, object],
    finals: tuple[_JournalFinal, ...],
    final_paths: tuple[Path, ...],
    status: str,
) -> None:
    raw_published = payload.get("published_final_paths")
    if not isinstance(raw_published, list) or not all(
        isinstance(item, str) for item in raw_published
    ):
        raise TransactionViolation(
            "publish journal published-final set is invalid",
            code="JOURNAL_INVALID",
        )
    published_paths = {
        Path(item).expanduser().resolve() for item in raw_published
    }
    progress_published = {
        item.path for item in finals if item.progress == "published"
    }
    if published_paths != progress_published:
        raise TransactionViolation(
            "publish journal progress disagrees with replaced-final set",
            code="JOURNAL_INVALID",
        )
    raw_active = payload.get("active_replace_final_path")
    active_path = (
        Path(raw_active).expanduser().resolve()
        if isinstance(raw_active, str) and raw_active
        else None
    )
    replacing_paths = {
        item.path for item in finals if item.progress == "replacing"
    }
    if (active_path is None and replacing_paths) or (
        active_path is not None and replacing_paths != {active_path}
    ):
        raise TransactionViolation(
            "publish journal active replace state is invalid",
            code="JOURNAL_INVALID",
        )
    if status in {"commit_ready", "completed"} and progress_published != set(
        final_paths
    ):
        raise TransactionViolation(
            "publish journal reached commit without every final",
            code="JOURNAL_INVALID",
        )


def _journal_owned_paths(payload: Mapping[str, object]) -> tuple[Path, ...]:
    raw_owned_paths = payload.get("owned_paths")
    if not isinstance(raw_owned_paths, list) or not all(
        isinstance(item, str) for item in raw_owned_paths
    ):
        raise TransactionViolation(
            "publish journal owned_paths is invalid",
            code="JOURNAL_INVALID",
        )
    return tuple(
        Path(item).expanduser().resolve() for item in raw_owned_paths
    )


class OwnedAssemblyTransaction:
    """Own stages and atomically publish a complete, recoverable final set."""

    def __init__(
        self,
        *,
        execution_id: str,
        final_paths: tuple[Path, ...],
        work_root: Path | None,
        atomic_replace: Callable[[str | Path, str | Path], object] = os.replace,
        lock_timeout_seconds: float = 5.0,
        lock_poll_seconds: float = 0.05,
    ) -> None:
        if not execution_id.strip():
            raise ValueError("execution_id must not be empty")
        if not final_paths:
            raise ValueError("final_paths must not be empty")
        normalized = tuple(path.expanduser().resolve() for path in final_paths)
        if len(set(normalized)) != len(normalized):
            raise ValueError("final paths must be unique")
        if not callable(atomic_replace):
            raise TypeError("atomic_replace must be callable")
        if (
            isinstance(lock_timeout_seconds, bool)
            or not isinstance(lock_timeout_seconds, (int, float))
            or lock_timeout_seconds < 0
        ):
            raise ValueError("lock_timeout_seconds must be non-negative")
        if (
            isinstance(lock_poll_seconds, bool)
            or not isinstance(lock_poll_seconds, (int, float))
            or lock_poll_seconds <= 0
        ):
            raise ValueError("lock_poll_seconds must be positive")

        self.execution_id = execution_id
        self.final_paths = normalized
        self._atomic_replace = atomic_replace
        self._owned_files: set[Path] = set()
        self._baselines: tuple[_FinalBaseline, ...] = ()
        self._lock_handles: dict[Path, _ExclusiveFileLock] = {}
        self._active_claim_paths: set[Path] = set()
        self._published = False
        self._released = False
        self._journal_active = False
        self._journal_status = ""
        self._publish_candidates: dict[Path, FileEvidence] = {}
        self._publish_progress: dict[Path, str] = {}
        self._published_final_paths: list[Path] = []
        self._active_replace: Path | None = None
        # ``None`` is deliberate until lock acquisition and crash recovery
        # finish.  Using ``Path()`` here would point at the process CWD and
        # would make constructor-failure cleanup dangerously ambiguous.
        self.work_dir: Path | None = None

        self.final_set_id = _final_set_id(self.final_paths)
        self.journal_path = _journal_path_for(self.final_paths)
        self.lock_paths = tuple(
            _lock_path_for(final)
            for final in sorted(self.final_paths, key=_canonical_path)
        )

        for final in normalized:
            final.parent.mkdir(parents=True, exist_ok=True)

        deadline = monotonic() + float(lock_timeout_seconds)
        try:
            self._replace_lock_set(
                set(self.final_paths),
                deadline=deadline,
                poll_seconds=float(lock_poll_seconds),
            )
            self._recover_intersecting_publishes(
                deadline=deadline,
                poll_seconds=float(lock_poll_seconds),
            )

            root = (
                work_root.expanduser().resolve()
                if work_root is not None
                else normalized[0].parent
            )
            root.mkdir(parents=True, exist_ok=True)
            self.work_dir = Path(
                tempfile.mkdtemp(
                    prefix=f".material-exec-{execution_id}-",
                    dir=str(root),
                )
            ).resolve()

            baselines: list[_FinalBaseline] = []
            for path in normalized:
                baselines.append(self._capture_baseline(path))
            self._baselines = tuple(baselines)
        except BaseException:
            self._cleanup_unjournaled_owned()
            self._release_locks()
            raise

    def _capture_baseline(self, final: Path) -> _FinalBaseline:
        if not final.exists():
            return _FinalBaseline(final, False, None, None, None)
        evidence = stable_file_evidence(final)
        backup = final.parent / (
            f".{final.name}.material-{self.execution_id}-{uuid4().hex}.backup"
        )
        if backup.exists():
            raise TransactionViolation(f"owned backup already exists: {backup}")
        # Only the exact bytes are part of the rollback contract.  ``copy2``
        # can copy a Windows read-only attribute and then prevent the mandatory
        # file flush; a fresh transaction-owned backup must remain writable.
        copyfile(final, backup)
        _fsync_file(backup)
        _fsync_directory(backup.parent)
        backup_evidence = stable_file_evidence(backup)
        if not same_file_identity(evidence, backup_evidence):
            backup.unlink(missing_ok=True)
            raise TransactionViolation(f"failed to verify final backup: {final}")
        self._owned_files.add(backup)
        return _FinalBaseline(final, True, evidence, backup, backup_evidence)

    def allocate_stage(self, variant_id: str, final: Path) -> Path:
        final = final.resolve()
        if final not in self.final_paths:
            raise TransactionViolation("stage final is outside this transaction")
        slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", variant_id).strip("-.") or "variant"
        suffix = final.suffix or ".bin"
        stage = final.parent / (
            f".{final.stem}.material-{self.execution_id}-{slug}-{uuid4().hex}.stage{suffix}"
        )
        if stage.exists():
            raise TransactionViolation(f"owned stage already exists: {stage}")
        self._owned_files.add(stage)
        return stage

    def own_work_file(self, relative_name: str) -> Path:
        if not relative_name or Path(relative_name).name != relative_name:
            raise ValueError("relative_name must be one filename")
        if self.work_dir is None:  # pragma: no cover - constructor invariant
            raise TransactionViolation("transaction work directory is unavailable")
        target = (self.work_dir / relative_name).resolve()
        if target.parent != self.work_dir:
            raise TransactionViolation("work file escaped the owned work directory")
        self._owned_files.add(target)
        return target

    def accept_layout_shadow(self, source_stage: Path, shadow_path: str | Path) -> Path:
        source = source_stage.resolve()
        raw_shadow = Path(shadow_path).expanduser()
        if raw_shadow.is_symlink():
            raise TransactionViolation("layout shadow cannot be a symbolic link")
        shadow = raw_shadow.resolve()
        if source not in self._owned_files:
            raise TransactionViolation("layout source is not an owned stage")
        if shadow.parent != source.parent or shadow == source:
            raise TransactionViolation("layout shadow is outside the owned stage directory")
        if not is_controlled_layout_shadow(source, shadow):
            raise TransactionViolation("layout shadow does not match the ownership contract")
        if shadow.is_symlink() or not shadow.is_file():
            raise TransactionViolation("layout shadow is not a regular file")
        self._owned_files.add(shadow)
        return shadow

    def verify_finals_unchanged(self) -> None:
        diagnostics: list[str] = []
        for baseline in self._baselines:
            if not baseline.existed:
                if baseline.path.exists():
                    diagnostics.append(f"unexpected final appeared: {baseline.path}")
                continue
            try:
                current = stable_file_evidence(baseline.path)
            except Exception as exc:
                diagnostics.append(f"cannot verify final {baseline.path}: {exc}")
                continue
            assert baseline.evidence is not None
            if not same_file_identity(current, baseline.evidence):
                diagnostics.append(f"final changed before publish: {baseline.path}")
        if diagnostics:
            raise TransactionViolation("; ".join(diagnostics))

    def publish(self, candidates: Mapping[Path, FileEvidence]) -> dict[Path, FileEvidence]:
        if self._published:
            raise TransactionViolation("transaction was already published")
        if self._released:
            raise TransactionViolation("transaction was already committed")
        normalized = {path.resolve(): evidence for path, evidence in candidates.items()}
        if set(normalized) != set(self.final_paths):
            raise TransactionViolation("publish candidates do not cover every final")
        candidate_paths = [Path(item.path).resolve() for item in normalized.values()]
        if len(set(candidate_paths)) != len(candidate_paths):
            raise TransactionViolation("one candidate cannot publish multiple variants")
        self.verify_finals_unchanged()
        for final, expected in normalized.items():
            candidate = Path(expected.path).resolve()
            if candidate not in self._owned_files:
                raise TransactionViolation(f"publish candidate is not owned: {candidate}")
            current = stable_file_evidence(candidate)
            if not same_file_identity(current, expected):
                raise TransactionViolation(f"publish candidate drifted: {candidate}")
            _fsync_file(candidate)
            _fsync_directory(candidate.parent)

        self._publish_candidates = dict(normalized)
        self._publish_progress = {final: "pending" for final in self.final_paths}
        self._published_final_paths = []
        self._journal_status = "prepared"
        self._write_current_journal()

        try:
            for final in self.final_paths:
                candidate = Path(normalized[final].path).resolve()
                self._journal_status = "publishing"
                self._publish_progress[final] = "replacing"
                self._active_replace = final
                self._write_current_journal()

                self._atomic_replace(candidate, final)
                _fsync_file(final)
                _fsync_directory(final.parent)
                self._owned_files.discard(candidate)

                self._publish_progress[final] = "published"
                self._published_final_paths.append(final)
                self._active_replace = None
                self._write_current_journal()
        except BaseException:
            self.restore_finals()
            raise

        published: dict[Path, FileEvidence] = {}
        try:
            for final in self.final_paths:
                current = stable_file_evidence(final)
                if not same_file_identity(current, normalized[final]):
                    raise TransactionViolation(
                        f"published final does not match candidate: {final}"
                    )
                published[final] = current
            self._journal_status = "commit_ready"
            self._write_current_journal()
        except BaseException:
            self.restore_finals()
            raise
        self._published = True
        return published

    def restore_finals(self) -> None:
        if self._released:
            raise TransactionViolation(
                "a committed transaction cannot be rolled back",
                code="TRANSACTION_COMMITTED",
            )
        failures: list[str] = []
        replacements: list[tuple[_FinalBaseline, Path]] = []
        removals: list[_FinalBaseline] = []

        for baseline in self._baselines:
            try:
                if baseline.existed:
                    assert baseline.evidence is not None
                    current = (
                        stable_file_evidence(baseline.path)
                        if baseline.path.is_file() and not baseline.path.is_symlink()
                        else None
                    )
                    if current is None or not same_file_identity(
                        current, baseline.evidence
                    ):
                        backup = baseline.backup_path
                        if backup is None or not backup.is_file():
                            raise TransactionViolation(
                                f"verified backup is unavailable: {baseline.path}"
                            )
                        backup_evidence = stable_file_evidence(backup)
                        expected_backup = baseline.backup_evidence
                        if (
                            expected_backup is None
                            or not same_file_identity(backup_evidence, expected_backup)
                            or not same_file_identity(backup_evidence, baseline.evidence)
                        ):
                            raise TransactionViolation(
                                f"verified backup drifted: {baseline.path}"
                            )
                        replacements.append((baseline, backup))
                elif baseline.path.exists():
                    removals.append(baseline)
            except Exception as exc:
                failures.append(f"{baseline.path}: {exc}")
        if failures:
            raise TransactionViolation("; ".join(failures))

        for baseline, backup in replacements:
            try:
                self._atomic_replace(backup, baseline.path)
                _fsync_file(baseline.path)
                _fsync_directory(baseline.path.parent)
                self._owned_files.discard(backup)
            except Exception as exc:
                failures.append(f"{baseline.path}: {exc}")
        for baseline in removals:
            try:
                baseline.path.unlink()
                _fsync_directory(baseline.path.parent)
            except Exception as exc:
                failures.append(f"{baseline.path}: {exc}")

        for baseline in self._baselines:
            try:
                if baseline.existed:
                    assert baseline.evidence is not None
                    restored = stable_file_evidence(baseline.path)
                    if not same_file_identity(restored, baseline.evidence):
                        raise TransactionViolation(
                            f"final rollback verification failed: {baseline.path}"
                        )
                elif baseline.path.exists():
                    raise TransactionViolation(
                        f"new final survived rollback: {baseline.path}"
                    )
            except Exception as exc:
                failures.append(f"{baseline.path}: {exc}")
        if failures:
            raise TransactionViolation("; ".join(failures))

        self._published = False
        if self._journal_active:
            self._journal_status = "rolled_back"
            self._active_replace = None
            self._publish_progress = {
                final: "pending" for final in self.final_paths
            }
            self._published_final_paths = []
            self._write_current_journal()
            self._remove_current_journal_artifacts()

    def release_backups(self) -> None:
        if self._released:
            return
        if not self._published or not self._journal_active:
            raise TransactionViolation("transaction has not been published")
        for final, expected in self._publish_candidates.items():
            current = stable_file_evidence(final)
            if not same_file_identity(current, expected):
                raise TransactionViolation(
                    f"final changed before durable commit: {final}",
                    code="COMMIT_FINAL_DRIFT",
                )

        # The completed journal is the commit point.  It must be durable before
        # any rollback backup is removed; otherwise a crash could leave neither
        # a commit record nor enough data to restore the baseline.
        self._journal_status = "completed"
        self._active_replace = None
        self._write_current_journal()
        self._released = True
        try:
            self._remove_current_journal_artifacts()
        except Exception:
            # Publication is already durably committed.  Keeping a completed
            # journal is intentional: the next holder will finish cleanup.
            pass

    def cleanup_owned(self) -> None:
        try:
            if self._journal_active:
                if self._released:
                    try:
                        self._remove_current_journal_artifacts()
                    except Exception:
                        pass
                else:
                    # An incomplete durable journal owns the backups.  Never
                    # destroy them here; release the locks and let recovery run.
                    return
            else:
                self._cleanup_unjournaled_owned()
        finally:
            self._release_locks()

    def _write_current_journal(self) -> None:
        if self.work_dir is None:  # pragma: no cover - constructor invariant
            raise TransactionViolation("transaction work directory is unavailable")
        payload: dict[str, object] = {
            "schema": _JOURNAL_SCHEMA,
            "schema_version": _JOURNAL_SCHEMA_VERSION,
            "final_set_id": self.final_set_id,
            "execution_id": self.execution_id,
            "status": self._journal_status,
            "final_paths": [
                str(path)
                for path in sorted(self.final_paths, key=_canonical_path)
            ],
            "work_dir": str(self.work_dir),
            "owned_paths": [
                str(path)
                for path in sorted(
                    self._owned_files
                    | {
                        Path(evidence.path).expanduser().resolve()
                        for evidence in self._publish_candidates.values()
                    }
                    | {
                        baseline.backup_path
                        for baseline in self._baselines
                        if baseline.backup_path is not None
                    },
                    key=_canonical_path,
                )
            ],
            "active_replace_final_path": (
                str(self._active_replace) if self._active_replace is not None else None
            ),
            "published_final_paths": [
                str(path) for path in self._published_final_paths
            ],
            "finals": [],
        }
        final_records: list[dict[str, object]] = []
        baseline_by_path = {item.path: item for item in self._baselines}
        for final in self.final_paths:
            baseline = baseline_by_path[final]
            candidate = self._publish_candidates[final]
            final_records.append(
                {
                    "path": str(final),
                    "existed": baseline.existed,
                    "baseline": (
                        baseline.evidence.to_dict()
                        if baseline.evidence is not None
                        else None
                    ),
                    "backup_path": (
                        str(baseline.backup_path)
                        if baseline.backup_path is not None
                        else None
                    ),
                    "backup": (
                        baseline.backup_evidence.to_dict()
                        if baseline.backup_evidence is not None
                        else None
                    ),
                    "candidate": candidate.to_dict(),
                    "progress": self._publish_progress[final],
                }
            )
        payload["finals"] = final_records
        first_write = not self._journal_active
        if first_write:
            self._write_current_claims()
        try:
            _atomic_write_json(self.journal_path, payload)
        except BaseException:
            if first_write:
                self._remove_active_claims()
            raise
        self._journal_active = True

    def _write_current_claims(self) -> None:
        payload: dict[str, object] = {
            "schema": _CLAIM_SCHEMA,
            "schema_version": _CLAIM_SCHEMA_VERSION,
            "final_set_id": self.final_set_id,
            "execution_id": self.execution_id,
            "journal_path": str(self.journal_path),
            "final_paths": [
                str(path) for path in sorted(self.final_paths, key=_canonical_path)
            ],
        }
        for final in sorted(self.final_paths, key=_canonical_path):
            claim_path = _claim_path_for(final)
            if claim_path.exists() or claim_path.is_symlink():
                raise TransactionViolation(
                    f"a publication claim already exists: {claim_path}",
                    code="CLAIM_CONFLICT",
                )
            _atomic_write_json(claim_path, payload)
            self._active_claim_paths.add(claim_path)

    def _remove_active_claims(self) -> None:
        for claim_path in self._active_claim_paths:
            claim_path.unlink(missing_ok=True)
            _fsync_directory(claim_path.parent)
        self._active_claim_paths.clear()

    def _load_claim(self, path: Path, *, owner_final: Path) -> _JournalClaim:
        if path.is_symlink():
            raise TransactionViolation(
                f"publication claim cannot be a symbolic link: {path}",
                code="CLAIM_INVALID",
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise TransactionViolation(
                f"cannot read publication claim: {path}",
                code="CLAIM_INVALID",
            ) from exc
        if not isinstance(payload, Mapping) or (
            payload.get("schema") != _CLAIM_SCHEMA
            or payload.get("schema_version") != _CLAIM_SCHEMA_VERSION
        ):
            raise TransactionViolation(
                f"publication claim schema is invalid: {path}",
                code="CLAIM_INVALID",
            )
        execution_id = payload.get("execution_id")
        raw_paths = payload.get("final_paths")
        if (
            not isinstance(execution_id, str)
            or not execution_id.strip()
            or not isinstance(raw_paths, list)
            or not raw_paths
            or not all(isinstance(item, str) for item in raw_paths)
        ):
            raise TransactionViolation(
                f"publication claim payload is invalid: {path}",
                code="CLAIM_INVALID",
            )
        final_paths = tuple(Path(item).expanduser().resolve() for item in raw_paths)
        if len(set(final_paths)) != len(final_paths) or owner_final not in final_paths:
            raise TransactionViolation(
                f"publication claim final set is invalid: {path}",
                code="CLAIM_INVALID",
            )
        identity = _final_set_id(final_paths)
        if payload.get("final_set_id") != identity:
            raise TransactionViolation(
                f"publication claim identity is invalid: {path}",
                code="CLAIM_INVALID",
            )
        journal_path = Path(str(payload.get("journal_path") or "")).expanduser().resolve()
        if journal_path != _journal_path_for(final_paths):
            raise TransactionViolation(
                f"publication claim journal path is invalid: {path}",
                code="CLAIM_INVALID",
            )
        return _JournalClaim(
            final_set_id=identity,
            execution_id=execution_id,
            journal_path=journal_path,
            final_paths=final_paths,
        )

    def _replace_lock_set(
        self,
        finals: set[Path],
        *,
        deadline: float,
        poll_seconds: float,
    ) -> None:
        self._release_locks()
        try:
            for final in sorted(finals, key=_canonical_path):
                lock = _ExclusiveFileLock(_lock_path_for(final))
                lock.acquire(deadline=deadline, poll_seconds=poll_seconds)
                self._lock_handles[final] = lock
        except BaseException:
            self._release_locks()
            raise

    def _recover_intersecting_publishes(
        self,
        *,
        deadline: float,
        poll_seconds: float,
    ) -> None:
        """Recover every unfinished journal intersecting the requested finals.

        A crashed ``{A, B}`` publish is discoverable even when the next request
        only contains ``{A}``: each final owns a small durable claim that points
        at the canonical journal.  Missing locks are added by releasing and
        reacquiring the complete union in canonical order, avoiding deadlocks.
        """

        locked_finals = set(self._lock_handles)
        while True:
            claims: dict[str, _JournalClaim] = {}
            expanded_finals = set(locked_finals)
            for final in sorted(locked_finals, key=_canonical_path):
                claim_path = _claim_path_for(final)
                if not claim_path.exists() and not claim_path.is_symlink():
                    continue
                claim = self._load_claim(claim_path, owner_final=final)
                previous = claims.get(claim.final_set_id)
                if previous is not None and previous != claim:
                    raise TransactionViolation(
                        "publication claims disagree about one final set",
                        code="CLAIM_INVALID",
                    )
                claims[claim.final_set_id] = claim
                expanded_finals.update(claim.final_paths)

            if expanded_finals != locked_finals:
                self._replace_lock_set(
                    expanded_finals,
                    deadline=deadline,
                    poll_seconds=poll_seconds,
                )
                locked_finals = expanded_finals
                continue

            recovered_any = False
            for identity, claim in sorted(claims.items()):
                source = self._find_journal_source(
                    claim.journal_path,
                    expected_final_set_id=identity,
                    expected_final_paths=claim.final_paths,
                )
                if source is None:
                    self._remove_claims_for(claim.final_paths)
                    recovered_any = True
                    continue
                record = self._load_journal_record(
                    source,
                    expected_final_set_id=identity,
                    expected_final_paths=claim.final_paths,
                )
                self._recover_record(record)
                self._cleanup_recovered_journal(record, source)
                recovered_any = True

            # Backward-compatible exact-set recovery also handles a journal
            # written before claim creation completed.  No replace can begin
            # until every claim and this canonical journal are durable.
            if self.final_set_id not in claims:
                source = self._find_journal_source(
                    self.journal_path,
                    expected_final_set_id=self.final_set_id,
                    expected_final_paths=self.final_paths,
                )
                if source is not None:
                    record = self._load_journal_record(
                        source,
                        expected_final_set_id=self.final_set_id,
                        expected_final_paths=self.final_paths,
                    )
                    self._recover_record(record)
                    self._cleanup_recovered_journal(record, source)
                    recovered_any = True

            if recovered_any:
                # Recovery may have removed claims or exposed another stale
                # claim in the expanded lock set.  Re-scan while all locks stay
                # held.
                continue
            break

        for final in tuple(self._lock_handles):
            if final not in self.final_paths:
                self._lock_handles.pop(final).close()

    def _find_journal_source(
        self,
        journal_path: Path,
        *,
        expected_final_set_id: str,
        expected_final_paths: tuple[Path, ...],
    ) -> Path | None:
        if journal_path.is_symlink():
            raise TransactionViolation(
                f"publish journal cannot be a symbolic link: {journal_path}",
                code="JOURNAL_INVALID",
            )
        if journal_path.is_file():
            return journal_path
        temporary_paths = sorted(
            journal_path.parent.glob(f".{journal_path.name}.*.tmp")
        )
        valid_temporaries: list[Path] = []
        for temporary in temporary_paths:
            try:
                self._load_journal_record(
                    temporary,
                    expected_final_set_id=expected_final_set_id,
                    expected_final_paths=expected_final_paths,
                )
            except TransactionViolation:
                temporary.unlink(missing_ok=True)
            else:
                valid_temporaries.append(temporary)
        if len(valid_temporaries) > 1:
            raise TransactionViolation(
                "multiple recoverable temporary publish journals exist",
                code="JOURNAL_AMBIGUOUS",
                details={
                    "journal_paths": [str(path) for path in valid_temporaries]
                },
            )
        return valid_temporaries[0] if valid_temporaries else None

    def _recover_record(self, record: _JournalRecord) -> None:
        if record.status == "completed":
            self._validate_record_backups(record)
        else:
            self._restore_journal_record(record)

    def _remove_claims_for(self, final_paths: tuple[Path, ...]) -> None:
        for final in final_paths:
            claim_path = _claim_path_for(final)
            claim_path.unlink(missing_ok=True)
            _fsync_directory(claim_path.parent)

    def _cleanup_recovered_journal(
        self,
        record: _JournalRecord,
        source: Path,
    ) -> None:
        self._cleanup_journal_record(record)
        canonical = _journal_path_for(tuple(item.path for item in record.finals))
        canonical.unlink(missing_ok=True)
        source.unlink(missing_ok=True)
        for temporary in canonical.parent.glob(f".{canonical.name}.*.tmp"):
            temporary.unlink(missing_ok=True)
        _fsync_directory(canonical.parent)
        self._remove_claims_for(tuple(item.path for item in record.finals))

    def _load_journal_record(
        self,
        path: Path,
        *,
        expected_final_set_id: str | None = None,
        expected_final_paths: tuple[Path, ...] | None = None,
    ) -> _JournalRecord:
        payload = _read_journal_payload(path)
        execution_id, status = _journal_header(payload)
        final_paths, final_set_id = _journal_final_identity(
            payload,
            expected_final_set_id=expected_final_set_id,
            expected_final_paths=expected_final_paths,
        )
        work_dir = _journal_work_dir(payload, execution_id)
        finals = _journal_finals(payload, final_paths)
        _validate_journal_progress(
            payload,
            finals,
            final_paths,
            status,
        )
        record = _JournalRecord(
            final_set_id=final_set_id,
            execution_id=execution_id,
            status=status,
            work_dir=work_dir,
            owned_paths=_journal_owned_paths(payload),
            finals=finals,
        )
        self._validate_record_ownership(record)
        return record

    def _validate_record_ownership(self, record: _JournalRecord) -> None:
        finals = {item.path for item in record.finals}
        backups = {
            item.backup_path for item in record.finals if item.backup_path is not None
        }
        candidates = {item.candidate_path for item in record.finals}
        if len(candidates) != len(record.finals):
            raise TransactionViolation(
                "publish journal reuses one candidate for multiple finals",
                code="JOURNAL_INVALID",
            )
        owned_paths = set(record.owned_paths)
        if not backups.issubset(owned_paths) or not candidates.issubset(owned_paths):
            raise TransactionViolation(
                "publish journal candidate or backup is not transaction-owned",
                code="JOURNAL_INVALID",
            )
        for item in record.finals:
            if item.candidate_path == item.path or (
                item.candidate_path.parent != item.path.parent
            ):
                raise TransactionViolation(
                    "publish journal candidate is outside its final directory",
                    code="JOURNAL_INVALID",
                )
            if item.backup_path is not None:
                backup_prefix = (
                    f".{item.path.name}.material-{record.execution_id}-"
                )
                if (
                    item.backup_path.parent != item.path.parent
                    or not item.backup_path.name.startswith(backup_prefix)
                    or not item.backup_path.name.endswith(".backup")
                ):
                    raise TransactionViolation(
                        "publish journal backup is outside its ownership contract",
                        code="JOURNAL_INVALID",
                    )
        final_parents = {item.path.parent for item in record.finals}
        for owned in record.owned_paths:
            if owned in finals:
                raise TransactionViolation(
                    "publish journal claims a final as an owned temporary",
                    code="JOURNAL_INVALID",
                )
            if owned in backups or owned in candidates:
                continue
            try:
                owned.relative_to(record.work_dir)
            except ValueError:
                if (
                    owned.parent not in final_parents
                    or f".material-{record.execution_id}-" not in owned.name
                    or not owned.name.endswith(".stage.docx")
                ):
                    raise TransactionViolation(
                        f"publish journal contains an unowned cleanup path: {owned}",
                        code="JOURNAL_INVALID",
                    )

    def _validate_record_backups(self, record: _JournalRecord) -> None:
        for item in record.finals:
            backup = item.backup_path
            expected = item.backup_evidence
            if backup is None:
                continue
            if backup.is_symlink():
                raise TransactionViolation(
                    f"publish journal backup became a symbolic link: {backup}",
                    code="RECOVERY_BACKUP_DRIFT",
                )
            if not backup.exists():
                continue
            if expected is None:
                raise TransactionViolation(
                    f"completed journal has an unexpected backup: {backup}",
                    code="JOURNAL_INVALID",
                )
            current = stable_file_evidence(backup)
            if not same_file_identity(current, expected):
                raise TransactionViolation(
                    f"completed journal backup drifted: {backup}",
                    code="RECOVERY_BACKUP_DRIFT",
                )

    def _restore_journal_record(self, record: _JournalRecord) -> None:
        self._validate_record_backups(record)
        actions: list[tuple[str, _JournalFinal]] = []
        for item in record.finals:
            if item.path.is_symlink() or (
                item.path.exists() and not item.path.is_file()
            ):
                raise TransactionViolation(
                    f"recovery final is not a regular file: {item.path}",
                    code="RECOVERY_CONFLICT",
                )
            current = stable_file_evidence(item.path) if item.path.is_file() else None
            replace_started = item.progress in {"replacing", "published"}
            if item.existed:
                assert item.baseline is not None
                if current is not None and same_file_identity(current, item.baseline):
                    continue
                if not replace_started:
                    raise TransactionViolation(
                        f"final changed outside the interrupted publish: {item.path}",
                        code="RECOVERY_CONFLICT",
                    )
                if current is not None and not same_file_identity(
                    current, item.candidate_evidence
                ):
                    raise TransactionViolation(
                        f"final was externally rewritten after publish crash: {item.path}",
                        code="RECOVERY_CONFLICT",
                    )
                backup = item.backup_path
                expected_backup = item.backup_evidence
                if (
                    backup is None
                    or expected_backup is None
                    or not backup.is_file()
                ):
                    raise TransactionViolation(
                        f"recovery backup is unavailable: {item.path}",
                        code="RECOVERY_BACKUP_MISSING",
                    )
                actions.append(("restore", item))
            elif current is not None:
                if not replace_started or not same_file_identity(
                    current, item.candidate_evidence
                ):
                    raise TransactionViolation(
                        f"new final was externally created after publish crash: {item.path}",
                        code="RECOVERY_CONFLICT",
                    )
                actions.append(("delete", item))

        for action, item in actions:
            if action == "restore":
                assert item.backup_path is not None
                os.replace(item.backup_path, item.path)
                _fsync_file(item.path)
                _fsync_directory(item.path.parent)
            else:
                item.path.unlink()
                _fsync_directory(item.path.parent)

        for item in record.finals:
            if item.existed:
                assert item.baseline is not None
                restored = stable_file_evidence(item.path)
                if not same_file_identity(restored, item.baseline):
                    raise TransactionViolation(
                        f"recovered final does not match baseline: {item.path}",
                        code="RECOVERY_VERIFY_FAILED",
                    )
            elif item.path.exists():
                raise TransactionViolation(
                    f"new final survived recovery: {item.path}",
                    code="RECOVERY_VERIFY_FAILED",
                )

    def _cleanup_journal_record(self, record: _JournalRecord) -> None:
        for owned in sorted(
            set(record.owned_paths), key=lambda item: len(str(item)), reverse=True
        ):
            if owned == record.work_dir:
                continue
            try:
                owned.relative_to(record.work_dir)
            except ValueError:
                if owned.is_file() or owned.is_symlink():
                    owned.unlink(missing_ok=True)
                    _fsync_directory(owned.parent)
            else:
                # The complete work directory is removed below.
                continue
        if record.work_dir.is_symlink():
            record.work_dir.unlink(missing_ok=True)
        elif record.work_dir.is_dir():
            rmtree(record.work_dir)
        for item in record.finals:
            backup = item.backup_path
            if backup is not None and (backup.is_file() or backup.is_symlink()):
                backup.unlink(missing_ok=True)
                _fsync_directory(backup.parent)

    def _remove_current_journal_artifacts(self) -> None:
        record = self._load_journal_record(
            self.journal_path,
            expected_final_set_id=self.final_set_id,
            expected_final_paths=self.final_paths,
        )
        if self._released and record.status != "completed":
            raise TransactionViolation(
                "committed transaction journal is not completed",
                code="JOURNAL_INVALID",
            )
        self._cleanup_journal_record(record)
        self.journal_path.unlink(missing_ok=True)
        for temporary in self.journal_path.parent.glob(
            f".{self.journal_path.name}.*.tmp"
        ):
            temporary.unlink(missing_ok=True)
        _fsync_directory(self.journal_path.parent)
        self._remove_claims_for(self.final_paths)
        self._active_claim_paths.clear()
        self._journal_active = False
        self._owned_files.clear()

    def _cleanup_unjournaled_owned(self) -> None:
        for path in sorted(
            self._owned_files, key=lambda item: len(str(item)), reverse=True
        ):
            try:
                if path.is_file() or path.is_symlink():
                    path.unlink(missing_ok=True)
            except OSError:
                pass
        self._owned_files.clear()
        try:
            if self.work_dir is not None and self.work_dir.is_symlink():
                self.work_dir.unlink(missing_ok=True)
            elif self.work_dir is not None and self.work_dir.is_dir():
                rmtree(self.work_dir)
        except OSError:
            pass
        self._remove_active_claims()

    def _release_locks(self) -> None:
        for lock in reversed(tuple(self._lock_handles.values())):
            lock.close()
        self._lock_handles.clear()

    def __del__(self) -> None:  # pragma: no cover - shutdown safety net
        try:
            self._release_locks()
        except Exception:
            pass


__all__ = [
    "OwnedAssemblyTransaction",
    "TransactionViolation",
    "same_file_identity",
    "stable_file_evidence",
]
