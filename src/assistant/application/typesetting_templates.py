# -*- coding: utf-8 -*-
"""Visual typesetting-template plugin for AI document authoring.

The AI writes long engineering documents chapter by chapter.  Before (and
while) it writes, a *typesetting template plugin* tells it — and the docx
composer — how the final document should look:

* page geometry (margins, page size)
* base fonts for body / headings
* heading numbering convention
* table visual style (three-line / full-grid / color…)
* whether the AI should emit tables for tabular points
* image placeholder convention: when a figure is needed the AI emits a
  visible marker such as ``[图：现场平面布置示意]`` instead of inventing a
  real image.  Real image synthesis is a later phase; the marker keeps the
  location and caption in the final document.

Templates are stored as JSON in the user config library, so they survive
restarts and can be edited from the UI (a visual editor dialog).  The
generation pipeline reads the *active* template and injects its instruction
into the per-chapter prompt; the composer reads it later when laying out the
final docx.
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.app_paths import config_library_data_root

_SCHEMA = "ldword-typesetting-template-v1"
_DIR_NAME = "typesetting_templates"
_ACTIVE_NAME = "active.json"
_ACTIVE_KEY = "active_template_id"
_LOCK = threading.RLock()

# Safe id rule for template file names.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")

# Default built-in engineering template, pre-seeded so a fresh install already
# behaves like the工程界 writing convention.
_DEFAULT_TEMPLATE = {
    "template_id": "engineering_standard",
    "name": "工程文档规范（默认）",
    "description": "适用于施工组织设计、专项方案、验收报告等工程文件：正文宋体/仿宋、"
    "章标题黑体加粗、编号到三级、数值用表、需要插图的位置放占位符。",
    "page": {
        "size": "A4",
        "orientation": "portrait",
        "margin_top_mm": 25.4,
        "margin_bottom_mm": 25.4,
        "margin_left_mm": 31.7,
        "margin_right_mm": 31.7,
    },
    "fonts": {
        "body_cn": "仿宋_GB2312",
        "body_en": "Times New Roman",
        "body_size_pt": 14,  # 四号
        "heading1_cn": "黑体",
        "heading1_size_pt": 16,  # 三号
        "heading2_cn": "黑体",
        "heading2_size_pt": 15,
        "heading3_cn": "仿宋_GB2312",
        "heading3_size_pt": 14,
        "heading_weight_bold": True,
    },
    "headings": {
        "chapter_prefix": "第X章",
        "number_levels": 3,
        "subsection_pattern": "{chapter}.{section}.{sub}",  # e.g. 1.1.2
    },
    "tables": {
        "style_key": "three_line",  # three_line | full_grid | color_table | none
        "color_palette": "blue",
        "prefer_table_for_data": True,
        "auto_number_caption": True,
        "caption_prefix": "表",
    },
    "figures": {
        "placeholder_prefix": "【图",
        "placeholder_suffix": "】",
        "prefer_figure_when": "现场照片、示意图、流程图、进度横道图、结构大样",
        "auto_number_caption": True,
        "caption_prefix": "图",
    },
    "knowledge": {
        "attach_reference_samples": True,
        "max_reference_chars": 4000,
        "style_guidance": (
            "用词客观专业，先写总体原则再展开措施；量化指标优先；"
            "同章内避免空话套话；工程术语与范本保持一致。"
        ),
    },
    "updated_at": "",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def typesetting_templates_dir() -> Path:
    return config_library_data_root() / _DIR_NAME


def _slug(name: str) -> str:
    import hashlib

    if _SAFE_ID.match(name):
        return name
    return "template_" + hashlib.sha256(str(name).encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True, slots=True)
class TypesettingTemplate:
    """A named, editable, persisted typesetting/authoring plugin."""

    template_id: str
    name: str
    page: dict = field(default_factory=dict)
    fonts: dict = field(default_factory=dict)
    headings: dict = field(default_factory=dict)
    tables: dict = field(default_factory=dict)
    figures: dict = field(default_factory=dict)
    knowledge: dict = field(default_factory=dict)
    description: str = ""
    updated_at: str = ""
    is_default: bool = False

    def to_dict(self) -> dict:
        return {
            "schema_version": _SCHEMA,
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "page": dict(self.page),
            "fonts": dict(self.fonts),
            "headings": dict(self.headings),
            "tables": dict(self.tables),
            "figures": dict(self.figures),
            "knowledge": dict(self.knowledge),
            "updated_at": self.updated_at,
            "is_default": self.is_default,
        }

    @classmethod
    def from_dict(cls, value: dict) -> "TypesettingTemplate":
        return cls(
            template_id=str(value.get("template_id") or ""),
            name=str(value.get("name") or "未命名模板"),
            page=dict(value.get("page") or {}),
            fonts=dict(value.get("fonts") or {}),
            headings=dict(value.get("headings") or {}),
            tables=dict(value.get("tables") or {}),
            figures=dict(value.get("figures") or {}),
            knowledge=dict(value.get("knowledge") or {}),
            description=str(value.get("description") or ""),
            updated_at=str(value.get("updated_at") or ""),
            is_default=bool(value.get("is_default", False)),
        )

    # ---- authoring directives -----------------------------------------
    def authoring_instruction(self) -> str:
        """Human-readable rules injected into the AI per-chapter prompt."""
        fonts = self.fonts
        tables = self.tables
        figures = self.figures
        page = self.page
        lines: list[str] = []
        lines.append("【本次排版模板要求】")
        lines.append(
            f"- 页面：{page.get('size', 'A4')} {page.get('orientation', 'portrait')}，"
            f"页边距 上{page.get('margin_top_mm', '')}mm 下{page.get('margin_bottom_mm', '')}mm "
            f"左{page.get('margin_left_mm', '')}mm 右{page.get('margin_right_mm', '')}mm。"
        )
        lines.append(
            f"- 字体：正文 {fonts.get('body_cn', '')}/{fonts.get('body_en', '')} "
            f"{fonts.get('body_size_pt', '')}pt；"
            f"章标题 {fonts.get('heading1_cn', '')} {fonts.get('heading1_size_pt', '')}pt 加粗。"
        )
        lines.append(
            f"- 标题层级：按「{self.headings.get('chapter_prefix', '第X章')}」与 "
            f"「{self.headings.get('subsection_pattern', 'x.y')}」逐级编号，"
            f"最多 {self.headings.get('number_levels', 3)} 级。"
        )
        if tables.get("prefer_table_for_data", True):
            lines.append(
                "- 表格：凡涉及工程量清单、参数对比、材料/机械配置、进度计划、"
                "风险清单等表格化数据，一律用 Markdown 表格输出，"
                f"表格样式按 {tables.get('style_key', 'three_line')}。"
            )
        prefer_figure = str(figures.get("prefer_figure_when", "") or "").strip()
        if prefer_figure:
            lines.append(
                f"- 插图：当需要表达「{prefer_figure}」等内容时，"
                f"在正文相应位置原样插入 {figures.get('placeholder_prefix', '【图')}"
                f"标题{figures.get('placeholder_suffix', '】')} 形式的占位符，不要省略该占位符；"
                "真实图片是否生成按系统提示词的要求执行。"
            )
        knowledge = self.knowledge
        if str(knowledge.get("style_guidance", "") or "").strip():
            lines.append(
                f"- 文风：{str(knowledge.get('style_guidance', '')).strip()}"
            )
        return "\n".join(lines)

    def table_style_key(self) -> str:
        return str(self.tables.get("style_key") or "three_line")

    def figure_placeholder_regex(self) -> "re.Pattern[str]":
        prefix = re.escape(str(self.figures.get("placeholder_prefix") or "【图"))
        suffix = re.escape(str(self.figures.get("placeholder_suffix") or "】"))
        return re.compile(rf"{prefix}[^{suffix}\n]*{suffix}")


def _resolve_heading_level_styles(styles: dict, heading) -> list:
    """Resolve heading1–6 styles with a derived fallback chain.

    模板显式定义了 heading1..6 就逐级返回；某级缺失时从通用 ``heading``
    样式派生：字号按「章→节→小节」每降一级递减 1pt（下限 12pt），
    加粗与字体继承通用标题样式。返回值为空表示连通用样式都没有。
    """
    if not isinstance(styles, dict):
        return []
    explicit = [styles.get(f"heading{i}") for i in range(1, 7)]
    if all(style is not None for style in explicit[:4]):
        return [style for style in explicit if style is not None][:6]
    if heading is None:
        return [style for style in explicit if style is not None]
    base_size = float(getattr(heading, "size_pt", 12) or 12)
    resolved: list = []
    for i in range(1, 7):
        style = styles.get(f"heading{i}")
        if style is not None:
            resolved.append(style)
            continue
        # 仅当更高级别存在或首级缺失时才派生，避免在已配置 H1-3 的模板里
        # 硬造出 AI 不需要的 H4-6 规矩。
        if i <= 4 and (i == 1 or resolved):
            from copy import copy

            derived = copy(heading)
            derived.size_pt = max(12.0, base_size - (i - 1))
            if i > 1:
                derived.bold = False
            resolved.append(derived)
        else:
            break
    return resolved


def _builtin_default() -> TypesettingTemplate:
    payload = dict(_DEFAULT_TEMPLATE)
    payload["template_id"] = "engineering_standard"
    payload["is_default"] = True
    payload["updated_at"] = _now_iso()
    return TypesettingTemplate.from_dict(payload)


class TypesettingTemplateStore:
    """Persistent named-template repository (user config library)."""

    def __init__(self, root: Path | None = None) -> None:
        self.base = Path(root) if root is not None else typesetting_templates_dir()

    def _path(self, template_id: str) -> Path:
        safe = _SAFE_ID.match(str(template_id or ""))
        if not safe:
            raise ValueError("invalid template id")
        return self.base / f"{template_id}.json"

    def list_templates(self) -> tuple[TypesettingTemplate, ...]:
        templates: list[TypesettingTemplate] = []
        if self.base.is_dir():
            for path in sorted(self.base.glob("*.json")):
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    templates.append(TypesettingTemplate.from_dict(raw))
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    continue
        if not templates:
            builtin = self.save(_builtin_default())
            templates.append(builtin)
        return tuple(templates)

    def get(self, template_id: str | None) -> TypesettingTemplate:
        target = str(template_id or "").strip()
        for template in self.list_templates():
            if template.template_id == target:
                return template
        # fall back to the default template (first user template or builtin)
        fallback = self.list_templates()
        for template in fallback:
            if template.is_default:
                return template
        return fallback[0]

    def save(self, template: TypesettingTemplate) -> TypesettingTemplate:
        with _LOCK:
            self.base.mkdir(parents=True, exist_ok=True)
            data = template.to_dict()
            data["updated_at"] = _now_iso()
            data["is_default"] = template.is_default or template.template_id == "engineering_standard"
            path = self._path(template.template_id)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
            tmp.replace(path)
            return TypesettingTemplate.from_dict(data)

    def delete(self, template_id: str) -> bool:
        if template_id == "engineering_standard":
            return False
        path = self._path(template_id)
        try:
            path.unlink()
            return True
        except OSError:
            return False

    def set_active_template_id(self, template_id: str | None) -> None:
        """Persist the template the authoring pipeline should apply next."""
        target = str(template_id or "").strip()
        if target:
            known = {t.template_id for t in self.list_templates()}
            if target not in known:
                raise ValueError(f"unknown template id: {target}")
        with _LOCK:
            self.base.mkdir(parents=True, exist_ok=True)
            path = self.base / _ACTIVE_NAME
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps({_ACTIVE_KEY: target}, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(path)

    def active_template_id(self) -> str:
        """Return the persisted active template id (fallback to default)."""
        path = self.base / _ACTIVE_NAME
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            target = str(payload.get(_ACTIVE_KEY) or "").strip()
        except (OSError, ValueError, json.JSONDecodeError):
            target = ""
        templates = self.list_templates()
        if target and any(t.template_id == target for t in templates):
            return target
        for t in templates:
            if t.is_default:
                return t.template_id
        return templates[0].template_id if templates else ""

    def set_active_default(self) -> str:
        """Reset the active template to the built-in default."""
        default = self.get("engineering_standard")
        self.set_active_template_id(default.template_id)
        return default.template_id

    def save_default(self) -> TypesettingTemplate:
        """Re-seed the builtin default (used on first run / reset)."""
        return self.save(_builtin_default())


# Convenience helpers used across the code base.
def active_typesetting_template() -> TypesettingTemplate:
    """Return the current (persisted active) visual template."""
    store = TypesettingTemplateStore()
    return store.get(store.active_template_id())


def typesetting_directives_from_library_template(
    template_id: str,
    mode_id: str | None = None,
) -> str:
    """Derive AI authoring directives from the canonical DOCX layout template.

    This is the bridge between the two template systems: the rich
    ``config_library`` template (page geometry, base fonts, multi-level heading
    numbering, three-line tables, captions, page header/footer) is the single
    source of truth for the final document.  Rather than maintaining a separate
    lightweight "authoring plugin" that can drift out of sync, we project the
    relevant fields of that template into the same【本次排版模板要求】prompt
    block the AI already receives while writing each chapter.

    Returns an empty string when the template cannot be resolved, so callers
    can fall back to the legacy lightweight plugin without breaking authoring.
    """
    target = str(template_id or "").strip()
    if not target:
        return ""
    try:
        from src.config.library import load_template_from_library

        template = load_template_from_library(target, mode_id=mode_id)
    except Exception:
        return ""

    lines: list[str] = []
    lines.append("【本次排版模板要求】")

    # Page geometry.
    page = getattr(template, "page_setup", None)
    if page is not None:
        margin = getattr(page, "margin", None)
        lines.append(
            f"- 页面：{getattr(page, 'paper_size', 'A4')} "
            f"{getattr(page, 'orientation', 'portrait')}；"
            f"页边距 上{getattr(margin, 'top_cm', '')}cm "
            f"下{getattr(margin, 'bottom_cm', '')}cm "
            f"左{getattr(margin, 'left_cm', '')}cm "
            f"右{getattr(margin, 'right_cm', '')}cm。"
        )

    # Base fonts for body and headings — 逐级展开标题字号，把模板里每一级
    # 标题的字体/字高/加粗都报给 AI（预设规矩：AI 边写就按这套样式排版）。
    styles = getattr(template, "styles", None) or {}
    body = styles.get("body")
    heading = styles.get("heading")
    if body is not None:
        lines.append(
            f"- 字体：正文 {getattr(body, 'font_cn', '')}/"
            f"{getattr(body, 'font_en', '')} {getattr(body, 'size_pt', '')}pt"
            f"{getattr(body, 'size_display', '') and '（' + getattr(body, 'size_display', '') + '）' or ''}；"
        )
    # 逐级标题样式：heading1–heading6 显式配置优先；缺失级别从通用 heading
    # 样式派生字号递减链（章→节→小节 逐级 -1pt，下限 12pt），保证任何模板
    # 都能给 AI 一套完整的各级规矩。
    level_styles = _resolve_heading_level_styles(styles, heading)
    if level_styles:
        parts: list[str] = []
        for idx, style in enumerate(level_styles, start=1):
            display = getattr(style, "size_display", "") or ""
            suffix = f"（{display}）" if display else ""
            bold = "加粗" if getattr(style, "bold", False) else ""
            parts.append(
                f"{idx}级 {getattr(style, 'font_cn', '')} "
                f"{getattr(style, 'size_pt', '')}pt{suffix}{bold}"
            )
        lines.append("  各级标题：" + "；".join(parts) + "。")
    elif heading is not None:
        lines.append(
            f"  章标题 {getattr(heading, 'font_cn', '')} "
            f"{getattr(heading, 'size_pt', '')}pt"
            f"{(' 加粗' if getattr(heading, 'bold', False) else '')}。"
        )

    # Heading numbering convention.
    heading_model = getattr(template, "heading_model", None)
    heading_numbering = getattr(template, "heading_numbering", None)
    if heading_numbering is not None:
        bindings = getattr(heading_numbering, "level_bindings", None) or {}
        max_level = int(getattr(heading_model, "max_heading_levels", 4) or 4)
        level_rules: list[str] = []
        for i in range(1, min(max_level, 6) + 1):
            binding = bindings.get(f"heading{i}")
            if binding is None or not getattr(binding, "enabled", False):
                continue
            template_text = (getattr(binding, "display_template", "") or "").strip()
            if template_text:
                level_rules.append(f"第{i}级用「{template_text}」")
        if level_rules:
            lines.append("- 标题编号：" + "，".join(level_rules) + "。")
        elif max_level:
            lines.append(f"- 标题层级：最多 {max_level} 级，逐级编号。")

    # Table visual style.
    table = getattr(template, "table", None)
    if table is not None:
        border_mode = getattr(table, "border_mode", "three_line")
        table_name = {
            "three_line": "三线表",
            "full_grid": "全网格",
            "color_table": "彩色表",
            "none": "无边框",
        }.get(border_mode, border_mode)
        lines.append(
            "- 表格：凡涉及参数对比、工程量清单、进度计划、风险清单等表格化数据，"
            f"一律用 Markdown 表格输出，排版样式为「{table_name}」。"
        )

    # Caption conventions.
    caption = getattr(template, "caption", None)
    if caption is not None:
        fig_prefix = getattr(caption, "figure_prefix", "图")
        tab_prefix = getattr(caption, "table_prefix", "表")
        lines.append(
            f"- 图注/表注：需要插图的位放置【{fig_prefix}：说明】占位符，"
            f"表格下方保留「{tab_prefix}」题注；真实图片是否生成按系统提示词的要求执行。"
        )

    # Page header/footer presence.
    header_footer = getattr(template, "header_footer", None)
    if header_footer is not None:
        hf_header = getattr(header_footer, "header", None)
        if hf_header is not None and getattr(hf_header, "enabled", False):
            lines.append("- 页眉：由模板自动生成，正文无需重复文档标题。")

    return "\n".join(lines)


__all__ = [
    "TypesettingTemplate",
    "TypesettingTemplateStore",
    "active_typesetting_template",
    "typesetting_directives_from_library_template",
    "typesetting_templates_dir",
]
