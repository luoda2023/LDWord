"""Engineering-only scene evidence summaries.

These projections support source-tree audits and tests. They are intentionally
kept out of the customer-facing scene summary and the static product import
graph.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from src.config.control_contract_registry import (
    ALLOWED_CONTROL_OWNER_LAYERS,
    ControlContractAuditResult,
    audit_control_contract_registry,
    list_control_contracts,
)
from src.config.scene import SceneWorkspace
from src.config.scene_coverage_manifest import (
    SceneCoveragePack,
    coverage_candidate_keys_for_config,
    coverage_packs_for_config,
)
from src.config.scene_parameter_ownership import (
    ALLOWED_PARAMETER_OWNER_LAYERS,
    ParameterOwnershipAuditResult,
    audit_scene_parameter_ownership,
    scene_parameter_ownership_specs,
)
from src.config.scene_product_readiness import (
    SceneProductReadinessSpec,
    product_readiness_for,
)
from src.config.scene_request_cell_fixture_registry import (
    build_scene_request_cell_fixture_summary,
)
from src.config.scene_sample_fixture_registry import (
    build_scene_sample_coverage_summary,
)


def build_scene_parameter_ownership_summary(scene: SceneWorkspace) -> str:
    audit = audit_scene_parameter_ownership(scene.__class__)
    status = "已守门" if audit.is_clean else f"{_ownership_issue_count(audit)}个缺口"
    return f"参数归属{status}（{_ownership_layer_compact_text()}）"


def build_scene_control_contract_summary() -> str:
    audit = audit_control_contract_registry()
    status = (
        "已守门"
        if audit.is_clean
        else f"{_control_contract_issue_count(audit)}个缺口"
    )
    return f"控件契约{status}（{_control_contract_layer_compact_text()}）"


def build_scene_sample_coverage_summary_text(scene: SceneWorkspace) -> str:
    packs = _coverage_packs_for_scene_context(scene)
    if not packs:
        return "样本覆盖未归属"
    summary = build_scene_sample_coverage_summary([pack.pack_id for pack in packs])
    issue_count = len(summary.missing_pack_ids) + len(summary.audit_issues)
    status = "已守门" if summary.is_clean else f"{issue_count}个缺口"
    manual = (
        f"/{len(summary.manual_gate_ids)}人工确认"
        if summary.manual_gate_ids
        else ""
    )
    return (
        f"样本覆盖{status}（"
        f"{len(summary.fixture_ids)}样本/"
        f"{len(summary.docx_surfaces)}类OOXML{manual}"
        "）"
    )


def build_scene_request_cell_summary_text(scene: SceneWorkspace) -> str:
    packs = _coverage_packs_for_scene_context(scene)
    if not packs:
        return "常见说法未归属"
    summary = build_scene_request_cell_fixture_summary(
        [pack.pack_id for pack in packs]
    )
    issue_count = len(summary.audit_issues)
    release_clean = (
        summary.is_clean
        and summary.family_proxy_count == 0
        and (
            summary.fixture_cell_count + summary.negative_control_count
            == summary.cell_count
        )
    )
    status = "已守门" if release_clean else f"{issue_count}个缺口"
    boundary = ""
    if summary.manual_boundary_count or summary.ambiguous_count:
        boundary = (
            f"/{summary.manual_boundary_count}人工确认"
            f"/{summary.ambiguous_count}容易误解"
        )
    return (
        f"常见说法{status}（"
        f"{summary.cell_count}请求/"
        f"{summary.fixture_cell_count}证据/"
        f"{summary.family_proxy_count}借用{boundary}"
        "）"
    )


def build_scene_product_readiness_summary(scene: SceneWorkspace) -> str:
    specs = _product_readiness_specs_for_scene_context(scene)
    if not specs:
        return "产品成熟度未登记"
    levels = _unique_summary_values(
        [
            spec.product_readiness_level
            for spec in specs
            if spec.product_readiness_level
        ]
    )
    level_text = "/".join(_product_readiness_label(level) for level in levels)
    static_closed = sum(
        1 for spec in specs if spec.static_closure_level == "closed"
    )
    non_green = sum(1 for spec in specs if not spec.is_green)
    gap_count = sum(len(spec.remaining_product_gaps) for spec in specs)
    return (
        f"产品成熟度{level_text}"
        f"（static闭合{static_closed}/非Green{non_green}/缺口{gap_count}）"
    )


def _control_contract_layer_compact_text() -> str:
    counts = Counter(contract.owner_layer for contract in list_control_contracts())
    layers = [
        layer
        for layer in ALLOWED_CONTROL_OWNER_LAYERS
        if counts.get(layer, 0)
    ]
    return "/".join(layers) if layers else "未登记"


def _control_contract_issue_count(audit: ControlContractAuditResult) -> int:
    return (
        len(audit.missing_required_contracts)
        + len(audit.invalid_owner_layers)
        + len(audit.missing_paired_contracts)
        + len(audit.missing_evidence_files)
        + len(audit.missing_evidence_markers)
    )


def _ownership_layer_compact_text() -> str:
    counts = Counter(
        spec.owner_layer for spec in scene_parameter_ownership_specs().values()
    )
    layers = [
        layer
        for layer in ALLOWED_PARAMETER_OWNER_LAYERS
        if counts.get(layer, 0)
    ]
    return "/".join(layers) if layers else "未登记"


def _ownership_issue_count(audit: ParameterOwnershipAuditResult) -> int:
    return (
        len(audit.missing_top_level_paths)
        + len(audit.missing_required_paths)
        + len(audit.unknown_spec_paths)
        + len(audit.invalid_owner_layers)
    )


def _coverage_packs_for_scene_context(
    scene: SceneWorkspace,
) -> tuple[SceneCoveragePack, ...]:
    return coverage_packs_for_config(scene)


def _product_readiness_specs_for_scene_context(
    scene: SceneWorkspace,
) -> tuple[SceneProductReadinessSpec, ...]:
    specs: list[SceneProductReadinessSpec] = []
    seen: set[tuple[str, str]] = set()
    for pack in _coverage_packs_for_scene_context(scene):
        _append_product_readiness_spec(specs, seen, "pack", pack.pack_id)
    for candidate in coverage_candidate_keys_for_config(scene):
        _append_product_readiness_spec(specs, seen, "family", candidate)
    return tuple(specs)


def _append_product_readiness_spec(
    specs: list[SceneProductReadinessSpec],
    seen: set[tuple[str, str]],
    subject_type: str,
    subject_id: str,
) -> None:
    normalized = str(subject_id or "").strip()
    if not normalized:
        return
    key = (subject_type, normalized)
    if key in seen:
        return
    try:
        spec = product_readiness_for(normalized, subject_type=subject_type)
    except KeyError:
        return
    specs.append(spec)
    seen.add(key)


def _product_readiness_label(level: str) -> str:
    return {
        "gray_l1": "Gray/L1",
        "blue_boundary": "Blue/Boundary",
        "yellow_l3": "Yellow/L3",
        "orange_l4": "Orange/L4",
        "green_l5": "Green/L5",
    }.get(str(level or "").strip(), str(level or "").strip() or "未登记")


def _unique_summary_values(values: Sequence[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "build_scene_control_contract_summary",
    "build_scene_parameter_ownership_summary",
    "build_scene_product_readiness_summary",
    "build_scene_request_cell_summary_text",
    "build_scene_sample_coverage_summary_text",
]
