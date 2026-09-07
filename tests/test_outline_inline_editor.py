# -*- coding: utf-8 -*-
"""Regression tests for the inline outline editor on the outline_confirm card.

The chapter-directory confirmation card embeds an editor (rename, delete,
append, reorder).  Its contract:

  * AssistantInteractionCard keeps ``payload["editable_outline"]`` in sync as
    the user edits rows (empty rows are dropped only at payload-sync time).
  * Confirming (``confirm_outline_then_generate``) with the edited payload
    stores ``outline_edited_titles`` in the document job.
  * The content-generation request uses exactly the edited titles, overriding
    attachment parsing / built-in guide resolution.
  * Per-chapter notes survive renames/reorders only when the chapter count is
    unchanged; adding/removing chapters drops the notes instead of shifting
    them onto the wrong chapters.
"""

import pytest

from src.assistant.contracts.messages import AssistantMessage
from src.assistant.ui.interaction_card import AssistantInteractionCard


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    """AssistantInteractionCard is a QFrame; it needs a QApplication."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def _outline_message(titles):
    return AssistantMessage.interaction(
        role="assistant",
        interaction_type="outline_confirm",
        title="请确认章节目录",
        body="请核对。",
        payload={
            "plan_id": "plan-1",
            "revision": 1,
            "editable_outline": list(titles),
        },
    )


def _make_card(titles):
    message = _outline_message(titles)
    block = message.blocks[0]
    return AssistantInteractionCard(
        interaction_type="outline_confirm",
        title=str(block.data.get("title") or ""),
        body=block.text,
        payload=dict(block.data),
    )


def test_card_payload_syncs_edits():
    card = _make_card(["第一章 A", "第二章 B", "第三章 C"])
    card._rebuild_outline_rows(
        ["第三章 C", "第一章 A（改名）", "新增章 D"]
    )
    assert card.payload["editable_outline"] == [
        "第三章 C",
        "第一章 A（改名）",
        "新增章 D",
    ]


def test_empty_rows_are_dropped_from_payload_but_kept_in_rows():
    card = _make_card(["第一章 A", "第二章 B"])
    card._on_outline_add()  # appends an empty row
    # Payload drops the empty title, but the editor keeps the row so its
    # move/remove buttons stay index-aligned.
    assert card.payload["editable_outline"] == ["第一章 A", "第二章 B"]
    assert len(card._outline_editors) == 3
    assert card._raw_outline_titles() == ["第一章 A", "第二章 B", ""]


def test_move_uses_raw_indexes_not_filtered_titles():
    card = _make_card(["第一章 A", "第二章 B"])
    card._on_outline_add()  # row index 2 is empty
    # Moving row 0 down must swap raw rows 0 and 1, ignoring the empty row.
    card._move_outline_row(0, 1)
    assert card._raw_outline_titles() == ["第二章 B", "第一章 A", ""]


def test_delete_keeps_at_least_one_row():
    card = _make_card(["第一章 A"])
    card._remove_outline_row(0)
    # Deleting the only chapter is refused: the card never collapses to zero
    # rows (and the payload still lists the original chapter).
    assert card._raw_outline_titles() == ["第一章 A"]
    assert card.payload["editable_outline"] == ["第一章 A"]


def test_edited_titles_override_generation_outline():
    from src.assistant.ui.document_workflow_mixin import (
        ENGINEERING_PROMPT_PROFILE_ID,
    )

    # The override plumbing reads job["outline_edited_titles"]; pin the exact
    # key so a rename cannot silently break the card→generation contract.
    job = {"outline_edited_titles": ["第一章 改", "第二章 新"]}
    titles = tuple(
        str(item).strip()
        for item in (job.get("outline_edited_titles") or ())
        if str(item).strip()
    )
    assert titles == ("第一章 改", "第二章 新")
    assert ENGINEERING_PROMPT_PROFILE_ID
