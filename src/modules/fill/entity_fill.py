"""
entity_fill — 实体信息填充模块

从 EntityArchive 中读取实体数据（作者、学校、日期等），
填充到文档中的占位符或指定位置。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.patterns import PLACEHOLDER_DBL_BRACE, PLACEHOLDER_DOLLAR
from src.shared.engine.run_ops import replace_run_text, get_full_text

if TYPE_CHECKING:
    from docx import Document
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


class EntityFillModule(BaseModule):
    """实体信息填充模块。

    职责：
    - 读取 config.entity_data 中的键值对
    - 替换文档中的 {{key}} / ${key} 占位符
    - 输出已填充的键值对到 context.entity_values
    """

    meta = ModuleMeta(
        name="entity_fill",
        description="实体信息填充",
        category="fill",
        requires_config=("entity_data",),
        provides=("entity_values",),
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        entity_data = config.entity_data
        if not entity_data:
            return

        total_replaced = 0
        filled_values: dict[str, str] = {}

        for para in doc.paragraphs:
            text = get_full_text(para)
            if not text:
                continue

            for key, value in entity_data.items():
                # 尝试 {{key}} 格式
                placeholder_dbl = "{{" + key + "}}"
                if placeholder_dbl in text:
                    count = replace_run_text(para, placeholder_dbl, value)
                    total_replaced += count
                    filled_values[key] = value
                    text = get_full_text(para)

                # 尝试 ${key} 格式
                placeholder_dollar = "${" + key + "}"
                if placeholder_dollar in text:
                    count = replace_run_text(para, placeholder_dollar, value)
                    total_replaced += count
                    filled_values[key] = value
                    text = get_full_text(para)

        # 同样处理页眉页脚
        for section in doc.sections:
            for part in (section.header, section.footer):
                for para in part.paragraphs:
                    text = get_full_text(para)
                    if not text:
                        continue
                    for key, value in entity_data.items():
                        for fmt in ("{{" + key + "}}", "${" + key + "}"):
                            if fmt in text:
                                replace_run_text(para, fmt, value)
                                total_replaced += 1
                                filled_values[key] = value
                                text = get_full_text(para)

        context.entity_values = filled_values

        if total_replaced:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{total_replaced} 处占位符",
                section="global",
                change_type="replace",
                before="{{...}} / ${...}",
                after=f"已填充 {len(filled_values)} 个字段",
            )
