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


def test_summary_grid_module_style_renders_icon_tile_without_changing_api():
    _app()
    grid = SummaryGrid(columns=1, tile_style="module")

    try:
        grid.set_items(
            [
                SummaryGridItem(
                    key="text",
                    label="文字样式",
                    value="宋体 / Times New Roman",
                    detail="字号 小四  字形 常规",
                    detail_emphasis=True,
                    icon_name="type-outline",
                )
            ]
        )

        tile = grid._tiles["text"]
        theme = get_theme()

        assert grid.value_for("text") == "宋体 / Times New Roman"
        assert grid.detail_for("text") == "字号 小四  字形 常规"
        assert tile._icon_container.width() == theme.module_summary_icon_container_size
        assert tile._label.font().pixelSize() == theme.module_summary_title_font_size
        assert tile._label.font().weight() == theme.font_weight_emphasis
        assert tile._value.font().pixelSize() == theme.font_size_md
        assert tile._detail.font().pixelSize() == theme.font_size_md
        assert tile._detail.font().weight() == theme.font_weight_normal
        assert tile.minimumHeight() == theme.module_summary_tile_min_height
        assert tile._label.minimumHeight() == theme.module_summary_title_line_height
        assert tile._value.minimumHeight() == theme.module_summary_body_line_height
        assert tile._text_layout.spacing() == theme.module_summary_content_spacing
        assert grid._layout.horizontalSpacing() == theme.module_summary_grid_gap
        assert grid._layout.verticalSpacing() == theme.module_summary_grid_gap
    finally:
        grid.close()


def test_summary_grid_module_style_keeps_fixed_single_row_layout():
    app = _app()
    grid = SummaryGrid(columns=6, tile_style="module")

    try:
        grid.set_items(
            [
                SummaryGridItem(key="text", label="文字样式", value="宋体", column_span=2, icon_name="type-outline"),
                SummaryGridItem(key="paragraph", label="对齐与缩进", value="两端对齐", column_span=2, icon_name="sliders-horizontal"),
                SummaryGridItem(key="spacing", label="行距与段距", value="多倍 2 倍", column_span=2, icon_name="sliders-horizontal"),
            ]
        )
        grid.resize(480, 300)
        grid.show()
        app.processEvents()

        assert grid._render_columns == 6
        assert grid._layout.itemAtPosition(0, 0).widget() is grid._tiles["text"]
        assert grid._layout.itemAtPosition(0, 2).widget() is grid._tiles["paragraph"]
        assert grid._layout.itemAtPosition(0, 4).widget() is grid._tiles["spacing"]
    finally:
        grid.close()
