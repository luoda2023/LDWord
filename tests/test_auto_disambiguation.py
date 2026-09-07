# -*- coding: utf-8 -*-
"""Regression tests for one-line-to-outline routing.

When a one-line authoring request ties between similar document scenes, the
assistant must pick the top-scored scene itself and proceed toward the
chapter-directory card — it must not stop to ask the user which scene was
meant (the 选模板/选方案 follow-up question has been removed).
"""

from src.assistant.application.request_policy import (
    POLICY_DOCUMENT_ACTION,
    evaluate_request_policy,
)


_AMBIGUOUS_QUERY = "写一份标书与可研报告"


def test_ambiguous_authoring_request_auto_picks_top_scene():
    decision = evaluate_request_policy(
        _AMBIGUOUS_QUERY,
        workspace_mode_id="custom",
    )
    assert decision.kind == POLICY_DOCUMENT_ACTION
    assert decision.route is not None
    # The engineering scene scores 124 vs bidding 122; the top match must win.
    assert decision.route.route_id == "engineering_document_authoring"


def test_ambiguous_request_no_longer_returns_clarification():
    decision = evaluate_request_policy(
        _AMBIGUOUS_QUERY,
        workspace_mode_id="custom",
    )
    assert decision.choices == ()
    assert "needs_route_clarification" != decision.kind


def test_route_status_reports_matched_after_auto_disambiguation():
    decision = evaluate_request_policy(
        _AMBIGUOUS_QUERY,
        workspace_mode_id="custom",
    )
    assert decision.route_status == "matched"


def test_clear_single_match_is_untouched():
    decision = evaluate_request_policy(
        "写一份标书",
        workspace_mode_id="custom",
    )
    assert decision.kind == POLICY_DOCUMENT_ACTION
    assert decision.route is not None
    assert decision.route.route_id == "bidding_document_authoring"
