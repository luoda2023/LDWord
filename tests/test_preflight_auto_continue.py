# -*- coding: utf-8 -*-
"""Regression tests for preflight → execution auto-continue.

When a local preflight passes cleanly the assistant should flow straight from
the single “生成 Word” click into producing the finished document, instead of
stopping on a second “确认并生成 Word” approval card.  A confirmation gate is
kept only when the user's eyes are genuinely needed: overwriting an existing
output file, or an exam candidate version offered for review.
"""

from src.assistant.contracts.execution import PreflightReceipt
from src.assistant.ui.document_workflow_mixin import (
    AssistantDocumentWorkflowMixin,
)


def _receipt(*warnings):
    return PreflightReceipt(
        preflight_id="preflight-x",
        plan_id="plan-x",
        plan_revision=1,
        plan_fingerprint="fp",
        input_hash="h",
        material_snapshot_digest="d",
        output_root="C:/out",
        ready=True,
        warnings=tuple(warnings),
    )


class _OutputPolicy:
    def __init__(self, overwrite):
        self.overwrite = overwrite


class _Plan:
    def __init__(self, overwrite=False):
        self.output_policy = _OutputPolicy(overwrite=overwrite)


def _host():
    return object.__new__(AssistantDocumentWorkflowMixin)


def test_clean_pass_auto_continues():
    assert _host()._preflight_needs_confirmation(
        _Plan(), _receipt()
    ) is False


def test_non_blocking_warning_does_not_gate():
    # A harmless informational warning should not force a confirmation card.
    assert _host()._preflight_needs_confirmation(
        _Plan(),
        _receipt("官方版式已应用"),
    ) is False


def test_overwrite_replacement_gates_confirmation():
    assert _host()._preflight_needs_confirmation(
        _Plan(overwrite=True), _receipt()
    ) is True


def test_output_replacement_requested_warning_gates():
    assert _host()._preflight_needs_confirmation(
        _Plan(),
        _receipt("output_replacement_requested"),
    ) is True


def test_exam_review_candidate_gates():
    assert _host()._preflight_needs_confirmation(
        _Plan(),
        _receipt("exam_source_warning:missing_paper_title"),
    ) is True
