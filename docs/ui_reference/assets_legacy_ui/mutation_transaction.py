"""Explicit rollback boundary for Assets mutations published to the Bridge."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import logging
from typing import Callable, Generic, TypeVar

from src.config.entity import EntityProfile
from src.config.material_batch import MaterialBatchSelection


LocalStateT = TypeVar("LocalStateT")
_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class MaterialMutationSnapshot(Generic[LocalStateT]):
    """Own only state explicitly supplied by the calling presenter."""

    local_state: LocalStateT
    profile_state: EntityProfile
    profile_index: int
    batch_selection: MaterialBatchSelection


def capture_material_mutation_snapshot(
    *,
    local_state: LocalStateT,
    profile_state: EntityProfile,
    profile_index: int,
    batch_selection: MaterialBatchSelection,
) -> MaterialMutationSnapshot[LocalStateT]:
    return MaterialMutationSnapshot(
        local_state=copy.deepcopy(local_state),
        profile_state=copy.deepcopy(profile_state),
        profile_index=int(profile_index),
        batch_selection=batch_selection.clone(),
    )


def publish_or_rollback_material_mutation(
    snapshot: MaterialMutationSnapshot[LocalStateT],
    *,
    publish: Callable[[], bool],
    restore_selection: Callable[[MaterialBatchSelection], object],
    restore_profile: Callable[[int, EntityProfile], object],
    restore_local: Callable[[LocalStateT], object],
    refresh: Callable[[], object],
) -> bool:
    """Publish exactly once; restore every explicit snapshot on rejection."""

    try:
        if publish():
            return True
    except Exception:
        _LOGGER.warning(
            "Material mutation publish failed; rolling back explicit state.",
            exc_info=True,
        )

    rollback_error: Exception | None = None
    callbacks: tuple[Callable[[], object], ...] = (
        lambda: restore_profile(
            snapshot.profile_index,
            copy.deepcopy(snapshot.profile_state),
        ),
        lambda: restore_local(copy.deepcopy(snapshot.local_state)),
        refresh,
        # Publish restored state only after every local observer can see the
        # matching profile, containers, and UI projection.
        lambda: restore_selection(snapshot.batch_selection.clone()),
    )
    for callback in callbacks:
        try:
            callback()
        except Exception as exc:
            if rollback_error is None:
                rollback_error = exc
    if rollback_error is not None:
        raise RuntimeError("material_mutation_rollback_failed") from rollback_error
    return False


__all__ = [
    "MaterialMutationSnapshot",
    "capture_material_mutation_snapshot",
    "publish_or_rollback_material_mutation",
]
