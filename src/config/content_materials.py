"""Pure contracts for reusable document-content materials.

This module deliberately contains no parser, filesystem, UI, or Word logic.
It defines the immutable facts exchanged by persistence, preflight, importers,
and renderers so Markdown and DOCX sources converge on one semantic IR.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from pathlib import PurePosixPath, PureWindowsPath
import re
from typing import Mapping, Sequence, TypeVar

from src.shared.engine.material_token_contract import (
    MaterialTokenKind,
    MaterialTokenNamespace,
    material_token,
    parse_material_token,
)


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CONTENT_ID_PATTERN = re.compile(r"^[^\s{}:]+$")


class _StringEnum(str, Enum):
    """Python 3.10-compatible string enum."""


class ContentOccurrencePolicy(_StringEnum):
    EXACTLY_ONE = "exactly_one"
    ALL = "all"


class ContentHeadingPolicy(_StringEnum):
    PRESERVE = "preserve"
    RELATIVE_TO_ANCHOR = "relative_to_anchor"


class ContentPageBreakPolicy(_StringEnum):
    DROP = "drop"
    PRESERVE_EXPLICIT = "preserve_explicit"


class ContentFormatMode(_StringEnum):
    TARGET_DOCUMENT = "target_document"
    PLAIN_TEXT = "plain_text"


class InlineKind(_StringEnum):
    TEXT = "text"
    SOFT_BREAK = "soft_break"
    HARD_BREAK = "hard_break"
    TAB = "tab"
    FIELD_TOKEN = "field_token"
    HYPERLINK = "hyperlink"


class InlineVerticalAlignment(_StringEnum):
    BASELINE = "baseline"
    SUPERSCRIPT = "superscript"
    SUBSCRIPT = "subscript"


class ListNumberFormat(_StringEnum):
    BULLET = "bullet"
    DECIMAL = "decimal"
    CHINESE_COUNTING = "chineseCounting"
    CHINESE_LEGAL_SIMPLIFIED = "chineseLegalSimplified"
    IDEOGRAPH_DIGITAL = "ideographDigital"
    DECIMAL_ENCLOSED_CIRCLE = "decimalEnclosedCircle"
    DECIMAL_FULL_WIDTH = "decimalFullWidth"


class ContentBlockKind(_StringEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    IMAGE = "image"
    PAGE_BREAK = "page_break"


@dataclass(frozen=True, slots=True)
class FileAssetRef:
    """Content-addressed reference to one source file.

    The contract does not assert that ``source_path`` currently exists. That
    belongs to intake/preflight. It does assert that identity metadata is
    complete and internally valid.
    """

    source_path: str
    original_name: str
    media_type: str
    content_sha256: str
    byte_size: int

    def __post_init__(self) -> None:
        _require_text(self.source_path, "source_path")
        _require_text(self.original_name, "original_name")
        _require_text(self.media_type, "media_type")
        _validate_sha256(self.content_sha256, "content_sha256")
        _validate_byte_size(self.byte_size)

    def to_dict(self) -> dict[str, object]:
        return {
            "source_path": self.source_path,
            "original_name": self.original_name,
            "media_type": self.media_type,
            "content_sha256": self.content_sha256,
            "byte_size": self.byte_size,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "FileAssetRef":
        return cls(
            source_path=str(payload.get("source_path", "") or ""),
            original_name=str(payload.get("original_name", "") or ""),
            media_type=str(payload.get("media_type", "") or ""),
            content_sha256=str(payload.get("content_sha256", "") or ""),
            byte_size=_as_int(payload.get("byte_size", 0), "byte_size"),
        )


@dataclass(frozen=True, order=True, slots=True)
class ContentResourceKey:
    """Unambiguous runtime identity of one content-local resource.

    An artifact resource id is only unique inside one content artifact.
    Runtime maps must therefore include the owning ``content_id``; using a
    bare id can silently cross-wire two reusable content materials.
    """

    content_id: str
    resource_id: str

    def __post_init__(self) -> None:
        _validate_content_id(self.content_id)
        object.__setattr__(
            self,
            "resource_id",
            normalize_content_resource_path(self.resource_id),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "content_id": self.content_id,
            "resource_id": self.resource_id,
        }

@dataclass(frozen=True, slots=True)
class ContentInsertionRule:
    """How one semantic fragment replaces one content anchor."""

    rule_id: str
    content_id: str
    anchor_token: str
    required: bool = True
    occurrence_policy: ContentOccurrencePolicy = ContentOccurrencePolicy.EXACTLY_ONE
    heading_policy: ContentHeadingPolicy = ContentHeadingPolicy.PRESERVE
    heading_level_offset: int = 0
    page_break_policy: ContentPageBreakPolicy = ContentPageBreakPolicy.DROP
    format_mode: ContentFormatMode = ContentFormatMode.TARGET_DOCUMENT

    def __post_init__(self) -> None:
        _require_text(self.rule_id, "rule_id")
        _validate_content_id(self.content_id)
        expected_token = content_anchor_token(self.content_id)
        if self.anchor_token != expected_token:
            raise ValueError(
                f"anchor_token must be the canonical token {expected_token!r}"
            )
        _coerce_enum_field(self, "occurrence_policy", ContentOccurrencePolicy)
        _coerce_enum_field(self, "heading_policy", ContentHeadingPolicy)
        _coerce_enum_field(self, "page_break_policy", ContentPageBreakPolicy)
        _coerce_enum_field(self, "format_mode", ContentFormatMode)
        if isinstance(self.heading_level_offset, bool) or not isinstance(
            self.heading_level_offset, int
        ):
            raise TypeError("heading_level_offset must be an integer")

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "content_id": self.content_id,
            "anchor_token": self.anchor_token,
            "required": self.required,
            "occurrence_policy": self.occurrence_policy.value,
            "heading_policy": self.heading_policy.value,
            "heading_level_offset": self.heading_level_offset,
            "page_break_policy": self.page_break_policy.value,
            "format_mode": self.format_mode.value,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ContentInsertionRule":
        return cls(
            rule_id=str(payload.get("rule_id", "") or ""),
            content_id=str(payload.get("content_id", "") or ""),
            anchor_token=str(payload.get("anchor_token", "") or ""),
            required=bool(payload.get("required", True)),
            occurrence_policy=str(
                payload.get("occurrence_policy", "exactly_one") or "exactly_one"
            ),
            heading_policy=str(payload.get("heading_policy", "preserve") or "preserve"),
            heading_level_offset=_as_int(
                payload.get("heading_level_offset", 0), "heading_level_offset"
            ),
            page_break_policy=str(payload.get("page_break_policy", "drop") or "drop"),
            format_mode=str(
                payload.get("format_mode", "target_document")
                or "target_document"
            ),
        )


@dataclass(frozen=True, slots=True)
class InlineContent:
    """Smallest supported semantic inline unit."""

    kind: InlineKind = InlineKind.TEXT
    text: str = ""
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    vertical_alignment: InlineVerticalAlignment = InlineVerticalAlignment.BASELINE
    href: str = ""
    field_key: str = ""
    text_color: str = ""

    def __post_init__(self) -> None:
        _coerce_enum_field(self, "kind", InlineKind)
        _coerce_enum_field(
            self,
            "vertical_alignment",
            InlineVerticalAlignment,
        )
        if self.kind is InlineKind.HYPERLINK:
            _require_text(self.href, "href")
        elif self.href:
            raise ValueError("href is only valid for hyperlink inlines")
        if self.kind is InlineKind.FIELD_TOKEN:
            _require_text(self.field_key, "field_key")
            ref = parse_material_token(self.field_key)
            if ref.kind is not MaterialTokenKind.FIELD:
                raise ValueError("only @text: and @time: may be field-token inlines")
        elif self.field_key:
            raise ValueError("field_key is only valid for field-token inlines")

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "text": self.text,
            "bold": self.bold,
            "italic": self.italic,
            "underline": self.underline,
            "strikethrough": self.strikethrough,
            "vertical_alignment": self.vertical_alignment.value,
            "href": self.href,
            "field_key": self.field_key,
            "text_color": self.text_color,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "InlineContent":
        return cls(
            kind=str(payload.get("kind", "text") or "text"),
            text=str(payload.get("text", "") or ""),
            bold=bool(payload.get("bold", False)),
            italic=bool(payload.get("italic", False)),
            underline=bool(payload.get("underline", False)),
            strikethrough=bool(payload.get("strikethrough", False)),
            vertical_alignment=str(
                payload.get("vertical_alignment", "baseline") or "baseline"
            ),
            href=str(payload.get("href", "") or ""),
            field_key=str(payload.get("field_key", "") or ""),
            text_color=str(payload.get("text_color", "") or ""),
        )


@dataclass(frozen=True, slots=True)
class HeadingBlock:
    level: int
    inlines: tuple[InlineContent, ...]
    kind: ContentBlockKind = ContentBlockKind.HEADING

    def __post_init__(self) -> None:
        _coerce_enum_field(self, "kind", ContentBlockKind)
        if self.kind is not ContentBlockKind.HEADING:
            raise ValueError("HeadingBlock.kind must be heading")
        if not 1 <= self.level <= 9:
            raise ValueError("heading level must be between 1 and 9")
        _normalize_inlines(self, "inlines")


@dataclass(frozen=True, slots=True)
class ParagraphBlock:
    inlines: tuple[InlineContent, ...]
    kind: ContentBlockKind = ContentBlockKind.PARAGRAPH
    shading: str = ""

    def __post_init__(self) -> None:
        _coerce_enum_field(self, "kind", ContentBlockKind)
        if self.kind is not ContentBlockKind.PARAGRAPH:
            raise ValueError("ParagraphBlock.kind must be paragraph")
        _normalize_inlines(self, "inlines")
        object.__setattr__(self, "shading", self.shading or "")


@dataclass(frozen=True, slots=True)
class ListItem:
    inlines: tuple[InlineContent, ...]

    def __post_init__(self) -> None:
        _normalize_inlines(self, "inlines")


@dataclass(frozen=True, slots=True)
class ListBlock:
    ordered: bool
    start: int
    nesting: int
    items: tuple[ListItem, ...]
    number_format: ListNumberFormat | None = None
    marker_template: str = ""
    kind: ContentBlockKind = ContentBlockKind.LIST

    def __post_init__(self) -> None:
        _coerce_enum_field(self, "kind", ContentBlockKind)
        if self.kind is not ContentBlockKind.LIST:
            raise ValueError("ListBlock.kind must be list")
        if self.start < 1:
            raise ValueError("list start must be at least 1")
        if self.nesting < 0:
            raise ValueError("list nesting cannot be negative")
        number_format = self.number_format or (
            ListNumberFormat.DECIMAL if self.ordered else ListNumberFormat.BULLET
        )
        if not isinstance(number_format, ListNumberFormat):
            number_format = ListNumberFormat(str(number_format))
        if self.ordered == (number_format is ListNumberFormat.BULLET):
            raise ValueError("ordered must agree with number_format")
        object.__setattr__(self, "number_format", number_format)
        marker_template = str(self.marker_template or "")
        if any(char in marker_template for char in "\r\n\x00"):
            raise ValueError("marker_template cannot contain control characters")
        if self.ordered and marker_template and f"%{self.nesting + 1}" not in marker_template:
            raise ValueError("numbered marker_template must reference its list level")
        object.__setattr__(self, "marker_template", marker_template)
        items = tuple(self.items or ())
        if any(not isinstance(item, ListItem) for item in items):
            raise TypeError("items must contain only ListItem values")
        object.__setattr__(self, "items", items)


@dataclass(frozen=True, slots=True)
class TableCell:
    blocks: tuple[ParagraphBlock | ListBlock | ImageBlock, ...]
    rowspan: int = 1
    colspan: int = 1

    def __post_init__(self) -> None:
        blocks = tuple(self.blocks or ())
        supported = (ParagraphBlock, ListBlock, ImageBlock)
        if not blocks or any(not isinstance(block, supported) for block in blocks):
            raise TypeError(
                "table cell blocks must contain paragraphs, lists, or images"
            )
        object.__setattr__(self, "blocks", blocks)
        if self.rowspan < 1 or self.colspan < 1:
            raise ValueError("table cell spans must be at least 1")


@dataclass(frozen=True, slots=True)
class TableRow:
    cells: tuple[TableCell, ...]

    def __post_init__(self) -> None:
        cells = tuple(self.cells or ())
        if any(not isinstance(cell, TableCell) for cell in cells):
            raise TypeError("cells must contain only TableCell values")
        object.__setattr__(self, "cells", cells)


@dataclass(frozen=True, slots=True)
class TableBlock:
    rows: tuple[TableRow, ...]
    kind: ContentBlockKind = ContentBlockKind.TABLE

    def __post_init__(self) -> None:
        _coerce_enum_field(self, "kind", ContentBlockKind)
        if self.kind is not ContentBlockKind.TABLE:
            raise ValueError("TableBlock.kind must be table")
        rows = tuple(self.rows or ())
        if any(not isinstance(row, TableRow) for row in rows):
            raise TypeError("rows must contain only TableRow values")
        _validate_table_grid(rows)
        object.__setattr__(self, "rows", rows)


@dataclass(frozen=True, slots=True)
class ImageBlock:
    resource_id: str
    alt_text: str = ""
    caption: str = ""
    width_px: int | None = None
    height_px: int | None = None
    generated_anchor_id: str = ""
    kind: ContentBlockKind = ContentBlockKind.IMAGE

    def __post_init__(self) -> None:
        _coerce_enum_field(self, "kind", ContentBlockKind)
        if self.kind is not ContentBlockKind.IMAGE:
            raise ValueError("ImageBlock.kind must be image")
        _require_text(self.resource_id, "resource_id")
        for name in ("width_px", "height_px"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or value <= 0):
                raise ValueError(f"{name} must be positive when provided")


@dataclass(frozen=True, slots=True)
class PageBreakBlock:
    kind: ContentBlockKind = ContentBlockKind.PAGE_BREAK

    def __post_init__(self) -> None:
        _coerce_enum_field(self, "kind", ContentBlockKind)
        if self.kind is not ContentBlockKind.PAGE_BREAK:
            raise ValueError("PageBreakBlock.kind must be page_break")


ContentBlock = (
    HeadingBlock
    | ParagraphBlock
    | ListBlock
    | TableBlock
    | ImageBlock
    | PageBreakBlock
)


@dataclass(frozen=True, slots=True)
class DocumentFragment:
    """Source-neutral semantic content produced by every importer."""

    blocks: tuple[ContentBlock, ...]

    def __post_init__(self) -> None:
        blocks = tuple(self.blocks or ())
        supported = (
            HeadingBlock,
            ParagraphBlock,
            ListBlock,
            TableBlock,
            ImageBlock,
            PageBreakBlock,
        )
        if any(not isinstance(block, supported) for block in blocks):
            raise TypeError("blocks contain an unsupported content block")
        object.__setattr__(self, "blocks", blocks)

    def to_dict(self) -> dict[str, object]:
        return {
            "blocks": [_block_to_dict(block) for block in self.blocks],
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @property
    def digest(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "DocumentFragment":
        raw_blocks = payload.get("blocks", ())
        if not isinstance(raw_blocks, Sequence) or isinstance(raw_blocks, (str, bytes)):
            raise TypeError("blocks must be a sequence")
        blocks = tuple(_block_from_dict(item) for item in raw_blocks)
        return cls(blocks=blocks)


def content_anchor_token(content_id: str) -> str:
    """Return the one canonical token for a content id."""

    _validate_content_id(content_id)
    return material_token(MaterialTokenNamespace.FILE, content_id)


def normalize_content_resource_path(value: str) -> str:
    """Normalize a package-local resource path and reject traversal."""

    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError("relative_path must not be empty")
    if PurePosixPath(raw).is_absolute() or PureWindowsPath(raw).is_absolute():
        raise ValueError("relative_path must be package-relative")
    parts = [part for part in PurePosixPath(raw).parts if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise ValueError("relative_path must not traverse outside its package root")
    normalized = PurePosixPath(*parts).as_posix()
    if normalized.endswith("/"):
        raise ValueError("relative_path must identify a file")
    return normalized


def _block_to_dict(block: ContentBlock) -> dict[str, object]:
    payload: dict[str, object] = {"kind": block.kind.value}
    if isinstance(block, HeadingBlock):
        payload.update(level=block.level, inlines=_inlines_to_dict(block.inlines))
    elif isinstance(block, ParagraphBlock):
        payload["inlines"] = _inlines_to_dict(block.inlines)
    elif isinstance(block, ListBlock):
        payload.update(
            ordered=block.ordered,
            start=block.start,
            nesting=block.nesting,
            number_format=block.number_format.value,
            marker_template=block.marker_template,
            items=[{"inlines": _inlines_to_dict(item.inlines)} for item in block.items],
        )
    elif isinstance(block, TableBlock):
        payload["rows"] = [
            {
                "cells": [
                    {
                        "blocks": [_block_to_dict(item) for item in cell.blocks],
                        "rowspan": cell.rowspan,
                        "colspan": cell.colspan,
                    }
                    for cell in row.cells
                ]
            }
            for row in block.rows
        ]
    elif isinstance(block, ImageBlock):
        payload.update(
            resource_id=block.resource_id,
            alt_text=block.alt_text,
            caption=block.caption,
            width_px=block.width_px,
            height_px=block.height_px,
            generated_anchor_id=block.generated_anchor_id,
        )
    return payload


def _block_from_dict(payload: object) -> ContentBlock:
    if not isinstance(payload, Mapping):
        raise TypeError("each block must be a mapping")
    try:
        kind = ContentBlockKind(str(payload.get("kind", "") or ""))
    except ValueError as exc:
        raise ValueError(f"unsupported content block kind: {payload.get('kind')!r}") from exc
    if kind is ContentBlockKind.HEADING:
        return HeadingBlock(
            level=_as_int(payload.get("level", 0), "level"),
            inlines=_inlines_from_payload(payload.get("inlines", ())),
        )
    if kind is ContentBlockKind.PARAGRAPH:
        return ParagraphBlock(inlines=_inlines_from_payload(payload.get("inlines", ())))
    if kind is ContentBlockKind.LIST:
        raw_items = payload.get("items", ())
        if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes)):
            raise TypeError("list items must be a sequence")
        items: list[ListItem] = []
        for item in raw_items:
            if not isinstance(item, Mapping):
                raise TypeError("each list item must be a mapping")
            items.append(ListItem(_inlines_from_payload(item.get("inlines", ()))))
        return ListBlock(
            ordered=bool(payload.get("ordered", False)),
            start=_as_int(payload.get("start", 1), "start"),
            nesting=_as_int(payload.get("nesting", 0), "nesting"),
            items=tuple(items),
            number_format=(
                str(payload.get("number_format", "") or "") or None
            ),
            marker_template=str(payload.get("marker_template", "") or ""),
        )
    if kind is ContentBlockKind.TABLE:
        raw_rows = payload.get("rows", ())
        if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
            raise TypeError("table rows must be a sequence")
        rows: list[TableRow] = []
        for raw_row in raw_rows:
            if not isinstance(raw_row, Mapping):
                raise TypeError("each table row must be a mapping")
            raw_cells = raw_row.get("cells", ())
            if not isinstance(raw_cells, Sequence) or isinstance(raw_cells, (str, bytes)):
                raise TypeError("table cells must be a sequence")
            cells: list[TableCell] = []
            for raw_cell in raw_cells:
                if not isinstance(raw_cell, Mapping):
                    raise TypeError("each table cell must be a mapping")
                cells.append(
                    TableCell(
                        tuple(
                            _block_from_dict(item)
                            for item in _sequence_payload(
                                raw_cell.get("blocks", ()),
                                "table cell blocks",
                            )
                        ),
                        rowspan=_as_int(raw_cell.get("rowspan", 1), "rowspan"),
                        colspan=_as_int(raw_cell.get("colspan", 1), "colspan"),
                    )
                )
            rows.append(TableRow(tuple(cells)))
        return TableBlock(tuple(rows))
    if kind is ContentBlockKind.IMAGE:
        return ImageBlock(
            resource_id=str(payload.get("resource_id", "") or ""),
            alt_text=str(payload.get("alt_text", "") or ""),
            caption=str(payload.get("caption", "") or ""),
            width_px=_as_optional_int(payload.get("width_px"), "width_px"),
            height_px=_as_optional_int(payload.get("height_px"), "height_px"),
            generated_anchor_id=str(payload.get("generated_anchor_id", "") or ""),
        )
    return PageBreakBlock()


def _inlines_to_dict(inlines: Sequence[InlineContent]) -> list[dict[str, object]]:
    return [inline.to_dict() for inline in inlines]


def _inlines_from_payload(payload: object) -> tuple[InlineContent, ...]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise TypeError("inlines must be a sequence")
    return tuple(
        InlineContent.from_dict(item)
        if isinstance(item, Mapping)
        else _raise_type("each inline must be a mapping")
        for item in payload
    )


def _normalize_inlines(instance: object, field_name: str) -> None:
    values = tuple(getattr(instance, field_name) or ())
    if any(not isinstance(value, InlineContent) for value in values):
        raise TypeError(f"{field_name} must contain only InlineContent values")
    object.__setattr__(instance, field_name, values)


def _sequence_payload(payload: object, label: str) -> Sequence[object]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise TypeError(f"{label} must be a sequence")
    return payload


def _validate_table_grid(rows: Sequence[TableRow]) -> None:
    if not rows:
        return
    active: dict[int, int] = {}
    expected_width: int | None = None
    for row in rows:
        occupied = set(active)
        next_active = {
            column: remaining - 1
            for column, remaining in active.items()
            if remaining > 1
        }
        cursor = 0
        for cell in row.cells:
            while cursor in occupied:
                cursor += 1
            columns = range(cursor, cursor + cell.colspan)
            if any(column in occupied for column in columns):
                raise ValueError("table cell spans overlap")
            occupied.update(columns)
            if cell.rowspan > 1:
                for column in columns:
                    next_active[column] = cell.rowspan - 1
            cursor += cell.colspan
        width = max(occupied, default=-1) + 1
        if width < 1:
            raise ValueError("table rows must not be empty")
        if expected_width is None:
            expected_width = width
        elif width != expected_width:
            raise ValueError("table rows do not form one logical grid")
        active = next_active
    if active:
        raise ValueError("table rowspan extends beyond the final row")


def _validate_content_id(value: str) -> None:
    text = str(value or "")
    if not _CONTENT_ID_PATTERN.fullmatch(text):
        raise ValueError(
            "content_id must be non-empty and contain no whitespace, braces, or colon"
        )


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _validate_sha256(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a lowercase 64-character SHA-256")


def _validate_byte_size(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("byte_size must be an integer")
    if value < 0:
        raise ValueError("byte_size cannot be negative")


EnumType = TypeVar("EnumType", bound=Enum)


def _coerce_enum_field(instance: object, name: str, enum_type: type[EnumType]) -> None:
    raw_value = getattr(instance, name)
    try:
        value = raw_value if isinstance(raw_value, enum_type) else enum_type(str(raw_value))
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(f"{name} must be one of: {allowed}") from exc
    object.__setattr__(instance, name, value)


def _as_int(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be an integer") from exc


def _as_optional_int(value: object, field_name: str) -> int | None:
    return None if value is None else _as_int(value, field_name)


def _raise_type(message: str):
    raise TypeError(message)


__all__ = [
    "ContentBlock",
    "ContentBlockKind",
    "ContentFormatMode",
    "ContentHeadingPolicy",
    "ContentInsertionRule",
    "ContentOccurrencePolicy",
    "ContentPageBreakPolicy",
    "DocumentFragment",
    "FileAssetRef",
    "HeadingBlock",
    "ImageBlock",
    "InlineContent",
    "InlineKind",
    "InlineVerticalAlignment",
    "ListBlock",
    "ListItem",
    "ListNumberFormat",
    "PageBreakBlock",
    "ParagraphBlock",
    "TableBlock",
    "TableCell",
    "TableRow",
    "content_anchor_token",
    "normalize_content_resource_path",
]
