# -*- coding: utf-8 -*-
"""Regression tests for the two-phase 目录确认 → 开始写正文 gate.

The user flow is: generate plan → a directory-confirm card appears listing the
chapters (NOT yet written into the left dock) → clicking "确认目录，开始写正文"
(ACTION_CONFIRM_OUTLINE_AND_GENERATE) is the only path that actually starts
the streaming writer.

These tests pin the *pure* projection contracts so the wiring cannot silently
drift: the action id is a real document action, the outline_confirm card stays
active only while the plan is ready, and the confirm button projects as a
right-aligned primary "check" action.
"""

from src.assistant.application.active_document_continuation import (
    ACTION_CONFIRM_OUTLINE_AND_GENERATE,
    DOCUMENT_ACTION_IDS,
)
from src.assistant.ui.conversation_presentation import (
    interaction_is_active,
    project_interaction,
)


def test_confirm_action_is_registered_document_action():
    assert ACTION_CONFIRM_OUTLINE_AND_GENERATE in DOCUMENT_ACTION_IDS


def test_confirm_action_is_accepted_when_plan_ready():
    """Confirm must clear the validator while the job is still plan_ready.

    Use a matching plan identity so the validator reaches the accept path
    instead of failing closed on a stale plan or unknown action.
    """
    from src.assistant.application.active_document_continuation import (
        validate_active_document_action,
    )

    class _StubPlan:
        plan_id = "plan-x"
        revision = 1
        generation_required = True
        blocking_issues = ()

    job = {"status": "plan_ready", "plan_id": "plan-x", "plan_revision": 1}
    rejection = validate_active_document_action(
        ACTION_CONFIRM_OUTLINE_AND_GENERATE,
        job=job,
        plan=_StubPlan(),  # type: ignore[arg-type]
    )
    assert rejection == ""


def test_confirm_action_rejected_on_unknown_status():
    from src.assistant.application.active_document_continuation import (
        validate_active_document_action,
    )

    class _StubPlan:
        plan_id = "plan-x"
        revision = 1
        generation_required = True
        blocking_issues = ()

    job = {"status": "content_generation_running", "plan_id": "plan-x", "plan_revision": 1}
    rejection = validate_active_document_action(
        ACTION_CONFIRM_OUTLINE_AND_GENERATE,
        job=job,
        plan=_StubPlan(),  # type: ignore[arg-type]
    )
    assert rejection == "assistant_document_action_state_changed"


def test_outline_confirm_card_projects_confirm_button():
    """The confirm card lists chapters and a right-aligned primary confirm."""
    card = project_interaction(
        interaction_type="outline_confirm",
        title="请确认章节目录",
        body="第1章 概述\n第2章 需求",
        payload={
            "plan_id": "plan-x",
            "revision": 1,
            "actions": [
                {
                    "id": ACTION_CONFIRM_OUTLINE_AND_GENERATE,
                    "label": "确认目录，开始写正文",
                    "variant": "primary",
                }
            ],
        },
    )
    assert card.interaction_type == "outline_confirm"
    assert card.eyebrow == "确认章节目录"
    assert "第1章" in card.body
    assert len(card.actions) == 1
    action = card.actions[0]
    assert action.action_id == ACTION_CONFIRM_OUTLINE_AND_GENERATE
    assert action.alignment == "right"
    assert action.icon_name == "check"


def test_outline_confirm_card_active_only_when_plan_ready():
    payload = {
        "plan_id": "plan-x",
        "revision": 1,
        "actions": [{"id": ACTION_CONFIRM_OUTLINE_AND_GENERATE, "label": "确认目录，开始写正文"}],
    }
    active_plan = {"plan_id": "plan-x", "revision": 1}
    # plan_ready → the card is actionable.
    assert interaction_is_active(
        interaction_type="outline_confirm",
        payload=payload,
        pending_continuation=None,
        active_plan=active_plan,
        document_job={"status": "plan_ready"},
        turn_status="completed",
    )
    # content_generation_ready is also still actionable (regenerate/retry path).
    assert interaction_is_active(
        interaction_type="outline_confirm",
        payload=payload,
        pending_continuation=None,
        active_plan=active_plan,
        document_job={"status": "content_generation_ready"},
        turn_status="completed",
    )
    # Once writing actually started, the old confirm card must go inactive.
    assert not interaction_is_active(
        interaction_type="outline_confirm",
        payload=payload,
        pending_continuation=None,
        active_plan=active_plan,
        document_job={"status": "content_generation_running"},
        turn_status="completed",
    )
    # A stale plan/revision must not remain actionable.
    assert not interaction_is_active(
        interaction_type="outline_confirm",
        payload=payload,
        pending_continuation=None,
        active_plan={"plan_id": "plan-y", "revision": 1},
        document_job={"status": "plan_ready"},
        turn_status="completed",
    )
