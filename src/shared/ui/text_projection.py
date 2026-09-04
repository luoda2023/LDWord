"""Canonical-text display projections that never mutate the stored value."""

from __future__ import annotations

from enum import Enum
from pathlib import PurePath

from src.qt_api import QEvent, QLabel, QSize, QSizePolicy, Qt, Signal


# QFontMetrics reports logical-pixel advances, while the final glyph raster is
# snapped to device pixels.  Keeping a tiny logical-pixel inset prevents the
# rightmost glyph from being cut at fractional Windows scale factors.
_TOKEN_PAINT_SAFETY_PX = 2


_COMPOUND_EXTENSIONS = {
    ".tar.bz2",
    ".tar.gz",
    ".tar.xz",
    ".tar.zst",
}


class TextElideMode(str, Enum):
    """Semantic elision modes used by material text surfaces."""

    RIGHT = "right"
    MIDDLE = "middle"
    PATH = "path"
    FILENAME = "filename"


def elide_plain_text(text: object, metrics, width: int) -> str:
    """Right-elide plain text within a pixel width."""

    value = str(text or "")
    available = max(0, int(width))
    if not value or available <= 0:
        return "" if available <= 0 else value
    if metrics.horizontalAdvance(value) <= available:
        return value
    return metrics.elidedText(value, Qt.ElideRight, available)


def elide_middle_text(text: object, metrics, width: int) -> str:
    """Middle-elide paths or identifiers whose beginning and end both matter."""

    value = str(text or "")
    available = max(0, int(width))
    if not value or available <= 0:
        return "" if available <= 0 else value
    if metrics.horizontalAdvance(value) <= available:
        return value
    return metrics.elidedText(value, Qt.ElideMiddle, available)


def elide_filename_text(text: object, metrics, width: int) -> str:
    """Elide a filename while preserving its extension whenever possible."""

    value = str(text or "")
    available = max(0, int(width))
    if not value or available <= 0:
        return "" if available <= 0 else value
    if metrics.horizontalAdvance(value) <= available:
        return value

    suffixes = PurePath(value).suffixes
    extension = suffixes[-1] if suffixes else ""
    if len(suffixes) >= 2:
        compound = "".join(suffixes[-2:])
        if compound.lower() in _COMPOUND_EXTENSIONS:
            extension = compound
    if not extension or not value.endswith(extension):
        return metrics.elidedText(value, Qt.ElideMiddle, available)

    stem = value[: -len(extension)]
    extension_width = metrics.horizontalAdvance(extension)
    ellipsis_width = metrics.horizontalAdvance("…")
    stem_width = available - extension_width
    if stem_width < ellipsis_width:
        if extension_width <= available:
            return extension
        return metrics.elidedText(value, Qt.ElideMiddle, available)
    return metrics.elidedText(stem, Qt.ElideRight, stem_width) + extension


def elide_path_text(text: object, metrics, width: int) -> str:
    """Elide a path while preserving its root cue and filename extension."""

    value = str(text or "")
    available = max(0, int(width))
    if not value or available <= 0:
        return "" if available <= 0 else value
    if metrics.horizontalAdvance(value) <= available:
        return value

    slash_index = value.rfind("/")
    backslash_index = value.rfind("\\")
    boundary = max(slash_index, backslash_index)
    if boundary < 0 or boundary >= len(value) - 1:
        return elide_middle_text(value, metrics, available)

    basename = value[boundary + 1 :]
    if len(value) >= 3 and value[1] == ":" and value[2] in {"/", "\\"}:
        anchor = value[:3]
    elif value.startswith(("\\\\", "//")):
        anchor = value[:2]
    elif value.startswith(("/", "\\")):
        anchor = value[:1]
    else:
        first_boundary = min(
            index for index in (value.find("/"), value.find("\\")) if index >= 0
        )
        anchor = value[: first_boundary + 1]

    # Every anchor above already ends in a separator.  A second separator
    # after the ellipsis consumes scarce width without adding information.
    omission = "…"
    fixed = anchor + omission
    tail_width = available - metrics.horizontalAdvance(fixed)
    if tail_width <= 0:
        return elide_middle_text(value, metrics, available)
    projected_name = elide_filename_text(basename, metrics, tail_width)
    if not projected_name:
        return elide_middle_text(value, metrics, available)
    return fixed + projected_name


def elide_token_parts(
    prefix: object,
    core: object,
    suffix: object,
    metrics,
    width: int,
) -> str:
    """Elide only a token's editable core and keep locked affixes visible."""

    locked_prefix = str(prefix or "")
    editable_core = str(core or "")
    locked_suffix = str(suffix or "")
    available = max(0, int(width))
    paint_budget = max(0, available - _TOKEN_PAINT_SAFETY_PX)
    canonical = locked_prefix + editable_core + locked_suffix
    if not canonical or paint_budget <= 0:
        return "" if paint_budget <= 0 else canonical
    if metrics.horizontalAdvance(canonical) <= paint_budget:
        return canonical

    locked_width = metrics.horizontalAdvance(locked_prefix + locked_suffix)
    if locked_width > paint_budget:
        # Extremely narrow controls cannot show both locked pieces in full.
        # Preserve the closing delimiter and elide the prefix before ever
        # allowing QLabel to clip the suffix at its right edge.
        suffix_width = metrics.horizontalAdvance(locked_suffix)
        if suffix_width > paint_budget:
            return metrics.elidedText(
                locked_suffix,
                Qt.ElideLeft,
                paint_budget,
            )
        prefix_budget = max(0, paint_budget - suffix_width)
        while prefix_budget > 0:
            visible_prefix = metrics.elidedText(
                locked_prefix,
                Qt.ElideRight,
                prefix_budget,
            )
            candidate = visible_prefix + locked_suffix
            overflow = metrics.horizontalAdvance(candidate) - paint_budget
            if overflow <= 0:
                return candidate
            prefix_budget = max(0, prefix_budget - max(1, overflow))
        return locked_suffix

    inner_width = max(0, paint_budget - locked_width)
    while inner_width > 0:
        elided_core = metrics.elidedText(
            editable_core,
            Qt.ElideRight,
            inner_width,
        )
        if not elided_core and metrics.horizontalAdvance("…") <= inner_width:
            elided_core = "…"
        candidate = locked_prefix + elided_core + locked_suffix
        overflow = metrics.horizontalAdvance(candidate) - paint_budget
        if overflow <= 0:
            return candidate
        # Measuring the three pieces independently can differ by a pixel from
        # measuring their final shaped string.  Re-budget against that final
        # string until the paint postcondition is true.
        inner_width = max(0, inner_width - max(1, overflow))
    return locked_prefix + locked_suffix


def projected_text(
    text: object,
    metrics,
    width: int,
    *,
    mode: TextElideMode = TextElideMode.RIGHT,
) -> str:
    """Project one canonical value according to its semantic elision mode."""

    resolved = TextElideMode(mode)
    if resolved is TextElideMode.PATH:
        return elide_path_text(text, metrics, width)
    if resolved is TextElideMode.MIDDLE:
        return elide_middle_text(text, metrics, width)
    if resolved is TextElideMode.FILENAME:
        return elide_filename_text(text, metrics, width)
    return elide_plain_text(text, metrics, width)


class ElidedTextLabel(QLabel):
    """A label that exposes canonical text while painting an elided projection."""

    elisionChanged = Signal(bool)

    def __init__(
        self,
        text: object = "",
        parent=None,
        *,
        mode: TextElideMode = TextElideMode.RIGHT,
    ) -> None:
        super().__init__("", parent)
        self._full_text = str(text or "")
        self._mode = TextElideMode(mode)
        self._token_parts: tuple[str, str, str] | None = None
        self._is_elided = False
        self.setWordWrap(False)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        policy = self.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Ignored)
        self.setSizePolicy(policy)
        self._refresh_projection()

    def text(self) -> str:  # noqa: A003 - Qt API
        return self._full_text

    def renderedText(self) -> str:  # noqa: N802 - Qt API style
        return super().text()

    def isElided(self) -> bool:  # noqa: N802 - Qt API style
        return self._is_elided

    def setText(self, text: object) -> None:  # noqa: N802 - Qt API
        self._full_text = str(text or "")
        self._token_parts = None
        self._refresh_projection()

    def setTokenParts(  # noqa: N802 - Qt API style
        self,
        prefix: object,
        core: object,
        suffix: object,
        *,
        canonical: object | None = None,
    ) -> None:
        parts = (str(prefix or ""), str(core or ""), str(suffix or ""))
        self._token_parts = parts
        self._full_text = (
            str(canonical)
            if canonical is not None
            else "".join(parts)
        )
        self._refresh_projection()

    def setElideMode(self, mode: TextElideMode) -> None:  # noqa: N802
        self._mode = TextElideMode(mode)
        self._refresh_projection()

    def refreshProjection(self) -> None:  # noqa: N802
        self._refresh_projection()

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API
        hint = super().minimumSizeHint()
        return QSize(0, hint.height())

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        # QSS padding/borders reduce the paintable text area.  Re-read the
        # post-style contents rect instead of projecting against the outer
        # widget width, otherwise the last glyph can still run under the
        # border even though elision was applied.
        self._refresh_projection(self.contentsRect().width())
        super().resizeEvent(event)

    def changeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.type() in {
            QEvent.FontChange,
            QEvent.StyleChange,
            QEvent.PaletteChange,
        }:
            self._refresh_projection()
        super().changeEvent(event)

    def _refresh_projection(self, width: int | None = None) -> None:
        available = self.contentsRect().width() if width is None else int(width)
        metrics = self.fontMetrics()
        if self._token_parts is not None:
            display = elide_token_parts(
                *self._token_parts,
                metrics,
                max(0, available),
            )
        else:
            display = projected_text(
                self._full_text,
                metrics,
                max(0, available),
                mode=self._mode,
            )
        if super().text() != display:
            super().setText(display)
        is_elided = bool(self._full_text and display != self._full_text)
        if is_elided != self._is_elided:
            self._is_elided = is_elided
            self.elisionChanged.emit(is_elided)
        self.setAccessibleName(self._full_text)


__all__ = [
    "ElidedTextLabel",
    "TextElideMode",
    "elide_filename_text",
    "elide_middle_text",
    "elide_path_text",
    "elide_plain_text",
    "elide_token_parts",
    "projected_text",
]
