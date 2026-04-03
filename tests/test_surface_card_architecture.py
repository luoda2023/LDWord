import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.ui import SurfaceCard
from src.shared.ui.rounded_surface import RoundedSurfaceFrame
from src.ui.panels.workbench.heading_quick_card import HeadingQuickCard
from src.ui.panels.workbench.quick_fill_card import QuickFillCard
from src.ui.panels.workbench.strategy_card import StrategyCard


def test_surface_card_uses_shared_surface_pipeline_without_touching_legacy_card():
    source = inspect.getsource(SurfaceCard)

    assert issubclass(SurfaceCard, RoundedSurfaceFrame)
    assert "configure_surface(" in source
    assert "QGraphicsDropShadowEffect" in source
    assert "card_padding_x" in source
    assert "card_padding_top" in source


def test_surface_card_is_exported_from_shared_ui():
    assert SurfaceCard.__name__ == "SurfaceCard"


def test_low_risk_workbench_cards_now_use_parallel_surface_card_base():
    assert issubclass(HeadingQuickCard, SurfaceCard)
    assert issubclass(QuickFillCard, SurfaceCard)
    assert issubclass(StrategyCard, SurfaceCard)
