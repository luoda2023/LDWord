"""Compatibility aliases for scene style override toggle controls."""

from __future__ import annotations

from dataclasses import dataclass

from src.shared.ui.style_policy_toggle_list import (
    StylePolicyToggleList,
    StylePolicyToggleOption,
)


@dataclass(frozen=True, slots=True)
class StyleOverrideToggleOption(StylePolicyToggleOption):
    """Backward-compatible option name for scene override callers."""


class StyleOverrideToggleList(StylePolicyToggleList):
    """Backward-compatible list name for scene override callers."""


__all__ = [
    "StyleOverrideToggleList",
    "StyleOverrideToggleOption",
]
