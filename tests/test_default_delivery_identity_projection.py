from dataclasses import asdict
import json
from types import SimpleNamespace

import pytest

from src.config.builtin_templates import create_builtin_template
from src.config.default_delivery_identity import project_default_delivery_identity
from src.config.scene import DeliveryPreset
from src.config.scene_presets import create_exam_scene, create_official_scene
from src.config.template import TemplateConfig
from src.ui.panels.scene_navigation_projection import (
    output_navigation_snapshot,
    output_result_nav_summary,
)
from src.ui.panels.scene_output_detail import _OutputDetail
from src.ui.panels.scene_panel import (
    ScenePanel,
    _SceneOutputRulesCard,
    _SceneRulesDetail,
    _ScopeDetail,
)
from src.ui.bridge import PanelBridge
from src.ui.panels.scene_overview_projection import build_scene_overview_spec
from src.ui.panels.scene_summary_projection import (
    build_delivery_summary_items,
    build_scene_overview_summary_items,
)


INVALID_DEFAULT_ID = "missing_delivery"


def _scene_with_invalid_default():
    scene = create_official_scene()
    first_id = scene.delivery_presets[0].preset_id
    scene.default_delivery_preset_id = INVALID_DEFAULT_ID
    return scene, first_id


def _serialized_scene(scene) -> str:
    return json.dumps(
        asdict(scene),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def test_default_delivery_identity_projection_never_guesses_list_order():
    missing = project_default_delivery_identity(
        SimpleNamespace(default_delivery_preset_id="", delivery_presets=[])
    )
    invalid = project_default_delivery_identity(
        SimpleNamespace(
            default_delivery_preset_id="missing",
            delivery_presets=[SimpleNamespace(preset_id="first")],
        )
    )
    duplicate = project_default_delivery_identity(
        SimpleNamespace(
            default_delivery_preset_id="same",
            delivery_presets=[
                SimpleNamespace(preset_id="same"),
                SimpleNamespace(preset_id="same"),
            ],
        )
    )
    valid_preset = SimpleNamespace(preset_id="selected")
    valid = project_default_delivery_identity(
        SimpleNamespace(
            default_delivery_preset_id="selected",
            delivery_presets=[SimpleNamespace(preset_id="first"), valid_preset],
        )
    )

    assert (missing.status, missing.requested_id, missing.preset) == (
        "missing",
        "",
        None,
    )
    assert (invalid.status, invalid.requested_id, invalid.preset) == (
        "invalid",
        "missing",
        None,
    )
    assert duplicate.status == "invalid"
    assert duplicate.preset is None
    assert valid.status == "ok"
    assert valid.preset is valid_preset


def test_invalid_default_is_visible_across_summary_overview_and_navigation():
    scene, first_id = _scene_with_invalid_default()

    delivery_items = {item.key: item for item in build_delivery_summary_items(scene)}
    overview_items = {
        item.key: item for item in build_scene_overview_summary_items(scene)
    }
    overview = build_scene_overview_spec(scene)
    delivery_step = next(step for step in overview.run_steps if step.key == "deliver")
    delivery_row = next(row for row in overview.key_settings if row.key == "delivery")
    nav_summary = output_result_nav_summary(scene)
    nav_snapshot = output_navigation_snapshot(scene)

    expected = f"无效引用：{INVALID_DEFAULT_ID}"
    assert delivery_items["default_delivery"].value == expected
    assert delivery_items["default_artifacts"].value == "未设置"
    assert overview_items["delivery"].value == expected
    assert expected in delivery_step.detail
    assert INVALID_DEFAULT_ID in delivery_row.summary
    assert expected in nav_summary
    assert expected in nav_snapshot["subtitle"]
    assert nav_snapshot["badge_text"] == "引用无效"
    assert first_id not in delivery_step.detail


def test_output_detail_keeps_invalid_identity_until_user_selects_valid_preset(qapp):
    scene, first_id = _scene_with_invalid_default()
    pane = _OutputDetail()
    try:
        pane.set_scene(scene)

        assert scene.default_delivery_preset_id == INVALID_DEFAULT_ID
        assert pane._default_delivery.currentData() in (None, "")
        assert pane._default_delivery.currentText() == (
            f"无效引用：{INVALID_DEFAULT_ID}"
        )
        assert pane._default_delivery.property("deliveryIdentityStatus") == "invalid"
        assert pane._default_delivery.findData(first_id) > 0
        assert pane._delivery_preset_id.isEnabled() is False
        assert pane._final_docx.isEnabled() is False
        assert pane._copy_preset_btn.isEnabled() is False

        pane._default_delivery.setCurrentIndex(
            pane._default_delivery.findData(first_id)
        )
        qapp.processEvents()

        assert scene.default_delivery_preset_id == first_id
        assert pane._default_delivery.currentData() == first_id
        assert pane._default_delivery.property("deliveryIdentityStatus") == "ok"
        assert pane._default_delivery.findText(
            f"无效引用：{INVALID_DEFAULT_ID}"
        ) == -1
        assert pane._delivery_preset_id.isEnabled() is True
        assert pane._final_docx.isEnabled() is True
        assert pane._copy_preset_btn.isEnabled() is True
    finally:
        pane.close()
        qapp.processEvents()


def test_real_rules_detail_projects_invalid_default_without_mutating_scene(qapp):
    scene, _first_id = _scene_with_invalid_default()
    before = _serialized_scene(scene)
    output = _OutputDetail()
    rules = _SceneRulesDetail(
        _ScopeDetail(),
        output,
    )
    try:
        rules.set_scene(scene, TemplateConfig(), mode_id="official")
        qapp.processEvents()

        assert _serialized_scene(scene) == before
        assert scene.default_delivery_preset_id == INVALID_DEFAULT_ID
        assert rules._output_rules._delivery_row.property(
            "deliveryProjectionStatus"
        ) == "invalid"
        assert INVALID_DEFAULT_ID in rules._output_rules._delivery_label.text()
        assert all(
            checkbox.isEnabled() is False
            for checkbox in rules._output_rules._general_checks.values()
        )
        assert output._default_delivery.currentData() in (None, "")
        assert INVALID_DEFAULT_ID in output._default_delivery.currentText()
    finally:
        rules.close()
        qapp.processEvents()


def test_scene_panel_lazy_rules_load_keeps_invalid_scene_bytes_unchanged(qapp):
    scene, _first_id = _scene_with_invalid_default()
    bridge = PanelBridge()
    bridge.set_current_work_mode("official", emit_signal=False)
    bridge.set_current_scene(scene, config_id=scene.scene_id, emit_signal=False)
    bridge.set_current_template(
        create_builtin_template("official_gbt"),
        config_id="official_gbt",
        emit_signal=False,
    )
    before = _serialized_scene(scene)
    panel = ScenePanel(bridge)
    try:
        assert "scn_rules" not in panel._loaded_detail_ids

        detail = panel._ensure_detail_loaded("scn_rules")
        qapp.processEvents()

        assert isinstance(detail, _SceneRulesDetail)
        assert _serialized_scene(scene) == before
        assert scene.default_delivery_preset_id == INVALID_DEFAULT_ID
        assert detail._output_rules._delivery_row.property(
            "deliveryProjectionStatus"
        ) == "invalid"
        assert INVALID_DEFAULT_ID in detail._output_rules._delivery_label.text()
    finally:
        panel.close()
        qapp.processEvents()


def test_exam_output_rules_load_is_read_only_until_user_changes_policy(qapp):
    scene = create_exam_scene()
    scene.exam_paper.answer_policy = "student_only"
    scene.delivery_presets = [DeliveryPreset(preset_id="untouched")]
    scene.default_delivery_preset_id = "untouched"
    before = _serialized_scene(scene)
    before_delivery_ids = [preset.preset_id for preset in scene.delivery_presets]
    output = _OutputDetail()
    card = _SceneOutputRulesCard(output)
    try:
        card.set_scene(scene, mode_id="exam")
        qapp.processEvents()

        assert _serialized_scene(scene) == before
        assert scene.default_delivery_preset_id == "untouched"
        assert [preset.preset_id for preset in scene.delivery_presets] == (
            before_delivery_ids
        )
        assert card._delivery_row.property("deliveryProjectionStatus") == "ok"
        assert card._exam_student_check.isEnabled() is True
        assert card._exam_answer_check.isEnabled() is True
        assert card._exam_student_check.isChecked() is True
        assert card._exam_answer_check.isChecked() is False

        card._exam_answer_check.click()
        qapp.processEvents()

        assert _serialized_scene(scene) != before
        assert scene.exam_paper.answer_policy == "student_plus_answer"
        assert scene.default_delivery_preset_id == "student"
        assert {preset.preset_id for preset in scene.delivery_presets} >= {
            "student",
            "answer_key",
        }
    finally:
        card.close()
        output.close()
        qapp.processEvents()


@pytest.mark.parametrize(
    ("tamper", "expected_status", "expected_text"),
    (
        ("missing", "missing", "试卷配置缺失"),
        ("invalid", "invalid", "答案版本策略无效：not-a-policy"),
    ),
)
def test_exam_output_rules_disable_missing_or_invalid_read_only_projection(
    qapp,
    tamper,
    expected_status,
    expected_text,
):
    scene = create_exam_scene()
    if tamper == "missing":
        scene.exam_paper = None
    else:
        scene.exam_paper.answer_policy = "not-a-policy"
    before = _serialized_scene(scene)
    before_default = scene.default_delivery_preset_id
    before_delivery_ids = [preset.preset_id for preset in scene.delivery_presets]
    output = _OutputDetail()
    card = _SceneOutputRulesCard(output)
    try:
        card.set_scene(scene, mode_id="exam")
        qapp.processEvents()

        assert _serialized_scene(scene) == before
        assert scene.default_delivery_preset_id == before_default
        assert [preset.preset_id for preset in scene.delivery_presets] == (
            before_delivery_ids
        )
        assert card._delivery_row.property("deliveryProjectionStatus") == (
            expected_status
        )
        assert expected_text in card._delivery_label.text()
        assert card._exam_student_check.isEnabled() is False
        assert card._exam_answer_check.isEnabled() is False
        assert card._exam_student_check.isChecked() is False
        assert card._exam_answer_check.isChecked() is False
    finally:
        card.close()
        output.close()
        qapp.processEvents()
