"""Convert standalone native equations into two-column equation tables."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement

from src.shared.engine.ooxml_ops import qn

from src.formula_core import parse_document_formulas
from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.document_scope_runtime import document_scope_allows_paragraph

if TYPE_CHECKING:
    from docx import Document

    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_TABLE_ALIGNMENTS = {
    "left": WD_TABLE_ALIGNMENT.LEFT,
    "center": WD_TABLE_ALIGNMENT.CENTER,
    "right": WD_TABLE_ALIGNMENT.RIGHT,
}


class FormulaToTableModule(BaseModule):
    """Containerize block equations without rewriting their formula payload."""

    meta = ModuleMeta(
        name="formula_to_table",
        description="块公式转换为公式表格",
        category="special",
        requires_config=("formula_table",),
        soft_after=("formula_convert",),
        modifies_structure=True,
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> dict[object, int]:
        parse_result = parse_document_formulas(doc)
        policy = config.formula_to_table
        if not bool(policy.enabled):
            return {}
        block_only = bool(policy.block_only)
        candidates: dict[object, object] = {}
        formula_runtime = getattr(context, "formula_runtime", None) or {}
        conversion_was_attempted = bool(
            formula_runtime.get("convert_enabled")
            and str(formula_runtime.get("output_mode") or "").lower()
            in {"word_native", "latex"}
        )
        for occurrence in parse_result.occurrences:
            if (
                (
                    conversion_was_attempted
                    and occurrence.source_type != "word_native"
                )
                or not occurrence.is_formula_only
                or (
                    block_only
                    and not _is_block_formula_occurrence(occurrence)
                )
                or occurrence.in_table
                or not _is_body_paragraph(occurrence.paragraph)
                or not document_scope_allows_paragraph(
                    context,
                    int(occurrence.paragraph_index),
                )
            ):
                continue
            candidates.setdefault(occurrence.paragraph._p, occurrence)

        ordered = sorted(
            candidates.values(),
            key=lambda item: int(item.paragraph_index),
            reverse=True,
        )
        converted = 0
        created_table_positions: dict[object, int] = {}
        for occurrence in ordered:
            paragraph = occurrence.paragraph
            table = doc.add_table(rows=1, cols=2)
            alignment = str(
                getattr(config.formula_table, "table_alignment", "center")
                or "center"
            ).strip().lower()
            table.alignment = _TABLE_ALIGNMENTS.get(
                alignment,
                WD_TABLE_ALIGNMENT.CENTER,
            )
            _mark_equation_table(table)
            _copy_paragraph_payload(paragraph, table.cell(0, 0).paragraphs[0])
            table.cell(0, 1).paragraphs[0].text = ""

            source = paragraph._p
            parent = source.getparent()
            generated = table._tbl
            if parent is None or generated.getparent() is None:
                continue
            generated.getparent().remove(generated)
            parent.insert(parent.index(source) + 1, generated)
            parent.remove(source)
            created_table_positions[generated] = int(occurrence.paragraph_index)
            converted += 1

        runtime = dict(context.formula_runtime or {})
        runtime["to_table_enabled"] = True
        runtime["tables_created"] = converted
        context.formula_runtime = runtime
        if converted:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{converted} 个块公式",
                section="formula",
                change_type="structure",
                before="独立公式段落",
                after="两列公式表（公式列 + 编号列）",
            )
        return created_table_positions


def _is_body_paragraph(paragraph) -> bool:
    parent = paragraph._p.getparent()
    if parent is None:
        return False
    return parent.tag.rsplit("}", 1)[-1] == "body"


def _is_block_formula_occurrence(occurrence) -> bool:
    if bool(getattr(occurrence, "is_block", False)):
        return True
    # Editable block LaTeX is emitted as m:oMath inside a centered w:p because
    # nesting m:oMathPara in w:p is invalid.  Preserve that block signal while
    # keeping a formula-only inline fragment (for example ``$x$``) out of the
    # equation-table path.
    return (
        occurrence.paragraph.paragraph_format.alignment
        == WD_ALIGN_PARAGRAPH.CENTER
    )


def _copy_paragraph_payload(source, target) -> None:
    ppr_tag = f"{{{_W_NS}}}pPr"
    for child in list(target._p):
        if child.tag != ppr_tag:
            target._p.remove(child)
    for child in list(source._p):
        if child.tag != ppr_tag:
            target._p.append(deepcopy(child))


def _mark_equation_table(table) -> None:
    tbl_pr = table._tbl.tblPr
    description = tbl_pr.find(qn("w:tblDescription"))
    if description is None:
        description = OxmlElement("w:tblDescription")
        tbl_pr.append(description)
    description.set(qn("w:val"), "ldword-equation-table")


__all__ = ["FormulaToTableModule"]
