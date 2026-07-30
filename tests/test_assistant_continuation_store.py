from __future__ import annotations

import pytest

from src.assistant.runtime.continuation_store import ContinuationRecord, ContinuationStore


def test_continuation_is_durable_and_consumed_once(tmp_path):
    store = ContinuationStore(tmp_path)
    record = ContinuationRecord(
        continuation_id="continuation-1",
        session_id="session-1",
        turn_id="turn-1",
        kind="tool_permission",
        payload={"tool_name": "run_document_production"},
        created_at="2026-07-16T00:00:00+00:00",
    )

    store.save(record)
    assert store.list_pending() == (record,)
    assert store.consume(record.continuation_id) == record
    assert store.list_pending() == ()
    with pytest.raises(FileNotFoundError):
        store.consume(record.continuation_id)


def test_continuation_rejects_unknown_kind_and_unsafe_id(tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        ContinuationRecord(
            continuation_id="continuation-1",
            session_id="session-1",
            turn_id="turn-1",
            kind="workflow_job",
        )
    store = ContinuationStore(tmp_path)
    with pytest.raises(ValueError, match="Unsafe"):
        store.load("../escape")
