"""Persistence coordinator for cached template edit sessions.

This module owns target resolution, identity collision checks, external source
revision checks, and the transition from staged files to committed sessions.
Qt dialogs and user-facing messages remain in ``TemplatePanel`` through the
injected overwrite confirmation callback.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from src.config.library import (
    is_template_library_lexical_path,
    is_template_library_path,
    template_user_target_path,
    template_source_type_for_path,
    validate_template_library_write_path,
)
from src.config.template_save_transaction import (
    TemplateSaveItem,
    save_template_batch,
)
from src.ui.template_edit_session import (
    TemplateDraftCollisionError,
    TemplateDraftContext,
    TemplateDraftStore,
    TemplateSourceRevision,
)


OVERWRITE_EXTERNAL_CHANGE = "external_change"
OVERWRITE_EXISTING_TARGET = "existing_target"


class TemplateSavePreparationCancelled(RuntimeError):
    """The user declined an overwrite required by the prepared save."""


class TemplateSaveRevisionChanged(RuntimeError):
    """A target changed after preparation and before commit."""


@dataclass(frozen=True, slots=True)
class PreparedTemplateSave:
    context: TemplateDraftContext
    target: Path
    template_id: str
    source: str
    source_type: str
    observed_revision: TemplateSourceRevision | None


class TemplateDraftSaveCoordinator:
    """Prepare and commit one collision-free batch of template drafts."""

    def __init__(
        self,
        store: TemplateDraftStore,
        *,
        confirm_overwrite: Callable[[str, Path], bool],
        save_batch: Callable[[Iterable[TemplateSaveItem]], tuple[Path, ...]] = save_template_batch,
    ) -> None:
        self._store = store
        self._confirm_overwrite = confirm_overwrite
        self._save_batch = save_batch

    @staticmethod
    def _target_key(path: Path) -> str:
        try:
            value = str(path.resolve(strict=False))
        except (OSError, RuntimeError):
            value = str(path.absolute())
        return value.casefold() if os.name == "nt" else value

    @staticmethod
    def _same_path(left: str | Path | None, right: Path) -> bool:
        if not str(left or "").strip():
            return False
        try:
            return Path(left).resolve(strict=False) == right.resolve(strict=False)
        except (OSError, RuntimeError):
            return TemplateDraftSaveCoordinator._target_key(
                Path(left)
            ) == TemplateDraftSaveCoordinator._target_key(right)

    @staticmethod
    def _observe_target_revision(target: Path) -> TemplateSourceRevision | None:
        """Capture one unambiguous missing-file or readable-file observation."""

        revision = TemplateSourceRevision.capture(target)
        path_exists = os.path.lexists(target)
        if path_exists and revision is None:
            raise OSError(f"保存目标不是可读取的常规文件: {target}")
        if not path_exists and revision is not None:
            raise TemplateSaveRevisionChanged(str(target))
        return revision

    def _prepare_context(
        self,
        context: TemplateDraftContext,
        path: str | Path | None,
    ) -> PreparedTemplateSave:
        target_value = str(path or context.path or "").strip()
        if target_value:
            target = Path(target_value)
            if is_template_library_lexical_path(target):
                target = validate_template_library_write_path(target)
            template_id = context.template_id
            same_source = self._same_path(context.path, target)
            source = "library" if is_template_library_path(target) else "file"
            source_type = template_source_type_for_path(target)
        else:
            template_id = context.template_id
            target = template_user_target_path(
                template_id,
                mode_id=context.mode_id,
            )
            same_source = False
            source = "library"
            source_type = "user"

        observed_revision = self._observe_target_revision(target)
        expected_revision = context.session.source_revision if same_source else None
        if same_source and expected_revision is not None:
            if (
                observed_revision != expected_revision
                and not self._confirm_overwrite(OVERWRITE_EXTERNAL_CHANGE, target)
            ):
                raise TemplateSavePreparationCancelled
        elif (
            observed_revision is not None
            and not self._confirm_overwrite(OVERWRITE_EXISTING_TARGET, target)
        ):
            # This includes a source path that did not exist when the edit
            # session began but was created by another process before save.
            raise TemplateSavePreparationCancelled

        self._store.ensure_rekey_available(
            context,
            mode_id=context.mode_id,
            template_id=template_id,
            path=target,
        )
        return PreparedTemplateSave(
            context=context,
            target=target,
            template_id=template_id,
            source=source,
            source_type=source_type,
            observed_revision=observed_revision,
        )

    def prepare(
        self,
        contexts: Iterable[TemplateDraftContext],
        *,
        path: str | Path | None = None,
    ) -> tuple[PreparedTemplateSave, ...]:
        selected = tuple(contexts)
        plans = tuple(
            self._prepare_context(
                context,
                path if len(selected) == 1 else None,
            )
            for context in selected
        )
        seen: dict[str, PreparedTemplateSave] = {}
        for plan in plans:
            key = self._target_key(plan.target)
            if key in seen:
                raise TemplateDraftCollisionError(
                    template_id=plan.template_id,
                    path=plan.target,
                )
            seen[key] = plan
        return plans

    def commit(
        self,
        plans: Iterable[PreparedTemplateSave],
    ) -> tuple[TemplateDraftContext, ...]:
        selected = tuple(plans)
        for plan in selected:
            try:
                current_revision = self._observe_target_revision(plan.target)
            except (OSError, TemplateSaveRevisionChanged) as exc:
                raise TemplateSaveRevisionChanged(str(plan.target)) from exc
            if current_revision != plan.observed_revision:
                raise TemplateSaveRevisionChanged(str(plan.target))

        self._save_batch(
            TemplateSaveItem(plan.context.session.draft, plan.target)
            for plan in selected
        )

        updated_contexts: list[TemplateDraftContext] = []
        for plan in selected:
            plan.context.session.accept_saved(source_path=plan.target)
            updated_contexts.append(
                self._store.rekey(
                    plan.context,
                    mode_id=plan.context.mode_id,
                    template_id=plan.template_id,
                    path=str(plan.target),
                    source=plan.source,
                    source_type=plan.source_type,
                )
            )
        return tuple(updated_contexts)


__all__ = [
    "OVERWRITE_EXISTING_TARGET",
    "OVERWRITE_EXTERNAL_CHANGE",
    "PreparedTemplateSave",
    "TemplateDraftSaveCoordinator",
    "TemplateSavePreparationCancelled",
    "TemplateSaveRevisionChanged",
]
