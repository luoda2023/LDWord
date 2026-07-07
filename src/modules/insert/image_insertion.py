"""
image_insertion — 图片插入模块

在指定位置插入图片（从配置中读取图片路径和插入位置）。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from docx.shared import Cm

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.run_ops import get_full_text, replace_run_text
if TYPE_CHECKING:
    from docx import Document
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


class ImageInsertionModule(BaseModule):
    """图片插入模块。

    职责：
    - 根据配置在指定位置插入图片
    - 自动缩放到适合页面的尺寸
    - 输出 inserted_images 到 context
    """

    meta = ModuleMeta(
        name="image_insertion",
        description="图片插入",
        category="insert",
        requires_config=("images",),
        provides=("inserted_images",),
        modifies_structure=True,
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        image_list = config.images
        if not image_list:
            return

        inserted: list[dict] = []
        for img_cfg in image_list:
            img_path = img_cfg.path
            position = img_cfg.position
            width_cm = img_cfg.width_cm

            if not img_path or not Path(img_path).exists():
                continue

            para = _resolve_image_paragraph(doc, position)

            run = para.add_run()
            run.add_picture(img_path, width=Cm(width_cm))

            inserted.append({
                "path": img_path,
                "position": position,
                "width_cm": width_cm,
            })

        context.inserted_images = inserted

        if inserted:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{len(inserted)} 张图片",
                section="global",
                change_type="insert",
                before="无",
                after="已插入",
            )


def _resolve_image_paragraph(doc: Document, position: int | str):
    if position == "end":
        return doc.add_paragraph()
    if isinstance(position, int) and position < len(doc.paragraphs):
        return doc.paragraphs[position]

    if isinstance(position, str):
        anchor = position.strip()
        if anchor and anchor != "end":
            for para in doc.paragraphs:
                if anchor in get_full_text(para):
                    replace_run_text(para, anchor, "")
                    return para

    return doc.add_paragraph()
