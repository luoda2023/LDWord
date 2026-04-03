"""
custom_themes - persist user-defined color themes.
"""

from __future__ import annotations

import json
import os
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
_LEGACY_CUSTOM_THEMES_FILE = (
    Path(__file__).resolve().parent.parent.parent / "config" / "custom_themes.json"
)


def _normalize_color(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    color = value.strip()
    if not color:
        return None
    if color.startswith("#"):
        return color.upper()
    return color


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


class CustomThemeStore:
    """Manage load/save/add/delete operations for user-defined themes."""

    def __init__(self, path: str | Path | None = None):
        self._entries: list[CustomThemeEntry] = []
        self._path = Path(path).expanduser() if path is not None else _resolve_custom_themes_file()

    @property
    def entries(self) -> list[CustomThemeEntry]:
        return list(self._entries)

    @property
    def path(self) -> Path:
        return self._path

    def _load_path(self) -> Path:
        if self._path.exists():
            return self._path
        if self._path != _LEGACY_CUSTOM_THEMES_FILE and _LEGACY_CUSTOM_THEMES_FILE.exists():
            return _LEGACY_CUSTOM_THEMES_FILE
        return self._path

    def load(self) -> None:
        path = self._load_path()
        if not path.exists():
            self._entries = []
            return

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            self._entries = []
            return

        if not isinstance(data, list):
            self._entries = []
            return

        entries: list[CustomThemeEntry] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            normalized_core = _normalize_core(item.get("core"))
            if normalized_core is None:
                continue
            entries.append(
                CustomThemeEntry(
                    id=str(item.get("id") or str(uuid.uuid4())[:8]),
                    name=str(item.get("name") or "Untitled Theme"),
                    core=normalized_core,
                )
            )
        self._entries = entries

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = [{"id": e.id, "name": e.name, "core": e.core} for e in self._entries]
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, name: str, core: dict[str, str]) -> CustomThemeEntry:
        normalized_core = _normalize_core(core)
        if normalized_core is None:
            raise ValueError("custom theme core is incomplete")

        entry = CustomThemeEntry(
            id=str(uuid.uuid4())[:8],
            name=name,
            core=normalized_core,
        )
        self._entries.append(entry)
        self.save()
        return entry

    def delete(self, theme_id: str) -> bool:
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.id != theme_id]
        if len(self._entries) < before:
            self.save()
            return True
        return False

    def get_by_id(self, theme_id: str) -> CustomThemeEntry | None:
        for e in self._entries:
            if e.id == theme_id:
                return e
        return None
