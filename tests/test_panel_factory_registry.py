from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ui.panel_registry import PANEL_FACTORIES, PANEL_SPECS, create_panel


def test_every_first_level_destination_has_one_lazy_factory() -> None:
    assert set(PANEL_FACTORIES) == {spec.id for spec in PANEL_SPECS}
    assert all(spec.module_name for spec in PANEL_FACTORIES.values())
    assert all(spec.class_name for spec in PANEL_FACTORIES.values())


def test_unknown_panel_id_is_rejected_instead_of_silently_hidden() -> None:
    with pytest.raises(KeyError, match="Unknown panel id"):
        create_panel("missing-destination", object())
