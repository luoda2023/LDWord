import ast
import json
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.services.production_runtime.question_figure_repair_runtime import (
    build_batch_question_figure_comparison_matrix,
    build_batch_question_figure_repair_queue,
)


def test_question_figure_runtime_exposes_only_production_projection_roots():
    runtime_path = (
        ROOT / "src/services/production_runtime/question_figure_repair_runtime.py"
    )
    runtime_tree = ast.parse(runtime_path.read_text(encoding="utf-8"))
    runtime_surface = {
        node.name
        for node in runtime_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    runtime_surface.update(
        alias.asname or alias.name
        for node in runtime_tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    )
    speculative_execution_surface = {
        "_freeze_question_figure_repair_batch_confirmation_plan",
        "_dry_run_question_figure_repair_batch_apply_guard",
        "_plan_question_figure_repair_batch_apply_execution",
        "_question_figure_repair_batch_apply_execution_plan_fingerprint",
        "_apply_question_figure_repair_batch_execution_to_docx",
        "_question_figure_batch_apply_audit_record",
        "_append_question_figure_batch_apply_audit_record",
        "_read_question_figure_batch_apply_audit_payload",
        "_question_figure_batch_apply_transaction_manifest_from_audit",
        "_question_figure_batch_apply_transaction_task_summary",
        "_write_question_figure_batch_apply_transaction_manifest",
        "_question_figure_batch_apply_transaction_manifest_markdown",
        "_rollback_question_figure_repair_batch_apply_from_audit",
        "_question_figure_batch_apply_rollback_audit_record",
        "_batch_apply_audit_output_dir",
        "_question_figure_repair_target_payload",
        "_file_sha1",
        "_resolve_question_figure_repair_queue_conflict",
    }
    assert runtime_surface.isdisjoint(speculative_execution_surface)

    consumer_path = ROOT / "src/services/production_runtime/batch_reporting.py"
    consumer_tree = ast.parse(consumer_path.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name
        for node in consumer_tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "question_figure_repair_runtime"
        for alias in node.names
    }
    assert imported_roots == {
        "build_batch_question_figure_comparison_matrix",
        "build_batch_question_figure_repair_queue",
    }


def test_question_figure_comparison_matrix_projects_production_report_shape():
    matrix = build_batch_question_figure_comparison_matrix(
        [
            {
                "profile_id": "exam_a",
                "profile_name": "Exam A",
                "repair_target_type": "question_figure_item",
                "repair_target_key": "target-a",
                "comparison_issue_items": [
                    {
                        "item_id": "figure-10",
                        "question_index": "10",
                        "comparison_issue_summary": "Question 10 differs",
                    },
                    {
                        "item_id": "figure-2",
                        "question_index": "2",
                        "comparison_issue_summary": "Question 2 differs",
                    },
                ],
            }
        ]
    )

    assert matrix["kind"] == "question_figure_comparison_matrix"
    assert matrix["total_issue_count"] == 2
    assert matrix["profile_count"] == 1
    assert matrix["question_count"] == 2
    assert matrix["profiles"][0]["profile_id"] == "exam_a"
    assert [
        question["question_index"]
        for question in matrix["profiles"][0]["questions"]
    ] == ["2", "10"]
    assert [question["question_index"] for question in matrix["questions"]] == [
        "2",
        "10",
    ]


def test_question_figure_repair_queue_blocks_conflicting_ready_candidates(tmp_path):
    current = tmp_path / "question_2.png"
    replacement_a = tmp_path / "question_2_expected_a.png"
    replacement_b = tmp_path / "question_2_expected_b.png"
    Image.new("RGB", (320, 240), color="blue").save(current)
    Image.new("RGB", (320, 240), color="yellow").save(replacement_a)
    Image.new("RGB", (320, 240), color="red").save(replacement_b)
    target_key = json.dumps(
        {
            "role": "question_figure",
            "item_id": "question_figure_2",
            "question_index": "2",
            "path": str(current),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

    queue = build_batch_question_figure_repair_queue(
        [
            {
                "issue_id": "issue-a",
                "kind": "manual_comparison_issue",
                "profile_id": "exam_a",
                "profile_name": "Exam A",
                "repair_target_type": "question_figure_item",
                "repair_target_key": target_key,
                "comparison_issue_items": [
                    {
                        "item_id": "question_figure_2",
                        "label": "Question figure 2",
                        "path": str(current),
                        "question_index": "2",
                        "comparison_issue_reference": str(replacement_a),
                        "comparison_issue_display_name": replacement_a.name,
                        "comparison_issue_summary": "候选 A",
                    },
                    {
                        "item_id": "question_figure_2",
                        "label": "Question figure 2",
                        "path": str(current),
                        "question_index": "2",
                        "comparison_issue_reference": str(replacement_b),
                        "comparison_issue_display_name": replacement_b.name,
                        "comparison_issue_summary": "候选 B",
                    },
                ],
            }
        ]
    )

    assert queue["kind"] == "question_figure_repair_queue"
    assert queue["status"] == "conflict"
    assert queue["queue_count"] == 2
    assert queue["conflict_group_count"] == 1
    assert queue["conflict_count"] == 2
    entries = queue["entries"]
    assert {entry["confirmation_status"] for entry in entries} == {"conflict"}
    assert {entry["confirmation_apply_supported"] for entry in entries} == {False}
    assert {
        entry["confirmation_action"] for entry in entries
    } == {"resolve_question_figure_replacement_conflict"}
    conflict_group_ids = {entry["conflict_group_id"] for entry in entries}
    assert len(conflict_group_ids) == 1
    for entry in entries:
        assert entry["conflict_candidate_count"] == 2
        assert len(entry["conflict_candidate_queue_ids"]) == 2
        assert "candidate_conflict_same_repair_target" in entry["apply_blockers"]
        assert entry["conflict_resolution_select_supported"] is True
        assert entry["conflict_resolution_action"] == (
            "select_question_figure_replacement_conflict_candidate"
        )
        assert entry["replacement_source_kind"] == "local_file"
        assert entry["replacement_source_path"] in {
            str(replacement_a),
            str(replacement_b),
        }


def test_question_figure_repair_batch_confirmation_plan_summarizes_queue(tmp_path):
    current_ready = tmp_path / "question_2.png"
    replacement_ready = tmp_path / "question_2_expected.png"
    current_blocked = tmp_path / "question_5.png"
    current_conflict = tmp_path / "question_7.png"
    replacement_conflict_a = tmp_path / "question_7_expected_a.png"
    replacement_conflict_b = tmp_path / "question_7_expected_b.png"
    for image_path, color in (
        (current_ready, "blue"),
        (replacement_ready, "yellow"),
        (current_blocked, "green"),
        (current_conflict, "purple"),
        (replacement_conflict_a, "red"),
        (replacement_conflict_b, "orange"),
    ):
        Image.new("RGB", (320, 240), color=color).save(image_path)

    def target_key(item_id: str, question_index: str, path: Path) -> str:
        return json.dumps(
            {
                "role": "question_figure",
                "item_id": item_id,
                "question_index": question_index,
                "path": str(path),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

    queue = build_batch_question_figure_repair_queue(
        [
            {
                "issue_id": "issue-ready",
                "kind": "manual_comparison_issue",
                "profile_id": "exam_ready",
                "profile_name": "Exam Ready",
                "repair_target_type": "question_figure_item",
                "repair_target_key": target_key(
                    "question_figure_2", "2", current_ready
                ),
                "comparison_issue_items": [
                    {
                        "item_id": "question_figure_2",
                        "label": "Question figure 2",
                        "path": str(current_ready),
                        "question_index": "2",
                        "comparison_issue_reference": str(replacement_ready),
                        "comparison_issue_display_name": replacement_ready.name,
                    }
                ],
            },
            {
                "issue_id": "issue-blocked",
                "kind": "manual_comparison_issue",
                "profile_id": "exam_blocked",
                "profile_name": "Exam Blocked",
                "repair_target_type": "question_figure_item",
                "repair_target_key": target_key(
                    "question_figure_5", "5", current_blocked
                ),
                "comparison_issue_items": [
                    {
                        "item_id": "question_figure_5",
                        "label": "Question figure 5",
                        "path": str(current_blocked),
                        "question_index": "5",
                        "comparison_issue_reference": "asset://expected-q5",
                        "comparison_issue_display_name": "expected-q5",
                    }
                ],
            },
            {
                "issue_id": "issue-conflict",
                "kind": "manual_comparison_issue",
                "profile_id": "exam_conflict",
                "profile_name": "Exam Conflict",
                "repair_target_type": "question_figure_item",
                "repair_target_key": target_key(
                    "question_figure_7", "7", current_conflict
                ),
                "comparison_issue_items": [
                    {
                        "item_id": "question_figure_7",
                        "label": "Question figure 7",
                        "path": str(current_conflict),
                        "question_index": "7",
                        "comparison_issue_reference": str(replacement_conflict_a),
                        "comparison_issue_display_name": replacement_conflict_a.name,
                    },
                    {
                        "item_id": "question_figure_7",
                        "label": "Question figure 7",
                        "path": str(current_conflict),
                        "question_index": "7",
                        "comparison_issue_reference": str(replacement_conflict_b),
                        "comparison_issue_display_name": replacement_conflict_b.name,
                    },
                ],
            },
        ]
    )

    plan = queue["batch_confirmation_plan"]

    assert queue["status"] == "conflict"
    assert plan["kind"] == "question_figure_repair_batch_confirmation_plan"
    assert plan["status"] == "partial"
    assert plan["action"] == "review_question_figure_repair_batch_confirmation_plan"
    assert plan["entry_count"] == 4
    assert plan["target_count"] == 3
    assert plan["eligible_count"] == 1
    assert plan["blocked_count"] == 3
    assert plan["conflict_count"] == 2
    assert plan["duplicate_target_count"] == 0
    assert plan["batch_confirmation_supported"] is True
    assert plan["batch_apply_supported"] is False
    assert plan["plan_fingerprint"]
    assert len(plan["eligible_queue_ids"]) == 1
    assert len(plan["blocked_queue_ids"]) == 3
    assert plan["eligible_entries"][0]["question_index"] == "2"
    assert any(
        "comparison_reference_not_local_file" in entry["blockers"]
        for entry in plan["blocked_entries"]
    )
    assert sum(
        "candidate_conflict_same_repair_target" in entry["blockers"]
        for entry in plan["blocked_entries"]
    ) == 2
