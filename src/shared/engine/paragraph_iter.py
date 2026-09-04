"""
paragraph_iter — scope-aware 段落遍历器

提供按范围/节/类型过滤的段落遍历，所有排版模块共用。
"""

from __future__ import annotations

from typing import Iterator, TYPE_CHECKING

from docx.table import _Cell

if TYPE_CHECKING:
    from docx import Document
    from docx.text.paragraph import Paragraph


def iter_paragraphs(
    doc: Document,
    *,
    start_index: int = 0,
    end_index: int | None = None,
    include_headers: bool = False,
    include_footers: bool = False,
) -> Iterator[tuple[int, Paragraph]]:
    """遍历文档段落，返回 (索引, 段落) 对。

    Args:
        doc: python-docx Document 对象
        start_index: 起始段落索引（含）
        end_index: 结束段落索引（含），None 表示到末尾
        include_headers: 是否包含页眉段落
        include_footers: 是否包含页脚段落

    Yields:
        (段落索引, Paragraph)
    """
    for i, para in enumerate(doc.paragraphs):
        if i < start_index:
            continue
        if end_index is not None and i > end_index:
            break
        yield i, para

    if include_headers or include_footers:
        for section in doc.sections:
            if include_headers:
                header = section.header
                if header and not header.is_linked_to_previous:
                    for para in header.paragraphs:
                        yield -1, para
            if include_footers:
                footer = section.footer
                if footer and not footer.is_linked_to_previous:
                    for para in footer.paragraphs:
                        yield -1, para


def iter_by_indices(
    doc: Document,
    indices: set[int],
) -> Iterator[tuple[int, Paragraph]]:
    """仅遍历指定索引的段落。"""
    for i, para in enumerate(doc.paragraphs):
        if i in indices:
            yield i, para


def iter_by_style(
    doc: Document,
    style_names: set[str],
    *,
    start_index: int = 0,
    end_index: int | None = None,
) -> Iterator[tuple[int, Paragraph]]:
    """遍历指定样式名称的段落。"""
    for i, para in iter_paragraphs(doc, start_index=start_index, end_index=end_index):
        style = para.style
        if style and style.name in style_names:
            yield i, para


def iter_tables(doc: Document):
    """遍历文档中所有表格，返回 (索引, Table)。"""
    for i, table in enumerate(doc.tables):
        yield i, table


def iter_table_cells(table):
    """遍历表格所有单元格（去重合并单元格），返回 (row, col, Cell)。"""
    for row_idx, row in enumerate(table._element.tr_lst):
        for col_idx, tc in enumerate(row.tc_lst):
            yield row_idx, col_idx, _Cell(tc, table)


def count_paragraphs(doc: Document) -> int:
    """文档总段落数。"""
    return len(doc.paragraphs)
