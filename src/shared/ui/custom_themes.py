"""
custom_themes - persist user-defined color themes.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.app_meta import APP_CUSTOM_THEMES_ENV, APP_DATA_DIR_NAME, APP_HOME_DIR_NAME
from src.shared.ui.theme import AppTheme, derive_theme_from_core


_CUSTOM_THEME_CORE_KEYS = (
    "primary",
    "accent",
    "bg_window",
    "bg_card",
    "bg_sidebar",
    "text_primary",
)
_CUSTOM_THEME_COLOR_PATTERN = re.compile(r"#[0-9A-Fa-f]{6}")


def _normalize_color(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    color = value.strip()
    if _CUSTOM_THEME_COLOR_PATTERN.fullmatch(color) is None:
        return None
    return color.upper()


def _normalize_core(core: Any) -> dict[str, str] | None:
    if not isinstance(core, dict):
        return None

    normalized: dict[str, str] = {}
    for key in _CUSTOM_THEME_CORE_KEYS:
        color = _normalize_color(core.get(key))
        if color is None:
            return None
        normalized[key] = color
    return normalized


def _default_store_dir() -> Path:
    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / APP_DATA_DIR_NAME
    return Path.home() / APP_HOME_DIR_NAME


def _resolve_custom_themes_file() -> Path:
    override = os.getenv(APP_CUSTOM_THEMES_ENV)
    if override:
        return Path(override).expanduser()
    return _default_store_dir() / "custom_themes.json"


@dataclass
class CustomThemeEntry:
    """A single persisted custom theme record."""

    id: str = ""
    name: str = ""
    core: dict[str, str] = field(default_factory=dict)

    def to_app_theme(self) -> AppTheme:
        normalized_core = _normalize_core(self.core)
        if normalized_core is None:
            raise ValueError("custom theme entry is missing required core colors")
        return derive_theme_from_core(**normalized_core)


class CustomThemeStoreError(ValueError):
    """The canonical custom-theme file cannot be used safely."""


class CustomThemeStore:
    """Manage load/save/add/delete operations for user-defined themes."""

    def __init__(self, path: str | Path | None = None):
        self._entries: list[CustomThemeEntry] = []
        self._path = (
            Path(path).expanduser()
            if path is not None
            else _resolve_custom_themes_file()
        )
        self._loaded = False
        self._load_error: CustomThemeStoreError | None = None

    @property
    def entries(self) -> list[CustomThemeEntry]:
        return list(self._entries)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> None:
        if not self._path.exists():
            self._entries = []
            self._loaded = True
            self._load_error = None
            return

        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            entries = self._parse_entries(data)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            error = CustomThemeStoreError(
                f"custom_theme_file_unreadable:{self._path}: {exc}"
            )
            self._loaded = False
            self._load_error = error
            raise error from exc
        except CustomThemeStoreError as exc:
            self._loaded = False
            self._load_error = exc
            raise

        self._entries = entries
        self._loaded = True
        self._load_error = None

    def _parse_entries(self, data: object) -> list[CustomThemeEntry]:
        if not isinstance(data, list):
            raise CustomThemeStoreError(
                f"custom_theme_schema_invalid:{self._path}: root must be an array"
            )

        entries: list[CustomThemeEntry] = []
        seen_ids: set[str] = set()
        for index, item in enumerate(data):
            location = f"$[{index}]"
            if not isinstance(item, dict):
                raise CustomThemeStoreError(
                    f"custom_theme_schema_invalid:{self._path}: {location} must be an object"
                )
            if set(item) != {"id", "name", "core"}:
                raise CustomThemeStoreError(
                    f"custom_theme_schema_invalid:{self._path}: "
                    f"{location} must contain exactly id, name and core"
                )
            theme_id = item.get("id")
            name = item.get("name")
            if not isinstance(theme_id, str) or not theme_id.strip():
                raise CustomThemeStoreError(
                    f"custom_theme_schema_invalid:{self._path}: {location}.id is required"
                )
            if theme_id.strip() in seen_ids:
                raise CustomThemeStoreError(
                    f"custom_theme_schema_invalid:{self._path}: "
                    f"duplicate id {theme_id.strip()!r}"
                )
            if not isinstance(name, str) or not name.strip():
                raise CustomThemeStoreError(
                    f"custom_theme_schema_invalid:{self._path}: {location}.name is required"
                )
            core = item.get("core")
            if not isinstance(core, dict) or set(core) != set(_CUSTOM_THEME_CORE_KEYS):
                raise CustomThemeStoreError(
                    f"custom_theme_schema_invalid:{self._path}: "
                    f"{location}.core must contain exactly the six canonical colors"
                )
            normalized_core = _normalize_core(core)
            if normalized_core is None:
                raise CustomThemeStoreError(
                    f"custom_theme_schema_invalid:{self._path}: "
                    f"{location}.core contains an invalid color"
                )
            normalized_id = theme_id.strip()
            seen_ids.add(normalized_id)
            entries.append(
                CustomThemeEntry(
                    id=normalized_id,
                    name=name.strip(),
                    core=normalized_core,
                )
            )
        return entries

    def save(self) -> None:
        self._ensure_writable()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = [{"id": e.id, "name": e.name, "core": e.core} for e in self._entries]
        temp_path = self._path.with_name(f".{self._path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temp_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temp_path, self._path)
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

    def add(self, name: str, core: dict[str, str]) -> CustomThemeEntry:
        self._ensure_writable()
        if not isinstance(name, str) or not name.strip():
            raise ValueError("custom theme name is required")
        if not isinstance(core, dict) or set(core) != set(_CUSTOM_THEME_CORE_KEYS):
            raise ValueError(
                "custom theme core must contain exactly the canonical colors"
            )
        normalized_core = _normalize_core(core)
        if normalized_core is None:
            raise ValueError("custom theme core is incomplete")

        entry = CustomThemeEntry(
            id=str(uuid.uuid4())[:8],
            name=name.strip(),
            core=normalized_core,
        )
        self._entries.append(entry)
        try:
            self.save()
        except Exception:
            self._entries.pop()
            raise
        return entry

    def delete(self, theme_id: str) -> bool:
        self._ensure_writable()
        previous = self._entries
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.id != theme_id]
        if len(self._entries) < before:
            try:
                self.save()
            except Exception:
                self._entries = previous
                raise
            return True
        return False

    def _ensure_writable(self) -> None:
        if self._load_error is not None:
            raise CustomThemeStoreError(
                f"custom_theme_store_write_blocked:{self._path}: "
                "the canonical file did not load successfully"
            ) from self._load_error
        if self._loaded:
            return
        if self._path.exists():
            self.load()
            return
        self._entries = []
        self._loaded = True

    def get_by_id(self, theme_id: str) -> CustomThemeEntry | None:
        for e in self._entries:
            if e.id == theme_id:
                return e
        return None


__all__ = [
    "CustomThemeEntry",
    "CustomThemeStore",
    "CustomThemeStoreError",
]
