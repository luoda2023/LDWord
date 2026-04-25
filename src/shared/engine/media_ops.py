"""Helpers for detecting media-related paragraph content."""

from __future__ import annotations


def paragraph_has_image(para) -> bool:
    """Return True when the paragraph contains an inline/anchored image."""
    drawing_ns = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
    for elem in para._element.iter():
        if elem.tag.endswith("}drawing") or elem.tag.endswith("}pict"):
            return True
        if elem.tag == f"{{{drawing_ns}}}inline":
            return True
        if elem.tag == f"{{{drawing_ns}}}anchor":
            return True
    return False
