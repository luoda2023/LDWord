"""Strict CommonMark importer for reusable document-content materials.

The module has two deliberately separate entry points:

``parse_markdown_content`` is deterministic and performs no filesystem I/O.
It consumes text plus an already-declared resource manifest.

Filesystem capture and raster validation belong to ``compiler.py``; this
module never opens the original Markdown path.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import PurePosixPath, PureWindowsPath
from typing import Mapping, Sequence
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt
from markdown_it.token import Token

from src.config.content_materials import (
    DocumentFragment,
    HeadingBlock,
    ImageBlock,
    InlineContent,
    InlineKind,
    ListBlock,
    ListItem,
    ParagraphBlock,
    TableBlock,
    TableCell,
    TableRow,
    normalize_content_resource_path,
)
from src.shared.engine.material_token_contract import (
    MaterialTokenKind,
    normalize_material_token,
    parse_material_token,
)

_FIELD_TOKEN_PATTERN = re.compile(r"\{\{([^{}\r\n]+)\}\}")
_TASK_ITEM_PATTERN = re.compile(r"^\[[ xX]\](?:\s|$)")
_RAW_FORBIDDEN_LINK_PATTERN = re.compile(
    r"(?<!!)\[[^\]\r\n]*\]\(\s*(?:file|data|javascript|vbscript):",
    re.IGNORECASE,
)
_RAW_FORBIDDEN_IMAGE_PATTERN = re.compile(
    r"!\[[^\]\r\n]*\]\(\s*(?:file|data|javascript|vbscript):",
    re.IGNORECASE,
)
_SUPPORTED_LINK_SCHEMES = frozenset({"http", "https", "mailto"})
@dataclass(frozen=True, slots=True)
class MarkdownImportDiagnostic:
    """Structured, stable evidence for one blocking import finding."""

    code: str
    message: str
    path: str = ""
    token: str = ""
    line: int | None = None


class MarkdownImportError(ValueError):
    """Fail-fast error carrying a typed diagnostic instead of free text only."""

    def __init__(self, diagnostic: MarkdownImportDiagnostic):
        self.diagnostic = diagnostic
        location = f" ({diagnostic.path})" if diagnostic.path else ""
        super().__init__(f"{diagnostic.code}{location}: {diagnostic.message}")

    @property
    def code(self) -> str:
        return self.diagnostic.code

    @property
    def path(self) -> str:
        return self.diagnostic.path

    @property
    def token(self) -> str:
        return self.diagnostic.token


@dataclass(frozen=True, slots=True)
class _RawInlineAtom:
    kind: str
    text: str = ""
    bold: bool = False
    italic: bool = False
    href: str = ""
    strikethrough: bool = False


@dataclass(slots=True)
class _ParseState:
    source_path: str
    resource_id_by_path: dict[str, str]
    referenced_paths: list[str]
    image_ordinal: int = 0
    events: Counter[str] = field(default_factory=Counter)


def parse_markdown_content(
    markdown_text: str,
    *,
    resource_id_by_path: Mapping[str, str] | None = None,
    source_path: str = "",
) -> DocumentFragment:
    """Purely parse CommonMark text into the shared semantic fragment IR."""

    fragment, _events = parse_markdown_content_with_events(
        markdown_text,
        resource_id_by_path=resource_id_by_path,
        source_path=source_path,
    )
    return fragment


def parse_markdown_content_with_events(
    markdown_text: str,
    *,
    resource_id_by_path: Mapping[str, str] | None = None,
    source_path: str = "",
) -> tuple[DocumentFragment, tuple[tuple[str, int], ...]]:
    """Parse Markdown and return deterministic normalization event counts."""

    if not isinstance(markdown_text, str):
        raise TypeError("markdown_text must be a string")
    by_path = {
        normalize_content_resource_path(str(path)): str(resource_id or "").strip()
        for path, resource_id in dict(resource_id_by_path or {}).items()
    }
    if any(not resource_id for resource_id in by_path.values()):
        raise ValueError("resource_id_by_path values must not be empty")
    forbidden_link = _RAW_FORBIDDEN_LINK_PATTERN.search(markdown_text)
    if forbidden_link:
        _raise(
            "link_scheme_not_allowed",
            "only http, https, and mailto links are supported",
            path=source_path,
            token=forbidden_link.group(0),
        )
    forbidden_image = _RAW_FORBIDDEN_IMAGE_PATTERN.search(markdown_text)
    if forbidden_image:
        _raise(
            "image_path_not_local_relative",
            "images must use plain relative local paths",
            path=source_path,
            token=forbidden_image.group(0),
        )

    # Keep the exact frozen dialect construction. Raw HTML tokens stay visible
    # to the importer and are explicitly blocked below rather than downgraded.
    parser = MarkdownIt("commonmark").enable(("table", "strikethrough"))
    tokens = parser.parse(markdown_text)
    state = _ParseState(source_path, by_path, [])
    blocks, cursor = _parse_blocks(tokens, 0, state, stop_types=frozenset())
    if cursor != len(tokens):
        _unsupported_token(tokens[cursor], state, context="document")

    referenced = set(state.referenced_paths)
    declared = set(by_path)
    if referenced != declared:
        missing = sorted(referenced - declared)
        unused = sorted(declared - referenced)
        details: list[str] = []
        if missing:
            details.append("undeclared=" + ",".join(missing))
        if unused:
            details.append("unused=" + ",".join(unused))
        _raise(
            "resource_manifest_mismatch",
            "image references must exactly match captured resources; " + "; ".join(details),
            path=source_path,
            token=",".join(missing or unused),
        )
    return (
        DocumentFragment(blocks=tuple(blocks)),
        tuple(sorted(state.events.items())),
    )


def discover_markdown_resource_paths(markdown_text: str) -> tuple[str, ...]:
    """Discover canonical local image paths without reading the filesystem."""

    if not isinstance(markdown_text, str):
        raise TypeError("markdown_text must be a string")
    parser = MarkdownIt("commonmark").enable(("table", "strikethrough"))
    state = _ParseState("", {}, [])
    paths: set[str] = set()
    for token in parser.parse(markdown_text):
        if token.type != "inline":
            continue
        for image in _inline_images(token):
            paths.add(
                _canonical_local_image_path(
                    image.attrGet("src") or "",
                    state,
                    image,
                )
            )
    return tuple(sorted(paths, key=str.casefold))


def _parse_blocks(
    tokens: Sequence[Token],
    cursor: int,
    state: _ParseState,
    *,
    stop_types: frozenset[str],
) -> tuple[list[object], int]:
    blocks: list[object] = []
    while cursor < len(tokens):
        token = tokens[cursor]
        if token.type in stop_types:
            break
        if token.type == "heading_open":
            block, cursor = _parse_heading(tokens, cursor, state)
            blocks.append(block)
            continue
        if token.type == "paragraph_open":
            block, cursor = _parse_paragraph(tokens, cursor, state)
            blocks.append(block)
            continue
        if token.type in {"bullet_list_open", "ordered_list_open"}:
            list_blocks, cursor = _parse_list(tokens, cursor, state, depth=0)
            blocks.extend(list_blocks)
            continue
        if token.type == "table_open":
            block, cursor = _parse_table(tokens, cursor, state)
            blocks.append(block)
            continue
        if token.type == "blockquote_open":
            quoted, cursor = _parse_blocks(
                tokens,
                cursor + 1,
                state,
                stop_types=frozenset({"blockquote_close"}),
            )
            _expect(tokens, cursor, "blockquote_close", state)
            blocks.extend(_normalize_quote_blocks(quoted))
            state.events["markdown_blockquote_normalized"] += 1
            cursor += 1
            continue
        if token.type in {"fence", "code_block"}:
            blocks.append(_normalized_code_block(token.content))
            state.events["markdown_code_block_normalized"] += 1
            cursor += 1
            continue
        if token.type == "hr":
            blocks.append(ParagraphBlock((InlineContent(text="────────"),)))
            state.events["markdown_horizontal_rule_normalized"] += 1
            cursor += 1
            continue
        _unsupported_token(token, state, context="document")
    return blocks, cursor


def _parse_heading(
    tokens: Sequence[Token], cursor: int, state: _ParseState
) -> tuple[HeadingBlock, int]:
    opening = tokens[cursor]
    match = re.fullmatch(r"h([1-6])", opening.tag)
    if match is None:
        _unsupported_token(opening, state, context="heading")
    inline = _expect(tokens, cursor + 1, "inline", state)
    closing = _expect(tokens, cursor + 2, "heading_close", state)
    if closing.tag != opening.tag:
        _raise_token("malformed_ast", "heading tags do not match", closing, state)
    if _inline_images(inline):
        _raise_token(
            "image_mixed_content",
            "images must occupy their own paragraph and cannot appear in headings",
            inline,
            state,
        )
    return HeadingBlock(int(match.group(1)), _parse_inline(inline, state)), cursor + 3


def _parse_paragraph(
    tokens: Sequence[Token], cursor: int, state: _ParseState
) -> tuple[ParagraphBlock | ImageBlock, int]:
    inline = _expect(tokens, cursor + 1, "inline", state)
    _expect(tokens, cursor + 2, "paragraph_close", state)
    images = _inline_images(inline)
    if images:
        image = _parse_exclusive_image(inline, images, state)
        return image, cursor + 3
    return ParagraphBlock(_parse_inline(inline, state)), cursor + 3


def _parse_exclusive_image(
    inline: Token,
    images: Sequence[Token],
    state: _ParseState,
) -> ImageBlock:
    children = tuple(inline.children or ())
    if len(images) > 1:
        _raise_token(
            "image_multiple_in_paragraph",
            "one image paragraph may contain exactly one image",
            inline,
            state,
        )
    meaningful = [
        child
        for child in children
        if not (child.type == "text" and not child.content.strip())
    ]
    if len(meaningful) != 1 or meaningful[0].type != "image":
        code = (
            "image_linked_unsupported"
            if any(child.type.startswith("link_") for child in meaningful)
            else "image_mixed_content"
        )
        _raise_token(
            code,
            "an image must be the only content in its paragraph",
            inline,
            state,
        )
    image = images[0]
    if image.attrGet("title"):
        state.events["markdown_image_title_ignored"] += 1
    relative_path = _canonical_local_image_path(image.attrGet("src") or "", state, image)
    if relative_path not in state.resource_id_by_path:
        _raise_token(
            "resource_not_declared",
            "image is absent from binding.resources",
            image,
            state,
            path=relative_path,
        )
    state.referenced_paths.append(relative_path)
    state.image_ordinal += 1
    anchor_identity = "\x1f".join(
        (state.source_path, relative_path, str(state.image_ordinal))
    )
    return ImageBlock(
        resource_id=state.resource_id_by_path[relative_path],
        alt_text=_image_alt_text(image),
        generated_anchor_id="content-image-"
        + hashlib.sha256(anchor_identity.encode("utf-8")).hexdigest()[:16],
    )


def _parse_inline(token: Token, state: _ParseState) -> tuple[InlineContent, ...]:
    atoms: list[_RawInlineAtom] = []
    bold = False
    italic = False
    strikethrough = False
    href = ""
    link_active = False
    for child in tuple(token.children or ()):
        if child.type == "text":
            atoms.append(
                _RawInlineAtom(
                    "text",
                    child.content,
                    bold,
                    italic,
                    href,
                    strikethrough,
                )
            )
        elif child.type == "softbreak":
            if link_active:
                _raise_token(
                    "link_multiline_unsupported",
                    "links cannot contain line breaks",
                    child,
                    state,
                )
            atoms.append(_RawInlineAtom("softbreak"))
        elif child.type == "hardbreak":
            if link_active:
                _raise_token(
                    "link_multiline_unsupported",
                    "links cannot contain line breaks",
                    child,
                    state,
                )
            atoms.append(_RawInlineAtom("hardbreak"))
        elif child.type == "strong_open":
            if bold:
                _raise_token("inline_nesting_invalid", "nested strong is unsupported", child, state)
            bold = True
        elif child.type == "strong_close":
            bold = False
        elif child.type == "em_open":
            if italic:
                _raise_token("inline_nesting_invalid", "nested emphasis is unsupported", child, state)
            italic = True
        elif child.type == "em_close":
            italic = False
        elif child.type == "s_open":
            if strikethrough:
                _raise_token(
                    "inline_nesting_invalid",
                    "nested strikethrough is unsupported",
                    child,
                    state,
                )
            strikethrough = True
        elif child.type == "s_close":
            strikethrough = False
        elif child.type == "link_open":
            if link_active:
                _raise_token("inline_nesting_invalid", "nested links are unsupported", child, state)
            link_active = True
            if child.attrGet("title"):
                state.events["markdown_link_title_ignored"] += 1
            href = _validate_external_link(child.attrGet("href") or "", child, state)
        elif child.type == "link_close":
            link_active = False
            href = ""
        elif child.type == "image":
            _raise_token(
                "image_mixed_content",
                "images are only supported as exclusive paragraphs",
                child,
                state,
            )
        elif child.type == "html_inline":
            _raise_token("raw_html_unsupported", "raw HTML is not supported", child, state)
        elif child.type == "code_inline":
            atoms.append(
                _RawInlineAtom(
                    "text",
                    child.content,
                    bold,
                    italic,
                    href,
                    strikethrough,
                )
            )
            state.events["markdown_inline_code_normalized"] += 1
        else:
            _unsupported_token(child, state, context="inline")
    if bold or italic or strikethrough or link_active:
        _raise_token("malformed_ast", "unclosed inline formatting token", token, state)
    return _atoms_to_inlines(atoms, token, state)


def _atoms_to_inlines(
    atoms: Sequence[_RawInlineAtom], token: Token, state: _ParseState
) -> tuple[InlineContent, ...]:
    output: list[InlineContent] = []
    text_group: list[_RawInlineAtom] = []

    def flush_text_group() -> None:
        if not text_group:
            return
        joined = "".join(atom.text for atom in text_group)
        positions: list[tuple[int, int, _RawInlineAtom]] = []
        offset = 0
        for atom in text_group:
            positions.append((offset, offset + len(atom.text), atom))
            offset += len(atom.text)
        cursor = 0
        for match in _FIELD_TOKEN_PATTERN.finditer(joined):
            _emit_text_range(output, positions, cursor, match.start())
            raw_key = match.group(1)
            key = raw_key.strip()
            if not key or key != raw_key:
                _raise_token(
                    "field_token_invalid",
                    "field Token cannot contain whitespace inside its braces",
                    token,
                    state,
                    token_text=match.group(0),
                )
            try:
                token_ref = parse_material_token(match.group(0))
            except (TypeError, ValueError):
                token_ref = None
            if token_ref is None or token_ref.kind is not MaterialTokenKind.FIELD:
                _raise_token(
                    "recursive_content_token",
                    "content sources may contain only @text: or @time: inline tokens",
                    token,
                    state,
                    token_text=match.group(0),
                )
            covered = [
                atom
                for start, end, atom in positions
                if match.start() < end and match.end() > start
            ]
            if any(atom.href for atom in covered):
                _raise_token(
                    "field_token_in_link_unsupported",
                    "field Tokens cannot be part of hyperlink labels",
                    token,
                    state,
                    token_text=match.group(0),
                )
            style = covered[0] if covered else _RawInlineAtom("text")
            _append_inline(
                output,
                InlineContent(
                    kind=InlineKind.FIELD_TOKEN,
                    bold=style.bold,
                    italic=style.italic,
                    strikethrough=style.strikethrough,
                    field_key=token_ref.key,
                ),
            )
            cursor = match.end()
        _emit_text_range(output, positions, cursor, len(joined))
        text_group.clear()

    for atom in atoms:
        if atom.kind == "text":
            text_group.append(atom)
            continue
        flush_text_group()
        _append_inline(
            output,
            InlineContent(
                kind=(
                    InlineKind.SOFT_BREAK
                    if atom.kind == "softbreak"
                    else InlineKind.HARD_BREAK
                )
            ),
        )
    flush_text_group()
    return tuple(output)


def _emit_text_range(
    output: list[InlineContent],
    positions: Sequence[tuple[int, int, _RawInlineAtom]],
    start: int,
    end: int,
) -> None:
    if end <= start:
        return
    for atom_start, atom_end, atom in positions:
        overlap_start = max(start, atom_start)
        overlap_end = min(end, atom_end)
        if overlap_end <= overlap_start:
            continue
        text = atom.text[overlap_start - atom_start : overlap_end - atom_start]
        _append_inline(
            output,
            InlineContent(
                kind=InlineKind.HYPERLINK if atom.href else InlineKind.TEXT,
                text=text,
                bold=atom.bold,
                italic=atom.italic,
                strikethrough=atom.strikethrough,
                href=atom.href,
            ),
        )


def _append_inline(output: list[InlineContent], value: InlineContent) -> None:
    if not value.text and value.kind in {InlineKind.TEXT, InlineKind.HYPERLINK}:
        return
    if output and value.kind in {InlineKind.TEXT, InlineKind.HYPERLINK}:
        previous = output[-1]
        if (
            previous.kind is value.kind
            and previous.bold == value.bold
            and previous.italic == value.italic
            and previous.underline == value.underline
            and previous.strikethrough == value.strikethrough
            and previous.href == value.href
        ):
            output[-1] = InlineContent(
                kind=previous.kind,
                text=previous.text + value.text,
                bold=previous.bold,
                italic=previous.italic,
                underline=previous.underline,
                strikethrough=previous.strikethrough,
                href=previous.href,
            )
            return
    output.append(value)


def _parse_list(
    tokens: Sequence[Token],
    cursor: int,
    state: _ParseState,
    *,
    depth: int,
) -> tuple[list[ListBlock], int]:
    if depth >= 3:
        _raise_token(
            "list_nesting_exceeded",
            "lists support at most three levels",
            tokens[cursor],
            state,
        )
    opening = tokens[cursor]
    ordered = opening.type == "ordered_list_open"
    closing_type = "ordered_list_close" if ordered else "bullet_list_close"
    source_start = int(opening.attrGet("start") or 1)
    cursor += 1
    output: list[ListBlock] = []
    pending: list[ListItem] = []
    pending_start = source_start
    item_number = source_start

    def flush_pending() -> None:
        nonlocal pending, pending_start
        if pending:
            output.append(
                ListBlock(
                    ordered=ordered,
                    start=pending_start if ordered else 1,
                    nesting=depth,
                    items=tuple(pending),
                )
            )
            pending = []

    while cursor < len(tokens) and tokens[cursor].type != closing_type:
        _expect(tokens, cursor, "list_item_open", state)
        cursor += 1
        item_inlines: tuple[InlineContent, ...] | None = None
        nested_groups: list[ListBlock] = []
        while cursor < len(tokens) and tokens[cursor].type != "list_item_close":
            current = tokens[cursor]
            if current.type == "paragraph_open":
                if item_inlines is not None:
                    _raise_token(
                        "list_item_multiple_paragraphs",
                        "list items support one text paragraph plus nested lists",
                        current,
                        state,
                    )
                inline = _expect(tokens, cursor + 1, "inline", state)
                _expect(tokens, cursor + 2, "paragraph_close", state)
                if _inline_images(inline):
                    _raise_token(
                        "image_in_list_unsupported",
                        "images are not supported inside list items",
                        inline,
                        state,
                    )
                item_inlines = _parse_inline(inline, state)
                cursor += 3
                continue
            if current.type in {"bullet_list_open", "ordered_list_open"}:
                nested, cursor = _parse_list(tokens, cursor, state, depth=depth + 1)
                nested_groups.extend(nested)
                continue
            _unsupported_token(current, state, context="list_item")
        _expect(tokens, cursor, "list_item_close", state)
        cursor += 1
        if item_inlines is None:
            _raise_token(
                "list_item_text_missing",
                "list items must contain one text paragraph",
                opening,
                state,
            )
        if _TASK_ITEM_PATTERN.match(_plain_inline_text(item_inlines)):
            item_inlines = _normalize_task_item(item_inlines)
            state.events["markdown_task_list_normalized"] += 1
        if not pending:
            pending_start = item_number
        pending.append(ListItem(item_inlines))
        if nested_groups:
            flush_pending()
            output.extend(nested_groups)
        item_number += 1
    _expect(tokens, cursor, closing_type, state)
    flush_pending()
    return output, cursor + 1


def _parse_table(
    tokens: Sequence[Token], cursor: int, state: _ParseState
) -> tuple[TableBlock, int]:
    opening = tokens[cursor]
    cursor += 1
    rows: list[TableRow] = []
    while cursor < len(tokens) and tokens[cursor].type != "table_close":
        if tokens[cursor].type in {"thead_open", "tbody_open"}:
            section_close = "thead_close" if tokens[cursor].type == "thead_open" else "tbody_close"
            cursor += 1
            while cursor < len(tokens) and tokens[cursor].type != section_close:
                _expect(tokens, cursor, "tr_open", state)
                cursor += 1
                cells: list[TableCell] = []
                while cursor < len(tokens) and tokens[cursor].type != "tr_close":
                    cell_open = tokens[cursor]
                    if cell_open.type not in {"th_open", "td_open"}:
                        _unsupported_token(cell_open, state, context="table_row")
                    inline = _expect(tokens, cursor + 1, "inline", state)
                    if _inline_images(inline):
                        _raise_token(
                            "image_in_table_unsupported",
                            "images are not supported in table cells",
                            inline,
                            state,
                        )
                    expected_close = "th_close" if cell_open.type == "th_open" else "td_close"
                    _expect(tokens, cursor + 2, expected_close, state)
                    cells.append(
                        TableCell(
                            (ParagraphBlock(_parse_inline(inline, state)),)
                        )
                    )
                    cursor += 3
                _expect(tokens, cursor, "tr_close", state)
                cursor += 1
                rows.append(TableRow(tuple(cells)))
            _expect(tokens, cursor, section_close, state)
            cursor += 1
            continue
        _unsupported_token(tokens[cursor], state, context="table")
    _expect(tokens, cursor, "table_close", state)
    try:
        return TableBlock(tuple(rows)), cursor + 1
    except ValueError as exc:
        _raise_token("table_not_rectangular", str(exc), opening, state)


def _validate_external_link(href: str, token: Token, state: _ParseState) -> str:
    parsed = urlsplit(str(href or ""))
    scheme = parsed.scheme.casefold()
    if not scheme and not parsed.netloc and parsed.path and not parsed.path.startswith(("/", "\\")):
        state.events["markdown_relative_link_normalized"] += 1
        return ""
    if scheme not in _SUPPORTED_LINK_SCHEMES:
        _raise_token(
            "link_scheme_not_allowed",
            "only http, https, and mailto links are supported",
            token,
            state,
            token_text=href,
        )
    if scheme in {"http", "https"} and not parsed.netloc:
        _raise_token("link_target_invalid", "HTTP links require a host", token, state)
    if scheme == "mailto" and not parsed.path:
        _raise_token("link_target_invalid", "mailto links require an address", token, state)
    return href


def _normalized_code_block(content: str) -> ParagraphBlock:
    lines = str(content or "").removesuffix("\n").split("\n")
    inlines: list[InlineContent] = []
    for index, line in enumerate(lines or [""]):
        if index:
            inlines.append(InlineContent(kind=InlineKind.HARD_BREAK))
        if line:
            inlines.append(InlineContent(text=line))
    return ParagraphBlock(tuple(inlines))


def _normalize_quote_blocks(blocks: Sequence[object]) -> tuple[object, ...]:
    output: list[object] = []
    prefix = InlineContent(text="│ ")
    for block in blocks:
        if isinstance(block, ParagraphBlock):
            output.append(ParagraphBlock((prefix, *block.inlines)))
        elif isinstance(block, HeadingBlock):
            output.append(ParagraphBlock((prefix, *block.inlines)))
        elif isinstance(block, ListBlock):
            output.append(
                ListBlock(
                    ordered=block.ordered,
                    start=block.start,
                    nesting=block.nesting,
                    items=tuple(
                        ListItem((prefix, *item.inlines)) for item in block.items
                    ),
                    number_format=block.number_format,
                    marker_template=block.marker_template,
                )
            )
        else:
            output.append(block)
    return tuple(output)


def _normalize_task_item(
    inlines: Sequence[InlineContent],
) -> tuple[InlineContent, ...]:
    output = list(inlines)
    for index, inline in enumerate(output):
        if inline.kind is not InlineKind.TEXT:
            continue
        match = _TASK_ITEM_PATTERN.match(inline.text)
        if match is None:
            break
        checked = inline.text[1:2].casefold() == "x"
        output[index] = InlineContent(
            kind=InlineKind.TEXT,
            text=("☑ " if checked else "☐ ") + inline.text[match.end():],
            bold=inline.bold,
            italic=inline.italic,
            underline=inline.underline,
        )
        break
    return tuple(output)


def _canonical_local_image_path(src: str, state: _ParseState, token: Token) -> str:
    raw = str(src or "").strip()
    parsed = urlsplit(raw)
    if (
        not raw
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or raw.startswith(("/", "\\", "//"))
        or "\\" in raw
        or PureWindowsPath(raw).is_absolute()
    ):
        _raise_token(
            "image_path_not_local_relative",
            "images must use plain relative local paths",
            token,
            state,
            token_text=raw,
        )
    decoded = unquote(parsed.path)
    path = PurePosixPath(decoded)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        _raise_token(
            "image_path_escape",
            "image paths cannot be absolute or traverse with ..",
            token,
            state,
            token_text=raw,
        )
    try:
        return normalize_content_resource_path(path.as_posix())
    except ValueError as exc:
        _raise_token(
            "image_path_invalid",
            str(exc),
            token,
            state,
            token_text=raw,
        )


def _inline_images(token: Token) -> tuple[Token, ...]:
    return tuple(child for child in tuple(token.children or ()) if child.type == "image")


def _image_alt_text(image: Token) -> str:
    children = tuple(image.children or ())
    if not children:
        return str(image.content or image.attrGet("alt") or "")
    return "".join(
        child.content if child.type == "text" else "\n"
        if child.type in {"softbreak", "hardbreak"}
        else ""
        for child in children
    )


def _plain_inline_text(inlines: Sequence[InlineContent]) -> str:
    return "".join(
        inline.text
        if inline.kind in {InlineKind.TEXT, InlineKind.HYPERLINK}
        else normalize_material_token(inline.field_key)
        if inline.kind is InlineKind.FIELD_TOKEN
        else "\n"
        for inline in inlines
    )


def _expect(
    tokens: Sequence[Token], cursor: int, token_type: str, state: _ParseState
) -> Token:
    if cursor >= len(tokens):
        _raise("malformed_ast", f"expected {token_type}, reached end", path=state.source_path)
    token = tokens[cursor]
    if token.type != token_type:
        _raise_token(
            "malformed_ast",
            f"expected {token_type}, got {token.type}",
            token,
            state,
        )
    return token


def _unsupported_token(token: Token, state: _ParseState, *, context: str) -> None:
    specific = {
        "html_block": "raw_html_unsupported",
        "html_inline": "raw_html_unsupported",
        "fence": "code_block_unsupported",
        "code_block": "code_block_unsupported",
        "blockquote_open": "blockquote_unsupported",
        "hr": "horizontal_rule_unsupported",
    }
    code = specific.get(token.type, "markdown_structure_unsupported")
    _raise_token(
        code,
        f"Markdown token {token.type!r} is unsupported in {context}",
        token,
        state,
    )


def _raise_token(
    code: str,
    message: str,
    token: Token,
    state: _ParseState,
    *,
    path: str | None = None,
    token_text: str | None = None,
) -> None:
    line = token.map[0] + 1 if token.map else None
    _raise(
        code,
        message,
        path=state.source_path if path is None else path,
        token=token.type if token_text is None else token_text,
        line=line,
    )


def _raise(
    code: str,
    message: str,
    *,
    path: str = "",
    token: str = "",
    line: int | None = None,
) -> None:
    raise MarkdownImportError(
        MarkdownImportDiagnostic(
            code=code,
            message=message,
            path=path,
            token=token,
            line=line,
        )
    )


__all__ = [
    "MarkdownImportDiagnostic",
    "MarkdownImportError",
    "discover_markdown_resource_paths",
    "parse_markdown_content",
    "parse_markdown_content_with_events",
]
