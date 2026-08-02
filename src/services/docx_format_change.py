"""Semantic DOCX formatting-change evidence for production receipts."""

from __future__ import annotations

from collections import Counter
import hashlib
from pathlib import Path
from xml.etree import ElementTree as ET
import zipfile


FORMAT_CHANGE_EVIDENCE_SCHEMA = "docx-format-change-v1"
_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_TEXT_TAGS = {
    f"{{{_WORD_NS}}}t",
}
_VISIBLE_CONTROL_TOKENS = {
    f"{{{_WORD_NS}}}tab": b"\t",
    f"{{{_WORD_NS}}}br": b"\n",
    f"{{{_WORD_NS}}}cr": b"\n",
}
_PROPERTY_LOCAL_NAMES = {
    "pPr",
    "rPr",
    "tblPr",
    "tblGrid",
    "trPr",
    "tcPr",
    "sectPr",
}
_WHOLE_FORMAT_PARTS = {
    "word/styles.xml",
    "word/numbering.xml",
    "word/settings.xml",
    "word/fontTable.xml",
    "word/theme/theme1.xml",
}


def compare_docx_formatting(
    before_path: str | Path,
    after_path: str | Path,
) -> dict[str, object]:
    """Compare semantic formatting while ignoring package compression noise."""

    before = docx_format_fingerprint(before_path)
    after = docx_format_fingerprint(after_path)
    before_elements = Counter(before.pop("element_hashes"))
    after_elements = Counter(after.pop("element_hashes"))
    removed = sum((before_elements - after_elements).values())
    added = sum((after_elements - before_elements).values())
    return {
        "schema_version": FORMAT_CHANGE_EVIDENCE_SCHEMA,
        "status": "compared",
        "format_changed": before["format_sha256"] != after["format_sha256"],
        "content_changed": before["content_sha256"] != after["content_sha256"],
        "format_elements_added": added,
        "format_elements_removed": removed,
        "before": before,
        "after": after,
    }


def docx_format_fingerprint(path: str | Path) -> dict[str, object]:
    source = Path(path).expanduser()
    if not source.is_file() or source.suffix.casefold() != ".docx":
        raise ValueError(f"docx_format_fingerprint_input_invalid:{source}")
    element_hashes: list[str] = []
    content = hashlib.sha256()
    whole_parts: dict[str, str] = {}
    with zipfile.ZipFile(source) as archive:
        names = set(archive.namelist())
        for name in sorted(names):
            if not _is_story_part(name):
                continue
            root = ET.fromstring(archive.read(name))
            content.update(name.encode("utf-8"))
            content.update(b"\0")
            for element in root.iter():
                if element.tag in _TEXT_TAGS and element.text:
                    content.update(element.text.encode("utf-8"))
                elif element.tag in _VISIBLE_CONTROL_TOKENS:
                    content.update(_VISIBLE_CONTROL_TOKENS[element.tag])
                if _local_name(element.tag) in _PROPERTY_LOCAL_NAMES:
                    element_hashes.append(_canonical_hash(element))
            content.update(b"\0")
        for name in sorted(_WHOLE_FORMAT_PARTS & names):
            root = ET.fromstring(archive.read(name))
            digest = _canonical_hash(root)
            whole_parts[name] = digest
            element_hashes.append(f"part:{name}:{digest}")
    format_digest = hashlib.sha256()
    for value in element_hashes:
        format_digest.update(value.encode("ascii"))
        format_digest.update(b"\n")
    return {
        "name": source.name,
        "format_sha256": format_digest.hexdigest(),
        "content_sha256": content.hexdigest(),
        "format_element_count": len(element_hashes),
        "whole_format_parts": whole_parts,
        "element_hashes": tuple(element_hashes),
    }


def _is_story_part(name: str) -> bool:
    if name == "word/document.xml":
        return True
    return bool(
        name.startswith("word/header")
        or name.startswith("word/footer")
        or name in {"word/footnotes.xml", "word/endnotes.xml", "word/comments.xml"}
    ) and name.endswith(".xml")


def _canonical_hash(element: ET.Element) -> str:
    serialized = ET.tostring(element, encoding="unicode")
    canonical = ET.canonicalize(serialized, strip_text=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


__all__ = [
    "FORMAT_CHANGE_EVIDENCE_SCHEMA",
    "compare_docx_formatting",
    "docx_format_fingerprint",
]
