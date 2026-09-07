# -*- coding: utf-8 -*-
"""Regression tests for the remembered one-time material authorization.

With "记住材料授权" enabled, a single manual approval is persisted and later
attachment runs skip the repeated disclosure card. Only *approval* is
remembered — a denial can never be remembered, and resetting clears the stored
decision while keeping the toggle itself.
"""

import pytest

from src.config import app_preferences as prefs


@pytest.fixture(autouse=True)
def _clean_state():
    prefs.set_material_disclosure_remember(False)
    prefs.reset_material_disclosure_remember()
    yield
    prefs.set_material_disclosure_remember(False)
    prefs.reset_material_disclosure_remember()


def test_defaults_ask_every_time():
    assert prefs.material_disclosure_remember() is False
    assert prefs.material_disclosure_approved() is False


def test_remembered_approval_roundtrip():
    prefs.set_material_disclosure_remember(True)
    prefs.set_material_disclosure_approved(True)
    assert prefs.material_disclosure_remember() is True
    assert prefs.material_disclosure_approved() is True


def test_reset_clears_approval_but_keeps_toggle():
    prefs.set_material_disclosure_remember(True)
    prefs.set_material_disclosure_approved(True)
    prefs.reset_material_disclosure_remember()
    assert prefs.material_disclosure_remember() is True
    assert prefs.material_disclosure_approved() is False


def test_auto_approve_gate_requires_both_flags():
    """The skip-card gate is remember AND approved — either alone is not enough."""
    prefs.set_material_disclosure_remember(True)
    assert (prefs.material_disclosure_remember() and prefs.material_disclosure_approved()) is False
    prefs.set_material_disclosure_approved(True)
    assert (prefs.material_disclosure_remember() and prefs.material_disclosure_approved()) is True
    prefs.reset_material_disclosure_remember()
    assert (prefs.material_disclosure_remember() and prefs.material_disclosure_approved()) is False
