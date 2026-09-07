"""Stable Design-aligned renderer for assistant Markdown bodies.

Qt's ``QTextEdit.setMarkdown`` parses the structures we need, but its default
heading scale and paragraph geometry are controlled by the Qt runtime rather
than by the stylesheet passed to ``QTextDocument``.  This component keeps the
single selectable text document while applying the final font and block
formats explicitly after parsing.
"""

from __future__ import annotations

import math
import re
import time

from src.qt_api import (
    QColor,
    QFont,
    QFrame,
    QPainter,
    QPen,
    QRectF,
    QSizePolicy,
    QTextBlockFormat,
    QTextCursor,
    QTextEdit,
    QTimer,
    Qt,
    Signal,
)
from src.shared.ui.theme import get_theme


_MESSAGE_FONT_FAMILY = "Microsoft YaHei UI"
_BODY_FONT_SIZE = 14
_BODY_LINE_HEIGHT_PERCENT = 146
_HEADING_FONT_SIZES = {1: 28, 2: 21, 3: 17}
_HEADING_LINE_HEIGHT_PERCENT = 134
_HEADING_BLOCK_GAP = 6
_PARAGRAPH_BLOCK_GAP = 9
_LIST_ROW_GAP = 5
_LIST_BLOCK_GAP = 8
_HEADING_AXIS_WIDTH = 3
_HEADING_TEXT_INDENT = 12
_HEADING_AXIS_ALPHA = {1: 255, 2: 153, 3: 102}
_CODE_FONT_SIZE = 13
_CODE_LINE_HEIGHT_PERCENT = 152
_CODE_PADDING_X = 10
_CODE_PADDING_Y = 10
_CODE_BLOCK_GAP = 12
_QUOTE_TEXT_LEFT = 25
_QUOTE_TEXT_RIGHT = 12
_QUOTE_PADDING_Y = 10
_QUOTE_BLOCK_GAP = 10
_IMAGE_MAX_WIDTH = 420
_BLOCK_QUOTE_LEVEL_PROPERTY = 4224
_IMAGE_RESOURCE_TYPE = 2

# Live streaming is rendered as a sequence of markdown snapshots: raw deltas
# never enter the visible document (that would flash `|`, `#` and `**` symbols
# between re-parses).  A completed line (ends with ``\n``) forces an immediate
# re-typeset so tables grow row by row — as soon as the header + delimiter
# rows exist Qt parses them into a real QTextTable and every finished data row
# after that adds a visible row.  Small intra-line fragments are coalesced by
# the debounce timer so token-by-token output stays cheap.
_LIVE_DEBOUNCE_MS = 90
_LIVE_LINE_DEBOUNCE_S = 0.06

# While a markdown table is streaming in, Qt only recognises it as a real
# ``QTextTable`` once BOTH the header row and the ``|---|`` delimiter row are
# present.  Between those two rows the accumulated text would otherwise render
# as raw ``| a | b |`` symbols.  ``_with_synthetic_table_delimiter`` appends a
# synthetic delimiter (render-time only, never persisted) so a table whose
# header has arrived but whose delimiter is still streaming typesets as a real
# header row instead of flashing raw pipes.
_TABLE_DELIMITER_CELL_RE = re.compile(r"^\s*:?-{2,}:?\s*$")


def _cell_count(row: str) -> int:
    """Number of ``|``-separated cells in a markdown table row (best-effort)."""
    stripped = str(row or "").strip()
    if not stripped.startswith("|") and not stripped.endswith("|"):
        stripped = f"|{stripped}|"
    inner = stripped.strip("|")
    parts = [part for part in inner.split("|") if part.strip()]
    return max(1, len(parts))


def _is_delimiter_row(row: str) -> bool:
    """True when ``row`` looks like a GFM table delimiter row (``|---|``)."""
    stripped = str(row or "").strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return False
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    return bool(cells) and all(
        _TABLE_DELIMITER_CELL_RE.fullmatch(cell) for cell in cells
    )


_DELIMITER_PREFIX_CHARS = frozenset("|-: ")


def _is_delimiter_prefix(line: str) -> bool:
    """True when ``line`` looks like a *partially streamed* delimiter row:
    it only contains ``|``, ``-``, ``:`` and spaces, and has at least one dash
    or is a lone ``|`` that is clearly starting the delimiter row.
    """
    stripped = str(line or "").strip()
    if not stripped:
        return False
    if not stripped.startswith("|"):
        return False
    if all(ch in _DELIMITER_PREFIX_CHARS for ch in stripped):
        return "-" in stripped or stripped in {"|", "| "}
    return False


def _with_synthetic_table_delimiter(markdown: str) -> str:
    """Return a render-only copy of a *streaming* markdown body whose trailing
    table has not finished opening yet (header streamed in, delimiter row not
    yet complete) so Qt typesets it as a real table instead of raw pipes.

    The persisted source is never touched.  Strategy, applied only to the
    trailing contiguous ``|``-line run:

    * a run that already contains a complete ``|---|`` row is left alone (Qt
      already parses it, and any half-typed *data* row after the delimiter is
      handled natively);
    * otherwise the run is an *opening* table: any partially streamed
      delimiter-prefix fragments (``|``, ``| ---``, ...) are dropped and a
      synthetic full ``|---|`` row is appended after the header rows, so the
      header displays as a real table row from the moment it appears.
    """
    text = str(markdown or "")
    if not text.strip() or "|" not in text:
        return text
    lines = text.splitlines()
    # Locate the trailing contiguous run of ``|``-prefixed lines.
    run_end = len(lines)
    while run_end > 0 and lines[run_end - 1].lstrip().startswith("|"):
        run_end -= 1
    tail = lines[run_end:]
    if not tail:
        return text
    if any(_is_delimiter_row(line) for line in tail):
        return text
    # Drop partially-streamed delimiter fragments (dash/pipe-only pieces) so
    # only genuine header text remains above the synthetic delimiter.
    header_lines = [line for line in tail if not _is_delimiter_prefix(line)]
    if not header_lines:
        # The trailing run is nothing but half-typed delimiter fragments or a
        # bare ``|`` (the model just started typing the header row).  Qt would
        # show that lone ``|`` as raw text, so strip the fragments for this
        # render snapshot; the real source is untouched and the header text
        # replaces them within a frame or two.
        kept = lines[:run_end]
        if not kept:
            return ""
        return "\n".join(kept).rstrip() + "\n"
    header_width = max((_cell_count(row) for row in header_lines), default=2)
    delimiter = "|" + "|".join(" --- " for _ in range(header_width)) + "|"
    kept = lines[:run_end] + header_lines
    joined = "\n".join(kept)
    return joined + "\n" + delimiter


def _message_font(size_px: int, *, weight: int = 400) -> QFont:
    font = QFont(_MESSAGE_FONT_FAMILY)
    font.setPixelSize(int(size_px))
    font.setWeight(QFont.Weight(int(weight)))
    font.setHintingPreference(QFont.PreferNoHinting)
    font.setStyleStrategy(QFont.PreferAntialias)
    return font


class AssistantMessageBodyRenderer(QTextEdit):
    """Selectable, link-aware assistant body with explicit Design geometry."""

    link_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source_text = ""
        self._live = False
        self._formatting = False
        self._code_block_positions: set[int] = set()
        self._quote_block_positions: set[int] = set()
        self.setObjectName("assistant_message_markdown")
        self.setReadOnly(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.document().setDocumentMargin(0)
        self.document().documentLayout().documentSizeChanged.connect(
            lambda _size: self._sync_height()
        )
        # See the module comment above `_LIVE_DEBOUNCE_MS`: live text is shown
        # as fast markdown snapshots (never raw symbols).  A completed line
        # flushes immediately so tables form row by row; intra-line deltas are
        # coalesced by the debounce timer.  The timer is a single-shot and only
        # fires while new deltas keep arriving; finalise stops it.
        self._live_format_timer = QTimer(self)
        self._live_format_timer.setSingleShot(True)
        self._live_format_timer.setInterval(_LIVE_DEBOUNCE_MS)
        self._live_format_timer.timeout.connect(self._reformat_live_as_markdown)
        self._last_live_render_at = 0.0
        self.apply_semantic_theme()

    def set_markdown(self, text: str) -> None:
        self._source_text = str(text or "")
        self._live = False
        self._prepare_document()
        self.setMarkdown(self._source_text)
        self._apply_document_geometry()

    def set_live_text(self, text: str) -> None:
        self._source_text = str(text or "")
        self._live = True
        self._render_live_snapshot()

    def append_live_text(self, text: str) -> None:
        delta = str(text or "")
        if not delta:
            return
        self._source_text += delta
        self._live = True
        # A completed line means a markdown row/block boundary just arrived
        # (e.g. one more table row).  Re-typeset right away (debounced) so the
        # table visibly gains rows while streaming instead of popping only once
        # the whole chapter is done.  Partial intra-line deltas fall through to
        # the debounce timer below.
        line_completed = delta.endswith("\n") or self._source_text.endswith("\n")
        self._arm_live_reformat(immediate=line_completed)

    def _render_live_snapshot(self) -> None:
        """Typeset the accumulated source as markdown (live mode)."""
        self._last_live_render_at = time.monotonic()
        self._prepare_document()
        # The streamed source may end right after a table header whose ``|---|``
        # delimiter row has not streamed in yet.  Qt would render that as raw
        # ``| a | b |`` symbols; the render-only synthetic delimiter lets the
        # header show as a real table row while the model is still typing.
        self.setMarkdown(_with_synthetic_table_delimiter(self._source_text))
        self._apply_document_geometry()

    def finalize_live_body(self) -> None:
        """Stop live throttling and render the final body as Markdown."""
        timer = getattr(self, "_live_format_timer", None)
        if timer is not None:
            timer.stop()
        if self._live:
            self._live = False
            self._render_source_markdown()

    def _arm_live_reformat(self, *, immediate: bool = False) -> None:
        """Schedule the next live snapshot re-typeset.

        ``immediate=True`` (a full line just arrived) re-renders right away as
        long as the previous snapshot is at least ``_LIVE_LINE_DEBOUNCE_S`` old;
        otherwise the single-shot debounce timer coalesces the pending text.
        """
        if not self._live:
            return
        timer = getattr(self, "_live_format_timer", None)
        if immediate and not self._source_text.strip():
            return
        if immediate:
            elapsed = time.monotonic() - self._last_live_render_at
            if elapsed >= _LIVE_LINE_DEBOUNCE_S:
                self._render_live_snapshot()
                return
        if timer is not None and not timer.isActive():
            timer.start()

    def _reformat_live_as_markdown(self) -> None:
        """Debounce-timer entry: typeset the accumulated text as markdown."""
        if not self._live or not self._source_text.strip():
            return
        self._render_live_snapshot()

    def _render_source_markdown(self) -> None:
        self._prepare_document()
        self.setMarkdown(self._source_text)
        self._apply_document_geometry()

    def apply_semantic_theme(self) -> None:
        self._prepare_document()
        if not self.document().isEmpty():
            self._apply_document_geometry()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        anchor = self.anchorAt(event.position().toPoint())
        if anchor:
            self.link_requested.emit(anchor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in {Qt.Key_Return, Qt.Key_Enter}:
            href = self.textCursor().charFormat().anchorHref()
            if href:
                self.link_requested.emit(href)
                event.accept()
                return
        super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.document().setTextWidth(max(1, self.viewport().width()))
        self._sync_image_geometry()
        self._sync_height()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        # QTextEdit clears its viewport during the base paint pass, so the
        # semantic surfaces must be composited afterwards. Their fills stay
        # deliberately light; borders and indicators provide the hard edge.
        self._paint_block_surfaces()
        self._paint_heading_axes()

    def _prepare_document(self) -> None:
        theme = get_theme()
        document = self.document()
        document.setDefaultFont(_message_font(_BODY_FONT_SIZE))
        document.setDocumentMargin(0)
        document.setDefaultStyleSheet(
            f"""
            body, p {{
                color: {theme.text_primary};
                font-family: "{_MESSAGE_FONT_FAMILY}";
                font-size: {_BODY_FONT_SIZE}px;
                font-weight: 400;
                margin: 0;
                padding: 0;
                white-space: pre-wrap;
            }}
            h1, h2, h3 {{
                color: {theme.text_primary};
                font-family: "{_MESSAGE_FONT_FAMILY}";
                font-weight: 700;
                margin: 0;
                padding: 0;
            }}
            h1 {{ font-size: {_HEADING_FONT_SIZES[1]}px; }}
            h2 {{ font-size: {_HEADING_FONT_SIZES[2]}px; }}
            h3 {{ font-size: {_HEADING_FONT_SIZES[3]}px; }}
            strong {{
                color: {theme.text_primary};
                font-weight: 700;
            }}
            a {{
                color: {theme.text_link};
                text-decoration: none;
            }}
            code {{
                color: {theme.text_primary};
                background-color: {theme.bg_hover};
                font-family: "Cascadia Mono", "Consolas";
                padding: 1px 3px;
            }}
            pre {{
                color: {theme.text_primary};
                background-color: {theme.bg_window};
                border: 1px solid {theme.border_light};
                padding: 10px;
                margin: 7px 0;
                white-space: pre-wrap;
            }}
            blockquote {{
                color: {theme.text_secondary};
                background-color: {theme.bg_window};
                border-left: 3px solid {theme.primary};
                padding: 7px 10px;
                margin: 7px 0;
            }}
            ul, ol {{
                margin: 0 0 {_LIST_BLOCK_GAP}px 18px;
                padding: 0;
            }}
            li {{
                color: {theme.text_primary};
                margin: 0 0 {_LIST_ROW_GAP}px 0;
            }}
            table {{
                border-collapse: collapse;
                margin: 8px 0;
            }}
            th {{
                color: {theme.text_primary};
                background-color: {theme.bg_window};
                border: 1px solid {theme.border_light};
                padding: 6px 8px;
                font-weight: 600;
            }}
            td {{
                color: {theme.text_primary};
                border: 1px solid {theme.border_light};
                padding: 6px 8px;
            }}
            """
        )

    def _apply_document_geometry(self) -> None:
        if self._formatting:
            return
        self._formatting = True
        try:
            document = self.document()
            self._code_block_positions.clear()
            self._quote_block_positions.clear()
            block = document.begin()
            while block.isValid():
                level = max(0, min(3, int(block.blockFormat().headingLevel())))
                list_object = block.textList()
                block_format = block.blockFormat()
                is_code_block = bool(block_format.nonBreakableLines())
                is_quote_block = bool(
                    block_format.property(_BLOCK_QUOTE_LEVEL_PROPERTY)
                )
                is_image_block = self._block_contains_image(block)
                block_format.setTopMargin(0)
                if level:
                    block_format.setLeftMargin(_HEADING_TEXT_INDENT)
                    block_format.setBottomMargin(_HEADING_BLOCK_GAP)
                    block_format.setLineHeight(
                        _HEADING_LINE_HEIGHT_PERCENT,
                        QTextBlockFormat.ProportionalHeight.value,
                    )
                    self._format_block_text(
                        block,
                        size_px=_HEADING_FONT_SIZES[level],
                        weight=700,
                    )
                elif is_code_block:
                    self._code_block_positions.add(block.position())
                    # Qt's Markdown importer marks fenced code as non-breakable.
                    # With the outer horizontal scrollbar hidden, that silently
                    # clipped long lines.  Keep the code surface readable inside
                    # the message width instead.
                    block_format.setNonBreakableLines(False)
                    block_format.setLeftMargin(_CODE_PADDING_X)
                    block_format.setRightMargin(_CODE_PADDING_X)
                    block_format.setTopMargin(_CODE_PADDING_Y)
                    block_format.setBottomMargin(_CODE_PADDING_Y + _CODE_BLOCK_GAP)
                    block_format.setLineHeight(
                        _CODE_LINE_HEIGHT_PERCENT,
                        QTextBlockFormat.ProportionalHeight.value,
                    )
                    self._format_block_text(
                        block,
                        size_px=_CODE_FONT_SIZE,
                        preserve_monospace=True,
                    )
                elif is_quote_block:
                    self._quote_block_positions.add(block.position())
                    block_format.setLeftMargin(_QUOTE_TEXT_LEFT)
                    block_format.setRightMargin(_QUOTE_TEXT_RIGHT)
                    block_format.setTopMargin(_QUOTE_PADDING_Y)
                    block_format.setBottomMargin(_QUOTE_PADDING_Y + _QUOTE_BLOCK_GAP)
                    block_format.setLineHeight(
                        _BODY_LINE_HEIGHT_PERCENT,
                        QTextBlockFormat.ProportionalHeight.value,
                    )
                    self._format_block_text(block, size_px=_BODY_FONT_SIZE)
                elif is_image_block:
                    # Proportional body line height would multiply the rendered
                    # bitmap height (for example 386 px became 563 px). Images
                    # own their intrinsic aspect-ratio geometry instead.
                    block_format.setLineHeight(
                        100,
                        QTextBlockFormat.ProportionalHeight.value,
                    )
                    block_format.setBottomMargin(16)
                else:
                    block_format.setLineHeight(
                        _BODY_LINE_HEIGHT_PERCENT,
                        QTextBlockFormat.ProportionalHeight.value,
                    )
                    next_block = block.next()
                    if list_object is not None:
                        next_is_same_list = (
                            next_block.isValid()
                            and next_block.textList() is list_object
                        )
                        block_format.setBottomMargin(
                            _LIST_ROW_GAP if next_is_same_list else _LIST_BLOCK_GAP
                        )
                    else:
                        block_format.setBottomMargin(_PARAGRAPH_BLOCK_GAP)
                    self._format_block_text(block, size_px=_BODY_FONT_SIZE)
                cursor = QTextCursor(block)
                cursor.setBlockFormat(block_format)
                block = block.next()
            self._sync_image_geometry()
            document.adjustSize()
        finally:
            self._formatting = False
        self._sync_height()
        self.viewport().update()

    @staticmethod
    def _format_block_text(
        block,
        *,
        size_px: int,
        weight: int | None = None,
        preserve_monospace: bool = False,
    ) -> None:
        fragments: list[tuple[int, int, object]] = []
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.length() > 0:
                char_format = fragment.charFormat()
                font = char_format.font()
                current_family = font.family().casefold()
                is_monospace = font.fixedPitch() or current_family in {
                    "monospace",
                    "cascadia mono",
                    "consolas",
                }
                if not (preserve_monospace or is_monospace):
                    font.setFamily(_MESSAGE_FONT_FAMILY)
                font.setPixelSize(int(size_px))
                if weight is not None:
                    font.setWeight(QFont.Weight(int(weight)))
                char_format.setFont(font)
                fragments.append((fragment.position(), fragment.length(), char_format))
            iterator += 1
        document = block.document()
        for position, length, char_format in fragments:
            cursor = QTextCursor(document)
            cursor.setPosition(position)
            cursor.setPosition(position + length, QTextCursor.KeepAnchor)
            cursor.setCharFormat(char_format)

    @staticmethod
    def _block_contains_image(block) -> bool:
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.charFormat().isImageFormat():
                return True
            iterator += 1
        return False

    def _sync_image_geometry(self) -> None:
        """Constrain Markdown images to Design's preview width without clipping."""

        if self._live:
            return
        available_width = max(1, min(_IMAGE_MAX_WIDTH, self.viewport().width()))
        document = self.document()
        block = document.begin()
        while block.isValid():
            image_only = False
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if not fragment.isValid():
                    iterator += 1
                    continue
                char_format = fragment.charFormat()
                if not char_format.isImageFormat():
                    iterator += 1
                    continue
                image_format = char_format.toImageFormat()
                resource = document.resource(
                    _IMAGE_RESOURCE_TYPE,
                    image_format.name(),
                )
                intrinsic = (
                    resource.size()
                    if resource is not None and hasattr(resource, "size")
                    else None
                )
                if (
                    intrinsic is None
                    or not intrinsic.isValid()
                    or intrinsic.width() <= 0
                    or intrinsic.height() <= 0
                ):
                    iterator += 1
                    continue
                target_width = min(available_width, intrinsic.width())
                target_height = max(
                    1,
                    round(intrinsic.height() * target_width / intrinsic.width()),
                )
                if (
                    round(image_format.width()) != target_width
                    or round(image_format.height()) != target_height
                ):
                    image_format.setWidth(target_width)
                    image_format.setHeight(target_height)
                    cursor = QTextCursor(document)
                    cursor.setPosition(fragment.position())
                    cursor.setPosition(
                        fragment.position() + fragment.length(),
                        QTextCursor.KeepAnchor,
                    )
                    cursor.setCharFormat(image_format)
                image_only = block.text().strip() in {"", "\ufffc"}
                iterator += 1
            if image_only:
                block_format = block.blockFormat()
                block_format.setAlignment(Qt.AlignHCenter)
                block_format.setBottomMargin(16)
                cursor = QTextCursor(block)
                cursor.setBlockFormat(block_format)
            block = block.next()

    def _sync_height(self) -> None:
        if self._formatting:
            return
        document_height = self.document().documentLayout().documentSize().height()
        self.setFixedHeight(max(24, int(math.ceil(document_height)) + 2))

    def _paint_heading_axes(self) -> None:
        headings = self._heading_axis_rects()
        if not headings:
            return
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        for level, rect in headings:
            color = QColor(get_theme().primary)
            color.setAlpha(_HEADING_AXIS_ALPHA[level])
            painter.setBrush(color)
            painter.drawRoundedRect(rect, 1.5, 1.5)
        painter.end()

    def _heading_axis_rects(self) -> list[tuple[int, QRectF]]:
        block = self.document().begin()
        headings: list[tuple[int, QRectF]] = []
        vertical_offset = self.verticalScrollBar().value()
        while block.isValid():
            level = max(0, min(3, int(block.blockFormat().headingLevel())))
            if level:
                block_rect = self.document().documentLayout().blockBoundingRect(block)
                headings.append(
                    (
                        level,
                        QRectF(
                            0.0,
                            float(block_rect.top() - vertical_offset),
                            float(_HEADING_AXIS_WIDTH),
                            float(max(10.0, block_rect.height())),
                        ),
                    )
                )
            block = block.next()
        return headings

    def _paint_block_surfaces(self) -> None:
        if not self._code_block_positions and not self._quote_block_positions:
            return
        theme = get_theme()
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing, True)
        vertical_offset = self.verticalScrollBar().value()
        block = self.document().begin()
        while block.isValid():
            position = block.position()
            if (
                position not in self._code_block_positions
                and position not in self._quote_block_positions
            ):
                block = block.next()
                continue
            block_rect = self.document().documentLayout().blockBoundingRect(block)
            padding_y = (
                _CODE_PADDING_Y
                if position in self._code_block_positions
                else _QUOTE_PADDING_Y
            )
            surface = QRectF(
                0.5,
                block_rect.top() - padding_y - vertical_offset + 0.5,
                max(1.0, self.viewport().width() - 1.0),
                block_rect.height() + padding_y * 2 - 1.0,
            )
            if position in self._code_block_positions:
                fill = QColor(theme.bg_hover)
                fill.setAlpha(102)
                border = QColor(theme.border_light)
                border.setAlpha(180)
                painter.setPen(QPen(border, 1))
                painter.setBrush(fill)
                painter.drawRoundedRect(surface, 8, 8)
            else:
                fill = QColor(theme.bg_hover)
                fill.setAlpha(76)
                painter.setPen(Qt.NoPen)
                painter.setBrush(fill)
                painter.drawRoundedRect(surface, 6, 6)
                indicator = QColor(theme.primary)
                painter.setBrush(indicator)
                painter.drawRoundedRect(
                    QRectF(
                        10,
                        surface.top() + 10,
                        3,
                        max(10.0, surface.height() - 20),
                    ),
                    1.5,
                    1.5,
                )
            block = block.next()
        painter.end()


__all__ = ["AssistantMessageBodyRenderer"]
