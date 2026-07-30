"""Extract source-neutral material token blocks from a loaded DOCX."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from docx.oxml.ns import qn

from src.shared.engine.material_token_router import TokenTextBlock


@dataclass(frozen=True, slots=True)
class DocxMaterialTokenBlocks:
    blocks: tuple[TokenTextBlock, ...]
    direct_body_blocks: Mapping[str, tuple[object, int]]

    def __post_init__(self) -> None:
        blocks = tuple(self.blocks or ())
        if any(not isinstance(item, TokenTextBlock) for item in blocks):
            raise TypeError("blocks must contain TokenTextBlock values")
        object.__setattr__(self, "blocks", blocks)
        object.__setattr__(
            self,
            "direct_body_blocks",
            MappingProxyType(dict(self.direct_body_blocks or {})),
        )


def extract_docx_material_token_blocks(document) -> DocxMaterialTokenBlocks:
    """Return all Word story paragraphs plus direct-body mutation anchors."""

    if not hasattr(document, "element") or not hasattr(document.element, "body"):
        raise TypeError("document must be a python-docx Document")
    blocks: list[TokenTextBlock] = []
    direct: dict[str, tuple[object, int]] = {}
    body = document.element.body
    nested_index = 0
    for paragraph in body.iter(qn("w:p")):
        parent = paragraph.getparent()
        if parent is body:
            # lxml may hand out different Python proxies for the same node;
            # identity-based maps are therefore unsafe here.
            body_index = body.index(paragraph)
            block_id = f"body-p-{body_index:06d}"
            surface = "body"
            direct[block_id] = (paragraph, body_index)
        else:
            block_id = f"body-nested-p-{nested_index:06d}"
            surface = "table_or_nested_body"
            nested_index += 1
        blocks.append(
            TokenTextBlock.from_runs(
                block_id,
                paragraph_text_fragments(paragraph),
                surface=surface,
                story_id="main-document",
            )
        )

    seen_roots: set[int] = {id(document.element)}
    story_index = 0
    for part in document.part.package.parts:
        root = getattr(part, "_element", None)
        if root is None or id(root) in seen_roots:
            continue
        seen_roots.add(id(root))
        if root.tag == qn("w:hdr"):
            surface = "header"
        elif root.tag == qn("w:ftr"):
            surface = "footer"
        else:
            paragraphs = tuple(root.iter(qn("w:p")))
            if not paragraphs:
                continue
            surface = "other_story"
        paragraphs = tuple(root.iter(qn("w:p")))
        part_name = str(getattr(part, "partname", f"part-{story_index}"))
        for paragraph_index, paragraph in enumerate(paragraphs):
            blocks.append(
                TokenTextBlock.from_runs(
                    f"story-{story_index:04d}-p-{paragraph_index:06d}",
                    paragraph_text_fragments(paragraph),
                    surface=surface,
                    story_id=part_name,
                )
            )
        story_index += 1
    return DocxMaterialTokenBlocks(tuple(blocks), direct)


def paragraph_text_fragments(paragraph) -> tuple[str, ...]:
    return tuple(item.text or "" for item in paragraph.iter(qn("w:t")))


def is_strict_material_token_paragraph(paragraph, token: str) -> bool:
    """Return whether a token is isolated in plain Word runs.

    Paragraph properties are allowed because each mutation owner validates
    its own unsafe properties (for example ``sectPr``) with a domain-specific
    diagnostic.  Every other direct child must be a plain run containing only
    run properties and text nodes, so removing the paragraph cannot silently
    discard bookmarks, fields, drawings, hyperlinks, or other OOXML state.
    """

    text = "".join(paragraph_text_fragments(paragraph))
    if text.count(token) != 1 or text.replace(token, "").strip():
        return False
    for child in paragraph:
        if child.tag == qn("w:pPr"):
            continue
        if child.tag != qn("w:r"):
            return False
        for run_child in child:
            if run_child.tag not in {qn("w:rPr"), qn("w:t")}:
                return False
    return True


__all__ = [
    "DocxMaterialTokenBlocks",
    "extract_docx_material_token_blocks",
    "is_strict_material_token_paragraph",
    "paragraph_text_fragments",
]
