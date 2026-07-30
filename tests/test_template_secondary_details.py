import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QBoxLayout, QLabel, QPoint, QPushButton, Qt, QVBoxLayout, QWidget
from src.config.template import TemplateConfig
from src.shared.ui.adaptive_pair_row import AdaptivePairRow
from src.shared.ui.dashed_separator import DashedSeparator
from src.shared.ui.flow_layout import FlowLayout
from src.shared.ui.form_row import FormRow
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.table_style_gallery import ColorTableGallery
from src.shared.ui.template_form_layout import TemplateFormGrid, TemplateSplitColumns, template_form_row
from src.shared.ui.theme import LIGHT
from src.shared.ui.toggle_switch import ToggleSwitch
from src.ui.bridge import PanelBridge
from src.ui.panels.template_caption_detail import CaptionDetail
from src.ui.panels.template_elements_detail import ElementsDetail
from src.ui.panels.template_elements_page_plan import PageSelectorEditor, SUPPRESS_HEADER_FOOTER_SELECTOR_OPTIONS
from src.ui.panels.template_formula_detail import FormulaDetail
from src.ui.panels.template_other_detail import OtherDetail
from src.ui.panels.template_table_detail import TableCaptionDetail
from src.ui.panels.template_panel import TemplatePanel


def _app():
    return QApplication.instance() or QApplication([])


def test_table_and_elements_details_reuse_shared_controls():
    table_source = (ROOT / "src/ui/panels/template_table_detail.py").read_text(encoding="utf-8")
    elements_source = (ROOT / "src/ui/panels/template_elements_detail.py").read_text(encoding="utf-8")
    header_footer_source = (ROOT / "src/ui/panels/template_elements_header_footer.py").read_text(encoding="utf-8")
    page_plan_source = (ROOT / "src/ui/panels/template_elements_page_plan.py").read_text(encoding="utf-8")
    toc_source = (ROOT / "src/ui/panels/template_elements_toc.py").read_text(encoding="utf-8")

    assert "StyledComboBox(" in table_source
    assert "ToggleSwitch(" in table_source
    assert "TemplateSummaryCard(" in table_source
    assert "_build_summary_card()" in table_source
    assert "_build_editor_column(self)" in table_source
    assert "InspectorForm(" in table_source
    assert "TemplateFormGrid" in table_source
    assert "TemplateFormStack" in table_source
    assert "TemplateSplitColumns" not in table_source
    assert "template_form_row" in table_source
    assert "_pair_row(first_row_bold_row, repeat_header_row, self._table_alignment_row)" in table_source
    assert '("keep", "保留原样")' in table_source
    assert "编辑表格边框" not in table_source
    assert "先定义表格视觉预设" not in table_source
    assert "控制表格内文字" not in table_source
    assert "控制跨页时" not in table_source
    assert "本面板只覆盖" not in table_source
    assert "StyledComboBox(" in header_footer_source
    assert "StyledComboBox(" in toc_source
    assert "ToggleSwitch(" in header_footer_source
    assert "ToggleSwitch(" in toc_source
    assert "StyledSpinBox(" in page_plan_source
    assert "InspectorForm(" in header_footer_source
    assert ".add_grid(" in header_footer_source
    assert ".add_split_columns(" not in header_footer_source
    assert "_page_toggle_group" in header_footer_source
    assert "column_stretches=(0, 0, 0)" not in header_footer_source
    assert "template_form_row" in header_footer_source
    assert "TemplateSummaryCard(" in elements_source
    assert "_sync_dependent_state" in elements_source
    assert "findChildren(QLineEdit)" not in elements_source
    assert "class HeaderFooterDetailSection" in header_footer_source
    assert "class PageNumberPlanSection" in page_plan_source
    assert "class TocDetailSection" in toc_source
    assert "HeaderFooterDetailSection(self)" in elements_source
    assert "TocDetailSection(self)" in elements_source
    assert "self._header_footer_detail.set_header_footer(template.header_footer)" in elements_source
    assert "self._toc_detail.set_template(template)" in elements_source
    assert "Card(parent=owner._editor_column)" in header_footer_source
    assert "高级：Word 页眉页脚" not in header_footer_source
    assert "self._owner._add_card_header(self._page_variants_card" in header_footer_source
    assert header_footer_source.find("self._build_scheme_form()") < header_footer_source.find("self._build_page_variants_form()")
    assert "_header_enabled_toggle" in header_footer_source
    assert "_footer_enabled_toggle" in header_footer_source
    assert 'owner._add_card_header(self._scheme_card, "list", "页眉页脚预设")' in header_footer_source
    assert 'owner._add_card_header(self._normal_page_card, "panel-top", "页眉")' in header_footer_source
    assert 'owner._add_card_header(self._footer_card, "panel-bottom", "页脚")' in header_footer_source
    assert 'owner._add_card_header(self._page_number_card, "list-ordered", "页码")' in header_footer_source
    assert "PageNumberPlanSection(owner, container=self._page_number_card, embedded=True)" in header_footer_source
    assert 'FlowSection("编号分组", expanded=True' in page_plan_source
    assert 'FlowSection("高级规则编辑器"' not in page_plan_source
    assert "save_header_footer_user_preset" not in header_footer_source
    assert "delete_header_footer_user_preset" not in header_footer_source
    assert "Card(parent=owner._editor_column)" in toc_source
    assert '"toc_title"' in toc_source
    assert '"toc_level6"' in toc_source
    assert '"目录共享样式"' not in toc_source
    assert "HeadingNumberingPanel" not in toc_source
    assert "def effective_style" not in toc_source
    assert "def phase_rows_to_configs" in page_plan_source
    assert "def refresh_validation_alert" in page_plan_source


def test_template_table_typography_uses_main_form_baseline():
    app = _app()
    detail = TableCaptionDetail()

    try:
        detail.set_template(TemplateConfig())
        detail.resize(1280, 900)
        detail.show()
        app.processEvents()

        assert detail.findChildren(TemplateFormGrid)
        assert not detail._typography_card.findChildren(TemplateSplitColumns)

        row_map = {row.label_text: row for row in detail.findChildren(FormRow)}
        for label in ("中文字体", "英文字体"):
            row = row_map[label]
            visible_gap = row.widget.x() - row.label_width
            assert row._label.alignment() & Qt.AlignLeft
            assert not (row._label.alignment() & Qt.AlignRight)
            assert row.layout().spacing() == 4
            assert visible_gap <= 20
        for label in ("字号", "字形"):
            row = row_map[label]
            visible_gap = row.widget.x() - row.label_width
            assert row._label.alignment() & Qt.AlignRight
            assert not (row._label.alignment() & Qt.AlignLeft)
            assert row.layout().spacing() == 4
            assert visible_gap <= 20
        alignment_row = row_map["对齐"]
        assert alignment_row._label.alignment() & Qt.AlignLeft
        assert not (alignment_row._label.alignment() & Qt.AlignRight)
        font_cn_top = row_map["中文字体"].mapTo(detail, row_map["中文字体"].rect().topLeft()).y()
        size_top = row_map["字号"].mapTo(detail, row_map["字号"].rect().topLeft()).y()
        font_en_top = row_map["英文字体"].mapTo(detail, row_map["英文字体"].rect().topLeft()).y()
        emphasis_top = row_map["字形"].mapTo(detail, row_map["字形"].rect().topLeft()).y()
        alignment_top = row_map["对齐"].mapTo(detail, row_map["对齐"].rect().topLeft()).y()
        assert abs(font_cn_top - size_top) <= 4
        assert abs(font_en_top - emphasis_top) <= 4
        assert font_en_top > font_cn_top
        assert alignment_top > font_en_top
    finally:
        detail.close()
        app.processEvents()


def test_table_and_elements_summary_grids_use_module_thumbnail_style():
    app = _app()
    table_detail = TableCaptionDetail()
    elements_detail = ElementsDetail()
    toc_detail = ElementsDetail(scope="toc")

    try:
        template = TemplateConfig()
        table_detail.set_template(template)
        elements_detail.set_template(template)
        toc_detail.set_template(template)
        app.processEvents()

        table_items = {item.key: item for item in table_detail._summary_grid.items()}
        element_items = {item.key: item for item in elements_detail._summary_grid.items()}
        toc_items = {item.key: item for item in toc_detail._summary_grid.items()}

        assert table_detail._summary_grid._tile_style == "module"
        assert elements_detail._summary_grid._tile_style == "module"
        assert toc_detail._summary_grid._tile_style == "module"
        assert len(table_detail._summary_grid.items()) == 3
        assert table_items["border"].icon_name == "table-2"
        assert table_items["width"].icon_name == "ruler"
        assert table_items["type"].icon_name == "type-outline"
        assert element_items["header"].icon_name == "panel-top"
        assert element_items["page_number"].icon_name == "list-ordered"
        assert element_items["toc"].icon_name == "chart-no-axes-gantt"
        assert element_items["toc_style"].icon_name == "type-outline"
        assert toc_items["toc"].icon_name == "chart-no-axes-gantt"
        assert toc_items["toc_style"].icon_name == "type-outline"
    finally:
        table_detail.close()
        elements_detail.close()
        toc_detail.close()
        app.processEvents()


def test_template_table_border_layout_uses_one_label_baseline():
    app = _app()
    detail = TableCaptionDetail()

    try:
        detail.set_template(TemplateConfig())
        detail.resize(1280, 900)
        detail.show()
        app.processEvents()

        row_map = {row.label_text: row for row in detail.findChildren(FormRow)}
        labels = ("边框样式", "布局", "智能层级", "外线宽", "表头下线", "表格行距")
        label_widths = {row_map[label].label_width for label in labels}

        assert len(label_widths) == 1
        label_width = label_widths.pop()
        assert detail._color_gallery._label_width_override == label_width
        assert detail._color_gallery._label.width() == label_width
        assert row_map["外线宽"].widget.x() == row_map["边框样式"].widget.x()
        assert row_map["表头下线"].widget.x() == row_map["布局"].widget.x()
    finally:
        detail.close()
        app.processEvents()


def test_template_table_three_line_width_pair_keeps_height_when_restored():
    app = _app()
    detail = TableCaptionDetail()

    def assert_visible_pair_has_height() -> None:
        pair = detail._three_line_width_pair
        assert pair.isHidden() is False
        assert pair.sizeHint().height() > 0
        assert pair.height() > 0

    try:
        detail.set_template(TemplateConfig())
        detail.resize(1280, 900)
        detail.show()
        app.processEvents()

        detail._border_combo.setCurrentIndex(detail._border_combo.findData("full_grid"))
        app.processEvents()
        detail._border_combo.setCurrentIndex(detail._border_combo.findData("three_line"))
        assert_visible_pair_has_height()
        app.processEvents()
        assert_visible_pair_has_height()

        detail._border_combo.setCurrentIndex(detail._border_combo.findData("color_table"))
        app.processEvents()
        detail._border_combo.setCurrentIndex(detail._border_combo.findData("three_line"))
        assert_visible_pair_has_height()
        app.processEvents()
        assert_visible_pair_has_height()
    finally:
        detail.close()
        app.processEvents()


def test_template_form_grid_packs_short_fixed_controls_when_requested():
    app = _app()
    host = QWidget()
    rows = [
        template_form_row("页码", ToggleSwitch(host), parent=host),
        template_form_row("页眉线", ToggleSwitch(host), parent=host),
        template_form_row("不显示分区", ToggleSwitch(host), parent=host),
    ]
    grid = TemplateFormGrid(
        [rows],
        parent=host,
        column_gap=LIGHT.form_grid_compact_column_gap,
        column_stretches=(0, 0, 0),
    )
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(grid)

    try:
        host.resize(900, 120)
        host.show()
        app.processEvents()

        assert len({row.label_width for row in rows}) == 1
        assert all(row.widget.x() <= row.label_width + 12 for row in rows)
        assert rows[2].mapTo(host, rows[2].rect().topRight()).x() < 460
    finally:
        host.close()
        app.processEvents()


def test_template_form_grid_defaults_to_standard_column_gap():
    app = _app()
    host = QWidget()
    left = template_form_row("Left", QWidget(host), parent=host)
    right = template_form_row("Right", QWidget(host), parent=host)
    grid = TemplateFormGrid([[left, right]], parent=host)
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(grid)

    try:
        host.resize(900, 120)
        host.show()
        app.processEvents()

        assert grid._column_gap == LIGHT.form_grid_column_gap
        assert left._label.alignment() & Qt.AlignLeft
        assert right._label.alignment() & Qt.AlignRight
        left_right = left.mapTo(host, left.rect().topRight()).x()
        right_left = right.mapTo(host, right.rect().topLeft()).x()
        assert right_left - left_right >= LIGHT.form_grid_column_gap - 1
    finally:
        host.close()
        app.processEvents()


def test_adaptive_pair_row_ignores_hidden_children_when_resolving_direction():
    app = _app()
    left = QPushButton("long long long control")
    right = QPushButton("long long long control")
    optional = QPushButton("long long long control")
    row = AdaptivePairRow(left, right, optional, spacing=12)

    try:
        row.resize(620, 120)
        row.show()
        app.processEvents()

        assert row.layout().direction() == QBoxLayout.TopToBottom

        optional.hide()
        app.processEvents()
        assert row.layout().direction() == QBoxLayout.LeftToRight
    finally:
        row.close()
        app.processEvents()


def test_inspector_form_standard_grid_uses_standard_column_gap():
    app = _app()
    host = QWidget()
    form = InspectorForm(parent=host)
    left = template_form_row("Left", QWidget(host), parent=form)
    right = template_form_row("Right", QWidget(host), parent=form)
    grid = form.add_grid([[left, right]])
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(form)

    try:
        host.resize(900, 120)
        host.show()
        app.processEvents()

        assert grid._column_gap == LIGHT.form_grid_column_gap
    finally:
        host.close()
        app.processEvents()


def test_inspector_form_keeps_short_fixed_pairs_compact():
    app = _app()
    host = QWidget()
    form = InspectorForm(parent=host)
    rows = [
        template_form_row("A", ToggleSwitch(host), parent=form),
        template_form_row("B", ToggleSwitch(host), parent=form),
        template_form_row("C", ToggleSwitch(host), parent=form),
    ]
    grid = form.add_pair(*rows, column_stretches=(0, 0, 0))
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(form)

    try:
        host.resize(900, 120)
        host.show()
        app.processEvents()

        assert grid._column_gap == LIGHT.form_grid_compact_column_gap
        assert all(row._label.alignment() & Qt.AlignLeft for row in rows)
    finally:
        host.close()
        app.processEvents()


def test_template_form_grid_defaults_to_no_horizontal_separators():
    _app()
    host = QWidget()
    grid = TemplateFormGrid(
        [
            [
                template_form_row("中文字体", QWidget(host), parent=host),
                template_form_row("字号", QWidget(host), parent=host),
            ],
            [
                template_form_row("英文字体", QWidget(host), parent=host),
                template_form_row("字形", QWidget(host), parent=host),
            ],
        ],
        parent=host,
    )
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(grid)

    try:
        assert not grid.findChildren(DashedSeparator)
    finally:
        host.close()


def test_template_form_grid_can_opt_into_horizontal_separators():
    _app()
    host = QWidget()
    grid = TemplateFormGrid(
        [
            [template_form_row("对齐", QWidget(host), parent=host)],
            [template_form_row("左缩进", QWidget(host), parent=host)],
        ],
        parent=host,
        show_row_separators=True,
    )
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(grid)

    try:
        separators = grid.findChildren(DashedSeparator)
        assert [separator.orientation() for separator in separators] == ["horizontal"]
    finally:
        host.close()


def test_template_split_columns_use_spacing_without_divider_by_default():
    _app()
    host = QWidget()
    split = TemplateSplitColumns(
        [template_form_row("宸︿晶", QWidget(host), parent=host)],
        [template_form_row("鍙充晶", QWidget(host), parent=host)],
        parent=host,
    )
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(split)

    try:
        assert not split.findChildren(DashedSeparator)
    finally:
        host.close()


def test_template_split_columns_can_opt_into_vertical_divider():
    _app()
    host = QWidget()
    split = TemplateSplitColumns(
        [template_form_row("宸︿晶", QWidget(host), parent=host)],
        [template_form_row("鍙充晶", QWidget(host), parent=host)],
        parent=host,
        show_divider=True,
    )
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(split)

    try:
        separators = split.findChildren(DashedSeparator)
        assert [separator.orientation() for separator in separators] == ["vertical"]
    finally:
        host.close()


def test_inspector_form_normalizes_single_grid_and_split_rows_in_one_scope():
    app = _app()
    host = QWidget()
    form = InspectorForm(parent=host)
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(form)

    single_row = form.add_field("A", QWidget(form))
    grid_left = template_form_row("Longer label", QWidget(form), parent=form)
    grid_right = template_form_row("B", QWidget(form), parent=form)
    reserved_left = template_form_row("Reserved left", QWidget(form), parent=form)
    grid = form.add_grid(
        [
            [grid_left, grid_right],
            [reserved_left, None],
        ]
    )
    split_left = template_form_row("Longest inspector label", QWidget(form), parent=form)
    split_right = template_form_row("C", QWidget(form), parent=form)
    form.add_split_columns([split_left], [split_right])

    try:
        host.resize(960, 260)
        host.show()
        app.processEvents()

        rows = (single_row, grid_left, grid_right, reserved_left, split_left, split_right)
        expected = max(row.preferred_label_width() for row in rows)
        assert {row.label_width for row in rows} == {expected}
        assert len(grid._rows[1]) == 1
        assert reserved_left.width() == grid.width()
    finally:
        host.close()
        app.processEvents()


def test_template_elements_header_footer_uses_main_form_baseline():
    app = _app()
    detail = ElementsDetail()

    try:
        detail.set_template(TemplateConfig())
        detail.resize(1280, 900)
        detail.show()
        app.processEvents()

        assert detail.findChildren(TemplateFormGrid)
        assert not detail._header_footer_detail.section.findChildren(TemplateSplitColumns)

        header_content_rows = (
            detail._header_footer_detail._header_mode_row,
            detail._header_footer_detail._header_alignment_row,
            detail._header_footer_detail._styleref_level_row,
            detail._header_footer_detail._header_text_row,
        )
        header_typography_rows = (
            detail._header_footer_detail._font_cn_row,
            detail._header_footer_detail._font_en_row,
            detail._header_footer_detail._size_row,
            detail._header_footer_detail._emphasis_row,
        )
        footer_typography_rows = (
            detail._header_footer_detail._footer_font_cn_row,
            detail._header_footer_detail._footer_font_en_row,
            detail._header_footer_detail._footer_size_row,
            detail._header_footer_detail._footer_emphasis_row,
        )
        expected_content_label_width = max(row.preferred_label_width() for row in header_content_rows)
        assert {row.label_width for row in header_content_rows} == {expected_content_label_width}
        expected_header_label_width = max(row.preferred_label_width() for row in header_typography_rows)
        assert {row.label_width for row in header_typography_rows} == {expected_header_label_width}
        expected_footer_label_width = max(row.preferred_label_width() for row in footer_typography_rows)
        assert {row.label_width for row in footer_typography_rows} == {expected_footer_label_width}
        assert detail._header_footer_detail._hide_cover_row.isHidden()
        assert detail._header_footer_detail._page_toggle_group.isHidden()
        assert (
            detail._header_footer_detail._suppress_selector_row.label_width
            == detail._header_footer_detail._suppress_selector_row.preferred_label_width()
        )
        assert detail._header_footer_detail._suppress_selector_row._label.alignment() & Qt.AlignTop
        font_cn_top = detail._header_footer_detail._font_cn_row.mapTo(
            detail, detail._header_footer_detail._font_cn_row.rect().topLeft()
        ).y()
        size_top = detail._header_footer_detail._size_row.mapTo(
            detail, detail._header_footer_detail._size_row.rect().topLeft()
        ).y()
        font_en_top = detail._header_footer_detail._font_en_row.mapTo(
            detail, detail._header_footer_detail._font_en_row.rect().topLeft()
        ).y()
        emphasis_top = detail._header_footer_detail._emphasis_row.mapTo(
            detail, detail._header_footer_detail._emphasis_row.rect().topLeft()
        ).y()
        assert abs(font_cn_top - size_top) <= 4
        assert abs(font_en_top - emphasis_top) <= 4
        assert font_en_top > font_cn_top
        assert len(detail._header_footer_detail._typography_grid._rows[1]) == 2
        assert len(detail._header_footer_detail._footer_typography_grid._rows[1]) == 2
        assert detail._header_footer_detail._font_en_row.width() == detail._header_footer_detail._font_cn_row.width()
        assert (
            detail._header_footer_detail._footer_font_en_row.width()
            == detail._header_footer_detail._footer_font_cn_row.width()
        )
        trailing_rows = {
            detail._header_footer_detail._header_alignment_row,
            detail._header_footer_detail._header_text_row,
            detail._header_footer_detail._size_row,
            detail._header_footer_detail._emphasis_row,
            detail._header_footer_detail._footer_size_row,
            detail._header_footer_detail._footer_emphasis_row,
        }
        for row in (*header_content_rows, *header_typography_rows, *footer_typography_rows):
            if row.isHidden():
                continue
            visible_gap = row.widget.x() - row.label_width
            if row in trailing_rows:
                assert row._label.alignment() & Qt.AlignRight
                assert not (row._label.alignment() & Qt.AlignLeft)
            else:
                assert row._label.alignment() & Qt.AlignLeft
                assert not (row._label.alignment() & Qt.AlignRight)
            assert row.layout().spacing() == 4
            assert visible_gap <= 20
    finally:
        detail.close()
        app.processEvents()


def test_header_footer_detail_writes_header_and_footer_typography_separately():
    app = _app()
    detail = ElementsDetail(scope="header_footer")

    try:
        template = TemplateConfig()
        detail.set_template(template)
        detail.resize(960, 900)
        detail.show()
        app.processEvents()

        header_footer = detail._header_footer_detail
        header_footer._font_cn_combo.set_font_name("黑体")
        header_footer._size_combo.set_pt(9)
        header_footer._bold_toggle.setChecked(True)
        header_footer._footer_font_cn_combo.set_font_name("宋体")
        header_footer._footer_size_combo.set_pt(11)
        header_footer._footer_italic_toggle.setChecked(True)
        app.processEvents()

        cfg = template.header_footer
        assert cfg.header.typography.font_cn == "黑体"
        assert cfg.header.typography.size_pt == 9
        assert cfg.header.typography.bold is True
        assert cfg.header.typography.italic is False
        assert cfg.footer.typography.font_cn == "宋体"
        assert cfg.footer.typography.size_pt == 11
        assert cfg.footer.typography.bold is False
        assert cfg.footer.typography.italic is True
    finally:
        detail.close()
        app.processEvents()


def test_header_footer_hidden_fixed_text_row_does_not_force_stacked_layout():
    app = _app()
    detail = ElementsDetail()

    try:
        detail.set_template(TemplateConfig())
        detail.resize(700, 800)
        detail.show()
        app.processEvents()

        normal_grid = detail._header_footer_detail._normal_page_grid
        rows = normal_grid.findChildren(AdaptivePairRow)
        assert len(rows) == 3
        assert all(row.layout().direction() == QBoxLayout.LeftToRight for row in rows)
        assert detail._header_footer_detail._header_alignment_row.isVisible()
        assert detail._header_footer_detail._header_text_row.isHidden()
        assert len(normal_grid._rows) == 3
        assert detail._header_footer_detail._header_mode_row.isVisible()
        assert detail._header_footer_detail._styleref_level_row.isVisible()
    finally:
        detail.close()
        app.processEvents()


def test_header_footer_hidden_footer_text_row_does_not_leave_blank_grid_row():
    app = _app()
    detail = ElementsDetail()

    try:
        detail.set_template(TemplateConfig())
        detail.resize(900, 800)
        detail.show()
        app.processEvents()

        footer_grid = detail._header_footer_detail._footer_grid
        assert len(footer_grid._rows) == 2
        assert detail._header_footer_detail._footer_text_row.isHidden()
        assert detail._header_footer_detail._bottom_text_mode_row.isVisible()
        assert detail._header_footer_detail._footer_alignment_row.isVisible()
    finally:
        detail.close()
        app.processEvents()


def test_header_footer_shows_scheme_preview_and_collapses_structure_settings():
    app = _app()
    detail = ElementsDetail()

    try:
        template = TemplateConfig()
        detail.set_template(template)
        detail.resize(960, 900)
        detail.show()
        app.processEvents()

        header_footer = detail._header_footer_detail
        assert header_footer._structure_section is header_footer._structure_card
        assert header_footer._structure_card.isVisible()
        assert header_footer._scheme_combo.currentData() in {"thesis", None}
        if header_footer._scheme_combo.currentData() is None:
            assert header_footer._scheme_combo.display_text() == "当前配置（自定义）"
        assert header_footer._scheme_note.isHidden()
        assert header_footer._quick_preview_label.isHidden()
        preview = header_footer._quick_preview_label.text()
        assert "顶部：跟随 1 级标题" in preview
        assert "底部文字：不显示" in preview
        assert "页码：全文阿拉伯从 1 起" in preview
        assert "排除：封面及声明页" in preview
        assert header_footer._exclusion_preset_row.isVisible()
        assert header_footer._exclusion_preset_combo.currentData() == "pre_numbering"
        assert header_footer._suppress_selector_row.isHidden()

        header_footer._scheme_combo.setCurrentIndex(header_footer._scheme_combo.findData("continuous"))
        app.processEvents()

        assert template.header_footer.suppress_header_footer_selectors == []
        assert template.header_footer.page_number_plan.phases[0].selectors == ["all_numbered_content"]
        preview = header_footer._quick_preview_label.text()
        assert "顶部：跟随 1 级标题" in preview
        assert "底部文字：不显示" in preview
        assert "页码：全文阿拉伯从 1 起" in preview
        assert "排除：" not in preview
        assert header_footer._exclusion_preset_row.isVisible()
        assert header_footer._exclusion_preset_combo.currentData() == "none"

        header_footer._scheme_combo.setCurrentIndex(header_footer._scheme_combo.findData("no_page_number"))
        app.processEvents()

        assert template.header_footer.footer.content_mode == "none"
        assert template.header_footer.suppress_header_footer_selectors == []
        assert template.header_footer.page_number_plan.phases[0].selectors == ["all_numbered_content"]
        assert header_footer._page_number_card.isHidden() is False
        assert header_footer._preset_row.isHidden() is False
        assert header_footer._numbering_mode_combo.currentData() == "continuous"
        assert header_footer._page_advanced_section.isHidden()
        preview = header_footer._quick_preview_label.text()
        assert "顶部：跟随 1 级标题" in preview
        assert "底部文字：不显示" in preview
        assert "页码：" not in preview

        header_footer._exclusion_preset_combo.setCurrentIndex(header_footer._exclusion_preset_combo.findData("pre_numbering"))
        app.processEvents()

        assert header_footer._scheme_combo.currentData() is None
        assert header_footer._scheme_combo.display_text() == "不显示页码（内置，已修改）"
    finally:
        detail.close()
        app.processEvents()


def test_header_footer_preset_management_is_folder_only():
    app = _app()
    detail = ElementsDetail(scope="header_footer")

    try:
        template = TemplateConfig()
        detail.set_template(template)
        detail.resize(960, 900)
        detail.show()
        app.processEvents()

        header_footer = detail._header_footer_detail
        assert header_footer._scheme_open_folder_btn.text() == "打开方案文件夹"
        assert not hasattr(header_footer, "_scheme_save_as_btn")
        assert not hasattr(header_footer, "_scheme_update_btn")
        assert not hasattr(header_footer, "_scheme_delete_btn")
        assert not hasattr(header_footer, "_on_scheme_save_as_requested")
        assert not hasattr(header_footer, "_on_scheme_update_requested")
        assert not hasattr(header_footer, "_on_scheme_delete_requested")
    finally:
        detail.close()
        app.processEvents()


def test_header_footer_preset_action_row_keeps_buttons_fully_visible():
    app = _app()
    detail = ElementsDetail(scope="header_footer")
    try:
        detail.set_template(TemplateConfig())
        detail.resize(960, 900)
        detail.show()
        app.processEvents()

        header_footer = detail._header_footer_detail
        buttons = (header_footer._scheme_open_folder_btn,)

        assert all(button.property("sizeClass") == "md" for button in buttons)
        assert header_footer._scheme_actions.layout().alignment() & Qt.AlignVCenter
        assert header_footer._scheme_actions.minimumHeight() >= max(
            button.sizeHint().height() for button in buttons
        )
        assert (
            header_footer._scheme_actions_row.minimumHeight()
            > header_footer._scheme_actions.minimumHeight()
        )
    finally:
        detail.close()
        app.processEvents()


def test_header_footer_section_exclusion_row_reclaims_height_after_toggle():
    app = _app()
    detail = ElementsDetail()

    try:
        detail.set_template(TemplateConfig())
        detail.resize(960, 1000)
        detail.show()
        app.processEvents()

        header_footer = detail._header_footer_detail
        card = header_footer._structure_card
        row = header_footer._suppress_selector_row
        editor = card.parentWidget()

        assert header_footer._exclusion_preset_row.isVisible()
        assert row.isHidden()
        header_footer._exclusion_preset_combo.setCurrentIndex(
            header_footer._exclusion_preset_combo.findData("custom")
        )
        app.processEvents()
        app.processEvents()

        assert row.isVisible()
        expanded_heights = (row.geometry().height(), card.geometry().height(), editor.geometry().height())

        header_footer._exclusion_preset_combo.setCurrentIndex(
            header_footer._exclusion_preset_combo.findData("none")
        )
        app.processEvents()
        app.processEvents()
        collapsed_heights = (row.geometry().height(), card.geometry().height(), editor.geometry().height())

        assert row.isHidden()
        assert expanded_heights[1] > collapsed_heights[1] + 40
        assert expanded_heights[2] > collapsed_heights[2] + 40

        header_footer._exclusion_preset_combo.setCurrentIndex(
            header_footer._exclusion_preset_combo.findData("custom")
        )
        app.processEvents()
        app.processEvents()
        reexpanded_heights = (row.geometry().height(), card.geometry().height(), editor.geometry().height())

        assert row.isVisible()
        assert reexpanded_heights[1] > collapsed_heights[1] + 40
        assert reexpanded_heights[2] > collapsed_heights[2] + 40
    finally:
        detail.close()
        app.processEvents()


def test_header_footer_section_exclusion_preset_and_custom_selectors_write_config():
    app = _app()
    detail = ElementsDetail(scope="header_footer")

    try:
        template = TemplateConfig()
        detail.set_template(template)
        detail.resize(960, 900)
        detail.show()
        app.processEvents()

        header_footer = detail._header_footer_detail
        header_footer._exclusion_preset_combo.setCurrentIndex(
            header_footer._exclusion_preset_combo.findData("cover")
        )
        app.processEvents()

        assert template.header_footer.suppress_header_footer_selectors == ["cover"]
        assert "排除：封面" in header_footer._quick_preview_label.text()

        header_footer._exclusion_preset_combo.setCurrentIndex(
            header_footer._exclusion_preset_combo.findData("custom")
        )
        app.processEvents()

        custom_index = header_footer._exclusion_preset_combo.findData("custom")
        assert header_footer._exclusion_preset_combo.itemText(custom_index) == "自选范围"
        assert header_footer._suppress_selector_row.isVisible()
        assert header_footer._suppress_selector_row.label_text == "选择范围"
        assert header_footer._suppress_selector_editor._custom_edit.isHidden()
        header_footer._suppress_selector_editor._selector_buttons["cover"].click()
        header_footer._suppress_selector_editor._selector_buttons["references"].click()
        header_footer._suppress_selector_editor._selector_buttons["appendix"].click()
        app.processEvents()

        assert template.header_footer.suppress_header_footer_selectors == ["references", "appendix"]
        preview = header_footer._quick_preview_label.text()
        assert "排除：参考文献、附录" in preview
    finally:
        detail.close()
        app.processEvents()


def test_template_caption_formula_other_details_share_single_label_baseline():
    app = _app()
    details = (
        (FormulaDetail(), ("公式字体", "公式字号", "块对齐", "编号方式", "统一间距")),
        (
            OtherDetail(),
            ("启用文字水印", "水印文字", "水印颜色", "旋转角度", "水印字号"),
        ),
    )

    try:
        for detail, labels in details:
            detail.set_template(TemplateConfig())
            detail.resize(1024, 800)
            detail.show()
            app.processEvents()

            row_map = {row.label_text: row for row in detail.findChildren(FormRow)}
            label_widths = {row_map[label].label_width for label in labels}

            assert len(label_widths) == 1
    finally:
        for detail, _labels in details:
            detail.close()
        app.processEvents()


def test_hidden_formula_and_watermark_editors_preserve_their_owned_fields():
    app = _app()
    formula = FormulaDetail()
    other = OtherDetail()
    template = TemplateConfig()
    try:
        formula.set_template(template)
        other.set_template(template)

        formula._table_alignment_combo.setCurrentIndex(
            formula._table_alignment_combo.findData("right")
        )
        formula._number_font_combo.set_font_name("Arial")
        formula._line_spacing.set_value(1.5, "multiple")
        formula._space_before.set_value(9.0, "pt")
        formula._auto_shrink_number.click()

        other._watermark_enabled.setChecked(True)
        other._watermark_text.setText("内部传阅")
        other._watermark_color.setText("#336699")
        other._watermark_rotation.setValue(-30)
        other._watermark_font_size.setValue(56)
        other._on_form_edited()
        app.processEvents()

        assert template.formula_table.table_alignment == "right"
        assert template.formula_table.number_font_name == "Arial"
        assert template.formula_table.formula_line_spacing == 1.5
        assert template.formula_table.formula_space_before_pt == 9.0
        assert template.formula_table.auto_shrink_number_column is False
        assert template.watermark.enabled is True
        assert template.watermark.text == "内部传阅"
        assert template.watermark.color == "#336699"
        assert template.watermark.rotation == -30
        assert template.watermark.font_size == 56
        assert not hasattr(template, "output")
        assert {item.key for item in formula._summary_card.summary_grid.items()} == {
            "formula_typography",
            "formula_layout",
            "formula_numbering",
        }
        assert {item.key for item in other._summary_card.summary_grid.items()} == {"watermark"}

        formula.set_save_enabled(True)
        other.set_save_enabled(True)
        formula._restore_btn.click()
        other._restore_btn.click()
        app.processEvents()

        assert template.formula_table.table_alignment == "center"
        assert template.formula_table.auto_shrink_number_column is True
        assert template.watermark.enabled is False
    finally:
        formula.close()
        other.close()
        app.processEvents()


def test_template_caption_detail_uses_semantic_cards_and_result_language():
    app = _app()
    detail = CaptionDetail()
    template = TemplateConfig()

    try:
        detail.set_template(template)
        detail.resize(1024, 900)
        detail.show()
        app.processEvents()

        assert detail._text_card is not detail._rules_card
        assert detail._rules_card is not detail._style_card
        assert not hasattr(detail, "_desc")
        assert not hasattr(detail, "_footer_note")

        assert [len(row) for row in detail._text_grid._rows] == [2, 2, 1, 1]
        assert [len(row) for row in detail._rules_grid._rows] == [2, 2]
        assert [len(row) for row in detail._style_grid._rows] == [2, 2, 2, 1, 2]
        assert detail._text_grid._rows[0] == (detail._figure_prefix_row, detail._table_prefix_row)
        assert detail._text_grid._rows[1] == (detail._separator_row, detail._placeholder_row)
        assert detail._rules_grid._rows[0] == (detail._numbering_mode_row, detail._numbering_format_row)
        assert detail._rules_grid._rows[1] == (detail._auto_insert_row, detail._numbering_type_row)
        assert detail._style_grid._rows[0] == (detail._font_cn_row, detail._size_row)
        assert detail._style_grid._rows[1] == (detail._font_en_row, detail._emphasis_row)

        row_map = {row.label_text: row for row in detail.findChildren(FormRow)}
        text_control_heights = {
            row_map[label].widget.height()
            for label in ("图题注前缀", "表题注前缀", "编号后间隔", "缺失题注标题")
        }
        assert len(text_control_heights) == 1
        for label in (
            "图题注前缀",
            "表题注前缀",
            "编号后间隔",
            "缺失题注标题",
            "编号范围",
            "显示格式",
            "缺失题注",
            "编号类型",
            "行距类型",
            "行距值",
        ):
            assert label in row_map
        for old_label in ("图前缀", "表前缀", "编号模式", "编号格式", "自动补题注", "域代码编号", "占位文本", "分隔符"):
            assert old_label not in row_map

        visible_texts = [child.text() for child in detail.findChildren(QLabel)]
        combo_texts = [
            combo.itemText(index)
            for combo in detail.findChildren(StyledComboBox)
            for index in range(combo.count())
        ]
        assert not any("域代码" in text or "caption" in text for text in [*visible_texts, *combo_texts])
        assert "Word 可更新编号" in combo_texts
        assert detail._separator_edit._mode_combo.currentText() == "全角空格（□）"
        assert detail._figure_preview_label.text() == "图1.1\u3000[待补充]"
        assert detail._table_preview_label.text() == "表1.1\u3000[待补充]"

        detail._numbering_format_combo.setCurrentIndex(detail._numbering_format_combo.findData("chapter-seq"))
        detail._separator_edit._mode_combo.setCurrentIndex(
            detail._separator_edit._mode_combo.findData("halfwidth_space")
        )
        detail._placeholder_edit.setText("示例标题")
        app.processEvents()

        assert detail._figure_preview_label.text() == "图1-1 示例标题"
        assert detail._table_preview_label.text() == "表1-1 示例标题"
        assert template.caption.separator == " "

        detail._separator_edit._mode_combo.setCurrentIndex(
            detail._separator_edit._mode_combo.findData("custom")
        )
        detail._separator_edit._custom_edit.setRawText(" - ")
        app.processEvents()

        assert template.caption.separator == " - "
        assert detail._figure_preview_label.text() == "图1-1 - 示例标题"

        detail._figure_prefix_edit.setText("Fig.")
        detail._table_prefix_edit.setText("Tab.")
        detail._numbering_mode_combo.setCurrentIndex(detail._numbering_mode_combo.findData("global"))
        detail._auto_insert_combo.setCurrentIndex(detail._auto_insert_combo.findData(False))
        detail._numbering_type_combo.setCurrentIndex(detail._numbering_type_combo.findData(True))
        app.processEvents()

        assert template.caption.figure_prefix == "Fig."
        assert template.caption.table_prefix == "Tab."
        assert template.caption.separator == " - "
        assert template.caption.placeholder == "示例标题"
        assert template.caption.numbering_format == "chapter-seq"
        assert template.caption.numbering_mode == "global"
        assert template.caption.auto_insert is False
        assert template.caption.format_inserted is True
    finally:
        detail.close()
        app.processEvents()


def test_template_toc_detail_uses_toc_level_style_editor_controls():
    app = _app()
    detail = ElementsDetail(scope="toc")

    try:
        detail.set_template(TemplateConfig())
        detail.resize(1280, 900)
        detail.show()
        app.processEvents()

        toc = detail._toc_detail
        structure_grids = toc.structure_section.findChildren(TemplateFormGrid)
        assert len(structure_grids) == 1
        assert [len(row) for row in structure_grids[0]._rows] == [2, 1]
        assert structure_grids[0]._align_trailing_labels is False

        assert not hasattr(toc, "_toc_preview_card")
        assert not hasattr(toc, "_toc_linkage_card")
        assert toc._toc_style_controls
        assert hasattr(toc, "_toc_style_editor_card")
        assert not hasattr(toc, "_toc_preset_combo")
        assert not hasattr(toc, "_toc_apply_preset_btn")
        assert hasattr(toc, "_toc_style_role_list")
        assert not hasattr(toc, "_toc_style_stack")
        assert toc._toc_styles_section.isVisible() is True
        assert hasattr(toc, "_toc_result_strip")
        assert hasattr(toc, "_toc_inline_preview")
        assert toc._toc_style_role_list.count() == 4
        assert toc._toc_style_role_list.item(0).data(Qt.UserRole) == "toc_title"
        assert toc._toc_style_role_list.item(1).data(Qt.UserRole) == "toc_level1"
    finally:
        detail.close()
        app.processEvents()


def test_template_toc_style_editor_pairs_rows_like_main_style_forms():
    app = _app()
    detail = ElementsDetail(scope="toc")

    try:
        detail.set_template(TemplateConfig())
        detail.resize(1280, 900)
        detail.show()
        app.processEvents()

        toc = detail._toc_detail
        assert toc._toc_style_list_frame.minimumWidth() == 230
        assert toc._toc_style_list_frame.maximumWidth() == 280
        content_layout = toc._toc_style_content.layout()
        sidebar = content_layout.itemAt(0).widget()
        inspector = content_layout.itemAt(1).widget()
        assert inspector.y() == sidebar.y()
        assert inspector.x() > sidebar.x() + sidebar.width()
        assert toc._toc_style_role_list.horizontalScrollBar().maximum() == 0
        assert toc._toc_style_grid._rows == [
            (toc._toc_font_cn_row, toc._toc_size_row),
            (toc._toc_font_en_row, toc._toc_emphasis_row),
            (toc._toc_alignment_row, toc._toc_special_indent_row),
            (toc._toc_left_indent_row, toc._toc_right_indent_row),
            (toc._toc_line_type_row, toc._toc_line_value_row),
            (toc._toc_space_before_row, toc._toc_space_after_row),
        ]
    finally:
        detail.close()
        app.processEvents()


def test_template_toc_role_list_rebuild_preserves_items_widgets_and_selection(
    monkeypatch,
):
    app = _app()
    detail = ElementsDetail(scope="toc")

    try:
        detail.set_template(TemplateConfig())
        toc = detail._toc_detail
        role_list = toc._toc_style_role_list
        role_list.setCurrentRow(2)
        app.processEvents()
        original_items = {
            item.data(Qt.UserRole): item
            for row in range(role_list.count())
            if (item := role_list.item(row)) is not None
        }
        original_widgets = {
            key: role_list.itemWidget(item)
            for key, item in original_items.items()
        }
        original_specs = toc._role_specs()
        spec_type = type(original_specs[0])
        monkeypatch.setattr(
            toc,
            "_role_specs",
            lambda: [
                spec_type(
                    spec.key,
                    "二级目录（更新）" if spec.key == "toc_level2" else spec.label,
                    "TOC Two" if spec.key == "toc_level2" else spec.word_style,
                )
                for spec in original_specs
            ],
        )

        toc._rebuild_role_list()

        assert role_list.currentItem().data(Qt.UserRole) == "toc_level2"
        assert all(
            toc._toc_role_items[key] is item
            for key, item in original_items.items()
        )
        assert all(
            role_list.itemWidget(toc._toc_role_items[key]) is widget
            for key, widget in original_widgets.items()
        )
        selected_widget = role_list.itemWidget(role_list.currentItem())
        assert selected_widget.findChild(QLabel, "toc_list_txt").text() == "二级目录（更新）"
        assert selected_widget.findChild(QLabel, "toc_list_lv").text() == "TOC Two"
    finally:
        detail.close()
        app.processEvents()


def test_template_toc_style_edit_updates_brief_without_rebuilding_role_row():
    app = _app()
    detail = ElementsDetail(scope="toc")

    try:
        detail.set_template(TemplateConfig())
        toc = detail._toc_detail
        role_list = toc._toc_style_role_list
        role_list.setCurrentRow(1)
        app.processEvents()
        item = role_list.currentItem()
        widget = role_list.itemWidget(item)
        title = widget.findChild(QLabel, "toc_list_txt")
        word_style = widget.findChild(QLabel, "toc_list_lv")
        meta = widget.findChild(QLabel, "toc_preview_meta")
        before_meta = meta.text()

        toc._toc_alignment_combo.setCurrentIndex(
            toc._toc_alignment_combo.findData("right")
        )
        app.processEvents()

        assert role_list.currentItem() is item
        assert role_list.itemWidget(item) is widget
        assert widget.findChild(QLabel, "toc_list_txt") is title
        assert widget.findChild(QLabel, "toc_list_lv") is word_style
        assert widget.findChild(QLabel, "toc_preview_meta") is meta
        assert title.text() == "1 级目录"
        assert word_style.text() == "TOC 1"
        assert meta.text() != before_meta
        assert meta.text().endswith("右对齐")
    finally:
        detail.close()
        app.processEvents()


def test_template_toc_depth_changes_only_add_and_remove_tail_roles():
    app = _app()
    detail = ElementsDetail(scope="toc")

    try:
        detail.set_template(TemplateConfig())
        toc = detail._toc_detail
        role_list = toc._toc_style_role_list
        role_list.setCurrentRow(2)
        app.processEvents()
        original_items = dict(toc._toc_role_items)
        original_widgets = dict(toc._toc_role_widgets)

        toc._toc_depth_combo.setCurrentIndex(toc._toc_depth_combo.findData(5))
        app.processEvents()

        assert list(toc._toc_role_items) == [
            "toc_title",
            "toc_level1",
            "toc_level2",
            "toc_level3",
            "toc_level4",
            "toc_level5",
        ]
        assert role_list.currentItem().data(Qt.UserRole) == "toc_level2"
        assert all(
            toc._toc_role_items[key] is item
            for key, item in original_items.items()
        )
        assert all(
            toc._toc_role_widgets[key] is widget
            for key, widget in original_widgets.items()
        )
        grown_items = dict(toc._toc_role_items)
        grown_widgets = dict(toc._toc_role_widgets)

        toc._toc_depth_combo.setCurrentIndex(toc._toc_depth_combo.findData(2))
        app.processEvents()

        assert list(toc._toc_role_items) == [
            "toc_title",
            "toc_level1",
            "toc_level2",
        ]
        assert role_list.currentItem().data(Qt.UserRole) == "toc_level2"
        assert all(
            toc._toc_role_items[key] is grown_items[key]
            for key in ("toc_title", "toc_level1", "toc_level2")
        )
        assert all(
            toc._toc_role_widgets[key] is grown_widgets[key]
            for key in ("toc_title", "toc_level1", "toc_level2")
        )
    finally:
        detail.close()
        app.processEvents()


def test_template_toc_style_editor_switches_all_pairs_as_one_responsive_group():
    app = _app()
    detail = ElementsDetail(scope="toc")

    try:
        detail.set_template(TemplateConfig())
        detail.resize(760, 900)
        detail.show()
        app.processEvents()
        app.processEvents()

        grid = detail._toc_detail._toc_style_grid
        assert all(row._forced_stacked is True for row in grid._pair_rows)

        detail.resize(848, 900)
        app.processEvents()
        app.processEvents()

        assert all(row._forced_stacked is False for row in grid._pair_rows)
    finally:
        detail.close()
        app.processEvents()


def test_template_toc_structure_edits_do_not_materialize_toc_style_overrides():
    app = _app()
    detail = ElementsDetail(scope="toc")

    try:
        template = TemplateConfig()
        detail.set_template(template)
        detail.resize(1280, 900)
        detail.show()
        app.processEvents()

        toc = detail._toc_detail
        toc._toc_depth_combo.setCurrentIndex(toc._toc_depth_combo.findData(4))
        app.processEvents()

        assert template.toc.max_level == 4
        assert template.heading_model.max_heading_levels == 4
        assert detail._toc_detail._toc_style_role_list.count() == 5
        assert not any(key.startswith("toc") for key in template.styles)
    finally:
        detail.close()
        app.processEvents()


def test_template_toc_style_editor_writes_toc_roles_not_heading_roles():
    app = _app()
    detail = ElementsDetail(scope="toc")

    try:
        template = TemplateConfig()
        detail.set_template(template)
        detail.resize(1280, 900)
        detail.show()
        app.processEvents()

        toc = detail._toc_detail
        toc._toc_style_role_list.setCurrentRow(1)
        toc._toc_size_combo.set_pt(18)
        app.processEvents()

        assert "toc_level1" in template.styles
        assert template.styles["toc_level1"].size_pt == 18
        assert "heading1" not in template.styles
    finally:
        detail.close()
        app.processEvents()


def test_template_toc_style_preview_tracks_selected_toc_role():
    app = _app()
    detail = ElementsDetail(scope="toc")

    try:
        template = TemplateConfig()
        detail.set_template(template)
        detail.resize(1280, 900)
        detail.show()
        app.processEvents()

        toc = detail._toc_detail
        assert toc._toc_inline_preview._role_key == "toc_title"

        toc._toc_style_role_list.setCurrentRow(2)
        app.processEvents()
        assert toc._toc_inline_preview._role_key == "toc_level2"

        toc._toc_size_combo.set_pt(18)
        app.processEvents()
        assert toc._toc_inline_preview._style.size_pt == 18
        assert "toc_level2" in template.styles
        assert "heading2" not in template.styles
    finally:
        detail.close()
        app.processEvents()


def test_template_elements_theme_does_not_restyle_embedded_combo_editors():
    app = _app()
    detail = ElementsDetail()

    def assert_embedded_editor_style(widget) -> None:
        editor = widget.lineEdit()
        assert editor is not None
        qss = editor.styleSheet()
        assert "border: none;" in qss
        assert "padding: 0;" in qss
        assert "border: 1px solid" not in qss
        assert "padding: 4px" not in qss

    try:
        detail.set_template(TemplateConfig())
        detail.resize(1280, 900)
        detail.show()
        detail.apply_theme()
        app.processEvents()

        assert "border: 1px solid" in detail._header_text_edit.styleSheet()

        assert_embedded_editor_style(detail._header_footer_detail._font_cn_combo)
        assert_embedded_editor_style(detail._header_footer_detail._font_en_combo)
        assert_embedded_editor_style(detail._header_footer_detail._size_combo)
    finally:
        detail.close()
        app.processEvents()


def test_page_selector_editor_uses_flow_chips_instead_of_fixed_grid():
    app = _app()
    editor = PageSelectorEditor(options=SUPPRESS_HEADER_FOOTER_SELECTOR_OPTIONS)

    try:
        editor.resize(760, 180)
        editor.show()
        app.processEvents()

        assert isinstance(editor._chips_layout, FlowLayout)
        assert editor._chips_layout.count() == len(SUPPRESS_HEADER_FOOTER_SELECTOR_OPTIONS)
        assert all(button.width() < 220 for button in editor._selector_buttons.values())
    finally:
        editor.close()
        app.processEvents()


def test_page_selector_editor_does_not_stretch_chips_into_blank_space():
    app = _app()
    root = QWidget()
    layout = QVBoxLayout(root)
    editor = PageSelectorEditor(options=SUPPRESS_HEADER_FOOTER_SELECTOR_OPTIONS)
    layout.addWidget(editor)

    try:
        root.resize(1080, 260)
        root.show()
        app.processEvents()

        expected_chips_height = editor._chips_layout.heightForWidth(editor._chips.width())
        assert editor._chips.height() <= expected_chips_height + 1
        assert editor._custom_edit.y() - editor._chips.geometry().bottom() <= editor.layout().spacing() + 2
    finally:
        root.close()
        app.processEvents()


def test_elements_detail_projects_default_page_number_phase_without_model_mutation():
    app = _app()
    detail = ElementsDetail()
    template = TemplateConfig()
    template.header_footer.page_number_plan.phases = []

    try:
        detail.set_template(template)
        detail.resize(960, 900)
        detail.show()
        app.processEvents()

        phases = template.header_footer.page_number_plan.phases
        assert phases == []
        projected = detail._header_footer_detail.phase_rows_to_configs()
        assert len(projected) == 1
        assert projected[0].phase_id == "main"
        assert projected[0].selectors == ["all_numbered_content"]
        assert projected[0].number_format == "decimal"
        assert detail._page_validation_mode_combo.isHidden()
        assert detail._page_missing_doc_tree_combo.isHidden()
        assert detail._page_validation_mode_combo.isVisible() is False
        assert detail._page_missing_doc_tree_combo.isVisible() is False
    finally:
        detail.close()
        app.processEvents()


def test_template_panel_elements_detail_summary_and_dependent_state():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        detail = panel._header_footer_detail
        toc_detail = panel._toc_detail

        assert "跟随" in detail._summary_grid.value_for("header")
        phase_row = detail._page_phase_rows[0]
        assert phase_row.section.is_expanded() is True
        assert "main" not in phase_row.section._toggle_button.text()
        assert "全文" in phase_row.section._toggle_button.text()
        assert detail._header_text_row.isHidden() is True
        assert detail._styleref_level_row.isHidden() is False

        detail._bold_toggle.click()
        detail._italic_toggle.click()
        app.processEvents()

        assert panel._current_template.header_footer.bold is True
        assert panel._current_template.header_footer.italic is True
        assert "\u52a0\u7c97\u3001\u659c\u4f53" in detail._summary_grid.detail_for("header")

        detail._header_mode_combo.setCurrentIndex(detail._header_mode_combo.findData("fixed"))
        detail._header_text_edit.setText("固定页眉")
        app.processEvents()

        assert panel._current_template.header_footer.header_mode == "fixed"
        assert detail._header_text_row.isHidden() is False
        assert detail._styleref_level_row.isHidden() is True
        assert detail._summary_grid.value_for("header") == "固定文字"
        assert "固定页眉" in detail._summary_grid.detail_for("header")

        detail._bottom_text_mode_combo.setCurrentIndex(detail._bottom_text_mode_combo.findData("none"))
        app.processEvents()

        assert panel._current_template.header_footer.page_number_enabled is False
        assert panel._current_template.header_footer.footer.content_mode == "none"
        assert detail._page_number_card.isHidden() is False
        assert detail._preset_row.isHidden() is False
        assert detail._numbering_mode_combo.currentData() == "continuous"
        assert detail._page_advanced_section.isHidden()
        assert detail._summary_grid.value_for("page_number") == "不显示页码"

        detail._bottom_text_mode_combo.setCurrentIndex(detail._bottom_text_mode_combo.findData("page_number_with_text"))
        detail._footer_text_edit.setText("Confidential")
        detail._footer_alignment_combo.setCurrentIndex(detail._footer_alignment_combo.findData("right"))
        app.processEvents()

        assert panel._current_template.header_footer.page_number_enabled is True
        assert panel._current_template.header_footer.footer.content_mode == "page_number_with_text"
        assert panel._current_template.header_footer.footer_text == "Confidential"
        assert panel._current_template.header_footer.footer_alignment == "right"
        assert detail._summary_grid.value_for("footer_text") == "固定文字"
        assert "Confidential" in detail._summary_grid.detail_for("footer_text")
        assert "页脚右侧" in detail._summary_grid.value_for("page_number")
        assert "全文阿拉伯数字从 1 起" in detail._summary_grid.detail_for("page_number")
        assert detail._preset_row.isHidden() is False

        detail._header_enabled_toggle.click()
        app.processEvents()

        assert panel._current_template.header_footer.header_enabled is False
        assert detail._header_mode_row.isEnabled() is False
        assert detail._styleref_level_row.isEnabled() is False
        assert detail._font_cn_row.isEnabled() is False
        assert detail._header_border_row.isEnabled() is False
        assert detail._summary_grid.value_for("header") == "页眉关闭"

        detail._footer_enabled_toggle.click()
        app.processEvents()

        assert panel._current_template.header_footer.footer_enabled is False
        assert panel._current_template.header_footer.footer.content_mode == "page_number_with_text"
        assert panel._current_template.header_footer.page_number_enabled is False
        assert detail._bottom_text_mode_row.isEnabled() is False
        assert detail._page_number_enabled_row.isEnabled() is False
        assert detail._footer_alignment_row.isEnabled() is False
        assert detail._footer_font_cn_row.isEnabled() is False
        assert detail._page_plan_section.isHidden() is False
        assert detail._preset_row.isEnabled() is False
        assert detail._page_advanced_section.isHidden()
        assert detail._summary_grid.value_for("footer_text") == "页脚关闭"
        assert detail._summary_grid.value_for("page_number") == "不显示页码"

        assert not hasattr(toc_detail, "_toc_enabled_toggle")
        assert toc_detail._toc_mode_row.isEnabled() is True
        assert toc_detail._toc_styles_section.isHidden() is False
        assert toc_detail._summary_grid.value_for("toc") != "目录关闭"
    finally:
        panel.close()
        app.processEvents()


def test_header_footer_reformat_toggle_off_keeps_configuration_visible():
    app = _app()
    detail = ElementsDetail(scope="header_footer")

    try:
        detail.set_template(TemplateConfig())
        detail.resize(960, 900)
        detail.show()
        app.processEvents()

        detail.set_reformat_enabled(False)
        app.processEvents()

        assert detail._editor_column.isHidden() is False
        assert detail._summary_grid.value_for("header")
        assert detail._summary_grid.value_for("footer_text")
        assert detail._summary_grid.value_for("page_number")
        assert "disabled" not in {item.key for item in detail._summary_grid.items()}
    finally:
        detail.close()
        app.processEvents()


def test_template_panel_table_detail_updates_preview_and_dirty_state():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        panel._table_detail._border_combo.setCurrentIndex(1)
        app.processEvents()

        assert panel._current_template.table.border_mode == "full_grid"
        assert "全框线" in panel._overview_detail._rows["table"]._value.text()
        assert "全框线" in panel._nav_cards["tpl_table"]._full_subtitle
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_table_detail_color_table_gallery_updates_template_and_preview():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        panel._table_detail._border_combo.setCurrentIndex(
            panel._table_detail._border_combo.findData("color_table")
        )
        panel._table_detail._color_gallery.set_selection("green", "header_grid_zebra")
        panel._table_detail._on_color_table_selected()
        app.processEvents()

        table = panel._current_template.table
        assert table.border_mode == "color_table"
        assert table.color_table_accent == "green"
        assert table.color_table_variant == "header_grid_zebra"
        assert "颜色表" in panel._overview_detail._rows["table"]._value.text()
        assert "绿色" in panel._overview_detail._rows["table"]._value.text()
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_color_table_gallery_uses_four_columns_with_responsive_breakpoints():
    app = _app()
    gallery = ColorTableGallery(label_width=72)

    try:
        gallery.resize(1120, 260)
        gallery.show()
        app.processEvents()
        assert gallery._current_columns == 4
        assert gallery.minimumSizeHint().width() <= 260

        gallery.resize(520, 360)
        app.processEvents()
        assert gallery._current_columns == 2

        gallery.resize(360, 360)
        app.processEvents()
        assert gallery._current_columns == 1
        assert gallery.minimumSizeHint().width() <= 260
    finally:
        gallery.close()
        app.processEvents()


def test_color_table_gallery_aligns_with_form_rows_without_hint_text():
    source = (ROOT / "src/shared/ui/table_style_gallery.py").read_text(encoding="utf-8")
    assert "先选主题色" not in source
    assert "color_table_gallery_hint" not in source

    app = _app()
    gallery = ColorTableGallery(label_width=72)

    try:
        gallery.resize(520, 220)
        gallery.show()
        app.processEvents()

        assert gallery._label.width() == 72
        assert gallery._preview_gutter.width() == gallery._label.width()
        assert gallery._dots_host.x() == gallery._grid_host.x()
    finally:
        gallery.close()
        app.processEvents()


def test_color_table_gallery_fills_preview_row_without_right_gutter():
    app = _app()
    gallery = ColorTableGallery(label_width=72)

    try:
        gallery.resize(1120, 260)
        gallery.show()
        app.processEvents()

        buttons = list(gallery._variant_buttons.values())
        first = buttons[0].geometry()
        second = buttons[1].geometry()
        fourth = buttons[3].geometry()
        fifth = buttons[4].geometry()
        assert gallery._current_columns == 4
        assert first.left() == 0
        assert second.top() == first.top()
        assert fourth.top() == first.top()
        assert fifth.left() == first.left()
        assert fourth.right() >= gallery._grid_host.width() - 2
        assert first.width() >= 168
        assert first.height() == 88
        assert gallery.height() == gallery.sizeHint().height()
        assert gallery.height() < 240

        gallery.resize(360, 360)
        app.processEvents()
        assert gallery._current_columns == 1
    finally:
        gallery.close()
        app.processEvents()


def test_template_panel_elements_detail_updates_preview_and_dirty_state():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        panel._toc_detail._toc_mode_combo.setCurrentIndex(
            panel._toc_detail._toc_mode_combo.findData("plain")
        )
        app.processEvents()

        assert panel._current_template.toc.mode == "plain"
        assert "普通目录" in panel._overview_detail._rows["toc"]._value.text()
        assert "普通目录" in panel._nav_cards["tpl_toc"]._full_subtitle
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_elements_detail_supports_fixed_header_text_and_plain_toc_mode():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        panel._header_footer_detail._header_mode_combo.setCurrentIndex(
            panel._header_footer_detail._header_mode_combo.findData("fixed")
        )
        panel._header_footer_detail._header_text_edit.setText("固定页眉")
        panel._toc_detail._toc_mode_combo.setCurrentIndex(
            panel._toc_detail._toc_mode_combo.findData("plain")
        )
        app.processEvents()

        assert panel._current_template.header_footer.header_mode == "fixed"
        assert panel._current_template.header_footer.header_text == "固定页眉"
        assert panel._current_template.toc.mode == "plain"
        assert "固定页眉" in panel._overview_detail._rows["header_footer"]._value.text()
        assert "页码：全文阿拉伯数字从 1 起" in panel._overview_detail._rows["header_footer"]._value.text()
        assert "页码：全文阿拉伯数字从 1 起" in panel._nav_cards["tpl_header_footer"]._full_subtitle
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_elements_detail_supports_page_number_strategy_fields():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        detail = panel._header_footer_detail
        detail._exclusion_preset_combo.setCurrentIndex(detail._exclusion_preset_combo.findData("none"))
        detail._preset_split_restart_btn.click()
        app.processEvents()

        front_phase = detail._page_phase_rows[0]
        front_phase.format_combo.setCurrentIndex(front_phase.format_combo.findData("lowerRoman"))
        app.processEvents()

        body_phase = detail._page_phase_rows[1]
        body_phase.start_mode_combo.setCurrentIndex(body_phase.start_mode_combo.findData("continue"))
        app.processEvents()

        body_phase = detail._page_phase_rows[1]
        body_phase.start_value_spin.setValue(3)
        app.processEvents()

        header_footer = panel._current_template.header_footer
        assert len(header_footer.page_number_plan.phases) == 2
        assert header_footer.hide_cover_header_footer is False
        assert header_footer.front_matter_page_number_format == "lowerRoman"
        assert header_footer.restart_body_page_number is False
        assert header_footer.body_page_number_start == 3
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_header_footer_supports_page_variant_controls():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        detail = panel._header_footer_detail
        detail._header_alignment_combo.setCurrentIndex(detail._header_alignment_combo.findData("right"))
        detail._different_first_page_toggle.click()
        detail._different_odd_even_toggle.click()
        detail._page_number_display_combo.setCurrentIndex(detail._page_number_display_combo.findData("total"))
        detail._first_header_mode_combo.setCurrentIndex(detail._first_header_mode_combo.findData("fixed"))
        detail._first_header_alignment_combo.setCurrentIndex(detail._first_header_alignment_combo.findData("left"))
        detail._first_header_text_edit.setText("首页页眉")
        detail._first_footer_mode_combo.setCurrentIndex(detail._first_footer_mode_combo.findData("template"))
        detail._first_footer_alignment_combo.setCurrentIndex(detail._first_footer_alignment_combo.findData("left"))
        detail._first_footer_text_edit.setText("第 {page} 页")
        detail._even_header_mode_combo.setCurrentIndex(detail._even_header_mode_combo.findData("styleref"))
        detail._even_header_alignment_combo.setCurrentIndex(detail._even_header_alignment_combo.findData("right"))
        detail._even_header_level_combo.setCurrentIndex(detail._even_header_level_combo.findData(3))
        detail._even_footer_mode_combo.setCurrentIndex(detail._even_footer_mode_combo.findData("page_number_with_text"))
        detail._even_footer_alignment_combo.setCurrentIndex(detail._even_footer_alignment_combo.findData("right"))
        detail._even_footer_text_edit.setText("内部")
        app.processEvents()

        header_footer = panel._current_template.header_footer
        assert header_footer.behavior.different_first_page is True
        assert header_footer.behavior.different_odd_even_pages is True
        assert header_footer.behavior.link_to_previous == "never"
        assert header_footer.behavior.preserve_existing_content is False
        assert header_footer.header_alignment == "right"
        assert header_footer.page_number_template == "第 {page} 页 / 共 {pages} 页"
        assert header_footer.variants.first.header.mode == "fixed"
        assert header_footer.variants.first.header.alignment == "left"
        assert header_footer.variants.first.header.fixed_text == "首页页眉"
        assert header_footer.variants.even.header.mode == "styleref"
        assert header_footer.variants.even.header.alignment == "right"
        assert header_footer.variants.even.header.styleref_level == 3
        assert header_footer.variants.first.footer.mode == "template"
        assert header_footer.variants.first.footer.alignment == "left"
        assert header_footer.variants.first.footer.template == "第 {page} 页"
        assert header_footer.variants.even.footer.mode == "page_number_with_text"
        assert header_footer.variants.even.footer.alignment == "right"
        assert header_footer.variants.even.footer.fixed_text == "内部"
        assert detail._scheme_combo.currentData() is None
        assert detail._scheme_combo.display_text() == "当前配置（自定义）"
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_header_footer_page_variant_rows_follow_toggles():
    app = _app()
    detail = ElementsDetail(scope="header_footer")

    try:
        detail.set_template(TemplateConfig())
        detail.resize(960, 900)
        detail.show()
        app.processEvents()

        header_footer = detail._header_footer_detail
        assert header_footer._page_variants_card.isVisible()
        assert header_footer._first_header_variant_grid.isHidden()
        assert header_footer._first_footer_variant_grid.isHidden()
        assert header_footer._even_header_variant_grid.isHidden()
        assert header_footer._even_footer_variant_grid.isHidden()
        assert header_footer._header_variant_separator.isHidden()
        assert header_footer._normal_header_title_label.text() == "普通页页眉"
        assert header_footer._first_header_title_label.isHidden()
        assert header_footer._even_header_title_label.isHidden()
        assert header_footer._even_header_separator.isHidden()
        assert header_footer._normal_footer_title_label.text() == "普通页页脚"
        assert header_footer._first_footer_title_label.isHidden()
        assert header_footer._even_footer_title_label.isHidden()
        assert header_footer._even_footer_separator.isHidden()
        assert header_footer._footer_variant_separator.isHidden()
        assert header_footer._first_header_mode_row not in header_footer._page_variants_card.findChildren(FormRow)
        assert header_footer._first_footer_mode_row not in header_footer._page_variants_card.findChildren(FormRow)

        header_footer._different_first_page_toggle.click()
        app.processEvents()

        assert header_footer._first_header_variant_grid.isVisible()
        assert header_footer._first_footer_variant_grid.isVisible()
        assert header_footer._even_header_variant_grid.isHidden()
        assert header_footer._even_footer_variant_grid.isHidden()
        assert header_footer._header_variant_separator.isVisible()
        assert header_footer._normal_header_title_label.text() == "普通页页眉（首页以外）"
        assert header_footer._first_header_title_label.isVisible()
        assert header_footer._even_header_title_label.isHidden()
        assert header_footer._even_header_separator.isHidden()
        assert header_footer._footer_variant_separator.isVisible()
        assert header_footer._normal_footer_title_label.text() == "普通页页脚（首页以外）"
        assert header_footer._first_footer_title_label.isVisible()
        assert header_footer._even_footer_title_label.isHidden()
        assert header_footer._even_footer_separator.isHidden()
        assert header_footer._first_header_mode_row.isVisible()
        assert header_footer._first_header_alignment_row.isHidden()
        assert header_footer._first_header_level_row.isHidden()
        assert header_footer._first_footer_mode_row.isVisible()
        assert header_footer._first_footer_alignment_row.isHidden()
        assert header_footer._first_header_text_row.isHidden()

        header_footer._first_header_mode_combo.setCurrentIndex(
            header_footer._first_header_mode_combo.findData("fixed")
        )
        app.processEvents()

        assert header_footer._first_header_text_row.isVisible()
        assert header_footer._first_header_alignment_row.isVisible()
        assert header_footer._first_header_level_row.isHidden()
        assert header_footer._first_footer_text_row.isHidden()

        header_footer._first_footer_mode_combo.setCurrentIndex(
            header_footer._first_footer_mode_combo.findData("page_number_with_text")
        )
        app.processEvents()

        assert header_footer._first_footer_text_row.isVisible()
        assert header_footer._first_footer_alignment_row.isVisible()

        header_footer._different_odd_even_toggle.click()
        app.processEvents()

        assert header_footer._even_header_variant_grid.isVisible()
        assert header_footer._even_footer_variant_grid.isVisible()
        assert header_footer._normal_header_title_label.text() == "奇数页页眉（首页以外）"
        assert header_footer._even_header_title_label.isVisible()
        assert header_footer._even_header_separator.isVisible()
        assert header_footer._normal_footer_title_label.text() == "奇数页页脚（首页以外）"
        assert header_footer._even_footer_title_label.isVisible()
        assert header_footer._even_footer_separator.isVisible()
        even_title_y = header_footer._even_header_title_label.mapTo(
            detail, header_footer._even_header_title_label.rect().topLeft()
        ).y()
        first_title_y = header_footer._first_header_title_label.mapTo(
            detail, header_footer._first_header_title_label.rect().topLeft()
        ).y()
        assert even_title_y < first_title_y
        even_footer_title_y = header_footer._even_footer_title_label.mapTo(
            detail, header_footer._even_footer_title_label.rect().topLeft()
        ).y()
        first_footer_title_y = header_footer._first_footer_title_label.mapTo(
            detail, header_footer._first_footer_title_label.rect().topLeft()
        ).y()
        assert even_footer_title_y < first_footer_title_y
        assert header_footer._even_header_mode_row.isVisible()
        assert header_footer._even_header_alignment_row.isHidden()
        assert header_footer._even_header_level_row.isHidden()
        assert header_footer._even_footer_mode_row.isVisible()
        assert header_footer._even_footer_alignment_row.isHidden()

        header_footer._even_header_mode_combo.setCurrentIndex(
            header_footer._even_header_mode_combo.findData("styleref")
        )
        header_footer._even_footer_mode_combo.setCurrentIndex(
            header_footer._even_footer_mode_combo.findData("page_number_with_text")
        )
        app.processEvents()

        assert header_footer._even_header_alignment_row.isVisible()
        assert header_footer._even_header_level_row.isVisible()
        assert header_footer._even_footer_alignment_row.isVisible()
        assert header_footer._even_footer_text_row.isVisible()

        header_footer._different_first_page_toggle.click()
        app.processEvents()

        assert header_footer._first_header_variant_grid.isHidden()
        assert header_footer._first_footer_variant_grid.isHidden()
        assert header_footer._first_header_mode_row.isHidden()
        assert header_footer._even_header_variant_grid.isVisible()
        assert header_footer._even_footer_variant_grid.isVisible()
        assert header_footer._normal_header_title_label.text() == "奇数页页眉"
        assert header_footer._first_header_title_label.isHidden()
        assert header_footer._even_header_title_label.isVisible()
        assert header_footer._even_header_separator.isHidden()
        assert header_footer._normal_footer_title_label.text() == "奇数页页脚"
        assert header_footer._first_footer_title_label.isHidden()
        assert header_footer._even_footer_title_label.isVisible()
        assert header_footer._even_footer_separator.isHidden()
        assert header_footer._header_variant_separator.isVisible()
        assert header_footer._footer_variant_separator.isVisible()

        header_footer._header_enabled_toggle.click()
        header_footer._footer_enabled_toggle.click()
        app.processEvents()

        assert header_footer._header_enabled_toggle.isChecked() is False
        assert header_footer._footer_enabled_toggle.isChecked() is False
        assert header_footer._even_header_mode_row.isVisible()
        assert header_footer._even_footer_mode_row.isVisible()
        assert header_footer._even_header_mode_row.isEnabled() is False
        assert header_footer._even_header_alignment_row.isEnabled() is False
        assert header_footer._even_footer_mode_row.isEnabled() is False
        assert header_footer._even_footer_alignment_row.isEnabled() is False
    finally:
        detail.close()
        app.processEvents()


def test_template_panel_table_detail_supports_width_font_and_alignment_fields():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        panel._table_detail._border_width_input.set_value(1.5, "pt")
        panel._table_detail._font_en_combo.set_font_name("Arial")
        panel._table_detail._table_alignment_combo.setCurrentIndex(
            panel._table_detail._table_alignment_combo.findData("right")
        )
        panel._table_detail._alignment_combo.setCurrentIndex(
            panel._table_detail._alignment_combo.findData("center")
        )
        panel._table_detail._bold_toggle.click()
        panel._table_detail._italic_toggle.click()
        app.processEvents()

        assert panel._current_template.table.border_width_pt == 1.5
        assert panel._current_template.table.font_en == "Arial"
        assert panel._current_template.table.bold is True
        assert panel._current_template.table.italic is True
        assert panel._current_template.table.table_alignment == "right"
        assert panel._current_template.table.cell_alignment == "center"
        assert "表格右对齐" not in panel._table_detail._summary_grid._items[0].value
        assert "表格右对齐" in panel._table_detail._summary_grid._items[2].detail
        assert "加粗、斜体" in panel._table_detail._summary_grid._items[2].detail
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_table_detail_syncs_none_alignment_to_no_adjust_option():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        first = TemplateConfig()
        first.table.table_alignment = "right"
        first.table.cell_alignment = "center"
        second = TemplateConfig()
        second.table.table_alignment = None
        second.table.cell_alignment = None

        panel.on_template_changed(first)
        app.processEvents()
        assert panel._table_detail._table_alignment_combo.currentData() == "right"
        assert panel._table_detail._alignment_combo.currentData() == "center"

        panel.on_template_changed(second)
        app.processEvents()
        assert panel._table_detail._table_alignment_combo.currentData() == ""
        assert panel._table_detail._alignment_combo.currentData() == ""

        panel._table_detail._border_width_input.set_value(1.2, "pt")
        app.processEvents()
        assert second.table.table_alignment is None
        assert second.table.cell_alignment is None
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_table_detail_smart_levels_match_engine_supported_range():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        detail = panel._table_detail
        values = [
            detail._smart_levels_combo.itemData(index)
            for index in range(detail._smart_levels_combo.count())
        ]
        assert values == [3, 4, 5, 6]

        legacy = TemplateConfig()
        legacy.table.smart_levels = 2
        detail.set_template(legacy)
        app.processEvents()

        assert legacy.table.smart_levels == 2
        assert detail._smart_levels_combo.currentData() == 4
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_table_detail_width_controls_follow_border_mode():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        detail = panel._table_detail

        detail._border_combo.setCurrentIndex(detail._border_combo.findData("three_line"))
        app.processEvents()
        assert detail._header_width_row.isHidden() is False
        assert detail._header_width_row.label_text == "外线宽"
        assert detail._bottom_width_row.isHidden() is False
        assert detail._bottom_width_row.label_text == "表头下线"
        assert detail._border_width_row.isHidden() is True
        assert "表头" in detail._summary_grid._items[1].value

        detail._border_combo.setCurrentIndex(detail._border_combo.findData("color_table"))
        detail._color_gallery.set_selection("blue", "header_grid")
        detail._sync_layout_dependent_state()
        app.processEvents()
        assert detail._color_gallery.isHidden() is False
        assert detail._border_width_row.isHidden() is False
        assert detail._border_width_row.label_text == "网格线宽"
        assert detail._header_width_row.isHidden() is True
        assert detail._bottom_width_row.isHidden() is True
        assert "行高" not in detail._summary_grid._items[1].label
        assert "行高" not in detail._summary_grid._items[1].value
        assert "行高" not in detail._summary_grid._items[1].detail

        detail._color_gallery.set_selection("blue", "header_rule")
        detail._sync_layout_dependent_state()
        app.processEvents()
        assert detail._border_width_row.isHidden() is True
        assert detail._header_width_row.isHidden() is False
        assert detail._header_width_row.label_text == "外线宽"
        assert detail._bottom_width_row.isHidden() is False
        assert detail._bottom_width_row.label_text == "表头下线"

        detail._border_combo.setCurrentIndex(detail._border_combo.findData("full_grid"))
        app.processEvents()
        assert detail._color_gallery.isHidden() is True
        assert detail._border_width_row.label_text == "网格线宽"
        assert detail._border_width_row.isHidden() is False
        assert detail._header_width_row.isHidden() is True
        assert detail._bottom_width_row.isHidden() is True

        detail._border_combo.setCurrentIndex(detail._border_combo.findData("none"))
        app.processEvents()
        assert detail._border_width_row.isHidden() is True
        assert detail._header_width_row.isHidden() is True
        assert detail._bottom_width_row.isHidden() is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_table_detail_supports_keep_layout_strategy():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        detail = panel._table_detail
        keep_index = detail._layout_combo.findData("keep")

        assert keep_index >= 0
        detail._layout_combo.setCurrentIndex(keep_index)
        app.processEvents()

        assert panel._current_template.table.layout_mode == "keep"
        assert "保留原样" in detail._summary_grid._items[0].value
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_table_detail_does_not_expose_row_height():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        detail = panel._table_detail
        detail.set_template(panel._current_template)
        app.processEvents()

        assert not hasattr(panel._current_template.table, "row_height_pt")
        assert not hasattr(detail, "_row_height_row")
        assert not hasattr(detail, "_row_height_input")
        assert "行高" not in detail._summary_grid._items[1].label
        assert "行高" not in detail._summary_grid._items[1].value
        assert "行高" not in detail._summary_grid._items[1].detail
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_table_detail_defaults_to_word_table_typography_and_supports_first_row_bold():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        assert panel._current_template.table.font_cn == "微软雅黑"
        assert panel._current_template.table.font_en == "Times New Roman"
        assert panel._current_template.table.size_pt == 10.5
        assert panel._table_detail._font_cn_combo.selected_font() == "微软雅黑"
        assert panel._table_detail._font_en_combo.selected_font() == "Times New Roman"
        assert panel._table_detail._size_combo.current_pt() == 10.5
        assert panel._table_detail._summary_grid._items[0].label == "边框与布局"
        assert panel._table_detail._summary_grid._items[2].label == "字体与对齐"
        assert panel._table_detail._summary_grid._items[2].value == "微软雅黑 / Times New Roman"
        assert panel._table_detail._summary_grid._items[2].detail == "10.5 磅 / 表格居中"
        assert "不首行加粗" in panel._table_detail._summary_grid._items[2].tooltip
        assert "不跨页重复表头" in panel._table_detail._summary_grid._items[2].tooltip
        assert "不首行加粗" in panel._overview_detail._rows["table"]._value.text()
        assert "不跨页重复表头" in panel._overview_detail._rows["table"]._value.text()

        panel._table_detail._first_row_bold_toggle.click()
        app.processEvents()

        assert panel._current_template.table.first_row_bold is True
        assert "首行加粗" in panel._overview_detail._rows["table"]._value.text()
        assert "首行加粗" in panel._nav_cards["tpl_table"]._full_subtitle
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_elements_detail_supports_custom_phase_rows():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        detail = panel._header_footer_detail
        detail._add_phase_btn.click()
        app.processEvents()

        new_phase = detail._page_phase_rows[-1]
        assert new_phase.section.is_expanded() is True
        assert new_phase.phase_id_edit.isHidden() is True
        start_value_grids = [
            grid
            for grid in new_phase.section.findChildren(TemplateFormGrid)
            if any(
                getattr(cell, "widget", None) is new_phase.start_value_spin
                for row in grid._rows
                for cell in row
            )
        ]
        assert len(start_value_grids) == 1
        assert [len(row) for row in start_value_grids[0]._rows] == [1]
        assert new_phase.section._toggle_button.text() == "未选择范围"
        new_phase.phase_id_edit.setText("appendix")
        app.processEvents()

        new_phase = detail._page_phase_rows[-1]
        new_phase.selector_editor._selector_buttons["appendix"].click()
        app.processEvents()
        assert new_phase.section._toggle_button.text() == "附录：阿拉伯数字，从 1 起"

        new_phase = detail._page_phase_rows[-1]
        new_phase.visible_toggle.click()
        app.processEvents()
        assert new_phase.section._toggle_button.text() == "附录：不显示页码"

        phases = panel._current_template.header_footer.page_number_plan.phases
        assert len(phases) == 2
        assert phases[-1].phase_id == "appendix"
        assert phases[-1].selectors == ["appendix"]
        assert phases[-1].visible is False
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_elements_detail_preserves_phase_row_instances_while_editing():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        detail = panel._header_footer_detail
        detail._add_phase_btn.click()
        app.processEvents()

        new_phase = detail._page_phase_rows[-1]
        new_phase.phase_id_edit.setText("appendix")
        app.processEvents()

        assert detail._page_phase_rows[-1] is new_phase

        new_phase.selector_editor._selector_buttons["appendix"].click()
        app.processEvents()

        assert detail._page_phase_rows[-1] is new_phase
        assert panel._current_template.header_footer.page_number_plan.phases[-1].selectors == ["appendix"]
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_elements_detail_can_duplicate_and_reorder_phase_rows():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        detail = panel._header_footer_detail
        first = detail._page_phase_rows[0]
        first.selector_editor._selector_buttons["body"].click()
        detail._add_phase_btn.click()
        app.processEvents()
        trailing = detail._page_phase_rows[1]

        first.duplicate_btn.click()
        app.processEvents()

        assert len(detail._page_phase_rows) == 3
        copied = detail._page_phase_rows[1]
        assert detail._page_phase_rows[0] is first
        assert detail._page_phase_rows[0].section is first.section
        assert detail._page_phase_rows[2] is trailing
        assert detail._page_phase_rows[2].section is trailing.section
        assert copied is not first
        assert copied.section is not first.section
        assert detail._page_phase_rows_layout.itemAt(0).widget() is first.section
        assert detail._page_phase_rows_layout.itemAt(1).widget() is copied.section
        assert detail._page_phase_rows_layout.itemAt(2).widget() is trailing.section
        phases = panel._current_template.header_footer.page_number_plan.phases
        assert phases[1].phase_id.endswith("_copy")
        assert phases[1].selectors == phases[0].selectors
        assert "同时出现在多个编号分组中" in copied.selector_preview.text()

        copied.move_up_btn.click()
        app.processEvents()

        assert detail._page_phase_rows == [copied, first, trailing]
        assert detail._page_phase_rows_layout.itemAt(0).widget() is copied.section
        assert detail._page_phase_rows_layout.itemAt(1).widget() is first.section
        assert detail._page_phase_rows_layout.itemAt(2).widget() is trailing.section
        phases = panel._current_template.header_footer.page_number_plan.phases
        assert phases[0].phase_id.endswith("_copy")
    finally:
        panel.close()
        app.processEvents()


def test_template_page_phase_delete_preserves_outer_scroll_anchor():
    app = _app()
    panel = TemplatePanel(PanelBridge())

    try:
        panel.resize(1280, 700)
        panel.show()
        panel._nav_rail.select_card("tpl_header_footer")
        for _ in range(4):
            app.processEvents()
        detail = panel._header_footer_detail
        page_plan = detail._header_footer_detail._page_plan
        while len(page_plan._page_phase_rows) < 6:
            page_plan._on_add_phase()
        for row in page_plan._page_phase_rows:
            row.section.set_expanded(True)
        for _ in range(4):
            app.processEvents()

        removed = page_plan._page_phase_rows[2]
        anchor_row = page_plan._page_phase_rows[3]
        surviving_sections = [
            row.section for row in page_plan._page_phase_rows if row is not removed
        ]
        scroll = panel._detail_scroll
        scroll.ensureWidgetVisible(anchor_row.section)
        app.processEvents()
        bar = scroll.verticalScrollBar()
        assert bar.value() > 0
        before_y = anchor_row.section.mapTo(scroll.viewport(), QPoint(0, 0)).y()
        observed_values: list[int] = []
        bar.valueChanged.connect(observed_values.append)

        page_plan._remove_phase_row(removed)
        for _ in range(8):
            app.processEvents()

        after_y = anchor_row.section.mapTo(scroll.viewport(), QPoint(0, 0)).y()
        assert abs(after_y - before_y) <= 1
        assert all(
            row.section is section
            for row, section in zip(page_plan._page_phase_rows, surviving_sections)
        )
        assert 0 not in observed_values
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_elements_detail_keeps_empty_rule_diagnostics_compact():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        detail = panel._header_footer_detail
        detail._add_phase_btn.click()
        detail._add_phase_btn.click()
        app.processEvents()

        alert = detail._page_plan_alert
        message = alert.message()
        assert alert.isHidden() is False
        assert alert.variant() == "error"
        assert "有 2 个编号分组尚未选择范围" in message
        assert "phase_2" not in message
        assert "phase_3" not in message
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_elements_detail_shows_page_plan_diagnostics_inline():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        detail = panel._header_footer_detail
        detail._add_phase_btn.click()
        app.processEvents()

        new_phase = detail._page_phase_rows[-1]
        new_phase.phase_id_edit.setText("overlap")
        app.processEvents()

        new_phase = detail._page_phase_rows[-1]
        new_phase.selector_editor._selector_buttons["all_numbered_content"].click()
        app.processEvents()

        alert = detail._page_plan_alert
        assert alert.isHidden() is False
        assert alert.variant() == "error"
        assert "同时属于多个编号分组" in alert.message()
        assert "建议：" not in alert.message()
        assert "同时出现在多个编号分组中" in new_phase.selector_preview.text()
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_elements_detail_phase_preview_shows_hidden_range_warning():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        detail = panel._header_footer_detail
        detail._exclusion_preset_combo.setCurrentIndex(detail._exclusion_preset_combo.findData("custom"))
        detail._suppress_selector_editor.set_selectors(["appendix"])
        detail._add_phase_btn.click()
        app.processEvents()

        new_phase = detail._page_phase_rows[-1]
        new_phase.selector_editor._selector_buttons["appendix"].click()
        app.processEvents()

        preview = new_phase.selector_preview.text()
        assert "这一组都在分区排除中，不会显示页码" in preview
        assert "附录：阿拉伯数字，从 1 起（不含附录）" in new_phase.section._toggle_button.text()
    finally:
        panel.close()
        app.processEvents()
