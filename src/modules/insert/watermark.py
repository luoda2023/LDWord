"""
watermark — 水印模块

在文档中添加文字/图片水印。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lxml import etree

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.ooxml_ops import qn

if TYPE_CHECKING:
    from docx import Document
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


class WatermarkModule(BaseModule):
    """水印模块。

    职责：
    - 添加文字水印（VML shape 方式）
    - 支持旋转、透明度、颜色配置
    """

    meta = ModuleMeta(
        name="watermark",
        description="水印",
        category="insert",
        requires_config=("watermark",),
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        wm_cfg = config.watermark
        if not wm_cfg.enabled:
            return

        text = wm_cfg.text
        if not text:
            return

        # 通过页眉注入 VML 水印
        for section in doc.sections:
            header = section.header
            header.is_linked_to_previous = False
            _inject_text_watermark(header, text, wm_cfg)

        tracker.record(
            rule_name=self.meta.name,
            target=f"{len(list(doc.sections))} 个节",
            section="global",
            change_type="insert",
            before="无水印",
            after=f"已添加水印: {text[:20]}",
        )


def _inject_text_watermark(header, text: str, wm_cfg) -> None:
    """通过页眉注入 VML 文字水印形状。"""
    color = wm_cfg.color
    rotation = wm_cfg.rotation
    font_size = wm_cfg.font_size

    # VML 水印 XML
    vml_ns = "urn:schemas-microsoft-com:vml"
    o_ns = "urn:schemas-microsoft-com:office:office"

    # 添加到页眉第一段
    if header.paragraphs:
        para = header.paragraphs[0]
    else:
        para = header.add_paragraph()

    # 创建 VML shape 元素
    r = etree.SubElement(para._element, qn("w:r"))
    pict = etree.SubElement(r, qn("w:pict"))

    shape = etree.SubElement(pict, f"{{{vml_ns}}}shape")
    shape.set("id", "WatermarkShape")
    shape.set("type", "#_x0000_t136")
    shape.set(
        "style",
        f"position:absolute;"
        f"margin-left:0;"
        f"margin-top:0;"
        f"width:500pt;"
        f"height:200pt;"
        f"rotation:{rotation};"
        f"z-index:-251657216;"
    )
    shape.set("fillcolor", color)
    shape.set("stroked", "f")

    textpath = etree.SubElement(shape, f"{{{vml_ns}}}textpath")
    textpath.set("style", f"font-family:SimSun;font-size:{font_size}pt")
    textpath.set("string", text)
