"""Safely convert common LaTeX fragments to native Word OMML equations."""

from __future__ import annotations

import re
from collections.abc import Iterable
from copy import deepcopy
from typing import TYPE_CHECKING

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement

from src.formula_core import (
    ConversionOutcome,
    FormulaNode,
    convert_formula_node,
    normalize_formula_node,
    parse_document_formulas,
)
from src.formula_core.parse import _looks_like_non_math_latex_text
from src.modules.base import BaseModule, Issue, ModuleMeta
from src.modules.table.table_format import top_level_table_anchor_positions
from src.shared.engine.document_scope_runtime import document_scope_allows_paragraph
from src.shared.engine.ooxml_ops import qn
from src.utils.ooxml_paragraph import replace_paragraph_payload_with_omml

if TYPE_CHECKING:
    from docx import Document
    from docx.text.paragraph import Paragraph
    from lxml.etree import _Element

    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


_FORMULA_FRAGMENT_RE = re.compile(
    r"(?P<dd>\$\$(?P<ddb>.+?)\$\$)"
    r"|(?P<id>(?<!\$)\$(?P<idb>[^$\r\n]+?)\$(?!\$))"
    r"|(?P<db>\\\[(?P<dbb>.+?)\\\])"
    r"|(?P<ip>\\\((?P<ipb>.+?)\\\))"
)
_PROTECTED_TAGS = (
    "m:oMath",
    "m:oMathPara",
    "w:object",
    "w:drawing",
    "w:fldChar",
    "w:instrText",
)
_SYMBOLS = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ",
    "epsilon": "ε", "varepsilon": "ϵ", "theta": "θ", "lambda": "λ",
    "mu": "μ", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ",
    "phi": "φ", "varphi": "ϕ", "omega": "ω", "Gamma": "Γ",
    "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Pi": "Π",
    "Sigma": "Σ", "Phi": "Φ", "Omega": "Ω", "times": "×",
    "cdot": "·", "pm": "±", "mp": "∓", "le": "≤", "leq": "≤",
    "ge": "≥", "geq": "≥", "ne": "≠", "neq": "≠", "approx": "≈",
    "equiv": "≡", "infty": "∞", "partial": "∂", "nabla": "∇",
    "sum": "∑", "prod": "∏", "int": "∫", "rightarrow": "→",
    "leftarrow": "←", "leftrightarrow": "↔", "degree": "°",
    "sin": "sin", "cos": "cos", "tan": "tan", "log": "log",
    "ln": "ln", "exp": "exp",
}


class FormulaParseError(ValueError):
    """The formula fragment cannot be converted without guessing."""


class FormulaConvertModule(BaseModule):
    """Convert formula sources to editable Word OMML before text cleanup."""

    meta = ModuleMeta(
        name="formula_convert",
        description="公式源转换为 Word 原生可编辑公式",
        category="special",
        requires_config=("formula_convert",),
        modifies_structure=True,
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        policy = config.formula_convert
        if not bool(policy.enabled):
            context.formula_runtime = {
                **dict(context.formula_runtime or {}),
                "convert_enabled": False,
            }
            return
        output_mode = str(
            getattr(policy, "output_mode", "") or "word_native"
        ).strip().lower()
        low_policy = str(
            getattr(policy, "low_confidence_policy", "") or "skip_and_mark"
        ).strip().lower()
        body_scope_positions = {
            paragraph._p: index for index, paragraph in enumerate(doc.paragraphs)
        }
        original_table_anchors = top_level_table_anchor_positions(doc)
        table_scope_positions = {
            table._element: (
                original_table_anchors[index]
                if index < len(original_table_anchors)
                else -1
            )
            for index, table in enumerate(doc.tables)
        }
        parse_result = parse_document_formulas(doc)
        scoped_occurrences = [
            occurrence
            for occurrence in parse_result.occurrences
            if _formula_occurrence_in_scope(
                occurrence,
                context,
                body_scope_positions=body_scope_positions,
                table_scope_positions=table_scope_positions,
            )
        ]
        scoped_source_counts = _formula_source_counts(scoped_occurrences)
        scoped_total = len(scoped_occurrences)
        if output_mode not in {"word_native", "latex"}:
            review_required = output_mode != "keep_source"
            preserved_diagnostics = (
                [
                    {
                        "location": str(occurrence.location),
                        "paragraph_index": int(occurrence.paragraph_index),
                        "source_type": str(occurrence.source_type),
                        "confidence": round(float(occurrence.node.confidence), 3),
                        "reason": "image_fallback_unavailable",
                    }
                    for occurrence in scoped_occurrences
                ]
                if review_required
                else []
            )
            context.formula_runtime = {
                "convert_enabled": True,
                "output_mode": output_mode,
                "source_counts": scoped_source_counts,
                "matched": scoped_total,
                "converted": 0,
                "skipped": scoped_total if review_required else 0,
                "preserved": scoped_total,
                "low_confidence": [],
                "diagnostics": preserved_diagnostics,
                "manual_review_required": review_required and bool(scoped_total),
            }
            tracker.record(
                rule_name=self.meta.name,
                target="公式源",
                section="global",
                change_type="preserve" if output_mode == "keep_source" else "review",
                before=output_mode or "(empty)",
                after=(
                    "保留原文"
                    if output_mode == "keep_source"
                    else "旧图片降级策略已停用，保留原文并要求复核"
                ),
            )
            return

        converted = 0
        skipped = 0
        low_confidence: list[dict[str, object]] = []
        diagnostics: list[dict[str, object]] = []

        # The migrated core covers formula-only paragraphs, multiline LaTeX,
        # repaired plain text, native OMML and MathType/OLE. Work backwards so
        # removing multiline source paragraphs cannot shift pending indices.
        occurrences = sorted(
            scoped_occurrences,
            key=_source_end_index,
            reverse=True,
        )
        saw_latex_source = any(
            str(getattr(item, "source_type", "") or "").lower() == "latex"
            for item in occurrences
        )
        latex_exchange: list[dict[str, object]] = []
        for occurrence in occurrences:
            if (
                occurrence.source_type == "word_native"
                or not occurrence.is_formula_only
            ):
                continue
            if occurrence.in_table and not _paragraph_is_in_equation_table(
                occurrence.paragraph
            ):
                continue

            normalized = normalize_formula_node(occurrence.node)
            preflight_diagnostic = _formula_diagnostic(normalized, "")
            if preflight_diagnostic:
                skipped += 1
                diagnostics.append(
                    _runtime_item(
                        occurrence,
                        float(normalized.confidence),
                        preflight_diagnostic,
                    )
                )
                _record_formula_skip(
                    tracker,
                    occurrence,
                    reason=preflight_diagnostic,
                    confidence=float(normalized.confidence),
                    review=True,
                )
                continue
            outcome, exchange_latex = _convert_to_editable_outcome(
                normalized,
                output_mode,
                # The replacement target is already a w:p. Embedding an
                # m:oMathPara inside it is invalid; block presentation is
                # represented by paragraph alignment instead.
                block=False,
            )
            guard_reason = _guard_untrusted_conversion(
                occurrence,
                normalized,
                outcome,
                exchange_latex,
            )
            confidence = float(
                outcome.confidence if outcome.success else normalized.confidence
            )
            if guard_reason:
                confidence = min(confidence, 0.45)
            diagnostic = _formula_diagnostic(normalized, outcome.reason)
            if diagnostic:
                diagnostics.append(_runtime_item(occurrence, confidence, diagnostic))

            if guard_reason or not outcome.success or outcome.omml_element is None:
                skipped += 1
                _record_formula_skip(
                    tracker,
                    occurrence,
                    reason=guard_reason or outcome.reason or diagnostic or "unsupported_conversion",
                    confidence=confidence,
                    review=(low_policy == "manual_review"),
                )
                continue

            if confidence < _CONFIDENCE_THRESHOLD:
                skipped += 1
                item = _runtime_item(
                    occurrence,
                    confidence,
                    outcome.reason or "low_confidence",
                )
                item["policy"] = low_policy
                low_confidence.append(item)
                _record_formula_skip(
                    tracker,
                    occurrence,
                    reason="low_confidence",
                    confidence=confidence,
                    review=(low_policy in {"manual_review", "image_fallback"}),
                )
                continue

            if not outcome.transformed:
                continue
            applied = replace_paragraph_payload_with_omml(
                occurrence.paragraph._p,
                outcome.omml_element,
            ).applied
            if not applied:
                skipped += 1
                _record_formula_skip(
                    tracker,
                    occurrence,
                    reason="unable_to_replace_paragraph_payload",
                    confidence=confidence,
                    review=True,
                )
                continue
            if occurrence.is_block:
                occurrence.paragraph.paragraph_format.alignment = (
                    WD_ALIGN_PARAGRAPH.CENTER
                )
            _remove_consumed_source_paragraphs(doc, occurrence)
            if output_mode == "latex" and exchange_latex:
                latex_exchange.append(
                    {
                        "location": str(occurrence.location),
                        "paragraph_index": int(occurrence.paragraph_index),
                        "latex": exchange_latex,
                    }
                )
            converted += 1

        wrappers_removed = 0
        if saw_latex_source and converted:
            wrappers_removed = _remove_non_math_latex_wrapper_paragraphs(
                doc,
                context=context,
                body_scope_positions=body_scope_positions,
            )

        # Mixed prose is intentionally excluded from structural replacement by
        # the core. Preserve the safe run-level converter for "$x_i$ means...".
        for paragraph in _iter_convertible_paragraphs(
            doc,
            context=context,
            body_scope_positions=body_scope_positions,
            table_scope_positions=table_scope_positions,
        ):
            converted_count, skipped_count = _convert_paragraph(paragraph)
            converted += converted_count
            skipped += skipped_count

        context.formula_runtime = {
            "convert_enabled": True,
            "output_mode": output_mode,
            "source_counts": scoped_source_counts,
            "matched": scoped_total,
            "converted": converted,
            "skipped": skipped,
            "low_confidence": low_confidence,
            "diagnostics": diagnostics,
            "latex_logic_editable_output": output_mode == "latex",
            "latex_exchange": latex_exchange,
            "latex_wrappers_removed": wrappers_removed,
            "manual_review_required": bool(low_confidence)
            and low_policy in {"manual_review", "image_fallback"},
        }

        if converted:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{converted} 个公式",
                section="global",
                change_type="convert",
                before="LaTeX/文本/MathType 公式源",
                after="Word 原生 OMML 公式",
            )
        if skipped:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{skipped} 个未自动改写的公式",
                section="global",
                change_type="skip",
                before="不受支持、跨 run 或低置信公式源",
                after=f"保留原文（{low_policy}）",
            )

    def validate(self, doc, config, context) -> list[Issue]:
        del doc, context
        output_mode = str(
            getattr(config.formula_convert, "output_mode", "") or "word_native"
        ).strip().lower()
        if output_mode != "image_fallback":
            return []
        return [
            Issue(
                level="warning",
                module_name=self.meta.name,
                message=(
                    "图片降级没有可靠的可编辑等价物，兼容配置将保留公式原文；"
                    "请改用 Word 原生公式或保留原文。"
                ),
            )
        ]


_CONFIDENCE_THRESHOLD = 0.60
_FORMULA_DIAGNOSTIC_CODES = {
    "mathtype_binary_unparsed",
    "missing_equation_native_stream",
    "mathtype_decode_failed",
    "ole_relationship_missing",
    "ole_target_missing",
    "mathtype_ole_dependency_missing",
    "olefile_dependency_missing",
    "ole_binary_unparsed",
}


def _formula_source_counts(occurrences) -> dict[str, int]:
    counts: dict[str, int] = {}
    for occurrence in occurrences:
        source_type = str(getattr(occurrence, "source_type", "") or "unknown")
        counts[source_type] = counts.get(source_type, 0) + 1
    return counts


def _formula_occurrence_in_scope(
    occurrence,
    context: PipelineContext,
    *,
    body_scope_positions: dict[object, int],
    table_scope_positions: dict[object, int],
) -> bool:
    if bool(getattr(occurrence, "in_table", False)):
        table_element = _paragraph_top_level_table_element(occurrence.paragraph)
        position = table_scope_positions.get(table_element, -1)
        return document_scope_allows_paragraph(context, position)

    positions = [
        int(position)
        for position in (
            getattr(occurrence, "source_paragraph_indices", None) or []
        )
        if int(position) >= 0
    ]
    if not positions:
        positions = [body_scope_positions.get(occurrence.paragraph._p, -1)]
    # A multiline formula that crosses a reviewed region boundary must remain
    # untouched; checking only its first paragraph would authorize a partial
    # structural rewrite outside the selected scope.
    return bool(positions) and all(
        document_scope_allows_paragraph(context, position)
        for position in positions
    )


def _remove_non_math_latex_wrapper_paragraphs(
    doc: Document,
    *,
    context: PipelineContext,
    body_scope_positions: dict[object, int],
) -> int:
    removed = 0
    for index in range(len(doc.paragraphs) - 1, -1, -1):
        paragraph = doc.paragraphs[index]
        position = body_scope_positions.get(paragraph._p, -1)
        if not document_scope_allows_paragraph(context, position):
            continue
        if not _looks_like_non_math_latex_text(str(paragraph.text or "").strip()):
            continue
        parent = paragraph._p.getparent()
        if parent is not None:
            parent.remove(paragraph._p)
            removed += 1
    return removed


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _contains_escape_placeholder_noise(text: str) -> bool:
    value = str(text or "")
    return "ESC_" in value or "__ESC" in value


def _guard_untrusted_conversion(
    occurrence,
    normalized_node: FormulaNode,
    editable_outcome: ConversionOutcome,
    exchange_latex: str,
) -> str | None:
    warnings = [
        str(item or "").strip()
        for item in (
            list(getattr(normalized_node, "warnings", []) or [])
            + list(editable_outcome.warnings or [])
        )
    ]
    recovered_escape = bool(
        {
            "escape_placeholder_command_recovered",
            "escape_placeholder_formula_extracted",
            "rendered_segment_extracted",
            "command_context_extracted",
            "big_operator_context_extracted",
        }.intersection(warnings)
    )
    if editable_outcome.reason == "fallback_literal_conversion" or (
        "fallback_literal_conversion" in warnings
    ):
        return "fallback_literal_conversion"
    payload = normalized_node.payload if isinstance(normalized_node.payload, dict) else {}
    texts = [
        str(payload.get("latex", "")),
        str(payload.get("normalized_latex", "")),
        exchange_latex,
    ]
    if not recovered_escape:
        texts.append(str(payload.get("text", "")))
    if any(_contains_escape_placeholder_noise(item) for item in texts):
        return "escape_placeholder_noise"
    if _contains_escape_placeholder_noise(
        str(getattr(occurrence, "source_text", "") or "")
    ) and not recovered_escape:
        return "escape_placeholder_noise"
    return None


def _convert_to_editable_outcome(
    node: FormulaNode,
    output_mode: str,
    *,
    block: bool,
) -> tuple[ConversionOutcome, str]:
    if output_mode == "word_native":
        return convert_formula_node(node, "word_native", block=block), ""
    if str(getattr(node, "source_type", "") or "").lower() == "word_native":
        return (
            ConversionOutcome(
                success=True,
                target_mode="word_native",
                confidence=max(0.85, float(getattr(node, "confidence", 0.0) or 0.0)),
                reason="already_word_native_latex_mode_noop",
                warnings=_dedupe(list(getattr(node, "warnings", []) or [])),
                transformed=False,
            ),
            "",
        )

    latex_out = convert_formula_node(node, "latex", block=block)
    if not latex_out.success:
        return latex_out, ""
    latex_expr = str(latex_out.latex_text or "").strip()
    if not latex_expr:
        return (
            ConversionOutcome(
                success=False,
                target_mode="word_native",
                confidence=max(0.0, float(latex_out.confidence)),
                reason="empty_latex_exchange",
                warnings=_dedupe(list(latex_out.warnings or []) + ["empty_latex_exchange"]),
            ),
            "",
        )

    roundtrip_node = FormulaNode(
        kind=node.kind,
        payload={"latex": latex_expr},
        children=[],
        source_type="latex",
        confidence=latex_out.confidence,
        warnings=list(latex_out.warnings or []),
    )
    word_out = convert_formula_node(roundtrip_node, "word_native", block=block)
    if not word_out.success:
        return (
            ConversionOutcome(
                success=False,
                target_mode="word_native",
                confidence=min(float(latex_out.confidence), float(word_out.confidence)),
                reason=f"latex_roundtrip_failed:{word_out.reason or 'unknown'}",
                warnings=_dedupe(
                    list(latex_out.warnings or [])
                    + list(word_out.warnings or [])
                    + ["latex_roundtrip_failed"]
                ),
            ),
            latex_expr,
        )
    word_out.confidence = min(float(latex_out.confidence), float(word_out.confidence))
    word_out.reason = "latex_roundtrip_to_word_native"
    word_out.warnings = _dedupe(
        list(latex_out.warnings or []) + list(word_out.warnings or [])
    )
    return word_out, latex_expr


def _source_end_index(occurrence) -> int:
    indices = [
        int(index)
        for index in list(getattr(occurrence, "source_paragraph_indices", []) or [])
        if isinstance(index, int) and index >= 0
    ]
    return max(indices) if indices else int(getattr(occurrence, "paragraph_index", -1))


def _remove_consumed_source_paragraphs(doc: Document, occurrence) -> None:
    anchor = int(getattr(occurrence, "paragraph_index", -1))
    indices = sorted(
        {
            int(index)
            for index in list(
                getattr(occurrence, "source_paragraph_indices", []) or []
            )
            if isinstance(index, int) and index >= 0 and index != anchor
        },
        reverse=True,
    )
    for index in indices:
        if index >= len(doc.paragraphs):
            continue
        paragraph = doc.paragraphs[index]
        parent = paragraph._p.getparent()
        if parent is not None:
            parent.remove(paragraph._p)


def _formula_diagnostic(node, outcome_reason: str) -> str:
    payload = node.payload if isinstance(node.payload, dict) else {}
    candidates = [payload.get("diagnostic_code"), outcome_reason]
    candidates.extend(list(getattr(node, "warnings", []) or []))
    for value in candidates:
        code = str(value or "").strip()
        if code in _FORMULA_DIAGNOSTIC_CODES or code.startswith(
            "unsupported_mtef_version"
        ):
            return code
    return ""


def _runtime_item(occurrence, confidence: float, reason: str) -> dict[str, object]:
    return {
        "location": str(occurrence.location),
        "paragraph_index": int(occurrence.paragraph_index),
        "source_type": str(occurrence.source_type),
        "confidence": round(float(confidence), 3),
        "reason": str(reason or "unknown"),
    }


def _record_formula_skip(
    tracker: ChangeTracker,
    occurrence,
    *,
    reason: str,
    confidence: float,
    review: bool,
) -> None:
    tracker.record(
        rule_name="formula_convert",
        target=str(occurrence.location),
        section="formula",
        change_type="review" if review else "skip",
        before=str(occurrence.source_type),
        after=(
            f"保留原文并要求人工复核（{reason}，置信度 {confidence:.2f}）"
            if review
            else f"保留原文并标记（{reason}，置信度 {confidence:.2f}）"
        ),
        paragraph_index=int(occurrence.paragraph_index),
    )


def _iter_convertible_paragraphs(
    doc: Document,
    *,
    context: PipelineContext,
    body_scope_positions: dict[object, int],
    table_scope_positions: dict[object, int],
) -> Iterable[Paragraph]:
    for paragraph in doc.paragraphs:
        position = body_scope_positions.get(paragraph._p, -1)
        if document_scope_allows_paragraph(context, position):
            yield paragraph
    for table in doc.tables:
        position = table_scope_positions.get(table._element, -1)
        if not document_scope_allows_paragraph(context, position):
            continue
        yield from _iter_table_paragraphs(table)


def _iter_table_paragraphs(table) -> Iterable[Paragraph]:
    from src.modules.table.table_format import _is_equation_table

    is_equation_table = _is_equation_table(table)
    seen_cells: set[int] = set()
    for row in table.rows:
        for cell in row.cells:
            identity = id(cell._tc)
            if identity in seen_cells:
                continue
            seen_cells.add(identity)
            if is_equation_table:
                yield from cell.paragraphs
            for nested_table in cell.tables:
                yield from _iter_table_paragraphs(nested_table)


def _paragraph_table_element(paragraph: Paragraph):
    node = getattr(paragraph, "_p", None)
    while node is not None:
        parent = node.getparent()
        if parent is None:
            return None
        if parent.tag.rsplit("}", 1)[-1] == "tbl":
            return parent
        node = parent
    return None


def _paragraph_top_level_table_element(paragraph: Paragraph):
    node = getattr(paragraph, "_p", None)
    outermost_table = None
    while node is not None:
        parent = node.getparent()
        if parent is None:
            return outermost_table
        local_name = parent.tag.rsplit("}", 1)[-1]
        if local_name == "tbl":
            outermost_table = parent
        elif local_name == "body":
            return outermost_table
        node = parent
    return outermost_table


def _paragraph_is_in_equation_table(paragraph: Paragraph) -> bool:
    table_element = _paragraph_table_element(paragraph)
    if table_element is None:
        return False
    from src.modules.table.table_format import _is_equation_table

    return _is_equation_table(table_element)


def paragraph_has_protected_formula_content(paragraph: Paragraph) -> bool:
    element = paragraph._element
    return any(element.find(f".//{qn(tag)}") is not None for tag in _PROTECTED_TAGS)


def paragraph_has_formula_source(text: str) -> bool:
    if not text:
        return False
    return bool(
        _FORMULA_FRAGMENT_RE.search(text)
        or "$" in text
        or "\\(" in text
        or "\\[" in text
    )


def _convert_paragraph(paragraph: Paragraph) -> tuple[int, int]:
    if paragraph_has_protected_formula_content(paragraph):
        return 0, 0

    converted = 0
    skipped = 0
    for run in list(paragraph.runs):
        text = run.text or ""
        matches = list(_FORMULA_FRAGMENT_RE.finditer(text))
        if not matches:
            if paragraph_has_formula_source(text):
                skipped += 1
            continue

        replacements: list[_Element] = []
        cursor = 0
        equations_in_run = 0
        contains_display_formula = False
        try:
            for match in matches:
                if match.start() > cursor:
                    replacements.append(_clone_text_run(run._element, text[cursor:match.start()]))
                body, display = _matched_formula(match)
                replacements.append(latex_fragment_to_omml(body, display=display))
                contains_display_formula = contains_display_formula or display
                equations_in_run += 1
                cursor = match.end()
        except FormulaParseError:
            skipped += len(matches)
            continue

        if cursor < len(text):
            replacements.append(_clone_text_run(run._element, text[cursor:]))
        parent = run._element.getparent()
        if parent is None:
            skipped += len(matches)
            continue
        insert_at = parent.index(run._element)
        parent.remove(run._element)
        for offset, node in enumerate(replacements):
            parent.insert(insert_at + offset, node)
        if contains_display_formula and not _visible_text_outside_formula(text, matches):
            paragraph.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        converted += equations_in_run
    return converted, skipped


def _matched_formula(match: re.Match[str]) -> tuple[str, bool]:
    for group_name, display in (("ddb", True), ("idb", False), ("dbb", True), ("ipb", False)):
        value = match.group(group_name)
        if value is not None:
            return value.strip(), display
    raise FormulaParseError("missing formula body")


def _clone_text_run(source_run: _Element, text: str) -> _Element:
    run = OxmlElement("w:r")
    run_pr = source_run.find(qn("w:rPr"))
    if run_pr is not None:
        run.append(deepcopy(run_pr))
    text_node = OxmlElement("w:t")
    if text[:1].isspace() or text[-1:].isspace():
        text_node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    text_node.text = text
    run.append(text_node)
    return run


def latex_fragment_to_omml(source: str, *, display: bool = False) -> _Element:
    nodes = _FormulaParser(source).parse()
    if not nodes:
        raise FormulaParseError("empty formula")
    math = OxmlElement("m:oMath")
    for node in nodes:
        math.append(node)
    # A formula fragment is inserted inside an existing ``w:p``.  ``m:oMath``
    # is valid there, while ``m:oMathPara`` is a body-level block and would
    # make the paragraph invalid.  Display fragments are centered by applying
    # paragraph alignment in ``_convert_paragraph``.
    del display
    return math


def _visible_text_outside_formula(
    text: str,
    matches: list[re.Match[str]],
) -> bool:
    cursor = 0
    for match in matches:
        if text[cursor:match.start()].strip():
            return True
        cursor = match.end()
    return bool(text[cursor:].strip())


class _FormulaParser:
    def __init__(self, source: str) -> None:
        self.source = str(source or "")
        self.position = 0

    def parse(self) -> list[_Element]:
        nodes = self._parse_sequence(stop=None)
        if self.position != len(self.source):
            raise FormulaParseError("unexpected trailing syntax")
        return nodes

    def _parse_sequence(self, *, stop: str | None) -> list[_Element]:
        nodes: list[_Element] = []
        while self.position < len(self.source):
            char = self.source[self.position]
            if stop is not None and char == stop:
                self.position += 1
                return nodes
            if char == "}":
                raise FormulaParseError("unbalanced closing brace")
            if char.isspace():
                self.position += 1
                if nodes and _node_text(nodes[-1]) != " ":
                    nodes.append(_math_run(" "))
                continue
            base = self._parse_atom()
            subscript: list[_Element] | None = None
            superscript: list[_Element] | None = None
            while self.position < len(self.source) and self.source[self.position] in "_^":
                operator = self.source[self.position]
                self.position += 1
                script = self._parse_script_argument()
                if operator == "_":
                    if subscript is not None:
                        raise FormulaParseError("duplicate subscript")
                    subscript = script
                else:
                    if superscript is not None:
                        raise FormulaParseError("duplicate superscript")
                    superscript = script
            nodes.append(_script_node(base, subscript=subscript, superscript=superscript))
        if stop is not None:
            raise FormulaParseError("unbalanced opening brace")
        return nodes

    def _parse_atom(self) -> _Element:
        char = self.source[self.position]
        if char == "{":
            self.position += 1
            return _box_node(self._parse_sequence(stop="}"))
        if char != "\\":
            self.position += 1
            return _math_run(char)

        self.position += 1
        if self.position >= len(self.source):
            raise FormulaParseError("dangling backslash")
        if not self.source[self.position].isalpha():
            escaped = self.source[self.position]
            self.position += 1
            return _math_run(escaped)
        start = self.position
        while self.position < len(self.source) and self.source[self.position].isalpha():
            self.position += 1
        command = self.source[start:self.position]
        if command == "frac":
            return _fraction_node(self._parse_required_group(), self._parse_required_group())
        if command == "sqrt":
            if self.position < len(self.source) and self.source[self.position] == "[":
                raise FormulaParseError("root degree requires manual review")
            return _radical_node(self._parse_required_group())
        if command in {"text", "mathrm", "mathbf", "mathit", "operatorname"}:
            return _box_node(self._parse_required_group())
        if command in {"left", "right"}:
            self._skip_spaces()
            if self.position >= len(self.source):
                raise FormulaParseError("missing delimiter")
            delimiter = self.source[self.position]
            self.position += 1
            return _math_run("" if delimiter == "." else delimiter)
        symbol = _SYMBOLS.get(command)
        if symbol is None:
            raise FormulaParseError(f"unsupported command: {command}")
        return _math_run(symbol)

    def _parse_required_group(self) -> list[_Element]:
        self._skip_spaces()
        if self.position >= len(self.source) or self.source[self.position] != "{":
            raise FormulaParseError("command argument must be braced")
        self.position += 1
        return self._parse_sequence(stop="}")

    def _parse_script_argument(self) -> list[_Element]:
        self._skip_spaces()
        if self.position >= len(self.source):
            raise FormulaParseError("missing script argument")
        if self.source[self.position] == "{":
            self.position += 1
            return self._parse_sequence(stop="}")
        return [self._parse_atom()]

    def _skip_spaces(self) -> None:
        while self.position < len(self.source) and self.source[self.position].isspace():
            self.position += 1


def _math_run(text: str) -> _Element:
    run = OxmlElement("m:r")
    text_node = OxmlElement("m:t")
    if text[:1].isspace() or text[-1:].isspace():
        text_node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    text_node.text = text
    run.append(text_node)
    return run


def _node_text(node: _Element) -> str:
    text_node = node.find(qn("m:t"))
    return str(text_node.text or "") if text_node is not None else ""


def _box_node(nodes: list[_Element]) -> _Element:
    box = OxmlElement("m:box")
    expression = OxmlElement("m:e")
    for node in nodes:
        expression.append(node)
    box.append(expression)
    return box


def _fraction_node(numerator: list[_Element], denominator: list[_Element]) -> _Element:
    fraction = OxmlElement("m:f")
    num = OxmlElement("m:num")
    den = OxmlElement("m:den")
    for node in numerator:
        num.append(node)
    for node in denominator:
        den.append(node)
    fraction.extend((num, den))
    return fraction


def _radical_node(nodes: list[_Element]) -> _Element:
    radical = OxmlElement("m:rad")
    properties = OxmlElement("m:radPr")
    degree_hidden = OxmlElement("m:degHide")
    degree_hidden.set(qn("m:val"), "1")
    properties.append(degree_hidden)
    expression = OxmlElement("m:e")
    for node in nodes:
        expression.append(node)
    radical.extend((properties, expression))
    return radical


def _script_node(
    base: _Element,
    *,
    subscript: list[_Element] | None,
    superscript: list[_Element] | None,
) -> _Element:
    if subscript is None and superscript is None:
        return base
    if subscript is not None and superscript is not None:
        scripted = OxmlElement("m:sSubSup")
        slots = (OxmlElement("m:e"), OxmlElement("m:sub"), OxmlElement("m:sup"))
        slots[0].append(base)
        for node in subscript:
            slots[1].append(node)
        for node in superscript:
            slots[2].append(node)
        scripted.extend(slots)
        return scripted
    if subscript is not None:
        scripted = OxmlElement("m:sSub")
        slots = (OxmlElement("m:e"), OxmlElement("m:sub"))
        slots[0].append(base)
        for node in subscript:
            slots[1].append(node)
        scripted.extend(slots)
        return scripted
    scripted = OxmlElement("m:sSup")
    slots = (OxmlElement("m:e"), OxmlElement("m:sup"))
    slots[0].append(base)
    for node in superscript or ():
        slots[1].append(node)
    scripted.extend(slots)
    return scripted


__all__ = [
    "FormulaConvertModule",
    "FormulaParseError",
    "latex_fragment_to_omml",
    "paragraph_has_formula_source",
    "paragraph_has_protected_formula_content",
]
