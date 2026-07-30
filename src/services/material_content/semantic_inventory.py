"""Deterministic semantic inventory for content-fragment acceptance checks."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256

from src.config.content_materials import (
    DocumentFragment,
    HeadingBlock,
    ImageBlock,
    InlineContent,
    InlineKind,
    ListBlock,
    PageBreakBlock,
    ParagraphBlock,
    TableBlock,
)
from src.shared.engine.material_token_contract import normalize_material_token
from src.services.material_content.import_contract import ContentSemanticInventory


def inventory_document_fragment(fragment: DocumentFragment) -> ContentSemanticInventory:
    """Project one fragment into stable counts and normalized visible text."""

    if not isinstance(fragment, DocumentFragment):
        raise TypeError("fragment must be a DocumentFragment")
    block_counts: Counter[str] = Counter()
    text_records: list[str] = []
    heading_count = 0
    list_item_count = 0
    table_cell_count = 0
    image_count = 0
    field_token_count = 0
    page_break_count = 0

    def inline_text(inlines: tuple[InlineContent, ...]) -> str:
        nonlocal field_token_count
        output: list[str] = []
        for inline in inlines:
            if inline.kind is InlineKind.FIELD_TOKEN:
                field_token_count += 1
                output.append(normalize_material_token(inline.field_key))
            elif inline.kind is InlineKind.SOFT_BREAK:
                output.append(" ")
            elif inline.kind is InlineKind.HARD_BREAK:
                output.append("\n")
            else:
                output.append(inline.text)
        return "".join(output)

    for block_index, block in enumerate(fragment.blocks):
        block_name = str(getattr(block.kind, "value", block.kind))
        block_counts[block_name] += 1
        if isinstance(block, HeadingBlock):
            heading_count += 1
            text_records.append(
                f"{block_index}:heading:{block.level}:{inline_text(block.inlines)}"
            )
        elif isinstance(block, ParagraphBlock):
            text_records.append(
                f"{block_index}:paragraph:{inline_text(block.inlines)}"
            )
        elif isinstance(block, ListBlock):
            for item_index, item in enumerate(block.items):
                list_item_count += 1
                text_records.append(
                    f"{block_index}:list:{int(block.ordered)}:{block.start}:"
                    f"{block.nesting}:{item_index}:{inline_text(item.inlines)}"
                )
        elif isinstance(block, TableBlock):
            for row_index, row in enumerate(block.rows):
                for column_index, cell in enumerate(row.cells):
                    table_cell_count += 1
                    cell_records: list[str] = []
                    for cell_block in cell.blocks:
                        if isinstance(cell_block, ParagraphBlock):
                            cell_records.append(inline_text(cell_block.inlines))
                        elif isinstance(cell_block, ListBlock):
                            for item in cell_block.items:
                                list_item_count += 1
                                cell_records.append(inline_text(item.inlines))
                        elif isinstance(cell_block, ImageBlock):
                            image_count += 1
                            cell_records.append(f"[image:{cell_block.resource_id}]")
                    text_records.append(
                        f"{block_index}:table:{row_index}:{column_index}:"
                        f"{cell.rowspan}:{cell.colspan}:{'|'.join(cell_records)}"
                    )
        elif isinstance(block, ImageBlock):
            image_count += 1
            text_records.append(
                f"{block_index}:image:{block.resource_id}:{block.alt_text}:"
                f"{block.width_px or 0}:{block.height_px or 0}"
            )
        elif isinstance(block, PageBreakBlock):
            page_break_count += 1
            text_records.append(f"{block_index}:page_break")

    normalized_text = "\n".join(text_records).encode("utf-8")
    return ContentSemanticInventory(
        normalized_text_sha256=sha256(normalized_text).hexdigest(),
        block_counts=tuple(block_counts.items()),
        heading_count=heading_count,
        list_item_count=list_item_count,
        table_cell_count=table_cell_count,
        image_count=image_count,
        field_token_count=field_token_count,
        page_break_count=page_break_count,
    )


__all__ = ["inventory_document_fragment"]
