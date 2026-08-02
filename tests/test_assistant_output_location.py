from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.assistant.application.output_location import (
    OUTPUT_FOLDER_NAME,
    default_assistant_output_root,
    load_last_output_root,
    remember_output_root,
    system_documents_directory,
)


def test_from_scratch_output_uses_os_documents_location_before_any_user_choice(
    tmp_path,
):
    documents = tmp_path / "Redirected Documents"

    output = default_assistant_output_root(
        storage_root=tmp_path / "assistant-state",
        documents_directory=documents,
    )

    assert output == documents / OUTPUT_FOLDER_NAME


def test_source_document_output_stays_next_to_the_source(tmp_path):
    source = tmp_path / "incoming" / "source.docx"

    output = default_assistant_output_root(
        source,
        storage_root=tmp_path / "assistant-state",
        documents_directory=tmp_path / "Documents",
    )

    assert output == source.parent / OUTPUT_FOLDER_NAME


def test_confirmed_output_location_is_remembered_for_future_authoring(tmp_path):
    state = tmp_path / "assistant-state"
    selected = tmp_path / "Desktop"
    selected.mkdir()

    saved = remember_output_root(selected, storage_root=state)

    assert saved == selected.resolve()
    assert load_last_output_root(storage_root=state) == selected.resolve()
    assert default_assistant_output_root(storage_root=state) == selected.resolve()
    payload = json.loads(
        (state / "output-location.json").read_text(encoding="utf-8")
    )
    assert payload["last_output_root"] == str(selected.resolve())


def test_stale_or_invalid_remembered_output_is_ignored(tmp_path):
    state = tmp_path / "assistant-state"
    state.mkdir()
    (state / "output-location.json").write_text(
        json.dumps(
            {
                "schema": "assistant-output-location-v1",
                "last_output_root": str(tmp_path / "missing"),
            }
        ),
        encoding="utf-8",
    )

    assert load_last_output_root(storage_root=state) is None
    with pytest.raises(ValueError, match="assistant_output_root_invalid"):
        remember_output_root(tmp_path / "missing", storage_root=state)


def test_system_documents_prefers_the_windows_known_folder(tmp_path):
    redirected = tmp_path / "OneDrive" / "文档"

    assert system_documents_directory(
        env={"USERPROFILE": str(tmp_path / "profile")},
        windows_resolver=lambda: redirected,
    ) == redirected
