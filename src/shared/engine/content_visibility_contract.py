"""Dependency-free grammar shared by content-visibility scanners and planners."""

from __future__ import annotations

import re


CONTENT_VISIBILITY_MARKER_RE = re.compile(
    r"\{\{\s*([#/])\s*(?:visibility|content)\s*:\s*([A-Za-z0-9_.-]+)\s*\}\}"
)


__all__ = ["CONTENT_VISIBILITY_MARKER_RE"]
