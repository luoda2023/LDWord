import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui.summary_grid import SummaryGrid, SummaryGridItem
from src.shared.ui.theme import get_theme


def _app():
    return QApplication.instance() or QApplication([])


def test_summary_grid_detail_emphasis_uses_explicit_emphasis_font():
    _app()
    grid = SummaryGrid(columns=1)

    try:
        grid.set_items(
            [
                SummaryGridItem(
                    key="text",
                    label="Text",
                    value="Body",
                    detail="Size 14  Bold",
                    detail_emphasis=True,
                )
            ]
        )

        tile = grid._tiles["text"]
        theme = get_theme()

        assert tile._value.font().weight() == theme.font_weight_emphasis
        assert tile._value.font().pixelSize() == theme.font_size_md
        assert tile._detail.font().weight() == theme.font_weight_emphasis
        assert tile._detail.font().pixelSize() == theme.font_size_md
    finally:
        grid.close()


def test_summary_grid_non_emphasis_detail_keeps_secondary_font_tone():
    _app()
    grid = SummaryGrid(columns=1)

    try:
        grid.set_items(
            [
                SummaryGridItem(
                    key="spacing",
                    label="Spacing",
                    value="1.5x",
                    detail="Before 6  After 4",
                    detail_emphasis=False,
                )
            ]
        )

        tile = grid._tiles["spacing"]
        theme = get_theme()

        assert tile._detail.font().weight() == theme.font_weight_normal
        assert tile._detail.font().pixelSize() == theme.font_size_sm
    finally:
        grid.close()
