"""Bind reviewed document-region evidence to one mutable execution document."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from src.config.document_scope import (
    DocumentScopePolicy,
    coerce_document_scope_policy,
    selectable_document_scope_roles,
)
from src.config.document_structure_contract import (
    DocumentStructureEvidence,
    ParagraphAnchor,
    RegionDecision,
    pending_document_structure_review_roles,
    validate_region_decisions,
)
from src.shared.engine.document_structure_model import DocSection
from src.shared.engine.section_semantics import canonicalize_section_type


@dataclass(slots=True)
class BoundRegionStart:
    role_id: str
    start_element: Any
    detection_status: str
    user_corrected: bool = False
    excluded: bool = False


@dataclass(slots=True)
class DocumentScopeBinding:
    evidence_digest: str
    regions: tuple[BoundRegionStart, ...]
    decision_roles: tuple[str, ...]


def bind_document_scope(
    doc,
    evidence: DocumentStructureEvidence,
    decisions: tuple[RegionDecision, ...] | list[RegionDecision],
    policy: DocumentScopePolicy,
    *,
    mode_id: str,
) -> DocumentScopeBinding:
    """Resolve frozen anchors before any writer is allowed to mutate the document."""

    resolved_policy = coerce_document_scope_policy(policy)
    decision_roles = tuple(
        dict.fromkeys(
            (
                *selectable_document_scope_roles(mode_id),
                *(
                    canonicalize_section_type(region.role_id)
                    for region in evidence.regions
                ),
            )
        )
    )
    issues = validate_region_decisions(
        evidence,
        decisions,
        allowed_roles=decision_roles,
    )
    if issues:
        raise ValueError(";".join(issues))

    decisions_by_role = {
        canonicalize_section_type(decision.role_id): decision
        for decision in decisions
    }
    pending_roles = pending_document_structure_review_roles(
        evidence,
        decisions,
        included_roles=resolved_policy.included_roles(mode_id),
    )
    if pending_roles:
        raise ValueError(
            "document_structure_review_required:" + ",".join(pending_roles)
        )

    paragraphs = tuple(doc.paragraphs)
    texts = tuple(str(paragraph.text or "").strip() for paragraph in paragraphs)
    region_specs: dict[str, tuple[ParagraphAnchor, str, bool, bool]] = {}
    for region in evidence.regions:
        role_id = canonicalize_section_type(region.role_id)
        decision = decisions_by_role.get(role_id)
        anchor = (
            decision.start_anchor
            if decision is not None and decision.action == "set_start"
            else region.start_anchor
        )
        if anchor is None:
            raise ValueError(f"document_structure_anchor_missing:{role_id}")
        region_specs[role_id] = (
            anchor,
            region.detection_status,
            bool(decision is not None),
            bool(decision is not None and decision.action == "exclude"),
        )

    for role_id, decision in decisions_by_role.items():
        if role_id in region_specs or decision.action != "set_start":
            continue
        if decision.start_anchor is None:
            raise ValueError(f"document_structure_anchor_missing:{role_id}")
        region_specs[role_id] = (decision.start_anchor, "accepted", True, False)

    bound: list[BoundRegionStart] = []
    occupied_indices: dict[int, str] = {}
    for role_id, (anchor, status, corrected, excluded) in region_specs.items():
        index = resolve_paragraph_anchor(anchor, texts)
        if index is None:
            raise ValueError(f"document_structure_anchor_unresolved:{role_id}")
        previous_role = occupied_indices.get(index)
        if previous_role is not None:
            raise ValueError(
                f"document_structure_anchor_conflict:{previous_role},{role_id}"
            )
        occupied_indices[index] = role_id
        bound.append(
            BoundRegionStart(
                role_id=role_id,
                start_element=paragraphs[index]._p,
                detection_status=status,
                user_corrected=corrected,
                excluded=excluded,
            )
        )

    bound.sort(key=lambda item: _paragraph_element_index(paragraphs, item.start_element))
    return DocumentScopeBinding(
        evidence_digest=evidence.evidence_digest,
        regions=tuple(bound),
        decision_roles=tuple(decisions_by_role),
    )


def project_document_scope_tree(
    doc,
    tree,
    binding: DocumentScopeBinding | None,
    policy: DocumentScopePolicy,
    *,
    mode_id: str,
):
    """Apply one stable binding to a freshly analysed DocTree without re-guessing."""

    resolved_policy = coerce_document_scope_policy(policy)
    if binding is None:
        tree.scope_mode = resolved_policy.mode
        tree.writable_roles = frozenset(resolved_policy.included_roles(mode_id))
        return tree

    paragraphs = tuple(doc.paragraphs)
    element_indices = {id(paragraph._p): index for index, paragraph in enumerate(paragraphs)}
    starts: list[tuple[int, BoundRegionStart]] = []
    for region in binding.regions:
        index = element_indices.get(id(region.start_element))
        if index is None:
            raise ValueError(f"document_structure_anchor_lost:{region.role_id}")
        starts.append((index, region))
    starts.sort(key=lambda item: item[0])

    sections: list[DocSection] = []
    for position, (start, region) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(paragraphs)
        if end <= start:
            raise ValueError(f"document_structure_region_invalid:{region.role_id}")
        sections.append(
            DocSection(
                section_type=region.role_id,
                start_index=start,
                end_index=end,
                confidence=10.0 if region.detection_status == "accepted" else 0.0,
                title_confident=region.detection_status == "accepted",
                excluded=region.excluded,
            )
        )

    tree.sections = sections
    tree.section_ranges = {
        section.section_type: (section.start_index, section.end_index)
        for section in sections
        if not section.excluded
    }
    tree.headings = [
        heading
        for heading in tree.headings
        if tree.get_section_for_paragraph(heading.para_index) == "body"
    ]
    tree.heading_map = {
        heading.para_index: heading.level
        for heading in tree.headings
    }
    tree.scope_mode = resolved_policy.mode
    tree.writable_roles = frozenset(resolved_policy.included_roles(mode_id))
    tree.evidence_digest = binding.evidence_digest
    tree.user_corrected_roles = frozenset(binding.decision_roles)
    return tree


def resolve_paragraph_anchor(
    anchor: ParagraphAnchor,
    paragraph_texts: tuple[str, ...],
) -> int | None:
    """Resolve one anchor exactly; ambiguous matches are rejected."""

    digests = tuple(_text_digest(text) for text in paragraph_texts)
    hint = int(anchor.source_index)
    if 0 <= hint < len(digests) and digests[hint] == anchor.text_digest:
        return hint

    candidates = [
        index
        for index, digest in enumerate(digests)
        if digest == anchor.text_digest
    ]
    if not candidates:
        return None

    occurrence_candidates = [
        index
        for occurrence, index in enumerate(candidates)
        if occurrence == int(anchor.occurrence)
    ]
    if len(occurrence_candidates) == 1:
        candidate = occurrence_candidates[0]
        if _neighbor_digests_match(anchor, digests, candidate):
            return candidate

    neighbor_matches = [
        index
        for index in candidates
        if _neighbor_digests_match(anchor, digests, index)
    ]
    return neighbor_matches[0] if len(neighbor_matches) == 1 else None


def document_scope_allows_paragraph(context, para_index: int) -> bool:
    if not bool(getattr(context, "document_scope_gate_active", False)):
        return True
    tree = getattr(context, "doc_tree", None)
    if tree is None:
        return False
    checker = getattr(tree, "is_paragraph_writable", None)
    return bool(callable(checker) and checker(para_index))


def document_scope_allows_role(context, role_id: str) -> bool:
    if not bool(getattr(context, "document_scope_gate_active", False)):
        return True
    tree = getattr(context, "doc_tree", None)
    if tree is None:
        return False
    checker = getattr(tree, "is_role_writable", None)
    return bool(callable(checker) and checker(role_id))


def document_scope_includes_role(context, role_id: str) -> bool:
    policy = coerce_document_scope_policy(
        getattr(context, "document_scope", None)
    )
    mode_id = str(getattr(context, "mode_id", "") or "custom")
    return policy.includes(role_id, mode_id=mode_id)


def _neighbor_digests_match(
    anchor: ParagraphAnchor,
    digests: tuple[str, ...],
    index: int,
) -> bool:
    previous = digests[index - 1] if index > 0 else ""
    following = digests[index + 1] if index + 1 < len(digests) else ""
    return (
        previous == anchor.previous_text_digest
        and following == anchor.next_text_digest
    )


def _paragraph_element_index(paragraphs, target_element) -> int:
    for index, paragraph in enumerate(paragraphs):
        if paragraph._p is target_element:
            return index
    raise ValueError("document_structure_anchor_unresolved")


def _text_digest(text: str) -> str:
    normalized = " ".join(str(text or "").split()).casefold().encode("utf-8")
    return sha256(normalized).hexdigest()


__all__ = [
    "BoundRegionStart",
    "DocumentScopeBinding",
    "bind_document_scope",
    "document_scope_allows_paragraph",
    "document_scope_allows_role",
    "document_scope_includes_role",
    "project_document_scope_tree",
    "resolve_paragraph_anchor",
]
