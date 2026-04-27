import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.builtin_templates import create_builtin_template
from src.config.style_semantics import CM_TO_PT
from src.config.template import PageNumberPhaseConfig, StyleConfig, TemplateConfig
from src.qt_api import QApplication, QRectF, Qt
from src.shared.ui.style_preview_utils import resolve_preview_indents_pt
from src.ui.adapters.heading_numbering_adapter import HeadingNumberingAdapter
from src.ui.panels.template_panel import (
    TemplateStylePreview,
    _build_template_preview_paragraphs,
    _content_rect_from_page,
    _line_height_px,
    _paper_dimensions_cm,
    _table_block_x,
    _table_cell_alignment_flags,
    _table_line_spacing_factor,
    _resolve_preview_header_footer,
)


def _app():
    return QApplication.instance() or QApplication([])


def test_template_style_preview_knows_common_paper_sizes():
    assert _paper_dimensions_cm("A4") == (21.0, 29.7)
    assert _paper_dimensions_cm("LETTER") == (21.59, 27.94)
    assert _paper_dimensions_cm("unknown") == (21.0, 29.7)


def test_template_style_preview_content_rect_respects_page_margins_and_gutter():
    cfg = TemplateConfig()
    cfg.page_setup.paper_size = "A4"
    cfg.page_setup.margin.top_cm = 4.0
    cfg.page_setup.margin.bottom_cm = 3.0
    cfg.page_setup.margin.left_cm = 3.0
    cfg.page_setup.margin.right_cm = 2.0
    cfg.page_setup.gutter_cm = 1.0

    content_rect = _content_rect_from_page(QRectF(0.0, 0.0, 210.0, 297.0), cfg)

    assert content_rect.left() == 40.0
    assert content_rect.top() == 40.0
    assert content_rect.right() == 190.0
    assert content_rect.bottom() == 267.0


def test_template_style_preview_header_footer_state_reflects_config():
    cfg = TemplateConfig()
    cfg.header_footer.header_mode = "none"
    cfg.header_footer.header_border = True
    cfg.header_footer.page_number_enabled = False

    state = _resolve_preview_header_footer(cfg)

    assert state.header_text == ""
    assert state.header_border is False
    assert state.footer_text == ""

    cfg.header_footer.header_mode = "fixed"
    cfg.header_footer.header_text = "固定页眉"
    cfg.header_footer.page_number_enabled = True
    cfg.header_footer.page_number_plan.phases = [
        PageNumberPhaseConfig(
            phase_id="front",
            selectors=["front_matter"],
            visible=True,
            number_format="upperRoman",
            start_mode="restart",
            start_value=3,
        )
    ]

    state = _resolve_preview_header_footer(cfg)

    assert state.header_text == "固定页眉"
    assert state.header_border is True
    assert state.footer_text == "- III -"


def test_template_style_preview_builds_paragraphs_from_real_heading_levels():
    _app()
    cfg = create_builtin_template("thesis_gbt")
    cfg.heading_model.max_heading_levels = 2

    paragraphs = _build_template_preview_paragraphs(cfg)
    adapter = HeadingNumberingAdapter()
    adapter.set_template(cfg)

    assert [paragraph.style_key for paragraph in paragraphs] == [
        "heading1",
        "body",
        "heading2",
        "body",
        "table_preview",
        "non_numbered_heading",
        "body",
    ]
    assert paragraphs[0].text
    assert paragraphs[2].text
    assert paragraphs[5].text

    first_prefix = adapter.preview_number(1)
    if first_prefix:
        assert paragraphs[0].text.startswith(first_prefix)


def test_template_style_preview_adds_third_level_when_enabled():
    _app()
    cfg = create_builtin_template("thesis_gbt")
    cfg.heading_model.max_heading_levels = 3

    paragraphs = _build_template_preview_paragraphs(cfg)

    assert [paragraph.style_key for paragraph in paragraphs] == [
        "heading1",
        "body",
        "heading2",
        "body",
        "heading3",
        "table_preview",
        "non_numbered_heading",
        "body",
    ]


def test_template_style_preview_always_includes_table_sample_even_without_third_level():
    _app()
    cfg = create_builtin_template("thesis_gbt")

    for max_levels in (1, 2):
        cfg.heading_model.max_heading_levels = max_levels
        paragraphs = _build_template_preview_paragraphs(cfg)
        style_keys = [paragraph.style_key for paragraph in paragraphs]

        assert style_keys.count("table_preview") == 1
        assert style_keys.index("table_preview") < style_keys.index("non_numbered_heading")



def test_template_style_preview_skips_non_numbered_heading_titles():
    _app()
    cfg = create_builtin_template("thesis_gbt")
    cfg.heading_model.max_heading_levels = 1
    cfg.heading_model.non_numbered_title_texts = ["摘要"]
    cfg.heading_model.non_numbered_prefixes = []

    paragraphs = _build_template_preview_paragraphs(cfg)

    non_numbered = next(paragraph for paragraph in paragraphs if paragraph.style_key == "non_numbered_heading")
    assert non_numbered.text == "摘要"



def test_template_style_preview_uses_custom_non_numbered_heading_style():
    _app()
    cfg = create_builtin_template("thesis_gbt")
    cfg.heading_model.max_heading_levels = 1
    cfg.heading_model.non_numbered_title_texts = ["摘要"]
    cfg.heading_model.non_numbered_heading_style_mode = "custom"
    cfg.styles["non_numbered_heading"] = StyleConfig(size_pt=20, bold=True)

    preview = TemplateStylePreview()
    try:
        preview.refresh(cfg)
        layout = preview._cached_layout
        assert layout is not None

        heading_line = next(line for line in layout.line_layouts if line.style_key == "non_numbered_heading")
        assert heading_line.font.bold() is True
    finally:
        preview.close()


def test_template_style_preview_line_height_uses_real_spacing_modes():
    exact = StyleConfig(line_spacing_type="exact", line_spacing_pt=20)
    multiple = StyleConfig(line_spacing_type="multiple", line_spacing_pt=1.8)
    double = StyleConfig(line_spacing_type="double", line_spacing_pt=2.0)

    assert _line_height_px(exact, font_height=11.0, pt_to_px=0.8) == 16.0
    assert round(_line_height_px(multiple, font_height=11.0, pt_to_px=0.8), 1) == 19.8
    assert _line_height_px(double, font_height=11.0, pt_to_px=0.8) == 22.0


def test_template_style_preview_table_alignment_helpers_match_word_options():
    assert _table_cell_alignment_flags("center") & Qt.AlignHCenter
    assert _table_cell_alignment_flags("right") & Qt.AlignRight
    assert _table_cell_alignment_flags(None) & Qt.AlignLeft
    assert _table_line_spacing_factor("single") == 1.0
    assert _table_line_spacing_factor("one_half") == 1.5
    assert _table_line_spacing_factor("double") == 2.0

    bounds = QRectF(10.0, 0.0, 100.0, 20.0)
    assert _table_block_x(bounds, 40.0, "left", "smart") == 10.0
    assert _table_block_x(bounds, 40.0, "center", "smart") == 40.0
    assert _table_block_x(bounds, 40.0, "right", "smart") == 70.0


def test_template_style_preview_reports_single_page_height_for_width():
    _app()
    preview = TemplateStylePreview()
    preview.refresh(create_builtin_template("thesis_gbt"))

    try:
        target_height = preview.heightForWidth(820)

        assert preview.hasHeightForWidth() is True
        assert target_height > 1000
        assert preview.sizeHint().height() == preview.heightForWidth(preview.sizeHint().width())
    finally:
        preview.close()


def test_template_style_preview_renders_without_crashing():
    app = _app()
    preview = TemplateStylePreview()

    try:
        preview.refresh(create_builtin_template("thesis_gbt"))
        target_height = preview.heightForWidth(820)
        preview.resize(820, target_height)
        preview.show()
        app.processEvents()

        pixmap = preview.grab()

        assert pixmap.isNull() is False
        assert preview.width() == 820
        assert preview.height() == target_height
        assert pixmap.deviceIndependentSize().width() == 820
        assert abs(pixmap.deviceIndependentSize().height() - target_height) < 1.0
    finally:
        preview.close()
        app.processEvents()


def test_template_style_preview_places_table_before_abstract():
    _app()
    cfg = create_builtin_template("thesis_gbt")
    cfg.heading_model.max_heading_levels = 3

    paragraphs = _build_template_preview_paragraphs(cfg)
    style_keys = [paragraph.style_key for paragraph in paragraphs]

    assert "table_preview" in style_keys
    assert style_keys.index("heading3") < style_keys.index("table_preview")
    assert style_keys.index("table_preview") < style_keys.index("non_numbered_heading")

    preview = TemplateStylePreview()
    try:
        preview.refresh(cfg)
        layout = preview._cached_layout
        assert layout is not None
        assert layout.table_layouts

        table_rect = layout.table_layouts[0].rect
        abstract_line = next(line for line in layout.line_layouts if line.style_key == "non_numbered_heading")
        assert table_rect.bottom() < abstract_line.y
    finally:
        preview.close()


def test_template_style_preview_maps_table_alignment_and_color_header_style():
    _app()
    cfg = create_builtin_template("thesis_gbt")
    cfg.heading_model.max_heading_levels = 3
    cfg.table.border_mode = "color_table"
    cfg.table.color_table_variant = "header_grid"
    cfg.table.cell_alignment = "center"
    cfg.table.first_row_bold = False
    cfg.table.bold = True
    cfg.table.italic = True

    preview = TemplateStylePreview()
    try:
        preview.refresh(cfg)
        layout = preview._cached_layout
        assert layout is not None
        table = layout.table_layouts[0]
        assert table.cell_alignment == "center"
        assert table.font.bold() is True
        assert table.font.italic() is True
        assert table.header_font.bold() is True
        assert table.header_font.italic() is True
    finally:
        preview.close()


def test_template_style_preview_maps_table_block_alignment():
    _app()
    left_cfg = create_builtin_template("thesis_gbt")
    left_cfg.heading_model.max_heading_levels = 3
    left_cfg.table.layout_mode = "compact"
    left_cfg.table.table_alignment = "left"

    right_cfg = create_builtin_template("thesis_gbt")
    right_cfg.heading_model.max_heading_levels = 3
    right_cfg.table.layout_mode = "compact"
    right_cfg.table.table_alignment = "right"

    preview = TemplateStylePreview()
    try:
        preview.refresh(left_cfg)
        left_layout = preview._cached_layout
        assert left_layout is not None
        left_table = left_layout.table_layouts[0]

        preview.refresh(right_cfg)
        right_layout = preview._cached_layout
        assert right_layout is not None
        right_table = right_layout.table_layouts[0]

        assert left_table.table_alignment == "left"
        assert right_table.table_alignment == "right"
        assert right_table.rect.left() > left_table.rect.left()
    finally:
        preview.close()


def test_template_style_preview_table_line_spacing_affects_row_height():
    _app()
    single_cfg = create_builtin_template("thesis_gbt")
    single_cfg.heading_model.max_heading_levels = 3
    single_cfg.table.line_spacing_mode = "single"

    double_cfg = create_builtin_template("thesis_gbt")
    double_cfg.heading_model.max_heading_levels = 3
    double_cfg.table.line_spacing_mode = "double"

    preview = TemplateStylePreview()
    try:
        preview.refresh(single_cfg)
        single_layout = preview._cached_layout
        assert single_layout is not None
        single_h = single_layout.table_layouts[0].rect.height()

        preview.refresh(double_cfg)
        double_layout = preview._cached_layout
        assert double_layout is not None
        double_h = double_layout.table_layouts[0].rect.height()

        assert double_h > single_h
    finally:
        preview.close()


def test_template_style_preview_full_table_keeps_border_inside_clip():
    _app()
    cfg = create_builtin_template("thesis_gbt")
    cfg.heading_model.max_heading_levels = 3
    cfg.table.layout_mode = "full"
    cfg.table.border_mode = "full_grid"
    cfg.table.border_width_pt = 1.2

    preview = TemplateStylePreview()
    try:
        preview.refresh(cfg)
        layout = preview._cached_layout
        assert layout is not None
        table = layout.table_layouts[0]
        text_rect = layout.content_rect.adjusted(4.0, 6.0, -4.0, -6.0)

        assert table.rect.left() > text_rect.left()
        assert table.rect.right() < text_rect.right()
        assert table.rect.width() > text_rect.width() - 6.0
    finally:
        preview.close()


def test_template_style_preview_distinguishes_keep_and_none_table_borders():
    app = _app()

    def border_pixel_count(border_mode: str) -> int:
        cfg = create_builtin_template("thesis_gbt")
        cfg.heading_model.max_heading_levels = 1
        cfg.table.border_mode = border_mode

        preview = TemplateStylePreview()
        try:
            preview.refresh(cfg)
            target_height = preview.heightForWidth(820)
            preview.resize(820, target_height)
            preview.show()
            app.processEvents()

            layout = preview._cached_layout
            assert layout is not None
            table = layout.table_layouts[0]
            image = preview.grab().toImage()

            x0 = max(0, int(table.rect.left()) + 3)
            x1 = min(image.width() - 1, int(table.rect.right()) - 3)
            y0 = max(0, int(table.rect.top()) - 2)
            y1 = min(image.height() - 1, int(table.rect.top()) + 3)
            count = 0
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    color = image.pixelColor(x, y)
                    if color.red() < 245 or color.green() < 245 or color.blue() < 245:
                        count += 1
            return count
        finally:
            preview.close()
            app.processEvents()

    assert border_pixel_count("keep") > border_pixel_count("none") + 8


def test_template_style_preview_resolves_named_heading_sizes_for_rendering():
    _app()
    cfg = TemplateConfig()
    cfg.styles["body"] = StyleConfig(size_pt=12)
    cfg.styles["heading1"] = StyleConfig(size_pt=None, size_display="18", bold=True)

    preview = TemplateStylePreview()
    try:
        preview.refresh(cfg)
        layout = preview._cached_layout
        heading_line = next(line for line in layout.line_layouts if line.style_key == "heading1")
        body_line = next(line for line in layout.line_layouts if line.style_key == "body")

        assert heading_line.font.pixelSize() > body_line.font.pixelSize()
    finally:
        preview.close()


def test_template_style_preview_uses_shared_indent_resolution_for_hanging_indent():
    _app()
    cfg = TemplateConfig()
    cfg.styles["body"] = StyleConfig(
        size_pt=12,
        left_indent_chars=0,
        left_indent_unit="pt",
        hanging_indent_chars=18,
        hanging_indent_unit="pt",
    )

    preview = TemplateStylePreview()
    try:
        preview.refresh(cfg)
        layout = preview._cached_layout
        assert layout is not None

        body_line = next(line for line in layout.line_layouts if line.style_key == "body")
        paper_w_cm, _ = _paper_dimensions_cm(cfg.page_setup.paper_size)
        pt_to_px = layout.page_rect.width() / (paper_w_cm * CM_TO_PT)
        text_rect = layout.content_rect.adjusted(4.0, 6.0, -4.0, -6.0)
        indents_pt = resolve_preview_indents_pt(cfg.styles["body"], size_pt=12.0)

        expected_x = text_rect.left() + indents_pt["left_pt"] * pt_to_px

        assert round(indents_pt["left_pt"], 1) == 18.0
        assert abs(body_line.x - expected_x) < 1.5
    finally:
        preview.close()


def test_template_style_preview_renders_line_based_paragraph_spacing():
    _app()
    cfg = TemplateConfig()
    cfg.styles["body"] = StyleConfig(
        size_pt=12,
        line_spacing_type="exact",
        line_spacing_pt=20,
        space_before_pt=2.0,
        space_before_unit="lines",
    )

    preview = TemplateStylePreview()
    try:
        preview.refresh(cfg)
        layout = preview._cached_layout
        assert layout is not None
        first_line = next(line for line in layout.line_layouts if line.style_key == "body")
        assert first_line.y > 10
    finally:
        preview.close()
