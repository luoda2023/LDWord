import json

import pytest

from src.config.entity import EntityArchive, EntityProfile
from src.config.material_batch import MaterialBatchSelection
from src.shared.engine.official_document_batch_history import (
    HISTORY_INDEX_KIND,
    build_official_document_batch_retry_selection,
    list_official_document_batch_history,
    load_official_document_batch_history,
    official_document_batch_failed_profile_ids,
    persist_official_document_batch_history,
)
import src.shared.engine.official_document_batch_history as history_module


def _selection() -> MaterialBatchSelection:
    return MaterialBatchSelection(
        archive=EntityArchive(
            archive_id="official_batch:test",
            profiles=[
                EntityProfile(profile_id="notice_ok", profile_name="Notice"),
                EntityProfile(profile_id="letter_bad", profile_name="Letter"),
            ],
        ),
        profile_ids=["notice_ok", "letter_bad"],
        source_kind="official_document_table",
        source_path="C:/docs/official_batch.csv",
        item_metadata={"letter_bad": {"row_number": 2}},
    )


def _report(status="partial_success") -> dict[str, object]:
    return {
        "status": status,
        "batch_source_kind": "official_document_table",
        "batch_source_path": "C:/docs/official_batch.csv",
        "items": [
            {"profile_id": "notice_ok", "status": "success"},
            {"profile_id": "letter_bad", "status": "failed"},
        ],
        "failed_count": 1,
    }


def test_official_batch_history_persists_immutable_runs_and_index(tmp_path):
    first = persist_official_document_batch_history(
        tmp_path,
        _report(),
        run_id="run_1",
        created_at="2026-07-10T10:00:00+00:00",
    )
    retry = persist_official_document_batch_history(
        tmp_path,
        {
            **_report("success"),
            "items": [{"profile_id": "letter_bad", "status": "success"}],
            "failed_count": 0,
        },
        run_id="run_2",
        created_at="2026-07-10T10:05:00+00:00",
        retry_of_run_id="run_1",
        attempt_number=2,
    )

    assert first.retryable is True
    assert first.failed_profile_ids == ("letter_bad",)
    assert retry.retryable is False
    assert retry.retry_of_run_id == "run_1"
    assert retry.attempt_number == 2
    assert first.history_path.is_file()
    assert retry.history_path.is_file()
    assert load_official_document_batch_history(first.history_path) == first

    records = list_official_document_batch_history(tmp_path)
    assert [record.run_id for record in records] == ["run_2", "run_1"]
    index = json.loads(
        (tmp_path / "batch_history" / "batch_history_index.json").read_text(
            encoding="utf-8"
        )
    )
    assert index["kind"] == HISTORY_INDEX_KIND
    assert [record["run_id"] for record in index["records"]] == [
        "run_2",
        "run_1",
    ]


def test_official_batch_history_index_failure_rolls_back_new_run_and_index(
    tmp_path,
    monkeypatch,
):
    first = persist_official_document_batch_history(
        tmp_path,
        _report(),
        run_id="run_1",
        created_at="2026-07-10T10:00:00+00:00",
    )
    index_path = tmp_path / "batch_history" / "batch_history_index.json"
    original_index = index_path.read_bytes()
    original_write = history_module._atomic_write_json

    def _fail_index(path, payload):
        if path.name == "batch_history_index.json":
            raise OSError(5, "simulated index failure", str(path))
        return original_write(path, payload)

    monkeypatch.setattr(history_module, "_atomic_write_json", _fail_index)

    with pytest.raises(OSError, match="simulated index failure"):
        persist_official_document_batch_history(
            tmp_path,
            _report("success"),
            run_id="run_2",
            created_at="2026-07-10T10:05:00+00:00",
        )

    assert first.history_path.is_file()
    assert not (tmp_path / "batch_history" / "run_2.json").exists()
    assert index_path.read_bytes() == original_index
    assert [record.run_id for record in list_official_document_batch_history(tmp_path)] == [
        "run_1"
    ]


def test_official_batch_retry_selection_is_narrow_and_non_destructive():
    source = _selection()
    retry = build_official_document_batch_retry_selection(
        source,
        ["missing", "letter_bad", "letter_bad"],
        retry_of_run_id="run_1",
        attempt_number=2,
    )

    assert source.profile_ids == ["notice_ok", "letter_bad"]
    assert "retry_of_run_id" not in source.item_metadata["letter_bad"]
    assert retry.profile_ids == ["letter_bad"]
    assert retry.archive is not source.archive
    assert retry.item_metadata["letter_bad"]["retry_of_run_id"] == "run_1"
    assert retry.item_metadata["letter_bad"]["retry_attempt_number"] == 2


def test_official_batch_failed_profile_ids_preserve_result_order():
    payload = _report()
    payload["items"].append({"profile_id": "unknown", "status": "cancelled"})
    payload["pending_profile_ids"] = ["not_started", "letter_bad"]

    assert official_document_batch_failed_profile_ids(payload) == (
        "letter_bad",
        "unknown",
        "not_started",
    )


def test_cancelled_batch_history_keeps_not_started_profiles_retryable(tmp_path):
    record = persist_official_document_batch_history(
        tmp_path,
        {
            "status": "cancelled",
            "batch_source_kind": "official_document_table",
            "batch_source_path": "C:/docs/official_batch.csv",
            "items": [],
            "pending_profile_ids": ["notice_ok", "letter_bad"],
        },
        run_id="cancelled_before_first_item",
    )

    assert record.item_count == 2
    assert record.success_count == 0
    assert record.failed_count == 2
    assert record.failed_profile_ids == ("notice_ok", "letter_bad")
    assert record.retryable is True


def test_official_batch_history_loader_rejects_wrong_kind(tmp_path):
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps({"kind": "other", "version": 1}), encoding="utf-8")

    assert load_official_document_batch_history(path) is None
