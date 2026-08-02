from dataclasses import asdict

from src.config.builtin_templates import create_builtin_template
from src.config.resolver import resolve_config, resolve_template_baseline
from src.config.scene import SceneWorkspace
from src.modules.registry import create_all_modules
from src.pipeline.module_selection import (
    ModuleDisposition,
    build_module_selection_plan,
)
from src.ui.panels.template_feature_specs import (
    TEMPLATE_FEATURE_BY_ID,
    TEMPLATE_FEATURE_SPECS,
)
from src.ui.panels.template_preview.model import (
    PreviewBlockKind,
    TemplatePreviewMode,
)
from src.ui.panels.template_preview.projector import (
    build_template_preview_projection,
)
from src.ui.panels.template_overview_projection import (
    build_template_overview_projection,
)


def _current_projection(
    *,
    switches: dict[str, bool] | None = None,
    template_id: str = "default",
):
    template = create_builtin_template(template_id)
    scene = SceneWorkspace()
    scene.module_switches.update(switches or {})
    config = resolve_config(template, scene)
    modules = create_all_modules()
    selection = build_module_selection_plan(modules, config.is_module_enabled)
    projection = build_template_preview_projection(
        config,
        selection,
        mode=TemplatePreviewMode.CURRENT_PLAN,
    )
    return template, scene, config, selection, projection


def _blocks(projection, kind: PreviewBlockKind):
    return tuple(block for block in projection.blocks if block.kind is kind)


def test_baseline_projection_ignores_plan_mask_and_shows_template_facts():
    template = create_builtin_template("default")
    config = resolve_template_baseline(template)
    modules = create_all_modules()
    defaults = {
        module.meta.name: module.meta.enabled_by_default
        for module in modules
    }
    selection = build_module_selection_plan(modules, defaults.__getitem__)

    projection = build_template_preview_projection(
        config,
        selection,
        mode=TemplatePreviewMode.TEMPLATE_BASELINE,
    )

    assert projection.status_text == "展示当前模板配置的样式基线"
    assert projection.hidden_feature_labels == ()
    assert projection.auto_pruned == ()
    assert _blocks(projection, PreviewBlockKind.PAGE_GUIDES)
    assert _blocks(projection, PreviewBlockKind.TABLE)
    assert _blocks(projection, PreviewBlockKind.TABLE_CAPTION)
    assert _blocks(projection, PreviewBlockKind.TOC) == ()
    assert _blocks(projection, PreviewBlockKind.FIGURE_CAPTION) == ()
    formula = _blocks(projection, PreviewBlockKind.FORMULA)
    assert formula == ()
    assert _blocks(projection, PreviewBlockKind.REFERENCE) == ()
    assert _blocks(projection, PreviewBlockKind.WATERMARK) == ()


def test_page_setup_master_off_uses_neutral_page_and_hides_every_page_guide():
    *_unused, projection = _current_projection(
        switches={"page_setup": False, "section_format": False}
    )

    assert projection.page_geometry.neutral is True
    assert projection.page_geometry.paper_label == "A4"
    assert projection.show_page_guides is False
    assert projection.show_header_distance_guide is False
    assert projection.show_footer_distance_guide is False
    assert "页面设置" in projection.hidden_feature_labels


def test_page_and_section_modules_have_independent_feature_state():
    *_unused, selection, projection = _current_projection(
        switches={"page_setup": False, "section_format": True}
    )

    assert selection.is_effectively_enabled("page_setup") is False
    assert selection.is_effectively_enabled("section_format") is True
    assert _blocks(projection, PreviewBlockKind.PAGE_GUIDES) == ()
    assert "页面设置" not in projection.hidden_feature_labels
    # A section break is document structure, not a fabricated style sample.
    assert _blocks(projection, PreviewBlockKind.SECTION_MARKER) == ()


def test_paragraph_off_keeps_numbered_neutral_heading_without_body():
    *_unused, projection = _current_projection(
        switches={"paragraph_style": False, "heading_numbering": True}
    )

    headings = _blocks(projection, PreviewBlockKind.HEADING)
    assert headings
    assert headings[0].text != "绪论"
    assert _blocks(projection, PreviewBlockKind.BODY) == ()


def test_numbering_off_keeps_heading_text_without_adding_a_toc_sample():
    *_unused, projection = _current_projection(
        switches={"heading_numbering": False, "toc": True}
    )

    assert _blocks(projection, PreviewBlockKind.HEADING)[0].text == "绪论"
    assert _blocks(projection, PreviewBlockKind.TOC) == ()


def test_heading_recognition_off_auto_prunes_numbering_and_toc():
    *_unused, selection, projection = _current_projection(
        switches={"heading_recognition": False}
    )

    assert selection.decision_for("heading_numbering").disposition is ModuleDisposition.AUTO_PRUNED
    assert selection.decision_for("toc").disposition is ModuleDisposition.AUTO_PRUNED
    assert _blocks(projection, PreviewBlockKind.TOC) == ()
    assert {item.module_name for item in projection.auto_pruned} >= {
        "heading_numbering",
        "toc",
    }
    assert "依赖未满足" in projection.status_text


def test_table_caption_follows_the_table_sample_visibility():
    *_unused, projection = _current_projection(
        switches={"table_format": False, "caption": True}
    )

    assert _blocks(projection, PreviewBlockKind.TABLE) == ()
    assert _blocks(projection, PreviewBlockKind.FIGURE_CAPTION) == ()
    assert _blocks(projection, PreviewBlockKind.TABLE_CAPTION) == ()


def test_table_title_is_the_only_caption_sample_and_precedes_the_table():
    *_unused, projection = _current_projection(
        switches={"table_format": True, "caption": True}
    )

    kinds = tuple(block.kind for block in projection.blocks)
    assert kinds.count(PreviewBlockKind.TABLE_CAPTION) == 1
    assert PreviewBlockKind.FIGURE_CAPTION not in kinds
    assert kinds.index(PreviewBlockKind.TABLE_CAPTION) < kinds.index(PreviewBlockKind.TABLE)


def test_table_projection_uses_the_same_three_line_and_color_preset_facts():
    template = create_builtin_template("default")
    template.table.border_mode = "color_table"
    template.table.color_table_accent = "orange"
    template.table.color_table_variant = "header_grid_zebra"
    projection = build_template_preview_projection(
        resolve_template_baseline(template),
        mode=TemplatePreviewMode.TEMPLATE_BASELINE,
    )

    table = _blocks(projection, PreviewBlockKind.TABLE)[0].table_style
    assert table is not None
    assert table.border_mode == "color_table"
    assert table.accent_color == "ED7D31"
    assert table.header_fill is True
    assert table.show_vertical is True
    assert table.show_horizontal is True
    assert table.zebra is True


def test_supplementary_capabilities_are_not_promoted_into_the_general_preview():
    template = create_builtin_template("default")
    template.watermark.enabled = True
    template.watermark.text = "内部"
    projection = build_template_preview_projection(
        resolve_template_baseline(template),
        mode=TemplatePreviewMode.TEMPLATE_BASELINE,
    )

    assert _blocks(projection, PreviewBlockKind.TOC) == ()
    assert _blocks(projection, PreviewBlockKind.FIGURE_CAPTION) == ()
    assert _blocks(projection, PreviewBlockKind.FORMULA) == ()
    assert _blocks(projection, PreviewBlockKind.REFERENCE) == ()
    assert _blocks(projection, PreviewBlockKind.WATERMARK) == ()


def test_header_footer_projection_preserves_first_even_and_default_variants():
    template = create_builtin_template("default")
    hf = template.header_footer
    hf.behavior.different_first_page = True
    hf.behavior.different_odd_even_pages = True
    hf.variants.first.header.mode = "none"
    hf.variants.first.footer.mode = "fixed"
    hf.variants.first.footer.fixed_text = "首页页脚"
    hf.variants.even.header.mode = "fixed"
    hf.variants.even.header.fixed_text = "偶数页页眉"
    projection = build_template_preview_projection(
        resolve_template_baseline(template),
        mode=TemplatePreviewMode.TEMPLATE_BASELINE,
    )

    headers = {block.page_variant: block for block in _blocks(projection, PreviewBlockKind.HEADER)}
    footers = {block.page_variant: block for block in _blocks(projection, PreviewBlockKind.FOOTER)}
    assert set(headers) == {"default", "first", "even"}
    assert headers["first"].text == ""
    assert headers["even"].text == "偶数页页眉"
    assert "首页页脚" in footers["first"].text
    assert "1" in footers["first"].text


def test_header_footer_projection_applies_independent_first_even_page_number_strategy():
    template = create_builtin_template("default")
    hf = template.header_footer
    hf.behavior.different_first_page = True
    hf.behavior.different_odd_even_pages = True
    hf.variants.first.footer.mode = "fixed"
    hf.variants.first.footer.fixed_text = "首页文字"
    hf.page_number_plan.first.visibility = "hide"
    hf.page_number_plan.even.visibility = "show"
    hf.page_number_plan.even.template = "第 {page} 页 / 共 {pages} 页"
    hf.page_number_plan.even.alignment = "right"

    projection = build_template_preview_projection(
        resolve_template_baseline(template),
        mode=TemplatePreviewMode.TEMPLATE_BASELINE,
    )

    footers = {block.page_variant: block for block in _blocks(projection, PreviewBlockKind.FOOTER)}
    assert footers["first"].text == "首页文字"
    assert "第 1 页 / 共 10 页" in footers["even"].text
    assert footers["even"].alignment == "right"


def test_header_footer_off_hides_content_and_distance_guides():
    *_unused, projection = _current_projection(
        switches={"header_footer": False}
    )

    assert _blocks(projection, PreviewBlockKind.HEADER) == ()
    assert _blocks(projection, PreviewBlockKind.FOOTER) == ()
    assert projection.show_header_distance_guide is False
    assert projection.show_footer_distance_guide is False


def test_header_and_footer_subcontrols_remain_independent():
    template = create_builtin_template("default")
    template.header_footer.header.enabled = False
    template.header_footer.footer.enabled = True
    scene = SceneWorkspace()
    config = resolve_config(template, scene)
    modules = create_all_modules()
    selection = build_module_selection_plan(modules, config.is_module_enabled)

    projection = build_template_preview_projection(
        config,
        selection,
        mode=TemplatePreviewMode.CURRENT_PLAN,
    )

    assert _blocks(projection, PreviewBlockKind.HEADER) == ()
    assert _blocks(projection, PreviewBlockKind.FOOTER)
    assert projection.show_header_distance_guide is False
    assert projection.show_footer_distance_guide is True


def test_caption_auto_insert_false_keeps_the_table_title_style_sample_only():
    template = create_builtin_template("default")
    template.caption.auto_insert = False
    scene = SceneWorkspace()
    config = resolve_config(template, scene)
    modules = create_all_modules()
    selection = build_module_selection_plan(modules, config.is_module_enabled)

    projection = build_template_preview_projection(
        config,
        selection,
        mode=TemplatePreviewMode.CURRENT_PLAN,
    )

    assert _blocks(projection, PreviewBlockKind.FIGURE_CAPTION) == ()
    assert _blocks(projection, PreviewBlockKind.TABLE_CAPTION)


def test_all_preview_modules_off_produces_neutral_inline_empty_state():
    switches = {
        module_name: False
        for feature in TEMPLATE_FEATURE_SPECS
        for control in feature.module_controls
        for module_name in control.module_names
    }
    *_unused, projection = _current_projection(switches=switches)

    assert projection.is_empty is True
    assert projection.page_geometry.neutral is True
    assert projection.blocks[0].kind is PreviewBlockKind.EMPTY_STATE
    assert projection.status_text == "当前方案未启用可预览的格式处理"


def test_projection_does_not_mutate_template_scene_or_official_bindings():
    template = create_builtin_template("official_gbt")
    scene = SceneWorkspace()
    before_template = asdict(template)
    before_scene = asdict(scene)
    config = resolve_config(template, scene)
    modules = create_all_modules()
    selection = build_module_selection_plan(modules, config.is_module_enabled)

    projection = build_template_preview_projection(
        config,
        selection,
        mode=TemplatePreviewMode.CURRENT_PLAN,
    )

    assert projection.blocks
    assert template.heading_numbering.level_bindings
    assert asdict(template) == before_template
    assert asdict(scene) == before_scene


def test_feature_registry_has_one_page_control_for_two_backend_modules():
    assert len(TEMPLATE_FEATURE_SPECS) == len(
        {spec.feature_id for spec in TEMPLATE_FEATURE_SPECS}
    )
    assert len(TEMPLATE_FEATURE_SPECS) == len(
        {spec.card_id for spec in TEMPLATE_FEATURE_SPECS}
    )
    page = TEMPLATE_FEATURE_BY_ID["page"]
    assert len(page.module_controls) == 1
    assert page.module_controls[0].label == "应用页面设置"
    assert page.module_controls[0].module_names == (
        "page_setup",
        "section_format",
    )


def test_overview_projection_uses_registry_order_and_effective_summaries():
    template = create_builtin_template("default")
    scene = SceneWorkspace(
        template_overrides={"page_setup.paper_size": "B5"}
    )
    config = resolve_config(template, scene)
    modules = create_all_modules()
    selection = build_module_selection_plan(modules, config.is_module_enabled)

    overview = build_template_overview_projection(
        config,
        selection,
        mode=TemplatePreviewMode.CURRENT_PLAN,
    )

    assert tuple(feature.feature_id for feature in overview.features) == tuple(
        spec.feature_id for spec in TEMPLATE_FEATURE_SPECS
    )
    assert "B5" in overview.features[0].summary
    assert overview.coverage_labels == tuple(
        spec.action_label for spec in TEMPLATE_FEATURE_SPECS
    )
