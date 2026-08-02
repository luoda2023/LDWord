"""Fail-closed integrity guard for document regions outside the write scope."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from lxml import etree


@dataclass(frozen=True, slots=True)
class FrozenXmlNode:
    kind: str
    label: str
    node: Any
    digest: str


@dataclass(frozen=True, slots=True)
class DocumentScopeGuard:
    nodes: tuple[FrozenXmlNode, ...]
    protected_paragraph_count: int
    protected_roles: tuple[str, ...]


def capture_document_scope_guard(doc, context) -> DocumentScopeGuard:
    """Snapshot paragraphs and inherited styles outside the writable region."""

    tree = getattr(context, "doc_tree", None)
    if tree is None:
        return DocumentScopeGuard((), 0, ())

    nodes: list[FrozenXmlNode] = []
    seen_styles: set[int] = set()
    roles: list[str] = []
    protected_count = 0
    for index, paragraph in enumerate(doc.paragraphs):
        if tree.is_paragraph_writable(index):
            continue
        protected_count += 1
        role = str(tree.get_section_for_paragraph(index) or "body")
        if role not in roles:
            roles.append(role)
        nodes.append(_snapshot("paragraph", f"{role}@{index}", paragraph._p))
        _capture_style_chain(paragraph.style, nodes, seen_styles)
        for run in paragraph.runs:
            _capture_style_chain(run.style, nodes, seen_styles)
    return DocumentScopeGuard(tuple(nodes), protected_count, tuple(roles))


def validate_document_scope_guard(guard: DocumentScopeGuard) -> tuple[str, ...]:
    """Return stable violation codes for removed or mutated frozen XML nodes."""

    violations: list[str] = []
    for snapshot in guard.nodes:
        if snapshot.node.getparent() is None:
            violations.append(f"{snapshot.kind}_removed:{snapshot.label}")
        elif _xml_digest(snapshot.node) != snapshot.digest:
            violations.append(f"{snapshot.kind}_changed:{snapshot.label}")
    return tuple(violations)


def _capture_style_chain(style, nodes: list[FrozenXmlNode], seen: set[int]) -> None:
    current = style
    while current is not None:
        element = getattr(current, "_element", None)
        if element is None or id(element) in seen:
            return
        seen.add(id(element))
        label = str(getattr(current, "style_id", "") or getattr(current, "name", ""))
        nodes.append(_snapshot("style", label or "anonymous", element))
        current = getattr(current, "base_style", None)


def _snapshot(kind: str, label: str, node) -> FrozenXmlNode:
    return FrozenXmlNode(kind, label, node, _xml_digest(node))


def _xml_digest(node) -> str:
    payload = etree.tostring(node, encoding="utf-8", with_tail=False)
    return sha256(payload).hexdigest()


__all__ = [
    "DocumentScopeGuard",
    "capture_document_scope_guard",
    "validate_document_scope_guard",
]
