# -*- coding: utf-8 -*-
"""Single source of truth for cross-pane status toasts.

The left workbench editor (QWidget / QSS) and the right embedded MarkText
editor (QWebEngine / HTML) both surface transient undo-baseline toasts —
chapter-switch history reset, autosave, export, save-as-new.  Keeping the
``(text, kind)`` pair for each shared event in this one module stops the two
panes drifting apart: each side reads the same text and the same semantic
``kind`` (``''`` / ``success`` / ``warning`` / ``error``) and resolves that
kind against the same active theme for its colour.
"""

from __future__ import annotations

# key -> (text, kind).  kind is one of '', 'success', 'warning' or 'error'.
_STATUS_TOAST_MESSAGES: dict[str, tuple[str, str]] = {
    "chapter_reset": ("已切换章节，撤销历史已重置", "warning"),
    "saved_kept": ("已保存，仍可撤销", "success"),
    "saved_cleared": ("已保存，撤销历史已清空", "warning"),
    "exported_kept": ("已导出，仍可撤销", "success"),
    "exported_cleared": ("已导出，撤销历史已清空", "warning"),
    "saved_new_kept": ("已保存为新文档，仍可撤销", "success"),
}


def status_toast(key: str) -> tuple[str, str]:
    """Return the shared ``(text, kind)`` for *key* (``("", "")`` if unknown)."""
    return _STATUS_TOAST_MESSAGES.get(str(key), ("", ""))


def status_toast_text(key: str) -> str:
    """Return the shared toast text for *key*."""
    return _STATUS_TOAST_MESSAGES.get(str(key), ("", ""))[0]


def status_toast_kind(key: str) -> str:
    """Return the shared toast kind for *key*."""
    return _STATUS_TOAST_MESSAGES.get(str(key), ("", ""))[1]


def status_toast_payload() -> dict[str, object]:
    """Return a JSON-serialisable payload for the embedded MarkText page.

    Kept in sync with :data:`_STATUS_TOAST_MESSAGES` so the right pane's
    inline JS reads the very same (text, kind) pairs the Python side uses.
    """
    return {
        key: {"text": text, "kind": kind, "ms": 2200}
        for key, (text, kind) in _STATUS_TOAST_MESSAGES.items()
    }
