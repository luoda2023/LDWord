"""Profile-driven document count helpers."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from lxml import etree


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
COUNT_PROFILE_DIR = _PROJECT_ROOT / "count_profiles"
_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NS = {"w": _WORD_NS}
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_EN_WORD_RE = re.compile(r"[A-Za-z]+(?:[-'][A-Za-z]+)*")
_REFERENCE_HEADING_RE = re.compile(
    r"^\s*(?:\u53c2\u8003\u6587\u732e|references)\s*$",
    re.IGNORECASE,
)
_REFERENCE_STOP_RE = re.compile(
    r"^\s*(?:\u9644\u5f55|appendix|\u81f4\u8c22|acknowledg(?:e)?ments?"
    r"|\u58f0\u660e|declaration)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CountSectionLimit:
    """One section-level count limit declared by a CountProfile."""

    section_id: str
    label: str
    heading_patterns: tuple[str, ...] = ()
    max_characters_no_spaces: int = 0
    max_cjk_characters: int = 0
    max_english_words: int = 0
    required: bool = False


@dataclass(frozen=True)
class CountProfile:
    """Registered counting policy for one scene/compliance profile."""

    profile_id: str
    label: str
    source: str = "builtin"
    scope: str = "document"
    included_scopes: tuple[str, ...] = (
        "body",
        "reference_heading",
        "references",
        "back_matter",
        "tables",
    )
    excluded_scopes: tuple[str, ...] = ()
    primary_metrics: tuple[str, ...] = (
        "cjk_characters",
        "english_words",
        "characters_no_spaces",
        "reference_count",
    )
    count_references: bool = True
    count_tables: bool = True
    count_figures: bool = True
    count_equations: bool = True
    section_limits: tuple[CountSectionLimit, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CountEngineResult:
    """Structured multi-metric count result for one document/profile."""

    profile_id: str
    scope: str = "document"
    profile_name: str = ""
    profile_source: str = ""
    included_scopes: list[str] = field(default_factory=list)
    excluded_scopes: list[str] = field(default_factory=list)
    primary_metrics: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        metric_order = [
            ("cjk_characters", "CJK chars"),
            ("english_words", "English words"),
            ("characters_no_spaces", "chars no spaces"),
            ("paragraph_count", "paragraphs"),
            ("reference_count", "references"),
            ("figure_count", "figures"),
            ("table_count", "tables"),
            ("equation_count", "equations"),
        ]
        parts = [
            f"{label} {self.counts[key]}"
            for key, label in metric_order
            if key in self.counts
        ]
        return f"{self.profile_id}: " + "; ".join(parts)


def count_document(doc, *, profile_id: str = "basic") -> CountEngineResult:
    """Count common Word document metrics without claiming one canonical policy."""

    profile = get_count_profile(profile_id)
    paragraph_texts = _body_paragraph_texts(doc)
    paragraph_sections = _classify_paragraph_sections(paragraph_texts)
    table_texts = _table_texts(doc)
    xml_scope_texts = _extended_xml_scope_texts(doc)
    included_paragraph_texts = [
        text
        for text, section in zip(paragraph_texts, paragraph_sections, strict=False)
        if _scope_included(section, profile)
    ]
    text_parts = [*included_paragraph_texts]
    if _scope_included("tables", profile):
        text_parts.extend(table_texts)
    for scope, texts in xml_scope_texts.items():
        if _scope_included(scope, profile):
            text_parts.extend(texts)
    all_text = "\n".join(text_parts)
    non_empty_paragraphs = [text for text in included_paragraph_texts if text.strip()]
    xml_scope_counts = {f"{scope}_count": len(texts) for scope, texts in xml_scope_texts.items()}

    counts = {
        "cjk_characters": len(_CJK_RE.findall(all_text)),
        "han_characters": len(_CJK_RE.findall(all_text)),
        "english_words": len(_EN_WORD_RE.findall(all_text)),
        "english_characters": sum(
            1 for char in all_text if char.isascii() and char.isalpha()
        ),
        "characters_no_spaces": sum(1 for char in all_text if not char.isspace()),
        "characters_with_spaces": len(all_text),
        "word_like_words": len(_EN_WORD_RE.findall(all_text)) + len(_CJK_RE.findall(all_text)),
        "punctuation_count": sum(1 for char in all_text if _is_punctuation(char)),
        "number_tokens": len(re.findall(r"\d+(?:[.,]\d+)*", all_text)),
        "paragraph_count": len(non_empty_paragraphs),
        "table_count": len(doc.tables) if profile.count_tables else 0,
        "figure_count": (
            len(getattr(doc, "inline_shapes", []) or []) if profile.count_figures else 0
        ),
        "equation_count": _count_equations(doc) if profile.count_equations else 0,
        "reference_count": (
            _count_references(paragraph_texts) if profile.count_references else 0
        ),
        **xml_scope_counts,
    }
    notes = [
        "Counts are computed by the local profile-driven CountEngine and may differ from Microsoft Word or target submission systems.",
        *profile.notes,
    ]
    return CountEngineResult(
        profile_id=profile.profile_id,
        scope=profile.scope,
        profile_name=profile.label,
        profile_source=profile.source,
        included_scopes=list(profile.included_scopes),
        excluded_scopes=list(profile.excluded_scopes),
        primary_metrics=list(profile.primary_metrics),
        counts=counts,
        notes=notes,
    )


def list_count_profiles() -> tuple[CountProfile, ...]:
    return COUNT_PROFILES


def get_count_profile(profile_id: str) -> CountProfile:
    normalized = str(profile_id or "").strip() or "basic"
    profile = COUNT_PROFILE_MAP.get(normalized)
    if profile is not None:
        return profile
    return CountProfile(
        profile_id=normalized,
        label=f"Ad hoc count profile: {normalized}",
        notes=(
            "This count profile is not registered; the broad local document scope was used.",
        ),
    )


def load_count_profiles_from_directory(directory: str | Path) -> tuple[CountProfile, ...]:
    """Load count profiles from JSON files in a directory."""

    root = Path(directory)
    if not root.exists():
        return ()
    profiles: list[CountProfile] = []
    seen: set[str] = set()
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries = payload.get("profiles", payload)
        if isinstance(entries, dict):
            entries = [entries]
        if not isinstance(entries, list):
            raise ValueError(f"Invalid count profile file: {path}")
        for item in entries:
            if not isinstance(item, dict):
                raise ValueError(f"Invalid count profile entry in: {path}")
            profile = _profile_from_payload(item, source=str(path))
            if profile.profile_id in seen:
                raise ValueError(f"Duplicate count profile id: {profile.profile_id}")
            seen.add(profile.profile_id)
            profiles.append(profile)
    return tuple(profiles)


def _profile_from_payload(payload: dict[str, Any], *, source: str) -> CountProfile:
    profile_id = str(payload.get("profile_id") or "").strip()
    if not profile_id:
        raise ValueError("Count profile requires profile_id")
    label = str(payload.get("label") or profile_id).strip()
    return CountProfile(
        profile_id=profile_id,
        label=label,
        source=str(payload.get("source") or source),
        scope=str(payload.get("scope") or "document").strip() or "document",
        included_scopes=_tuple_field(payload, "included_scopes", CountProfile.included_scopes),
        excluded_scopes=_tuple_field(payload, "excluded_scopes", ()),
        primary_metrics=_tuple_field(payload, "primary_metrics", CountProfile.primary_metrics),
        count_references=bool(payload.get("count_references", True)),
        count_tables=bool(payload.get("count_tables", True)),
        count_figures=bool(payload.get("count_figures", True)),
        count_equations=bool(payload.get("count_equations", True)),
        section_limits=_section_limits_field(payload.get("section_limits", [])),
        notes=_tuple_field(payload, "notes", ()),
    )


def _tuple_field(
    payload: dict[str, Any],
    key: str,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    value = payload.get(key, default)
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value if str(item or "").strip())


def _section_limits_field(value: object) -> tuple[CountSectionLimit, ...]:
    if not isinstance(value, list):
        return ()
    limits: list[CountSectionLimit] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        section_id = str(item.get("section_id") or "").strip()
        if not section_id:
            continue
        limits.append(
            CountSectionLimit(
                section_id=section_id,
                label=str(item.get("label") or section_id).strip() or section_id,
                heading_patterns=_tuple_field(item, "heading_patterns", ()),
                max_characters_no_spaces=_int_field(item, "max_characters_no_spaces"),
                max_cjk_characters=_int_field(item, "max_cjk_characters"),
                max_english_words=_int_field(item, "max_english_words"),
                required=bool(item.get("required", False)),
            )
        )
    return tuple(limits)


def _int_field(payload: dict[str, Any], key: str) -> int:
    try:
        return max(0, int(payload.get(key) or 0))
    except (TypeError, ValueError):
        return 0


COUNT_PROFILES: tuple[CountProfile, ...] = load_count_profiles_from_directory(
    COUNT_PROFILE_DIR
)

COUNT_PROFILE_MAP: dict[str, CountProfile] = {
    profile.profile_id: profile for profile in COUNT_PROFILES
}


def _body_paragraph_texts(doc) -> list[str]:
    root = _part_root(doc, "/word/document.xml")
    if root is None:
        return [str(paragraph.text or "") for paragraph in doc.paragraphs]
    body = root.find("w:body", namespaces=_NS)
    if body is None:
        return []
    texts: list[str] = []
    for paragraph in body.findall("w:p", namespaces=_NS):
        texts.append(_visible_text(paragraph))
    return texts


def _extended_xml_scope_texts(doc) -> dict[str, list[str]]:
    document_root = _part_root(doc, "/word/document.xml")
    field_codes, field_results = _field_scope_texts(doc)
    return {
        "headers": _prefixed_part_texts(doc, "/word/header"),
        "footers": _prefixed_part_texts(doc, "/word/footer"),
        "footnotes": _part_texts(doc, "/word/footnotes.xml"),
        "endnotes": _part_texts(doc, "/word/endnotes.xml"),
        "comments": _part_texts(doc, "/word/comments.xml"),
        "textboxes": _textbox_texts(document_root),
        "hidden_text": _hidden_texts(document_root),
        "tracked_changes": _tracked_change_texts(document_root),
        "field_codes": field_codes,
        "field_results": field_results,
    }


def _table_texts(doc) -> list[str]:
    texts: list[str] = []
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                cell_text = "\n".join(str(paragraph.text or "") for paragraph in cell.paragraphs)
                if cell_text.strip():
                    texts.append(cell_text)
    return texts


def _part_texts(doc, partname: str) -> list[str]:
    root = _part_root(doc, partname)
    if root is None:
        return []
    return _grouped_paragraph_texts(root)


def _prefixed_part_texts(doc, partname_prefix: str) -> list[str]:
    texts: list[str] = []
    for root in _prefixed_part_roots(doc, partname_prefix):
        texts.extend(_grouped_paragraph_texts(root))
    return texts


def _part_root(doc, partname: str):
    part = _package_part(doc, partname)
    if part is None:
        return None
    blob = getattr(part, "blob", b"")
    if not blob:
        return None
    try:
        return etree.fromstring(blob)
    except Exception:
        return None


def _package_part(doc, partname: str):
    package = getattr(getattr(doc, "part", None), "package", None)
    parts = getattr(package, "parts", None) or []
    normalized = "/" + str(partname or "").lstrip("/")
    for part in parts:
        if str(getattr(part, "partname", "")) == normalized:
            return part
    return None


def _prefixed_part_roots(doc, partname_prefix: str) -> list[Any]:
    package = getattr(getattr(doc, "part", None), "package", None)
    parts = getattr(package, "parts", None) or []
    normalized = "/" + str(partname_prefix or "").lstrip("/")
    roots: list[Any] = []
    for part in parts:
        partname = str(getattr(part, "partname", ""))
        if not partname.startswith(normalized):
            continue
        blob = getattr(part, "blob", b"")
        if not blob:
            continue
        try:
            roots.append(etree.fromstring(blob))
        except Exception:
            continue
    return roots


def _grouped_paragraph_texts(root) -> list[str]:
    paragraphs = root.xpath(".//w:p", namespaces=_NS)
    if not paragraphs:
        text = _visible_text(root)
        return [text] if text.strip() else []
    texts: list[str] = []
    for paragraph in paragraphs:
        text = _visible_text(paragraph)
        if text.strip():
            texts.append(text)
    return texts


def _textbox_texts(root) -> list[str]:
    if root is None:
        return []
    hosts = root.xpath(".//*[local-name()='txbxContent' or local-name()='textbox']")
    texts: list[str] = []
    for host in hosts:
        text = _text_under(host, allow_textbox=True)
        if text.strip():
            texts.append(text)
    return texts


def _hidden_texts(root) -> list[str]:
    if root is None:
        return []
    texts: list[str] = []
    for run in root.xpath(".//w:r[w:rPr/w:vanish]", namespaces=_NS):
        text = _text_under(run, allow_hidden=True, allow_tracked=True)
        if text.strip():
            texts.append(text)
    return texts


def _tracked_change_texts(root) -> list[str]:
    if root is None:
        return []
    texts: list[str] = []
    for node in root.xpath(
        ".//*[local-name()='ins' or local-name()='del' or local-name()='moveFrom' or local-name()='moveTo']"
    ):
        text = _text_under(node, allow_hidden=True, allow_tracked=True)
        if text.strip():
            texts.append(text)
    return texts


def _field_scope_texts(doc) -> tuple[list[str], list[str]]:
    codes: list[str] = []
    results: list[str] = []
    for root in _word_story_roots(doc):
        codes.extend(_field_code_texts(root))
        results.extend(_field_result_texts(root))
    return codes, results


def _word_story_roots(doc) -> list[Any]:
    roots: list[Any] = []
    for partname in (
        "/word/document.xml",
        "/word/footnotes.xml",
        "/word/endnotes.xml",
        "/word/comments.xml",
    ):
        root = _part_root(doc, partname)
        if root is not None:
            roots.append(root)
    roots.extend(_prefixed_part_roots(doc, "/word/header"))
    roots.extend(_prefixed_part_roots(doc, "/word/footer"))
    return roots


def _field_code_texts(root) -> list[str]:
    if root is None:
        return []
    codes: list[str] = []
    for field in root.xpath(".//*[local-name()='fldSimple']"):
        instr = field.get(f"{{{_WORD_NS}}}instr") or field.get("instr") or ""
        if instr.strip():
            codes.append(instr.strip())
    paragraph_codes: list[str] = []
    for node in root.xpath(".//*[local-name()='instrText']"):
        text = str(node.text or "").strip()
        if text:
            paragraph_codes.append(text)
    if paragraph_codes:
        codes.append(" ".join(paragraph_codes))
    return codes


def _field_result_texts(root) -> list[str]:
    if root is None:
        return []
    results: list[str] = []
    for field in root.xpath(".//*[local-name()='fldSimple']"):
        result = _text_under(field, allow_textbox=True)
        if result.strip():
            results.append(result)
    for paragraph in root.xpath(".//w:p", namespaces=_NS):
        results.extend(_complex_field_results(paragraph))
    return results


def _complex_field_results(paragraph) -> list[str]:
    results: list[str] = []
    in_field = False
    in_result = False
    chunks: list[str] = []
    for child in paragraph:
        if _local_name(child) != "r":
            continue
        field_types = [
            str(node.get(f"{{{_WORD_NS}}}fldCharType") or "")
            for node in child.xpath("./w:fldChar", namespaces=_NS)
        ]
        if "begin" in field_types:
            in_field = True
            in_result = False
            chunks = []
            continue
        if "separate" in field_types and in_field:
            in_result = True
            continue
        if "end" in field_types and in_field:
            result = "".join(chunks)
            if result.strip():
                results.append(result)
            in_field = False
            in_result = False
            chunks = []
            continue
        if in_field and in_result:
            chunks.append(_text_under(child, allow_textbox=True))
    return results


def _visible_text(node) -> str:
    return _text_under(node, allow_hidden=False, allow_tracked=False)


def _text_under(
    node,
    *,
    allow_hidden: bool = False,
    allow_tracked: bool = False,
    allow_textbox: bool = False,
) -> str:
    chunks: list[str] = []
    for text_node in node.xpath(".//*[local-name()='t' or local-name()='delText']"):
        if not allow_tracked and _has_ancestor_named(
            text_node, {"ins", "del", "moveFrom", "moveTo"}
        ):
            continue
        if not allow_hidden and _has_hidden_run(text_node):
            continue
        if not allow_textbox and _has_ancestor_named(text_node, {"txbxContent", "textbox"}):
            continue
        value = text_node.text or ""
        if value:
            chunks.append(value)
    return "".join(chunks)


def _has_hidden_run(node) -> bool:
    for ancestor in node.iterancestors():
        if _local_name(ancestor) != "r":
            continue
        return bool(ancestor.xpath("./w:rPr/w:vanish", namespaces=_NS))
    return False


def _has_ancestor_named(node, names: set[str]) -> bool:
    return any(_local_name(ancestor) in names for ancestor in node.iterancestors())


def _local_name(node) -> str:
    tag = getattr(node, "tag", "")
    if not isinstance(tag, str):
        return ""
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _count_equations(doc) -> int:
    body = getattr(doc, "_element", None)
    if body is None:
        return 0
    try:
        return len(body.xpath(".//m:oMathPara | .//m:oMath"))
    except Exception:
        return len(
            body.xpath(
                ".//*[local-name()='oMathPara'] | .//*[local-name()='oMath']"
            )
        )


def _count_references(paragraph_texts: list[str]) -> int:
    in_references = False
    count = 0
    for text in paragraph_texts:
        stripped = text.strip()
        if not stripped:
            continue
        if not in_references:
            if _REFERENCE_HEADING_RE.match(stripped):
                in_references = True
            continue
        if _REFERENCE_STOP_RE.match(stripped):
            break
        count += 1
    return count


def _classify_paragraph_sections(paragraph_texts: list[str]) -> list[str]:
    sections: list[str] = []
    in_references = False
    after_reference_stop = False
    for text in paragraph_texts:
        stripped = text.strip()
        if after_reference_stop:
            sections.append("back_matter")
            continue
        if in_references:
            if _REFERENCE_STOP_RE.match(stripped):
                after_reference_stop = True
                sections.append("back_matter")
            else:
                sections.append("references")
            continue
        if _REFERENCE_HEADING_RE.match(stripped):
            in_references = True
            sections.append("reference_heading")
            continue
        sections.append("body")
    return sections


def _scope_included(scope: str, profile: CountProfile) -> bool:
    if scope in profile.excluded_scopes:
        return False
    return scope in profile.included_scopes


def _is_punctuation(char: str) -> bool:
    if not char or char.isspace() or char.isalnum() or _CJK_RE.match(char):
        return False
    category = unicodedata.category(char)
    return category.startswith("P") or category.startswith("S")


__all__ = [
    "COUNT_PROFILE_DIR",
    "COUNT_PROFILES",
    "COUNT_PROFILE_MAP",
    "CountEngineResult",
    "CountProfile",
    "CountSectionLimit",
    "count_document",
    "get_count_profile",
    "load_count_profiles_from_directory",
    "list_count_profiles",
]
