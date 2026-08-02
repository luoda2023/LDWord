import json

from src.ui.adapters.workbench_execution_adapter import (
    WorkbenchExecutionAdapter,
    output_target_preflight_issue_items,
    question_figure_transaction_task_issue_items,
)
from src.ui.adapters.workbench_product_issue_navigation import (
    workbench_issue_navigation_for_target,
)
from src.ui.panels.workbench.quick_execution_result_presenter import (
    build_execution_result_presentation,
)


def _delivery_terminal_payload() -> dict[str, object]:
    return {
        "status": "success",
        "output_path": "delivery/source_review.docx",
        "output_paths": {"review": "delivery/source_review.docx"},
        "compare_paths": {"review": "delivery/source_review_compare.docx"},
        "report_paths": ["delivery/source_review_changes.md"],
        "intermediate_paths": {
            "review": "delivery/source_review_intermediate.json"
        },
        "material_manifest_paths": {
            "material": "delivery/material_manifest.json"
        },
        "material_package_paths": {
            "zip": "delivery/material_package.zip",
            "report": "delivery/material_package_report.md",
        },
        "scene_sample_manifest_paths": {
            "manifest": "delivery/scene_sample_manifest.json"
        },
        "failed_count": 0,
        "error_text": "",
    }


def test_v1_execution_adapter_projects_delivery_artifacts_and_report_groups():
    state = WorkbenchExecutionAdapter().build_result_state(
        terminal_payload=_delivery_terminal_payload()
    )

    by_path = {item.path: item for item in state.artifact_items}
    assert by_path["delivery/source_review.docx"].kind == "output"
    assert by_path["delivery/source_review_compare.docx"].kind == "compare"
    assert by_path["delivery/source_review_changes.md"].kind == "report"
    assert by_path["delivery/source_review_changes.md"].group_id == "review"
    assert by_path["delivery/source_review_intermediate.json"].kind == (
        "intermediate"
    )
    assert by_path["delivery/material_manifest.json"].kind == "material_manifest"
    assert by_path["delivery/material_package.zip"].kind == "material_package"
    assert by_path["delivery/material_package_report.md"].kind == (
        "material_package_report"
    )
    assert by_path["delivery/scene_sample_manifest.json"].kind == (
        "scene_sample_manifest"
    )


def test_v1_quick_result_log_lists_delivery_artifacts():
    state = WorkbenchExecutionAdapter().build_result_state(
        terminal_payload=_delivery_terminal_payload()
    )

    presentation = build_execution_result_presentation(state)
    messages = [entry.message for entry in presentation.log_entries]

    assert any("delivery/source_review.docx" in message for message in messages)
    assert any("delivery/source_review_changes.md" in message for message in messages)
    assert any("delivery/material_package.zip" in message for message in messages)


def test_v1_output_target_issue_preserves_repair_route():
    items = output_target_preflight_issue_items(
        {
            "items": [
                {
                    "preset_id": "review",
                    "display_label": "Review",
                    "path": "delivery/source_review.docx",
                    "issues": [{"message": "Review: destination already exists"}],
                }
            ]
        }
    )

    assert len(items) == 1
    assert items[0].repair_target_type == "output_target"
    assert items[0].repair_target_key == "review"
    assert items[0].details == ("destination already exists",)

    navigation = workbench_issue_navigation_for_target(
        items[0].repair_target_type,
        items[0].repair_target_key,
    )
    assert (navigation.action_kind, navigation.panel_id, navigation.card_id) == (
        "scene_panel",
        "scene",
        "scn_rules",
    )


def test_v1_question_figure_transaction_task_routes_to_report_artifact():
    report_path = "delivery/question_figure_transaction_report.md"
    artifact_path = "delivery/question_figure_transaction_manifest.json"
    items = question_figure_transaction_task_issue_items(
        {
            "batch_apply_transaction_manifest": {
                "artifact_path": artifact_path,
                "report_path": report_path,
                "task_summary": {
                    "status": "active",
                    "next_action": "rollback",
                    "report_path": report_path,
                    "transaction_count": 1,
                    "active_count": 1,
                    "rollback_available_count": 1,
                    "active_transaction_ids": ["tx-1"],
                    "rollback_available_transaction_ids": ["tx-1"],
                    "latest_transaction_id": "tx-1",
                    "latest_transaction_status": "applied",
                },
            }
        }
    )

    assert len(items) == 1
    issue = items[0]
    assert issue.repair_target_type == (
        "question_figure_batch_apply_transaction_task_summary"
    )
    action_payload = json.loads(issue.repair_target_key)
    assert action_payload["report_path"] == report_path
    assert action_payload["artifact_path"] == artifact_path
    assert action_payload["fragment"] == (
        "question-figure-batch-apply-transaction-task-summary"
    )

    navigation = workbench_issue_navigation_for_target(
        issue.repair_target_type,
        issue.repair_target_key,
    )
    assert navigation.action_kind == "transaction_artifact"
    assert navigation.feature_card_id == "quick_execute"
