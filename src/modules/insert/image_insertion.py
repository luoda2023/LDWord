"""
image_insertion — 图片插入模块

在指定位置插入图片（从配置中读取图片路径和插入位置）。
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image as PillowImage
from PIL import UnidentifiedImageError
from docx.image.exceptions import UnrecognizedImageError
from docx.oxml import OxmlElement
from docx.shared import Cm
from docx.text.paragraph import Paragraph

from src.config.materials import is_supported_image_path
from src.modules.base import BaseModule, Issue, ModuleMeta
from src.shared.engine.run_ops import get_full_text, iter_story_paragraphs, replace_run_text
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

    def validate(
        self,
        doc: Document,
        config: ResolvedConfig,
        context: PipelineContext,
    ) -> list[Issue]:
        issues: list[Issue] = []
        for img_cfg in config.images:
            path = str(img_cfg.path or "").strip()
            if not path or not Path(path).exists():
                continue
            reason = _image_validation_error(path)
            if reason:
                issues.append(
                    Issue(
                        level="error",
                        module_name=self.meta.name,
                        message=reason,
                        location=path,
                    )
                )
        return issues

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
        group_paragraphs: dict[tuple[str, str], Paragraph] = {}
        for img_cfg in image_list:
            img_path = img_cfg.path
            position = img_cfg.position
            width_cm = img_cfg.width_cm

            if (
                not img_path
                or not Path(img_path).exists()
                or _image_validation_error(img_path)
            ):
                continue

            group_id = str(getattr(img_cfg, "group_id", "") or "").strip()
            group_key = (group_id, str(position))
            if group_id and group_key in group_paragraphs:
                para = _insert_paragraph_after(group_paragraphs[group_key])
            else:
                para = _resolve_image_paragraph(doc, position)
            if group_id:
                group_paragraphs[group_key] = para

            run = para.add_run()
            try:
                picture_source = _word_picture_source(img_path)
                run.add_picture(picture_source, width=Cm(width_cm))
            except (OSError, ValueError, UnidentifiedImageError, UnrecognizedImageError):
                tracker.record(
                    rule_name=self.meta.name,
                    target=img_path,
                    section="global",
                    change_type="insert_failed",
                    before="",
                    after="图片内容无法读取，已跳过",
                    success=False,
                )
                continue

            inserted.append({
                "path": img_path,
                "position": position,
                "width_cm": width_cm,
                "role": str(getattr(img_cfg, "role", "") or ""),
                "item_id": str(getattr(img_cfg, "item_id", "") or ""),
                "group_id": group_id,
                "sequence": getattr(img_cfg, "sequence", None),
                "normalized_name": str(
                    getattr(img_cfg, "normalized_name", "") or ""
                ),
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
            for para in iter_story_paragraphs(doc):
                if anchor in get_full_text(para):
                    replace_run_text(para, anchor, "")
                    return para

    return doc.add_paragraph()


def _insert_paragraph_after(paragraph: Paragraph) -> Paragraph:
    new_element = OxmlElement("w:p")
    paragraph._p.addnext(new_element)
    return Paragraph(new_element, paragraph._parent)


def _image_validation_error(path: str) -> str:
    if not is_supported_image_path(path):
        return "文件格式不受图片插入链路支持。"
    try:
        with PillowImage.open(path) as image:
            image.verify()
    except (OSError, ValueError, UnidentifiedImageError):
        return "文件内容不是可读取的图片。"
    return ""


def _word_picture_source(path: str):
    if Path(path).suffix.lower() != ".webp":
        return path
    stream = BytesIO()
    with PillowImage.open(path) as image:
        converted = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        converted.save(stream, format="PNG")
    stream.seek(0)
    return stream
