"""Helpers for reading heading-related paragraph semantics from OOXML."""

from __future__ import annotations

from src.shared.engine.ooxml_ops import qn


def get_paragraph_outline_level(para) -> int | None:
    """Return the raw outline level (0-based) when explicitly present."""
    p_pr = para._element.find(qn("w:pPr"))
    if p_pr is None:
        return None
    outline = p_pr.find(qn("w:outlineLvl"))
    if outline is None:
        return None
    raw = (outline.get(qn("w:val")) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
