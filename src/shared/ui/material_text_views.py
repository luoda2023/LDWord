"""Semantic projected-text controls for values, filenames, and paths."""

from __future__ import annotations

from src.shared.ui.projected_text_edit import (
    EditActivation,
    ProjectedTextEdit,
    TextSurface,
)
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.text_projection import TextElideMode


class ElidedValueEdit(ProjectedTextEdit):
    """Direct-edit value that elides only while it is not being edited."""

    def __init__(self, text: object = "", parent=None) -> None:
        super().__init__(
            text,
            parent,
            editable=True,
            activation=EditActivation.DIRECT_EDIT,
            surface=TextSurface.FRAMED,
            elide_mode=TextElideMode.RIGHT,
        )
        apply_size_class(self, "md")


class ElidedReadOnlyValue(ProjectedTextEdit):
    """Copyable read-only value with right-side elision."""

    def __init__(self, text: object = "", parent=None) -> None:
        super().__init__(
            text,
            parent,
            editable=False,
            activation=EditActivation.COPY_ONLY,
            surface=TextSurface.FRAMED,
            elide_mode=TextElideMode.RIGHT,
        )
        apply_size_class(self, "md")


class ElidedPathEdit(ProjectedTextEdit):
    """Copyable read-only path preserving both root and basename."""

    def __init__(self, text: object = "", parent=None) -> None:
        super().__init__(
            text,
            parent,
            editable=False,
            activation=EditActivation.COPY_ONLY,
            surface=TextSurface.FRAMED,
            elide_mode=TextElideMode.PATH,
        )
        apply_size_class(self, "md")


class ElidedFilenameEdit(ProjectedTextEdit):
    """Copyable read-only filename that preserves its extension."""

    def __init__(self, text: object = "", parent=None) -> None:
        super().__init__(
            text,
            parent,
            editable=False,
            activation=EditActivation.COPY_ONLY,
            surface=TextSurface.FRAMED,
            elide_mode=TextElideMode.FILENAME,
        )
        apply_size_class(self, "md")


__all__ = [
    "ElidedFilenameEdit",
    "ElidedPathEdit",
    "ElidedReadOnlyValue",
    "ElidedValueEdit",
]
