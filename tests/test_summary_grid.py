import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui.summary_grid import SummaryGrid, SummaryGridItem
from src.shared.ui.template_summary_card import (
    DetailSummaryCard,
    TemplateSummaryCard,
    apply_detail_summary_action_button,
    apply_template_summary_action_button,
)
from src.shared.ui.template_summary_header import DetailSummaryHeader, TemplateSummaryHeader
from src.shared.ui.theme import get_theme


def _app():
    return QApplication.instance() or QApplication([])


def test_module_summary_grid_gap_uses_global_16px_rhythm_token():
    theme = get_theme()

    assert theme.module_summary_grid_gap == theme.template_detail_section_gap == theme.spacing_lg == 16


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
        assert grid.tooltip_for("text") == "文字样式\n宋体 / Times New Roman\n字号 小四  字形 常规"
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


def test_summary_grid_module_style_keeps_empty_detail_row_as_alignment_placeholder():
    app = _app()
    grid = SummaryGrid(columns=1, tile_style="module")

    try:
        grid.set_items(
            [
                SummaryGridItem(
                    key="border",
                    label="边框与布局",
                    value="三线表 / 智能布局",
                    detail="",
                    icon_name="table-2",
                )
            ]
        )
        grid.show()
        app.processEvents()

        tile = grid._tiles["border"]
        theme = get_theme()

        assert tile._detail.isVisible()
        assert tile._detail.minimumHeight() == theme.module_summary_body_line_height
    finally:
        grid.close()


def test_summary_grid_module_style_elides_long_value_inside_compact_tile():
    app = _app()
    grid = SummaryGrid(columns=12, tile_style="module", layout_policy="single_row_preferred")

    try:
        grid.resize(720, 240)
        grid.set_items(
            [
                SummaryGridItem(
                    key="border",
                    label="边框与布局",
                    value="三线表 / 智能布局",
                    detail="不跨页重复表头",
                    column_span=4,
                    icon_name="table-2",
                ),
                SummaryGridItem(
                    key="width",
                    label="宽度与间距",
                    value="跟随页面宽度",
                    detail="单元格边距 0.2cm",
                    column_span=4,
                    icon_name="maximize",
                ),
                SummaryGridItem(
                    key="type",
                    label="字体与对齐",
                    value="微软雅黑 / Times New Roman",
                    detail="10.5 磅 / 表格居中",
                    column_span=4,
                    icon_name="type-outline",
                ),
            ]
        )
        grid.show()
        app.processEvents()
        app.processEvents()

        tile = grid._tiles["type"]
        assert grid._render_columns == 6
        assert tile._value.wordWrap() is False
        assert tile._value.full_text == "微软雅黑 / Times New Roman"
        assert tile._value.text().endswith("Times...")
        assert "New" not in tile._value.text()
        assert "Roman" not in tile._value.text()
        assert tile._value.maximumHeight() == get_theme().module_summary_body_line_height
        assert tile.toolTip().startswith("字体与对齐\n微软雅黑 / Times New Roman")
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


def test_summary_grid_single_row_preferred_distributes_common_tile_counts():
    app = _app()
    grid = SummaryGrid(columns=12, tile_style="module", layout_policy="single_row_preferred")

    try:
        grid.set_items(
            [
                SummaryGridItem(key=f"item_{index}", label=f"Item {index}", value="Value")
                for index in range(5)
            ]
        )
        grid.resize(1280, 240)
        grid.show()
        app.processEvents()

        assert grid._render_columns == 12
        assert grid._layout.itemAtPosition(0, 0).widget() is grid._tiles["item_0"]
        assert grid._layout.itemAtPosition(0, 2).widget() is grid._tiles["item_1"]
        assert grid._layout.itemAtPosition(0, 4).widget() is grid._tiles["item_2"]
        assert grid._layout.itemAtPosition(0, 6).widget() is grid._tiles["item_3"]
        assert grid._layout.itemAtPosition(0, 9).widget() is grid._tiles["item_4"]
        assert grid._tiles["item_0"].toolTip() == "Item 0\nValue"
    finally:
        grid.close()


def test_summary_grid_single_row_preferred_scales_explicit_spans_on_medium_width():
    app = _app()
    grid = SummaryGrid(columns=12, tile_style="module", layout_policy="single_row_preferred")

    try:
        grid.resize(994, 240)
        grid.set_items(
            [
                SummaryGridItem(key="paper", label="Paper", value="A4", column_span=4),
                SummaryGridItem(key="margin", label="Margin", value="3.8", column_span=4),
                SummaryGridItem(key="header", label="Header", value="3", column_span=4),
            ]
        )
        grid.show()
        app.processEvents()

        assert grid._render_columns == 6
        assert grid._layout.itemAtPosition(0, 0).widget() is grid._tiles["paper"]
        assert grid._layout.itemAtPosition(0, 2).widget() is grid._tiles["margin"]
        assert grid._layout.itemAtPosition(0, 4).widget() is grid._tiles["header"]
        assert grid._layout.itemAtPosition(1, 0) is None
    finally:
        grid.close()


def test_summary_grid_single_row_preferred_keeps_three_columns_at_high_dpi_screenshot_width():
    app = _app()
    grid = SummaryGrid(columns=12, tile_style="module", layout_policy="single_row_preferred")

    try:
        grid.resize(816, 240)
        grid.set_items(
            [
                SummaryGridItem(key="scheme", label="Scheme", value="Custom", column_span=4),
                SummaryGridItem(key="levels", label="Levels", value="4", column_span=4),
                SummaryGridItem(key="rules", label="Rules", value="12", column_span=4),
            ]
        )
        grid.show()
        app.processEvents()

        assert grid._render_columns == 6
        assert grid._layout.itemAtPosition(0, 0).widget() is grid._tiles["scheme"]
        assert grid._layout.itemAtPosition(0, 2).widget() is grid._tiles["levels"]
        assert grid._layout.itemAtPosition(0, 4).widget() is grid._tiles["rules"]
        assert grid._layout.itemAtPosition(1, 0) is None
    finally:
        grid.close()


def test_summary_grid_single_row_preferred_collapses_on_narrow_width():
    app = _app()
    grid = SummaryGrid(columns=12, tile_style="module", layout_policy="single_row_preferred")

    try:
        grid.resize(320, 300)
        grid.set_items(
            [
                SummaryGridItem(key="ready", label="准备情况", value="还缺资料", column_span=4),
                SummaryGridItem(key="fields", label="资料", value="0 项", column_span=4),
                SummaryGridItem(key="copies", label="生成份数", value="1 份", column_span=4),
            ]
        )
        grid.show()
        app.processEvents()

        assert grid._render_columns == 1
        assert grid._layout.itemAtPosition(0, 0).widget() is grid._tiles["ready"]
        assert grid._layout.itemAtPosition(1, 0).widget() is grid._tiles["fields"]
        assert grid._layout.itemAtPosition(2, 0).widget() is grid._tiles["copies"]
    finally:
        grid.close()


def test_template_summary_card_height_is_stable_on_first_narrow_layout():
    app = _app()
    card = TemplateSummaryCard("Summary", "ruler")

    try:
        card.resize(694, 180)
        card.set_summary_items(
            [
                SummaryGridItem(key="paper", label="Paper", value="A4", column_span=4),
                SummaryGridItem(key="margin", label="Margin", value="3.8", column_span=4),
                SummaryGridItem(key="header", label="Header", value="3", column_span=4),
            ]
        )

        theme = get_theme()
        margins = card.layout().contentsMargins()
        expected_height = (
            margins.top()
            + card.header.sizeHint().height()
            + card._content_layout.spacing()
            + 3 * theme.module_summary_tile_min_height
            + 2 * theme.module_summary_grid_gap
            + margins.bottom()
        )

        assert card._content_height_hint() == expected_height
        assert card.minimumHeight() == expected_height
        assert card.maximumHeight() >= expected_height
        assert card.sizeHint().height() == expected_height

        card.show()
        app.processEvents()
        first_height = card.height()
        first_grid_hint = card.summary_grid.sizeHint().height()
        app.processEvents()

        assert first_height == expected_height
        assert card.height() == first_height
        assert card.summary_grid.sizeHint().height() == first_grid_hint
    finally:
        card.close()
        app.processEvents()


def test_template_summary_card_keeps_detail_summary_card_compatibility():
    assert issubclass(TemplateSummaryCard, DetailSummaryCard)


def test_detail_summary_card_hides_empty_summary_grid():
    _app()
    card = DetailSummaryCard("Summary", "ruler")
    try:
        assert card.summary_grid.isHidden() is True

        card.set_summary_items(
            [SummaryGridItem(key="paper", label="Paper", value="A4")]
        )
        assert card.summary_grid.isHidden() is False

        card.set_summary_items(())
        assert card.summary_grid.isHidden() is True
    finally:
        card.close()


def test_template_summary_header_keeps_detail_summary_header_compatibility():
    assert TemplateSummaryHeader is DetailSummaryHeader


def test_detail_summary_card_uses_detail_summary_header():
    _app()
    card = DetailSummaryCard("Summary", "ruler")
    try:
        assert isinstance(card.header, DetailSummaryHeader)
        assert isinstance(card.header, TemplateSummaryHeader)
        assert card.header.title_label.objectName() == "detail_summary_header_title"
    finally:
        card.close()


def test_template_summary_action_button_keeps_detail_action_button_compatibility():
    assert apply_template_summary_action_button is apply_detail_summary_action_button
