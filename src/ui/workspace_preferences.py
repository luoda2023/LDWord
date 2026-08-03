"""Versioned persistence for durable workspace choices.

The store deliberately excludes task inputs and execution feedback.  It owns
only choices that a user reasonably expects to survive an application restart:
the active work mode, the current plan/template identities, Workbench feature
switches, the selected material package, and the output-location preference.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from src.app_paths import app_data_root
from src.config.atomic_io import atomic_write_text
from src.config.work_mode import default_work_mode, get_work_mode


logger = logging.getLogger(__name__)

WORKSPACE_PREFERENCES_SCHEMA = "workspace-preferences-v1"
_OUTPUT_MODES = {"default", "custom"}


def workspace_preferences_path() -> Path:
    return app_data_root() / "workspace-preferences.json"


@dataclass(frozen=True, slots=True)
class ModeWorkspacePreferences:
    scene_id: str = ""
    template_id: str = ""
    template_path: str = ""
    template_source: str = ""
    template_source_type: str = ""
    execution_template_id: str = ""
    plan_enabled: bool = True
    template_enabled: bool = True
    material_enabled: bool = False
    material_package_id: str = ""
    official_document_type_id: str = "notice"
    output_mode: str = "default"
    custom_output_dir: str = ""


@dataclass(frozen=True, slots=True)
class WorkspacePreferences:
    active_mode_id: str = field(default_factory=lambda: default_work_mode().mode_id)
    modes: dict[str, ModeWorkspacePreferences] = field(default_factory=dict)

    def for_mode(self, mode_id: str) -> ModeWorkspacePreferences | None:
        return self.modes.get(str(mode_id or "").strip())


class WorkspacePreferenceStore:
    """Atomic, fail-safe owner of the durable workspace preference file."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else workspace_preferences_path()
        self._cached: WorkspacePreferences | None = None

    def load(self, *, refresh: bool = False) -> WorkspacePreferences:
        if self._cached is not None and not refresh:
            return self._cached
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            state = _preferences_from_payload(payload)
        except FileNotFoundError:
            state = WorkspacePreferences()
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning(
                "Ignoring unavailable workspace preferences at %s: %s",
                self.path,
                exc,
            )
            state = WorkspacePreferences()
        self._cached = state
        return state

    def update_active_mode(self, mode_id: str) -> WorkspacePreferences:
        normalized = _known_mode_id(mode_id)
        current = self.load()
        if current.active_mode_id == normalized:
            return current
        return self.save(replace(current, active_mode_id=normalized))

    def update_mode(
        self,
        mode_id: str,
        **changes: object,
    ) -> WorkspacePreferences:
        normalized_mode = _known_mode_id(mode_id)
        current = self.load()
        before = current.for_mode(normalized_mode) or ModeWorkspacePreferences()
        allowed = set(ModeWorkspacePreferences.__dataclass_fields__)
        unknown = set(changes) - allowed
        if unknown:
            raise TypeError(
                "Unknown workspace preference fields: " + ", ".join(sorted(unknown))
            )
        after = replace(before, **changes)
        if after == before and normalized_mode in current.modes:
            return current
        modes = dict(current.modes)
        modes[normalized_mode] = after
        return self.save(replace(current, modes=modes))

    def save(self, state: WorkspacePreferences) -> WorkspacePreferences:
        if not isinstance(state, WorkspacePreferences):
            raise TypeError("state must be WorkspacePreferences")
        payload = {
            "schema_version": WORKSPACE_PREFERENCES_SCHEMA,
            "active_mode_id": _known_mode_id(state.active_mode_id),
            "modes": {
                mode_id: asdict(preferences)
                for mode_id, preferences in sorted(state.modes.items())
                if get_work_mode(mode_id) is not None
            },
        }
        atomic_write_text(
            self.path,
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self._cached = _preferences_from_payload(payload)
        return self._cached


def _preferences_from_payload(payload: object) -> WorkspacePreferences:
    if not isinstance(payload, dict):
        raise ValueError("Workspace preferences must be an object")
    if payload.get("schema_version") != WORKSPACE_PREFERENCES_SCHEMA:
        raise ValueError("Unsupported workspace preferences schema")

    active_mode_id = _known_mode_id(payload.get("active_mode_id"))
    raw_modes = payload.get("modes")
    if not isinstance(raw_modes, dict):
        raise ValueError("Workspace preferences modes must be an object")

    modes: dict[str, ModeWorkspacePreferences] = {}
    for raw_mode_id, raw_preference in raw_modes.items():
        mode_id = str(raw_mode_id or "").strip()
        if get_work_mode(mode_id) is None or not isinstance(raw_preference, dict):
            continue
        modes[mode_id] = _mode_preferences_from_payload(raw_preference)
    return WorkspacePreferences(active_mode_id=active_mode_id, modes=modes)


def _mode_preferences_from_payload(
    payload: dict[object, object],
) -> ModeWorkspacePreferences:
    output_mode = _text(payload.get("output_mode"), max_length=16)
    if output_mode not in _OUTPUT_MODES:
        output_mode = "default"
    custom_output_dir = _text(payload.get("custom_output_dir"), max_length=32768)
    if output_mode != "custom" or not custom_output_dir:
        output_mode = "default"
        custom_output_dir = ""
    return ModeWorkspacePreferences(
        scene_id=_text(payload.get("scene_id")),
        template_id=_text(payload.get("template_id")),
        template_path=_text(payload.get("template_path"), max_length=32768),
        template_source=_text(payload.get("template_source"), max_length=64),
        template_source_type=_text(payload.get("template_source_type"), max_length=64),
        execution_template_id=_text(payload.get("execution_template_id")),
        plan_enabled=_boolean(payload.get("plan_enabled"), True),
        template_enabled=_boolean(payload.get("template_enabled"), True),
        material_enabled=_boolean(payload.get("material_enabled"), False),
        material_package_id=_text(payload.get("material_package_id")),
        official_document_type_id=(
            _text(payload.get("official_document_type_id")) or "notice"
        ),
        output_mode=output_mode,
        custom_output_dir=custom_output_dir,
    )


def _known_mode_id(value: object) -> str:
    normalized = _text(value, max_length=128)
    if get_work_mode(normalized) is not None:
        return normalized
    return default_work_mode().mode_id


def _text(value: object, *, max_length: int = 1024) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


def _boolean(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else bool(default)


__all__ = [
    "ModeWorkspacePreferences",
    "WORKSPACE_PREFERENCES_SCHEMA",
    "WorkspacePreferenceStore",
    "WorkspacePreferences",
    "workspace_preferences_path",
]
