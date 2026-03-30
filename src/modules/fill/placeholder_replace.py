"""
placeholder_replace — 通用占位符替换模块

批量替换文档中的自由定义占位符。
区别于 entity_fill / source_fill 的预定义字段，这里处理用户自定义的任意替换对。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.run_ops import replace_run_text, get_full_text

if TYPE_CHECKING:
    from docx import Document
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


class PlaceholderReplaceModule(BaseModule):
    """通用占位符替换模块。

    职责：
    - 读取 config.replacements（list of {old, new}）
    - 在全文查找替换
    - 支持正则替换（可选）
    """

    meta = ModuleMeta(
        name="placeholder_replace",
        description="占位符替换",
        category="fill",
        requires_config=("replacements",),
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        replacements = config.replacements
        if not replacements:
            return

        total = 0
        for rule in replacements:
            old_text = rule.old
            new_text = rule.new
            if not old_text:
                continue

            for para in doc.paragraphs:
                text = get_full_text(para)
                if old_text in text:
                    count = replace_run_text(para, old_text, new_text)
                    total += count

            # 页眉页脚也替换
            for section in doc.sections:
                for part in (section.header, section.footer):
                    for para in part.paragraphs:
                        text = get_full_text(para)
                        if old_text in text:
                            replace_run_text(para, old_text, new_text)
                            total += 1

        if total:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{total} 处替换",
                section="global",
                change_type="replace",
                before=f"{len(replacements)} 条替换规则",
                after="已完成替换",
            )
