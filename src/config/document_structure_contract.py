"""Immutable document-structure evidence and review-decision contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from src.config.section_semantics import canonicalize_section_type


@dataclass(frozen=True, slots=True)
class ParagraphAnchor:
    """Stable source-paragraph identity with an index used only as a hint."""

    source_index: int
    text_digest: str
    previous_text_digest: str
    next_text_digest: str
    occurrence: int
    preview_text: str = ""


@dataclass(frozen=True, slots=True)
class DetectedRegion:
    role_id: str
    start_anchor: ParagraphAnchor
    end_anchor: ParagraphAnchor | None
    detection_status: str
    evidence_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StructureReviewItem:
    role_id: str
    code: str


@dataclass(frozen=True, slots=True)
class RegionDecision:
    role_id: str
    action: str
    start_anchor: ParagraphAnchor | None = None


@dataclass(frozen=True, slots=True)
class DocumentStructureEvidence:
    source_path: str
    source_revision: str
    detector_revision: str
    evidence_digest: str
    regions: tuple[DetectedRegion, ...]
    review_items: tuple[StructureReviewItem, ...]
    issues: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return bool(self.source_revision and self.evidence_digest) and not self.issues

    @property
    def requires_review(self) -> bool:
        return bool(self.review_items)

    def to_dict(self) -> dict[str, object]:
        return {
            "source_path": self.source_path,
            "source_revision": self.source_revision,
            "detector_revision": self.detector_revision,
            "evidence_digest": self.evidence_digest,
            "regions": [asdict(region) for region in self.regions],
            "review_items": [asdict(item) for item in self.review_items],
            "issues": list(self.issues),
        }


def validate_region_decisions(
    evidence: DocumentStructureEvidence,
    decisions: tuple[RegionDecision, ...] | list[RegionDecision],
    *,
    allowed_roles: tuple[str, ...],
) -> tuple[str, ...]:
    issues: list[str] = []
    allowed = set(allowed_roles)
    seen: set[str] = set()
    for decision in decisions:
        role_id = canonicalize_section_type(decision.role_id)
        if role_id not in allowed:
            issues.append(f"document_structure_decision_role_unsupported:{role_id}")
        if role_id in seen:
            issues.append(f"document_structure_decision_duplicate:{role_id}")
        seen.add(role_id)
        if decision.action not in {"accept", "exclude", "set_start"}:
            issues.append(
                f"document_structure_decision_action_invalid:{decision.action}"
            )
        if decision.action == "set_start" and decision.start_anchor is None:
            issues.append(f"document_structure_decision_anchor_missing:{role_id}")
    if not evidence.ready:
        issues.append("document_structure_evidence_not_ready")
    return tuple(dict.fromkeys(issues))


def pending_document_structure_review_roles(
    evidence: DocumentStructureEvidence,
    decisions: tuple[RegionDecision, ...] | list[RegionDecision],
    *,
    included_roles: tuple[str, ...],
) -> tuple[str, ...]:
    """Return unresolved review roles that can change the writable range.

    A region start defines both its own beginning and the preceding region's
    end.  Therefore the first boundary after an included region is relevant
    even when that following region is outside the plan's processing scope.
    """

    decided = {
        canonicalize_section_type(decision.role_id)
        for decision in decisions
    }
    included = set(included_roles)
    starts = {
        canonicalize_section_type(region.role_id): region.start_anchor.source_index
        for region in evidence.regions
    }
    for decision in decisions:
        if decision.action == "set_start" and decision.start_anchor is not None:
            starts[canonicalize_section_type(decision.role_id)] = (
                decision.start_anchor.source_index
            )

    ordered_roles = tuple(
        role_id
        for role_id, _index in sorted(
            starts.items(),
            key=lambda item: (item[1], item[0]),
        )
    )
    relevant = set(included)
    for index, role_id in enumerate(ordered_roles[:-1]):
        if role_id in included:
            relevant.add(ordered_roles[index + 1])

    return tuple(
        dict.fromkeys(
            canonicalize_section_type(item.role_id)
            for item in evidence.review_items
            if canonicalize_section_type(item.role_id) in relevant
            and canonicalize_section_type(item.role_id) not in decided
        )
    )


__all__ = [
    "DetectedRegion",
    "DocumentStructureEvidence",
    "ParagraphAnchor",
    "RegionDecision",
    "StructureReviewItem",
    "pending_document_structure_review_roles",
    "validate_region_decisions",
]
