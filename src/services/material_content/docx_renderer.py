"""Render source-neutral content IR into a target DOCX document.

This module consumes only ``DocumentFragment`` and ``ContentInsertionRule``.
It deliberately has no knowledge of Markdown, source DOCX XML, or importer
implementation details.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import re
from typing import TYPE_CHECKING, Sequence
from urllib.parse import urlsplit

from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

from src.config.content_materials import (
    ContentHeadingPolicy,
    ContentInsertionRule,
    ContentOccurrencePolicy,
    ContentPageBreakPolicy,
    ContentResourceKey,
    DocumentFragment,
    HeadingBlock,
    ImageBlock,
    InlineContent,
    InlineKind,
    ListBlock,
    ListNumberFormat,
    PageBreakBlock,
    ParagraphBlock,
    TableBlock,
)
from src.shared.engine.docx_material_tokens import (
    is_strict_material_token_paragraph,
)
from src.shared.engine.material_token_contract import normalize_material_token

if TYPE_CHECKING:
    from docx.document import Document as DocumentType


_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
_HEADING_STYLE_RE = re.compile(r"^heading\s*([1-9])$", re.IGNORECASE)


class ContentRenderSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class ContentRenderDiagnostic:
    severity: ContentRenderSeverity
    code: str
    message: str
    rule_id: str
    anchor_token: str
    occurrence_index: int | None = None
    block_index: int | None = None
    surface: str = "body"


@dataclass(frozen=True, slots=True)
class ContentImageJobDraft:
    job_id: str
    content_id: str
    resource_id: str
    stable_marker_id: str
    occurrence_id: str
    sequence: int
    reserved_docpr_id: int
    alt_text: str = ""
    width_px: int | None = None
    height_px: int | None = None

    @property
    def resource_key(self) -> ContentResourceKey:
        return ContentResourceKey(self.content_id, self.resource_id)


@dataclass(frozen=True, slots=True)
class ContentOccurrenceReceipt:
    occurrence_id: str
    original_body_index: int
    inserted_body_element_count: int


@dataclass(frozen=True, slots=True)
class ContentRenderPreflight:
    rule_id: str
    anchor_token: str
    anchor_count: int
    diagnostics: tuple[ContentRenderDiagnostic, ...]

    @property
    def ready(self) -> bool:
        return not any(
            item.severity is ContentRenderSeverity.ERROR
            for item in self.diagnostics
        )


@dataclass(frozen=True, slots=True)
class ContentRenderReceipt:
    rule_id: str
    content_id: str
    anchor_token: str
    occurrence_count: int
    rendered_block_count: int
    inserted_body_element_count: int
    dropped_page_break_count: int
    image_job_drafts: tuple[ContentImageJobDraft, ...]
    occurrences: tuple[ContentOccurrenceReceipt, ...]
    diagnostics: tuple[ContentRenderDiagnostic, ...]


class ContentRenderBlockedError(ValueError):
    """Aggregate preflight failure; the target document is unchanged."""

    def __init__(self, diagnostics: Sequence[ContentRenderDiagnostic]):
        self.diagnostics = tuple(diagnostics)
        detail = "\n".join(
            f"- [{item.code}] {item.message}" for item in self.diagnostics
        )
        super().__init__(f"Content rendering blocked:\n{detail}")


@dataclass(frozen=True, slots=True)
class _AnchorPlan:
    element: object
    body_index: int
    occurrence_index: int
    occurrence_id: str
    heading_levels: tuple[int, ...]
    table_width_twips: int


@dataclass(frozen=True, slots=True)
class _RenderPlan:
    anchors: tuple[_AnchorPlan, ...]
    normal_style_id: str
    heading_style_ids: dict[int, str]
    table_style_id: str | None
    diagnostics: tuple[ContentRenderDiagnostic, ...]
    existing_bookmark_names: frozenset[str]
    next_bookmark_id: int
    next_docpr_id: int


class ContentDocxRenderer:
    """Strict two-step renderer: complete preflight, then one write pass."""

    def preflight(
        self,
        document: "DocumentType",
        fragment: DocumentFragment,
        rule: ContentInsertionRule,
    ) -> ContentRenderPreflight:
        plan, diagnostics, anchor_count = _build_render_plan(
            document, fragment, rule
        )
        del plan
        return ContentRenderPreflight(
            rule_id=rule.rule_id,
            anchor_token=rule.anchor_token,
            anchor_count=anchor_count,
            diagnostics=tuple(diagnostics),
        )

    def render(
        self,
        document: "DocumentType",
        fragment: DocumentFragment,
        rule: ContentInsertionRule,
    ) -> ContentRenderReceipt:
        plan, diagnostics, _anchor_count = _build_render_plan(
            document, fragment, rule
        )
        errors = [
            item
            for item in diagnostics
            if item.severity is ContentRenderSeverity.ERROR
        ]
        if errors:
            raise ContentRenderBlockedError(errors)
        if plan is None:
            return ContentRenderReceipt(
                rule_id=rule.rule_id,
                content_id=rule.content_id,
                anchor_token=rule.anchor_token,
                occurrence_count=0,
                rendered_block_count=0,
                inserted_body_element_count=0,
                dropped_page_break_count=0,
                image_job_drafts=(),
                occurrences=(),
                diagnostics=tuple(diagnostics),
            )
        return _commit_render_plan(document, fragment, rule, plan)


def render_document_fragment(
    document: "DocumentType",
    fragment: DocumentFragment,
    rule: ContentInsertionRule,
) -> ContentRenderReceipt:
    """Convenience API for the strict renderer."""

    return ContentDocxRenderer().render(document, fragment, rule)


def _build_render_plan(document, fragment, rule):
    if not isinstance(fragment, DocumentFragment):
        raise TypeError("fragment must be a DocumentFragment")
    if not isinstance(rule, ContentInsertionRule):
        raise TypeError("rule must be a ContentInsertionRule")

    diagnostics: list[ContentRenderDiagnostic] = []
    body = document.element.body
    body_children = list(body)
    direct_paragraphs = [item for item in body_children if item.tag == qn("w:p")]
    direct_ids = {id(item) for item in direct_paragraphs}
    candidates: list[tuple[object, int]] = []

    for paragraph in body.iter(qn("w:p")):
        text = _paragraph_text(paragraph)
        if rule.anchor_token not in text:
            continue
        if id(paragraph) not in direct_ids or paragraph.getparent() is not body:
            diagnostics.append(
                _diagnostic(
                    rule,
                    "anchor_forbidden_surface",
                    "content anchor occurs outside a direct body paragraph",
                    surface="table_or_nested_body",
                )
            )
            continue
        body_index = body_children.index(paragraph)
        if not is_strict_material_token_paragraph(
            paragraph,
            rule.anchor_token,
        ):
            diagnostics.append(
                _diagnostic(
                    rule,
                    "anchor_not_isolated",
                    "content anchor paragraph contains non-whitespace text or unsupported XML",
                    surface="body",
                )
            )
            continue
        paragraph_properties = paragraph.find(qn("w:pPr"))
        if (
            paragraph_properties is not None
            and paragraph_properties.find(qn("w:sectPr")) is not None
        ):
            diagnostics.append(
                _diagnostic(
                    rule,
                    "anchor_section_boundary_unsupported",
                    "content anchor paragraph carries a section boundary and cannot be removed safely",
                    surface="body",
                )
            )
            continue
        candidates.append((paragraph, body_index))

    for root, surface in _non_document_story_roots(document):
        for paragraph in root.iter(qn("w:p")):
            if rule.anchor_token in _paragraph_text(paragraph):
                diagnostics.append(
                    _diagnostic(
                        rule,
                        "anchor_forbidden_surface",
                        f"content anchor occurs in {surface}",
                        surface=surface,
                    )
                )

    anchor_count = len(candidates)
    if anchor_count == 0 and rule.required:
        diagnostics.append(
            _diagnostic(rule, "anchor_missing", "required content anchor was not found")
        )
    if (
        rule.occurrence_policy is ContentOccurrencePolicy.EXACTLY_ONE
        and anchor_count != 1
        and (anchor_count > 0 or rule.required)
    ):
        diagnostics.append(
            _diagnostic(
                rule,
                "anchor_occurrence_mismatch",
                f"exactly_one requires one strict anchor, found {anchor_count}",
            )
        )
    if not fragment.blocks and anchor_count:
        diagnostics.append(
            _diagnostic(rule, "empty_fragment", "content fragment has no blocks")
        )

    normal_style_id = _semantic_style_id(document, "Normal")
    table_style_id = _semantic_table_style_id(document, "Table Grid")
    if normal_style_id is None and anchor_count:
        diagnostics.append(
            _diagnostic(rule, "normal_style_missing", "target Normal paragraph style is missing")
        )

    diagnostics.extend(_validate_fragment_blocks(document, fragment, rule))
    headings = tuple(
        block for block in fragment.blocks if isinstance(block, HeadingBlock)
    )
    shallowest = min((block.level for block in headings), default=1)
    heading_style_ids: dict[int, str] = {}
    anchor_plans: list[_AnchorPlan] = []
    fragment_fingerprint = _fragment_fingerprint(fragment, rule)

    for occurrence_index, (element, body_index) in enumerate(candidates):
        levels: list[int] = []
        baseline = None
        if headings and rule.heading_policy is ContentHeadingPolicy.RELATIVE_TO_ANCHOR:
            baseline = _nearest_preceding_heading_level(body_children, body_index)
            if baseline is None:
                diagnostics.append(
                    _diagnostic(
                        rule,
                        "relative_heading_baseline_missing",
                        "relative_to_anchor requires a preceding target heading",
                        occurrence_index=occurrence_index,
                    )
                )
        for block in headings:
            if rule.heading_policy is ContentHeadingPolicy.PRESERVE:
                target_level = block.level + rule.heading_level_offset
            else:
                target_level = (
                    0
                    if baseline is None
                    else baseline + 1 + (block.level - shallowest)
                ) + rule.heading_level_offset
            levels.append(target_level)
            if not 1 <= target_level <= 9:
                diagnostics.append(
                    _diagnostic(
                        rule,
                        "heading_level_out_of_range",
                        f"resolved heading level {target_level} is outside 1..9",
                        occurrence_index=occurrence_index,
                    )
                )
                continue
            style_id = _semantic_style_id(document, f"Heading {target_level}")
            if style_id is None:
                diagnostics.append(
                    _diagnostic(
                        rule,
                        "heading_style_missing",
                        f"target Heading {target_level} style is missing",
                        occurrence_index=occurrence_index,
                    )
                )
            else:
                heading_style_ids[target_level] = style_id

        occurrence_digest = sha256(
            f"{fragment_fingerprint}:{body_index}:{occurrence_index}".encode("utf-8")
        ).hexdigest()
        anchor_plans.append(
            _AnchorPlan(
                element=element,
                body_index=body_index,
                occurrence_index=occurrence_index,
                occurrence_id=f"content-occ-{occurrence_digest[:16]}",
                heading_levels=tuple(levels),
                table_width_twips=_available_width_twips(document, body_index),
            )
        )

    if diagnostics and any(
        item.severity is ContentRenderSeverity.ERROR for item in diagnostics
    ):
        return None, diagnostics, anchor_count
    if not anchor_plans:
        return None, diagnostics, anchor_count

    bookmark_names, max_bookmark_id, max_docpr_id = _existing_marker_state(document)
    return (
        _RenderPlan(
            anchors=tuple(anchor_plans),
            normal_style_id=normal_style_id or "Normal",
            heading_style_ids=heading_style_ids,
            table_style_id=table_style_id,
            diagnostics=tuple(diagnostics),
            existing_bookmark_names=frozenset(bookmark_names),
            next_bookmark_id=max_bookmark_id + 1,
            next_docpr_id=max_docpr_id + 1,
        ),
        diagnostics,
        anchor_count,
    )


def _validate_fragment_blocks(document, fragment, rule):
    diagnostics: list[ContentRenderDiagnostic] = []
    has_list = False
    for block_index, block in enumerate(fragment.blocks):
        inline_groups: list[Sequence[InlineContent]] = []
        if isinstance(block, (HeadingBlock, ParagraphBlock)):
            inline_groups.append(block.inlines)
            if isinstance(block, HeadingBlock) and not block.inlines:
                diagnostics.append(
                    _diagnostic(rule, "empty_heading", "heading block is empty", block_index=block_index)
                )
        elif isinstance(block, ListBlock):
            has_list = True
            if not 0 <= block.nesting <= 8:
                diagnostics.append(
                    _diagnostic(
                        rule,
                        "list_nesting_unsupported",
                        "list nesting must be within 0..8",
                        block_index=block_index,
                    )
                )
            if not block.items:
                diagnostics.append(
                    _diagnostic(rule, "empty_list", "list block has no items", block_index=block_index)
                )
            inline_groups.extend(item.inlines for item in block.items)
        elif isinstance(block, TableBlock):
            if not block.rows or not block.rows[0].cells:
                diagnostics.append(
                    _diagnostic(rule, "empty_table", "table block must be non-empty", block_index=block_index)
                )
            try:
                _logical_table_layout(block)
            except ValueError as exc:
                diagnostics.append(
                    _diagnostic(
                        rule,
                        "table_not_rectangular",
                        str(exc),
                        block_index=block_index,
                    )
                )
            for row in block.rows:
                for cell in row.cells:
                    for cell_block in cell.blocks:
                        if isinstance(cell_block, ParagraphBlock):
                            inline_groups.append(cell_block.inlines)
                        elif isinstance(cell_block, ListBlock):
                            has_list = True
                            inline_groups.extend(
                                item.inlines for item in cell_block.items
                            )
                        elif isinstance(cell_block, ImageBlock):
                            pass
        elif isinstance(block, (ImageBlock, PageBreakBlock)):
            pass
        else:  # pragma: no cover - DocumentFragment enforces the union
            diagnostics.append(
                _diagnostic(rule, "unsupported_block", f"unsupported block: {type(block).__name__}", block_index=block_index)
            )

        for inlines in inline_groups:
            diagnostics.extend(_validate_inlines(inlines, rule, block_index))

    if has_list:
        try:
            document.part.numbering_part
        except Exception:
            diagnostics.append(
                _diagnostic(rule, "numbering_part_missing", "target document has no numbering part")
            )
    if any(isinstance(block, PageBreakBlock) for block in fragment.blocks) and (
        rule.page_break_policy is ContentPageBreakPolicy.DROP
    ):
        diagnostics.append(
            _diagnostic(
                rule,
                "page_break_dropped",
                "explicit source page break will be dropped by policy",
                severity=ContentRenderSeverity.WARNING,
            )
        )
    return diagnostics


def _validate_inlines(inlines, rule, block_index):
    diagnostics: list[ContentRenderDiagnostic] = []
    for inline in inlines:
        if inline.kind is InlineKind.HYPERLINK:
            if not inline.text:
                diagnostics.append(
                    _diagnostic(rule, "hyperlink_text_missing", "hyperlink display text is empty", block_index=block_index)
                )
            if not _allowed_external_href(inline.href):
                diagnostics.append(
                    _diagnostic(
                        rule,
                        "hyperlink_protocol_unsupported",
                        f"unsupported hyperlink target: {inline.href!r}",
                        block_index=block_index,
                    )
                )
        elif inline.kind is InlineKind.FIELD_TOKEN:
            if (
                not inline.field_key
                or inline.field_key.strip() != inline.field_key
                or any(char in inline.field_key for char in "{}\r\n")
            ):
                diagnostics.append(
                    _diagnostic(rule, "field_token_invalid", "field token key is not canonical", block_index=block_index)
                )
            if inline.text:
                diagnostics.append(
                    _diagnostic(
                        rule,
                        "field_token_payload_unsupported",
                        "field token inline must not carry ignored literal text",
                        block_index=block_index,
                    )
                )
        elif inline.kind in (
            InlineKind.SOFT_BREAK,
            InlineKind.HARD_BREAK,
            InlineKind.TAB,
        ):
            if inline.text or inline.href or inline.field_key:
                diagnostics.append(
                    _diagnostic(
                        rule,
                        "control_inline_invalid",
                        "break/tab inline must not contain text or references",
                        block_index=block_index,
                    )
                )
    return diagnostics


def _commit_render_plan(document, fragment, rule, plan):
    bookmark_names = set(plan.existing_bookmark_names)
    next_bookmark_id = plan.next_bookmark_id
    next_docpr_id = plan.next_docpr_id
    image_jobs: list[ContentImageJobDraft] = []
    occurrence_receipts: list[ContentOccurrenceReceipt] = []
    dropped_breaks = 0
    inserted_elements_total = 0
    image_sequence = 0
    fragment_fingerprint = _fragment_fingerprint(fragment, rule)

    def image_sentinel(block: ImageBlock, identity: str, occurrence_id: str):
        nonlocal next_bookmark_id, next_docpr_id, image_sequence
        salt = (
            f"{fragment_fingerprint}:{occurrence_id}:{identity}:"
            f"{block.resource_id}:{block.generated_anchor_id}"
        )
        marker_id = _unique_marker_id(salt, bookmark_names)
        bookmark_names.add(marker_id)
        job_digest = sha256(f"{salt}:{marker_id}".encode("utf-8")).hexdigest()
        paragraph = _image_sentinel_paragraph(
            plan.normal_style_id,
            marker_id,
            next_bookmark_id,
        )
        image_jobs.append(
            ContentImageJobDraft(
                job_id=f"content-image-{job_digest[:20]}",
                content_id=rule.content_id,
                resource_id=block.resource_id,
                stable_marker_id=marker_id,
                occurrence_id=occurrence_id,
                sequence=image_sequence,
                reserved_docpr_id=next_docpr_id,
                alt_text=block.alt_text,
                width_px=block.width_px,
                height_px=block.height_px,
            )
        )
        next_bookmark_id += 1
        next_docpr_id += 1
        image_sequence += 1
        return paragraph

    for anchor in plan.anchors:
        nodes: list[object] = []
        heading_cursor = 0
        for block_index, block in enumerate(fragment.blocks):
            if isinstance(block, HeadingBlock):
                level = anchor.heading_levels[heading_cursor]
                heading_cursor += 1
                nodes.append(
                    _paragraph_element(
                        document,
                        plan.heading_style_ids[level],
                        block.inlines,
                    )
                )
            elif isinstance(block, ParagraphBlock):
                nodes.append(
                    _paragraph_element(document, plan.normal_style_id, block.inlines)
                )
            elif isinstance(block, ListBlock):
                num_id = _add_numbering_definition(
                    document,
                    block.number_format,
                    start=block.start,
                    level=block.nesting,
                    marker_template=block.marker_template,
                )
                for item in block.items:
                    paragraph = _paragraph_element(
                        document, plan.normal_style_id, item.inlines
                    )
                    _apply_num_pr(paragraph, num_id, block.nesting)
                    nodes.append(paragraph)
            elif isinstance(block, TableBlock):
                nodes.append(
                    _table_element(
                        document,
                        block,
                        plan.normal_style_id,
                        plan.table_style_id,
                        anchor.table_width_twips,
                        image_factory=lambda image, identity: image_sentinel(
                            image,
                            f"{block_index}:{identity}",
                            anchor.occurrence_id,
                        ),
                    )
                )
            elif isinstance(block, PageBreakBlock):
                if rule.page_break_policy is ContentPageBreakPolicy.DROP:
                    dropped_breaks += 1
                    continue
                nodes.append(_page_break_paragraph(plan.normal_style_id))
            elif isinstance(block, ImageBlock):
                nodes.append(
                    image_sentinel(
                        block,
                        str(block_index),
                        anchor.occurrence_id,
                    )
                )

        parent = anchor.element.getparent()
        insert_at = parent.index(anchor.element)
        for offset, node in enumerate(nodes):
            parent.insert(insert_at + offset, node)
        parent.remove(anchor.element)
        inserted_elements_total += len(nodes)
        occurrence_receipts.append(
            ContentOccurrenceReceipt(
                occurrence_id=anchor.occurrence_id,
                original_body_index=anchor.body_index,
                inserted_body_element_count=len(nodes),
            )
        )

    return ContentRenderReceipt(
        rule_id=rule.rule_id,
        content_id=rule.content_id,
        anchor_token=rule.anchor_token,
        occurrence_count=len(plan.anchors),
        rendered_block_count=len(fragment.blocks) * len(plan.anchors),
        inserted_body_element_count=inserted_elements_total,
        dropped_page_break_count=dropped_breaks,
        image_job_drafts=tuple(image_jobs),
        occurrences=tuple(occurrence_receipts),
        diagnostics=plan.diagnostics,
    )


def _paragraph_element(document, style_id, inlines):
    paragraph = OxmlElement("w:p")
    _set_paragraph_style(paragraph, style_id)
    for inline in inlines:
        if inline.kind is InlineKind.SOFT_BREAK:
            paragraph.append(_run_element(" ", inline))
        elif inline.kind is InlineKind.HARD_BREAK:
            run = _run_element("", inline)
            run.append(OxmlElement("w:br"))
            paragraph.append(run)
        elif inline.kind is InlineKind.TAB:
            run = _run_element("", inline)
            run.append(OxmlElement("w:tab"))
            paragraph.append(run)
        elif inline.kind is InlineKind.HYPERLINK:
            relationship_id = document.part.relate_to(
                inline.href, RT.HYPERLINK, is_external=True
            )
            hyperlink = OxmlElement("w:hyperlink")
            hyperlink.set(qn("r:id"), relationship_id)
            hyperlink.append(_run_element(inline.text, inline, hyperlink=True))
            paragraph.append(hyperlink)
        elif inline.kind is InlineKind.FIELD_TOKEN:
            paragraph.append(
                _run_element(normalize_material_token(inline.field_key), inline)
            )
        else:
            paragraph.append(_run_element(inline.text, inline))
    return paragraph


def _run_element(text, inline, *, hyperlink=False):
    run = OxmlElement("w:r")
    if (
        inline.bold
        or inline.italic
        or inline.underline
        or inline.strikethrough
        or inline.vertical_alignment.value != "baseline"
        or hyperlink
    ):
        rpr = OxmlElement("w:rPr")
        if hyperlink:
            style = OxmlElement("w:rStyle")
            style.set(qn("w:val"), "Hyperlink")
            rpr.append(style)
        if inline.bold:
            rpr.append(OxmlElement("w:b"))
        if inline.italic:
            rpr.append(OxmlElement("w:i"))
        if inline.underline:
            underline = OxmlElement("w:u")
            underline.set(qn("w:val"), "single")
            rpr.append(underline)
        if inline.strikethrough:
            rpr.append(OxmlElement("w:strike"))
        if inline.vertical_alignment.value != "baseline":
            vertical = OxmlElement("w:vertAlign")
            vertical.set(qn("w:val"), inline.vertical_alignment.value)
            rpr.append(vertical)
        run.append(rpr)
    if text:
        text_element = OxmlElement("w:t")
        text_element.set(_XML_SPACE, "preserve")
        text_element.text = text
        run.append(text_element)
    return run


def _page_break_paragraph(style_id):
    paragraph = OxmlElement("w:p")
    _set_paragraph_style(paragraph, style_id)
    run = OxmlElement("w:r")
    page_break = OxmlElement("w:br")
    page_break.set(qn("w:type"), "page")
    run.append(page_break)
    paragraph.append(run)
    return paragraph


def _image_sentinel_paragraph(style_id, marker_id, bookmark_id):
    paragraph = OxmlElement("w:p")
    _set_paragraph_style(paragraph, style_id)
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(bookmark_id))
    start.set(qn("w:name"), marker_id)
    paragraph.append(start)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    rpr.append(OxmlElement("w:vanish"))
    rpr.append(OxmlElement("w:noProof"))
    run.append(rpr)
    text = OxmlElement("w:t")
    text.text = marker_id
    run.append(text)
    paragraph.append(run)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(bookmark_id))
    paragraph.append(end)
    return paragraph


def _table_element(
    document,
    block,
    normal_style_id,
    table_style_id,
    total_width,
    *,
    image_factory,
):
    column_count, layout_rows = _logical_table_layout(block)
    table_indent = 120
    usable_width = max(720, total_width - table_indent)
    base, remainder = divmod(usable_width, column_count)
    widths = [base + (1 if index < remainder else 0) for index in range(column_count)]
    table = OxmlElement("w:tbl")
    table_properties = OxmlElement("w:tblPr")
    if table_style_id:
        table_style = OxmlElement("w:tblStyle")
        table_style.set(qn("w:val"), table_style_id)
        table_properties.append(table_style)
    table_width = OxmlElement("w:tblW")
    table_width.set(qn("w:w"), str(sum(widths)))
    table_width.set(qn("w:type"), "dxa")
    table_properties.append(table_width)
    indent = OxmlElement("w:tblInd")
    indent.set(qn("w:w"), str(table_indent))
    indent.set(qn("w:type"), "dxa")
    table_properties.append(indent)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    table_properties.append(layout)
    cell_margins = OxmlElement("w:tblCellMar")
    for side, width in (("top", 80), ("left", 120), ("bottom", 80), ("right", 120)):
        margin = OxmlElement(f"w:{side}")
        margin.set(qn("w:w"), str(width))
        margin.set(qn("w:type"), "dxa")
        cell_margins.append(margin)
    table_properties.append(cell_margins)
    table.append(table_properties)
    grid = OxmlElement("w:tblGrid")
    for width in widths:
        column = OxmlElement("w:gridCol")
        column.set(qn("w:w"), str(width))
        grid.append(column)
    table.append(grid)
    for row_index, placements in enumerate(layout_rows):
        tr = OxmlElement("w:tr")
        for column_index, cell, continuation in placements:
            tc = OxmlElement("w:tc")
            tc_pr = OxmlElement("w:tcPr")
            tc_width = OxmlElement("w:tcW")
            cell_width = sum(widths[column_index : column_index + cell.colspan])
            tc_width.set(qn("w:w"), str(cell_width))
            tc_width.set(qn("w:type"), "dxa")
            tc_pr.append(tc_width)
            if cell.colspan > 1:
                grid_span = OxmlElement("w:gridSpan")
                grid_span.set(qn("w:val"), str(cell.colspan))
                tc_pr.append(grid_span)
            if cell.rowspan > 1:
                vertical_merge = OxmlElement("w:vMerge")
                if not continuation:
                    vertical_merge.set(qn("w:val"), "restart")
                tc_pr.append(vertical_merge)
            tc.append(tc_pr)
            if continuation:
                tc.append(_paragraph_element(document, normal_style_id, ()))
            else:
                for cell_block_index, cell_block in enumerate(cell.blocks):
                    if isinstance(cell_block, ParagraphBlock):
                        tc.append(
                            _paragraph_element(
                                document,
                                normal_style_id,
                                cell_block.inlines,
                            )
                        )
                    elif isinstance(cell_block, ListBlock):
                        num_id = _add_numbering_definition(
                            document,
                            cell_block.number_format,
                            start=cell_block.start,
                            level=cell_block.nesting,
                            marker_template=cell_block.marker_template,
                        )
                        for item in cell_block.items:
                            paragraph = _paragraph_element(
                                document,
                                normal_style_id,
                                item.inlines,
                            )
                            _apply_num_pr(paragraph, num_id, cell_block.nesting)
                            tc.append(paragraph)
                    elif isinstance(cell_block, ImageBlock):
                        tc.append(
                            image_factory(
                                cell_block,
                                f"table:{row_index}:{column_index}:"
                                f"{cell_block_index}",
                            )
                        )
            tr.append(tc)
        table.append(tr)
    return table


def _logical_table_layout(block):
    active: dict[int, tuple[object, int]] = {}
    rows: list[tuple[tuple[int, object, bool], ...]] = []
    expected_width: int | None = None
    for row in block.rows:
        occupied = set(active)
        next_active = {
            column: (cell, remaining - 1)
            for column, (cell, remaining) in active.items()
            if remaining > 1
        }
        origins: list[tuple[int, object, bool]] = []
        cursor = 0
        for cell in row.cells:
            while cursor in occupied:
                cursor += 1
            columns = range(cursor, cursor + cell.colspan)
            if any(column in occupied for column in columns):
                raise ValueError("table cell spans overlap")
            origins.append((cursor, cell, False))
            occupied.update(columns)
            if cell.rowspan > 1:
                for column in columns:
                    next_active[column] = (cell, cell.rowspan - 1)
            cursor += cell.colspan
        width = max(occupied, default=-1) + 1
        if width < 1:
            raise ValueError("table rows must not be empty")
        if expected_width is None:
            expected_width = width
        elif width != expected_width:
            raise ValueError("table rows do not form one logical grid")
        continuations: dict[int, tuple[int, object, bool]] = {}
        for column, (cell, _remaining) in active.items():
            identity = id(cell)
            existing = continuations.get(identity)
            if existing is None or column < existing[0]:
                continuations[identity] = (column, cell, True)
        rows.append(tuple(sorted((*origins, *continuations.values()), key=lambda item: item[0])))
        active = next_active
    if active:
        raise ValueError("table rowspan extends beyond the final row")
    return int(expected_width or 0), tuple(rows)


def _add_numbering_definition(
    document,
    number_format,
    *,
    start=1,
    level=0,
    marker_template="",
):
    if not isinstance(number_format, ListNumberFormat):
        number_format = ListNumberFormat(str(number_format))
    ordered = number_format is not ListNumberFormat.BULLET
    numbering = document.part.numbering_part.element
    abstract_ids = [
        _int_attr(item, "w:abstractNumId")
        for item in numbering.findall(qn("w:abstractNum"))
    ]
    num_ids = [
        _int_attr(item, "w:numId") for item in numbering.findall(qn("w:num"))
    ]
    abstract_id = max(abstract_ids, default=-1) + 1
    num_id = max(num_ids, default=0) + 1
    abstract = OxmlElement("w:abstractNum")
    abstract.set(qn("w:abstractNumId"), str(abstract_id))
    multi = OxmlElement("w:multiLevelType")
    multi.set(qn("w:val"), "hybridMultilevel")
    abstract.append(multi)
    bullets = ("•", "◦", "▪", "–", "○", "◆", "◇", "■", "□")
    for current_level in range(9):
        lvl = OxmlElement("w:lvl")
        lvl.set(qn("w:ilvl"), str(current_level))
        level_start = OxmlElement("w:start")
        level_start.set(qn("w:val"), "1")
        lvl.append(level_start)
        num_fmt = OxmlElement("w:numFmt")
        num_fmt.set(qn("w:val"), number_format.value)
        lvl.append(num_fmt)
        lvl_text = OxmlElement("w:lvlText")
        lvl_text.set(
            qn("w:val"),
            (
                marker_template
                if ordered and current_level == level and marker_template
                else f"%{current_level + 1}."
                if ordered
                else bullets[current_level]
            ),
        )
        lvl.append(lvl_text)
        ppr = OxmlElement("w:pPr")
        ind = OxmlElement("w:ind")
        ind.set(qn("w:left"), str(720 * (current_level + 1)))
        ind.set(qn("w:hanging"), "360")
        ppr.append(ind)
        lvl.append(ppr)
        abstract.append(lvl)
    # CT_Numbering requires every abstractNum before every num.  Appending an
    # abstract definition after existing num instances produces schema-invalid
    # numbering.xml even though some Word versions repair it on open.
    abstract_insert_at = next(
        (
            index
            for index, child in enumerate(numbering)
            if child.tag in {qn("w:num"), qn("w:numIdMac")}
        ),
        len(numbering),
    )
    numbering.insert(abstract_insert_at, abstract)
    num = OxmlElement("w:num")
    num.set(qn("w:numId"), str(num_id))
    abstract_ref = OxmlElement("w:abstractNumId")
    abstract_ref.set(qn("w:val"), str(abstract_id))
    num.append(abstract_ref)
    if ordered and start != 1:
        override = OxmlElement("w:lvlOverride")
        override.set(qn("w:ilvl"), str(level))
        start_override = OxmlElement("w:startOverride")
        start_override.set(qn("w:val"), str(start))
        override.append(start_override)
        num.append(override)
    num_id_mac = numbering.find(qn("w:numIdMac"))
    if num_id_mac is None:
        numbering.append(num)
    else:
        numbering.insert(numbering.index(num_id_mac), num)
    return num_id


def _apply_num_pr(paragraph, num_id, level):
    ppr = paragraph.find(qn("w:pPr"))
    num_pr = OxmlElement("w:numPr")
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), str(level))
    num = OxmlElement("w:numId")
    num.set(qn("w:val"), str(num_id))
    num_pr.append(ilvl)
    num_pr.append(num)
    ppr.append(num_pr)


def _set_paragraph_style(paragraph, style_id):
    ppr = paragraph.find(qn("w:pPr"))
    if ppr is None:
        ppr = OxmlElement("w:pPr")
        paragraph.insert(0, ppr)
    style = OxmlElement("w:pStyle")
    style.set(qn("w:val"), style_id)
    ppr.insert(0, style)


def _paragraph_text(paragraph):
    return "".join(item.text or "" for item in paragraph.iter(qn("w:t")))


def _non_document_story_roots(document):
    seen: set[int] = set()
    for part in document.part.package.parts:
        root = getattr(part, "_element", None)
        if root is None or id(root) in seen or root is document.element:
            continue
        seen.add(id(root))
        if root.tag == qn("w:hdr"):
            yield root, "header"
        elif root.tag == qn("w:ftr"):
            yield root, "footer"
        elif any(True for _ in root.iter(qn("w:p"))):
            local_name = str(root.tag).rsplit("}", 1)[-1]
            yield root, f"other_story:{local_name}"


def _semantic_style_id(document, semantic_name):
    normalized = semantic_name.replace(" ", "").casefold()
    for style in document.styles:
        if style.type is not WD_STYLE_TYPE.PARAGRAPH:
            continue
        style_id = str(style.style_id or "")
        name = str(style.name or "")
        if style_id.replace(" ", "").casefold() == normalized:
            return style_id
        if name.replace(" ", "").casefold() == normalized:
            return style_id
    return None


def _semantic_table_style_id(document, semantic_name):
    normalized = semantic_name.replace(" ", "").casefold()
    for style in document.styles:
        if style.type is not WD_STYLE_TYPE.TABLE:
            continue
        style_id = str(style.style_id or "")
        name = str(style.name or "")
        if style_id.replace(" ", "").casefold() == normalized:
            return style_id
        if name.replace(" ", "").casefold() == normalized:
            return style_id
    return None


def _nearest_preceding_heading_level(body_children, body_index):
    for element in reversed(body_children[:body_index]):
        if element.tag != qn("w:p"):
            continue
        ppr = element.find(qn("w:pPr"))
        if ppr is None:
            continue
        style = ppr.find(qn("w:pStyle"))
        if style is not None:
            raw = str(style.get(qn("w:val"), "") or "")
            match = _HEADING_STYLE_RE.match(raw.replace("_", " "))
            if match:
                return int(match.group(1))
            compact = re.match(r"^Heading([1-9])$", raw, re.IGNORECASE)
            if compact:
                return int(compact.group(1))
        outline = ppr.find(qn("w:outlineLvl"))
        if outline is not None:
            try:
                value = int(outline.get(qn("w:val"), "9"))
            except ValueError:
                continue
            if 0 <= value <= 8:
                return value + 1
    return None


def _allowed_external_href(href):
    try:
        parsed = urlsplit(href)
    except ValueError:
        return False
    scheme = parsed.scheme.casefold()
    if scheme in {"http", "https"}:
        return bool(parsed.netloc)
    if scheme == "mailto":
        return bool(parsed.path and "@" in parsed.path)
    return False


def _available_width_twips(document, body_index):
    section_index = 0
    for element in list(document.element.body)[:body_index]:
        if element.tag != qn("w:p"):
            continue
        ppr = element.find(qn("w:pPr"))
        if ppr is not None and ppr.find(qn("w:sectPr")) is not None:
            section_index += 1
    sections = document.sections
    section = sections[min(section_index, len(sections) - 1)]
    emu = int(section.page_width) - int(section.left_margin) - int(section.right_margin)
    return max(720, int(round(emu / 635)))


def _existing_marker_state(document):
    names: set[str] = set()
    max_bookmark_id = 0
    max_docpr_id = 0
    for part in document.part.package.parts:
        root = getattr(part, "_element", None)
        if root is None:
            continue
        for bookmark in root.iter(qn("w:bookmarkStart")):
            name = bookmark.get(qn("w:name"))
            if name:
                names.add(name)
            max_bookmark_id = max(max_bookmark_id, _int_attr(bookmark, "w:id"))
        for docpr in root.iter(qn("wp:docPr")):
            max_docpr_id = max(max_docpr_id, _int_attr(docpr, "id", qualified=False))
    return names, max_bookmark_id, max_docpr_id


def _unique_marker_id(salt, existing):
    attempt = 0
    while True:
        digest = sha256(f"{salt}:{attempt}".encode("utf-8")).hexdigest()
        marker = f"LarkContentImage_{digest[:20]}"
        if marker not in existing:
            return marker
        attempt += 1


def _fragment_fingerprint(fragment, rule):
    payload = {"fragment": fragment.to_dict(), "rule": rule.to_dict()}
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _int_attr(element, name, *, qualified=True):
    raw = element.get(qn(name) if qualified else name, "0")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _diagnostic(
    rule,
    code,
    message,
    *,
    severity=ContentRenderSeverity.ERROR,
    occurrence_index=None,
    block_index=None,
    surface="body",
):
    return ContentRenderDiagnostic(
        severity=severity,
        code=code,
        message=message,
        rule_id=rule.rule_id,
        anchor_token=rule.anchor_token,
        occurrence_index=occurrence_index,
        block_index=block_index,
        surface=surface,
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
