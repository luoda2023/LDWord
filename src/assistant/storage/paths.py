"""Assistant storage paths that never depend on the project checkout."""

from __future__ import annotations

import os
from pathlib import Path

from src.app_meta import APP_DATA_DIR_NAME, APP_HOME_DIR_NAME


ASSISTANT_HOME_ENV = "LDWORD_FORM_ASSISTANT_HOME"


def assistant_storage_root(*, env: dict[str, str] | None = None) -> Path:
    values = os.environ if env is None else env
    explicit = str(values.get(ASSISTANT_HOME_ENV, "") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    local_app_data = str(values.get("LOCALAPPDATA", "") or "").strip()
    if local_app_data:
        return Path(local_app_data) / APP_DATA_DIR_NAME / "assistant"
    return Path.home() / APP_HOME_DIR_NAME / "assistant"


__all__ = ["ASSISTANT_HOME_ENV", "assistant_storage_root"]
