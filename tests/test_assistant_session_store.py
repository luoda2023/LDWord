from __future__ import annotations

import json

import pytest

from src.assistant.application.session_coordinator import AssistantSessionCoordinator
from src.assistant.contracts.messages import AssistantMessage, ROLE_ASSISTANT, ROLE_USER
from src.assistant.storage.paths import assistant_storage_root
from src.assistant.storage.session_store import AssistantSessionStore


def test_assistant_storage_root_prefers_explicit_override(tmp_path):
    assert assistant_storage_root(env={"ALAVETTE_FORM_ASSISTANT_HOME": str(tmp_path)}) == tmp_path


def test_session_store_is_lazy_and_round_trips_atomically(tmp_path):
    store = AssistantSessionStore(tmp_path / "assistant")
    coordinator = AssistantSessionCoordinator(store)

    assert not store.sessions_dir.exists()
    assert coordinator.list_sessions() == ()

    session = coordinator.create_session()
    session = coordinator.append_message(
        session,
        AssistantMessage.text(role=ROLE_USER, text="请统一标题格式"),
    )
    session = coordinator.append_message(
        session,
        AssistantMessage.text(role=ROLE_ASSISTANT, text="我会先形成计划"),
    )

    restored = coordinator.load_session(session.session_id)
    assert restored == session
    assert restored.title == "请统一标题格式"
    assert [message.role for message in restored.messages] == [ROLE_USER, ROLE_ASSISTANT]
    assert list(store.sessions_dir.glob("*.tmp")) == []


def test_session_store_rejects_path_escape(tmp_path):
    store = AssistantSessionStore(tmp_path)
    with pytest.raises(ValueError, match="Unsafe"):
        store.load("../outside")


def test_session_store_lists_corrupt_entry_for_recovery_and_fails_explicit_load(tmp_path):
    store = AssistantSessionStore(tmp_path)
    store.sessions_dir.mkdir(parents=True)
    broken = store.sessions_dir / "broken.json"
    broken.write_text("{not-json", encoding="utf-8")

    summaries = store.list_summaries()
    assert len(summaries) == 1
    assert summaries[0].corrupt is True
    assert summaries[0].recovery_path == str(broken.resolve())
    assert broken.is_file()
    with pytest.raises(json.JSONDecodeError):
        store.load("broken")


def test_session_delete_only_removes_requested_session(tmp_path):
    coordinator = AssistantSessionCoordinator(AssistantSessionStore(tmp_path))
    first = coordinator.create_session(title="A")
    second = coordinator.create_session(title="B")

    assert coordinator.delete_session(first.session_id)
    assert [item.session_id for item in coordinator.list_sessions()] == [second.session_id]
