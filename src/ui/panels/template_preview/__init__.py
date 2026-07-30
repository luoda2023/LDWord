"""Public template preview projection and widget API."""

from .model import (
    PreviewBlockKind,
    PreviewTableStyle,
    PreviewTextStyle,
    TemplatePreviewBlock,
    TemplatePreviewMode,
    TemplatePreviewProjection,
)


def build_template_preview_projection(*args, **kwargs):
    from .projector import build_template_preview_projection as build

    return build(*args, **kwargs)

__all__ = [
    "PreviewBlockKind",
    "PreviewTableStyle",
    "PreviewTextStyle",
    "TemplatePreviewBlock",
    "TemplatePreviewMode",
    "TemplatePreviewProjection",
    "build_template_preview_projection",
]
