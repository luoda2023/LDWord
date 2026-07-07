"""Generate lightweight DOCX comparison artifacts."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


_TOKEN_RE = re.compile(r"\s+|\w+|[^\w\s]+", re.UNICODE)


def write_compare_docx(
    original_path: str | Path,
    revised_path: str | Path,
    compare_path: str | Path,
    *,
    compare_text: bool = True,
    compare_formatting: bool = True,
) -> Path:
    """Write a DOCX containing tracked-change text differences.

    This internal compare artifact is intentionally deterministic and does not
    require Microsoft Word. It records textual insertions/deletions with real
    WordprocessingML revision elements; formatting comparison is noted as
    metadata for now and can be upgraded to a Word COM-backed implementation.
    """
    original = Document(str(original_path))
    revised = Document(str(revised_path))
    target = Path(compare_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    doc = Document()
    doc.core_properties.title = "DOCX comparison"
    doc.add_heading("DOCX Comparison", level=1)
    doc.add_paragraph(f"Original: {Path(original_path).name}")
    doc.add_paragraph(f"Revised: {Path(revised_path).name}")
    doc.add_paragraph(f"Text comparison: {'enabled' if compare_text else 'disabled'}")
    doc.add_paragraph(
        f"Formatting comparison: {'requested' if compare_formatting else 'disabled'}"
    )

    if compare_text:
        change_count = _append_text_comparison(doc, original, revised)
        if change_count == 0:
            doc.add_paragraph("No text changes detected.")
    else:
        doc.add_paragraph("Text comparison was disabled for this artifact.")

    doc.save(str(target))
    return target


def _append_text_comparison(doc: Document, original: Document, revised: Document) -> int:
    original_units = _document_text_units(original)
    revised_units = _document_text_units(revised)
    matcher = SequenceMatcher(a=original_units, b=revised_units)
    revision_id = 1
    change_count = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        original_slice = original_units[i1:i2]
        revised_slice = revised_units[j1:j2]
        span = max(len(original_slice), len(revised_slice))
        for offset in range(span):
            old_text = original_slice[offset] if offset < len(original_slice) else ""
            new_text = revised_slice[offset] if offset < len(revised_slice) else ""
            _append_changed_unit(
                doc,
                old_text=old_text,
                new_text=new_text,
                revision_id=revision_id,
                label=f"Change {change_count + 1}",
            )
            revision_id += 2
            change_count += 1

    return change_count


def _append_changed_unit(
    doc: Document,
    *,
    old_text: str,
    new_text: str,
    revision_id: int,
    label: str,
) -> None:
    label_para = doc.add_paragraph()
    label_para.add_run(label).bold = True
    para = doc.add_paragraph()

    if old_text and new_text:
        _append_token_diff(para, old_text, new_text, revision_id=revision_id)
        return

    if old_text:
        _append_revision_run(para, old_text, kind="delete", revision_id=revision_id)
    if new_text:
        _append_revision_run(para, new_text, kind="insert", revision_id=revision_id + 1)


def _append_token_diff(para, old_text: str, new_text: str, *, revision_id: int) -> None:
    old_tokens = _tokenize(old_text)
    new_tokens = _tokenize(new_text)
    matcher = SequenceMatcher(a=old_tokens, b=new_tokens)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old_fragment = "".join(old_tokens[i1:i2])
        new_fragment = "".join(new_tokens[j1:j2])
        if tag == "equal":
            para.add_run(old_fragment)
        elif tag == "delete":
            _append_revision_run(para, old_fragment, kind="delete", revision_id=revision_id)
        elif tag == "insert":
            _append_revision_run(para, new_fragment, kind="insert", revision_id=revision_id + 1)
        else:
            if old_fragment:
                _append_revision_run(para, old_fragment, kind="delete", revision_id=revision_id)
            if new_fragment:
                _append_revision_run(
                    para,
                    new_fragment,
                    kind="insert",
                    revision_id=revision_id + 1,
                )


def _append_revision_run(para, text: str, *, kind: str, revision_id: int) -> None:
    wrapper = OxmlElement("w:ins" if kind == "insert" else "w:del")
    wrapper.set(qn("w:id"), str(revision_id))
    wrapper.set(qn("w:author"), "Lark Formatter")
    wrapper.set(qn("w:date"), _revision_timestamp())

    run = OxmlElement("w:r")
    text_node = OxmlElement("w:t" if kind == "insert" else "w:delText")
    if _needs_preserve_space(text):
        text_node.set(qn("xml:space"), "preserve")
    text_node.text = text
    run.append(text_node)
    wrapper.append(run)
    para._p.append(wrapper)


def _document_text_units(doc: Document) -> list[str]:
    units: list[str] = []
    for paragraph in doc.paragraphs:
        text = paragraph.text
        if text:
            units.append(text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                text = "\n".join(
                    paragraph.text for paragraph in cell.paragraphs if paragraph.text
                ).strip()
                if text:
                    units.append(text)
    return units


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text or "")


def _needs_preserve_space(text: str) -> bool:
    return bool(text) and (text[0].isspace() or text[-1].isspace())


def _revision_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


__all__ = ["write_compare_docx"]
