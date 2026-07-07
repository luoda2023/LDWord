"""
entity_fill — 实体信息填充模块

从 EntityArchive 中读取实体数据（作者、学校、日期等），
填充到文档中的占位符或指定位置。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.modules.base import BaseModule, ModuleMeta
from src.config.material_schema_registry import resolve_material_schema_ids
from src.shared.engine.patterns import PLACEHOLDER_DBL_BRACE, PLACEHOLDER_DOLLAR
from src.shared.engine.run_ops import replace_run_text, get_full_text
from src.shared.engine.fixed_layout_text import (
    replace_fixed_layout_mapped_fields,
    replace_fixed_layout_placeholders,
)

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

        fixed_layout_replacements: dict[str, str] = {}
        token_to_key: dict[str, str] = {}
        for key, value in entity_data.items():
            for token in ("{{" + key + "}}", "${" + key + "}"):
                fixed_layout_replacements[token] = value
                token_to_key[token] = key
        fixed_layout_result = replace_fixed_layout_placeholders(
            doc,
            fixed_layout_replacements,
        )
        total_replaced += fixed_layout_result.total_replacements
        for token in fixed_layout_result.replaced_tokens:
            key = token_to_key.get(token)
            if key:
                filled_values[key] = entity_data[key]

        input_profile = getattr(config, "input_source_profile", None)
        schema_ids = resolve_material_schema_ids(
            str(getattr(input_profile, "material_schema_id", "") or "").strip(),
            list(getattr(input_profile, "material_schema_ids", []) or []),
        )
        mapped_result = replace_fixed_layout_mapped_fields(
            doc,
            entity_data,
            field_aliases=getattr(config, "field_aliases", {}) or {},
            schema_ids=schema_ids,
        )
        total_replaced += mapped_result.total_replacements
        for key in mapped_result.replaced_fields:
            filled_values[key] = entity_data[key]
        if mapped_result.has_replacements:
            tracker.record(
                rule_name=self.meta.name,
                target=(
                    f"{mapped_result.total_replacements} 处固定版位字段映射"
                ),
                section="fixed_layout",
                change_type="fixed_layout_field_mapping",
                before=", ".join(mapped_result.matched_identifiers),
                after=", ".join(mapped_result.replaced_fields),
            )

        context.entity_values = filled_values

        if total_replaced:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{total_replaced} 处占位符/字段",
                section="global",
                change_type="replace",
                before="{{...}} / ${...}",
                after=f"已填充 {len(filled_values)} 个字段",
            )
