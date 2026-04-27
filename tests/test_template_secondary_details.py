import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QBoxLayout, QPushButton, Qt, QVBoxLayout, QWidget
from src.config.template import TemplateConfig
from src.shared.ui.adaptive_pair_row import AdaptivePairRow
from src.shared.ui.dashed_separator import DashedSeparator
from src.shared.ui.flow_layout import FlowLayout
from src.shared.ui.form_row import FormRow
from src.shared.ui.inspector_form import InspectorForm
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
    assert "SummaryGrid(" in table_source
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
    assert ".add_pair(" in header_footer_source
    assert ".add_grid(" in header_footer_source
    assert ".add_split_columns(" not in header_footer_source
    assert "_page_toggle_group" in header_footer_source
    assert "column_stretches=(0, 0, 0)" not in header_footer_source
    assert "template_form_row" in header_footer_source
    assert "SummaryGrid(" in elements_source
    assert "_sync_dependent_state" in elements_source
    assert "findChildren(QLineEdit)" not in elements_source
    assert "class HeaderFooterDetailSection" in header_footer_source
    assert "PageNumberPlanSection(owner)" in header_footer_source
    assert "class PageNumberPlanSection" in page_plan_source
    assert "class TocDetailSection" in toc_source
    assert "HeaderFooterDetailSection(self)" in elements_source
    assert "TocDetailSection(self)" in elements_source
    assert "self._header_footer_detail.set_header_footer(template.header_footer)" in elements_source
    assert "self._toc_detail.set_template(template)" in elements_source
    assert "Card(parent=owner._editor_column)" in header_footer_source
    assert "Card(parent=owner._editor_column)" in toc_source
    assert "def phase_rows_to_configs" in page_plan_source
    assert "def refresh_validation_alert" in page_plan_source
    assert "def _on_toc_style_edited" in toc_source
    assert "def effective_style" in toc_source


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


def test_template_form_grid_packs_short_fixed_controls_when_requested():
    app = _app()
    host = QWidget()
    rows = [
        template_form_row("页码", ToggleSwitch(host), parent=host),
        template_form_row("页眉线", ToggleSwitch(host), parent=host),
        template_form_row("起始前留空", ToggleSwitch(host), parent=host),
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

        rows = (
            detail._header_footer_detail._header_mode_row,
            detail._header_footer_detail._styleref_level_row,
            detail._header_footer_detail._header_text_row,
            detail._header_footer_detail._font_cn_row,
            detail._header_footer_detail._font_en_row,
            detail._header_footer_detail._size_row,
            detail._header_footer_detail._emphasis_row,
            detail._header_footer_detail._suppress_selector_row,
        )
        toggle_rows = (
            detail._header_footer_detail._page_number_row,
            detail._header_footer_detail._header_border_row,
            detail._header_footer_detail._hide_cover_row,
        )
        expected_label_width = max(row.preferred_label_width() for row in rows)
        assert {row.label_width for row in rows} == {expected_label_width}
        expected_toggle_label_width = max(row.preferred_label_width() for row in toggle_rows)
        assert {row.label_width for row in toggle_rows} == {expected_toggle_label_width}
        assert detail._header_footer_detail._page_toggle_group.layout().direction() == QBoxLayout.LeftToRight
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
        assert detail._header_footer_detail._font_en_row.width() == detail._header_footer_detail._font_cn_row.width()
        trailing_rows = {
            detail._header_footer_detail._styleref_level_row,
            detail._header_footer_detail._header_text_row,
            detail._header_footer_detail._size_row,
            detail._header_footer_detail._emphasis_row,
        }
        for row in (*rows, *toggle_rows):
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


def test_header_footer_hidden_fixed_text_row_does_not_force_stacked_layout():
    app = _app()
    detail = ElementsDetail()

    try:
        detail.set_template(TemplateConfig())
        detail.resize(700, 800)
        detail.show()
        app.processEvents()

        row = detail._header_footer_detail._header_mode_pair.findChild(AdaptivePairRow)
        assert row is not None
        assert detail._header_footer_detail._header_text_row.isHidden()
        assert row.layout().direction() == QBoxLayout.LeftToRight
    finally:
        detail.close()
        app.processEvents()


def test_template_caption_formula_other_details_share_single_label_baseline():
    app = _app()
    details = (
        (CaptionDetail(), ("图前缀", "表前缀", "编号模式", "段前", "段后")),
        (FormulaDetail(), ("公式字体", "公式字号", "块对齐", "编号方式", "统一间距")),
        (OtherDetail(), ("最终稿 DOCX", "对比稿 DOCX", "JSON 报告", "Markdown 报告")),
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


def test_template_toc_style_editor_uses_section_level_baseline():
    app = _app()
    detail = ElementsDetail()

    try:
        detail.set_template(TemplateConfig())
        detail.resize(1280, 900)
        detail.show()
        app.processEvents()

        section = detail._toc_detail._toc_style_controls["toc"]["section"]
        row_map = {row.label_text: row for row in section.findChildren(FormRow)}
        labels = ("中文字体", "英文字体", "字号", "字形", "对齐", "左缩进", "行距类型", "行距值", "段前", "段后")

        x_positions = {row_map[label].widget.x() for label in labels}
        assert len(x_positions) == 1

        label_widths = {row_map[label].label_width for label in labels}
        assert len(label_widths) == 1
        assert row_map["段前"]._suffix is None
        assert row_map["段后"]._suffix is None
        assert "italic" in detail._toc_detail._toc_style_controls["toc"]
        assert detail._toc_detail._toc_style_controls["toc"]["space_before"].unit_combo.isVisible()
        assert detail._toc_detail._toc_style_controls["toc"]["space_after"].unit_combo.isVisible()
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

        toc_controls = detail._toc_detail._toc_style_controls["toc"]
        assert_embedded_editor_style(toc_controls["font_cn"])
        assert_embedded_editor_style(toc_controls["font_en"])
        assert_embedded_editor_style(toc_controls["size"])

        spin_editor = toc_controls["space_before"].spin_box.lineEdit()
        assert "border: none;" in spin_editor.styleSheet()
        assert "padding: 0;" in spin_editor.styleSheet()
        assert "border: 1px solid" not in spin_editor.styleSheet()
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


def test_elements_detail_materializes_default_page_number_phase():
    app = _app()
    detail = ElementsDetail()
    template = TemplateConfig()
    template.header_footer.page_number_plan.phases = []

    try:
        detail.set_template(template)
        app.processEvents()

        phases = template.header_footer.page_number_plan.phases
        assert len(phases) == 1
        assert phases[0].phase_id == "main"
        assert phases[0].selectors == ["all_numbered_content"]
        assert phases[0].number_format == "decimal"
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
        assert phase_row.section.is_expanded() is False
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
        assert "固定页眉" in detail._summary_grid.value_for("header")

        detail._page_number_toggle.click()
        app.processEvents()

        assert panel._current_template.header_footer.page_number_enabled is False
        assert detail._page_plan_section.isHidden() is True
        assert detail._summary_grid.value_for("page_number") == "页码关闭"

        toc_detail._toc_enabled_toggle.click()
        app.processEvents()

        assert panel._current_template.toc.enabled is False
        assert toc_detail._toc_mode_row.isEnabled() is False
        assert toc_detail._toc_styles_section.isHidden() is True
        assert toc_detail._summary_grid.value_for("toc") == "目录关闭"
    finally:
        panel.close()
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
        panel._toc_detail._toc_enabled_toggle.click()
        app.processEvents()

        assert panel._current_template.toc.enabled is False
        assert "目录关闭" in panel._overview_detail._rows["toc"]._value.text()
        assert "目录关闭" in panel._nav_cards["tpl_toc"]._full_subtitle
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
        detail._hide_cover_toggle.click()
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
        assert "表格右对齐" in panel._table_detail._summary_grid._items[3].value
        assert "字形 加粗、斜体" in panel._table_detail._summary_grid._items[2].detail
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

        assert legacy.table.smart_levels == 4
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
        assert "表头下线" in detail._summary_grid._items[1].value

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


def test_template_panel_table_detail_normalizes_legacy_row_height():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        detail = panel._table_detail
        panel._current_template.table.row_height_pt = 24
        detail.set_template(panel._current_template)
        app.processEvents()

        assert panel._current_template.table.row_height_pt is None
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
        assert "不首行加粗" in panel._table_detail._summary_grid._items[3].value
        assert "不跨页重复表头" in panel._table_detail._summary_grid._items[3].value
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
        assert new_phase.section._toggle_button.text() == "规则 2：未选择范围"
        new_phase.phase_id_edit.setText("appendix")
        app.processEvents()

        new_phase = detail._page_phase_rows[-1]
        new_phase.selector_editor._selector_buttons["appendix"].click()
        app.processEvents()
        assert new_phase.section._toggle_button.text() == "规则 2：附录阿拉伯页码"

        new_phase = detail._page_phase_rows[-1]
        new_phase.visible_toggle.click()
        app.processEvents()
        assert new_phase.section._toggle_button.text() == "规则 2：附录不显示页码"

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
        assert "有 2 条页码规则未选择适用范围" in message
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
        assert "同时命中了多个页码规则" in alert.message()
        assert "建议：" in alert.message()
    finally:
        panel.close()
        app.processEvents()
