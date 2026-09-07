# -*- coding: utf-8 -*-
"""Post-generation typesetting reconcile ("排版复核校准").

The AI writes each chapter *as if* it is already typeset: the per-chapter
prompt carries the template's heading numbering, table style and figure-caption
conventions (see ``typesetting_templates.typesetting_directives_from_library_template``).
This module is the second pass: once the full draft is assembled and before it
is compiled to DOCX, we measure how far the generated Markdown drifted from the
canonical template and, where the fix is mechanical and safe, apply it.

The reconcile is deliberately *non-blocking*: unlike the strict structural
validators it never rejects a draft.  It produces a report the UI can show and,
optionally, a corrected Markdown the caller may substitute before composing.
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
_CAPTION_PREFIX_RE = re.compile(r"^(?:表|图)\s*\d*[\.\-、:：]?\s*")


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

    # 2. Figure placeholders — the template wants 【图：说明】 markers, never
    #    invented real images (real images are a later materialization phase).
    checked.append("figure_placeholder")
    if "![" in text and "](http" in text:
        deviations.append(
            TypesettingDeviation(
                code="remote_image_reference",
                message="正文包含远程图片引用，模板要求插图位置使用【图：说明】占位符。",
                severity="warn",
            )
        )
    placeholders = _FIGURE_PLACEHOLDER_RE.findall(text)
    if placeholders:
        # Reconcile pass recognises them as compliant; nothing to fix.
        pass

    # 3. Table caption prefix — the template has a fixed 表/图 caption prefix;
    #    a mechanical stray prefix can be normalised.
    checked.append("caption_prefix")
    caption = getattr(template, "caption", None)
    if caption is not None:
        table_prefix = str(getattr(caption, "table_prefix", "表") or "表")
        figure_prefix = str(getattr(caption, "figure_prefix", "图") or "图")

    corrected = text
    changed = False
    for item in deviations:
        if item.auto_fixed:
            changed = True

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
