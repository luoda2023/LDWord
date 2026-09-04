"""Business invariants for AI-authored template payloads.

Structural dataclass validation proves that a payload is complete and typed.
This module proves that the few collection-shaped authoring fields still mean
something executable after the model has legitimately reordered or replaced
their contents.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from src.config.feature_configs import (
    PAGE_NUMBER_MISSING_DOC_TREE_POLICY_VALUES,
    PAGE_NUMBER_START_MODE_VALUES,
    PAGE_NUMBER_VALIDATION_MODE_VALUES,
    normalize_page_number_format_value,
)
from src.config.migration import normalize_page_scope_selectors


class TemplateAuthoringSemanticError(ValueError):
    """An authored payload is structurally valid but not executable."""


def validate_authored_template_semantics(
    result_template: Mapping[str, Any],
    *,
    baseline_template: Mapping[str, Any],
) -> None:
    """Validate collection semantics without relying on baseline list indexes."""

    heading_model = _mapping(result_template.get("heading_model"), "heading_model")
    _validate_text_set(
        heading_model.get("non_numbered_title_texts"),
        "heading_model.non_numbered_title_texts",
    )
    _validate_text_set(
        heading_model.get("non_numbered_prefixes"),
        "heading_model.non_numbered_prefixes",
    )

    header_footer = _mapping(result_template.get("header_footer"), "header_footer")
    for channel_name in ("header", "footer"):
        channel = _mapping(
            header_footer.get(channel_name),
            f"header_footer.{channel_name}",
        )
        _validate_selector_set(
            channel.get("hidden_selectors"),
            f"header_footer.{channel_name}.hidden_selectors",
            allow_empty=True,
        )

    numbering = _mapping(
        result_template.get("heading_numbering"),
        "heading_numbering",
    )
    chain_catalog = _mapping(
        numbering.get("chain_catalog"),
        "heading_numbering.chain_catalog",
    )
    for chain_id, chain_value in chain_catalog.items():
        chain = _mapping(
            chain_value,
            f"heading_numbering.chain_catalog.{chain_id}",
        )
        segments = _list(
            chain.get("segments"),
            f"heading_numbering.chain_catalog.{chain_id}.segments",
        )
        for index, raw_segment in enumerate(segments):
            segment = _mapping(
                raw_segment,
                f"heading_numbering.chain_catalog.{chain_id}.segments[{index}]",
            )
            segment_type = str(segment.get("type") or "").strip()
            if segment_type not in {"value", "literal"}:
                raise TemplateAuthoringSemanticError(
                    "编号链片段类型不受支持："
                    f"heading_numbering.chain_catalog.{chain_id}.segments[{index}].type"
                )

    baseline_header_footer = _mapping(
        baseline_template.get("header_footer"),
        "baseline.header_footer",
    )
    _validate_page_number_plan(
        _mapping(
            header_footer.get("page_number_plan"),
            "header_footer.page_number_plan",
        ),
        baseline_plan=_mapping(
            baseline_header_footer.get("page_number_plan"),
            "baseline.header_footer.page_number_plan",
        ),
    )


def _validate_page_number_plan(
    plan: Mapping[str, Any],
    *,
    baseline_plan: Mapping[str, Any],
) -> None:
    path = "header_footer.page_number_plan"
    alignment = str(plan.get("alignment") or "").strip()
    if alignment not in {"left", "center", "right"}:
        raise TemplateAuthoringSemanticError(f"{path}.alignment 不受支持：{alignment}")
    validation_mode = str(plan.get("validation_mode") or "").strip()
    if validation_mode not in PAGE_NUMBER_VALIDATION_MODE_VALUES:
        raise TemplateAuthoringSemanticError(
            f"{path}.validation_mode 不受支持：{validation_mode}"
        )
    missing_policy = str(plan.get("on_missing_doc_tree") or "").strip()
    if missing_policy not in PAGE_NUMBER_MISSING_DOC_TREE_POLICY_VALUES:
        raise TemplateAuthoringSemanticError(
            f"{path}.on_missing_doc_tree 不受支持：{missing_policy}"
        )
    if bool(plan.get("enabled")) and "{page}" not in str(plan.get("template") or ""):
        raise TemplateAuthoringSemanticError(
            f"{path}.template 必须包含 {{page}} 占位符"
        )

    for variant_name in ("first", "even"):
        variant = _mapping(plan.get(variant_name), f"{path}.{variant_name}")
        visibility = str(variant.get("visibility") or "").strip()
        if visibility not in {"inherit", "show", "hide"}:
            raise TemplateAuthoringSemanticError(
                f"{path}.{variant_name}.visibility 不受支持：{visibility}"
            )
        variant_alignment = str(variant.get("alignment") or "").strip()
        if variant_alignment not in {"inherit", "left", "center", "right"}:
            raise TemplateAuthoringSemanticError(
                f"{path}.{variant_name}.alignment 不受支持：{variant_alignment}"
            )

    phases = _list(plan.get("phases"), f"{path}.phases")
    if not phases:
        raise TemplateAuthoringSemanticError(f"{path}.phases 不能为空")

    phase_ids: set[str] = set()
    claimed_by_selector: dict[str, list[str]] = defaultdict(list)
    result_coverage: set[str] = set()
    for index, raw_phase in enumerate(phases):
        phase_path = f"{path}.phases[{index}]"
        phase = _mapping(raw_phase, phase_path)
        phase_id = str(phase.get("phase_id") or "").strip()
        if not phase_id:
            raise TemplateAuthoringSemanticError(f"{phase_path}.phase_id 不能为空")
        if phase_id in phase_ids:
            raise TemplateAuthoringSemanticError(f"页码编号分组名称重复：{phase_id}")
        phase_ids.add(phase_id)

        number_format = str(phase.get("number_format") or "").strip()
        if not normalize_page_number_format_value(number_format):
            raise TemplateAuthoringSemanticError(
                f"{phase_path}.number_format 不受支持：{number_format}"
            )
        start_mode = str(phase.get("start_mode") or "").strip()
        if start_mode not in PAGE_NUMBER_START_MODE_VALUES:
            raise TemplateAuthoringSemanticError(
                f"{phase_path}.start_mode 不受支持：{start_mode}"
            )
        start_value = phase.get("start_value")
        if type(start_value) is not int or start_value < 1:
            raise TemplateAuthoringSemanticError(
                f"{phase_path}.start_value 必须是大于等于 1 的整数"
            )

        selectors = _validate_selector_set(
            phase.get("selectors"),
            f"{phase_path}.selectors",
            allow_empty=False,
        )
        for selector in selectors:
            claimed_by_selector[selector].append(phase_id)
        result_coverage.update(selectors)

    overlaps = {
        selector: owners
        for selector, owners in claimed_by_selector.items()
        if len(owners) > 1
    }
    if overlaps:
        selector, owners = next(iter(overlaps.items()))
        raise TemplateAuthoringSemanticError(
            f"页码范围 {selector} 同时属于多个编号分组：{'、'.join(owners)}"
        )

    baseline_coverage: set[str] = set()
    for index, raw_phase in enumerate(
        _list(baseline_plan.get("phases"), "baseline.header_footer.page_number_plan.phases")
    ):
        phase = _mapping(
            raw_phase,
            f"baseline.header_footer.page_number_plan.phases[{index}]",
        )
        baseline_coverage.update(
            _expanded_selectors(
                phase.get("selectors"),
                f"baseline.header_footer.page_number_plan.phases[{index}].selectors",
            )
        )
    missing = sorted(baseline_coverage - result_coverage)
    if missing:
        raise TemplateAuthoringSemanticError(
            "页码计划丢失基准覆盖范围：" + "、".join(missing)
        )


def _validate_text_set(value: Any, path: str) -> tuple[str, ...]:
    items = _list(value, path)
    normalized = tuple(str(item).strip() for item in items)
    if any(not item for item in normalized):
        raise TemplateAuthoringSemanticError(f"{path} 不能包含空文本")
    if len(normalized) != len(set(normalized)):
        raise TemplateAuthoringSemanticError(f"{path} 不能包含重复文本")
    return normalized


def _validate_selector_set(
    value: Any,
    path: str,
    *,
    allow_empty: bool,
) -> tuple[str, ...]:
    expanded = _expanded_selectors(value, path)
    if not expanded and not allow_empty:
        raise TemplateAuthoringSemanticError(f"{path} 不能为空")
    if len(expanded) != len(set(expanded)):
        raise TemplateAuthoringSemanticError(f"{path} 包含重复或重叠范围")
    return expanded


def _expanded_selectors(value: Any, path: str) -> tuple[str, ...]:
    items = _list(value, path)
    expanded: list[str] = []
    for index, raw_selector in enumerate(items):
        selector = str(raw_selector or "").strip()
        normalized = normalize_page_scope_selectors([selector])
        if not selector or not normalized:
            raise TemplateAuthoringSemanticError(
                f"{path}[{index}] 不是可执行的页面范围：{selector or '<empty>'}"
            )
        expanded.extend(normalized)
    return tuple(expanded)


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TemplateAuthoringSemanticError(f"{path} 必须是对象")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise TemplateAuthoringSemanticError(f"{path} 必须是数组")
    return value


__all__ = [
    "TemplateAuthoringSemanticError",
    "validate_authored_template_semantics",
]
