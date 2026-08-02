from src.config.resolver import resolve_config
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig
from src.qt_api import QApplication, Qt
from src.ui.bridge import PanelBridge
from src.ui.panels.scene_formula_detail import (
    _SceneChemTypographyDetail,
    _SceneFormulaRulesCard,
)
from src.ui.panels.scene_navigation_projection import (
    chem_typography_navigation_snapshot,
    formula_navigation_snapshot,
)
from src.ui.panels.scene_panel import ScenePanel


def _app():
    return QApplication.instance() or QApplication([])


def test_thesis_formula_policy_card_writes_only_the_nested_thesis_rules():
    _app()
    scene = SceneWorkspace(scene_id="thesis", mode_id="thesis")
    card = _SceneFormulaRulesCard()
    try:
        card.set_scene(scene, mode_id="thesis")
        assert card.isHidden() is False

        card._office_fallback.click()
        card._office_timeout.setValue(55)
        card._convert_enabled.setChecked(False)
        card._formula_workflow_checks["formula_to_table"].setChecked(False)
        card._formula_workflow_checks["equation_numbering"].setChecked(False)
        card._formula_workflow_checks["formula_style"].setChecked(False)
        card._output_mode.setCurrentIndex(card._output_mode.findData("keep_source"))
        card._low_confidence.setCurrentIndex(
            card._low_confidence.findData("manual_review")
        )
        rules = scene.thesis_formula_rules
        assert rules is not None
        assert rules.formula_convert.enabled is False
        assert rules.formula_to_table.enabled is False
        assert rules.equation_numbering.enabled is False
        assert rules.formula_style.enabled is False
        assert "formula_convert" not in scene.module_switches
        assert "equation_table_format" not in scene.module_switches
        assert rules.formula_convert.output_mode == "keep_source"
        assert rules.formula_convert.low_confidence_policy == "manual_review"
        assert rules.formula_convert.office_fallback_enabled is True
        assert rules.formula_convert.office_fallback_timeout_sec == 55
    finally:
        card.close()


def test_thesis_formula_rules_write_layout_directly():
    _app()
    scene = SceneWorkspace(scene_id="thesis", mode_id="thesis")
    template = TemplateConfig()
    card = _SceneFormulaRulesCard()
    try:
        card.set_scene(scene, template, mode_id="thesis")

        card._formula_font.set_font_name("Arial")
        card._formula_size.set_pt(10.5)
        card._number_font.set_font_name("Courier New")
        card._number_size.set_pt(9.0)
        card._formula_alignment.setCurrentIndex(
            card._formula_alignment.findData("left")
        )
        card._table_alignment.setCurrentIndex(card._table_alignment.findData("right"))
        card._formula_cell_alignment.setCurrentIndex(
            card._formula_cell_alignment.findData("center")
        )
        card._number_alignment.setCurrentIndex(
            card._number_alignment.findData("center")
        )
        card._numbering.setCurrentIndex(card._numbering.findData("global"))
        card._formula_line_spacing.setValue(1.25)
        card._formula_space_before.set_value(0.5, "cm")
        card._formula_space_after.set_value(3.0, "pt")
        card._auto_shrink_number.setChecked(False)
        card._formula_style_checks["unify_spacing"].setChecked(False)

        rules = scene.thesis_formula_rules
        assert rules is not None
        assert rules.formula_table.formula_font_name == "Arial"
        assert rules.formula_table.formula_font_size_pt == 10.5
        assert rules.formula_table.number_font_name == "Courier New"
        assert rules.formula_table.number_font_size_pt == 9.0
        assert rules.formula_table.block_alignment == "left"
        assert rules.formula_table.table_alignment == "right"
        assert rules.formula_table.formula_cell_alignment == "center"
        assert rules.formula_table.number_alignment == "center"
        assert rules.formula_table.formula_line_spacing == 1.25
        assert rules.formula_table.formula_space_before_pt == 0.5
        assert rules.formula_table.formula_space_before_unit == "cm"
        assert rules.formula_table.formula_space_after_pt == 3.0
        assert rules.formula_table.formula_space_after_unit == "pt"
        assert rules.formula_table.auto_shrink_number_column is False
        assert rules.equation_numbering.numbering_format == "global"
        assert rules.formula_style.unify_spacing is False
        assert not any(
            str(key).startswith(("formula_", "equation_numbering", "chem_typography"))
            for key in scene.template_overrides
        )

        resolved = resolve_config(template, scene)
        assert resolved.formula_table.formula_font_name == "Arial"
        assert resolved.formula_table.formula_font_size_pt == 10.5
        assert resolved.formula_table.table_alignment == "right"
        assert resolved.formula_table.number_alignment == "center"
        assert resolved.formula_table.number_font_name == "Courier New"
        assert resolved.formula_table.number_font_size_pt == 9.0
        assert resolved.formula_table.formula_line_spacing == 1.25
        assert resolved.formula_table.formula_space_before_pt == 0.5
        assert resolved.formula_table.formula_space_before_unit == "cm"
        assert resolved.formula_table.auto_shrink_number_column is False
    finally:
        card.close()


def test_chem_typography_is_an_independent_detail_with_restore_and_save_actions():
    _app()
    scene = SceneWorkspace(scene_id="thesis", mode_id="thesis")
    detail = _SceneChemTypographyDetail()
    saved = []
    detail.save_requested.connect(lambda: saved.append(True))
    try:
        detail.set_scene(scene, mode_id="thesis")
        assert detail.isHidden() is False
        assert detail._chem_all_scope.isChecked() is False

        detail._chem_enabled.click()
        detail._chem_all_scope.setChecked(True)
        detail._chem_scope_checks["references"].setChecked(False)
        detail._chem_font.set_font_name("Arial")

        rules = scene.ensure_thesis_formula_rules()
        assert rules.chem_typography.enabled is True
        assert rules.chem_typography.scopes["body"] is True
        assert rules.chem_typography.scopes["references"] is False
        assert rules.chem_typography.western_font == "Arial"
        assert "chem_typography" not in scene.module_switches
        assert detail._persistence.restore_button.isEnabled() is True

        detail._persistence.restore_button.click()
        assert rules.chem_typography.enabled is False
        assert not any(rules.chem_typography.scopes.values())
        assert rules.chem_typography.western_font == "Times New Roman"

        detail.set_save_enabled(True)
        detail._persistence.save_button.click()
        assert saved == [True]
    finally:
        detail.close()


def test_formula_master_switch_gates_execution_without_erasing_child_workflow():
    _app()
    scene = SceneWorkspace(scene_id="thesis", mode_id="thesis")
    detail = _SceneFormulaRulesCard()
    try:
        detail.set_scene(scene, mode_id="thesis")
        rules = scene.ensure_thesis_formula_rules()
        assert rules.formula_enabled is True
        assert rules.formula_convert.enabled is True
        assert rules.equation_numbering.enabled is True

        detail._feature_enabled.click()
        assert rules.formula_enabled is False
        assert rules.formula_convert.enabled is True
        assert rules.equation_numbering.enabled is True
        assert scene.is_module_enabled("formula_convert") is False
        assert scene.is_module_enabled("equation_table_format") is False
        assert detail._persistence.restore_button.isEnabled() is True

        detail._feature_enabled.click()
        assert scene.is_module_enabled("formula_convert") is True
        assert scene.is_module_enabled("equation_table_format") is True
    finally:
        detail.close()


def test_thesis_formula_navigation_cards_are_independent_and_lazy_loaded():
    app = _app()
    bridge = PanelBridge()
    bridge.set_current_work_mode("thesis", emit_signal=False)
    scene = SceneWorkspace(
        scene_id="thesis",
        mode_id="thesis",
        template_id="thesis_gbt",
    )
    bridge.set_current_scene(scene, config_id="thesis", emit_signal=False)
    bridge.set_current_template(
        TemplateConfig(),
        config_id="thesis_gbt",
        emit_signal=False,
    )
    panel = ScenePanel(bridge)
    try:
        assert panel._nav_cards["scn_formula"].isHidden() is False
        assert panel._nav_cards["scn_chem_typography"].isHidden() is False
        assert panel._nav_cards["scn_formula"]._badge.text() == "已启用"
        assert panel._nav_cards["scn_chem_typography"]._badge.text() == "已关闭"
        assert "scn_formula" not in panel._loaded_detail_ids
        assert "scn_chem_typography" not in panel._loaded_detail_ids

        panel._nav_rail.select_card("scn_formula")
        app.processEvents()
        assert "scn_formula" in panel._loaded_detail_ids
        assert panel._details.current_detail is panel._formula_detail
        assert (
            panel._formula_detail._summary_card.header.title_label.text() == "公式处理"
        )

        panel._formula_detail._feature_enabled.click()
        app.processEvents()
        assert bridge.is_scene_dirty() is True
        assert panel._nav_cards["scn_formula"]._badge.text() == "已关闭"
        assert panel._formula_detail._persistence.save_button.isEnabled() is True
    finally:
        panel.close()
        app.processEvents()


def test_formula_navigation_projection_uses_master_and_chem_states():
    scene = SceneWorkspace(scene_id="thesis", mode_id="thesis")
    rules = scene.ensure_thesis_formula_rules()

    assert formula_navigation_snapshot(scene)["badge_text"] == "已启用"
    assert chem_typography_navigation_snapshot(scene)["badge_text"] == "已关闭"

    rules.formula_enabled = False
    rules.chem_typography.enabled = True
    rules.chem_typography.scopes["body"] = True

    assert formula_navigation_snapshot(scene)["badge_text"] == "已关闭"
    chem_snapshot = chem_typography_navigation_snapshot(scene)
    assert chem_snapshot["badge_text"] == "已启用"
    assert "1 个范围" in chem_snapshot["subtitle"]


def test_formula_navigation_projection_distinguishes_disabled_and_incomplete():
    scene = SceneWorkspace(scene_id="thesis", mode_id="thesis")
    rules = scene.ensure_thesis_formula_rules()
    rules.formula_convert.enabled = False
    rules.formula_to_table.enabled = False
    rules.equation_numbering.enabled = False
    rules.formula_style.enabled = False

    formula_snapshot = formula_navigation_snapshot(scene)
    assert formula_snapshot["badge_text"] == "待配置"
    assert formula_snapshot["badge_variant"] == "warning"
    assert formula_snapshot["subtitle"].startswith("不转换")

    rules.chem_typography.enabled = True
    chem_snapshot = chem_typography_navigation_snapshot(scene)
    assert chem_snapshot["badge_text"] == "待配置"
    assert chem_snapshot["badge_variant"] == "warning"
    assert scene.is_module_enabled("chem_typography") is False

    rules.chem_typography.scopes["body"] = True
    assert chem_typography_navigation_snapshot(scene)["badge_text"] == "已启用"
    assert scene.is_module_enabled("chem_typography") is True


def test_formula_policy_card_is_not_shown_for_non_thesis_mode():
    _app()
    card = _SceneFormulaRulesCard()
    try:
        card.set_scene(SceneWorkspace(scene_id="custom", mode_id="custom"))
        assert card.isHidden() is True
        assert card.focus_navigation_field("formula_style") is False
    finally:
        card.close()

    chem_detail = _SceneChemTypographyDetail()
    try:
        chem_detail.set_scene(SceneWorkspace(scene_id="custom", mode_id="custom"))
        assert chem_detail.isHidden() is True
        assert chem_detail.focus_navigation_field("chem_typography") is False
    finally:
        chem_detail.close()


def test_formula_detail_uses_shared_two_column_alignment_rules():
    app = _app()
    detail = _SceneFormulaRulesCard()
    try:
        detail.set_scene(
            SceneWorkspace(scene_id="thesis", mode_id="thesis"),
            mode_id="thesis",
        )
        detail.resize(1280, 1200)
        detail.show()
        app.processEvents()
        app.processEvents()

        def x(widget):
            return widget.mapTo(detail, widget.rect().topLeft()).x()

        assert (
            len(
                {
                    x(detail._formula_font),
                    x(detail._formula_alignment),
                    x(detail._formula_space_before),
                    x(detail._formula_style_checks["unify_font"]),
                    x(detail._formula_style_checks["unify_spacing"]),
                }
            )
            == 1
        )
        assert (
            len(
                {
                    x(detail._formula_size),
                    x(detail._formula_line_spacing),
                    x(detail._formula_space_after),
                    x(detail._formula_style_checks["unify_size"]),
                }
            )
            == 1
        )
        assert (
            len(
                {
                    x(detail._numbering),
                    x(detail._number_font),
                    x(detail._table_alignment),
                }
            )
            == 1
        )
        assert (
            len(
                {
                    x(detail._number_alignment),
                    x(detail._number_size),
                    x(detail._formula_cell_alignment),
                }
            )
            == 1
        )
        assert x(detail._formula_size) > x(detail._formula_font)
        assert x(detail._formula_workflow_checks["formula_to_table"]) == x(
            detail._formula_workflow_checks["formula_style"]
        )
        assert x(detail._formula_workflow_checks["equation_numbering"]) == x(
            detail._formula_workflow_checks["block_only"]
        )
    finally:
        detail.close()


def test_chem_scope_options_use_a_stable_two_column_grid():
    app = _app()
    detail = _SceneChemTypographyDetail()
    try:
        scene = SceneWorkspace(scene_id="thesis", mode_id="thesis")
        scene.ensure_thesis_formula_rules().chem_typography.enabled = True
        detail.set_scene(scene, mode_id="thesis")
        detail.resize(1280, 720)
        detail.show()
        app.processEvents()
        app.processEvents()

        def x(widget):
            return widget.mapTo(detail, widget.rect().topLeft()).x()

        left_column = {
            x(detail._chem_all_scope),
            x(detail._chem_scope_checks["body"]),
            x(detail._chem_scope_checks["abstract_cn"]),
            x(detail._chem_scope_checks["tables"]),
            x(detail._chem_scope_checks["references"]),
        }
        right_column = {
            x(detail._chem_scope_checks["headings"]),
            x(detail._chem_scope_checks["abstract_en"]),
            x(detail._chem_scope_checks["captions"]),
        }
        assert len(left_column) == 1
        assert len(right_column) == 1
        assert next(iter(right_column)) > next(iter(left_column))
    finally:
        detail.close()


def test_chem_all_scope_is_a_tri_state_aggregate_and_can_clear_every_scope():
    app = _app()
    scene = SceneWorkspace(scene_id="thesis", mode_id="thesis")
    rules = scene.ensure_thesis_formula_rules()
    rules.chem_typography.enabled = True
    detail = _SceneChemTypographyDetail()
    try:
        detail.set_scene(scene, mode_id="thesis")
        detail._chem_scope_checks["body"].setChecked(True)
        app.processEvents()
        assert detail._chem_all_scope.checkState() == Qt.PartiallyChecked

        detail._chem_all_scope.setCheckState(Qt.Checked)
        app.processEvents()
        assert all(rules.chem_typography.scopes.values())

        detail._chem_all_scope.setCheckState(Qt.Unchecked)
        app.processEvents()
        assert not any(rules.chem_typography.scopes.values())
        assert detail._chem_all_scope.checkState() == Qt.Unchecked
    finally:
        detail.close()


def test_formula_restore_recomputes_global_scene_dirty_state():
    app = _app()
    bridge = PanelBridge()
    bridge.set_current_work_mode("thesis", emit_signal=False)
    scene = SceneWorkspace(
        scene_id="thesis",
        mode_id="thesis",
        template_id="thesis_gbt",
    )
    bridge.set_current_scene(scene, config_id="thesis", emit_signal=False)
    bridge.set_current_template(
        TemplateConfig(),
        config_id="thesis_gbt",
        emit_signal=False,
    )
    panel = ScenePanel(bridge)
    try:
        panel._nav_rail.select_card("scn_formula")
        app.processEvents()
        detail = panel._formula_detail
        detail._feature_enabled.click()
        app.processEvents()
        assert bridge.is_scene_dirty() is True
        assert detail._persistence.save_button.isEnabled() is True

        detail._persistence.restore_button.click()
        app.processEvents()
        assert bridge.is_scene_dirty() is False
        assert detail._persistence.save_button.isEnabled() is False
        assert detail._persistence.restore_button.isEnabled() is False
    finally:
        panel.close()
        app.processEvents()


def test_formula_restore_keeps_dirty_when_another_formula_domain_is_modified():
    app = _app()
    bridge = PanelBridge()
    bridge.set_current_work_mode("thesis", emit_signal=False)
    scene = SceneWorkspace(
        scene_id="thesis",
        mode_id="thesis",
        template_id="thesis_gbt",
    )
    bridge.set_current_scene(scene, config_id="thesis", emit_signal=False)
    bridge.set_current_template(
        TemplateConfig(),
        config_id="thesis_gbt",
        emit_signal=False,
    )
    panel = ScenePanel(bridge)
    try:
        panel._nav_rail.select_card("scn_formula")
        app.processEvents()
        formula = panel._formula_detail
        formula._feature_enabled.click()

        panel._nav_rail.select_card("scn_chem_typography")
        app.processEvents()
        chem = panel._chem_typography_detail
        chem._chem_enabled.click()
        chem._chem_scope_checks["body"].setChecked(True)

        panel._nav_rail.select_card("scn_formula")
        app.processEvents()
        formula._persistence.restore_button.click()
        app.processEvents()

        assert bridge.is_scene_dirty() is True
        assert formula._persistence.restore_button.isEnabled() is False
        assert formula._persistence.save_button.isEnabled() is True
        assert scene.ensure_thesis_formula_rules().chem_typography.enabled is True
    finally:
        panel.close()
        app.processEvents()


def test_formula_controls_follow_their_actual_runtime_substeps():
    app = _app()
    scene = SceneWorkspace(scene_id="thesis", mode_id="thesis")
    detail = _SceneFormulaRulesCard()
    try:
        detail.set_scene(scene, mode_id="thesis")
        for key in ("formula_to_table", "equation_numbering", "formula_style"):
            detail._formula_workflow_checks[key].setChecked(False)
        app.processEvents()

        assert detail._formula_style_card.isEnabled() is False
        assert detail._numbering_card.isEnabled() is False
        assert detail._formula_workflow_checks["block_only"].isEnabled() is False

        detail._formula_workflow_checks["formula_to_table"].setChecked(True)
        app.processEvents()
        assert detail._numbering_card.isEnabled() is True
        assert detail._numbering_rows["table_alignment"].isEnabled() is True
        assert detail._numbering_rows["numbering"].isEnabled() is False
        assert detail._formula_style_card.isEnabled() is False
        assert detail._formula_workflow_checks["block_only"].isEnabled() is True

        detail._formula_workflow_checks["formula_to_table"].setChecked(False)
        detail._formula_workflow_checks["formula_style"].setChecked(True)
        app.processEvents()
        assert detail._formula_style_card.isEnabled() is True
        assert detail._numbering_card.isEnabled() is False

        detail._formula_workflow_checks["formula_style"].setChecked(False)
        detail._formula_workflow_checks["equation_numbering"].setChecked(True)
        app.processEvents()
        assert detail._formula_style_card.isEnabled() is True
        assert detail._numbering_card.isEnabled() is True
        assert detail._numbering_rows["numbering"].isEnabled() is True
    finally:
        detail.close()
