from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from .diagnostics import log_path_fallback_failure

if TYPE_CHECKING:
    from .quick_execution_detail import QuickExecutionDetail


class WorkbenchDocumentPathController:
    """Keep document selection, cached paths, and execution fallback in sync."""

    def __init__(
        self,
        quick_execution_detail: "QuickExecutionDetail",
        *,
        pick_document_path: Callable[[], str | None],
    ) -> None:
        self._quick_execution_detail = quick_execution_detail
        self._pick_document_path = pick_document_path
        self._cached_document_path = ""

    @property
    def cached_document_path(self) -> str:
        return self._cached_document_path

    def has_selected_document(self) -> bool:
        return any(
            self._normalize_existing_path(candidate)
            for candidate in (
                self._quick_execution_detail.document_path(),
                self._cached_document_path,
            )
        )

    def selected_existing_document(self) -> str | None:
        for candidate in (
            self._quick_execution_detail.document_path(),
            self._cached_document_path,
        ):
            normalized = self._normalize_existing_path(candidate)
            if normalized:
                return self._cache_and_sync(normalized)
        return None

    def accept_detail_selection(self, file_path: str) -> str | None:
        normalized = self._normalize_any_path(file_path)
        if not normalized:
            return None
        return self._cache_and_sync(normalized)

    def clear_selection(self) -> None:
        self._cached_document_path = ""
        self._sync_detail_path("")

    def apply_loaded_document(self, file_path: str) -> str | None:
        normalized = self._normalize_existing_path(file_path)
        if not normalized:
            return None
        return self._cache_and_sync(normalized)

    def resolve_execution_document(self) -> str | None:
        for candidate in (
            self._quick_execution_detail.document_path(),
            self._cached_document_path,
        ):
            normalized = self._normalize_existing_path(candidate)
            if normalized:
                return self._cache_and_sync(normalized)

        picked = self._normalize_any_path(self._pick_document_path())
        if not picked:
            return None
        return self._cache_and_sync(picked)

    def _cache_and_sync(self, file_path: str) -> str:
        self._cached_document_path = file_path
        self._sync_detail_path(file_path)
        return file_path

    def _sync_detail_path(self, file_path: str) -> None:
        if self._quick_execution_detail.document_path() == file_path:
            return
        self._quick_execution_detail.set_document_path(file_path)

    @staticmethod
    def _coerce_candidate_path(file_path: str | None) -> tuple[str | None, Path | None]:
        cleaned = str(file_path or "").strip()
        if not cleaned:
            return None, None
        try:
            return cleaned, Path(cleaned).expanduser()
        except Exception as exc:
            log_path_fallback_failure("document path controller", "expanduser", cleaned, exc)
            return cleaned, None

    @classmethod
    def _normalize_any_path(cls, file_path: str | None) -> str | None:
        cleaned, candidate = cls._coerce_candidate_path(file_path)
        if not cleaned:
            return None
        if candidate is None:
            return cleaned
        try:
            exists = candidate.exists()
        except Exception as exc:
            log_path_fallback_failure("document path controller", "exists probe", cleaned, exc)
            return str(candidate)
        if exists:
            try:
                return str(candidate.resolve())
            except Exception as exc:
                log_path_fallback_failure("document path controller", "resolve", cleaned, exc)
                return str(candidate)
        return str(candidate)

    @classmethod
    def _normalize_existing_path(cls, file_path: str | None) -> str | None:
        cleaned, candidate = cls._coerce_candidate_path(file_path)
        if not cleaned or candidate is None:
            return None
        try:
            if not candidate.exists():
                return None
        except Exception as exc:
            log_path_fallback_failure("document path controller", "existing-path check", cleaned, exc)
            return None
        try:
            return str(candidate.resolve())
        except Exception as exc:
            log_path_fallback_failure("document path controller", "resolve", cleaned, exc)
            return str(candidate)


__all__ = ["WorkbenchDocumentPathController"]
