"""Strict direct-body visibility planning and mutation for delivery variants.

The first-version contract deliberately understands only direct ``w:p`` and
``w:tbl`` children of ``document.element.body``.  Visibility markers on any
nested surface are rejected before mutation.  Valid marker blocks are planned
against the original body order and removed in descending index order so a
table, a content-image sentinel, and surrounding paragraphs remain one atomic
visibility range.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Iterable, Mapping, Sequence

from docx.oxml.ns import qn

from src.shared.engine.content_visibility_contract import CONTENT_VISIBILITY_MARKER_RE


BLOCK_VISIBILITY_PLAN_VERSION = "block-visibility-plan-v1"
BLOCK_VISIBILITY_RECEIPT_VERSION = "block-visibility-receipt-v1"

_W_P = qn("w:p")
_W_TBL = qn("w:tbl")
_W_T = qn("w:t")
_W_BOOKMARK_START = qn("w:bookmarkStart")
_W_NAME = qn("w:name")
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
_CONTENT_IMAGE_MARKER_RE = re.compile(r"\b(?:LDWord|Lark)ContentImage_[A-Za-z0-9_.-]+\b")
_CONTENT_IMAGE_MARKER_PREFIX = "LDWordContentImage_"
_PARAGRAPH_PAYLOAD_TAGS = frozenset(
    {
        qn("w:bookmarkStart"),
        qn("w:bookmarkEnd"),
        qn("w:commentReference"),
        qn("w:drawing"),
        qn("w:endnoteReference"),
        qn("w:fldChar"),
        qn("w:footnoteReference"),
        qn("w:instrText"),
        qn("w:object"),
        qn("w:pict"),
    }
)


@dataclass(frozen=True, slots=True)
class BlockVisibilityDiagnostic:
    code: str
    message: str
    selector: str = ""
    body_index: int = -1
    location: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "selector": self.selector,
            "body_index": self.body_index,
            "location": self.location,
        }


class BlockVisibilityPlanError(ValueError):
    """Aggregate planning/apply failure raised before unsafe mutation."""

    def __init__(self, diagnostics: Sequence[BlockVisibilityDiagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        if not self.diagnostics:
            raise ValueError("BlockVisibilityPlanError requires diagnostics")
        detail = "\n".join(
            f"- [{item.code}] {item.message}" for item in self.diagnostics
        )
        super().__init__(f"Block visibility planning failed:\n{detail}")


@dataclass(frozen=True, slots=True)
class BlockVisibilityRange:
    selector: str
    start_body_index: int
    end_body_index: int
    body_element_count: int
    paragraph_count: int
    table_count: int
    content_image_markers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "selector": self.selector,
            "start_body_index": self.start_body_index,
            "end_body_index": self.end_body_index,
            "body_element_count": self.body_element_count,
            "paragraph_count": self.paragraph_count,
            "table_count": self.table_count,
            "content_image_markers": list(self.content_image_markers),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> BlockVisibilityRange:
        if not isinstance(payload, Mapping):
            raise TypeError("block visibility range payload must be a mapping")
        markers = payload.get("content_image_markers", ())
        if not isinstance(markers, (list, tuple)):
            raise TypeError("content_image_markers must be a sequence")
        return cls(
            selector=str(payload.get("selector", "") or ""),
            start_body_index=int(payload.get("start_body_index", 0)),
            end_body_index=int(payload.get("end_body_index", 0)),
            body_element_count=int(payload.get("body_element_count", 0)),
            paragraph_count=int(payload.get("paragraph_count", 0)),
            table_count=int(payload.get("table_count", 0)),
            content_image_markers=tuple(str(item) for item in markers),
        )


@dataclass(frozen=True, slots=True)
class BlockVisibilityMarkerParagraph:
    body_index: int
    marker_count: int
    selectors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "body_index": self.body_index,
            "marker_count": self.marker_count,
            "selectors": list(self.selectors),
        }


@dataclass(frozen=True, slots=True)
class BlockVisibilityPlan:
    plan_id: str
    contract_version: str
    body_sha256: str
    body_element_count: int
    remove_selectors: tuple[str, ...]
    matched_remove_selectors: tuple[str, ...]
    unmatched_remove_selectors: tuple[str, ...]
    remove_ranges: tuple[BlockVisibilityRange, ...]
    retained_marker_paragraphs: tuple[BlockVisibilityMarkerParagraph, ...]

    def __post_init__(self) -> None:
        if self.contract_version != BLOCK_VISIBILITY_PLAN_VERSION:
            raise ValueError("unsupported block visibility plan contract")
        supplied = str(self.plan_id or "").strip()
        computed = sha256(self.canonical_json().encode("utf-8")).hexdigest()
        if supplied and supplied != computed:
            raise ValueError("plan_id does not match canonical plan payload")
        object.__setattr__(self, "plan_id", computed)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "body_sha256": self.body_sha256,
            "body_element_count": self.body_element_count,
            "remove_selectors": list(self.remove_selectors),
            "matched_remove_selectors": list(self.matched_remove_selectors),
            "unmatched_remove_selectors": list(self.unmatched_remove_selectors),
            "remove_ranges": [item.to_dict() for item in self.remove_ranges],
            "retained_marker_paragraphs": [
                item.to_dict() for item in self.retained_marker_paragraphs
            ],
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def to_dict(self) -> dict[str, object]:
        return {"plan_id": self.plan_id, **self.canonical_payload()}


@dataclass(frozen=True, slots=True)
class BlockVisibilityReceipt:
    receipt_id: str
    contract_version: str
    plan_id: str
    body_sha256_before: str
    body_sha256_after: str
    remove_selectors: tuple[str, ...]
    matched_remove_selectors: tuple[str, ...]
    unmatched_remove_selectors: tuple[str, ...]
    removed_ranges: tuple[BlockVisibilityRange, ...]
    removed_range_body_element_count: int
    removed_body_element_count: int
    removed_paragraph_count: int
    removed_table_count: int
    stripped_marker_paragraph_count: int
    stripped_marker_token_count: int
    removed_empty_marker_paragraph_count: int
    removed_content_image_markers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != BLOCK_VISIBILITY_RECEIPT_VERSION:
            raise ValueError("unsupported block visibility receipt contract")
        supplied = str(self.receipt_id or "").strip()
        computed = sha256(self.canonical_json().encode("utf-8")).hexdigest()
        if supplied and supplied != computed:
            raise ValueError("receipt_id does not match canonical receipt payload")
        object.__setattr__(self, "receipt_id", computed)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "plan_id": self.plan_id,
            "body_sha256_before": self.body_sha256_before,
            "body_sha256_after": self.body_sha256_after,
            "remove_selectors": list(self.remove_selectors),
            "matched_remove_selectors": list(self.matched_remove_selectors),
            "unmatched_remove_selectors": list(self.unmatched_remove_selectors),
            "removed_ranges": [item.to_dict() for item in self.removed_ranges],
            "removed_range_body_element_count": self.removed_range_body_element_count,
            "removed_body_element_count": self.removed_body_element_count,
            "removed_paragraph_count": self.removed_paragraph_count,
            "removed_table_count": self.removed_table_count,
            "stripped_marker_paragraph_count": self.stripped_marker_paragraph_count,
            "stripped_marker_token_count": self.stripped_marker_token_count,
            "removed_empty_marker_paragraph_count": (
                self.removed_empty_marker_paragraph_count
            ),
            "removed_content_image_markers": list(
                self.removed_content_image_markers
            ),
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def to_dict(self) -> dict[str, object]:
        return {"receipt_id": self.receipt_id, **self.canonical_payload()}

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> BlockVisibilityReceipt:
        if not isinstance(payload, Mapping):
            raise TypeError("block visibility receipt payload must be a mapping")

        def sequence(name: str) -> tuple[object, ...]:
            value = payload.get(name, ())
            if not isinstance(value, (list, tuple)):
                raise TypeError(f"{name} must be a sequence")
            return tuple(value)

        raw_ranges = sequence("removed_ranges")
        if any(not isinstance(item, Mapping) for item in raw_ranges):
            raise TypeError("removed_ranges entries must be mappings")

        return cls(
            receipt_id=str(payload.get("receipt_id", "") or ""),
            contract_version=str(payload.get("contract_version", "") or ""),
            plan_id=str(payload.get("plan_id", "") or ""),
            body_sha256_before=str(payload.get("body_sha256_before", "") or ""),
            body_sha256_after=str(payload.get("body_sha256_after", "") or ""),
            remove_selectors=tuple(str(item) for item in sequence("remove_selectors")),
            matched_remove_selectors=tuple(
                str(item) for item in sequence("matched_remove_selectors")
            ),
            unmatched_remove_selectors=tuple(
                str(item) for item in sequence("unmatched_remove_selectors")
            ),
            removed_ranges=tuple(
                BlockVisibilityRange.from_dict(item)
                for item in raw_ranges
                if isinstance(item, Mapping)
            ),
            removed_range_body_element_count=int(
                payload.get("removed_range_body_element_count", 0)
            ),
            removed_body_element_count=int(
                payload.get("removed_body_element_count", 0)
            ),
            removed_paragraph_count=int(payload.get("removed_paragraph_count", 0)),
            removed_table_count=int(payload.get("removed_table_count", 0)),
            stripped_marker_paragraph_count=int(
                payload.get("stripped_marker_paragraph_count", 0)
            ),
            stripped_marker_token_count=int(
                payload.get("stripped_marker_token_count", 0)
            ),
            removed_empty_marker_paragraph_count=int(
                payload.get("removed_empty_marker_paragraph_count", 0)
            ),
            removed_content_image_markers=tuple(
                str(item) for item in sequence("removed_content_image_markers")
            ),
        )


@dataclass(frozen=True, slots=True)
class _MarkerEvent:
    marker_type: str
    selector: str
    raw_text: str
    body_index: int


def build_block_visibility_plan(
    document,
    *,
    remove_selectors: Iterable[str] = (),
) -> BlockVisibilityPlan:
    """Build one read-only, direct-body visibility plan or raise atomically."""

    body = _document_body(document)
    children = tuple(body)
    normalized_remove = tuple(
        sorted(
            {
                _normalize_selector(value)
                for value in remove_selectors
                if _normalize_selector(value)
            }
        )
    )
    diagnostics = _nested_surface_diagnostics(body, children)
    events_by_body_index: dict[int, tuple[_MarkerEvent, ...]] = {}
    for body_index, child in enumerate(children):
        if child.tag != _W_P:
            continue
        events = tuple(_marker_events(child, body_index))
        if events:
            events_by_body_index[body_index] = events

    all_ranges, parse_diagnostics = _parse_ranges(events_by_body_index)
    diagnostics.extend(parse_diagnostics)
    selected_ranges = tuple(
        item for item in all_ranges if item.selector in normalized_remove
    )
    # The v1 grammar is a document-wide contract, not merely a mutation-time
    # check for the current preset.  Unsupported elements or overlapping
    # blocks must therefore fail even when that selector is retained in this
    # particular delivery variant.
    diagnostics.extend(_range_surface_diagnostics(children, all_ranges))
    diagnostics.extend(_overlap_diagnostics(all_ranges))
    if diagnostics:
        raise BlockVisibilityPlanError(diagnostics)
    selected_ranges = tuple(
        _enrich_range(item, children) for item in selected_ranges
    )

    remove_indices = {
        body_index
        for item in selected_ranges
        for body_index in range(item.start_body_index, item.end_body_index + 1)
    }
    retained = tuple(
        BlockVisibilityMarkerParagraph(
            body_index=body_index,
            marker_count=len(events),
            selectors=tuple(sorted({item.selector for item in events})),
        )
        for body_index, events in sorted(events_by_body_index.items())
        if body_index not in remove_indices
    )
    matched = tuple(
        sorted({item.selector for item in selected_ranges})
    )
    unmatched = tuple(
        selector for selector in normalized_remove if selector not in matched
    )
    return BlockVisibilityPlan(
        plan_id="",
        contract_version=BLOCK_VISIBILITY_PLAN_VERSION,
        body_sha256=_body_sha256(body),
        body_element_count=len(children),
        remove_selectors=normalized_remove,
        matched_remove_selectors=matched,
        unmatched_remove_selectors=unmatched,
        remove_ranges=selected_ranges,
        retained_marker_paragraphs=retained,
    )


def apply_block_visibility_plan(document, plan: BlockVisibilityPlan) -> BlockVisibilityReceipt:
    """Apply a previously validated plan in descending original body order."""

    if not isinstance(plan, BlockVisibilityPlan):
        raise TypeError("plan must be a BlockVisibilityPlan")
    body = _document_body(document)
    children = tuple(body)
    before_hash = _body_sha256(body)
    if len(children) != plan.body_element_count or before_hash != plan.body_sha256:
        raise BlockVisibilityPlanError(
            (
                BlockVisibilityDiagnostic(
                    "plan_stale",
                    "document body changed after block visibility planning",
                    location="document.body",
                ),
            )
        )

    remove_indices = {
        body_index
        for item in plan.remove_ranges
        for body_index in range(item.start_body_index, item.end_body_index + 1)
    }
    strip_by_index = {
        item.body_index: item for item in plan.retained_marker_paragraphs
    }
    strip_diagnostics = []
    for body_index, marker_plan in strip_by_index.items():
        child = children[body_index]
        actual_count = len(
            tuple(CONTENT_VISIBILITY_MARKER_RE.finditer(_element_text(child)))
        )
        if child.tag != _W_P or actual_count != marker_plan.marker_count:
            strip_diagnostics.append(
                BlockVisibilityDiagnostic(
                    "marker_strip_mismatch",
                    "retained marker paragraph no longer matches its plan",
                    body_index=body_index,
                    location=f"document.body[{body_index}]",
                )
            )
    if strip_diagnostics:
        raise BlockVisibilityPlanError(strip_diagnostics)
    removed_paragraphs = sum(
        _paragraph_count(children[index]) for index in sorted(remove_indices)
    )
    removed_tables = sum(
        1 for index in remove_indices if children[index].tag == _W_TBL
    )
    removed_content_markers = tuple(
        sorted(
            {
                marker
                for index in remove_indices
                for marker in _content_image_markers(children[index])
            }
        )
    )
    stripped_paragraphs = 0
    stripped_tokens = 0
    removed_empty_marker_paragraphs = 0

    for body_index in sorted(remove_indices | set(strip_by_index), reverse=True):
        child = children[body_index]
        if body_index in remove_indices:
            body.remove(child)
            continue
        marker_plan = strip_by_index[body_index]
        stripped = _strip_visibility_marker_tokens(child)
        # Counts were checked for every retained marker paragraph before the
        # first mutation, so the apply pass remains all-or-nothing for stale
        # plans and deterministic for a valid plan.
        assert stripped == marker_plan.marker_count
        stripped_paragraphs += 1
        stripped_tokens += stripped
        if not _element_text(child).strip() and not _paragraph_has_payload(child):
            body.remove(child)
            removed_empty_marker_paragraphs += 1

    after_hash = _body_sha256(body)
    removed_range_elements = len(remove_indices)
    return BlockVisibilityReceipt(
        receipt_id="",
        contract_version=BLOCK_VISIBILITY_RECEIPT_VERSION,
        plan_id=plan.plan_id,
        body_sha256_before=before_hash,
        body_sha256_after=after_hash,
        remove_selectors=plan.remove_selectors,
        matched_remove_selectors=plan.matched_remove_selectors,
        unmatched_remove_selectors=plan.unmatched_remove_selectors,
        removed_ranges=plan.remove_ranges,
        removed_range_body_element_count=removed_range_elements,
        removed_body_element_count=(
            removed_range_elements + removed_empty_marker_paragraphs
        ),
        removed_paragraph_count=removed_paragraphs,
        removed_table_count=removed_tables,
        stripped_marker_paragraph_count=stripped_paragraphs,
        stripped_marker_token_count=stripped_tokens,
        removed_empty_marker_paragraph_count=removed_empty_marker_paragraphs,
        removed_content_image_markers=removed_content_markers,
    )


def apply_block_visibility(
    document,
    *,
    remove_selectors: Iterable[str] = (),
) -> BlockVisibilityReceipt:
    plan = build_block_visibility_plan(
        document,
        remove_selectors=remove_selectors,
    )
    return apply_block_visibility_plan(document, plan)


def _document_body(document):
    element = getattr(document, "element", None)
    body = getattr(element, "body", None)
    if body is None:
        raise TypeError("document must expose document.element.body")
    return body


def _nested_surface_diagnostics(
    body,
    children,
) -> list[BlockVisibilityDiagnostic]:
    diagnostics: list[BlockVisibilityDiagnostic] = []
    for paragraph in body.iter(_W_P):
        if paragraph.getparent() is body:
            continue
        matches = tuple(CONTENT_VISIBILITY_MARKER_RE.finditer(_element_text(paragraph)))
        if not matches:
            continue
        body_index = _owning_body_index(paragraph, body, children)
        selectors = tuple(
            sorted({_normalize_selector(item.group(2)) for item in matches})
        )
        diagnostics.append(
            BlockVisibilityDiagnostic(
                "marker_not_direct_body",
                "visibility markers are allowed only in direct document-body paragraphs",
                selector=",".join(selectors),
                body_index=body_index,
                location=(
                    f"document.body[{body_index}]/nested"
                    if body_index >= 0
                    else "document.body/nested"
                ),
            )
        )
    return diagnostics


def _marker_events(paragraph, body_index: int) -> list[_MarkerEvent]:
    text = _element_text(paragraph)
    return [
        _MarkerEvent(
            marker_type=match.group(1),
            selector=_normalize_selector(match.group(2)),
            raw_text=match.group(0),
            body_index=body_index,
        )
        for match in CONTENT_VISIBILITY_MARKER_RE.finditer(text)
    ]


def _parse_ranges(
    events_by_body_index: Mapping[int, Sequence[_MarkerEvent]],
) -> tuple[tuple[BlockVisibilityRange, ...], list[BlockVisibilityDiagnostic]]:
    stack: list[_MarkerEvent] = []
    raw_ranges: list[tuple[str, int, int]] = []
    diagnostics: list[BlockVisibilityDiagnostic] = []
    for body_index, events in sorted(events_by_body_index.items()):
        for event in events:
            if event.marker_type == "#":
                if stack:
                    diagnostics.append(
                        BlockVisibilityDiagnostic(
                            "nested_marker_block",
                            "nested visibility marker blocks are not supported",
                            selector=event.selector,
                            body_index=body_index,
                            location=f"document.body[{body_index}]",
                        )
                    )
                stack.append(event)
                continue

            if not stack:
                diagnostics.append(
                    BlockVisibilityDiagnostic(
                        "orphan_end_marker",
                        "visibility end marker has no matching start marker",
                        selector=event.selector,
                        body_index=body_index,
                        location=f"document.body[{body_index}]",
                    )
                )
                continue
            start = stack[-1]
            if start.selector != event.selector:
                diagnostics.append(
                    BlockVisibilityDiagnostic(
                        "mismatched_end_marker",
                        "visibility end marker does not match the active selector",
                        selector=event.selector,
                        body_index=body_index,
                        location=f"document.body[{body_index}]",
                    )
                )
                continue
            stack.pop()
            raw_ranges.append((event.selector, start.body_index, body_index))

    diagnostics.extend(
        BlockVisibilityDiagnostic(
            "unclosed_start_marker",
            "visibility start marker has no matching end marker",
            selector=event.selector,
            body_index=event.body_index,
            location=f"document.body[{event.body_index}]",
        )
        for event in stack
    )
    ranges = tuple(
        BlockVisibilityRange(
            selector=selector,
            start_body_index=start,
            end_body_index=end,
            body_element_count=end - start + 1,
            paragraph_count=0,
            table_count=0,
            content_image_markers=(),
        )
        for selector, start, end in sorted(raw_ranges, key=lambda item: (item[1], item[2]))
    )
    return ranges, diagnostics


def _range_surface_diagnostics(
    children,
    ranges: Sequence[BlockVisibilityRange],
) -> list[BlockVisibilityDiagnostic]:
    diagnostics: list[BlockVisibilityDiagnostic] = []
    for item in ranges:
        for body_index in range(item.start_body_index, item.end_body_index + 1):
            if children[body_index].tag in {_W_P, _W_TBL}:
                continue
            diagnostics.append(
                BlockVisibilityDiagnostic(
                    "unsupported_body_element_in_range",
                    "visibility ranges may contain only direct w:p and w:tbl elements",
                    selector=item.selector,
                    body_index=body_index,
                    location=f"document.body[{body_index}]",
                )
            )
    return diagnostics


def _overlap_diagnostics(
    ranges: Sequence[BlockVisibilityRange],
) -> list[BlockVisibilityDiagnostic]:
    diagnostics: list[BlockVisibilityDiagnostic] = []
    previous: BlockVisibilityRange | None = None
    for item in sorted(ranges, key=lambda value: (value.start_body_index, value.end_body_index)):
        if previous is not None and item.start_body_index <= previous.end_body_index:
            diagnostics.append(
                BlockVisibilityDiagnostic(
                    "overlapping_remove_ranges",
                    "selected visibility ranges overlap in document body order",
                    selector=item.selector,
                    body_index=item.start_body_index,
                    location=f"document.body[{item.start_body_index}]",
                )
            )
        previous = item
    return diagnostics


def _enrich_range(item: BlockVisibilityRange, children) -> BlockVisibilityRange:
    selected = children[item.start_body_index : item.end_body_index + 1]
    return BlockVisibilityRange(
        selector=item.selector,
        start_body_index=item.start_body_index,
        end_body_index=item.end_body_index,
        body_element_count=len(selected),
        paragraph_count=sum(_paragraph_count(element) for element in selected),
        table_count=sum(1 for element in selected if element.tag == _W_TBL),
        content_image_markers=tuple(
            sorted(
                {
                    marker
                    for element in selected
                    for marker in _content_image_markers(element)
                }
            )
        ),
    )


def _strip_visibility_marker_tokens(paragraph) -> int:
    text_nodes = tuple(paragraph.iter(_W_T))
    text = "".join(str(node.text or "") for node in text_nodes)
    matches = tuple(CONTENT_VISIBILITY_MARKER_RE.finditer(text))
    for match in reversed(matches):
        _remove_text_span(text_nodes, match.start(), match.end())
    return len(matches)


def _remove_text_span(text_nodes, start: int, end: int) -> None:
    cursor = 0
    for node in text_nodes:
        text = str(node.text or "")
        node_start = cursor
        node_end = cursor + len(text)
        cursor = node_end
        if node_end <= start or node_start >= end:
            continue
        local_start = max(0, start - node_start)
        local_end = min(len(text), end - node_start)
        remaining = text[:local_start] + text[local_end:]
        node.text = remaining
        if remaining.startswith(" ") or remaining.endswith(" "):
            node.set(_XML_SPACE, "preserve")


def _paragraph_has_payload(paragraph) -> bool:
    return any(
        element is not paragraph and element.tag in _PARAGRAPH_PAYLOAD_TAGS
        for element in paragraph.iter()
    )


def _element_text(element) -> str:
    return "".join(str(node.text or "") for node in element.iter(_W_T))


def _paragraph_count(element) -> int:
    return sum(1 for _paragraph in element.iter(_W_P))


def _content_image_markers(element) -> tuple[str, ...]:
    markers = {
        name
        for bookmark in element.iter(_W_BOOKMARK_START)
        if (name := str(bookmark.get(_W_NAME, "") or "")).startswith(
            _CONTENT_IMAGE_MARKER_PREFIX
        )
    }
    markers.update(_CONTENT_IMAGE_MARKER_RE.findall(_element_text(element)))
    return tuple(sorted(markers))


def _owning_body_index(element, body, children) -> int:
    current = element
    while current is not None and current.getparent() is not body:
        current = current.getparent()
    if current is None or current.getparent() is not body:
        return -1
    try:
        return children.index(current)
    except ValueError:
        return -1


def _body_sha256(body) -> str:
    return sha256(body.xml.encode("utf-8")).hexdigest()


def _normalize_selector(value: object) -> str:
    return str(value or "").strip().casefold()


__all__ = [
    "BLOCK_VISIBILITY_PLAN_VERSION",
    "BLOCK_VISIBILITY_RECEIPT_VERSION",
    "BlockVisibilityDiagnostic",
    "BlockVisibilityMarkerParagraph",
    "BlockVisibilityPlan",
    "BlockVisibilityPlanError",
    "BlockVisibilityRange",
    "BlockVisibilityReceipt",
    "apply_block_visibility",
    "apply_block_visibility_plan",
    "build_block_visibility_plan",
]
