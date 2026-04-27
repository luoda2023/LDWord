"""Header/footer formatting with section-aware page-number strategy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.modules.base import BaseModule, Issue, ModuleMeta
from src.shared.engine.field_builder import build_complex_field, iter_field_instructions
from src.shared.engine.font_resolver import resolve_font
from src.shared.engine.ooxml_ops import find_or_create, qn
from src.shared.engine.page_number_planner import (
    NON_NUMBERED_HEADING_SECTION_TYPES,
    build_page_number_execution_plan,
    collect_page_number_diagnostics,
    format_page_number_diagnostic_text,
)
from src.shared.engine.run_ops import set_run_east_asian_font

if TYPE_CHECKING:
    from docx import Document
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


_PAGE_NUMBER_FIELD_INSTRUCTIONS = {
    "decimal": " PAGE ",
    "upperRoman": " PAGE \\* ROMAN ",
    "lowerRoman": " PAGE \\* roman ",
}

_PAGE_NUMBER_W_FORMATS = {
    "decimal": "decimal",
    "upperRoman": "upperRoman",
    "lowerRoman": "lowerRoman",
}


class HeaderFooterModule(BaseModule):
    meta = ModuleMeta(
        name="header_footer",
        description="页眉页脚",
        category="basic",
        requires_config=("header_footer",),
        soft_after=("heading_recognition", "section_format"),
        soft_consumes=("doc_tree",),
        enabled_by_default=True,
    )

    def validate(
        self,
        doc: Document,
        config: ResolvedConfig,
        context: PipelineContext,
    ) -> list[Issue]:
        return [
            Issue(
                level=item.level,
                module_name=self.meta.name,
                message=format_page_number_diagnostic_text(item),
                location=item.location,
            )
            for item in collect_page_number_diagnostics(doc, context, config.header_footer)
        ]

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        hf_cfg = config.header_footer
        count = 0

        header_mode = str(hf_cfg.header_mode or "styleref")
        header_border = bool(hf_cfg.header_border)
        page_number_enabled = bool(hf_cfg.page_number_enabled)
        section_plan = build_page_number_execution_plan(doc, context, hf_cfg)

        for section, plan in zip(doc.sections, section_plan.sections):
            section_type = plan.section_type
            is_cover = plan.hide_header_footer

            if is_cover or header_mode == "none":
                _clear_header(section)
                count += 1
            elif header_mode == "fixed":
                _set_fixed_header(section, hf_cfg)
                count += 1
            else:
                style_ref = None
                include_number = True
                if section_type in NON_NUMBERED_HEADING_SECTION_TYPES:
                    style_ref = getattr(config.heading_model, "non_numbered_heading_style_name", "") or None
                    include_number = False
                _set_styleref_header(section, hf_cfg, style_ref=style_ref, include_number=include_number)
                count += 1

            _set_header_border(section, header_border and not is_cover and header_mode != "none")

            if is_cover:
                _clear_footer(section)
                count += 1
            elif page_number_enabled and plan.page_number_visible:
                _set_page_number(section, num_format=plan.number_format)
                _set_page_number_format(section, plan.number_format, start=plan.start_value)
                count += 1
            elif _clear_page_number_fields(section):
                count += 1

            # Font unification must run after header/footer content is rebuilt.
            _format_header_footer_font(section, hf_cfg)

        if count:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{len(list(doc.sections))} 个节",
                section="global",
                change_type="format",
                before="(mixed)",
                after=(
                    f"header={header_mode}, "
                    f"border={header_border}, "
                    f"page_num={page_number_enabled}"
                ),
            )

def _set_styleref_header(section, hf_cfg, *, style_ref: str | None = None, include_number: bool = True) -> None:
    header = section.header
    header.is_linked_to_previous = False

    for para in header.paragraphs:
        for run in list(para.runs):
            run._element.getparent().remove(run._element)

    para = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
    level = int(hf_cfg.styleref_level or 1)
    style_name = str(style_ref or f"Heading {level}").strip() or f"Heading {level}"

    if include_number:
        _add_field_to_paragraph(para, f' STYLEREF "{style_name}" \\n ')
    _add_field_to_paragraph(para, f' STYLEREF "{style_name}" ')


def _set_fixed_header(section, hf_cfg) -> None:
    header = section.header
    header.is_linked_to_previous = False

    for para in header.paragraphs:
        for run in list(para.runs):
            run._element.getparent().remove(run._element)

    para = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
    text = str(hf_cfg.header_text or "")
    if text:
        para.add_run(text)


def _clear_header(section) -> None:
    header = section.header
    header.is_linked_to_previous = False

    if not header.paragraphs:
        header.add_paragraph()
    for para in header.paragraphs:
        _clear_paragraph_runs(para)


def _clear_footer(section) -> None:
    footer = section.footer
    footer.is_linked_to_previous = False

    if not footer.paragraphs:
        footer.add_paragraph()
    for para in footer.paragraphs:
        _clear_paragraph_runs(para)


def _set_header_border(section, enable: bool) -> None:
    header = section.header
    if not header.paragraphs:
        return

    para = header.paragraphs[0]
    p_pr = find_or_create(para._element, "w:pPr")
    p_bdr = find_or_create(p_pr, "w:pBdr")
    bottom = find_or_create(p_bdr, "w:bottom")

    if enable:
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "4")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), "auto")
    else:
        bottom.set(qn("w:val"), "none")
        bottom.set(qn("w:sz"), "0")


def _set_page_number(section, hf_cfg=None, *, num_format: str = "decimal") -> None:
    footer = section.footer
    footer.is_linked_to_previous = False

    for para in footer.paragraphs:
        _clear_paragraph_runs(para)

    para = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p_pr = find_or_create(para._element, "w:pPr")
    jc = find_or_create(p_pr, "w:jc")
    jc.set(qn("w:val"), "center")

    field_instruction = _PAGE_NUMBER_FIELD_INSTRUCTIONS.get(
        str(num_format or "decimal"),
        _PAGE_NUMBER_FIELD_INSTRUCTIONS["decimal"],
    )
    _add_field_to_paragraph(para, field_instruction)


def _set_page_number_format(section, fmt: str = "decimal", *, start: int | None = None) -> None:
    sect_pr = section._sectPr
    pg_num_type = sect_pr.find(qn("w:pgNumType"))
    if pg_num_type is None:
        pg_num_type = find_or_create(sect_pr, "w:pgNumType")

    normalized_fmt = _PAGE_NUMBER_W_FORMATS.get(str(fmt or "decimal"), "decimal")
    pg_num_type.set(qn("w:fmt"), normalized_fmt)
    if start is not None:
        pg_num_type.set(qn("w:start"), str(int(start)))
    else:
        pg_num_type.attrib.pop(qn("w:start"), None)


def _clear_page_number_fields(section) -> bool:
    footer = section.footer
    footer.is_linked_to_previous = False

    changed = False
    for para in footer.paragraphs:
        if not _paragraph_has_field(para, "PAGE"):
            continue
        _clear_paragraph_runs(para)
        changed = True
    return changed


def _format_header_footer_font(section, hf_cfg) -> None:
    font_cn = hf_cfg.font_cn
    font_en = hf_cfg.font_en
    size_pt = hf_cfg.size_pt
    bold = bool(getattr(hf_cfg, "bold", False))
    italic = bool(getattr(hf_cfg, "italic", False))

    if not any((font_cn, font_en, size_pt, bold, italic)):
        return

    from docx.shared import Pt

    for part in (section.header, section.footer):
        for para in part.paragraphs:
            for run in para.runs:
                if font_en:
                    run.font.name = resolve_font(font_en, lang="en")
                if font_cn:
                    set_run_east_asian_font(run, font_cn)
                if size_pt:
                    run.font.size = Pt(size_pt)
                run.font.bold = bold
                run.font.italic = italic


def _add_field_to_paragraph(para, instr: str) -> None:
    for elem in build_complex_field(instr, result_text=" "):
        para._element.append(elem)


def _clear_paragraph_runs(para) -> None:
    for child in list(para._element):
        if child.tag != qn("w:pPr"):
            para._element.remove(child)


def _paragraph_has_field(para, field_keyword: str) -> bool:
    keyword = field_keyword.strip().upper()
    for _kind, _elem, instr in iter_field_instructions(para._element):
        normalized = " ".join((instr or "").upper().split())
        if normalized.startswith(keyword):
            return True
    return False
