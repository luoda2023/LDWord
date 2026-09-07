# -*- coding: utf-8 -*-
"""Regression tests for the auto-outline skip.

A fresh multi-chapter authoring request should skip the intermediate
“文档处理计划” plan card and land directly on the 章节目录 (outline_confirm)
card.  Exam / official authoring keeps its own intake editors, so those modes
must NOT auto-skip (they still present the classic plan card).  An
unconfigured provider must also fall back to the plan card instead of leaving
the user with nothing to press.
"""

from src.assistant.ui.document_workflow_mixin import (
    AssistantDocumentWorkflowMixin,
)


class _StubPlan:
    def __init__(self, *, mode_id, generation_required=True, blocking_issues=(), scene_ref=None):
        self.work_mode_id = mode_id
        self.generation_required = generation_required
        self.blocking_issues = tuple(blocking_issues)
        self.scene_ref = dict(scene_ref or {})


class _Session:
    provider_profile_id = "mock-default"


def _make_host(*, gateway_ok=True):
    class _Router:
        def resolve(self, profile_id, **kwargs):
            if not gateway_ok:
                from src.assistant.runtime.providers.router import (
                    ProviderResolutionError,
                )
                raise ProviderResolutionError("no gateway")
            return object()

    host = object.__new__(AssistantDocumentWorkflowMixin)
    host._fixed_turn_runner = None
    host._provider_router = _Router()
    host._active_session = None
    calls = []

    def _start_content_generation(session, plan, **kwargs):
        calls.append((session, plan, kwargs))

    host._start_content_generation = _start_content_generation
    return host, calls


def test_skips_for_engineering_authoring():
    host, calls = _make_host()
    session = _Session()
    plan = _StubPlan(mode_id="engineering")
    assert host._attempt_auto_outline(session, plan) is True
    assert len(calls) == 1
    assert calls[0][0] is session
    assert calls[0][1] is plan
    assert calls[0][2].get("outline_confirmed") is False


def test_keeps_plan_card_for_exam():
    host, calls = _make_host()
    plan = _StubPlan(mode_id="exam")
    assert host._attempt_auto_outline(_Session(), plan) is False
    assert calls == []


def test_keeps_plan_card_for_official():
    host, calls = _make_host()
    plan = _StubPlan(mode_id="official")
    assert host._attempt_auto_outline(_Session(), plan) is False
    assert calls == []


def test_falls_back_when_generation_not_required():
    host, calls = _make_host()
    plan = _StubPlan(mode_id="custom", generation_required=False)
    assert host._attempt_auto_outline(_Session(), plan) is False
    assert calls == []


def test_falls_back_on_blocking_issues():
    host, calls = _make_host()
    plan = _StubPlan(mode_id="engineering", blocking_issues=("issue",))
    assert host._attempt_auto_outline(_Session(), plan) is False
    assert calls == []


def test_falls_back_when_provider_unresolvable():
    host, calls = _make_host(gateway_ok=False)
    plan = _StubPlan(mode_id="engineering")
    assert host._attempt_auto_outline(_Session(), plan) is False
    assert calls == []
