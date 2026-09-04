from __future__ import annotations

from src.config.plugin_manual_gate import plugin_manual_gate_for_pack
from src.config.scene_coverage_manifest import (
    SceneCoveragePack,
    coverage_packs_for_family,
    coverage_packs_for_scene,
    get_scene_coverage_pack,
)
from src.config.scene_sample_fixture_registry import (
    SceneSampleFixtureAuditIssue,
    audit_scene_sample_fixtures,
    get_scene_sample_fixture,
    scene_sample_fixtures_for_pack,
)
from src.ui.adapters.workbench_issue_models import WorkbenchIssueItem


def coverage_boundary_issue_items(scene) -> list[WorkbenchIssueItem]:
    """Return non-blocking Workbench issues for manifest boundary warnings."""

    items: list[WorkbenchIssueItem] = []
    for pack in _coverage_packs_for_scene_context(scene):
        is_contract_legal_boundary = pack.pack_id == "contract_delivery"
        if not pack.plugin_boundary and not is_contract_legal_boundary:
            continue
        gate = plugin_manual_gate_for_pack(pack.pack_id)
        category = "plugin_boundary" if pack.plugin_boundary else "coverage_boundary"
        title = "插件/专业边界" if pack.plugin_boundary else "法律/交付边界"
        target_type = "plugin_manual_gate" if gate is not None else "coverage_boundary"
        items.append(
            WorkbenchIssueItem(
                issue_id=f"coverage.{pack.pack_id}.{category}",
                category=category,
                severity="warning",
                title=title,
                summary=f"{pack.label}: {pack.boundary}",
                details=_coverage_boundary_details(pack),
                source_notes=(f"coverage pack：{pack.pack_id}",),
                repair_target_type=target_type,
                repair_target_key=gate.gate_id if gate is not None else pack.pack_id,
                blocking=False,
                owner="plugin" if pack.plugin_boundary else "scene",
            )
        )
    return items


def sample_fixture_issue_items(
    scene,
    audit: (
        tuple[SceneSampleFixtureAuditIssue, ...]
        | list[SceneSampleFixtureAuditIssue]
        | None
    ) = None,
) -> list[WorkbenchIssueItem]:
    """Return Workbench issues for scene sample coverage audit gaps."""

    packs = _coverage_packs_for_scene_context(scene)
    if not packs:
        return []
    pack_ids = tuple(pack.pack_id for pack in packs)
    audit_issues = tuple(audit) if audit is not None else audit_scene_sample_fixtures()
    items: list[WorkbenchIssueItem] = []

    for pack_id in pack_ids:
        if scene_sample_fixtures_for_pack(pack_id):
            continue
        items.append(
            _sample_fixture_issue(
                pack_id=pack_id,
                issue=SceneSampleFixtureAuditIssue(
                    fixture_id=pack_id,
                    kind="missing_required_pack_fixture",
                    message=f"Required pack '{pack_id}' has no DOCX sample fixture.",
                ),
            )
        )

    for issue in audit_issues:
        target_pack_id = _sample_fixture_issue_pack_id(issue, pack_ids)
        if not target_pack_id:
            continue
        issue_key = f"{target_pack_id}.{issue.kind}.{issue.fixture_id}"
        duplicate_issue_id = f"sample_fixture.{_issue_token(issue_key)}"
        if any(item.issue_id == duplicate_issue_id for item in items):
            continue
        items.append(_sample_fixture_issue(pack_id=target_pack_id, issue=issue))
    return items


def _coverage_packs_for_scene_context(scene) -> tuple[SceneCoveragePack, ...]:
    keys = _unique_texts(
        [
            str(getattr(scene, "scene_id", "") or ""),
            str(getattr(scene, "category", "") or ""),
        ]
    )
    packs: list[SceneCoveragePack] = []
    for key in keys:
        try:
            packs.append(get_scene_coverage_pack(key))
        except KeyError:
            pass
        packs.extend(coverage_packs_for_scene(key))
        packs.extend(coverage_packs_for_family(key))
    return tuple(_dedupe_coverage_packs(packs))


def _dedupe_coverage_packs(packs: list[SceneCoveragePack]) -> list[SceneCoveragePack]:
    result: list[SceneCoveragePack] = []
    seen: set[str] = set()
    for pack in packs:
        if pack.pack_id in seen:
            continue
        seen.add(pack.pack_id)
        result.append(pack)
    return result


def _coverage_boundary_details(pack: SceneCoveragePack) -> tuple[str, ...]:
    details: list[str] = []
    primary = ", ".join(pack.primary_landings)
    secondary = ", ".join(pack.secondary_landings)
    axes = ", ".join(pack.capability_axis_ids)
    if primary:
        details.append("首选承载：" + primary)
    if secondary:
        details.append("次级承载：" + secondary)
    if axes:
        details.append("能力轴：" + axes)
    gate = plugin_manual_gate_for_pack(pack.pack_id)
    if gate is not None:
        details.append("插件入口：" + gate.plugin_entry_id)
        details.append(
            "人工确认："
            + ("required" if gate.manual_confirmation_required else "optional")
        )
        details.append(
            "置信度报告："
            + ("required" if gate.confidence_report_required else "optional")
        )
        if gate.risk_domain_ids:
            details.append("风险域：" + ", ".join(gate.risk_domain_ids))
        if gate.confirmation_decision_states:
            details.append("确认状态：" + ", ".join(gate.confirmation_decision_states))
        if gate.unsupported_core_inputs:
            details.append("核心不直接承诺：" + ", ".join(gate.unsupported_core_inputs))
    if pack.closure_tasks:
        for task in list(pack.closure_tasks)[:3]:
            details.append(
                f"未闭合[{task.priority}/{task.owner}/{task.target_phase}]："
                f"{task.summary}"
            )
    else:
        for closure in list(pack.missing_closures or ())[:3]:
            details.append("未闭合：" + closure)
    details.append("执行策略：核心只做排版/资料/交付闭环，专业判断或生成质量需插件或人工确认")
    return tuple(details)


def _sample_fixture_issue(
    *,
    pack_id: str,
    issue: SceneSampleFixtureAuditIssue,
) -> WorkbenchIssueItem:
    issue_key = f"{pack_id}.{issue.kind}.{issue.fixture_id}"
    details = [
        "覆盖 pack：" + pack_id,
        "缺口类型：" + issue.kind,
        issue.message,
    ]
    if issue.fixture_id and issue.fixture_id != pack_id:
        details.append("样本/对象：" + issue.fixture_id)
    return WorkbenchIssueItem(
        issue_id=f"sample_fixture.{_issue_token(issue_key)}",
        category="sample_fixture",
        severity=issue.severity or "warning",
        title="样本覆盖缺口",
        summary=f"{pack_id}: {issue.kind}",
        details=tuple(details),
        source_notes=("scene_sample_fixture_registry",),
        repair_target_type="sample_fixture",
        repair_target_key=pack_id,
        blocking=False,
        owner="scene",
    )


def _sample_fixture_issue_pack_id(
    issue: SceneSampleFixtureAuditIssue,
    pack_ids: tuple[str, ...],
) -> str:
    fixture_or_pack = str(getattr(issue, "fixture_id", "") or "").strip()
    if fixture_or_pack in pack_ids:
        return fixture_or_pack
    try:
        fixture = get_scene_sample_fixture(fixture_or_pack)
    except KeyError:
        if str(getattr(issue, "kind", "") or "").strip() == "missing_required_surface":
            return pack_ids[0] if pack_ids else ""
        return ""
    return fixture.pack_id if fixture.pack_id in pack_ids else ""


def _unique_texts(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _issue_token(value: str) -> str:
    token = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_"
        for char in str(value or "").strip().lower()
    ).strip("_")
    return token or "item"
