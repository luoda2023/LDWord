from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.workbench import WorkbenchPanel
from src.ui.panels.workbench.release_policy import (
    MATERIAL_SUITE_DELIVERY_CARD_ID,
    MATERIAL_SUITE_DELIVERY_RELEASED,
    RETIRED_WORKBENCH_CARD_IDS,
    is_workbench_card_released,
)


def _app():
    return QApplication.instance() or QApplication([])


def test_material_suite_delivery_requires_an_explicit_future_release() -> None:
    assert MATERIAL_SUITE_DELIVERY_RELEASED is False
    assert not is_workbench_card_released(MATERIAL_SUITE_DELIVERY_CARD_ID)


def test_retired_material_fill_destinations_can_never_be_released() -> None:
    assert RETIRED_WORKBENCH_CARD_IDS == {"content_fill", "quick_fill"}
    assert all(
        not is_workbench_card_released(card_id)
        for card_id in RETIRED_WORKBENCH_CARD_IDS
    )


def test_release_gate_blocks_accidental_suite_card_registration() -> None:
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        with pytest.raises(ValueError, match="not released"):
            panel._navigation.add_navigation_card(
                MATERIAL_SUITE_DELIVERY_CARD_ID
            )

        assert MATERIAL_SUITE_DELIVERY_CARD_ID not in panel._navigation_cards
        assert MATERIAL_SUITE_DELIVERY_CARD_ID not in panel._detail_map
        assert panel._suite_generation_detail is None
    finally:
        panel.close()


@pytest.mark.parametrize("card_id", ("content_fill", "quick_fill"))
def test_release_gate_blocks_retired_material_card_registration(card_id: str) -> None:
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        with pytest.raises(ValueError, match="not released"):
            panel._navigation.add_navigation_card(card_id)
        assert card_id not in panel._navigation_cards
        assert card_id not in panel._detail_map
    finally:
        panel.close()
