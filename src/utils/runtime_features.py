"""Runtime feature flags used by packaged environments."""

from __future__ import annotations

import os


def _env_flag(name: str) -> bool:
    value = os.environ.get(name, "")
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def is_macos_packaged_runtime() -> bool:
    """Return True only for the dedicated macOS packaged launcher runtime."""
    return _env_flag("DOCX_MACOS_BUNDLE")


def word_page_scope_forced_disabled() -> bool:
    """Return True when runtime forbids Word-based real page probing."""
    return _env_flag("DOCX_DISABLE_WORD_PAGE_SCOPE")


def mathtype_office_fallback_forced_disabled() -> bool:
    """Return True when runtime forbids MathType Office fallback."""
    return _env_flag("DOCX_DISABLE_MATHTYPE_OFFICE_FALLBACK")
