"""Regression tests for IndentInput.set_reference_size() invariants.

These tests guard the contract that changing the font size (reference size)
must NOT silently alter the user-visible indent value when the unit is
"chars", and must NOT alter the canonical pt value when the unit is "pt"
or "cm".

See: coupling_audit.md — Problem #1 & #2.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui.paragraph_style_inputs import IndentInput, SpecialIndentInput


def _app():
    return QApplication.instance() or QApplication([])


# ──────────────────────────────────────────────────────────
# IndentInput — chars unit: display value must survive
# ──────────────────────────────────────────────────────────

def test_indent_input_chars_unit_preserved_after_reference_size_change():
    """Core invariant: '首行缩进 2字' stays 2字 when font size changes."""
    _app()
    w = IndentInput(reference_size_pt=12.0)
    w.set_value(2.0, "chars")

    assert w.value() == 2.0
    assert w.unit() == "chars"

    # Change font size from 12pt to 42pt
    w.set_reference_size(42.0)

    # The user-visible character count must NOT change.
    assert w.value() == 2.0, (
        f"Changing reference size should preserve char count, got {w.value()}"
    )
    assert w.unit() == "chars"


def test_indent_input_chars_preserved_across_many_size_changes():
    """Ensure repeated reference size changes don't accumulate drift."""
    _app()
    w = IndentInput(reference_size_pt=12.0)
    w.set_value(2.0, "chars")

    for pt in [14.0, 18.0, 42.0, 5.0, 72.0, 12.0]:
        w.set_reference_size(pt)
        assert abs(w.value() - 2.0) < 0.01, (
            f"After set_reference_size({pt}), value drifted to {w.value()}"
        )


def test_indent_input_zero_chars_stays_zero():
    """Edge case: 0 chars must stay 0 regardless of font size."""
    _app()
    w = IndentInput(reference_size_pt=12.0)
    w.set_value(0.0, "chars")

    w.set_reference_size(42.0)
    assert w.value() == 0.0


# ──────────────────────────────────────────────────────────
# IndentInput — pt unit: canonical pt must survive
# ──────────────────────────────────────────────────────────

def test_indent_input_pt_unit_preserved_after_reference_size_change():
    """When unit is 'pt', the physical pt value must NOT change."""
    _app()
    w = IndentInput(reference_size_pt=12.0)
    w.set_value(24.0, "pt")

    assert w.value() == 24.0
    assert w.unit() == "pt"

    w.set_reference_size(42.0)

    assert w.value() == 24.0, (
        f"pt value should be preserved, got {w.value()}"
    )


def test_indent_input_cm_unit_preserved_after_reference_size_change():
    """When unit is 'cm', the physical cm value must NOT change."""
    _app()
    w = IndentInput(reference_size_pt=12.0)
    w.set_value(2.54, "cm")

    original_value = w.value()

    w.set_reference_size(42.0)

    assert abs(w.value() - original_value) < 0.01, (
        f"cm value should be preserved, got {w.value()} (was {original_value})"
    )


# ──────────────────────────────────────────────────────────
# IndentInput — no-op when reference size unchanged
# ──────────────────────────────────────────────────────────

def test_indent_input_same_reference_size_is_noop():
    """set_reference_size with the same value should be a no-op."""
    _app()
    w = IndentInput(reference_size_pt=12.0)
    w.set_value(2.0, "chars")

    w.set_reference_size(12.0)
    assert w.value() == 2.0


# ──────────────────────────────────────────────────────────
# SpecialIndentInput — end-to-end
# ──────────────────────────────────────────────────────────

def test_special_indent_chars_preserved_after_reference_size_change():
    """SpecialIndentInput wraps IndentInput — same invariant applies."""
    _app()
    w = SpecialIndentInput(reference_size_pt=12.0)
    w.set_value("first_line", 2.0, "chars")

    assert w.mode() == "first_line"
    assert w.value() == 2.0

    w.set_reference_size(42.0)

    assert w.mode() == "first_line"
    assert w.value() == 2.0, (
        f"SpecialIndentInput char count should be preserved, got {w.value()}"
    )


# ──────────────────────────────────────────────────────────
# Data pollution guard: value() after set_reference_size
# must be safe to write back into config
# ──────────────────────────────────────────────────────────

def test_value_after_reference_size_change_is_safe_for_config_writeback():
    """Simulates _on_form_edited: read value() after set_reference_size.

    This guards against Problem #2 from the coupling audit: the value
    read after set_reference_size must equal what the user originally set.
    """
    _app()
    w = IndentInput(reference_size_pt=12.0)
    w.set_value(2.0, "chars")

    # Simulate what _on_form_edited does:
    # 1. set_reference_size (font changed)
    w.set_reference_size(42.0)
    # 2. read value() to write into config
    read_back_value = w.value()
    read_back_unit = w.unit()

    assert read_back_value == 2.0, (
        f"Config writeback would store {read_back_value} instead of 2.0 — data pollution!"
    )
    assert read_back_unit == "chars"
