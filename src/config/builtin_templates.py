"""Built-in template registry for UI-facing template selection.

Each built-in template id resolves to a fresh ``TemplateConfig`` instance so
preview panels can inspect real parameters instead of a name-only shell.
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Callable

from src.config.loader import load_template
from src.config.template import StyleConfig, TemplateConfig


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULTS_DIR = _PROJECT_ROOT / "defaults"


def _normalize_template(cfg: TemplateConfig) -> TemplateConfig:
    """Align older assets with current UI expectations without mutating cache."""
    normalized = deepcopy(cfg)
    if "body" not in normalized.styles and "normal" in normalized.styles:
        normalized.styles["body"] = deepcopy(normalized.styles["normal"])
    return normalized


@lru_cache(maxsize=1)
def _load_thesis_asset() -> TemplateConfig:
    return load_template(_DEFAULTS_DIR / "thesis.yaml")


def _default_template() -> TemplateConfig:
    cfg = TemplateConfig(
        name="默认格式",
        description="通用默认排版模板，适合作为自定义模板的起点。",
    )
    cfg.styles["body"] = StyleConfig(
        font_cn="宋体",
        font_en="Times New Roman",
        size_pt=12,
        size_display="小四",
        alignment="justify",
        first_line_indent_chars=2,
        line_spacing_type="exact",
        line_spacing_pt=20,
    )
    return cfg


def _thesis_gbt_template() -> TemplateConfig:
    cfg = _normalize_template(_load_thesis_asset())
    cfg.name = "GB/T 7713 学位论文"
    cfg.description = "适用于学位论文与学术论文的内置模板。"
    return cfg


def _thesis_custom_template() -> TemplateConfig:
    cfg = _thesis_gbt_template()
    cfg.name = "自定义论文模板"
    cfg.description = "基于学位论文模板的可调整版本。"
    return cfg


def _bid_engineering_template() -> TemplateConfig:
    cfg = _normalize_template(_load_thesis_asset())
    cfg.name = "工程类投标文件"
    cfg.description = "适用于工程投标与商务标书的内置模板。"
    cfg.page_setup.margin.top_cm = 2.8
    cfg.page_setup.margin.bottom_cm = 2.6
    cfg.page_setup.margin.left_cm = 2.8
    cfg.page_setup.margin.right_cm = 2.6
    cfg.table.border_mode = "full_grid"
    cfg.table.layout_mode = "full"
    cfg.header_footer.header_mode = "fixed"
    cfg.header_footer.header_text = "工程类投标文件"
    return cfg


def _bid_procurement_template() -> TemplateConfig:
    cfg = _bid_engineering_template()
    cfg.name = "政府采购投标"
    cfg.description = "适用于政府采购投标文件的内置模板。"
    cfg.header_footer.header_text = "政府采购投标文件"
    cfg.table.layout_mode = "smart"
    return cfg


def _bid_custom_template() -> TemplateConfig:
    cfg = _bid_engineering_template()
    cfg.name = "自定义标书模板"
    cfg.description = "基于标书模板的可调整版本。"
    return cfg


def _official_gbt_template() -> TemplateConfig:
    cfg = _default_template()
    cfg.name = "GB/T 9704 公文格式"
    cfg.description = "适用于公文、通知和批复的内置模板。"
    cfg.page_setup.margin.top_cm = 3.7
    cfg.page_setup.margin.bottom_cm = 3.5
    cfg.page_setup.margin.left_cm = 2.8
    cfg.page_setup.margin.right_cm = 2.6
    cfg.header_footer.header_mode = "fixed"
    cfg.header_footer.header_text = ""
    cfg.header_footer.page_number_enabled = True
    cfg.heading_numbering.level_bindings = {}
    return cfg


def _official_custom_template() -> TemplateConfig:
    cfg = _official_gbt_template()
    cfg.name = "自定义公文模板"
    cfg.description = "基于公文模板的可调整版本。"
    return cfg


def _tech_standard_template() -> TemplateConfig:
    cfg = _default_template()
    cfg.name = "通用技术文档"
    cfg.description = "适用于技术方案、设计说明和操作手册的内置模板。"
    cfg.page_setup.margin.top_cm = 2.5
    cfg.page_setup.margin.bottom_cm = 2.5
    cfg.table.border_mode = "full_grid"
    cfg.header_footer.header_mode = "styleref"
    cfg.toc.enabled = True
    cfg.toc.mode = "word_native"
    return cfg


def _tech_custom_template() -> TemplateConfig:
    cfg = _tech_standard_template()
    cfg.name = "自定义技术模板"
    cfg.description = "基于技术文档模板的可调整版本。"
    return cfg


def _report_default_template() -> TemplateConfig:
    cfg = _default_template()
    cfg.name = "通用报告格式"
    cfg.description = "适用于汇报、总结和调研报告的内置模板。"
    cfg.page_setup.margin.top_cm = 2.54
    cfg.page_setup.margin.bottom_cm = 2.54
    cfg.page_setup.margin.left_cm = 3.0
    cfg.page_setup.margin.right_cm = 3.0
    cfg.table.layout_mode = "smart"
    cfg.header_footer.header_mode = "none"
    cfg.toc.enabled = True
    return cfg


def _report_custom_template() -> TemplateConfig:
    cfg = _report_default_template()
    cfg.name = "自定义报告模板"
    cfg.description = "基于报告模板的可调整版本。"
    return cfg


_BUILTIN_TEMPLATE_FACTORIES: dict[str, Callable[[], TemplateConfig]] = {
    "default": _default_template,
    "thesis_gbt": _thesis_gbt_template,
    "thesis_custom": _thesis_custom_template,
    "bid_engineering": _bid_engineering_template,
    "bid_procurement": _bid_procurement_template,
    "bid_custom": _bid_custom_template,
    "official_gbt": _official_gbt_template,
    "official_custom": _official_custom_template,
    "tech_standard": _tech_standard_template,
    "tech_custom": _tech_custom_template,
    "report_default": _report_default_template,
    "report_custom": _report_custom_template,
}


def create_builtin_template(template_id: str) -> TemplateConfig:
    """Resolve a built-in template id to a fresh ``TemplateConfig`` instance."""
    factory = _BUILTIN_TEMPLATE_FACTORIES.get(str(template_id or "").strip())
    if factory is None:
        raise ValueError(f"unknown built-in template id: {template_id}")
    return factory()


def has_builtin_template(template_id: str) -> bool:
    return str(template_id or "").strip() in _BUILTIN_TEMPLATE_FACTORIES


__all__ = ["create_builtin_template", "has_builtin_template"]
