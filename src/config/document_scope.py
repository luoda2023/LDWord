"""Persisted plan intent for document-region processing.

The policy deliberately does not contain document paths, paragraph indices,
page numbers, detector settings, or style values.  It says only which logical
regions a plan is allowed to modify after the current input has been analysed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from src.config.section_semantics import canonicalize_section_type


DocumentScopeMode = Literal["all", "body", "selected"]

DOCUMENT_SCOPE_MODES: tuple[str, ...] = ("all", "body", "selected")

_ROLE_LABELS: dict[str, str] = {
    "cover": "封面",
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

ALL_DOCUMENT_REGION_ROLES: tuple[str, ...] = tuple(_ROLE_LABELS)
_COMMON_ROLES = ("toc", "body", "references", "appendix")

# Reusable plans declare which region types they can target.  This is a
# capability list, not a claim that every input document contains every role;
# the execution workbench intersects it with current-document scan evidence.
_SELECTABLE_ROLES_BY_MODE: dict[str, tuple[str, ...]] = {
    "custom": _COMMON_ROLES,
    "thesis": (
        "abstract_cn",
        "abstract_en",
        "toc",
        "body",
        "references",
        "appendix",
        "acknowledgment",
        "resume",
    ),
    "report": _COMMON_ROLES,
    "technical": _COMMON_ROLES,
    "bidding": ("toc", "body", "appendix"),
    # Official documents and exam papers use structured/master assembly.
    "official": (),
    "exam": (),
}


@dataclass
class DocumentScopePolicy:
    """One plan's persisted content-region selection."""

    mode: DocumentScopeMode | str = "all"
    selected_roles: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.mode = str(self.mode or "").strip() or "all"
        normalized: list[str] = []
        for role in self.selected_roles or ():
            candidate = canonicalize_section_type(role)
            if candidate and candidate not in normalized:
                normalized.append(candidate)
        self.selected_roles = normalized

    def included_roles(self, mode_id: str) -> tuple[str, ...]:
        selectable = selectable_document_scope_roles(mode_id)
        if self.mode == "all":
            return ALL_DOCUMENT_REGION_ROLES if selectable else ()
        if self.mode == "body":
            return ("body",) if "body" in selectable else ()
        if self.mode == "selected":
            selected = set(self.selected_roles)
            return tuple(role for role in selectable if role in selected)
        return ()

    def includes(self, section_type: str, *, mode_id: str) -> bool:
        return canonicalize_section_type(section_type) in self.included_roles(mode_id)


def selectable_document_scope_roles(mode_id: str) -> tuple[str, ...]:
    normalized = str(mode_id or "").strip() or "custom"
    return _SELECTABLE_ROLES_BY_MODE.get(normalized, _COMMON_ROLES)


def document_scope_role_label(role_id: str) -> str:
    canonical = canonicalize_section_type(role_id)
    return _ROLE_LABELS.get(canonical, canonical)


def coerce_document_scope_policy(
    value: DocumentScopePolicy | dict | None,
) -> DocumentScopePolicy:
    if isinstance(value, DocumentScopePolicy):
        return DocumentScopePolicy(
            mode=value.mode,
            selected_roles=list(value.selected_roles),
        )
    if isinstance(value, dict):
        return DocumentScopePolicy(
            mode=value.get("mode", "all"),
            selected_roles=list(value.get("selected_roles", ()) or ()),
        )
    return DocumentScopePolicy()


def document_scope_policy_issue(
    value: DocumentScopePolicy | dict | None,
    *,
    mode_id: str,
) -> str:
    policy = coerce_document_scope_policy(value)
    if policy.mode not in DOCUMENT_SCOPE_MODES:
        return f"document_scope_mode_invalid:{policy.mode}"

    selectable = set(selectable_document_scope_roles(mode_id))
    unsupported = tuple(
        role for role in policy.selected_roles if role not in selectable
    )
    if unsupported:
        return "document_scope_roles_unsupported:" + ",".join(unsupported)
    if policy.mode == "selected" and not policy.selected_roles:
        return "document_scope_selected_roles_missing"
    if policy.mode in {"body", "selected"} and not policy.included_roles(mode_id):
        return "document_scope_effective_roles_empty"
    return ""


__all__ = [
    "ALL_DOCUMENT_REGION_ROLES",
    "DOCUMENT_SCOPE_MODES",
    "DocumentScopeMode",
    "DocumentScopePolicy",
    "coerce_document_scope_policy",
    "document_scope_policy_issue",
    "document_scope_role_label",
    "selectable_document_scope_roles",
]
