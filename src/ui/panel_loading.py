"""Shared lifecycle state for lazily constructed top-level panels."""

from __future__ import annotations

from enum import Enum


class PanelLoadState(str, Enum):
    """Observable lifecycle of a first-level application panel."""

    UNLOADED = "unloaded"
    SCHEDULED = "scheduled"
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"
