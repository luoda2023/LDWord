from src.config.entity import EntityArchive, EntityProfile
import pytest

from src.config.material_batch import MaterialBatchSelection
from src.config.material_context import MaterialExecutionContext
from src.config.scene import SceneWorkspace
from src.ui.adapters.workbench_execution_gate import (
    ExecutionGateAction,
    decide_execution_gate,
    decide_execution_gate_for_policy,
    execution_gate_decision_from_issues,
    normalize_execution_failure_policy,
)
from src.ui.adapters.workbench_issue_models import WorkbenchIssueItem
from src.ui.adapters.workbench_material_issues import (
    material_batch_readiness_gate_decision,
    material_readiness_gate_decision,
    material_readiness_issue_items,
)
from src.services.production_runtime.material_preflight import material_failure_policy


def _scene_with_missing_exam_metadata(*, failure_policy: str) -> SceneWorkspace:
    scene = SceneWorkspace(scene_id="exam")
    scene.input_source_profile.material_schema_id = "exam_items_v1"
    scene.input_source_profile.failure_policy = failure_policy
    return scene


def test_execution_gate_warn_policy_allows_run():
    action = ExecutionGateAction("补充资料", "field", "paper_title")

    decision = decide_execution_gate_for_policy(
        ["资料字段缺失", " 资料字段缺失 "],
        failure_policy="warn",
        primary_action=action,
    )

    assert decision.can_run is True
    assert decision.ready_to_start is True
    assert decision.requires_confirmation is False
    assert decision.blocking_reasons == ()
    assert decision.warning_reasons == ("资料字段缺失",)
    assert decision.confirmation_reasons == ()
    assert decision.primary_action is action
    assert decision.state == "warning"


def test_execution_gate_block_policy_prevents_run():
    decision = decide_execution_gate_for_policy(
        ["缺少必需资料"],
        failure_policy="block",
    )

    assert decision.can_run is False
    assert decision.ready_to_start is False
    assert decision.requires_confirmation is False
    assert decision.blocking_reasons == ("缺少必需资料",)
    assert decision.warning_reasons == ()
    assert decision.state == "blocked"


def test_execution_gate_confirmation_requires_explicit_confirmation():
    decision = decide_execution_gate_for_policy(
        ["检测到批注，继续前请确认"],
        failure_policy="confirm",
    )

    assert decision.can_run is True
    assert decision.ready_to_start is False
    assert decision.requires_confirmation is True
    assert decision.confirmation_reasons == ("检测到批注，继续前请确认",)
    assert decision.state == "confirmation"


def test_execution_gate_blocker_dominates_confirmation():
    decision = decide_execution_gate(
        blocking_reasons=["输出目录不可写"],
        confirmation_reasons=["检测到批注"],
    )

    assert decision.can_run is False
    assert decision.requires_confirmation is False
    assert decision.blocking_reasons == ("输出目录不可写",)
    assert decision.confirmation_reasons == ("检测到批注",)
    assert decision.state == "blocked"


def test_execution_gate_from_issues_ignores_terminal_status_and_opts_into_confirmation():
    items = [
        WorkbenchIssueItem(
            issue_id="material.warning",
            category="material",
            severity="warning",
            title="资料信息不完整",
            summary="部分信息将留空",
        ),
        WorkbenchIssueItem(
            issue_id="object.confirm",
            category="object_preflight",
            severity="warning",
            title="检测到对象风险",
            summary="继续前请确认",
        ),
        WorkbenchIssueItem(
            issue_id="resolved.blocker",
            category="output",
            severity="error",
            title="旧阻断",
            summary="已解决",
            blocking=True,
            status="resolved",
        ),
    ]

    decision = execution_gate_decision_from_issues(
        items,
        confirmation_issue_ids=["object.confirm"],
    )

    assert decision.can_run is True
    assert decision.requires_confirmation is True
    assert decision.warning_reasons == ("资料信息不完整：部分信息将留空",)
    assert decision.confirmation_reasons == ("检测到对象风险：继续前请确认",)
    assert decision.blocking_reasons == ()


def test_material_readiness_gate_matches_warn_issue_contract():
    scene = _scene_with_missing_exam_metadata(failure_policy="warn")

    decision = material_readiness_gate_decision(scene, MaterialExecutionContext())
    items = material_readiness_issue_items(scene, MaterialExecutionContext())

    assert decision.can_run is True
    assert decision.state == "warning"
    assert decision.blocking_reasons == ()
    assert decision.warning_reasons
    assert decision.primary_action == ExecutionGateAction(
        "补充资料",
        "field",
        "paper_title",
    )
    assert items
    assert all(item.blocking is False for item in items)
    assert all(item.severity == "warning" for item in items)


def test_material_readiness_gate_matches_block_issue_contract():
    scene = _scene_with_missing_exam_metadata(failure_policy="block")

    decision = material_readiness_gate_decision(scene, MaterialExecutionContext())
    items = material_readiness_issue_items(scene, MaterialExecutionContext())

    assert decision.can_run is False
    assert decision.state == "blocked"
    assert decision.blocking_reasons
    assert decision.warning_reasons == ()
    assert items
    assert all(item.blocking is True for item in items)
    assert all(item.severity == "error" for item in items)


def test_material_batch_gate_checks_every_selected_profile_context():
    scene = SceneWorkspace(scene_id="official")
    scene.input_source_profile.failure_policy = "block"
    scene.input_source_profile.required_material_fields = ["title"]
    selection = MaterialBatchSelection(
        archive=EntityArchive(
            profiles=[
                EntityProfile(
                    profile_id="ready",
                    profile_name="Ready",
                    fields={"title": "已填写"},
                ),
                EntityProfile(
                    profile_id="missing",
                    profile_name="Missing",
                ),
            ]
        ),
        profile_ids=["ready", "missing"],
        source_kind="official_document_table",
    )

    decision = material_batch_readiness_gate_decision(scene, selection)

    assert decision.can_run is False
    assert decision.state == "blocked"
    assert any(reason.startswith("Missing：") for reason in decision.blocking_reasons)
    assert all(not reason.startswith("Ready：") for reason in decision.blocking_reasons)


def test_material_failure_policy_rejects_noncanonical_values_fail_closed():
    scene = SceneWorkspace()
    scene.input_source_profile.failure_policy = "block"

    assert normalize_execution_failure_policy("block") == "block"
    assert material_failure_policy(scene) == "block"

    scene.input_source_profile.failure_policy = "unsupported-policy"

    with pytest.raises(
        ValueError,
        match="execution_failure_policy_invalid:unsupported-policy",
    ):
        normalize_execution_failure_policy("unsupported-policy")
    assert material_failure_policy(scene) == "block"

    decision = decide_execution_gate_for_policy(
        [],
        failure_policy="unsupported-policy",
    )
    assert decision.can_run is False
    assert decision.state == "blocked"
    assert decision.blocking_reasons == (
        "execution_failure_policy_invalid:unsupported-policy",
    )
