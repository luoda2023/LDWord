"""
ModuleRegistry — 管线模块注册表

集中注册所有 V1.0 管线模块，Pipeline 从这里获取完整模块列表。
"""

from __future__ import annotations

from src.modules.base import BaseModule

# ── 基础排版 ─────────────────────────────────────
from src.modules.basic.page_setup import PageSetupModule
from src.modules.basic.section_format import SectionFormatModule
from src.modules.basic.paragraph_style import ParagraphStyleModule
from src.modules.basic.header_footer import HeaderFooterModule

# ── 结构编号 ─────────────────────────────────────
from src.modules.structure.heading_recognition import HeadingRecognitionModule
from src.modules.structure.heading_numbering import HeadingNumberingModule
from src.modules.structure.toc import TocModule

# ── 表格题注 ─────────────────────────────────────
from src.modules.table.caption import CaptionModule
from src.modules.table.table_format import TableFormatModule
from src.modules.table.figure_table_center import FigureTableCenterModule

# ── 填充替换 ─────────────────────────────────────
from src.modules.fill.entity_fill import EntityFillModule
from src.modules.fill.source_fill import SourceFillModule
from src.modules.fill.placeholder_replace import PlaceholderReplaceModule

# ── 插入 ────────────────────────────────────────
from src.modules.insert.image_insertion import ImageInsertionModule
from src.modules.insert.watermark import WatermarkModule

# ── 特殊 ────────────────────────────────────────
from src.modules.special.chem_typography import ChemTypographyModule
from src.modules.validate.md_cleanup import MdCleanupModule
from src.modules.validate.whitespace_normalize import WhitespaceNormalizeModule
from src.modules.validate.validation import ValidationModule
from src.modules.special.citation_link import CitationLinkModule
from src.modules.special.equation_table_format import EquationTableFormatModule
from src.modules.special.reference_format import ReferenceFormatModule


# ── 注册表 ───────────────────────────────────────

ALL_MODULES: list[type[BaseModule]] = [
    # 基础排版
    PageSetupModule,
    SectionFormatModule,
    ParagraphStyleModule,
    HeaderFooterModule,
    # 结构编号
    HeadingRecognitionModule,
    HeadingNumberingModule,
    TocModule,
    # 表格题注
    CaptionModule,
    TableFormatModule,
    FigureTableCenterModule,
    # 填充替换
    EntityFillModule,
    SourceFillModule,
    PlaceholderReplaceModule,
    # 插入
    ImageInsertionModule,
    WatermarkModule,
    # 特殊
    ChemTypographyModule,
    MdCleanupModule,
    WhitespaceNormalizeModule,
    ValidationModule,
    CitationLinkModule,
    EquationTableFormatModule,
    ReferenceFormatModule,
]


def create_all_modules() -> list[BaseModule]:
    """实例化所有注册模块。"""
    return [cls() for cls in ALL_MODULES]


def create_modules_by_names(names: list[str]) -> list[BaseModule]:
    """按名称筛选并实例化模块。"""
    name_map = {cls.meta.name: cls for cls in ALL_MODULES}
    return [name_map[n]() for n in names if n in name_map]


def list_module_names() -> list[str]:
    """列出所有已注册模块名称。"""
    return [cls.meta.name for cls in ALL_MODULES]
