"""Reusable local-path acquisition for browse and drag/drop Qt surfaces."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal

from src.qt_api import QEvent, QObject, Signal


PathKind = Literal["file", "directory", "either"]
PathCardinality = Literal["single", "multiple"]


def _normalized_suffixes(values: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in tuple(values or ()):
        suffix = str(value or "").strip().casefold()
        if not suffix:
            continue
        candidate = suffix if suffix.startswith(".") else f".{suffix}"
        if candidate not in normalized:
            normalized.append(candidate)
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class PathAcceptancePolicy:
    """One source for dialog filtering and pre-intake drag acceptance."""

    path_kind: PathKind = "file"
    suffixes: tuple[str, ...] = ()
    cardinality: PathCardinality = "single"
    max_paths: int | None = None
    require_exists: bool = True
    dialog_label: str = "支持的文件"
    include_all_files: bool = True

    def __post_init__(self) -> None:
        if self.path_kind not in {"file", "directory", "either"}:
            raise ValueError(f"unsupported path_kind: {self.path_kind}")
        if self.cardinality not in {"single", "multiple"}:
            raise ValueError(f"unsupported cardinality: {self.cardinality}")
        if self.max_paths is not None and int(self.max_paths) < 1:
            raise ValueError("max_paths must be positive")
        object.__setattr__(self, "suffixes", _normalized_suffixes(self.suffixes))
        object.__setattr__(
            self,
            "dialog_label",
            str(self.dialog_label or "支持的文件").strip(),
        )

    @property
    def dialog_filter(self) -> str:
        if self.path_kind == "directory":
            return ""
        filters: list[str] = []
        if self.suffixes:
            patterns = " ".join(f"*{suffix}" for suffix in self.suffixes)
            filters.append(f"{self.dialog_label} ({patterns})")
        if self.include_all_files or not filters:
            filters.append("所有文件 (*)")
        return ";;".join(filters)


class PathRejectionCode(str, Enum):
    NO_URLS = "no_urls"
    NON_LOCAL_URL = "non_local_url"
    EMPTY_PATH = "empty_path"
    DUPLICATE_PATH = "duplicate_path"
    WRONG_CARDINALITY = "wrong_cardinality"
    TOO_MANY_PATHS = "too_many_paths"
    SOURCE_MISSING = "source_missing"
    SOURCE_NOT_FILE = "source_not_file"
    SOURCE_NOT_DIRECTORY = "source_not_directory"
    SUFFIX_NOT_ALLOWED = "suffix_not_allowed"


@dataclass(frozen=True, slots=True)
class PathProposalResult:
    paths: tuple[str, ...] = ()
    rejection_code: PathRejectionCode | None = None
    detail: str = ""

    @property
    def accepted(self) -> bool:
        return self.rejection_code is None and bool(self.paths)

    @classmethod
    def rejected(
        cls,
        code: PathRejectionCode,
        detail: object = "",
    ) -> "PathProposalResult":
        return cls(rejection_code=code, detail=str(detail or ""))


def local_path_proposal(mime) -> PathProposalResult:
    """Extract local URLs and retain the exact reason a proposal is rejected."""

    if mime is None or not getattr(mime, "hasUrls", lambda: False)():
        return PathProposalResult.rejected(PathRejectionCode.NO_URLS)
    paths: list[str] = []
    seen: set[str] = set()
    for url in tuple(mime.urls() or ()):
        if not getattr(url, "isLocalFile", lambda: False)():
            return PathProposalResult.rejected(PathRejectionCode.NON_LOCAL_URL)
        raw = str(url.toLocalFile() or "").strip()
        if not raw:
            return PathProposalResult.rejected(PathRejectionCode.EMPTY_PATH)
        candidate = Path(raw).expanduser()
        try:
            normalized = str(candidate.resolve()) if candidate.exists() else str(candidate)
        except OSError:
            normalized = str(candidate)
        identity = normalized.casefold()
        if identity in seen:
            return PathProposalResult.rejected(
                PathRejectionCode.DUPLICATE_PATH,
                normalized,
            )
        seen.add(identity)
        paths.append(normalized)
    if not paths:
        return PathProposalResult.rejected(PathRejectionCode.NO_URLS)
    return PathProposalResult(paths=tuple(paths))


def evaluate_paths(
    paths: Iterable[str],
    policy: PathAcceptancePolicy,
) -> PathProposalResult:
    """Evaluate normalized paths against one domain-owned acceptance policy."""

    candidates = tuple(str(path or "").strip() for path in paths)
    if not candidates or any(not path for path in candidates):
        return PathProposalResult.rejected(PathRejectionCode.EMPTY_PATH)
    if policy.cardinality == "single" and len(candidates) != 1:
        return PathProposalResult.rejected(
            PathRejectionCode.WRONG_CARDINALITY,
            len(candidates),
        )
    if policy.max_paths is not None and len(candidates) > int(policy.max_paths):
        return PathProposalResult.rejected(
            PathRejectionCode.TOO_MANY_PATHS,
            len(candidates),
        )
    for raw in candidates:
        path = Path(raw)
        if policy.require_exists and not path.exists():
            return PathProposalResult.rejected(
                PathRejectionCode.SOURCE_MISSING,
                raw,
            )
        if policy.path_kind == "file" and not path.is_file():
            return PathProposalResult.rejected(
                PathRejectionCode.SOURCE_NOT_FILE,
                raw,
            )
        if policy.path_kind == "directory" and not path.is_dir():
            return PathProposalResult.rejected(
                PathRejectionCode.SOURCE_NOT_DIRECTORY,
                raw,
            )
        if (
            policy.suffixes
            and path.is_file()
            and path.suffix.casefold() not in policy.suffixes
        ):
            return PathProposalResult.rejected(
                PathRejectionCode.SUFFIX_NOT_ALLOWED,
                path.suffix.casefold(),
            )
    return PathProposalResult(paths=candidates)


def evaluate_drop_mime(
    mime,
    policy: PathAcceptancePolicy,
) -> PathProposalResult:
    proposal = local_path_proposal(mime)
    return evaluate_paths(proposal.paths, policy) if proposal.accepted else proposal


def local_paths_from_mime(mime) -> tuple[str, ...]:
    """Compatibility projection for callers that only need accepted local URLs."""

    proposal = local_path_proposal(mime)
    return proposal.paths if proposal.accepted else ()


def accepted_drop_paths(
    mime,
    policy: PathAcceptancePolicy,
) -> tuple[str, ...]:
    """Compatibility projection for callers that only need accepted paths."""

    proposal = evaluate_drop_mime(mime, policy)
    return proposal.paths if proposal.accepted else ()


class PathDropController(QObject):
    """Install one path policy across complete, dynamically changing surfaces."""

    paths_dropped = Signal(object)
    proposal_rejected = Signal(object)
    hover_changed = Signal(bool)

    def __init__(
        self,
        policy: PathAcceptancePolicy | None = None,
        *,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._policy = policy or PathAcceptancePolicy()
        self._targets: list[object] = []
        self._hovering = False
        self._last_rejection: tuple[object, str] | None = None

    @property
    def policy(self) -> PathAcceptancePolicy:
        return self._policy

    @property
    def spec(self) -> PathAcceptancePolicy:
        """Compatibility alias for the former drop-only contract name."""

        return self._policy

    def set_policy(self, policy: PathAcceptancePolicy) -> None:
        self._policy = policy
        self._last_rejection = None
        self._set_hovering(False)

    def set_spec(self, policy: PathAcceptancePolicy) -> None:
        self.set_policy(policy)

    def install_on_surface(self, *surfaces) -> None:
        """Cover every current and future descendant of each surface."""

        for surface in surfaces:
            self._install_tree(surface)

    def _install_tree(self, target) -> None:
        if target is None:
            return
        self._install_target(target)
        for child in tuple(getattr(target, "children", lambda: ())() or ()):
            self._install_tree(child)

    def _install_target(self, target) -> None:
        if target is None or target is self or target in self._targets:
            return
        set_accept_drops = getattr(target, "setAcceptDrops", None)
        # Layouts, theme subscriptions, and other QObject helpers can appear
        # below a composite drop surface. They never receive drag/drop input;
        # installing this controller on them can also interfere with event
        # filters those helpers install while handling ChildAdded. Limit the
        # drop tree to actual QWidget-like targets.
        if not callable(set_accept_drops):
            return
        set_accept_drops(True)
        target.installEventFilter(self)
        self._targets.append(target)

    def accepts_path(self, path: str) -> bool:
        return evaluate_paths((path,), self._policy).accepted

    def proposal(self, mime) -> PathProposalResult:
        return evaluate_drop_mime(mime, self._policy)

    def accepted_paths(self, mime) -> tuple[str, ...]:
        proposal = self.proposal(mime)
        return proposal.paths if proposal.accepted else ()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API
        try:
            event_type = event.type()
        except RuntimeError:
            return False
        if event_type == QEvent.ChildAdded:
            child = getattr(event, "child", lambda: None)()
            self._install_tree(child)
            return super().eventFilter(watched, event)
        if event_type in {QEvent.DragEnter, QEvent.DragMove}:
            proposal = self.proposal(event.mimeData())
            if proposal.rejection_code is PathRejectionCode.NO_URLS:
                self._last_rejection = None
                self._set_hovering(False)
                return super().eventFilter(watched, event)
            if proposal.accepted:
                event.acceptProposedAction()
                self._last_rejection = None
            else:
                event.ignore()
                signature = (proposal.rejection_code, proposal.detail)
                if signature != self._last_rejection:
                    self._last_rejection = signature
                    self.proposal_rejected.emit(proposal)
            self._set_hovering(proposal.accepted)
            return True
        if event_type == QEvent.DragLeave:
            if not self._hovering and self._last_rejection is None:
                return super().eventFilter(watched, event)
            self._last_rejection = None
            self._set_hovering(False)
            event.accept()
            return True
        if event_type == QEvent.Drop:
            proposal = self.proposal(event.mimeData())
            if proposal.rejection_code is PathRejectionCode.NO_URLS:
                self._last_rejection = None
                self._set_hovering(False)
                return super().eventFilter(watched, event)
            self._last_rejection = None
            self._set_hovering(False)
            if proposal.accepted:
                self.paths_dropped.emit(proposal.paths)
                event.acceptProposedAction()
            else:
                self.proposal_rejected.emit(proposal)
                event.ignore()
            return True
        return super().eventFilter(watched, event)

    def _set_hovering(self, hovering: bool) -> None:
        resolved = bool(hovering)
        if resolved == self._hovering:
            return
        self._hovering = resolved
        self.hover_changed.emit(resolved)


def attach_path_drop(
    *,
    parent,
    surface,
    policy: PathAcceptancePolicy,
    on_paths: Callable[[tuple[str, ...]], object],
    on_rejected: Callable[[PathProposalResult], object] | None = None,
) -> PathDropController:
    """Create a controller that owns one complete composite drop surface."""

    controller = PathDropController(policy, parent=parent)
    controller.paths_dropped.connect(on_paths)
    if on_rejected is not None:
        controller.proposal_rejected.connect(on_rejected)
    controller.install_on_surface(surface)
    return controller


# Compatibility name retained for packages that imported the first revision.
PathDropSpec = PathAcceptancePolicy


__all__ = [
    "PathAcceptancePolicy",
    "PathDropController",
    "PathDropSpec",
    "PathProposalResult",
    "PathRejectionCode",
    "accepted_drop_paths",
    "attach_path_drop",
    "evaluate_drop_mime",
    "evaluate_paths",
    "local_path_proposal",
    "local_paths_from_mime",
]
