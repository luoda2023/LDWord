"""Stable, versioned placeholder inventory for DOCX masters."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Mapping
from zipfile import BadZipFile, ZipFile

from lxml import etree

from src.shared.engine.material_token_contract import try_parse_material_token


MASTER_PLACEHOLDER_SCANNER_VERSION = "master-placeholder-index-v1"
_PLACEHOLDER_PATTERN = re.compile(r"\{\{([^{}\r\n]+)\}\}")
_REFERENCE_PAGE_HEADINGS = frozenset({"版式占位符说明", "母版占位符说明"})
_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_W = f"{{{_WORD_NS}}}"
_STORY_PART_PATTERN = re.compile(
    r"^word/(?:document|header\d+|footer\d+)\.xml$"
)


@dataclass(frozen=True, slots=True)
class MasterPlaceholderIndex:
    docx_path: Path
    sha256: str
    scanner_version: str
    placeholder_ids: tuple[str, ...]
    raw_occurrence_counts: tuple[tuple[str, int], ...]
    replaceable_occurrence_counts: tuple[tuple[str, int], ...]
    placeholder_surfaces: tuple[tuple[str, tuple[str, ...]], ...]
    reference_page_excluded: bool = False

    @property
    def raw_counts(self) -> dict[str, int]:
        return dict(self.raw_occurrence_counts)

    @property
    def replaceable_counts(self) -> dict[str, int]:
        return dict(self.replaceable_occurrence_counts)

    @property
    def replaceable_placeholder_ids(self) -> tuple[str, ...]:
        return tuple(key for key, _count in self.replaceable_occurrence_counts)

    def to_payload(self) -> dict[str, object]:
        return {
            "docx_path": str(self.docx_path),
            "sha256": self.sha256,
            "scanner_version": self.scanner_version,
            "placeholder_ids": list(self.placeholder_ids),
            "raw_occurrence_counts": self.raw_counts,
            "replaceable_occurrence_counts": self.replaceable_counts,
            "placeholder_surfaces": {
                key: list(surfaces) for key, surfaces in self.placeholder_surfaces
            },
            "reference_page_excluded": self.reference_page_excluded,
        }


_INDEX_CACHE: dict[tuple[str, int, int, str], MasterPlaceholderIndex] = {}


def scan_master_placeholder_index(
    path: Path | str,
    *,
    use_cache: bool = True,
) -> MasterPlaceholderIndex:
    """Return a stable inventory keyed by XML part and paragraph path."""

    target = Path(path).resolve()
    stat = target.stat()
    cache_key = (
        str(target),
        int(stat.st_size),
        int(stat.st_mtime_ns),
        MASTER_PLACEHOLDER_SCANNER_VERSION,
    )
    if use_cache and cache_key in _INDEX_CACHE:
        return _INDEX_CACHE[cache_key]

    raw_bytes = target.read_bytes()
    raw_counts: Counter[str] = Counter()
    replaceable_counts: Counter[str] = Counter()
    surfaces: dict[str, set[str]] = defaultdict(set)
    first_seen: list[str] = []
    reference_page_excluded = False
    try:
        with ZipFile(target) as archive:
            story_parts = sorted(
                name
                for name in archive.namelist()
                if _STORY_PART_PATTERN.fullmatch(name)
            )
            for part_name in story_parts:
                xml_bytes = archive.read(part_name)
                raw_root = etree.fromstring(xml_bytes)
                _collect_placeholders(
                    raw_root,
                    part_name=part_name,
                    counts=raw_counts,
                    first_seen=first_seen,
                )

                replaceable_root = etree.fromstring(xml_bytes)
                if part_name == "word/document.xml":
                    reference_page_excluded = (
                        _remove_reference_page(replaceable_root)
                        or reference_page_excluded
                    )
                _collect_placeholders(
                    replaceable_root,
                    part_name=part_name,
                    counts=replaceable_counts,
                    first_seen=first_seen,
                    surfaces=surfaces,
                )
    except (BadZipFile, etree.XMLSyntaxError) as exc:
        raise ValueError(f"Unreadable DOCX placeholder index: {target}") from exc

    ordered_ids = tuple(
        key for key in first_seen if key in raw_counts or key in replaceable_counts
    )
    result = MasterPlaceholderIndex(
        docx_path=target,
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
        scanner_version=MASTER_PLACEHOLDER_SCANNER_VERSION,
        placeholder_ids=ordered_ids,
        raw_occurrence_counts=tuple(
            (key, raw_counts[key]) for key in ordered_ids if raw_counts[key]
        ),
        replaceable_occurrence_counts=tuple(
            (key, replaceable_counts[key])
            for key in ordered_ids
            if replaceable_counts[key]
        ),
        placeholder_surfaces=tuple(
            (key, tuple(sorted(surfaces.get(key, ()))))
            for key in ordered_ids
            if surfaces.get(key)
        ),
        reference_page_excluded=reference_page_excluded,
    )
    if use_cache:
        _INDEX_CACHE.clear()
        _INDEX_CACHE[cache_key] = result
    return result


def _collect_placeholders(
    root,
    *,
    part_name: str,
    counts: Counter[str],
    first_seen: list[str],
    surfaces: dict[str, set[str]] | None = None,
) -> None:
    tree = root.getroottree()
    paragraph_text: dict[object, list[str]] = {}
    paragraph_order: list[object] = []
    for text_node in root.iter(f"{_W}t"):
        paragraph = _nearest_paragraph(text_node)
        if paragraph is None:
            continue
        if paragraph not in paragraph_text:
            paragraph_text[paragraph] = []
            paragraph_order.append(paragraph)
        paragraph_text[paragraph].append(str(text_node.text or ""))

    for paragraph in paragraph_order:
        text = "".join(paragraph_text[paragraph])
        surface_id = f"{part_name}:{tree.getpath(paragraph)}"
        for match in _PLACEHOLDER_PATTERN.finditer(text):
            raw_key = match.group(1)
            key = raw_key.strip()
            if not key or raw_key != key:
                continue
            counts[key] += 1
            if key not in first_seen:
                first_seen.append(key)
            if surfaces is not None:
                surfaces[key].add(surface_id)


def _nearest_paragraph(node):
    parent = node.getparent()
    while parent is not None:
        if parent.tag == f"{_W}p":
            return parent
        parent = parent.getparent()
    return None


def _remove_reference_page(root) -> bool:
    body = root.find(f".//{_W}body")
    if body is None:
        return False
    children = list(body)
    start_index = -1
    for index, child in enumerate(children):
        if child.tag != f"{_W}p":
            continue
        text = "".join(str(node.text or "") for node in child.iter(f"{_W}t"))
        if text.strip() in _REFERENCE_PAGE_HEADINGS:
            start_index = index
            break
    if start_index < 0:
        return False

    if start_index > 0:
        preceding = children[start_index - 1]
        has_section_break = preceding.find(f".//{_W}sectPr") is not None
        preceding_text = "".join(
            str(node.text or "") for node in preceding.iter(f"{_W}t")
        ).strip()
        if has_section_break and not preceding_text:
            body.remove(preceding)
            start_index -= 1
    for child in list(body)[start_index:]:
        if child.tag == f"{_W}sectPr":
            continue
        body.remove(child)
    return True


def placeholder_index_matches_payload(
    index: MasterPlaceholderIndex,
    payload: Mapping[str, object] | None,
) -> bool:
    value = dict(payload or {})
    return bool(
        str(value.get("sha256") or "") == index.sha256
        and str(value.get("scanner_version") or "") == index.scanner_version
        and tuple(value.get("placeholder_ids") or ()) == index.placeholder_ids
    )


def placeholder_identifier(value: object) -> str:
    """Return the contract identifier for one indexed placeholder surface.

    Master indexes intentionally retain the exact external spelling (for
    example ``@text:official_title``) so a manifest can detect a changed DOCX.
    Placeholder contracts, however, bind stable internal identifiers.  This
    boundary is the single place where an external material token is projected
    back to that identifier; non-material master placeholders remain unchanged.
    """

    raw = str(value or "").strip()
    parsed = try_parse_material_token(raw)
    return parsed.identifier if parsed is not None else raw


__all__ = [
    "MASTER_PLACEHOLDER_SCANNER_VERSION",
    "MasterPlaceholderIndex",
    "placeholder_index_matches_payload",
    "placeholder_identifier",
    "scan_master_placeholder_index",
]
