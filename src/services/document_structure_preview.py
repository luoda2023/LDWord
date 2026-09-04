"""Small document-structure preview used by execution-time UI choices."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.document_scope import document_scope_role_label
from src.services.document_structure_evidence import (
    build_document_structure_evidence,
)


@dataclass(frozen=True, slots=True)
class StructurePreviewItem:
    section_type: str
    label: str
    start_index: int
    end_index: int
    title: str = ""

    @property
    def display_text(self) -> str:
        title = str(self.title or "").strip()
        if title:
            return f"{self.label}：{title}"
        return self.label


def analyze_document_structure(path: str | Path) -> list[StructurePreviewItem]:
    evidence = build_document_structure_evidence(path)
    return [
        StructurePreviewItem(
            section_type=region.role_id,
            label=document_scope_role_label(region.role_id),
            start_index=region.start_anchor.source_index,
            end_index=(
                region.end_anchor.source_index
                if region.end_anchor is not None
                else region.start_anchor.source_index + 1
            ),
            title=region.start_anchor.preview_text,
        )
        for region in evidence.regions
    ]


def suppression_selectors_before(
    items: list[StructurePreviewItem],
    selected_index: int,
) -> list[str]:
    selected_index = max(0, min(int(selected_index), len(items)))
    selectors: list[str] = []
    for item in items[:selected_index]:
        selector = str(item.section_type or "").strip()
        if selector and selector not in selectors:
            selectors.append(selector)
    return selectors


__all__ = [
    "StructurePreviewItem",
    "analyze_document_structure",
    "suppression_selectors_before",
]
