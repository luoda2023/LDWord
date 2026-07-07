"""validation — lightweight document validation module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.modules.base import BaseModule, Issue, ModuleMeta
from src.shared.engine.count_engine import count_document

if TYPE_CHECKING:
    from docx import Document
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


_BROKEN_TOC_BOOKMARK_HINTS = (
    "error! bookmark not defined",
    "bookmark not defined",
    "未定义书签",
)


class ValidationModule(BaseModule):
    """Validate final document state against core formatting expectations."""

    meta = ModuleMeta(
        name="validation",
        description="结果校验",
        category="validate",
        depends_on=("heading_recognition",),
        consumes=("doc_tree", "heading_map"),
        provides=("validation_issues", "count_result"),
        enabled_by_default=True,
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        context.validation_issues = self.validate(doc, config, context)
        count_profile_id = str(
            getattr(getattr(config, "compliance_profile", None), "count_profile_id", "")
            or ""
        ).strip()
        if count_profile_id:
            context.count_result = count_document(doc, profile_id=count_profile_id)
            tracker.record(
                rule_name="count_engine",
                target=count_profile_id,
                section="global",
                change_type="count_summary",
                after=context.count_result.summary(),
                paragraph_index=-1,
                success=True,
            )

    def validate(
        self,
        doc: Document,
        config: ResolvedConfig,
        context: PipelineContext,
    ) -> list[Issue]:
        issues: list[Issue] = []
        issues.extend(self._check_page_setup(doc, config))
        issues.extend(self._check_heading_styles(doc, config, context))
        issues.extend(self._check_broken_toc_placeholders(doc))
        return issues

    def _check_page_setup(self, doc, config) -> list[Issue]:
        issues: list[Issue] = []
        ps = config.page_setup
        expected_top = round(ps.margin.top_cm * 360000)
        for index, section in enumerate(doc.sections):
            actual_top = section.top_margin
            if actual_top and abs(actual_top - expected_top) > 5000:
                issues.append(
                    Issue(
                        level="warning",
                        module_name=self.meta.name,
                        message=f"页边距(上)不符: 期望 {ps.margin.top_cm}cm",
                        location=f"Section {index + 1}",
                    )
                )
        return issues

    def _check_heading_styles(self, doc, config, context) -> list[Issue]:
        issues: list[Issue] = []
        heading_map = getattr(context, "heading_map", None) or {}
        style_map = getattr(config.heading_model, "level_to_word_style", {}) or {}
        for para_index, level in heading_map.items():
            if not isinstance(para_index, int) or para_index < 0 or para_index >= len(doc.paragraphs):
                continue
            para = doc.paragraphs[para_index]
            expected = style_map.get(f"heading{level}", "")
            actual = para.style.name if para.style else ""
            if expected and actual != expected:
                issues.append(
                    Issue(
                        level="warning",
                        module_name=self.meta.name,
                        message=f"标题样式不符: 期望 '{expected}', 实际 '{actual}'",
                        location=f"段落 #{para_index}",
                    )
                )
        return issues

    def _check_broken_toc_placeholders(self, doc) -> list[Issue]:
        issues: list[Issue] = []
        for index, para in enumerate(doc.paragraphs):
            raw = (para.text or "").strip()
            if not raw or "\t" not in raw:
                continue
            low = raw.lower()
            if any(hint in low for hint in _BROKEN_TOC_BOOKMARK_HINTS):
                issues.append(
                    Issue(
                        level="error",
                        module_name=self.meta.name,
                        message="目录条目存在损坏的书签占位文本",
                        location=f"段落 #{index}",
                    )
                )
        return issues
