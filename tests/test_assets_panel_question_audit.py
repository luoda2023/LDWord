import json

from src.config.materials import AssetItem
from src.ui.panels import assets_panel
from src.ui.panels.assets import question_audit


def test_question_audit_helpers_are_compatibly_exported_from_assets_panel():
    assert (
        assets_panel._question_figure_repair_audit_record
        is question_audit._question_figure_repair_audit_record
    )
    assert (
        assets_panel._append_question_figure_repair_audit_record
        is question_audit._append_question_figure_repair_audit_record
    )


def test_question_audit_apply_and_rollback_records_round_trip(tmp_path):
    original = tmp_path / "original.png"
    replacement = tmp_path / "replacement.png"
    original.write_bytes(b"original")
    replacement.write_bytes(b"replacement")
    item = AssetItem(
        item_id="q1",
        label="Question 1",
        role="question_figure",
        path=str(original),
        metadata={"question_index": "1", "asset_id": "remote-q1"},
    )
    candidate = {
        "queue_id": "queue-1",
        "kind": "missing_file",
        "source_issue_id": "issue-1",
        "repair_target_key": "question_figure:1",
        "conflict_resolution_candidate_queue_ids": ["queue-1", "queue-2"],
    }

    record = question_audit._question_figure_repair_audit_record(
        candidate,
        original_item=item,
        replacement_path=str(replacement),
        archive_id="archive-1",
        archive_name="Archive",
        profile_id="profile-1",
        profile_name="Profile",
        applied_at="2026-07-06T00:00:00Z",
    )
    audit_dir = question_audit._question_figure_repair_audit_dir(
        "",
        str(original),
        str(replacement),
    )
    written = question_audit._append_question_figure_repair_audit_record(
        audit_dir,
        record,
    )
    payload = question_audit._read_question_figure_repair_audit_payload(
        tmp_path / "question_figure_repair_audit.json"
    )
    rollback = question_audit._question_figure_repair_rollback_audit_record(
        written,
        rollback_from_item=item,
        rollback_path=str(original),
        archive_id="archive-1",
        archive_name="Archive",
        profile_id="profile-1",
        profile_name="Profile",
        rolled_back_at="2026-07-06T00:05:00Z",
    )

    assert record["audit_id"].startswith("repair-apply-")
    assert record["question_index"] == "1"
    assert written["artifact_path"].endswith("question_figure_repair_audit.json")
    assert payload["entry_count"] == 1
    assert payload["records"][0]["audit_id"] == record["audit_id"]
    assert rollback["audit_id"].startswith("repair-rollback-")
    assert rollback["linked_apply_audit_id"] == record["audit_id"]
    assert json.loads(json.dumps(rollback))["status"] == "rolled_back"
