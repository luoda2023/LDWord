"""Text helpers for fixed-layout Word surfaces.

python-docx exposes normal paragraphs and table cells well, but fixed-layout
forms often keep user-visible text inside structured document tags or textboxes.
These helpers provide a narrow runtime path for those surfaces without treating
them as ordinary body paragraphs.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping, Sequence

from src.shared.engine.ooxml_ops import qn


FIXED_LAYOUT_TEXT_SURFACES: tuple[str, ...] = (
    "textboxes",
    "content_controls",
)


@dataclass(frozen=True, slots=True)
class FixedLayoutTextBlock:
    surface: str
    text: str


@dataclass(frozen=True, slots=True)
class FixedLayoutTextReplacementResult:
    total_replacements: int = 0
    content_control_replacements: int = 0
    textbox_replacements: int = 0
    replaced_tokens: tuple[str, ...] = ()

    @property
    def has_replacements(self) -> bool:
        return self.total_replacements > 0


@dataclass(frozen=True, slots=True)
class FixedLayoutMappedFieldReplacementResult:
    total_replacements: int = 0
    content_control_replacements: int = 0
    textbox_replacements: int = 0
    replaced_fields: tuple[str, ...] = ()
    matched_identifiers: tuple[str, ...] = ()

    @property
    def has_replacements(self) -> bool:
        return self.total_replacements > 0


def replace_fixed_layout_placeholders(
    document,
    replacements: Mapping[str, str],
) -> FixedLayoutTextReplacementResult:
    """Replace placeholders inside ``w:sdt`` and textbox XML surfaces."""

    normalized_replacements = _normalized_replacements(replacements)
    if not normalized_replacements:
        return FixedLayoutTextReplacementResult()

    counts = {
        "content_controls": 0,
        "textboxes": 0,
    }
    replaced_tokens: list[str] = []
    visited_text_nodes: set[str] = set()

    for root_index, root in enumerate(_document_story_roots(document)):
        for host in _textbox_hosts(root):
            replaced = _replace_text_nodes(
                host,
                normalized_replacements,
                visited_text_nodes,
                replaced_tokens,
                root_index=root_index,
            )
            counts["textboxes"] += replaced
        for host in root.findall(f".//{qn('w:sdt')}"):
            replaced = _replace_text_nodes(
                host,
                normalized_replacements,
                visited_text_nodes,
                replaced_tokens,
                root_index=root_index,
            )
            counts["content_controls"] += replaced

    return FixedLayoutTextReplacementResult(
        total_replacements=sum(counts.values()),
        content_control_replacements=counts["content_controls"],
        textbox_replacements=counts["textboxes"],
        replaced_tokens=tuple(replaced_tokens),
    )


def replace_fixed_layout_mapped_fields(
    document,
    field_values: Mapping[str, str],
    *,
    field_aliases: Mapping[str, str] | None = None,
    schema_ids: Sequence[str] | None = None,
) -> FixedLayoutMappedFieldReplacementResult:
    """Fill fixed-layout controls by field tags, aliases, or textbox anchors."""

    normalized_values = _normalized_replacements(field_values)
    if not normalized_values:
        return FixedLayoutMappedFieldReplacementResult()

    field_lookup = _field_identifier_lookup(
        normalized_values,
        schema_ids or (),
        field_aliases or {},
    )
    if not field_lookup:
        return FixedLayoutMappedFieldReplacementResult()

    counts = {
        "content_controls": 0,
        "textboxes": 0,
    }
    replaced_fields: list[str] = []
    matched_identifiers: list[str] = []
    visited_text_nodes: set[str] = set()

    for root_index, root in enumerate(_document_story_roots(document)):
        for host in _textbox_hosts(root):
            field_key, identifier = _matched_field_key(
                _textbox_identifiers(host),
                field_lookup,
            )
            if not field_key:
                continue
            replaced = _replace_host_text(
                host,
                normalized_values[field_key],
                visited_text_nodes,
                root_index=root_index,
            )
            if replaced:
                counts["textboxes"] += replaced
                _append_once(replaced_fields, field_key)
                _append_once(matched_identifiers, identifier)
        for host in root.findall(f".//{qn('w:sdt')}"):
            field_key, identifier = _matched_field_key(
                _content_control_identifiers(host),
                field_lookup,
            )
            if not field_key:
                continue
            replaced = _replace_host_text(
                host,
                normalized_values[field_key],
                visited_text_nodes,
                root_index=root_index,
            )
            if replaced:
                counts["content_controls"] += replaced
                _append_once(replaced_fields, field_key)
                _append_once(matched_identifiers, identifier)

    return FixedLayoutMappedFieldReplacementResult(
        total_replacements=sum(counts.values()),
        content_control_replacements=counts["content_controls"],
        textbox_replacements=counts["textboxes"],
        replaced_fields=tuple(replaced_fields),
        matched_identifiers=tuple(matched_identifiers),
    )


def iter_fixed_layout_text_blocks(document) -> tuple[FixedLayoutTextBlock, ...]:
    """Return visible text found in fixed-layout XML surfaces."""

    blocks: list[FixedLayoutTextBlock] = []
    visited_text_nodes: set[str] = set()
    for root_index, root in enumerate(_document_story_roots(document)):
        for host in _textbox_hosts(root):
            text = _text_under_host(host, visited_text_nodes, root_index=root_index)
            if text.strip():
                blocks.append(FixedLayoutTextBlock(surface="textboxes", text=text.strip()))
        for host in root.findall(f".//{qn('w:sdt')}"):
            text = _text_under_host(host, visited_text_nodes, root_index=root_index)
            if text.strip():
                blocks.append(
                    FixedLayoutTextBlock(surface="content_controls", text=text.strip())
                )
    return tuple(blocks)


def _normalized_replacements(replacements: Mapping[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for old, new in dict(replacements or {}).items():
        old_text = str(old or "")
        if not old_text:
            continue
        result[old_text] = str(new or "")
    return result


def _field_identifier_lookup(
    field_values: Mapping[str, str],
    schema_ids: Sequence[str],
    field_aliases: Mapping[str, str],
) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for key in field_values:
        _register_field_identifier(lookup, key, key)

    for alias, field_key in dict(field_aliases or {}).items():
        normalized_field_key = str(field_key or "").strip()
        if normalized_field_key not in field_values:
            continue
        _register_field_identifier(lookup, str(alias or ""), normalized_field_key)

    try:
        from src.config.material_schema_registry import MATERIAL_SCHEMA_MAP
    except Exception:
        return lookup

    for schema_id in _unique_texts(schema_ids):
        schema = MATERIAL_SCHEMA_MAP.get(schema_id)
        if schema is None:
            continue
        for field in schema.fields:
            if field.key not in field_values:
                continue
            for identifier in (field.key, field.label, *field.aliases):
                _register_field_identifier(lookup, identifier, field.key)
    return lookup


def _register_field_identifier(
    lookup: dict[str, str],
    identifier: str,
    field_key: str,
) -> None:
    for candidate in _identifier_candidates(identifier):
        normalized = _normalize_identifier(candidate)
        if normalized:
            lookup.setdefault(normalized, field_key)


def _matched_field_key(
    identifiers: Sequence[str],
    field_lookup: Mapping[str, str],
) -> tuple[str, str]:
    for identifier in identifiers:
        for candidate in _identifier_candidates(identifier):
            field_key = field_lookup.get(_normalize_identifier(candidate))
            if field_key:
                return field_key, candidate
    return "", ""


def _content_control_identifiers(host) -> tuple[str, ...]:
    identifiers: list[str] = []
    properties = host.find(qn("w:sdtPr"))
    if properties is None:
        return ()
    for tag_name in ("w:tag", "w:alias"):
        element = properties.find(qn(tag_name))
        if element is not None:
            _append_once(identifiers, element.get(qn("w:val")) or "")
    return tuple(identifiers)


def _textbox_identifiers(host) -> tuple[str, ...]:
    identifiers: list[str] = []
    current = host
    depth = 0
    while current is not None and depth < 10:
        _collect_element_identifiers(current, identifiers)
        for element in current.xpath(
            "./*[local-name()='docPr' or local-name()='cNvPr' or local-name()='shape']"
        ):
            _collect_element_identifiers(element, identifiers)
        current = current.getparent()
        depth += 1
    return tuple(identifiers)


def _collect_element_identifiers(element, identifiers: list[str]) -> None:
    for attr_name, value in element.attrib.items():
        local_name = attr_name.rsplit("}", 1)[-1]
        if local_name in {"name", "descr", "title", "alt", "id"}:
            _append_once(identifiers, value)


def _identifier_candidates(value: str) -> tuple[str, ...]:
    raw = str(value or "").strip()
    if not raw:
        return ()
    candidates: list[str] = []
    for part in re.split(r"[|;,，；\n\r]+", raw):
        part = part.strip()
        if not part:
            continue
        _append_once(candidates, part)
        for separator in (":", "=", "："):
            if separator in part:
                right = part.rsplit(separator, 1)[-1].strip()
                left = part.split(separator, 1)[0].strip()
                _append_once(candidates, right)
                _append_once(candidates, left)
    return tuple(candidates)


def _normalize_identifier(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[\s\-.\\/]+", "_", text)
    text = re.sub(r"[^0-9a-z_\u4e00-\u9fff]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    for prefix in ("field", "material", "placeholder", "tag", "key", "name"):
        prefix_text = prefix + "_"
        if text.startswith(prefix_text):
            text = text[len(prefix_text) :]
    return text


def _replace_text_nodes(
    host,
    replacements: dict[str, str],
    visited_text_nodes: set[str],
    replaced_tokens: list[str],
    *,
    root_index: int,
) -> int:
    text_nodes = []
    for text_node in host.findall(f".//{qn('w:t')}"):
        node_key = _text_node_key(text_node, root_index=root_index)
        if node_key in visited_text_nodes:
            continue
        visited_text_nodes.add(node_key)
        text_nodes.append(text_node)
    if not text_nodes:
        return 0

    texts = [str(text_node.text or "") for text_node in text_nodes]
    full_text = "".join(texts)
    matches = _non_overlapping_replacement_matches(full_text, replacements)
    if not matches:
        return 0

    starts: list[int] = []
    offset = 0
    for text in texts:
        starts.append(offset)
        offset += len(text)

    for start, end, old, new in sorted(matches, reverse=True):
        start_index, start_offset = _text_item_position(starts, texts, start)
        end_index, end_offset = _text_item_position(starts, texts, end - 1)
        end_offset += 1
        if start_index == end_index:
            current = str(text_nodes[start_index].text or "")
            text_nodes[start_index].text = (
                current[:start_offset] + new + current[end_offset:]
            )
        else:
            first_text = str(text_nodes[start_index].text or "")
            last_text = str(text_nodes[end_index].text or "")
            text_nodes[start_index].text = first_text[:start_offset] + new
            for node_index in range(start_index + 1, end_index):
                text_nodes[node_index].text = ""
            text_nodes[end_index].text = last_text[end_offset:]
        if old not in replaced_tokens:
            replaced_tokens.append(old)
    return len(matches)


def _non_overlapping_replacement_matches(
    text: str,
    replacements: Mapping[str, str],
) -> list[tuple[int, int, str, str]]:
    matches: list[tuple[int, int, str, str]] = []
    occupied: list[tuple[int, int]] = []
    for old, new in replacements.items():
        start = 0
        while True:
            index = text.find(old, start)
            if index < 0:
                break
            end = index + len(old)
            if not any(index < used_end and end > used_start for used_start, used_end in occupied):
                matches.append((index, end, old, new))
                occupied.append((index, end))
            start = end
    return matches


def _text_item_position(
    starts: Sequence[int],
    texts: Sequence[str],
    position: int,
) -> tuple[int, int]:
    for index in range(len(texts) - 1, -1, -1):
        if position >= starts[index] and texts[index]:
            return index, position - starts[index]
    return 0, max(0, position)


def _replace_host_text(
    host,
    value: str,
    visited_text_nodes: set[str],
    *,
    root_index: int,
) -> int:
    text_nodes = []
    for text_node in host.findall(f".//{qn('w:t')}"):
        node_key = _text_node_key(text_node, root_index=root_index)
        if node_key in visited_text_nodes:
            continue
        visited_text_nodes.add(node_key)
        text_nodes.append(text_node)
    if not text_nodes:
        return 0

    current_text = "".join(text_node.text or "" for text_node in text_nodes)
    next_text = str(value or "")
    if current_text == next_text:
        return 0

    text_nodes[0].text = next_text
    if next_text != next_text.strip():
        text_nodes[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    for text_node in text_nodes[1:]:
        text_node.text = ""
    return 1


def _text_under_host(host, visited_text_nodes: set[str], *, root_index: int) -> str:
    parts: list[str] = []
    for text_node in host.findall(f".//{qn('w:t')}"):
        node_key = _text_node_key(text_node, root_index=root_index)
        if node_key in visited_text_nodes:
            continue
        visited_text_nodes.add(node_key)
        if text_node.text:
            parts.append(str(text_node.text))
    return "".join(parts)


def _text_node_key(text_node, *, root_index: int) -> str:
    return f"{root_index}:{text_node.getroottree().getpath(text_node)}"


def _textbox_hosts(root) -> list:
    hosts: list = []
    for pattern in (
        ".//*[local-name()='txbxContent']",
        ".//*[local-name()='textbox']",
    ):
        for host in root.xpath(pattern):
            if host not in hosts:
                hosts.append(host)
    return hosts


def _document_story_roots(document) -> tuple:
    roots = [document._element]
    for section in list(getattr(document, "sections", []) or []):
        for part in (section.header, section.footer):
            element = getattr(part, "_element", None)
            if element is not None:
                roots.append(element)
    return tuple(roots)


def _append_once(items: list[str], value: str) -> None:
    normalized = str(value or "").strip()
    if normalized and normalized not in items:
        items.append(normalized)


def _unique_texts(values: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "FIXED_LAYOUT_TEXT_SURFACES",
    "FixedLayoutMappedFieldReplacementResult",
    "FixedLayoutTextBlock",
    "FixedLayoutTextReplacementResult",
    "iter_fixed_layout_text_blocks",
    "replace_fixed_layout_mapped_fields",
    "replace_fixed_layout_placeholders",
]
