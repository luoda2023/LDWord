"""Shared helpers for miniature typography previews."""

from __future__ import annotations

from src.config.style_semantics import resolve_style_size_pt
from src.qt_api import Qt
from src.shared.engine.indent_ops import resolve_style_config_indents


def preview_alignment_flags(alignment: str | None):
    raw = str(alignment or "left").strip().lower()
    if raw == "center":
        return Qt.AlignHCenter | Qt.AlignVCenter
    if raw == "right":
        return Qt.AlignRight | Qt.AlignVCenter
    if raw == "justify":
        return Qt.AlignJustify | Qt.AlignVCenter
    return Qt.AlignLeft | Qt.AlignVCenter


def resolve_preview_size_pt(style_config, *, default: float = 12.0) -> float:
    size_pt = resolve_style_size_pt(style_config, default=default)
    return float(size_pt if size_pt is not None else default)


def resolve_preview_indents_pt(style_config, *, size_pt: float | None = None) -> dict[str, float]:
    resolved = resolve_style_config_indents(style_config, size_pt=size_pt)
    return {
        "size_pt": float(resolved["size_pt"]),
        "left_pt": float(resolved["effective_left_pt"]),
        "right_pt": float(resolved["right_pt"]),
        "first_pt": float(resolved["first_pt"]),
        "hanging_pt": float(resolved["hanging_pt"]),
    }


__all__ = [
    "preview_alignment_flags",
    "resolve_preview_indents_pt",
    "resolve_preview_size_pt",
]
