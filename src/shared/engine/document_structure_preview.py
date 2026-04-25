"""Small document-structure preview used by execution-time UI choices."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from docx import Document

from src.config.resolved import ResolvedConfig
from src.modules.structure.heading_recognition import HeadingRecognitionModule
from src.pipeline.context import PipelineContext
from src.pipeline.tracker import ChangeTracker


_SECTION_LABELS: dict[str, str] = {
    "cover": "封面",
    "statement": "声明页",
    "authorization": "授权书",
    "front_note": "说明页",
    "abstract_cn": "中文摘要",
    "abstract_en": "英文摘要",
    "toc": "目录",
    "body": "正文",
    "references": "参考文献",
    "errata": "勘误",
    "appendix": "附录",
    "acknowledgment": "致谢",
    "resume": "个人简历",
}


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
    doc = Document(str(path))
    context = PipelineContext()
    HeadingRecognitionModule().apply(doc, ResolvedConfig(), ChangeTracker(), context)

    doc_tree = getattr(context, "doc_tree", None)
    sections = list(getattr(doc_tree, "sections", []) or [])
    items: list[StructurePreviewItem] = []
    for section in sections:
        section_type = str(getattr(section, "section_type", "") or "").strip() or "body"
        start_index = max(0, int(getattr(section, "start_index", 0) or 0))
        end_index = max(start_index, int(getattr(section, "end_index", start_index) or start_index))
        label = _SECTION_LABELS.get(section_type, section_type)
        items.append(
            StructurePreviewItem(
                section_type=section_type,
                label=label,
                start_index=start_index,
                end_index=end_index,
                title=_first_non_empty_paragraph_text(doc, start_index, end_index),
            )
        )
    return items


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


def _first_non_empty_paragraph_text(doc, start_index: int, end_index: int) -> str:
    paragraphs = list(getattr(doc, "paragraphs", []) or [])
    for index in range(max(0, start_index), min(max(start_index, end_index), len(paragraphs))):
        text = str(paragraphs[index].text or "").strip()
        if text:
            return text[:36]
    return ""


__all__ = [
    "StructurePreviewItem",
    "analyze_document_structure",
    "suppression_selectors_before",
]
