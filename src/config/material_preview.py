"""Preview helpers for material placeholder matching."""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document


PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_\-.\u4e00-\u9fff]+)\s*\}\}")


def scan_docx_placeholders(path: str | Path) -> list[str]:
    target = Path(str(path or ""))
    if not target.exists() or target.suffix.lower() != ".docx":
        return []

    document = Document(str(target))
    tokens: list[str] = []
    seen: set[str] = set()

    for text in _iter_document_text(document):
        for match in PLACEHOLDER_PATTERN.finditer(text or ""):
            token = match.group(1).strip()
            if token and token not in seen:
                seen.add(token)
                tokens.append(token)
    return tokens


def _iter_document_text(document) -> list[str]:
    text_parts: list[str] = []
    for paragraph in document.paragraphs:
        text_parts.append(paragraph.text)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    text_parts.append(paragraph.text)
    for section in document.sections:
        for part in (section.header, section.footer):
            for paragraph in part.paragraphs:
                text_parts.append(paragraph.text)
            for table in part.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            text_parts.append(paragraph.text)
    return text_parts


__all__ = ["scan_docx_placeholders"]
