"""Stable output-location policy for Assistant document production."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from pathlib import Path

from src.assistant.storage.paths import assistant_storage_root


OUTPUT_FOLDER_NAME = "LDWord-Outputs"
_SETTINGS_FILENAME = "output-location.json"
_SETTINGS_SCHEMA = "assistant-output-location-v1"


def system_documents_directory(
    *,
    env: Mapping[str, str] | None = None,
    windows_resolver: Callable[[], Path | None] | None = None,
) -> Path:
    """Return the OS-owned Documents directory without assuming its location."""

    values = os.environ if env is None else env
    resolver = windows_resolver or _windows_documents_directory
    known = resolver()
    if known is not None and str(known).strip():
        return Path(known).expanduser()

    one_drive = str(values.get("OneDrive", "") or "").strip()
    if one_drive:
        return Path(one_drive).expanduser() / "Documents"
    user_profile = str(values.get("USERPROFILE", "") or "").strip()
    if user_profile:
        return Path(user_profile).expanduser() / "Documents"
    return Path.home() / "Documents"


def default_assistant_output_root(
    input_path: str | Path | None = None,
    *,
    storage_root: str | Path | None = None,
    documents_directory: str | Path | None = None,
) -> Path:
    """Resolve the first-choice output root for one new plan.

    Existing files stay adjacent to their source.  From-scratch authoring uses
    the user's last confirmed location and then the OS Documents known folder.
    """

    source = Path(input_path).expanduser() if input_path else None
    if source is not None:
        return source.parent / OUTPUT_FOLDER_NAME

    remembered = load_last_output_root(storage_root=storage_root)
    if remembered is not None:
        return remembered
    documents = (
        Path(documents_directory).expanduser()
        if documents_directory is not None
        else system_documents_directory()
    )
    return documents / OUTPUT_FOLDER_NAME


def load_last_output_root(
    *,
    storage_root: str | Path | None = None,
) -> Path | None:
    """Load a previously confirmed output folder, ignoring stale settings."""

    path = _settings_path(storage_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get("schema") != _SETTINGS_SCHEMA:
        return None
    raw = str(payload.get("last_output_root") or "").strip()
    if not raw:
        return None
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute() or not candidate.is_dir():
        return None
    return candidate.resolve(strict=False)


def remember_output_root(
    value: str | Path,
    *,
    storage_root: str | Path | None = None,
) -> Path:
    """Persist an explicitly confirmed existing output folder atomically."""

    candidate = Path(value).expanduser()
    if not candidate.is_absolute() or not candidate.is_dir():
        raise ValueError("assistant_output_root_invalid")
    candidate = candidate.resolve(strict=False)
    path = _settings_path(storage_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f".json.{os.getpid()}.tmp")
    payload = {
        "schema": _SETTINGS_SCHEMA,
        "last_output_root": str(candidate),
    }
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
    return candidate


def _settings_path(storage_root: str | Path | None) -> Path:
    root = (
        Path(storage_root).expanduser()
        if storage_root is not None
        else assistant_storage_root()
    )
    return root / _SETTINGS_FILENAME


def _windows_documents_directory() -> Path | None:
    if os.name != "nt":
        return None
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            raw, _value_type = winreg.QueryValueEx(key, "Personal")
    except (ImportError, OSError):
        return None
    expanded = os.path.expandvars(str(raw or "").strip())
    return Path(expanded) if expanded else None


__all__ = [
    "OUTPUT_FOLDER_NAME",
    "default_assistant_output_root",
    "load_last_output_root",
    "remember_output_root",
    "system_documents_directory",
]
