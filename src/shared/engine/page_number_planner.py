"""Shared page-number planning for section boundaries and header/footer output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterable

from src.config.feature_configs import default_continuous_page_number_phases
from src.config.section_semantics import canonicalize_section_type

if TYPE_CHECKING:
    from docx import Document
    from src.config.feature_configs import HeaderFooterConfig
    from src.pipeline.context import PipelineContext


COVER_SECTION_TYPES = frozenset({"cover"})
PRE_NUMBERING_SECTION_TYPES = frozenset({"cover", "statement", "authorization", "front_note"})
FRONT_MATTER_SECTION_TYPES = frozenset({"abstract_cn", "abstract_en", "toc"})
BACK_MATTER_SECTION_TYPES = frozenset(
    {"references", "errata", "appendix", "acknowledgment", "resume"}
)
NON_NUMBERED_HEADING_SECTION_TYPES = BACK_MATTER_SECTION_TYPES
ALL_NUMBERED_SECTION_TYPES = FRONT_MATTER_SECTION_TYPES | {"body"} | BACK_MATTER_SECTION_TYPES
BOUNDARY_SECTION_TYPES = PRE_NUMBERING_SECTION_TYPES | FRONT_MATTER_SECTION_TYPES | {"body"} | BACK_MATTER_SECTION_TYPES

_SELECTOR_SECTION_TYPES: dict[str, frozenset[str]] = {
    "cover": COVER_SECTION_TYPES,
    "pre_numbering": PRE_NUMBERING_SECTION_TYPES,
    "statement": frozenset({"statement"}),
    "authorization": frozenset({"authorization"}),
    "front_note": frozenset({"front_note"}),
    "front_matter": FRONT_MATTER_SECTION_TYPES,
    "abstracts": frozenset({"abstract_cn", "abstract_en"}),
    "toc": frozenset({"toc"}),
    "body": frozenset({"body"}),
    "back_matter": BACK_MATTER_SECTION_TYPES,
    "references": frozenset({"references"}),
    "errata": frozenset({"errata"}),
    "appendix": frozenset({"appendix"}),
    "acknowledgment": frozenset({"acknowledgment"}),
    "resume": frozenset({"resume"}),
    "all_numbered_content": ALL_NUMBERED_SECTION_TYPES,
}


@dataclass(slots=True)
class PageNumberPhaseRule:
    phase_id: str
    selectors: tuple[str, ...]
    matched_section_types: frozenset[str]
    visible: bool
    number_format: str
    start_mode: str
    start_value: int


@dataclass(slots=True)
class LogicalSectionBoundary:
    start_index: int
    section_type: str
    phase_id: str | None
    reasons: tuple[str, ...] = ()

    @property
    def requires_section_break(self) -> bool:
        return self.start_index > 0


@dataclass(slots=True)
class PageNumberSectionPlan:
    section_index: int
    start_index: int
    section_type: str
    phase_id: str | None
    page_number_visible: bool
    number_format: str
    start_value: int | None
    hide_header_footer: bool


@dataclass(slots=True)
class PageNumberExecutionPlan:
    boundaries: list[LogicalSectionBoundary] = field(default_factory=list)
    sections: list[PageNumberSectionPlan] = field(default_factory=list)
    diagnostics: list["PageNumberDiagnostic"] = field(default_factory=list)
    missing_doc_tree: bool = False


@dataclass(slots=True)
class PageNumberDiagnostic:
    level: str
    message: str
    suggestion: str = ""
    location: str = ""


_SECTION_TYPE_LABELS: dict[str, str] = {
    "front_matter": "前置部分",
    "body": "正文部分",
    "back_matter": "后置部分",
    "cover": "封面",
    "pre_numbering": "页码前排除分区",
    "statement": "声明页",
    "authorization": "授权书",
    "front_note": "说明页",
    "toc": "目录",
    "references": "参考文献",
    "appendix": "附录",
    "acknowledgment": "致谢",
    "resume": "简历",
    "errata": "勘误",
    "abstract_cn": "中文摘要",
    "abstract_en": "英文摘要",
}


def build_page_number_execution_plan(
    doc: Document,
    context: PipelineContext,
    header_footer,
) -> PageNumberExecutionPlan:
    rules, diagnostics = _resolve_phase_rules(header_footer)
    suppressed_section_types = resolve_suppressed_header_footer_section_types(header_footer)
    missing_doc_tree = getattr(context, "doc_tree", None) is None
    boundaries = _collect_logical_boundaries(doc, context, rules)
    section_starts = _section_start_indices(doc)

    sections: list[PageNumberSectionPlan] = []
    previous_phase_id: str | None = None
    for section_index, start_index in enumerate(section_starts):
        section_type = _resolve_section_type(context, start_index)
        phase = _match_phase_rule(rules, section_type)
        hide_header_footer = section_type in suppressed_section_types
        phase_id = phase.phase_id if phase is not None else None
        page_number_visible = bool(header_footer.page_number_enabled) and not hide_header_footer
        number_format = "decimal"
        start_value: int | None = None

        if page_number_visible and phase is not None:
            page_number_visible = bool(phase.visible)
            number_format = phase.number_format
            if phase.phase_id != previous_phase_id and phase.start_mode == "restart":
                start_value = phase.start_value
        elif page_number_visible and phase is None:
            number_format = "decimal"

        sections.append(
            PageNumberSectionPlan(
                section_index=section_index,
                start_index=start_index,
                section_type=section_type,
                phase_id=phase_id,
                page_number_visible=page_number_visible,
                number_format=number_format,
                start_value=start_value,
                hide_header_footer=hide_header_footer,
            )
        )
        previous_phase_id = phase_id

    return PageNumberExecutionPlan(
        boundaries=boundaries,
        sections=sections,
        diagnostics=diagnostics + _collect_missing_phase_diagnostics(context, rules),
        missing_doc_tree=missing_doc_tree,
    )


def _resolve_phase_rules(
    header_footer,
) -> tuple[list[PageNumberPhaseRule], list[PageNumberDiagnostic]]:
    phases = list(getattr(getattr(header_footer, "page_number_plan", None), "phases", []) or [])
    if not phases:
        phases = default_continuous_page_number_phases()

    diagnostics: list[PageNumberDiagnostic] = []
    rules: list[PageNumberPhaseRule] = []
    claimed_by_section_type: dict[str, list[str]] = {}
    claimed_phase_ids: dict[str, int] = {}

    for index, phase in enumerate(phases):
        selectors = tuple(
            str(selector or "").strip()
            for selector in (getattr(phase, "selectors", None) or [])
            if str(selector or "").strip()
        )
        phase_id = str(getattr(phase, "phase_id", "") or "").strip() or f"phase_{index + 1}"
        claimed_phase_ids[phase_id] = claimed_phase_ids.get(phase_id, 0) + 1
        matched = expand_page_number_selectors(selectors)
        rule = PageNumberPhaseRule(
            phase_id=phase_id,
            selectors=selectors,
            matched_section_types=matched,
            visible=bool(getattr(phase, "visible", True)),
            number_format=_normalize_number_format(getattr(phase, "number_format", "decimal")),
            start_mode=_normalize_start_mode(getattr(phase, "start_mode", "continue")),
            start_value=max(1, int(getattr(phase, "start_value", 1) or 1)),
        )
        rules.append(rule)
        for section_type in matched:
            claimed_by_section_type.setdefault(section_type, []).append(phase_id)

    for section_type, phase_ids in claimed_by_section_type.items():
        if len(phase_ids) > 1:
            diagnostics.append(
                _build_phase_overlap_diagnostic(
                    section_type=section_type,
                    phase_ids=phase_ids,
                    level="error",
                    location="header_footer.page_number_plan",
                )
            )

    for phase_id, count in claimed_phase_ids.items():
        if count <= 1:
            continue
        diagnostics.append(
            PageNumberDiagnostic(
                level="error",
                message=f"页码结果名称“{phase_id}”重复出现。",
                suggestion="为每个页码结果使用唯一名称，便于诊断和维护。",
                location="header_footer.page_number_plan",
            )
        )

    return rules, diagnostics


def expand_page_number_selectors(selectors: Iterable[str]) -> frozenset[str]:
    matched: set[str] = set()
    for selector in selectors:
        canonical = canonicalize_section_type(selector)
        if canonical in _SELECTOR_SECTION_TYPES:
            matched.update(_SELECTOR_SECTION_TYPES[canonical])
        elif selector in _SELECTOR_SECTION_TYPES:
            matched.update(_SELECTOR_SECTION_TYPES[selector])
        elif canonical:
            matched.add(canonical)
    return frozenset(matched)


def resolve_suppressed_header_footer_section_types(header_footer) -> frozenset[str]:
    selectors_raw = getattr(header_footer, "suppress_header_footer_selectors", None)
    if selectors_raw is None:
        legacy_hide = bool(getattr(header_footer, "hide_cover_header_footer", True))
        selectors = ("cover",) if legacy_hide else ()
    else:
        selectors = tuple(
            str(selector or "").strip()
            for selector in selectors_raw
            if str(selector or "").strip()
        )
    return expand_page_number_selectors(selectors)


def collect_page_number_diagnostics(
    doc: Document,
    context: PipelineContext,
    header_footer,
) -> list[PageNumberDiagnostic]:
    page_number_enabled = bool(getattr(header_footer, "page_number_enabled", True))
    suppress_header_footer = bool(resolve_suppressed_header_footer_section_types(header_footer))
    if not page_number_enabled and not suppress_header_footer:
        return []

    plan = build_page_number_execution_plan(doc, context, header_footer)
    plan_cfg = getattr(header_footer, "page_number_plan", None)
    validation_mode = str(getattr(plan_cfg, "validation_mode", "strict") or "strict")
    on_missing_doc_tree = str(
        getattr(plan_cfg, "on_missing_doc_tree", "warn_and_fallback") or "warn_and_fallback"
    )

    diagnostics: list[PageNumberDiagnostic] = []
    if plan.missing_doc_tree and on_missing_doc_tree == "warn_and_fallback":
        message = "当前页码和分区排除规则依赖文档结构识别，但本次没有识别到文档结构。"
        suggestion = "先运行标题/结构识别，或把模板里的“无结构识别时”改成“直接使用默认规则”。"
        if not page_number_enabled and suppress_header_footer:
            message = "页眉页脚分区排除依赖文档结构识别，但本次没有识别到文档结构。"
            suggestion = "先运行标题/结构识别，或关闭“分区排除”。"
        diagnostics.append(
            PageNumberDiagnostic(
                level="warning",
                message=message,
                suggestion=suggestion,
                location="context.doc_tree",
            )
        )

    if not page_number_enabled:
        return diagnostics

    diagnostic_level = "error" if validation_mode == "strict" else "warning"
    for item in plan.diagnostics:
        diagnostics.append(
            PageNumberDiagnostic(
                level="error" if item.level == "error" else diagnostic_level,
                message=item.message,
                suggestion=item.suggestion,
                location=item.location or "header_footer.page_number_plan",
            )
        )

    return diagnostics


def collect_static_page_number_diagnostics(header_footer) -> list[PageNumberDiagnostic]:
    if not bool(getattr(header_footer, "page_number_enabled", True)):
        return []

    diagnostics: list[PageNumberDiagnostic] = []
    validation_mode = str(
        getattr(getattr(header_footer, "page_number_plan", None), "validation_mode", "strict") or "strict"
    )
    level = "error" if validation_mode == "strict" else "warning"
    location = "header_footer.page_number_plan"
    phases = list(getattr(getattr(header_footer, "page_number_plan", None), "phases", []) or [])
    if not phases:
        phases = default_continuous_page_number_phases()

    for index, phase in enumerate(phases, start=1):
        phase_id = str(getattr(phase, "phase_id", "") or "").strip() or f"phase_{index}"
        selectors = [
            str(selector or "").strip()
            for selector in (getattr(phase, "selectors", None) or [])
            if str(selector or "").strip()
        ]
        if not selectors:
            diagnostics.append(
                PageNumberDiagnostic(
                    level=level,
                    message=f"第 {index} 条页码结果尚未选择编号分区。",
                    suggestion="为这一项选择要编号的分区，或者直接删除这个空项。",
                    location=location,
                )
            )
            continue
        if not expand_page_number_selectors(selectors):
            diagnostics.append(
                PageNumberDiagnostic(
                    level=level,
                    message=f"规则“{phase_id}”的编号分区没有命中任何已知分区。",
                    suggestion="检查分区名称；如果这是自定义分区，请确认结构识别里确实会产出同名分区。",
                    location=location,
                )
            )

    rules, overlap_messages = _resolve_phase_rules(header_footer)
    diagnostics.extend(
        PageNumberDiagnostic(
            level="error" if item.level == "error" else level,
            message=item.message,
            suggestion=item.suggestion,
            location=item.location or location,
        )
        for item in overlap_messages
    )
    suppressed = resolve_suppressed_header_footer_section_types(header_footer)
    for rule in rules:
        hidden_matches = sorted(rule.matched_section_types & suppressed)
        if not hidden_matches:
            continue
        hidden_text = "、".join(_section_type_label(section_type) for section_type in hidden_matches)
        diagnostics.append(
            PageNumberDiagnostic(
                level="warning",
                message=f"规则“{rule.phase_id}”命中的分区已被设置为分区排除：{hidden_text}。",
                suggestion="这些分区不会输出页码；如需显示页码，请从排除分区中移除对应分区。",
                location=location,
            )
        )
    return diagnostics


def _collect_logical_boundaries(
    doc: Document,
    context: PipelineContext,
    rules: list[PageNumberPhaseRule],
) -> list[LogicalSectionBoundary]:
    doc_tree = getattr(context, "doc_tree", None)
    if doc_tree is None:
        return []

    section_boundary_starts: set[int] = set()
    body_heading_starts: set[int] = set()

    for section in getattr(doc_tree, "sections", []) or []:
        section_type = canonicalize_section_type(getattr(section, "section_type", ""))
        start_index = int(getattr(section, "start_index", -1))
        if section_type in BOUNDARY_SECTION_TYPES and start_index > 0:
            section_boundary_starts.add(start_index)

    body_section = getattr(doc_tree, "get_section", lambda *_: None)("body")
    body_start = int(getattr(body_section, "start_index", -1)) if body_section is not None else -1
    body_end = int(getattr(body_section, "end_index", len(doc.paragraphs))) if body_section is not None else len(doc.paragraphs)
    for para_index, level in (getattr(context, "heading_map", None) or {}).items():
        if level == 1 and body_start >= 0 and body_start < para_index < body_end:
            body_heading_starts.add(int(para_index))

    start_points = sorted(section_boundary_starts | body_heading_starts)
    boundaries: list[LogicalSectionBoundary] = []
    previous_phase_id: str | None = _match_phase_id(rules, _resolve_section_type(context, 0))

    for start_index in start_points:
        section_type = _resolve_section_type(context, start_index)
        phase_id = _match_phase_id(rules, section_type)
        reasons: list[str] = []
        if start_index in section_boundary_starts:
            reasons.append("section_start")
        if start_index in body_heading_starts:
            reasons.append("body_heading")
        if phase_id != previous_phase_id:
            reasons.append("phase_change")
        boundaries.append(
            LogicalSectionBoundary(
                start_index=start_index,
                section_type=section_type,
                phase_id=phase_id,
                reasons=tuple(reasons),
            )
        )
        previous_phase_id = phase_id

    return boundaries


def _collect_missing_phase_diagnostics(
    context: PipelineContext,
    rules: list[PageNumberPhaseRule],
) -> list[PageNumberDiagnostic]:
    doc_tree = getattr(context, "doc_tree", None)
    if doc_tree is None:
        return []

    diagnostics: list[PageNumberDiagnostic] = []
    seen_section_types: set[str] = set()
    for section in getattr(doc_tree, "sections", []) or []:
        section_type = canonicalize_section_type(getattr(section, "section_type", ""))
        if section_type in seen_section_types or section_type not in ALL_NUMBERED_SECTION_TYPES:
            continue
        seen_section_types.add(section_type)
        if _match_phase_rule(rules, section_type) is None:
            diagnostics.append(
                _build_uncovered_section_diagnostic(
                    section_type=section_type,
                    level="warning",
                    location="header_footer.page_number_plan",
                )
            )

    return diagnostics


def format_page_number_diagnostic_text(diagnostic: PageNumberDiagnostic) -> str:
    message = str(diagnostic.message or "").strip()
    suggestion = str(diagnostic.suggestion or "").strip()
    if not suggestion:
        return message
    return f"{message}\n建议：{suggestion}"


def _section_type_label(section_type: str) -> str:
    return _SECTION_TYPE_LABELS.get(section_type, section_type or "未知分区")


def _build_phase_overlap_diagnostic(
    *,
    section_type: str,
    phase_ids: list[str],
    level: str,
    location: str,
) -> PageNumberDiagnostic:
    section_label = _section_type_label(section_type)
    phase_text = "、".join(str(phase_id or "").strip() for phase_id in phase_ids if str(phase_id or "").strip())
    return PageNumberDiagnostic(
        level=level,
        message=f"分区“{section_label}”同时命中了多个页码结果：{phase_text}。",
        suggestion="让同一分区只属于一个页码结果；如果只是想续号，请保留一项并把起号方式改为“延续前段”。",
        location=location,
    )


def _build_uncovered_section_diagnostic(
    *,
    section_type: str,
    level: str,
    location: str,
) -> PageNumberDiagnostic:
    section_label = _section_type_label(section_type)
    return PageNumberDiagnostic(
        level=level,
        message=f"可编号分区“{section_label}”没有对应页码结果。",
        suggestion="新增一项覆盖该分区的页码结果，或把它并入现有项。",
        location=location,
    )


def _resolve_section_type(context: PipelineContext, para_index: int) -> str:
    doc_tree = getattr(context, "doc_tree", None)
    if doc_tree is None:
        return "body"

    getter = getattr(doc_tree, "get_section_for_paragraph", None)
    try:
        section_type = getter(para_index) if callable(getter) else "body"
    except Exception:
        section_type = "body"
    return canonicalize_section_type(section_type)


def _section_start_indices(doc: Document) -> list[int]:
    from src.shared.engine.ooxml_ops import qn

    starts = [0]
    total = len(doc.paragraphs)
    for index, para in enumerate(doc.paragraphs):
        if index + 1 >= total:
            continue
        p_pr = para._element.find(qn("w:pPr"))
        if p_pr is None or p_pr.find(qn("w:sectPr")) is None:
            continue
        starts.append(index + 1)

    deduped: list[int] = []
    for start in starts:
        if start not in deduped:
            deduped.append(start)
    return deduped


def _match_phase_rule(
    rules: list[PageNumberPhaseRule],
    section_type: str,
) -> PageNumberPhaseRule | None:
    for rule in rules:
        if section_type in rule.matched_section_types:
            return rule
    return None


def _match_phase_id(rules: list[PageNumberPhaseRule], section_type: str) -> str | None:
    rule = _match_phase_rule(rules, section_type)
    return rule.phase_id if rule is not None else None


def _normalize_number_format(value) -> str:
    raw = str(value or "decimal")
    if raw in {"decimal", "upperRoman", "lowerRoman"}:
        return raw
    return "decimal"


def _normalize_start_mode(value) -> str:
    raw = str(value or "continue")
    if raw in {"continue", "restart"}:
        return raw
    return "continue"
