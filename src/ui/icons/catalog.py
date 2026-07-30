"""Compatibility exports for the canonical shared icon catalog.

New code must import from :mod:`src.shared.ui.icons.catalog`.
"""

from src.shared.ui.icons.catalog import (
    get_app_logo,
    get_icon,
    get_icon_names,
    invalidate_icon_cache,
    is_icon_registered,
)

__all__ = [
    "get_app_logo",
    "get_icon",
    "get_icon_names",
    "invalidate_icon_cache",
    "is_icon_registered",
]
