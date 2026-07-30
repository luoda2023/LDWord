"""Strict renderer for ``@attach`` inventory references in a target DOCX."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Iterable

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from src.config.attachment_materials import AttachmentBinding, AttachmentRenderMode
from src.shared.engine.docx_material_tokens import (
    is_strict_material_token_paragraph,
)


@dataclass(frozen=True, slots=True)
class AttachmentRenderDiagnostic:
    code: str
    message: str
    role: str
    anchor_token: str


class AttachmentRenderBlockedError(ValueError):
    def __init__(self, diagnostics: Iterable[AttachmentRenderDiagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        if not self.diagnostics:
            raise ValueError("AttachmentRenderBlockedError requires diagnostics")
        super().__init__("; ".join(item.code for item in self.diagnostics))


@dataclass(frozen=True, slots=True)
class AttachmentRenderPreflight:
    role: str
    anchor_token: str
    occurrence_count: int
    diagnostics: tuple[AttachmentRenderDiagnostic, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.diagnostics


@dataclass(frozen=True, slots=True)
class AttachmentRenderReceipt:
    role: str
    anchor_token: str
    render_mode: AttachmentRenderMode
    occurrence_count: int
    rendered_item_count: int
    rendered_lines: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "anchor_token": self.anchor_token,
            "render_mode": self.render_mode.value,
            "occurrence_count": self.occurrence_count,
            "rendered_item_count": self.rendered_item_count,
            "rendered_lines": list(self.rendered_lines),
        }


class AttachmentReferenceDocxRenderer:
    """Replace optional isolated anchors with deterministic inventory lines."""

    def preflight(self, document, binding: AttachmentBinding) -> AttachmentRenderPreflight:
        candidates, diagnostics = _find_anchors(document, binding)
        if len(candidates) > 1:
            diagnostics.append(
                _diagnostic(
                    binding,
                    "duplicate_attachment_anchor",
                    "attachment inventory anchor must occur at most once",
                )
            )
        if candidates and not binding.items:
            diagnostics.append(
                _diagnostic(
                    binding,
                    "attachment_inventory_empty",
                    "an attachment anchor cannot render an empty binding",
                )
            )
        return AttachmentRenderPreflight(
            role=binding.role,
            anchor_token=binding.anchor_token,
            occurrence_count=len(candidates),
            diagnostics=tuple(diagnostics),
        )

    def render(self, document, binding: AttachmentBinding) -> AttachmentRenderReceipt:
        candidates, diagnostics = _find_anchors(document, binding)
        if len(candidates) > 1:
            diagnostics.append(
                _diagnostic(
                    binding,
                    "duplicate_attachment_anchor",
                    "attachment inventory anchor must occur at most once",
                )
            )
        if candidates and not binding.items:
            diagnostics.append(
                _diagnostic(
                    binding,
                    "attachment_inventory_empty",
                    "an attachment anchor cannot render an empty binding",
                )
            )
        if diagnostics:
            raise AttachmentRenderBlockedError(diagnostics)
        if not candidates:
            return AttachmentRenderReceipt(
                role=binding.role,
                anchor_token=binding.anchor_token,
                render_mode=binding.render_mode,
                occurrence_count=0,
                rendered_item_count=0,
                rendered_lines=(),
            )

        lines = tuple(
            _inventory_line(item, index, len(binding.items))
            for index, item in enumerate(binding.items, start=1)
        )
        anchor = candidates[0]
        for line in lines:
            anchor.addprevious(_paragraph_from_anchor(anchor, line))
        anchor.getparent().remove(anchor)
        return AttachmentRenderReceipt(
            role=binding.role,
            anchor_token=binding.anchor_token,
            render_mode=binding.render_mode,
            occurrence_count=1,
            rendered_item_count=len(lines),
            rendered_lines=lines,
        )


def render_attachment_references(
    document,
    bindings: Iterable[AttachmentBinding],
) -> tuple[AttachmentRenderReceipt, ...]:
    renderer = AttachmentReferenceDocxRenderer()
    bindings = tuple(bindings)
    diagnostics = tuple(
        finding
        for binding in bindings
        for finding in renderer.preflight(document, binding).diagnostics
    )
    if diagnostics:
        raise AttachmentRenderBlockedError(diagnostics)
    return tuple(renderer.render(document, binding) for binding in bindings)


def _find_anchors(document, binding: AttachmentBinding):
    body = document.element.body
    candidates: list[object] = []
    diagnostics: list[AttachmentRenderDiagnostic] = []
    for paragraph in body.iter(qn("w:p")):
        text = _paragraph_text(paragraph)
        if binding.anchor_token not in text:
            continue
        if (
            paragraph.getparent() is not body
            or not is_strict_material_token_paragraph(
                paragraph,
                binding.anchor_token,
            )
        ):
            diagnostics.append(
                _diagnostic(
                    binding,
                    "attachment_anchor_not_isolated_body",
                    "attachment anchor must be isolated in plain runs in a "
                    "direct body paragraph",
                )
            )
            continue
        paragraph_properties = paragraph.find(qn("w:pPr"))
        if (
            paragraph_properties is not None
            and paragraph_properties.find(qn("w:sectPr")) is not None
        ):
            diagnostics.append(
                _diagnostic(
                    binding,
                    "attachment_anchor_section_boundary",
                    "attachment anchor paragraph must not carry a section boundary",
                )
            )
            continue
        candidates.append(paragraph)

    for root, story_name in _existing_header_footer_roots(document):
        for paragraph in root.iter(qn("w:p")):
            if binding.anchor_token in _paragraph_text(paragraph):
                diagnostics.append(
                    _diagnostic(
                        binding,
                        "attachment_anchor_forbidden_surface",
                        f"attachment anchor cannot occur in {story_name}",
                    )
                )
    return candidates, diagnostics


def _paragraph_text(paragraph) -> str:
    return "".join(node.text or "" for node in paragraph.iter(qn("w:t")))


def _existing_header_footer_roots(document):
    seen: set[int] = set()
    for part in document.part.package.parts:
        root = getattr(part, "_element", None)
        if root is None or id(root) in seen:
            continue
        seen.add(id(root))
        if root.tag == qn("w:hdr"):
            yield root, "header"
        elif root.tag == qn("w:ftr"):
            yield root, "footer"


def _paragraph_from_anchor(anchor, text: str):
    paragraph = OxmlElement("w:p")
    paragraph_properties = anchor.find(qn("w:pPr"))
    if paragraph_properties is not None:
        paragraph.append(deepcopy(paragraph_properties))
    run = OxmlElement("w:r")
    text_node = OxmlElement("w:t")
    if text.startswith(" ") or text.endswith(" "):
        text_node.set(qn("xml:space"), "preserve")
    text_node.text = text
    run.append(text_node)
    paragraph.append(run)
    return paragraph


def _inventory_line(item, index: int, total: int) -> str:
    filename = str(item.file_ref.original_name or "").strip()
    label = str(item.label or "").strip()
    display = (
        f"{label}（{filename}）"
        if label and filename and label.casefold() != filename.casefold()
        else label or filename
    )
    prefix = "附件" if total == 1 else f"附件{index}"
    return f"{prefix}：{display}"


def _diagnostic(binding: AttachmentBinding, code: str, message: str):
    return AttachmentRenderDiagnostic(
        code=code,
        message=message,
        role=binding.role,
        anchor_token=binding.anchor_token,
    )


__all__ = [
    "AttachmentReferenceDocxRenderer",
    "AttachmentRenderBlockedError",
    "AttachmentRenderDiagnostic",
    "AttachmentRenderPreflight",
    "AttachmentRenderReceipt",
    "render_attachment_references",
]
