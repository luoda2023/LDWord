from __future__ import annotations

import pytest

from src.assistant.application.execution_lease import ExecutionLeaseManager
from src.assistant.application.session_coordinator import AssistantSessionCoordinator
from src.assistant.application.session_recovery import AssistantSessionRecovery
from src.assistant.storage.execution_journal import (
    ExecutionJournalRecord,
    ExecutionJournalStore,
)
from src.assistant.storage.session_store import AssistantSessionStore


def _coordinator(tmp_path):
    return AssistantSessionCoordinator(AssistantSessionStore(tmp_path / "assistant"))


def test_recovery_marks_unreceipted_running_job_interrupted(tmp_path):
    coordinator = _coordinator(tmp_path)
    session = coordinator.create_session()
    session = coordinator.update_state(
        session,
        document_job={"status": "execution_running", "execution_id": "execution-1"},
    )
    recovery = AssistantSessionRecovery(
        coordinator,
        ExecutionJournalStore(tmp_path / "executions"),
        ExecutionLeaseManager(),
    )

    summary = recovery.reconcile()
    restored = coordinator.load_session(session.session_id)

    assert summary.interrupted_jobs == 1
    assert restored.document_job["status"] == "failed"
    assert restored.document_job["error_text"] == "assistant_execution_interrupted"
    assert restored.messages[-1].blocks[0].data["interaction_type"] == "recovery"


def test_recovery_restores_terminal_result_from_execution_journal(tmp_path):
    coordinator = _coordinator(tmp_path)
    session = coordinator.create_session()
    session = coordinator.update_state(
        session,
        document_job={"status": "execution_running", "execution_id": "execution-1"},
    )
    journals = ExecutionJournalStore(tmp_path / "executions")
    student_path = tmp_path / "student.docx"
    answer_path = tmp_path / "answer.docx"
    student_path.touch()
    answer_path.touch()
    journals.begin(
        ExecutionJournalRecord(
            execution_id="execution-1",
            session_id=session.session_id,
            plan_id="plan-1",
            plan_revision=1,
            plan_fingerprint="fingerprint-1",
            status="running",
            started_at="2026-07-16T00:00:00+00:00",
        )
    )
    journals.finish(
        "execution-1",
        status="success",
        completed_at="2026-07-16T00:01:00+00:00",
        result={
            "status": "success",
            "output_path": str(student_path),
            "output_paths": {
                "student": str(student_path),
                "answer_key": str(answer_path),
            },
        },
    )
    recovery = AssistantSessionRecovery(
        coordinator,
        journals,
        ExecutionLeaseManager(),
    )

    summary = recovery.reconcile()
    restored = coordinator.load_session(session.session_id)

    assert summary.recovered_terminal_jobs == 1
    assert restored.document_job["status"] == "success"
    assert restored.document_job["recovered_from_journal"] is True
    assert restored.messages[-1].blocks[0].data["interaction_type"] == "artifact"
    assert restored.messages[-1].blocks[0].data["actions"] == [
        {"id": "runtime_open_reference", "label": "打开文档"}
    ]
    assert {
        item["artifact_key"]
        for item in restored.messages[-1].blocks[0].data["references"]
    } == {"student", "answer_key"}


def test_recovery_preserves_job_message_when_provider_turn_was_also_running(tmp_path):
    coordinator = _coordinator(tmp_path)
    session = coordinator.create_session()
    session = coordinator.update_state(
        session,
        turn_status="provider_running",
        document_job={
            "status": "content_generation_running",
            "execution_id": "execution-1",
        },
    )
    recovery = AssistantSessionRecovery(
        coordinator,
        ExecutionJournalStore(tmp_path / "executions"),
        ExecutionLeaseManager(),
    )

    summary = recovery.reconcile()
    restored = coordinator.load_session(session.session_id)

    assert summary.interrupted_jobs == 1
    assert summary.interrupted_turns == 1
    assert restored.turn_status == "failed"
    assert [message.blocks[0].data.get("title") for message in restored.messages] == [
        "上次内容起草已中断",
        "上次 AI 回复已中断",
    ]
    assert restored.messages[0].blocks[0].data["actions"] == [
        {"id": "generate_content_draft", "label": "重新生成内容草稿"}
    ]


def test_recovery_turns_interrupted_preflight_into_actionable_retry(tmp_path):
    coordinator = _coordinator(tmp_path)
    session = coordinator.create_session()
    session = coordinator.update_state(
        session,
        document_job={"status": "preflight_running"},
    )
    recovery = AssistantSessionRecovery(
        coordinator,
        ExecutionJournalStore(tmp_path / "executions"),
        ExecutionLeaseManager(),
    )

    summary = recovery.reconcile()
    restored = coordinator.load_session(session.session_id)

    assert summary.interrupted_jobs == 1
    assert restored.document_job["status"] == "preflight_failed"
    assert restored.document_job["error_text"] == "assistant_preflight_interrupted"
    assert restored.messages[-1].blocks[0].data["actions"] == [
        {"id": "retry_preflight", "label": "重新检查"}
    ]


def test_recovery_reopens_authorized_generation_that_never_started(tmp_path):
    coordinator = _coordinator(tmp_path)
    session = coordinator.create_session()
    session = coordinator.update_state(
        session,
        document_job={"status": "content_generation_ready"},
    )
    recovery = AssistantSessionRecovery(
        coordinator,
        ExecutionJournalStore(tmp_path / "executions"),
        ExecutionLeaseManager(),
    )

    summary = recovery.reconcile()
    restored = coordinator.load_session(session.session_id)

    assert summary.interrupted_jobs == 1
    assert restored.document_job["status"] == "plan_ready"
    assert restored.messages[-1].blocks[0].data["actions"] == [
        {
            "id": "generate_content_draft",
            "label": "继续生成内容草稿",
        }
    ]


def test_recovery_closes_incomplete_official_field_continuation(tmp_path):
    coordinator = _coordinator(tmp_path)
    session = coordinator.create_session()
    session = coordinator.update_state(
        session,
        document_job={"status": "needs_official_field_completion"},
    )
    recovery = AssistantSessionRecovery(
        coordinator,
        ExecutionJournalStore(tmp_path / "executions"),
        ExecutionLeaseManager(),
    )

    summary = recovery.reconcile()
    restored = coordinator.load_session(session.session_id)

    assert summary.interrupted_jobs == 1
    assert restored.document_job["status"] == "failed"
    assert restored.document_job["error_text"] == (
        "assistant_official_field_completion_interrupted"
    )


def test_execution_journal_never_overwrites_an_existing_execution(tmp_path):
    journals = ExecutionJournalStore(tmp_path / "executions")
    record = ExecutionJournalRecord(
        execution_id="execution-1",
        session_id="session-1",
        plan_id="plan-1",
        plan_revision=1,
        plan_fingerprint="fingerprint-1",
        status="running",
        started_at="2026-07-16T00:00:00+00:00",
    )

    journals.begin(record)

    with pytest.raises(FileExistsError):
        journals.begin(record)
    assert journals.load("execution-1") == record
