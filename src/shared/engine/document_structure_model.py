"""Shared in-memory heading and logical-section model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from src.shared.engine.section_semantics import canonicalize_section_type


@dataclass
class HeadingInfo:
    para_index: int
    level: int
    text: str
    confidence: str = "high"


@dataclass
class DocSection:
    section_type: str
    start_index: int
    end_index: int = -1
    confidence: float = 0.0
    title_confident: bool = True
    excluded: bool = False
    boundary_confident: bool = False


@dataclass
class DocTree:
    headings: list[HeadingInfo] = field(default_factory=list)
    heading_map: dict[int, int] = field(default_factory=dict)
    section_ranges: dict[str, tuple[int, int]] = field(default_factory=dict)
    sections: list[DocSection] = field(default_factory=list)
    special_title_matches: dict[int, str] = field(default_factory=dict)
    special_title_ranges: list[DocSection] = field(default_factory=list)
    detection_log: list[str] = field(default_factory=list)
    scope_mode: str = "all"
    writable_roles: frozenset[str] = field(default_factory=frozenset)
    evidence_digest: str = ""
    user_corrected_roles: frozenset[str] = field(default_factory=frozenset)

    def get_heading_level(self, para_index: int) -> int | None:
        return self.heading_map.get(para_index)

    def get_section(self, section_type: str) -> DocSection | None:
        canonical = canonicalize_section_type(section_type)
        for section in self.sections:
            if section.section_type == canonical and not section.excluded:
                return section
        if canonical in self.section_ranges:
            start, end = self.section_ranges[canonical]
            return DocSection(canonical, start, end)
        return None

    def get_section_for_paragraph(self, para_index: int) -> str:
        for section in self.sections:
            if section.start_index <= para_index < section.end_index:
                return canonicalize_section_type(section.section_type)
        for section_name, (start, end) in self.section_ranges.items():
            if start <= para_index < end:
                return canonicalize_section_type(section_name)
        return "body"

    def get_special_title_match(self, para_index: int) -> str | None:
        return self.special_title_matches.get(para_index)

    def get_special_title_selectors_for_paragraph(
        self,
        para_index: int,
    ) -> tuple[str, ...]:
        selectors: list[str] = []
        for section in self.special_title_ranges:
            if section.start_index <= para_index < section.end_index:
                selector = str(section.section_type or "").strip()
                if selector and selector not in selectors:
                    selectors.append(selector)
        return tuple(selectors)

    def is_role_writable(self, section_type: str) -> bool:
        canonical = canonicalize_section_type(section_type)
        if canonical not in self.writable_roles:
            return False
        return self.get_section(canonical) is not None

    def insertion_index_for_role(self, section_type: str) -> int | None:
        """Return a structure-owned insertion boundary for a missing region."""

        canonical = canonicalize_section_type(section_type)
        existing = self.get_section(canonical)
        if existing is not None:
            return existing.start_index
        if canonical == "toc":
            body = self.get_section("body")
            return body.start_index if body is not None else None
        return None

    def is_paragraph_writable(self, para_index: int) -> bool:
        for section in self.sections:
            if section.start_index <= para_index < section.end_index:
                return (
                    not section.excluded
                    and canonicalize_section_type(section.section_type)
                    in self.writable_roles
                )
        for section_name, (start, end) in self.section_ranges.items():
            if start <= para_index < end:
                return canonicalize_section_type(section_name) in self.writable_roles
        return False


def normalize_heading_map(heading_map: Mapping[int, int] | None) -> dict[int, int]:
    """Return a stable, positive integer heading map."""

    result: dict[int, int] = {}
    for key, value in dict(heading_map or {}).items():
        try:
            index = int(key)
            level = int(value)
        except (TypeError, ValueError):
            continue
        if index >= 0 and level > 0:
            result[index] = level
    return dict(sorted(result.items()))


__all__ = ["DocSection", "DocTree", "HeadingInfo", "normalize_heading_map"]
