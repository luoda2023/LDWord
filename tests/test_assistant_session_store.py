from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.assistant.application.session_coordinator import AssistantSessionCoordinator
from src.assistant.contracts.messages import ROLE_ASSISTANT, ROLE_USER, AssistantMessage
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


def test_append_user_message_can_consume_staged_draft_atomically(tmp_path):
    coordinator = AssistantSessionCoordinator(AssistantSessionStore(tmp_path))
    session = coordinator.create_session()
    session = coordinator.stage_draft(session, "尚未发送的要求")

    session = coordinator.append_message(
        session,
        AssistantMessage.text(role=ROLE_USER, text="尚未发送的要求"),
        consume_draft=True,
    )

    restored = coordinator.load_session(session.session_id)
    assert restored.draft_text == ""
    assert [message.visible_text() for message in restored.messages] == [
        "尚未发送的要求"
    ]


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


def test_corrupt_session_can_be_quarantined_but_not_by_escaping_store(tmp_path):
    store = AssistantSessionStore(tmp_path / "assistant")
    store.sessions_dir.mkdir(parents=True)
    broken = store.sessions_dir / "broken.json"
    broken.write_text("{not-json", encoding="utf-8")
    outside = tmp_path / "outside.json"
    outside.write_text("{outside", encoding="utf-8")

    destination = store.quarantine_corrupt(str(broken.resolve()))

    assert not broken.exists()
    assert destination.parent == store.root / "recovery"
    assert destination.read_text(encoding="utf-8") == "{not-json"
    assert store.list_summaries() == ()
    with pytest.raises(ValueError, match="Unsafe"):
        store.quarantine_corrupt(str(outside.resolve()))
    assert outside.is_file()


def test_icon_and_manual_section_order_round_trip(tmp_path):
    coordinator = AssistantSessionCoordinator(AssistantSessionStore(tmp_path))
    first = coordinator.create_session(title="一")
    second = coordinator.create_session(title="二")
    third = coordinator.create_session(title="三")

    first = coordinator.set_icon(first, "file-text")
    reordered = coordinator.reorder_sessions(
        (first.session_id, third.session_id, second.session_id),
        pinned=False,
    )

    assert [session.sidebar_order for session in reordered] == [0, 1, 2]
    assert [
        summary.session_id for summary in coordinator.list_sessions()
    ] == [first.session_id, third.session_id, second.session_id]
    restored = coordinator.load_session(first.session_id)
    assert restored.icon_name == "file-text"
    assert restored.sidebar_order == 0
    with pytest.raises(ValueError, match="Unsupported"):
        coordinator.set_icon(restored, "not-an-icon")


def test_sidebar_layout_failure_does_not_partially_mutate_sessions(
    tmp_path,
    monkeypatch,
):
    store = AssistantSessionStore(tmp_path)
    coordinator = AssistantSessionCoordinator(store)
    first = coordinator.create_session(title="一")
    second = coordinator.create_session(title="二")
    coordinator.reorder_sessions(
        (first.session_id, second.session_id),
        pinned=False,
    )
    before_order = tuple(
        summary.session_id for summary in coordinator.list_sessions()
    )
    before_payloads = {
        path.name: path.read_bytes()
        for path in store.sessions_dir.glob("*.json")
    }
    before_sidebar_state = store.sidebar_state_path.read_bytes()
    original_replace = os.replace

    def fail_sidebar_replace(source, destination):
        if Path(destination) == store.sidebar_state_path:
            raise OSError("injected sidebar transaction failure")
        return original_replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_sidebar_replace)

    with pytest.raises(OSError, match="transaction failure"):
        coordinator.move_session_to_section(
            second.session_id,
            pinned=True,
            target_index=0,
        )

    assert tuple(
        summary.session_id for summary in coordinator.list_sessions()
    ) == before_order
    assert coordinator.load_session(second.session_id).pinned is False
    assert {
        path.name: path.read_bytes()
        for path in store.sessions_dir.glob("*.json")
    } == before_payloads
    assert store.sidebar_state_path.read_bytes() == before_sidebar_state
    assert coordinator.load_session(first.session_id).sidebar_order == 0
    assert not tuple(store.root.glob(".sidebar-state.json.*.tmp"))


def test_list_summaries_uses_lightweight_cache_after_session_save(
    tmp_path,
    monkeypatch,
):
    store = AssistantSessionStore(tmp_path)
    coordinator = AssistantSessionCoordinator(store)
    session = coordinator.create_session(title="缓存摘要")
    session = coordinator.append_message(
        session,
        AssistantMessage.text(role=ROLE_USER, text="不要重读完整历史"),
    )
    cache_path = store.summaries_dir / f"{session.session_id}.json"

    assert cache_path.is_file()
    monkeypatch.setattr(
        store,
        "_load_path",
        lambda _path: (_ for _ in ()).throw(
            AssertionError("full aggregate should not be loaded")
        ),
    )

    summaries = coordinator.list_sessions()

    assert len(summaries) == 1
    assert summaries[0].session_id == session.session_id
    assert summaries[0].preview == "不要重读完整历史"


def test_summary_cache_does_not_add_a_second_durable_flush(
    tmp_path,
    monkeypatch,
):
    fsync_calls: list[int] = []
    monkeypatch.setattr(os, "fsync", lambda descriptor: fsync_calls.append(descriptor))
    coordinator = AssistantSessionCoordinator(AssistantSessionStore(tmp_path))

    coordinator.create_session(title="仅会话正文需要强制刷盘")

    assert len(fsync_calls) == 1


def test_persisted_draft_defers_recoverable_summary_cache_refresh(tmp_path):
    store = AssistantSessionStore(tmp_path)
    coordinator = AssistantSessionCoordinator(store)
    session = coordinator.create_session(title="草稿缓存")
    cache_path = store.summaries_dir / f"{session.session_id}.json"
    cached_before = cache_path.read_bytes()

    session = coordinator.persist(
        coordinator.stage_draft(session, "防抖后保存的内容")
    )

    assert coordinator.load_session(session.session_id).draft_text == "防抖后保存的内容"
    assert cache_path.read_bytes() == cached_before
    summaries = coordinator.list_sessions()
    assert summaries[0].has_draft is True
    assert cache_path.read_bytes() != cached_before


def test_reorder_requires_a_complete_distinct_section(tmp_path):
    coordinator = AssistantSessionCoordinator(AssistantSessionStore(tmp_path))
    first = coordinator.create_session(title="一")
    second = coordinator.create_session(title="二")

    with pytest.raises(ValueError, match="full section"):
        coordinator.reorder_sessions((first.session_id,), pinned=False)
    with pytest.raises(ValueError, match="duplicate"):
        coordinator.reorder_sessions(
            (first.session_id, first.session_id),
            pinned=False,
        )

    assert {
        summary.session_id for summary in coordinator.list_sessions()
    } == {first.session_id, second.session_id}


def test_metadata_update_state_can_preserve_activity_timestamp(tmp_path):
    coordinator = AssistantSessionCoordinator(AssistantSessionStore(tmp_path))
    session = coordinator.create_session()
    original_activity = session.activity_at

    session = coordinator.update_state(
        session,
        model_id="another-model",
        touch_activity=False,
    )
    session = coordinator.update_state(
        session,
        provider_profile_id="another-provider",
        provider_history_grant={"approved": True},
        touch_activity=False,
    )
    session = coordinator.update_state(
        session,
        context_refs=({"path": "sample.docx"},),
        touch_activity=False,
    )

    assert session.activity_at == original_activity
    assert session.updated_at >= original_activity


def test_legacy_v1_session_defaults_activity_icon_and_order(tmp_path):
    coordinator = AssistantSessionCoordinator(AssistantSessionStore(tmp_path))
    session = coordinator.create_session(title="旧会话")
    path = coordinator.store.sessions_dir / f"{session.session_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("activity_at")
    payload.pop("unread")
    payload.pop("icon_name")
    payload.pop("sidebar_order")
    path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    restored = coordinator.load_session(session.session_id)

    assert restored.activity_at == restored.updated_at
    assert restored.unread is False
    assert restored.icon_name == "message-circle"
    assert restored.sidebar_order is None


def test_summary_projects_draft_preview_and_user_turn_count(tmp_path):
    coordinator = AssistantSessionCoordinator(AssistantSessionStore(tmp_path))
    session = coordinator.create_session()
    session = coordinator.append_message(
        session,
        AssistantMessage.text(role=ROLE_USER, text="第一条用户要求"),
    )
    session = coordinator.append_message(
        session,
        AssistantMessage.text(role=ROLE_ASSISTANT, text="这是最新预览"),
    )
    session = coordinator.update_draft(session, "尚未发送")

    summary = session.summary()

    assert summary.has_draft is True
    assert summary.preview == "这是最新预览"
    assert summary.turn_count == 1

    unread = coordinator.set_unread(session, True)
    assert unread.activity_at == session.activity_at
    assert unread.summary().unread is True
