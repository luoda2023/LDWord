"""Shared semantics for logical document sections and style-key routing."""

from __future__ import annotations

SECTION_TYPE_ALIASES: dict[str, str] = {
    "references": "references",
    "bibliography": "references",
    "abstract_cn": "abstract_cn",
    "abstract_en": "abstract_en",
    "appendix": "appendix",
    "toc": "toc",
    "body": "body",
    "pre_numbering": "pre_numbering",
    "errata": "errata",
    "acknowledgement": "acknowledgment",
    "acknowledgements": "acknowledgment",
    "acknowledgment": "acknowledgment",
    "resume": "resume",
    "bio": "resume",
}

SECTION_STYLE_KEY_MAP: dict[str, str] = {
    "references": "references_body",
    "abstract_cn": "abstract_body",
    "abstract_en": "abstract_body",
    "appendix": "appendix_body",
    "acknowledgment": "acknowledgment_body",
    "resume": "resume_body",
}

STYLE_ALIAS_GROUPS: dict[str, tuple[str, ...]] = {
    "references_body": ("references_body",),
    "abstract_body": ("abstract_body", "abstract_body_en"),
    "appendix_body": ("appendix_body",),
    "acknowledgment_body": ("acknowledgment_body", "acknowledgements_body"),
    "resume_body": ("resume_body", "bio_body"),
}


def canonicalize_section_type(section_type: str | None) -> str:
    raw = str(section_type or "").strip().lower()
    if not raw:
        return "body"
    return SECTION_TYPE_ALIASES.get(raw, raw)


def style_key_for_section(section_type: str | None) -> str | None:
    canonical = canonicalize_section_type(section_type)
    return SECTION_STYLE_KEY_MAP.get(canonical)
