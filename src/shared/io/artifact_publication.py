"""Shared atomic publication for artifacts rendered in isolated staging areas."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import os
from pathlib import Path
from shutil import copyfile

from src.shared.io.artifact_transaction import (
    OwnedAssemblyTransaction,
    stable_file_evidence,
)


@dataclass(frozen=True, slots=True)
class StagedArtifact:
    """One verified staging file and the final path it exclusively owns."""

    artifact_id: str
    stage_path: Path
    final_path: Path


def publish_staged_artifacts(
    artifacts: Sequence[StagedArtifact],
    *,
    execution_id: str,
    work_root: Path | None = None,
    atomic_replace: Callable[[str | Path, str | Path], object] = os.replace,
) -> dict[str, str]:
    """Publish a complete artifact set or restore every previous final.

    Renderers may freely create their files below a temporary directory.  This
    boundary copies only the declared regular files into transaction-owned
    sibling stages, verifies their bytes, and publishes the whole set under a
    single rollback contract.
    """

    declared = tuple(artifacts)
    if not declared:
        raise ValueError("artifacts must not be empty")
    artifact_ids = [str(item.artifact_id or "").strip() for item in declared]
    if any(not artifact_id for artifact_id in artifact_ids):
        raise ValueError("artifact_id must not be empty")
    if len(set(artifact_ids)) != len(artifact_ids):
        raise ValueError("artifact_id values must be unique")

    normalized: list[tuple[str, Path, Path]] = []
    for artifact_id, item in zip(artifact_ids, declared):
        stage = Path(item.stage_path).expanduser()
        if stage.is_symlink() or not stage.is_file():
            raise ValueError(f"staged artifact is not a regular file: {stage}")
        stage = stage.resolve()
        final = Path(os.path.abspath(str(Path(item.final_path).expanduser())))
        symbolic_component = _first_symbolic_path_component(final)
        if symbolic_component is not None:
            raise ValueError(
                "final artifact path contains a symbolic link or junction: "
                f"{symbolic_component}"
            )
        if _paths_share_identity(stage, final):
            raise ValueError(f"staging path aliases final path: {final}")
        normalized.append((artifact_id, stage, final))
    final_paths = tuple(item[2] for item in normalized)
    if len({_path_identity_key(path) for path in final_paths}) != len(final_paths):
        raise ValueError("final artifact paths must be unique")

    transaction = OwnedAssemblyTransaction(
        execution_id=execution_id,
        final_paths=final_paths,
        work_root=work_root,
        atomic_replace=atomic_replace,
    )
    try:
        candidates = {}
        for artifact_id, stage, final in normalized:
            owned_stage = transaction.allocate_stage(artifact_id, final)
            copyfile(stage, owned_stage)
            candidates[final] = stable_file_evidence(owned_stage)
        transaction.publish(candidates)
        transaction.release_backups()
    except BaseException:
        try:
            transaction.restore_finals()
        finally:
            transaction.cleanup_owned()
        raise
    else:
        transaction.cleanup_owned()

    return {
        artifact_id: str(final)
        for artifact_id, _stage, final in normalized
    }


def _first_symbolic_path_component(path: Path) -> Path | None:
    """Return the first existing symlink/junction in a publication path."""

    current = path
    components: list[Path] = []
    while True:
        components.append(current)
        if current.parent == current:
            break
        current = current.parent
    for component in reversed(components):
        try:
            is_junction = bool(
                getattr(component, "is_junction", lambda: False)()
            )
            if component.is_symlink() or is_junction:
                return component
        except OSError:
            continue
    return None


def _paths_share_identity(left: Path, right: Path) -> bool:
    try:
        if left.exists() and right.exists() and os.path.samefile(left, right):
            return True
    except OSError:
        pass
    return _path_identity_key(left) == _path_identity_key(right)


def _path_identity_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(str(path))).casefold()


__all__ = ["StagedArtifact", "publish_staged_artifacts"]
