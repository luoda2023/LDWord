import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.ui import DesignSystemCard, SurfaceCard
from src.shared.ui.rounded_surface import RoundedSurfaceFrame
from src.ui.panels.workbench.heading_quick_card import HeadingQuickCard
from src.ui.panels.workbench.quick_fill_card import QuickFillCard
from src.ui.panels.workbench.strategy_card import StrategyCard


def test_surface_card_uses_shared_design_system_card_pipeline(qapp):
    source = inspect.getsource(DesignSystemCard)

    assert issubclass(SurfaceCard, RoundedSurfaceFrame)
    assert issubclass(SurfaceCard, DesignSystemCard)
    assert "configure_surface(" in source
    card = SurfaceCard()
    try:
        assert card.graphicsEffect() is None
    finally:
        card.deleteLater()
    assert "card_padding_x" in source
    assert "card_padding_top" in source


def test_surface_card_is_exported_from_shared_ui():
    assert SurfaceCard is DesignSystemCard


def test_rounded_surface_accepts_qss_rgba_colors(qapp):
    surface = RoundedSurfaceFrame()
    try:
        surface.configure_surface(
            background="rgba(33, 120, 255, 0.020)",
            radius=8,
        )
        assert surface._background.isValid()
        assert surface._background.red() == 33
        assert surface._background.green() == 120
        assert surface._background.blue() == 255
        assert surface._background.alpha() == 5
    finally:
        surface.deleteLater()


def test_low_risk_workbench_cards_now_use_parallel_surface_card_base():
    assert issubclass(HeadingQuickCard, SurfaceCard)
    assert issubclass(QuickFillCard, SurfaceCard)
    assert issubclass(StrategyCard, SurfaceCard)
