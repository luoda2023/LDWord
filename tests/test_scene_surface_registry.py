from src.config.scene import SceneWorkspace
from src.config.work_mode import execution_work_mode_issue, resolve_work_mode_id
from src.config.scene_surface_registry import (
    scene_surface_for_scene,
    scene_uses_official_document_surface,
)
from src.ui.panels.scene_overview_projection import build_scene_overview_spec
from src.ui.panels.scene_state_projection import (
    scene_is_exam,
    scene_should_show_content_card,
)


def test_exam_surface_is_fixed_by_scene_identity_not_display_text():
    scene = SceneWorkspace(
        scene_id="custom",
        category="custom",
        name="exam notes",
        description="question paper cleanup",
    )

    assert scene_is_exam(scene) is False
    assert scene_should_show_content_card(scene) is True

    spec = build_scene_overview_spec(scene, template_label="Default")

    assert "scn_exam_paper" not in {
        row.target_card_id for row in spec.key_settings
    }


def test_exam_surface_is_owned_by_explicit_mode_not_ids_or_categories():
    assert scene_is_exam(SceneWorkspace(scene_id="exam", mode_id="exam")) is True
    assert scene_is_exam(
        SceneWorkspace(scene_id="custom", category="exam_paper", mode_id="exam")
    ) is True
    assert scene_is_exam(
        SceneWorkspace(scene_id="exam_teaching", mode_id="custom")
    ) is False


def test_explicit_mode_precedes_scene_mode_for_surface_selection():
    scene = SceneWorkspace(
        scene_id="custom",
        category="custom",
        mode_id="exam",
    )

    assert scene_surface_for_scene(scene).surface_id == "exam_paper"
    assert scene_surface_for_scene(scene, mode_id="   ").surface_id == "exam_paper"
    assert (
        scene_surface_for_scene(
            scene,
            mode_id="official_document",
        ).surface_id
        == "official_document"
    )
    assert scene_uses_official_document_surface(
        scene,
        mode_id="official_document",
    ) is True
    assert scene_is_exam(scene, mode_id="official_document") is False


def test_scene_mode_precedes_legacy_scene_identity_and_category():
    scene = SceneWorkspace(
        scene_id="official",
        category="official_document",
        mode_id="custom",
    )

    assert scene_surface_for_scene(scene).surface_id == "general"
    assert scene_uses_official_document_surface(scene) is False


def test_missing_mode_does_not_infer_surface_from_scene_identity_or_category():
    assert scene_uses_official_document_surface(
        SceneWorkspace(scene_id="official", category="custom")
    ) is False
    assert scene_uses_official_document_surface(
        SceneWorkspace(scene_id="custom", category="official_document")
    ) is False
    assert scene_surface_for_scene(
        SceneWorkspace(scene_id="official", category="exam_paper")
    ).surface_id == "general"


def test_ui_mode_normalizer_does_not_consult_scene_category():
    scene = SceneWorkspace(
        scene_id="custom",
        category="official_document",
        mode_id="",
    )

    assert resolve_work_mode_id(scene) == "custom"
    assert resolve_work_mode_id(
        scene,
        requested_mode_id="official_document",
    ) == "official"
    assert execution_work_mode_issue(scene) == "execution_mode_missing:scene.mode_id"
    assert execution_work_mode_issue(
        SceneWorkspace(mode_id="official_document")
    ) == (
        "execution_mode_not_canonical:scene.mode_id:"
        "official_document:official"
    )


def test_effective_mode_owner_preserves_unknown_explicit_mode_for_validation():
    scene = SceneWorkspace(scene_id="official", mode_id="official")

    assert resolve_work_mode_id(scene, requested_mode_id="Future_Mode") == "future_mode"
    assert scene_surface_for_scene(
        scene,
        mode_id="Future_Mode",
    ).surface_id == "general"
