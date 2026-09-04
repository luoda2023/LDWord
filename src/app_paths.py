"""Writable application paths independent of the install directory."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from src.app_meta import APP_DATA_DIR_NAME, APP_HOME_DIR_NAME


APP_HOME_ENV = "ALAVETTE_FORM_HOME"


def default_app_data_root(*, env: Mapping[str, str] | None = None) -> Path:
    """Return the normal per-user data root, ignoring developer overrides."""

    values = os.environ if env is None else env
    local_app_data = str(values.get("LOCALAPPDATA", "") or "").strip()
    if local_app_data:
        return Path(local_app_data) / APP_DATA_DIR_NAME
    return Path.home() / APP_HOME_DIR_NAME


def app_data_root(*, env: Mapping[str, str] | None = None) -> Path:
    values = os.environ if env is None else env
    explicit = str(values.get(APP_HOME_ENV, "") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return default_app_data_root(env=values)


def config_library_data_root(*, env: Mapping[str, str] | None = None) -> Path:
    return app_data_root(env=env) / "config_library"


def header_footer_preset_data_root(
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    return app_data_root(env=env) / "header_footer_presets"


def heading_numbering_scheme_data_root(
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    return app_data_root(env=env) / "heading_numbering_schemes"


def master_library_data_root(*, env: Mapping[str, str] | None = None) -> Path:
    return config_library_data_root(env=env) / "masters"


def log_data_root(*, env: Mapping[str, str] | None = None) -> Path:
    return app_data_root(env=env) / "logs"


__all__ = [
    "APP_HOME_ENV",
    "app_data_root",
    "config_library_data_root",
    "default_app_data_root",
    "header_footer_preset_data_root",
    "heading_numbering_scheme_data_root",
    "log_data_root",
    "master_library_data_root",
]
