"""Compatibility import path for the shared DOCX fragment renderer."""

from src.shared.engine.docx_renderer import (
    ContentDocxRenderer,
    ContentImageJobDraft,
    ContentOccurrenceReceipt,
    ContentRenderBlockedError,
    ContentRenderDiagnostic,
    ContentRenderPreflight,
    ContentRenderReceipt,
    ContentRenderSeverity,
    render_document_fragment,
)

__all__ = [
    "ContentDocxRenderer",
    "ContentImageJobDraft",
    "ContentOccurrenceReceipt",
    "ContentRenderBlockedError",
    "ContentRenderDiagnostic",
    "ContentRenderPreflight",
    "ContentRenderReceipt",
    "ContentRenderSeverity",
    "render_document_fragment",
]
