from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtTest import QTest

from src.config.builtin_templates import create_builtin_template
from src.config.resolver import resolve_template_baseline
from src.config.template import StyleConfig
from src.modules.registry import create_all_modules
from src.pipeline.module_selection import build_module_selection_plan
from src.qt_api import QApplication, Qt
from src.ui.panels.template_preview.layout import build_template_preview_layout
from src.ui.panels.template_preview.model import (
    PreviewBlockKind,
    TemplatePreviewMode,
)
from src.ui.panels.template_preview.projector import (
    build_template_preview_projection,
)
from src.ui.panels.template_preview.widget import TemplateStylePreview


def _projection(*, landscape: bool = False, large: bool = False):
    template = create_builtin_template("default")
    if landscape:
        template.page_setup.orientation = "landscape"
    if large:
        for style in template.styles.values():
            style.size_pt = 26
            style.space_before_pt = 18
            style.space_after_pt = 18
    config = resolve_template_baseline(template)
    modules = create_all_modules()
    defaults = {
        module.meta.name: module.meta.enabled_by_default
        for module in modules
    }
    selection = build_module_selection_plan(modules, defaults.__getitem__)
    return build_template_preview_projection(
        config,
        selection,
        mode=TemplatePreviewMode.TEMPLATE_BASELINE,
    )


def _flow_blocks(projection):
    return tuple(
        block
        for block in projection.blocks
        if block.kind
        not in {
            PreviewBlockKind.PAGE_GUIDES,
            PreviewBlockKind.HEADER,
            PreviewBlockKind.FOOTER,
        }
    )


def _long_projection():
    """Create overflow without relying on optional feature showcase blocks."""

    projection = _projection(large=True)
    fixed = tuple(
        block
        for block in projection.blocks
        if block.kind
        in {
            PreviewBlockKind.PAGE_GUIDES,
            PreviewBlockKind.HEADER,
            PreviewBlockKind.FOOTER,
        }
    )
    return replace(projection, blocks=fixed + _flow_blocks(projection) * 4)


def test_landscape_layout_uses_one_consistent_page_aspect_ratio():
    projection = _projection(landscape=True)
    layout = build_template_preview_layout(projection, 900)
    page = layout.pages[0]

    assert projection.page_geometry.width_cm == 29.7
    assert projection.page_geometry.height_cm == 21.0
    assert round(page.page_rect.width() / page.page_rect.height(), 3) == round(29.7 / 21.0, 3)
    assert round(page.scale_x, 3) == round(page.scale_y, 3)


def test_typography_scale_uses_each_paper_width_instead_of_an_a4_constant():
    a4 = _projection()
    a3_template = create_builtin_template("default")
    a3_template.page_setup.paper_size = "A3"
    a3 = build_template_preview_projection(
        resolve_template_baseline(a3_template),
        mode=TemplatePreviewMode.TEMPLATE_BASELINE,
    )

    a4_layout = build_template_preview_layout(a4, 900)
    a3_layout = build_template_preview_layout(a3, 900)
    a4_body = next(
        item
        for item in a4_layout.pages[0].block_layouts
        if item.block.kind is PreviewBlockKind.BODY
    )
    a3_body = next(
        item
        for item in a3_layout.pages[0].block_layouts
        if item.block.kind is PreviewBlockKind.BODY
    )

    assert a3_body.font.pixelSize() < a4_body.font.pixelSize()
    assert a3_body.pt_scale < a4_body.pt_scale


def test_overflow_uses_compact_density_then_adds_pages_without_dropping_blocks():
    projection = _long_projection()
    layout = build_template_preview_layout(projection, 700)
    rendered = tuple(
        block_layout.block
        for page in layout.pages
        for block_layout in page.block_layouts
    )

    assert layout.compact is True
    assert len(layout.pages) >= 2
    assert rendered == _flow_blocks(projection)


def test_narrow_multi_page_layout_stacks_and_wide_layout_can_pair_pages():
    projection = _long_projection()
    narrow = build_template_preview_layout(projection, 420)
    wide = build_template_preview_layout(projection, 1200)

    assert len(narrow.pages) >= 2
    assert narrow.columns == 1
    assert len(wide.pages) >= 2
    assert wide.columns == 2


def test_compact_density_changes_sample_text_not_projected_style_values():
    projection = _projection(large=True)
    before_styles = tuple(block.style for block in projection.blocks)
    layout = build_template_preview_layout(projection, 700)

    assert layout.compact is True
    assert tuple(block.style for block in projection.blocks) == before_styles
    assert any(
        block_layout.text == block_layout.block.compact_text
        for page in layout.pages
        for block_layout in page.block_layouts
        if block_layout.block.compact_text
    )


def test_heading_space_before_is_rendered_above_text_not_as_extra_space_after():
    template = create_builtin_template("default")
    template.styles["heading2"] = StyleConfig(
        size_pt=14,
        space_before_pt=24,
        space_after_pt=6,
    )
    body = template.styles.get("body") or template.styles["normal"]
    body.space_before_pt = 0
    body.space_after_pt = 0
    projection = build_template_preview_projection(
        resolve_template_baseline(template),
        mode=TemplatePreviewMode.TEMPLATE_BASELINE,
    )

    layout = build_template_preview_layout(projection, 900)
    block_layouts = [
        item
        for page in layout.pages
        for item in page.block_layouts
    ]
    heading_index = next(
        index
        for index, item in enumerate(block_layouts)
        if item.block.kind is PreviewBlockKind.HEADING
        and item.block.level == 2
    )
    heading_layout = block_layouts[heading_index]
    body_layout = block_layouts[heading_index + 1]
    base_gap = 4.0 if layout.compact else 6.0

    assert body_layout.block.kind is PreviewBlockKind.BODY
    assert heading_layout.space_before_px == pytest.approx(
        24 * heading_layout.pt_scale
    )
    assert heading_layout.space_after_px == pytest.approx(
        6 * heading_layout.pt_scale
    )
    visible_gap = (
        body_layout.rect.top()
        + body_layout.space_before_px
        - (
            heading_layout.rect.bottom()
            - heading_layout.space_after_px
        )
    )
    assert visible_gap == pytest.approx(
        base_gap + heading_layout.space_after_px
    )
    assert visible_gap < heading_layout.space_before_px


def test_widget_opens_whole_preview_and_skips_equal_projection_rebuild():
    app = QApplication.instance() or QApplication([])
    projection = _projection()
    widget = TemplateStylePreview()
    requests: list[bool] = []
    widget.preview_requested.connect(lambda: requests.append(True))
    try:
        widget.resize(900, 1000)
        widget.set_projection(projection)
        widget.show()
        app.processEvents()
        snapshot = widget.layout_snapshot

        widget.set_projection(replace(projection))
        app.processEvents()

        assert widget.layout_snapshot is snapshot
        assert widget.toolTip() == ""
        assert widget.focusPolicy() == Qt.StrongFocus
        assert widget.cursor().shape() == Qt.PointingHandCursor
        assert widget.accessibleName() == "模板样式预览，点击打开整体预览"
        assert projection.status_text in widget.accessibleDescription()
        assert snapshot.page_width == 640.0

        QTest.mouseClick(
            widget,
            Qt.LeftButton,
            pos=snapshot.pages[0].content_rect.center().toPoint(),
        )
        QTest.keyClick(widget, Qt.Key_Return)
        assert requests == [True, True]
    finally:
        widget.close()
        app.processEvents()


def test_inline_and_dialog_presentations_use_distinct_page_width_caps():
    app = QApplication.instance() or QApplication([])
    projection = _projection()
    inline = TemplateStylePreview(presentation="inline")
    dialog = TemplateStylePreview(presentation="dialog")
    try:
        for widget in (inline, dialog):
            widget.resize(1000, 1200)
            widget.set_projection(projection)
        app.processEvents()

        assert inline.layout_snapshot.page_width == 640.0
        assert dialog.layout_snapshot.page_width == 900.0
    finally:
        inline.close()
        dialog.close()
        app.processEvents()


def test_margin_guides_use_dimension_lines_without_rotated_side_labels():
    source = (
        Path(__file__).resolve().parents[1]
        / "src/ui/panels/template_preview/widget.py"
    ).read_text(encoding="utf-8")

    assert "_draw_horizontal_dimension" in source
    assert "_draw_vertical_dimension" in source
    assert "painter.rotate(-90)" not in source
    assert "painter.rotate(90)" not in source
