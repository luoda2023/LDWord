# -*- coding: utf-8 -*-
"""Post-generation typesetting reconcile ("排版复核校准").

The AI writes each chapter *as if* it is already typeset: the per-chapter
prompt carries the template's heading numbering, table style and figure-caption
conventions (``typesetting_templates.typesetting_directives_from_library_template``).
This module is the second pass: once the full draft is assembled and before it
is compiled to DOCX, we measure how far the generated Markdown drifted from the
canonical template and, where the fix is mechanical and safe, apply it.

The reconcile is deliberately *non-blocking*: unlike the strict structural
validators it never rejects a draft.  It produces a report the UI can show and,
optionally, a corrected Markdown the caller may substitute before composing.

Checks (each mapped to a template field, so rules never drift from the
template the user picked):

1. ``heading_depth``      — heading levels beyond the template cap.
2. ``heading_numbering``  — chapter/section numbers re-rendered from the
   template's own ``level_bindings`` (第X章 / 1.1 / （一）…).  Mechanically
   fixable: the canonical number is deterministic from heading order.
3. ``table_structure``    — markdown tables must keep a header row, a
   ``| --- |`` separator and equal cell counts per row.
4. ``caption_prefix``     — table/figure caption prefixes must match the
   template's ``caption.table_prefix`` / ``figure_prefix``.
5. ``figure_placeholder`` — remote image references are rejected in favour of
   the template's 【图：说明】 placeholder convention.
6. ``page_number_plan``   — informational: page numbers are owned by the DOCX
   composer from ``header_footer.page_number_plan``; the check reports the
   plan so the user knows what will be applied (nothing to fix in Markdown).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TypesettingDeviation:
    """A single measured gap between the draft and the template."""

    code: str
    message: str
    severity: str = "info"  # info | warn | fix
    auto_fixed: bool = False


@dataclass(frozen=True, slots=True)
class TypesettingReconcileReport:
    """Result of a reconcile pass over a generated Markdown draft."""

    template_id: str = ""
    checked: tuple[str, ...] = ()
    deviations: tuple[TypesettingDeviation, ...] = field(default_factory=tuple)
    corrected_markdown: str = ""
    changed: bool = False

    @property
    def fix_count(self) -> int:
        return sum(1 for item in self.deviations if item.auto_fixed)

    @property
    def warn_count(self) -> int:
        return sum(1 for item in self.deviations if item.severity == "warn")

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "checked": list(self.checked),
            "deviations": [
                {
                    "code": item.code,
                    "message": item.message,
                    "severity": item.severity,
                    "auto_fixed": item.auto_fixed,
                }
                for item in self.deviations
            ],
            "changed": self.changed,
            "fix_count": self.fix_count,
            "warn_count": self.warn_count,
        }


# ── Markdown-level checks ──────────────────────────────────────────────────

_ATX_HEADING_RE = re.compile(r"^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*#*\s*$")
_FIGURE_PLACEHOLDER_RE = re.compile(r"【图[:：]\s*[^】\n]*】")
_REMOTE_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(\s*https?://[^)]+\)")

# Existing chapter number like 第一章/第 1 章/第1章 at the start of a title.
_CN_NUM = "(?:[一二三四五六七八九十百]+|\\d+)"
_CHAPTER_NUM_RE = re.compile(rf"^第\s*{_CN_NUM}\s*(?:章|篇|部分)\s*")
_H2_NUM_RE = re.compile(r"^\d+(?:\.\d+)*\s*")
_H3_CN_PAREN_RE = re.compile(r"^[（(][一二三四五六七八九十百\d]+[)）]\s*")


def _cn_number(value: int) -> str:
    from src.shared.engine.numbering import format_number

    return format_number(int(value), "cn_lower")


def _strip_leading_number(title: str) -> str:
    """Remove any leading chapter/section/paren number from a title."""
    text = str(title or "").strip()
    for pattern in (_CHAPTER_NUM_RE, _H2_NUM_RE, _H3_CN_PAREN_RE):
        text = pattern.sub("", text, count=1).strip()
    return text


def _load_template(template_id: str, mode_id: str | None):
    """Return the canonical TemplateConfig, or ``None`` when unresolved."""
    target = str(template_id or "").strip()
    if not target:
        return None
    try:
        from src.config.library import load_template_from_library

        return load_template_from_library(target, mode_id=mode_id)
    except Exception:
        return None


def _expected_h1(chapter_index: int, binding) -> str:
    """Render the canonical chapter number (第X章 …) from the binding."""
    from src.shared.engine.heading_numbering_format import (
        format_heading_level_number,
    )

    counters = [0] * 9
    counters[1] = chapter_index
    text = format_heading_level_number(1, counters, binding, None)
    return text.rstrip("\u3000 \t")


def _expected_h2(chapter: int, section: int, bindings) -> str:
    from src.shared.engine.heading_numbering_format import (
        format_heading_level_number,
    )

    counters = [0] * 9
    counters[1] = chapter
    counters[2] = section
    binding = bindings.get("heading2")
    if binding is None:
        return f"{chapter}.{section}"
    text = format_heading_level_number(2, counters, binding, bindings)
    return text.rstrip("\u3000 \t")


def _expected_h3(chapter: int, section: int, sub: int, bindings) -> str:
    from src.shared.engine.heading_numbering_format import (
        format_heading_level_number,
    )

    counters = [0] * 9
    counters[1] = chapter
    counters[2] = section
    counters[3] = sub
    binding = bindings.get("heading3")
    if binding is None:
        return f"（{_cn_number(sub)}）"
    text = format_heading_level_number(3, counters, binding, bindings)
    return text.rstrip("\u3000 \t")


_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}.*\|\s*$")


def _reconcile_table_structure(
    text: str,
    deviations: list[TypesettingDeviation],
) -> str:
    """Ensure each markdown table has a separator row and rectangular rows.

    Fixable mechanically: a table whose separator row is missing gets one
    inserted after its header; ragged rows are padded/truncated to the header
    cell count (empty cells added, never content dropped beyond the header
    width).  Returns the corrected text.
    """
    lines = text.splitlines()
    out: list[str] = []
    fixed_any = False
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if _TABLE_ROW_RE.match(line):
            # Collect the consecutive table block.
            block: list[str] = [line]
            j = i + 1
            while j < n and _TABLE_ROW_RE.match(lines[j]):
                block.append(lines[j])
                j += 1
            has_sep = len(block) >= 2 and _TABLE_SEP_RE.match(block[1])
            header_cells = len([c for c in block[0].strip().strip("|").split("|")])
            if not has_sep and len(block) >= 2:
                # Missing separator after header: insert one.
                sep = "| " + " | ".join(["---"] * header_cells) + " |"
                block.insert(1, sep)
                fixed_any = True
                deviations.append(
                    TypesettingDeviation(
                        code="table_separator_missing",
                        message="检测到表格缺少表头分隔行，已按模板表格规范自动补齐。",
                        severity="fix",
                        auto_fixed=True,
                    )
                )
            # Rectangle-normalise remaining rows (skip the header+sep).
            for k in range(2 if not has_sep else 1, len(block)):
                row = block[k]
                cells = row.strip().strip("|").split("|")
                width = len(cells)
                if width != header_cells:
                    if width < header_cells:
                        padded = row.strip().rstrip("|") + " |" * (
                            header_cells - width
                        )
                        if not padded.strip().startswith("|"):
                            padded = "| " + padded
                        block[k] = padded
                    else:
                        parts = row.strip().strip("|").split("|")
                        block[k] = "| " + " | ".join(parts[:header_cells]) + " |"
                    fixed_any = True
                    deviations.append(
                        TypesettingDeviation(
                            code="table_row_ragged",
                            message=(
                                f"表格第 {k + 1} 行列数与表头不一致，"
                                "已自动对齐列数。"
                            ),
                            severity="fix",
                            auto_fixed=True,
                        )
                    )
            out.extend(block)
            i = j
        else:
            out.append(line)
            i += 1
    if fixed_any:
        return "\n".join(out) + ("\n" if text.endswith("\n") else "")
    return text


def _reconcile_heading_numbering(
    text: str,
    bindings,
    deviations: list[TypesettingDeviation],
) -> str:
    """Re-number headings to the template's canonical scheme.

    Counters track the outline order of H1/H2/H3 in the assembled draft; each
    heading's leading number is replaced by the template-rendered canonical
    number (第X章 / 1.1 / （一）…).  Titles keep their own wording — only the
    machine-derived number prefix is normalised, so wording is never touched.
    """
    if bindings is None:
        return text
    h1_binding = bindings.get("heading1")
    if h1_binding is None or not getattr(h1_binding, "enabled", False):
        return text

    lines = text.splitlines()
    counters = [0] * 9  # index 1..6 used
    changed = False
    out: list[str] = []
    for line in lines:
        match = _ATX_HEADING_RE.match(line)
        if not match:
            out.append(line)
            continue
        level = len(match.group("marks"))
        title = match.group("title").strip()
        if level <= 3:
            counters[level] += 1
            # reset deeper counters when a shallower heading appears
            for deeper in range(level + 1, 7):
                counters[deeper] = 0
            if level == 1:
                canonical = _expected_h1(counters[1], h1_binding)
            elif level == 2:
                h2b = bindings.get("heading2")
                if h2b is None or not getattr(h2b, "enabled", False):
                    out.append(line)
                    continue
                canonical = _expected_h2(counters[1], counters[2], bindings)
            else:
                h3b = bindings.get("heading3")
                if h3b is None or not getattr(h3b, "enabled", False):
                    out.append(line)
                    continue
                canonical = _expected_h3(
                    counters[1], counters[2], counters[3], bindings
                )
            bare = _strip_leading_number(title)
            expected_line = f"{'#' * level} {canonical}\u3000{bare}".rstrip()
            if expected_line != line:
                changed = True
            out.append(expected_line)
        else:
            out.append(line)
    if changed:
        deviations.append(
            TypesettingDeviation(
                code="heading_numbering_normalized",
                message="标题编号已按模板编号规则（第X章/1.1/（一）…）统一重排。",
                severity="fix",
                auto_fixed=True,
            )
        )
        return "\n".join(out) + ("\n" if text.endswith("\n") else "")
    return text


def _check_caption_prefix(
    text: str,
    caption,
    deviations: list[TypesettingDeviation],
) -> None:
    if caption is None:
        return
    table_prefix = str(getattr(caption, "table_prefix", "表") or "表").strip()
    figure_prefix = str(getattr(caption, "figure_prefix", "图") or "图").strip()
    # A caption-like line with an English prefix is drift worth reporting.
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # A caption-like line: 表…/图…/Table…/Figure… near tables — detect a
        # plain "Table x" / "Figure x" English prefix as drift worth warning.
        if re.match(r"^(?:Table|Figure)\s*\d*", stripped):
            deviations.append(
                TypesettingDeviation(
                    code="caption_prefix_english",
                    message=(
                        f"题注使用了英文前缀（{stripped[:12]}…），"
                        f"模板要求使用「{table_prefix}/{figure_prefix}」前缀。"
                    ),
                    severity="warn",
                )
            )


def reconcile_generated_markdown(
    markdown: str,
    *,
    template_id: str = "",
    mode_id: str | None = None,
) -> TypesettingReconcileReport:
    """Measure and (safely) repair template drift in a generated draft.

    Returns a report even when no template is available (empty report), so
    callers never need to branch on template resolution before invoking this.
    """
    text = str(markdown or "")
    template = _load_template(template_id, mode_id)
    if template is None or not text.strip():
        return TypesettingReconcileReport(template_id=template_id)

    deviations: list[TypesettingDeviation] = []
    checked: list[str] = []

    # 1. Heading depth — the template caps how many levels are meaningful.
    heading_model = getattr(template, "heading_model", None)
    max_level = int(getattr(heading_model, "max_heading_levels", 4) or 4)
    checked.append("heading_depth")
    deepest = 0
    for line in text.splitlines():
        match = _ATX_HEADING_RE.match(line)
        if match:
            deepest = max(deepest, len(match.group("marks")))
    if deepest > max_level:
        deviations.append(
            TypesettingDeviation(
                code="heading_depth_exceeds_template",
                message=f"正文出现 {deepest} 级标题，模板最多 {max_level} 级。",
                severity="warn",
            )
        )

    # 2. Heading numbering — canonical re-number from template bindings.
    heading_numbering = getattr(template, "heading_numbering", None)
    if heading_numbering is not None:
        checked.append("heading_numbering")
        bindings = getattr(heading_numbering, "level_bindings", None)
        text = _reconcile_heading_numbering(text, bindings, deviations)

    # 3. Table structure — separator row + rectangular shape.
    checked.append("table_structure")
    table_cfg = getattr(template, "table", None)
    border_mode = str(getattr(table_cfg, "border_mode", "three_line") or "three_line")
    if border_mode != "none":
        text = _reconcile_table_structure(text, deviations)

    # 4. Caption prefix conventions.
    checked.append("caption_prefix")
    caption = getattr(template, "caption", None)
    _check_caption_prefix(text, caption, deviations)

    # 5. Figure placeholders / remote images.
    checked.append("figure_placeholder")
    if _REMOTE_IMAGE_RE.search(text):
        deviations.append(
            TypesettingDeviation(
                code="remote_image_reference",
                message="正文包含远程图片引用，模板要求插图位置使用【图：说明】占位符。",
                severity="warn",
            )
        )

    # 6. Page-number plan — informational, applied by the DOCX composer.
    header_footer = getattr(template, "header_footer", None)
    if header_footer is not None:
        plan = getattr(header_footer, "page_number_plan", None)
        if plan is not None and getattr(plan, "enabled", False):
            checked.append("page_number_plan")
            template_text = str(getattr(plan, "template", "{page}") or "{page}")
            visible_phases = [
                str(p.phase_id)
                for p in (getattr(plan, "phases", ()) or ())
                if getattr(p, "visible", False)
            ]
            deviations.append(
                TypesettingDeviation(
                    code="page_number_plan_applied",
                    message=(
                        "页码将按模板方案由排版引擎生成"
                        f"（格式「{template_text}」，启用分节："
                        f"{'、'.join(visible_phases) or '默认'}）。"
                    ),
                    severity="info",
                )
            )

    corrected = text
    changed = any(item.auto_fixed for item in deviations)

    return TypesettingReconcileReport(
        template_id=str(template_id),
        checked=tuple(checked),
        deviations=tuple(deviations),
        corrected_markdown=corrected,
        changed=changed,
    )


__all__ = [
    "TypesettingDeviation",
    "TypesettingReconcileReport",
    "reconcile_generated_markdown",
]
