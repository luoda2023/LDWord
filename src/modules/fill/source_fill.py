"""
source_fill — 来源信息填充模块

填充文档来源相关的元信息（文件名、路径、日期等）。
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.run_ops import replace_run_text, get_full_text

if TYPE_CHECKING:
    from docx import Document
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


# 预定义来源键
SOURCE_KEYS: dict[str, str] = {
    "source_filename": "源文件名",
    "source_dir": "源目录",
    "source_path": "完整路径",
    "process_date": "处理日期",
    "process_time": "处理时间",
    "process_datetime": "处理日期时间",
}


class SourceFillModule(BaseModule):
    """来源信息填充模块。

    职责：
    - 自动计算来源信息（文件名、路径、当前日期等）
    - 替换文档中的 {{source_xxx}} 占位符
    - 输出到 context.source_values
    """

    meta = ModuleMeta(
        name="source_fill",
        description="来源信息填充",
        category="fill",
        requires_config=(),
        provides=("source_values",),
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        now = datetime.now()
        src_path = Path(context.source_doc_path) if context.source_doc_path else Path()

        source_values: dict[str, str] = {
            "source_filename": src_path.stem if src_path.stem else "",
            "source_dir": str(src_path.parent) if src_path.parent else "",
            "source_path": str(src_path),
            "process_date": now.strftime("%Y-%m-%d"),
            "process_time": now.strftime("%H:%M:%S"),
            "process_datetime": now.strftime("%Y-%m-%d %H:%M"),
        }

        total_replaced = 0
        for para in doc.paragraphs:
            text = get_full_text(para)
            if not text:
                continue
            for key, value in source_values.items():
                for fmt in ("{{" + key + "}}", "${" + key + "}"):
                    if fmt in text:
                        replace_run_text(para, fmt, value)
                        total_replaced += 1
                        text = get_full_text(para)

        context.source_values = source_values

        if total_replaced:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{total_replaced} 处来源占位符",
                section="global",
                change_type="replace",
                before="{{source_xxx}}",
                after="已填充来源信息",
            )
