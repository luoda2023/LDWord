"""
chem_typography ? ???????

??????
- ?? scope ??????/??????????
- ?? shared.engine.chem_marks ?? run ?????/?????
- ?? tracker ???
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.chem_marks import apply_chem_typography_to_paragraph
from src.shared.engine.paragraph_iter import iter_tables, iter_table_cells

if TYPE_CHECKING:
    from docx import Document
    from docx.text.paragraph import Paragraph
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


_SCOPE_KEYS = (
    'references',
    'body',
    'headings',
    'abstract_cn',
    'abstract_en',
    'captions',
    'tables',
)
_HEADING_STYLE_RE = re.compile(
    r'^(heading\s*\d+|heading|\u6807\u9898)',
    re.IGNORECASE,
)
_CAPTION_RE = re.compile(
    r'^(?:\u56fe|\u8868|Figure|Table|Fig\.?|Tab\.?)\s*',
    re.IGNORECASE,
)
_BODY_LIKE_SECTIONS = {'body', 'errata', 'acknowledgment', 'appendix', 'resume'}


class ChemTypographyModule(BaseModule):
    """????????"""

    meta = ModuleMeta(
        name='chem_typography',
        description='\u5316\u5b66\u5f0f\u6392\u7248',
        category='special',
        requires_config=('chem_typography',),
        soft_after=('paragraph_style', 'heading_recognition', 'caption'),
        soft_consumes=('doc_tree', 'heading_map'),
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        chem_cfg = config.chem_typography
        active_scopes = _resolve_active_scopes(chem_cfg)
        compatibility_global = not active_scopes

        para_count = 0
        font_chars = 0
        mark_chars = 0

        for para_index, para in enumerate(doc.paragraphs):
            text = para.text or ''
            if not text.strip():
                continue
            if not _should_process_paragraph(
                para_index,
                para,
                context=context,
                active_scopes=active_scopes,
                compatibility_global=compatibility_global,
            ):
                continue

            para_font_chars, para_mark_chars = _apply_chem_typography(para, chem_cfg)
            if para_font_chars or para_mark_chars:
                para_count += 1
                font_chars += para_font_chars
                mark_chars += para_mark_chars

        if 'tables' in active_scopes:
            for _, table in iter_tables(doc):
                for _, _, cell in iter_table_cells(table):
                    for para in cell.paragraphs:
                        text = para.text or ''
                        if not text.strip():
                            continue
                        para_font_chars, para_mark_chars = _apply_chem_typography(para, chem_cfg)
                        if para_font_chars or para_mark_chars:
                            para_count += 1
                            font_chars += para_font_chars
                            mark_chars += para_mark_chars

        if para_count:
            tracker.record(
                rule_name=self.meta.name,
                target=f'{para_count} \u4e2a\u6bb5\u843d',
                section='global',
                change_type='format',
                before='\u5316\u5b66\u5f0f\u683c\u5f0f\u5f02\u5e38',
                after=(
                    f'\u5df2\u6062\u590d\u4e0a\u4e0b\u6807 {mark_chars} \u4e2a\u5b57\u7b26\uff0c'
                    f'\u897f\u6587\u5b57\u4f53 {font_chars} \u4e2a\u5b57\u7b26'
                ),
            )



def _resolve_active_scopes(chem_cfg) -> set[str]:
    raw_scopes = getattr(chem_cfg, 'scopes', {}) or {}
    active = {key for key in _SCOPE_KEYS if bool(raw_scopes.get(key, False))}
    if bool(raw_scopes.get('abstract', False)):
        active.update({'abstract_cn', 'abstract_en'})
    return active



def _get_section_type(para_index: int, context: PipelineContext) -> str:
    doc_tree = getattr(context, 'doc_tree', None)
    if doc_tree is None:
        return 'body'
    getter = getattr(doc_tree, 'get_section_for_paragraph', None)
    if callable(getter):
        try:
            section = getter(para_index)
            if section:
                return str(section)
        except Exception:
            pass
    return 'body'



def _is_heading_paragraph(para_index: int, para: Paragraph, context: PipelineContext) -> bool:
    heading_map = getattr(context, 'heading_map', None) or {}
    if para_index in heading_map:
        return True

    doc_tree = getattr(context, 'doc_tree', None)
    if doc_tree is not None:
        getter = getattr(doc_tree, 'get_heading_level', None)
        if callable(getter):
            try:
                if getter(para_index) is not None:
                    return True
            except Exception:
                pass

    style = para.style
    style_name = style.name if style else ''
    return bool(_HEADING_STYLE_RE.match(style_name or ''))



def _is_caption_paragraph(para: Paragraph) -> bool:
    return bool(_CAPTION_RE.match((para.text or '').strip()))



def _should_process_paragraph(
    para_index: int,
    para: Paragraph,
    *,
    context: PipelineContext,
    active_scopes: set[str],
    compatibility_global: bool,
) -> bool:
    if compatibility_global:
        return True

    if _is_heading_paragraph(para_index, para, context):
        return 'headings' in active_scopes

    if _is_caption_paragraph(para):
        return 'captions' in active_scopes

    section_type = _get_section_type(para_index, context)
    if section_type == 'references':
        return 'references' in active_scopes
    if section_type in {'abstract_cn', 'abstract_en'}:
        return section_type in active_scopes
    if section_type in _BODY_LIKE_SECTIONS:
        return 'body' in active_scopes
    return False



def _apply_chem_typography(para: Paragraph, chem_cfg) -> tuple[int, int]:
    """?????????????"""
    return apply_chem_typography_to_paragraph(para, chem_cfg=chem_cfg)
