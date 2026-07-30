from __future__ import annotations

import copy

import pytest

from src.config.scene_presets import SCENE_FACTORIES, create_scene
import src.ui.panels.scene_product_summary_projection as product_projection
import src.ui.panels.scene_summary_projection as engineering_projection


PUBLIC_CONSTANTS = (
    "COVERAGE_PACK_DISPLAY_LABELS",
    "FAMILY_DISPLAY_LABELS",
    "FAILURE_POLICY_LABELS",
    "FORMAT_DISPLAY_LABELS",
    "LATEX_POLICY_LABELS",
    "MARKDOWN_POLICY_LABELS",
    "PRESERVATION_MODE_LABELS",
)

SCENE_FUNCTIONS = (
    "build_compliance_summary_items",
    "build_delivery_summary_items",
    "build_input_profile_summary_items",
    "build_product_scene_overview_summary_items",
    "build_scene_scope_summary_items",
    "recommended_object_preflight_targets_for_scene",
    "scene_document_scope_display_name",
)

SCALAR_CASES = {
    "material_asset_role_display_name": (
        "primary",
        "reference",
        "attachment",
        "unknown",
        "",
        None,
    ),
    "material_field_display_name": (
        "title",
        "body",
        "answer",
        "analysis",
        "unknown",
        "",
        None,
    ),
    "material_schema_display_name": (
        "document",
        "question_bank",
        "table",
        "unknown",
        "",
        None,
    ),
}


def test_product_projection_constants_match_engineering_projection():
    for name in PUBLIC_CONSTANTS:
        assert getattr(product_projection, name) == getattr(
            engineering_projection,
            name,
        )


@pytest.mark.parametrize("scene_id", sorted(SCENE_FACTORIES))
@pytest.mark.parametrize("function_name", SCENE_FUNCTIONS)
def test_product_scene_projection_matches_engineering_projection(
    scene_id,
    function_name,
):
    product_scene = copy.deepcopy(create_scene(scene_id))
    engineering_scene = copy.deepcopy(create_scene(scene_id))

    assert getattr(product_projection, function_name)(product_scene) == getattr(
        engineering_projection,
        function_name,
    )(engineering_scene)


@pytest.mark.parametrize(
    ("function_name", "value"),
    [
        (function_name, value)
        for function_name, values in SCALAR_CASES.items()
        for value in values
    ],
)
def test_product_scalar_projection_matches_engineering_projection(
    function_name,
    value,
):
    assert getattr(product_projection, function_name)(value) == getattr(
        engineering_projection,
        function_name,
    )(value)


def test_nullable_product_projection_matches_engineering_projection():
    assert product_projection.build_scene_scope_summary_items(None) == (
        engineering_projection.build_scene_scope_summary_items(None)
    )
    assert product_projection.scene_document_scope_display_name(None) == (
        engineering_projection.scene_document_scope_display_name(None)
    )
