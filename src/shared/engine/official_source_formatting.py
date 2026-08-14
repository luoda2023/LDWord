"""Format an existing official-document DOCX without rebuilding its content.

The official workbench has two input shapes behind one product entry:

* structured material is assembled into an approved master;
* an existing DOCX is formatted in place after conservative role detection.

This module owns the second shape.  It never replaces paragraph text and never
reconstructs the document body, so drawings, tables, comments, and other source
package parts remain owned by the original DOCX.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from src.config.official_document_profiles import (
    get_official_document_assembly_contract,
    get_official_document_profile,
)
from src.shared.engine.font_resolver import resolve_font
from src.shared.engine.run_ops import set_run_fonts

_DOCUMENT_NUMBER_RE = re.compile(
    r"(?:〔|\[|【)\s*[12]\d{3}\s*(?:〕|\]|】)\s*\d+\s*号|第\s*\d+\s*号"
)
_DATE_RE = re.compile(
    r"(?:[二〇零○一二三四五六七八九十\d]{4}\s*年\s*"
    r"[一二三四五六七八九十\d]{1,3}\s*月\s*"
    r"[一二三四五六七八九十\d]{1,3}\s*日|"
    r"20\d{2}[-./年]\d{1,2}[-./月]\d{1,2}日?)"
)
_BODY_LEVEL_PATTERNS = (
    (1, re.compile(r"^[一二三四五六七八九十百]+、")),
    (2, re.compile(r"^（[一二三四五六七八九十百]+）")),
    (3, re.compile(r"^\d+[.．]")),
    (4, re.compile(r"^（\d+）")),
)
_ISSUER_HINT_RE = re.compile(
    r"(?:人民政府|委员会|办公厅|办公室|人民法院|人民检察院|"
    r"党委|市委|区委|县委|党组|协会|学校|大学|"
    r"厅|局|部|署|院|会|中心|集团|公司)$"
)
_COPY_SCOPE_RE = re.compile(r"^抄送[：:]")
_ATTACHMENT_RE = re.compile(r"^附件(?:\s*\d+)?[：:]?")
_TYPE_LABELS = {
    "resolution": "决议",
    "decision": "决定",
    "order": "命令",
    "bulletin": "公报",
    "announcement": "公告",
    "notice_public": "通告",
    "opinion": "意见",
    "notice": "通知",
    "circular": "通报",
    "report": "报告",
    "request": "请示",
    "approval": "批复",
    "proposal": "议案",
    "letter": "函",
    "minutes": "纪要",
}
_LAYOUT_FAMILY_BY_MASTER_ID = {
    "official_gbt_standard": "common",
    "official_gbt_upward": "upward",
    "official_gbt_letter": "letter",
    "official_gbt_minutes": "minutes",
    "official_gbt_order": "order",
}


@dataclass(frozen=True, slots=True)
class OfficialSourceRole:
    paragraph_index: int
    role: str
    confidence: str
    text_preview: str
    level: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class OfficialSourceFormattingResult:
    status: str
    strategy: str
    document_type_id: str
    master_id: str
    layout_family: str
    roles: tuple[OfficialSourceRole, ...]
    formatted_paragraph_count: int
    preserved_table_count: int
    preserved_inline_shape_count: int
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["roles"] = [role.to_dict() for role in self.roles]
        return payload


def format_existing_official_document(
    document,
    *,
    document_type_id: str = "",
) -> OfficialSourceFormattingResult:
    """Apply GB/T-style formatting to an existing DOCX without changing text."""

    profile_id = str(document_type_id or "").strip()
    master_id, layout_family = _source_master_contract(profile_id)
    roles, warnings = detect_official_source_roles(
        document,
        document_type_id=profile_id,
    )
    _configure_page_layout(document, layout_family=layout_family)
    _configure_base_styles(document)
    _configure_family_footer(document, layout_family=layout_family)

    formatted = 0
    roles_by_index = {role.paragraph_index: role for role in roles}
    for index, paragraph in enumerate(document.paragraphs):
        role = roles_by_index.get(index)
        if role is None:
            continue
        _format_role_paragraph(paragraph, role, layout_family=layout_family)
        formatted += 1

    return OfficialSourceFormattingResult(
        status="warning" if warnings else "ok",
        strategy="builtin_master_overlay",
        document_type_id=profile_id,
        master_id=master_id,
        layout_family=layout_family,
        roles=roles,
        formatted_paragraph_count=formatted,
        preserved_table_count=len(document.tables),
        preserved_inline_shape_count=len(document.inline_shapes),
        warnings=warnings,
    )


def detect_official_source_roles(
    document,
    *,
    document_type_id: str = "",
) -> tuple[tuple[OfficialSourceRole, ...], tuple[str, ...]]:
    """Conservatively map top-level paragraphs to common official roles."""

    paragraphs = list(document.paragraphs)
    nonempty = [
        index for index, paragraph in enumerate(paragraphs)
        if _text(paragraph)
    ]
    if not nonempty:
        return (), ("official_source_empty",)

    document_no_index = next(
        (index for index in nonempty if _DOCUMENT_NUMBER_RE.search(_text(paragraphs[index]))),
        None,
    )
    issue_date_index = next(
        (
            index
            for index in reversed(nonempty)
            if _DATE_RE.search(_text(paragraphs[index]))
        ),
        None,
    )
    organization_index = _organization_index(
        paragraphs,
        nonempty,
        document_no_index=document_no_index,
    )
    title_index, title_confidence = _title_index(
        paragraphs,
        nonempty,
        document_type_id=document_type_id,
        document_no_index=document_no_index,
        issue_date_index=issue_date_index,
    )
    recipient_index = _recipient_index(
        paragraphs,
        nonempty,
        title_index=title_index,
        document_no_index=document_no_index,
        issue_date_index=issue_date_index,
    )
    attachment_indices = tuple(
        index for index in nonempty if _ATTACHMENT_RE.match(_text(paragraphs[index]))
    )
    copy_scope_indices = tuple(
        index for index in nonempty if _COPY_SCOPE_RE.match(_text(paragraphs[index]))
    )
    issuer_index = _issuer_index(
        paragraphs,
        nonempty,
        issue_date_index=issue_date_index,
        title_index=title_index,
    )

    assigned: dict[int, OfficialSourceRole] = {}

    def assign(
        index: int | None,
        role: str,
        confidence: str = "high",
        *,
        level: int = 0,
    ) -> None:
        if index is None or index in assigned:
            return
        assigned[index] = OfficialSourceRole(
            paragraph_index=index,
            role=role,
            confidence=confidence,
            text_preview=_text(paragraphs[index])[:80],
            level=level,
        )

    assign(organization_index, "organization")
    assign(document_no_index, "document_no")
    assign(title_index, "title", title_confidence)
    assign(recipient_index, "recipient")
    assign(issuer_index, "issuer", "medium")
    assign(issue_date_index, "issue_date")
    for index in attachment_indices:
        assign(index, "attachment_note")
    for index in copy_scope_indices:
        assign(index, "copy_scope")

    body_start = (
        (recipient_index + 1)
        if recipient_index is not None
        else ((title_index + 1) if title_index is not None else nonempty[0])
    )
    body_boundaries = [
        index
        for index in (
            *attachment_indices,
            issuer_index,
            issue_date_index,
            *copy_scope_indices,
        )
        if index is not None and index >= body_start
    ]
    body_end = min(body_boundaries, default=len(paragraphs))
    for index in nonempty:
        if index < body_start or index >= body_end or index in assigned:
            continue
        level = _body_level(paragraphs[index])
        assign(
            index,
            "body_heading" if level else "body",
            "high" if level else "medium",
            level=level,
        )

    warnings: list[str] = []
    if title_index is None:
        warnings.append("official_source_title_not_detected")
    elif title_confidence != "high":
        warnings.append("official_source_title_needs_review")
    if not any(role.role in {"body", "body_heading"} for role in assigned.values()):
        warnings.append("official_source_body_not_detected")
    if document_no_index is None:
        warnings.append("official_source_document_no_not_detected")
    if issue_date_index is None:
        warnings.append("official_source_issue_date_not_detected")

    return (
        tuple(assigned[index] for index in sorted(assigned)),
        tuple(dict.fromkeys(warnings)),
    )


def _organization_index(paragraphs, nonempty, *, document_no_index):
    upper_bound = (
        document_no_index
        if document_no_index is not None
        else nonempty[min(1, len(nonempty) - 1)] + 1
    )
    candidates = [
        index
        for index in nonempty
        if index < upper_bound
        and len(_text(paragraphs[index])) <= 40
        and (
            "文件" in _text(paragraphs[index])
            or _ISSUER_HINT_RE.search(_text(paragraphs[index]))
        )
    ]
    return candidates[0] if candidates else None


def _title_index(
    paragraphs,
    nonempty,
    *,
    document_type_id,
    document_no_index,
    issue_date_index,
):
    profile = get_official_document_profile(str(document_type_id or "").strip())
    type_label = str(getattr(profile, "label", "") or "").replace("（令）", "")
    if not type_label:
        type_label = _TYPE_LABELS.get(str(document_type_id or "").strip(), "")
    lower_bound = document_no_index + 1 if document_no_index is not None else nonempty[0]
    upper_bound = issue_date_index if issue_date_index is not None else len(paragraphs)
    scored: list[tuple[int, int]] = []
    for index in nonempty:
        if index < lower_bound or index >= upper_bound:
            continue
        paragraph = paragraphs[index]
        text = _text(paragraph)
        if not (4 <= len(text) <= 100):
            continue
        score = 0
        if type_label and type_label in text:
            score += 8
        if any(label in text for label in _TYPE_LABELS.values()):
            score += 3
        if paragraph.alignment == WD_ALIGN_PARAGRAPH.CENTER:
            score += 3
        style_name = str(getattr(getattr(paragraph, "style", None), "name", "") or "")
        if style_name.casefold() == "title" or "标题" in style_name:
            score += 2
        if document_no_index is not None and index <= document_no_index + 3:
            score += 2
        if _max_run_size(paragraph) >= 18:
            score += 2
        if _body_level(paragraph):
            score -= 6
        if text.endswith(("：", ":", "。", "；", ";")):
            score -= 4
        if "文件" in text or _DOCUMENT_NUMBER_RE.search(text) or _DATE_RE.search(text):
            score -= 8
        scored.append((score, index))
    if not scored:
        return None, "low"
    score, index = max(scored, key=lambda item: (item[0], -item[1]))
    if score < 3:
        return None, "low"
    return index, "high" if score >= 8 else "medium"


def _recipient_index(
    paragraphs,
    nonempty,
    *,
    title_index,
    document_no_index,
    issue_date_index,
):
    lower_bound = (
        title_index
        if title_index is not None
        else (document_no_index if document_no_index is not None else -1)
    )
    upper_bound = issue_date_index if issue_date_index is not None else len(paragraphs)
    for index in nonempty:
        if index <= lower_bound or index >= upper_bound:
            continue
        text = _text(paragraphs[index])
        if len(text) <= 100 and text.endswith(("：", ":")):
            return index
        if _body_level(paragraphs[index]) or "。" in text:
            break
    return None


def _issuer_index(paragraphs, nonempty, *, issue_date_index, title_index):
    upper_bound = issue_date_index if issue_date_index is not None else len(paragraphs)
    candidates = [index for index in nonempty if index < upper_bound]
    for index in reversed(candidates):
        if title_index is not None and index <= title_index:
            break
        text = _text(paragraphs[index])
        if (
            2 <= len(text) <= 40
            and not _ATTACHMENT_RE.match(text)
            and not _COPY_SCOPE_RE.match(text)
            and not text.endswith(("。", "；", ";", "：", ":"))
            and _ISSUER_HINT_RE.search(text)
        ):
            return index
    return None


def _body_level(paragraph) -> int:
    text = _text(paragraph)
    for level, pattern in _BODY_LEVEL_PATTERNS:
        if pattern.match(text):
            return level
    style_name = str(getattr(getattr(paragraph, "style", None), "name", "") or "")
    match = re.search(r"(?:Heading|标题)\s*(\d+)", style_name, re.IGNORECASE)
    if match:
        return min(4, max(1, int(match.group(1))))
    return 0


def _source_master_contract(document_type_id: str) -> tuple[str, str]:
    contract = get_official_document_assembly_contract(document_type_id)
    master_id = str(getattr(contract, "master_id", "") or "official_gbt_standard")
    layout_family = _LAYOUT_FAMILY_BY_MASTER_ID.get(master_id, "common")
    return master_id, layout_family


def _configure_page_layout(document, *, layout_family: str) -> None:
    for section in document.sections:
        section.orientation = WD_ORIENT.PORTRAIT
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2.35 if layout_family == "letter" else 3.7)
        section.bottom_margin = Cm(3.5)
        section.left_margin = Cm(2.8)
        section.right_margin = Cm(2.6)
        section.header_distance = Cm(1.5)
        section.footer_distance = Cm(2.0 if layout_family == "letter" else 2.35)
        if layout_family == "letter":
            section.different_first_page_header_footer = True


def _configure_family_footer(document, *, layout_family: str) -> None:
    if layout_family != "letter":
        return
    document.settings.odd_and_even_pages_header_footer = True
    for section in document.sections:
        section.first_page_footer.paragraphs[0].text = ""
        footers = (
            section.first_page_footer,
            section.footer,
            section.even_page_footer,
        )
        for footer in footers:
            paragraph = footer.paragraphs[0]
            paragraph.paragraph_format.left_indent = Cm(-0.7)
            paragraph.paragraph_format.right_indent = Cm(-0.7)
            _set_bottom_border(
                paragraph,
                color="C00000",
                style="thinThickSmallGap",
                size="18",
                space="2",
            )


def _configure_base_styles(document) -> None:
    roles = (
        ("Normal", "仿宋"),
        ("Heading 1", "黑体"),
        ("Heading 2", "楷体"),
        ("Heading 3", "仿宋"),
        ("Heading 4", "仿宋"),
    )
    for style_name, font_role in roles:
        try:
            style = document.styles[style_name]
        except KeyError:
            continue
        resolved = resolve_font(font_role, lang="cn")
        style.font.name = resolved
        style.font.size = Pt(16)
        style.font.bold = False
        style.paragraph_format.space_before = Pt(0)
        style.paragraph_format.space_after = Pt(0)
        style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        style.paragraph_format.line_spacing = Pt(28)


def _format_role_paragraph(
    paragraph,
    role: OfficialSourceRole,
    *,
    layout_family: str,
) -> None:
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.keep_with_next = False
    paragraph.paragraph_format.keep_together = False
    paragraph.paragraph_format.page_break_before = False

    if role.role == "organization":
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.first_line_indent = Cm(0)
        is_letter = layout_family == "letter"
        paragraph.paragraph_format.left_indent = Cm(-0.7 if is_letter else 0)
        paragraph.paragraph_format.right_indent = Cm(-0.7 if is_letter else 0)
        paragraph.paragraph_format.space_after = Pt(0 if is_letter else 6)
        paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.AT_LEAST
        mark_size = 36 if is_letter else 50
        paragraph.paragraph_format.line_spacing = Pt(mark_size * 1.2)
        _format_runs(
            paragraph,
            font_role="小标宋",
            size_pt=mark_size,
            color="C00000",
        )
        if is_letter:
            _set_bottom_border(
                paragraph,
                color="C00000",
                style="thickThinSmallGap",
                size="18",
                space="0",
            )
        return
    if role.role == "title":
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.first_line_indent = Cm(0)
        paragraph.paragraph_format.space_before = Pt(
            28 if layout_family == "letter" else 56
        )
        paragraph.paragraph_format.space_after = Pt(18)
        paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        paragraph.paragraph_format.line_spacing = Pt(32)
        _format_runs(paragraph, font_role="小标宋", size_pt=22)
        return
    if role.role == "document_no":
        paragraph.alignment = (
            WD_ALIGN_PARAGRAPH.RIGHT
            if layout_family == "letter"
            else WD_ALIGN_PARAGRAPH.CENTER
        )
        paragraph.paragraph_format.first_line_indent = Cm(0)
        if layout_family != "letter":
            paragraph.paragraph_format.space_before = Pt(12)
            paragraph.paragraph_format.space_after = Pt(2)
        _body_grid(paragraph)
        _format_runs(paragraph, font_role="仿宋", size_pt=16)
        return
    if role.role == "recipient":
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.first_line_indent = Cm(0)
        _body_grid(paragraph)
        _format_runs(paragraph, font_role="仿宋", size_pt=16)
        return
    if role.role in {"issuer", "issue_date"}:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        paragraph.paragraph_format.first_line_indent = Cm(0)
        paragraph.paragraph_format.right_indent = Cm(1.1)
        _body_grid(paragraph)
        _format_runs(paragraph, font_role="仿宋", size_pt=16)
        return
    if role.role == "copy_scope":
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.first_line_indent = Cm(0)
        _body_grid(paragraph)
        _format_runs(paragraph, font_role="仿宋", size_pt=14)
        return

    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    paragraph.paragraph_format.first_line_indent = Cm(1.1)
    _body_grid(paragraph)
    font_role = {
        1: "黑体",
        2: "楷体",
        3: "仿宋",
        4: "仿宋",
    }.get(role.level, "仿宋")
    _format_runs(paragraph, font_role=font_role, size_pt=16)


def _body_grid(paragraph) -> None:
    paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    paragraph.paragraph_format.line_spacing = Pt(28)


def _set_bottom_border(
    paragraph,
    *,
    color: str,
    style: str,
    size: str,
    space: str,
) -> None:
    paragraph_properties = paragraph._p.get_or_add_pPr()
    borders = paragraph_properties.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        paragraph_properties.append(borders)
    existing = borders.find(qn("w:bottom"))
    if existing is not None:
        borders.remove(existing)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), style)
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), space)
    bottom.set(qn("w:color"), color)
    borders.append(bottom)


def _format_runs(paragraph, *, font_role: str, size_pt: float, color: str = "000000") -> None:
    for run in paragraph.runs:
        set_run_fonts(
            run,
            font_cn=font_role,
            font_en=font_role,
            size_pt=size_pt,
            bold=False,
        )
        run.font.color.rgb = RGBColor.from_string(color)


def _text(paragraph) -> str:
    return str(getattr(paragraph, "text", "") or "").strip()


def _max_run_size(paragraph) -> float:
    sizes = [
        float(run.font.size.pt)
        for run in paragraph.runs
        if run.font.size is not None
    ]
    return max(sizes, default=0.0)


__all__ = [
    "OfficialSourceFormattingResult",
    "OfficialSourceRole",
    "detect_official_source_roles",
    "format_existing_official_document",
]
