import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene import SceneWorkspace
from src.config.template import StyleConfig, TemplateConfig
from src.ui.panels.style_difference_projection import (
    StyleDifferenceProjection,
    StyleDifferenceSummaryProjection,
    build_scene_style_difference_projections,
    build_style_difference_projection,
    build_style_difference_summary_projection,
)


def test_style_difference_projection_uses_conservative_label_without_template():
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    scene.section_styles["references_body"] = StyleConfig()

    projection = build_style_difference_projection(scene, None, "references_body")

    assert projection.template_available is False
    assert projection.overridden is True
    assert projection.follows_template is False
    assert projection.changed_labels == ()
    assert projection.detail_label == "独立设置"
    assert projection.compact_label == "参考文献"
    assert projection.source_line_label == "参考文献"
    assert projection.diff_tag == "参考文献：独立设置"
    assert projection.current_status == "独立样式"
    assert projection.difference_status == "待比较"


def test_style_difference_projection_compacts_changed_fields_against_template():
    template = TemplateConfig()
    template.styles["body"] = StyleConfig(line_spacing_type="exact", line_spacing_pt=20)
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    scene.section_styles["references_body"] = StyleConfig(
        line_spacing_type="exact",
        line_spacing_pt=26,
    )

    projection = build_style_difference_projection(scene, template, "references_body")

    assert projection.template_available is True
    assert projection.overridden is True
    assert projection.changed_labels == ("行距",)
    assert projection.detail_label == "行距"
    assert projection.compact_label == "参考文献（行距）"
    assert projection.source_line_label == "参考文献（行距）"
    assert projection.diff_tag == "参考文献：行距"
    assert projection.status_label == "有格式例外"
    assert projection.template_status == "模板基线"
    assert projection.current_status == "独立样式"
    assert projection.difference_status == "已调整 1 项"
    assert projection.detail == "不同：行距"


def test_style_difference_projection_marks_independent_style_that_matches_template():
    template = TemplateConfig()
    template.styles["body"] = StyleConfig(line_spacing_type="exact", line_spacing_pt=20)
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    scene.section_styles["references_body"] = StyleConfig(
        line_spacing_type="exact",
        line_spacing_pt=20,
    )

    projection = build_style_difference_projection(scene, template, "references_body")

    assert projection.overridden is True
    assert projection.changed_labels == ()
    assert projection.detail_label == "与模板一致"
    assert projection.compact_label == "参考文献（与模板一致）"
    assert projection.status_label == "有独立样式"
    assert projection.difference_status == "未改字段"
    assert projection.detail == "已独立，但字段仍与模板一致。"


def test_scene_style_difference_projection_filters_to_overridden_sections():
    template = TemplateConfig()
    template.styles["body"] = StyleConfig(line_spacing_type="exact", line_spacing_pt=20)
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    scene.section_styles["references_body"] = StyleConfig(
        line_spacing_type="exact",
        line_spacing_pt=26,
    )

    projections = build_scene_style_difference_projections(
        scene,
        template,
        overridden_only=True,
    )

    assert [projection.variant_key for projection in projections] == ["references_body"]
    assert [projection.compact_label for projection in projections] == ["参考文献（行距）"]


def test_style_difference_summary_projection_returns_none_without_overrides():
    assert build_style_difference_summary_projection(()) is None
    assert (
        build_style_difference_summary_projection(
            (
                StyleDifferenceProjection(
                    variant_key="references_body",
                    scope_label="参考文献",
                    section_enabled=True,
                    overridden=False,
                    follows_template=True,
                    template_available=True,
                    current_status="跟随模板",
                    difference_status="无差异",
                ),
            )
        )
        is None
    )


def test_style_difference_summary_projection_keeps_single_section_readable():
    summary = build_style_difference_summary_projection(
        (
            StyleDifferenceProjection(
                variant_key="references_body",
                scope_label="参考文献",
                section_enabled=True,
                overridden=True,
                follows_template=False,
                template_available=True,
                changed_labels=("行距",),
                current_status="独立样式",
                difference_status="已调整 1 项",
                detail="不同：行距",
                variant="warning",
            ),
        )
    )

    assert isinstance(summary, StyleDifferenceSummaryProjection)
    assert summary.section_count == 1
    assert summary.changed_section_count == 1
    assert summary.pending_section_count == 0
    assert summary.template_status == "模板基线"
    assert summary.current_status == "参考文献 独立样式"
    assert summary.difference_status == "已调整 1 项"
    assert summary.detail == "不同：行距"
    assert summary.variant == "warning"


def test_style_difference_summary_projection_aggregates_multiple_sections():
    summary = build_style_difference_summary_projection(
        (
            StyleDifferenceProjection(
                variant_key="references_body",
                scope_label="参考文献",
                section_enabled=True,
                overridden=True,
                follows_template=False,
                template_available=True,
                changed_labels=("行距",),
                current_status="独立样式",
                difference_status="已调整 1 项",
                detail="不同：行距",
            ),
            StyleDifferenceProjection(
                variant_key="acknowledgment_body",
                scope_label="致谢",
                section_enabled=True,
                overridden=True,
                follows_template=False,
                template_available=True,
                changed_labels=("字号", "中文字体"),
                current_status="独立样式",
                difference_status="已调整 2 项",
                detail="不同：字号、中文字体",
            ),
            StyleDifferenceProjection(
                variant_key="abstract_body",
                scope_label="摘要",
                section_enabled=True,
                overridden=True,
                follows_template=False,
                template_available=True,
                changed_labels=(),
                current_status="独立样式",
                difference_status="未改字段",
                detail="已独立，但字段仍与模板一致。",
            ),
        )
    )

    assert isinstance(summary, StyleDifferenceSummaryProjection)
    assert summary.section_count == 3
    assert summary.changed_section_count == 2
    assert summary.pending_section_count == 0
    assert summary.current_status == "3 个格式例外"
    assert summary.difference_status == "2 个格式例外已调整"
    assert summary.detail == "不同：参考文献改了行距；致谢改了字号、中文字体"


def test_style_difference_summary_projection_aggregates_pending_compare_sections():
    summary = build_style_difference_summary_projection(
        (
            StyleDifferenceProjection(
                variant_key="references_body",
                scope_label="参考文献",
                section_enabled=True,
                overridden=True,
                follows_template=False,
                template_available=False,
                current_status="独立样式",
                difference_status="待比较",
                detail="需要模板基线后比较字段差异。",
            ),
            StyleDifferenceProjection(
                variant_key="acknowledgment_body",
                scope_label="致谢",
                section_enabled=True,
                overridden=True,
                follows_template=False,
                template_available=False,
                current_status="独立样式",
                difference_status="待比较",
                detail="需要模板基线后比较字段差异。",
            ),
        )
    )

    assert isinstance(summary, StyleDifferenceSummaryProjection)
    assert summary.section_count == 2
    assert summary.changed_section_count == 0
    assert summary.pending_section_count == 2
    assert summary.current_status == "2 个格式例外"
    assert summary.difference_status == "待比较"
    assert summary.detail == "需要模板基线后比较：参考文献；致谢"
