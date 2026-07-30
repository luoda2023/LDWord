"""Transactional edit state for template authoring.

The authoring UI owns a mutable draft.  The bridge and execution surfaces only
receive committed copies after an explicit save (or when a template is loaded).
"""

from __future__ import annotations

import copy
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from src.config.template import TemplateConfig


@dataclass(frozen=True, slots=True)
class TemplateEditSessionState:
    """Recoverable in-memory state for one edit session transaction."""

    committed: TemplateConfig
    draft: TemplateConfig
    source_revision: "TemplateSourceRevision | None"


@dataclass(frozen=True)
class TemplateSourceRevision:
    """Content identity captured when a template source was loaded or saved."""

    path: str
    size: int
    mtime_ns: int
    sha256: str

    @classmethod
    def capture(cls, path: str | Path | None) -> "TemplateSourceRevision | None":
        value = str(path or "").strip()
        if not value:
            return None
        target = Path(value)
        if not target.is_file():
            return None
        try:
            payload = target.read_bytes()
            stat = target.stat()
        except OSError:
            # The file may disappear between is_file(), read_bytes(), and
            # stat() when an editor replaces it.  Do not fail activation; a
            # later clean reload or successful save captures a fresh revision.
            return None
        return cls(
            path=str(target.resolve()),
            size=len(payload),
            mtime_ns=int(stat.st_mtime_ns),
            sha256=hashlib.sha256(payload).hexdigest(),
        )


class TemplateEditSession:
    """Own the committed/draft boundary for one active template."""

    def __init__(self, template: TemplateConfig, *, source_path: str | Path | None = None):
        self._committed: TemplateConfig
        self._draft: TemplateConfig
        self._source_revision: TemplateSourceRevision | None
        self.reset(template, source_path=source_path)

    @property
    def draft(self) -> TemplateConfig:
        return self._draft

    @property
    def source_revision(self) -> TemplateSourceRevision | None:
        return self._source_revision

    def committed_copy(self) -> TemplateConfig:
        return copy.deepcopy(self._committed)

    def reset(
        self,
        template: TemplateConfig,
        *,
        source_path: str | Path | None = None,
    ) -> TemplateConfig:
        self._committed = copy.deepcopy(template)
        self._draft = copy.deepcopy(self._committed)
        self._source_revision = TemplateSourceRevision.capture(source_path)
        return self._draft

    def replace_draft(self, template: TemplateConfig) -> TemplateConfig:
        """Adopt editor output without retaining an unrelated external alias."""

        if template is not self._draft:
            self._draft = copy.deepcopy(template)
        return self._draft

    def is_dirty(self) -> bool:
        return self._draft != self._committed

    def discard(self) -> TemplateConfig:
        self._draft = copy.deepcopy(self._committed)
        return self._draft

    def accept_saved(self, *, source_path: str | Path | None = None) -> TemplateConfig:
        self._committed = copy.deepcopy(self._draft)
        self._source_revision = TemplateSourceRevision.capture(source_path)
        return self.committed_copy()

    def capture_state(self) -> TemplateEditSessionState:
        """Capture both sides of the committed/draft boundary."""

        return TemplateEditSessionState(
            committed=copy.deepcopy(self._committed),
            draft=copy.deepcopy(self._draft),
            source_revision=self._source_revision,
        )

    def restore_state(self, state: TemplateEditSessionState) -> TemplateConfig:
        """Restore a previous state without changing this session's identity."""

        self._committed = copy.deepcopy(state.committed)
        self._draft = copy.deepcopy(state.draft)
        self._source_revision = state.source_revision
        return self._draft


@dataclass(frozen=True, slots=True)
class TemplateDraftIdentity:
    """Stable in-process identity for one editable template resource."""

    mode_id: str
    source_key: str

    @classmethod
    def build(
        cls,
        *,
        mode_id: str,
        template_id: str,
        source_path: str | Path | None,
    ) -> "TemplateDraftIdentity":
        normalized_mode = str(mode_id or "").strip() or "custom"
        normalized_id = str(template_id or "").strip() or "default"
        raw_path = str(source_path or "").strip()
        if raw_path:
            try:
                normalized_path = str(Path(raw_path).resolve(strict=False))
            except (OSError, RuntimeError):
                normalized_path = str(Path(raw_path).absolute())
            if os.name == "nt":
                normalized_path = normalized_path.casefold()
            source_key = f"path:{normalized_path}"
        else:
            source_key = f"id:{normalized_id}"
        return cls(normalized_mode, source_key)


class TemplateDraftCollisionError(RuntimeError):
    """Raised when rekeying would hide another cached edit context."""

    def __init__(
        self,
        *,
        template_id: str,
        path: str | Path | None,
    ) -> None:
        self.template_id = str(template_id or "").strip()
        self.path = str(path or "").strip()
        target = self.path or self.template_id or "unknown template"
        super().__init__(f"保存目标已有另一个编辑上下文: {target}")


@dataclass(slots=True)
class TemplateDraftContext:
    """One cached authoring draft together with its persistence metadata."""

    identity: TemplateDraftIdentity
    session: TemplateEditSession
    template_id: str
    path: str
    source: str
    source_type: str

    @property
    def mode_id(self) -> str:
        return self.identity.mode_id


@dataclass(frozen=True, slots=True)
class TemplateDraftContextState:
    """One context entry inside a recoverable draft-store snapshot."""

    context: TemplateDraftContext
    identity: TemplateDraftIdentity
    template_id: str
    path: str
    source: str
    source_type: str
    session: TemplateEditSessionState


@dataclass(frozen=True, slots=True)
class TemplateDraftStoreState:
    """Recoverable snapshot that preserves existing context object identities."""

    contexts: tuple[TemplateDraftContextState, ...]


class TemplateDraftStore:
    """Retain independent in-memory drafts while users navigate between templates."""

    def __init__(self) -> None:
        self._contexts: dict[TemplateDraftIdentity, TemplateDraftContext] = {}

    def activate(
        self,
        template: TemplateConfig,
        *,
        mode_id: str,
        template_id: str,
        path: str | Path | None = None,
        source: str = "",
        source_type: str = "",
        replace: bool = False,
    ) -> TemplateDraftContext:
        identity = TemplateDraftIdentity.build(
            mode_id=mode_id,
            template_id=template_id,
            source_path=path,
        )
        context = self._contexts.get(identity)
        if context is None or replace:
            context = TemplateDraftContext(
                identity=identity,
                session=TemplateEditSession(template, source_path=path),
                template_id=str(template_id or "").strip() or "default",
                path=str(path or "").strip(),
                source=str(source or "").strip(),
                source_type=str(source_type or "").strip(),
            )
            self._contexts[identity] = context
            return context

        context.template_id = str(template_id or "").strip() or "default"
        context.path = str(path or "").strip()
        context.source = str(source or "").strip()
        context.source_type = str(source_type or "").strip()
        if not context.session.is_dirty():
            context.session.reset(template, source_path=path)
        return context

    def rekey(
        self,
        context: TemplateDraftContext,
        *,
        mode_id: str,
        template_id: str,
        path: str | Path | None,
        source: str,
        source_type: str,
    ) -> TemplateDraftContext:
        old_identity = context.identity
        new_identity = TemplateDraftIdentity.build(
            mode_id=mode_id,
            template_id=template_id,
            source_path=path,
        )
        existing = self._contexts.get(new_identity)
        if existing is not None and existing is not context:
            raise TemplateDraftCollisionError(
                template_id=template_id,
                path=path,
            )
        if self._contexts.get(old_identity) is context:
            self._contexts.pop(old_identity, None)
        context.identity = new_identity
        context.template_id = str(template_id or "").strip() or "default"
        context.path = str(path or "").strip()
        context.source = str(source or "").strip()
        context.source_type = str(source_type or "").strip()
        self._contexts[new_identity] = context
        return context

    def ensure_rekey_available(
        self,
        context: TemplateDraftContext,
        *,
        mode_id: str,
        template_id: str,
        path: str | Path | None,
    ) -> None:
        """Reject a target identity that already owns another dirty draft."""

        identity = TemplateDraftIdentity.build(
            mode_id=mode_id,
            template_id=template_id,
            source_path=path,
        )
        existing = self._contexts.get(identity)
        if existing is not None and existing is not context:
            raise TemplateDraftCollisionError(
                template_id=template_id,
                path=path,
            )

    def dirty_contexts(self) -> tuple[TemplateDraftContext, ...]:
        return tuple(
            context
            for context in self._contexts.values()
            if context.session.is_dirty()
        )

    def discard_all(self) -> None:
        for context in self.dirty_contexts():
            context.session.discard()

    def capture_state(self) -> TemplateDraftStoreState:
        return TemplateDraftStoreState(
            contexts=tuple(
                TemplateDraftContextState(
                    context=context,
                    identity=context.identity,
                    template_id=context.template_id,
                    path=context.path,
                    source=context.source,
                    source_type=context.source_type,
                    session=context.session.capture_state(),
                )
                for context in self._contexts.values()
            )
        )

    def restore_state(self, state: TemplateDraftStoreState) -> None:
        """Restore entries in place so prepared plans never retain stale owners."""

        restored: dict[TemplateDraftIdentity, TemplateDraftContext] = {}
        for item in state.contexts:
            context = item.context
            context.identity = item.identity
            context.template_id = item.template_id
            context.path = item.path
            context.source = item.source
            context.source_type = item.source_type
            context.session.restore_state(item.session)
            restored[item.identity] = context
        self._contexts = restored

    def remove(self, context: TemplateDraftContext) -> bool:
        """Forget one context after its underlying template is deleted."""

        if self._contexts.get(context.identity) is not context:
            return False
        self._contexts.pop(context.identity, None)
        return True

    def __len__(self) -> int:
        return len(self._contexts)


__all__ = [
    "TemplateDraftContext",
    "TemplateDraftCollisionError",
    "TemplateDraftIdentity",
    "TemplateDraftContextState",
    "TemplateDraftStoreState",
    "TemplateDraftStore",
    "TemplateEditSessionState",
    "TemplateEditSession",
    "TemplateSourceRevision",
]
