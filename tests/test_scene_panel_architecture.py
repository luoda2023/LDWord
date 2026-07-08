import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QPoint, Qt
from src.ui.icons.catalog import get_icon_names
from src.shared.ui.form_row import FormRow
from src.shared.ui.style_owner_state import scene_section_style_owner_state
from src.shared.ui.theme import get_theme
from src.shared.ui.themed_radio_button import ThemedRadioButton
from src.config import library as config_library
from src.config.scene import SceneWorkspace
from src.config.builtin_templates import create_builtin_template
from src.config.scene_family_application import apply_planned_scene_family_defaults
from src.config.template import StyleConfig
from src.config.style_variant_semantics import (
    STYLE_VARIANTS,
    build_section_style_override_projection,
    enable_section_style_override,
)
from src.ui.bridge import PanelBridge
from src.ui.panels.scene_panel import ScenePanel, _set_combo_by_data
from src.ui.panels.scene_overview_projection import FIRST_SCREEN_BANNED_TERMS
from src.ui.panels.scene_scope_sections import SceneScopeZoneSection
from src.ui.panels.scene_style_override_sections import SceneStyleOverrideSection
from src.ui.panels.scene_style_rules_block import SceneStyleRulesBlock
from src.ui.panels.scene_style_override_service import (
    restore_all_scene_section_styles_to_template,
    restore_scene_section_style_to_template,
    scene_section_effective_style,
    scene_section_style_override_projection,
    scene_section_style_preview_projection,
    scene_style_variants_for_scene,
    set_scene_section_style_override,
    sync_disabled_section_style_overrides,
)
from src.ui.panels.scene_scope_service import apply_scene_scope_zone_states
from src.ui.panels.template_format import build_template_preview_context
from src.ui.panels.scene_summary_projection import (
    build_academic_rule_source_evidence_summary_items,
    build_application_report_evidence_summary_items,
    build_compliance_summary_items,
    build_contract_field_evidence_summary_items,
    build_control_contract_summary_items,
    build_coverage_summary_items,
    build_delivery_summary_items,
    build_fixed_layout_batch_evidence_summary_items,
    build_input_profile_summary_items,
    build_journal_submission_evidence_summary_items,
    build_parameter_ownership_summary_items,
    build_product_readiness_summary_items,
    build_scene_request_cell_summary_items,
    build_scene_overview_summary_items,
    build_scene_scope_summary_items,
    build_scene_sample_fixture_detail_text,
    build_scene_sample_fixture_summary_items,
    build_scene_style_override_summary_items,
    recommended_object_preflight_targets_for_scene,
    scene_request_cell_filter_options,
    scene_request_cell_fixture_specs_for_scene,
)
from src.ui.panels.workbench.scene_presets import (
    create_bidding_scene,
    create_exam_scene,
    create_official_scene,
    create_technical_scene,
    create_thesis_scene,
)


def _app():
    return QApplication.instance() or QApplication([])


def test_scene_panel_removes_page_elements_detail_from_scene_surface():
    source = (ROOT / "src/ui/panels/scene_panel.py").read_text(encoding="utf-8")

    assert "self._page_number = ToggleSwitch" not in source
    assert "hf.page_number_enabled =" not in source
    assert "_PageElementsDetail" not in source
    assert "_page_elem" not in source
    assert "scn_page_elem" not in source


def test_scene_panel_uses_shared_card_header_and_flow_scope_layout():
    source = (ROOT / "src/ui/panels/scene_panel.py").read_text(encoding="utf-8")
    projection_source = (
        ROOT / "src/ui/panels/scene_overview_projection.py"
    ).read_text(encoding="utf-8")
    scope_section_source = (
        ROOT / "src/ui/panels/scene_scope_sections.py"
    ).read_text(encoding="utf-8")
    style_override_section_source = (
        ROOT / "src/ui/panels/scene_style_override_sections.py"
    ).read_text(encoding="utf-8")
    style_rules_block_source = (
        ROOT / "src/ui/panels/scene_style_rules_block.py"
    ).read_text(encoding="utf-8")
    style_object_builder_source = (
        ROOT / "src/ui/panels/style_object_projection_builders.py"
    ).read_text(encoding="utf-8")
    style_editing_source = (
        ROOT / "src/shared/ui/style_editing_section.py"
    ).read_text(encoding="utf-8")
    style_management_source = (
        ROOT / "src/shared/ui/style_management_block.py"
    ).read_text(encoding="utf-8")
    style_rule_deck_source = (
        ROOT / "src/shared/ui/style_rule_control_deck.py"
    ).read_text(encoding="utf-8")
    scene_card_definitions_source = (
        ROOT / "src/ui/panels/scene_card_definitions.py"
    ).read_text(encoding="utf-8")
    scene_navigation_projection_source = (
        ROOT / "src/ui/panels/scene_navigation_projection.py"
    ).read_text(encoding="utf-8")
    style_policy_deck_source = (
        ROOT / "src/shared/ui/style_policy_control_deck.py"
    ).read_text(encoding="utf-8")
    style_difference_slot_source = (
        ROOT / "src/shared/ui/style_difference_summary_slot.py"
    ).read_text(encoding="utf-8")
    scope_checklist_source = (
        ROOT / "src/shared/ui/scope_zone_checklist.py"
    ).read_text(encoding="utf-8")

    assert "_make_card_header" not in source
    assert "_apply_cached_header_theme" not in source
    assert "QGridLayout" not in source
    assert "FlowLayout" in source
    assert "SceneScopeZoneSection" in source
    assert "SceneStyleRulesBlock" in source
    assert "SceneStyleOverrideSection" not in source
    assert "ScopeZoneChecklist" not in source
    assert "ScopeZoneOption" not in source
    assert "StyleOverrideToggleList" not in source
    assert "StyleOverrideToggleOption" not in source
    assert "_zones_flow = FlowLayout" not in source
    assert "ScopeZoneChecklist" in scope_section_source
    assert "ScopeZoneOption" in scope_section_source
    assert "zone_changed = Signal(str, bool)" in scope_section_source
    assert "ScopeZoneChecklist" in scope_checklist_source
    assert "checked_changed = Signal(str, bool)" in scope_checklist_source
    assert "QCheckBox(option.label" in scope_checklist_source
    assert 'self._make_scene_overview_header("mountain-snow", "当前场景")' in source
    assert 'self._make_scene_overview_header("sliders-horizontal", "场景策略")' in source
    registered_icons = set(get_icon_names())
    assert {"mountain-snow", "sliders-horizontal"} <= registered_icons
    assert '"scn_evidence"' not in source
    assert '"核对依据"' not in source
    assert "from src.ui.panels.scene_card_definitions import" in source
    assert '"scn_rules": ("场景规则", "sliders-horizontal")' in scene_card_definitions_source
    assert "from src.ui.panels.scene_navigation_projection import" in source
    assert "SCENE_RULES_ALIAS_CARDS = frozenset" in scene_navigation_projection_source
    assert "NAV_OUTPUT_FIELDS = (" in scene_navigation_projection_source
    assert "def _normalise_scene_detail_card_id" not in source
    assert "self._style_rules = _StyleRulesDetail()" in source
    assert "self._rules = _SceneRulesDetail(" in source
    assert "self._style_rules_block = SceneStyleRulesBlock" in source
    assert '"scn_rules": self._create_rules_detail' in source
    assert "self._detail_map[card_id] = detail" in source
    assert 'SCENE_SCOPE_ZONE_SECTION_TITLE = "处理范围"' in scope_section_source
    assert 'SCENE_SCOPE_ZONE_SECTION_DESCRIPTION = ""' in scope_section_source
    assert '.set_header(title, icon_name="crosshair")' in scope_section_source
    assert "crosshair" in registered_icons
    assert 'SCENE_STYLE_OVERRIDE_SECTION_TITLE = "分区样式"' in style_override_section_source
    assert "SceneStyleOverrideSection(" in style_rules_block_source
    assert "StyleManagementBlock(" in style_override_section_source
    assert "build_scene_section_style_projection" in source
    assert "StyleObjectProjection" not in source
    assert "StyleObjectProjection" in style_object_builder_source
    assert "apply_style_object_projection(" in source
    assert "def apply_style_object_projection" in style_rules_block_source
    assert "def apply_style_object_projection" in style_override_section_source
    assert "StyleRuleControlDeck(" in style_override_section_source
    assert "StylePolicyControlDeck" in style_rule_deck_source
    assert "def apply_projection" in style_policy_deck_source
    assert "policy=build_scene_section_style_policy_projection" in (
        style_object_builder_source
    )
    assert "summary_items=build_scene_style_override_summary_items" in (
        style_object_builder_source
    )
    assert "style_object.policy" in style_management_source
    assert "self._style_rules_block.set_summary_items" not in source
    assert "self._style_rules_block.set_restore_all_enabled" not in source
    assert "self._style_rules_block.set_undo_restore_all_enabled" not in source
    assert "def _section_style_override_labels" not in source
    assert "rule_control=self._rule_control_deck" in style_override_section_source
    assert "difference_slot=self._rule_control_deck.difference_slot" in (
        style_override_section_source
    )
    assert "management_widgets=" not in style_override_section_source
    assert "StyleComparisonStrip(" not in style_override_section_source
    assert "StyleDifferenceSummarySlot(" in style_policy_deck_source
    assert "StyleComparisonStrip(" not in style_policy_deck_source
    assert "StyleComparisonStrip(" in style_difference_slot_source
    assert "StylePolicyToggleList(" in style_policy_deck_source
    assert "StyleOverrideToggleList(" not in style_policy_deck_source
    assert "scene_section_style_comparison_projection" not in source
    assert "scene_section_style_comparison_projection" in style_object_builder_source
    assert "StyleSourceSlot(" not in source
    assert "StyleSourceCompactRow(" not in source
    assert "DetailSummaryCard(" in style_management_source
    assert "TemplateSummaryCard(" not in style_management_source
    assert "StyleEditingSection(" in style_management_source
    assert "_set_editor_surface_visible(" in style_management_source
    assert "style_management_editor_visible" in style_management_source
    assert "style_management_editor_collapsed_by_readonly" in style_management_source
    assert "style_surface.setVisible(editable)" not in style_management_source
    assert "分区样式编辑" not in source
    assert '"style_source"' in source
    assert '"template_style"' not in source
    assert "编辑样式" in style_editing_source or "编辑样式" in style_management_source
    assert '"scn_features"' not in source
    assert '.set_header("执行能力", icon_name="toggle-right")' not in source
    assert '"scn_table_chart"' not in source
    assert '"scn_formula"' not in source
    assert '"scn_citation"' not in source
    assert '"format_template"' in source
    assert '"场景策略"' in source
    assert '"格式与模板"' not in source
    assert 'add_section_header("风险与边界")' not in source
    assert 'add_section_header("资料包")' in source
    assert 'add_section_header("输出")' not in source
    assert "RISK_BOUNDARY_CARDS" not in source
    assert 'add_section_header("功能参数")' not in source
    assert '"功能开关"' not in source
    assert 'INPUT_MATERIAL_CARDS = ("scn_content",)' in scene_card_definitions_source
    assert '"content_fill":  "scn_content"' not in source
    assert "TemplateStylePreview" not in source
    assert "_template_preview_context_for_scene" in source
    assert "template_preview_action" in projection_source
    assert "统一页面、正文、标题、表格和页眉页脚" not in projection_source


def test_scene_scope_zone_section_wraps_summary_and_checklist():
    app = _app()
    section = SceneScopeZoneSection(
        summary_items=build_scene_scope_summary_items(None),
        zone_labels={"body": "正文", "references": "参考文献"},
        object_name_prefix="test_scene_scope_zone_section",
    )
    changed: list[tuple[str, bool]] = []
    mode_changed: list[str] = []
    section.zone_changed.connect(lambda key, checked: changed.append((key, checked)))
    section.boundary_mode_changed.connect(mode_changed.append)

    try:
        app.processEvents()

        assert section.summary.value_for("main_controls") == "选择处理范围"
        assert section.summary.isVisibleTo(section) is False
        assert section.boundary_mode() == "follow_template"
        assert section.boundary_mode_control.objectName() == (
            "test_scene_scope_zone_section_boundary_mode"
        )
        assert section.boundary_mode_control.isVisibleTo(section) is True
        assert set(section.checks) == {"body", "references"}
        assert section.checklist.objectName() == "test_scene_scope_zone_section"
        assert section.checklist.isVisibleTo(section) is False
        assert section.checks["references"].text() == "参考文献"

        section.set_boundary_mode("body_only")
        app.processEvents()

        assert section.boundary_mode() == "body_only"
        assert mode_changed == ["body_only"]

        section.set_zone_checked("references", True)
        app.processEvents()

        assert section.checked_states()["references"] is True
        assert changed == [("references", True)]
    finally:
        section.close()
        app.processEvents()


def test_scene_style_override_section_wraps_owner_preview_and_surface():
    app = _app()
    section = SceneStyleOverrideSection(
        summary_items=build_scene_style_override_summary_items(None, None),
        style_variants=STYLE_VARIANTS[:2],
        object_name_prefix="test_scene_style_override",
    )
    toggled: list[tuple[str, bool]] = []
    changed: list[str] = []
    restored: list[bool] = []
    restored_all: list[bool] = []
    undone_restore_all: list[bool] = []
    section.policy_toggled.connect(
        lambda key, checked: toggled.append((key, checked))
    )
    section.current_variant_changed.connect(changed.append)
    section.restore_requested.connect(lambda: restored.append(True))
    section.restore_all_requested.connect(lambda: restored_all.append(True))
    section.undo_restore_all_requested.connect(lambda: undone_restore_all.append(True))

    try:
        app.processEvents()

        assert section.summary.value_for("override_status") == "无格式例外"
        assert section.management_block.property("style_management_mode") == (
            "scene_section_rules"
        )
        assert section.management_block.property("style_management_content_plan") == (
            "source|scope|rules|difference|editor|preview"
        )
        assert section.management_block.property("style_management_has_rules") is True
        assert (
            section.management_block.property("style_management_has_difference")
            is True
        )
        assert (
            section.management_block.property("style_management_has_difference_slot")
            is True
        )
        assert section.management_block.property("style_management_has_preview") is True
        assert section.management_block.preview_slot is None
        assert section.management_block.effective_preview_slot is (
            section.editing_section.preview_surface
        )
        assert section.management_block.property(
            "style_management_effective_preview_protocol"
        ) == "preview_projection"
        assert section.management_block.property(
            "style_management_effective_preview_ready"
        ) is True
        assert section.editing_section.preview_surface.property(
            "style_preview_surface_renderer_protocol"
        ) == "envelope_projection"
        assert section.editing_section.preview_surface.property(
            "style_preview_surface_renderer_ready"
        ) is True
        assert (
            section.management_block.property("style_management_has_legacy_widgets")
            is False
        )
        assert section.rule_control_deck.objectName() == (
            "test_scene_style_override_rule_control_deck"
        )
        assert section.management_block.rule_control is section.rule_control_deck
        assert section.management_block.property(
            "style_management_rule_control_protocol"
        ) == "policy_projection"
        assert section.management_block.property(
            "style_management_rule_control_ready"
        ) is True
        assert section.management_block.difference_slot is section.difference_slot
        assert section.toggle_list is section.rule_control_deck.toggle_list
        assert section.difference_slot is section.rule_control_deck.difference_slot
        assert section.difference_slot.parentWidget() is section.rule_control_deck
        assert section.difference_slot.property("style_difference_content_plan") == (
            "difference"
        )
        assert section.comparison_strip is section.rule_control_deck.comparison_strip
        assert set(section.toggles) == {"references_body", "acknowledgment_body"}
        assert section.selector.objectName() == "test_scene_style_override_owner_selector"
        assert section.restore_button.objectName() == "scn_section_style_restore_template"
        assert section.restore_all_button.objectName() == (
            "test_scene_style_override_restore_all_template"
        )
        assert section.undo_restore_all_button.objectName() == (
            "test_scene_style_override_undo_restore_all_template"
        )
        assert section.restore_all_button.isEnabled() is False
        assert section.undo_restore_all_button.isEnabled() is False
        assert section.style_surface.editor is section.editor
        assert section.comparison_strip.objectName() == (
            "test_scene_style_override_comparison"
        )

        section.apply_preview_projection(None)
        assert section.preview.text() == "选择分区后预览样式"
        assert section.preview.isEnabled() is False
        section.apply_comparison_projection(None)
        assert section.comparison_strip.property("style_compare_current_status") == (
            "选择分区"
        )

        section.set_policy_row_visible("acknowledgment_body", False)
        assert section.rows["acknowledgment_body"].isHidden() is True
        section.set_override_row_visible("acknowledgment_body", True)
        assert section.rows["acknowledgment_body"].isHidden() is False
        assert section.has_policy_key("references_body") is True
        assert section.policy_toggle_for_key("references_body") is (
            section.toggles["references_body"]
        )

        index = section.selector.findData("acknowledgment_body")
        assert index >= 0
        section.selector.setCurrentIndex(index)
        app.processEvents()
        assert changed[-1] == "acknowledgment_body"

        section.toggles["references_body"].click()
        app.processEvents()
        assert toggled[-1] == ("references_body", True)

        section.restore_button.click()
        app.processEvents()
        assert restored == [True]

        section.set_restore_all_enabled(True)
        section.restore_all_button.click()
        app.processEvents()
        assert restored_all == [True]

        section.set_undo_restore_all_enabled(True, ("参考文献",))
        section.undo_restore_all_button.click()
        app.processEvents()
        assert undone_restore_all == [True]
    finally:
        section.close()
        app.processEvents()


def test_scene_style_rules_block_wraps_override_section_as_stable_object():
    app = _app()
    block = SceneStyleRulesBlock(
        summary_items=build_scene_style_override_summary_items(None, None),
        style_variants=STYLE_VARIANTS[:2],
        object_name_prefix="test_scene_style_rules",
    )
    toggled: list[tuple[str, bool]] = []
    changed: list[str] = []
    restored: list[bool] = []
    block.policy_toggled.connect(
        lambda key, checked: toggled.append((key, checked))
    )
    block.current_variant_changed.connect(changed.append)
    block.restore_requested.connect(lambda: restored.append(True))

    try:
        app.processEvents()

        assert isinstance(block.section, SceneStyleOverrideSection)
        assert block.management_block.property("style_management_mode") == (
            "scene_section_rules"
        )
        assert block.summary.value_for("override_status") == "无格式例外"
        assert block.rule_control_deck is block.section.rule_control_deck
        assert block.toggle_list is block.section.toggle_list
        assert set(block.toggles) == {"references_body", "acknowledgment_body"}
        assert block.rows is block.section.rows
        assert block.current_variant_key() == "references_body"
        assert block.current_policy_key() == "references_body"
        assert block.rows["references_body"].property(
            "style_policy_row_current"
        ) is True
        assert block.rows["acknowledgment_body"].property(
            "style_policy_row_current"
        ) is False
        assert block.owner_toolbar is block.section.owner_toolbar
        assert block.owner_status is block.section.owner_status
        assert block.selector is block.section.selector
        assert block.restore_button is block.section.restore_button
        assert block.restore_all_button is block.section.restore_all_button
        assert block.undo_restore_all_button is block.section.undo_restore_all_button
        assert block.comparison_strip is block.section.comparison_strip
        assert block.preview is block.section.preview
        assert block.style_surface is block.section.style_surface
        assert block.editor is block.section.editor
        assert block.unit_labels == block.section.unit_labels

        block.apply_preview_projection(None)
        assert block.preview.text() == "选择分区后预览样式"
        block.apply_comparison_projection(None)
        assert block.comparison_strip.property("style_compare_current_status") == (
            "选择分区"
        )

        block.set_policy_row_visible("acknowledgment_body", False)
        assert block.rows["acknowledgment_body"].isHidden() is True
        block.set_override_row_visible("acknowledgment_body", True)
        assert block.rows["acknowledgment_body"].isHidden() is False

        assert block.set_policy_checked("references_body", True) is True
        assert block.toggles["references_body"].isChecked() is True
        assert block.toggles["references_body"].thumb_position == (
            block.toggles["references_body"].TRACK_W
            - block.toggles["references_body"].THUMB_D
            - block.toggles["references_body"].THUMB_MARGIN
        )
        assert block.set_policy_checked("references_body", False) is True
        assert block.toggles["references_body"].isChecked() is False
        assert block.toggles["references_body"].thumb_position == (
            block.toggles["references_body"].THUMB_MARGIN
        )
        assert block.set_policy_checked("unknown", True) is False
        assert block.set_override_checked("references_body", True) is True
        assert block.has_policy_key("references_body") is True
        assert block.has_policy_key("unknown") is False
        assert block.has_variant("references_body") is True
        assert (
            block.policy_toggle_for_key("references_body")
            is block.toggles["references_body"]
        )
        assert block.override_toggle_for_variant("references_body") is (
            block.toggles["references_body"]
        )
        assert block.override_toggle_for_variant("unknown") is None
        assert block.set_policy_checked("references_body", False) is True
        assert block.editor_widget_for_field("font_cn") is block.editor.font_cn
        assert block.editor_widget_for_field("") is None
        assert (
            block.navigation_widget_for_field(
                "font_cn",
                variant_key="references_body",
                prefer_toggle=True,
            )
            is block.toggles["references_body"]
        )
        assert (
            block.navigation_widget_for_field("font_cn", variant_key="references_body")
            is block.editor.font_cn
        )
        assert (
            block.navigation_widget_for_field(
                "font_cn",
                variant_key="references_body",
                prefer_toggle_when_unchecked=True,
            )
            is block.toggles["references_body"]
        )
        block.set_editor_editable(False)
        assert block.editor.font_cn.isEnabled() is False
        block.set_editor_editable(True)
        assert block.editor.font_cn.isEnabled() is True
        target_style = StyleConfig()
        block.set_editor_values(font_cn="黑体", bold=True, line_spacing_type="single")
        block.apply_editor_to_style(target_style)
        assert target_style.font_cn == "黑体"
        assert target_style.bold is True
        assert target_style.line_spacing_type == "single"

        index = block.selector.findData("acknowledgment_body")
        assert index >= 0
        block.selector.setCurrentIndex(index)
        app.processEvents()
        assert block.current_variant_key() == "acknowledgment_body"
        assert block.current_policy_key() == "acknowledgment_body"
        assert block.rows["acknowledgment_body"].property(
            "style_policy_row_current"
        ) is True
        assert block.rows["references_body"].property(
            "style_policy_row_current"
        ) is False
        assert changed[-1] == "acknowledgment_body"

        assert block.set_current_policy_key("references_body") is True
        assert block.current_variant_key() == "references_body"
        assert block.current_policy_key() == "references_body"
        assert block.rows["references_body"].property(
            "style_policy_row_current"
        ) is True

        block.toggles["references_body"].click()
        app.processEvents()
        assert toggled[-1] == ("references_body", True)

        block.restore_button.click()
        app.processEvents()
        assert restored == [True]
    finally:
        block.close()
        app.processEvents()


def test_scene_panel_controls_follow_template_management_contract():
    source = (ROOT / "src/ui/panels/scene_panel.py").read_text(encoding="utf-8")
    surface_source = (
        ROOT / "src/shared/ui/paragraph_style_surface.py"
    ).read_text(encoding="utf-8")
    toolbar_source = (
        ROOT / "src/shared/ui/style_owner_toolbar.py"
    ).read_text(encoding="utf-8")
    scope_checklist_source = (
        ROOT / "src/shared/ui/scope_zone_checklist.py"
    ).read_text(encoding="utf-8")
    scope_section_source = (
        ROOT / "src/ui/panels/scene_scope_sections.py"
    ).read_text(encoding="utf-8")
    style_override_section_source = (
        ROOT / "src/ui/panels/scene_style_override_sections.py"
    ).read_text(encoding="utf-8")
    style_rules_block_source = (
        ROOT / "src/ui/panels/scene_style_rules_block.py"
    ).read_text(encoding="utf-8")
    style_object_builder_source = (
        ROOT / "src/ui/panels/style_object_projection_builders.py"
    ).read_text(encoding="utf-8")
    style_editing_source = (
        ROOT / "src/shared/ui/style_editing_section.py"
    ).read_text(encoding="utf-8")
    style_management_source = (
        ROOT / "src/shared/ui/style_management_block.py"
    ).read_text(encoding="utf-8")
    override_list_source = (
        ROOT / "src/shared/ui/style_override_toggle_list.py"
    ).read_text(encoding="utf-8")
    policy_list_source = (
        ROOT / "src/shared/ui/style_policy_toggle_list.py"
    ).read_text(encoding="utf-8")
    owner_state_source = (
        ROOT / "src/shared/ui/style_owner_state.py"
    ).read_text(encoding="utf-8")
    service_source = (
        ROOT / "src/ui/panels/scene_style_override_service.py"
    ).read_text(encoding="utf-8")
    scope_service_source = (
        ROOT / "src/ui/panels/scene_scope_service.py"
    ).read_text(encoding="utf-8")
    editor_source = (
        ROOT / "src/shared/ui/paragraph_style_editor.py"
    ).read_text(encoding="utf-8")

    assert "QRadioButton" not in source
    assert "ThemedRadioButton" in source
    assert "SceneScopeZoneSection" in source
    assert "SceneStyleRulesBlock" in source
    assert "SceneStyleOverrideSection" not in source
    assert "_StyleRulesDetail" in source
    assert "StyleControlSurface" not in source
    assert "ScopeZoneChecklist" not in source
    assert "ScopeZoneOption" not in source
    assert "scene_section_style_override_projection" in source
    assert "set_scene_section_style_override" in source
    assert "restore_scene_section_style_to_template" in source
    assert "apply_scene_scope_zone_states" in source
    assert "sync_disabled_section_style_overrides" not in source
    assert "enable_section_style_override" not in source
    assert "disable_section_style_override" not in source
    assert "build_section_style_override_projection" not in source
    assert "build_section_style_preview_projection" not in source
    assert "StyleControlOwnerToolbar" not in source
    assert "StyleOwnerOption" not in source
    assert "StyleOverrideToggleList" not in source
    assert "StyleOverrideToggleOption" not in source
    assert "management_block = self._style_override_section.management_block" not in source
    assert "rule_deck = self._style_override_section.rule_control_deck" not in source
    assert "editing_section = self._style_override_section.editing_section" not in source
    assert "self._style_rules_block.toggle_list" in source
    assert "self._style_rules_block.style_surface" in source
    assert "self._section_style_editor =" not in source
    assert "self._section_font_cn =" not in source
    assert "self._section_font_en =" not in source
    assert "self._section_size_combo =" not in source
    assert "self._section_bold_switch =" not in source
    assert "self._section_italic_switch =" not in source
    assert "self._section_emphasis =" not in source
    assert "self._section_alignment_combo =" not in source
    assert "self._section_special_indent =" not in source
    assert "self._section_left_indent =" not in source
    assert "self._section_right_indent =" not in source
    assert "self._section_line_type_combo =" not in source
    assert "self._section_line_value =" not in source
    assert "self._section_line_value_suffix =" not in source
    assert "self._section_space_before =" not in source
    assert "self._section_space_after =" not in source
    assert "TRACK_W" not in source
    assert "THUMB_D" not in source
    assert "thumb_position" not in source
    assert "set_policy_checked(" in source
    assert "set_override_checked(" not in source
    assert "set_policy_checked(" in style_rules_block_source
    assert "set_override_checked(" in style_rules_block_source
    assert "_variant_toggles.get" not in source
    assert "_section_style_editor.widget_for_field(" not in source
    assert "navigation_widget_for_field(" in source
    assert "editor_widget_for_field(" in source
    assert "has_policy_key(" in source
    assert "scene_style_navigation_target_from_field_id" in source
    assert "has_variant(" not in source
    assert "_section_style_editor.set_editable(" not in source
    assert "_section_style_editor.apply_to_style(" not in source
    assert "set_editor_editable(" in source
    assert "apply_editor_to_style(" in source
    assert "set_editor_editable(" in style_rules_block_source
    assert "apply_editor_to_style(" in style_rules_block_source
    assert "set_editor_values(" in style_rules_block_source
    assert "self.editor.set_values(" in style_rules_block_source
    assert "build_scene_section_style_projection" in source
    assert "scene_section_style_owner_state" not in source
    assert "scene_section_style_owner_state" in style_object_builder_source
    assert "ParagraphStyleEditor" not in source
    assert "StyleControlSurfaceState(" not in source
    assert "NavigationHighlighter" in source
    assert "当前执行问题定位" not in source
    assert "_navigation_highlight_base_style" not in source
    assert "FontCombo(" not in source
    assert "SizeCombo(" not in source
    assert "SpecialIndentInput(" not in source
    assert "IndentInput(" not in source
    assert "SpacingInput(" not in source
    assert "build_emphasis_widget" not in source
    assert "LINE_SPACING_OPTIONS" not in source
    assert "FontCombo(" in editor_source
    assert "SizeCombo(" in editor_source
    assert "SpecialIndentInput(" in editor_source
    assert "IndentInput(" in editor_source
    assert "SpacingInput(" in editor_source
    assert "build_emphasis_widget" in editor_source
    assert "LINE_SPACING_OPTIONS" in editor_source
    assert "ParagraphStyleEditor(" in surface_source
    assert "style_field_layout_rows" in surface_source
    assert "InspectorForm(" in surface_source
    assert "template_form_row(selector_label" in toolbar_source
    assert "StyledComboBox(" in toolbar_source
    assert "QPushButton(action_label" in toolbar_source
    assert "ScopeZoneChecklist" in scope_checklist_source
    assert "build_checkbox_stylesheet" in scope_checklist_source
    assert "ScopeZoneChecklist" in scope_section_source
    assert "ScopeZoneOption" in scope_section_source
    assert "SummaryGrid(" in scope_section_source
    assert "SceneStyleOverrideSection(" in style_rules_block_source
    assert "policy_toggled.connect(self.policy_toggled.emit)" in style_rules_block_source
    assert "override_toggled.connect(self.override_toggled.emit)" in style_rules_block_source
    assert "def management_block" in style_rules_block_source
    assert "def rule_control_deck" in style_rules_block_source
    assert "def editing_section" in style_rules_block_source
    assert "StyleManagementBlock" in style_override_section_source
    assert "StyleEditingSection(" not in style_override_section_source
    assert "StyleControlSurface" not in style_override_section_source
    assert "StyleControlOwnerToolbar" not in style_override_section_source
    assert "StyleOwnerOption" in style_override_section_source
    assert "StylePolicyToggleList" in style_override_section_source
    assert "StylePolicyToggleOption" in style_override_section_source
    assert "StyleOverrideToggleList" not in style_override_section_source
    assert "StyleOverrideToggleOption" not in style_override_section_source
    assert "StyleControlSurface" in style_editing_source
    assert "StyleControlOwnerToolbar" in style_editing_source
    assert "StylePreviewSurface(" in style_editing_source
    assert "show_metadata=False" in style_editing_source
    assert "StylePreview(" in style_editing_source
    assert "DetailSummaryCard(" in style_management_source
    assert "TemplateSummaryCard(" not in style_management_source
    assert "StyleEditingSection(" in style_management_source
    assert "StylePolicyToggleList" in policy_list_source
    assert "ToggleSwitch(row" in policy_list_source
    assert "toggled = Signal(str, bool)" in policy_list_source
    assert "StyleOverrideToggleList(StylePolicyToggleList)" in override_list_source
    assert "ToggleSwitch(row" not in override_list_source
    assert "scene_section_style_owner_state" in owner_state_source
    assert "StyleOwnerViewState" in owner_state_source
    assert "enable_section_style_override" in service_source
    assert "disable_section_style_override" in service_source
    assert "build_section_style_override_projection" in service_source
    assert "apply_scene_scope_zone_states" in scope_service_source
    assert "sync_disabled_section_style_overrides" not in scope_service_source
    assert "style_field_layout_rows" in editor_source
    assert "template_form_pair_row(rows[0], rows[1]" in editor_source
    assert '"font_cn": self._font_cn' in editor_source
    assert '"emphasis": self._emphasis' in editor_source
    assert '"line_spacing_pt": self._line_value' in editor_source
    assert "build_text_input_stylesheet" in source
    assert "apply_button_variant" in source
    assert "_tpl_combo" not in source
    assert '"关联模板"' not in source

    app = _app()
    bridge = PanelBridge()
    scene = create_thesis_scene()
    template = create_builtin_template("thesis_gbt")
    bridge.set_current_scene(scene, config_id="thesis", emit_signal=False)
    bridge.set_current_template(template, config_id="thesis_gbt", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        assert isinstance(panel._overview._rebuild_radio, ThemedRadioButton)
        assert isinstance(panel._overview._preserve_radio, ThemedRadioButton)
        assert panel._overview._strategy_group.exclusive() is True
        assert panel._nav_cards["scn_content"].isHidden() is False
        assert panel._nav_section_headers["input_material"].isHidden() is False
        for detail in (
            panel._scope,
            panel._cleanup,
            panel._content,
            panel._output,
        ):
            assert detail._detail_summary.value_for("advanced_evidence") == ""
        assert panel._scope._detail_summary.isVisibleTo(panel._scope) is False
        assert panel._scope._detail_summary.value_for("main_controls") == "按模板默认"
        assert panel._scope._detail_summary.detail_for("main_controls") == (
            "模板负责识别正文、附录等区域。"
        )
        assert panel._cleanup._detail_summary.value_for("main_controls") == "执行前检查"
        assert panel._cleanup._detail_summary.value_for("risk_note") == "高风险先提醒"
        assert panel._output._detail_summary.value_for("main_controls") == "交付版本"
        assert panel._output._detail_summary.value_for("risk_note") == "输出路径需确认"
        output_labels = {
            row.label_text for row in panel._output.findChildren(FormRow)
        }
        assert "最终 Word" in output_labels
        assert "对比 Word" in output_labels
        assert "交付名称" in output_labels
        assert "交付编号" in output_labels
        assert "版本管理" in output_labels
        assert "版本模板" in output_labels
        assert "命名信息" in output_labels
        assert "添加内容块" in output_labels
        assert "内容块规则" in output_labels
        assert "最终 DOCX" not in output_labels
        assert "对比 DOCX" not in output_labels
        assert "交付 ID" not in output_labels
        assert "交付操作" not in output_labels
        assert "业务模板" not in output_labels
        assert "变量插入" not in output_labels
        assert "规则插入" not in output_labels
        assert "显隐规则" not in output_labels
        assert panel._output._add_preset_btn.text() == "新增版本"
        assert panel._output._copy_preset_btn.text() == "复制版本"
        assert panel._output._remove_preset_btn.text() == "移除版本"
        assert panel._output._add_preset_template_btn.text() == "套用模板"
        assert panel._output._apply_family_delivery_btn.text() == "应用推荐"
        assert "新增交付版本" in panel._output._add_preset_template_btn.toolTip()
        assert "推荐交付版本" in panel._output._apply_family_delivery_btn.toolTip()
        student_template_index = panel._output._delivery_preset_template_combo.findData(
            "student_version"
        )
        assert student_template_index >= 0
        assert (
            panel._output._delivery_preset_template_combo.itemText(student_template_index)
            == "学生版"
        )
        student_template_tooltip = panel._output._delivery_preset_template_combo.itemData(
            student_template_index,
            Qt.ToolTipRole,
        )
        assert "新增交付版本：学生版" in student_template_tooltip
        assert "输出内容：最终 Word、报告 JSON、报告 Markdown" in student_template_tooltip
        assert "答案：删除块" in student_template_tooltip
        assert "解析：删除块" in student_template_tooltip
        assert "模板编号：student_version" in student_template_tooltip
        assert "student_version" not in panel._output._delivery_preset_template_combo.itemText(
            student_template_index
        )
        assert panel._output._delivery_preset_id.placeholderText() == "自动生成，可按需修改"
        assert "review_copy" not in panel._output._delivery_preset_id.placeholderText()
        assert "review_copy" in panel._output._delivery_preset_id.toolTip()
        content_labels = {
            row.label_text for row in panel._content.findChildren(FormRow)
        }
        assert "必填资料字段" in content_labels
        assert "必需图片/签章" in content_labels
        assert "必填字段" not in content_labels
        assert "资产角色" not in content_labels
        assert panel._content._replace_unknown_schema_btn.text() == "替换未识别"
        assert panel._content._remove_unknown_schema_btn.text() == "移除未识别"
        selector = panel._content._material_rule_selector
        assert selector is panel._content._material_requirement_block
        assert selector.schema_registry_tools is panel._content._schema_registry_tools
        assert selector.primary_schema_editor is panel._content._material_schema_id
        assert selector.schema_list_editor is panel._content._material_schema_ids
        assert (
            selector.required_material_fields_editor
            is panel._content._required_material_fields
        )
        assert selector.required_image_roles_editor is panel._content._required_image_roles
        assert selector.preview_summary is panel._content._schema_validation_summary
        assert (
            selector.navigation_widget_for_field(
                "input_source_profile.material_schema_id"
            )
            is panel._content._material_schema_id
        )
        assert (
            selector.navigation_widget_for_field(
                "input_source_profile.required_material_fields"
            )
            is panel._content._required_material_fields
        )
        assert (
            selector.navigation_widget_for_field(
                "input_source_profile.required_image_roles"
            )
            is panel._content._required_image_roles
        )
        contract_schema_index = panel._content._schema_registry_combo.findData(
            "contract_parties_v1"
        )
        assert contract_schema_index >= 0
        assert (
            panel._content._schema_registry_combo.itemText(contract_schema_index)
            == "合同方字段资料"
        )
        assert (
            "contract_parties_v1"
            not in panel._content._schema_registry_combo.itemText(contract_schema_index)
        )
        schema_tooltip = panel._content._schema_registry_combo.itemData(
            contract_schema_index,
            Qt.ToolTipRole,
        )
        assert "contract_parties_v1" in schema_tooltip
        assert "Contract party fields" in schema_tooltip
        schema_id_placeholder = panel._content._material_schema_id.placeholderText()
        schema_list_placeholder = (
            panel._content._material_schema_ids._text_edit.placeholderText()
        )
        field_placeholder = (
            panel._content._required_material_fields._text_edit.placeholderText()
        )
        image_placeholder = (
            panel._content._required_image_roles._text_edit.placeholderText()
        )
        assert "资料规则" in schema_id_placeholder
        assert "资料规则" in schema_list_placeholder
        assert "资料规则" in field_placeholder
        assert "资料规则" in image_placeholder
        assert "资料字段" in field_placeholder
        assert "图片或签章" in image_placeholder
        assert "contract_parties_v1" not in schema_id_placeholder
        assert "signature_assets_v1" not in schema_list_placeholder
        assert "party_a" not in field_placeholder
        assert "seal" not in image_placeholder
        assert "schema" not in schema_id_placeholder.lower()
        assert "schema" not in schema_list_placeholder.lower()
        variable_index = panel._output._delivery_variable_combo.findData("preset_label")
        assert variable_index >= 0
        variable_text = panel._output._delivery_variable_combo.itemText(variable_index)
        assert "preset_label" not in variable_text
        assert "{preset_label}" not in variable_text
        variable_tooltip = panel._output._delivery_variable_combo.itemData(
            variable_index,
            Qt.ToolTipRole,
        )
        assert "{preset_label}" in variable_tooltip
        assert "交付名称" in variable_tooltip
        assert "preset_label" not in panel._output._delivery_variable_combo.toolTip()

        selector_index = panel._output._visibility_selector_combo.findData("answer")
        assert selector_index >= 0
        selector_text = panel._output._visibility_selector_combo.itemText(selector_index)
        assert selector_text == "答案"
        assert "answer" not in selector_text
        selector_tooltip = panel._output._visibility_selector_combo.itemData(
            selector_index,
            Qt.ToolTipRole,
        )
        assert "answer" in selector_tooltip
        assert "{{#visibility:answer}}" in selector_tooltip
        assert "answer" not in panel._output._visibility_selector_input.placeholderText()
        assert "{{#visibility:answer}}" not in panel._output._visibility_selector_input.placeholderText()

        for line_edit in (
            panel._content._material_schema_id,
            panel._content._watermark_text,
            panel._output._delivery_preset_id,
            panel._output._delivery_label,
            panel._output._delivery_target_template,
            panel._output._delivery_output_dir,
            panel._output._delivery_filename,
            panel._output._visibility_selector_input,
        ):
            assert line_edit.property("sizeClass") == "md"
            assert "QLineEdit" in line_edit.styleSheet()
            assert "border-radius" in line_edit.styleSheet()

        expected_variants = {
            panel._overview._new_scene_btn: "secondary",
            panel._overview._duplicate_scene_btn: "secondary",
            panel._overview._rename_scene_btn: "secondary",
            panel._overview._open_scene_folder_btn: "secondary",
            panel._overview._delete_scene_btn: "ghost-danger",
            panel._content._set_primary_schema_btn: "secondary",
            panel._content._append_schema_btn: "secondary",
            panel._content._replace_unknown_schema_btn: "secondary",
            panel._content._remove_unknown_schema_btn: "ghost-danger",
            panel._cleanup._apply_family_preflight_btn: "secondary",
            panel._output._add_preset_btn: "secondary",
            panel._output._copy_preset_btn: "secondary",
            panel._output._remove_preset_btn: "ghost-danger",
            panel._output._move_up_preset_btn: "secondary",
            panel._output._move_down_preset_btn: "secondary",
            panel._output._add_preset_template_btn: "secondary",
            panel._output._apply_family_delivery_btn: "secondary",
            panel._output._insert_output_variable_btn: "secondary",
            panel._output._insert_filename_variable_btn: "secondary",
            panel._output._insert_visibility_rule_btn: "secondary",
        }
        for button, variant in expected_variants.items():
            assert button.property("variant") == variant
            assert button.property("sizeClass") == "md"
            assert "QPushButton[variant" in button.styleSheet()
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_projects_scene_profiles_with_shared_summary_grid():
    source = (ROOT / "src/ui/panels/scene_panel.py").read_text(encoding="utf-8")
    projection_source = (
        ROOT / "src/ui/panels/scene_summary_projection.py"
    ).read_text(encoding="utf-8")

    assert "scene_summary_projection" in source
    assert "SummaryGrid" in source
    assert "build_scene_overview_summary_items" in source
    assert "build_scene_scope_summary_items" in source
    assert "build_input_profile_summary_items" in source
    assert "build_compliance_summary_items" in source
    assert "build_scene_style_override_summary_items" in source
    assert "build_parameter_ownership_summary_items" in projection_source
    assert "build_coverage_summary_items" in projection_source
    assert "build_scene_style_override_summary_items" in projection_source
    assert "build_delivery_summary_items" in source
    assert "input_source_profile" in source
    assert "compliance_profile" in source
    assert "default_delivery_preset_id" in source


def test_scene_navigation_cards_use_readable_status_subtitles():
    _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(
        scene_id="contract_delivery",
        category="contract_delivery",
        template_id="default",
    )
    scene.input_source_profile.accepted_formats = ["docx", "xlsx"]
    scene.input_source_profile.required_material_fields = [
        "company_name",
        "contract_no",
    ]
    scene.input_source_profile.material_schema_id = "contract_parties_v1"
    scene.compliance_profile.rule_family = "contract_delivery"
    scene.compliance_profile.count_profile_id = "contract_fields"
    panel = ScenePanel(bridge)
    try:
        snapshots = panel._navigation_card_snapshots(scene)
        content_subtitle = snapshots["scn_content"]["subtitle"]
        rules_subtitle = snapshots["scn_rules"]["subtitle"]

        assert "scn_features" not in snapshots
        assert "scn_table_chart" not in snapshots
        assert "scn_formula" not in snapshots
        assert "scn_citation" not in snapshots
        assert "scn_scope" not in snapshots
        assert "scn_style_rules" not in snapshots
        assert "scn_reference" not in snapshots
        assert "scn_cleanup" not in snapshots
        assert "scn_output" not in snapshots
        assert "Word 文档、Excel 表格" in content_subtitle
        assert "资料字段 2 个" in content_subtitle
        assert "资料规则 1 项" in content_subtitle
        assert "schema" not in content_subtitle.lower()
        assert "/" not in content_subtitle
        assert "_" not in content_subtitle
        assert "/" not in rules_subtitle
        assert "按模板默认" in rules_subtitle
        assert "无格式例外" in rules_subtitle
        assert "产物" in rules_subtitle
        assert snapshots["scn_rules"]["badge_text"] == "按模板默认"
        assert snapshots["scn_content"]["badge_text"] == "已配置"
    finally:
        panel.close()


def test_scene_scope_summary_projection_tracks_application_boundary():
    scene = SceneWorkspace(scene_id="scope_summary", template_id="default")

    default_items = {
        item.key: item for item in build_scene_scope_summary_items(scene)
    }
    assert set(default_items) == {"main_controls"}
    assert default_items["main_controls"].label == "处理范围"
    assert default_items["main_controls"].value == "按模板默认"
    assert default_items["main_controls"].detail == "模板负责识别正文、附录等区域。"

    scene.application_boundary.mode = "body_only"

    items = {
        item.key: item for item in build_scene_scope_summary_items(scene)
    }
    assert items["main_controls"].value == "只处理正文"
    assert items["main_controls"].detail == "只处理模板识别出的正文内容。"

    scene.application_boundary.mode = "confirm_before_apply"
    confirm_items = {
        item.key: item for item in build_scene_scope_summary_items(scene)
    }
    assert confirm_items["main_controls"].value == "每次执行前选择"
    assert confirm_items["main_controls"].variant == "warning"


def test_scene_style_override_summary_projection_tracks_follow_and_override():
    template = create_builtin_template("thesis_gbt")
    scene = SceneWorkspace(scene_id="thesis", template_id="thesis_gbt")
    scene.format_scope.sections["acknowledgment"] = True

    projection = build_section_style_override_projection(
        scene,
        template,
        "references_body",
    )
    items = {
        item.key: item
        for item in build_scene_style_override_summary_items(scene, projection)
    }

    assert items["override_status"].value == "无格式例外"
    assert items["override_status"].detail == "默认跟随模板；需要局部不同时再添加例外。"
    assert items["current_variant_status"].value == "参考文献 · 跟随模板"
    assert items["current_variant_status"].detail == "使用模板样式。"
    assert items["owner_boundary"].value == "仅当前场景"

    enable_section_style_override(scene, template, "references_body")
    projection = build_section_style_override_projection(
        scene,
        template,
        "references_body",
    )
    items = {
        item.key: item
        for item in build_scene_style_override_summary_items(scene, projection)
    }

    assert items["override_status"].value == "1 个格式例外"
    assert items["override_status"].detail == "参考文献"
    assert items["current_variant_status"].value == "参考文献 · 已开启独立样式"
    assert items["current_variant_status"].detail == "与模板一致。"


def test_scene_section_style_override_service_tracks_actions_and_projections():
    template = create_builtin_template("thesis_gbt")
    template.styles["references_body"] = StyleConfig(font_cn="黑体")
    scene = SceneWorkspace(scene_id="thesis", template_id="thesis_gbt")
    scene.format_scope.sections["references"] = True

    projection = scene_section_style_override_projection(
        scene,
        template,
        "references_body",
    )
    assert projection.status_value == "跟随模板"
    assert projection.editor_hint == "跟随模板 · 开启独立样式后可编辑"
    assert scene_section_effective_style(scene, template, "references_body").font_cn == "黑体"

    style = set_scene_section_style_override(
        scene,
        template,
        "references_body",
        True,
    )
    assert style is scene.section_styles["references_body"]
    assert style.font_cn == "黑体"

    projection = scene_section_style_override_projection(
        scene,
        template,
        "references_body",
    )
    preview = scene_section_style_preview_projection(
        scene,
        template,
        "references_body",
    )
    assert projection.status_value == "已开启独立样式"
    assert projection.editor_hint == "已开启独立样式 · 与模板一致"
    assert preview.source_label == "已开启独立样式"

    assert restore_scene_section_style_to_template(scene, "references_body") is True
    assert "references_body" not in scene.section_styles
    assert restore_scene_section_style_to_template(scene, "references_body") is False


def test_scene_section_style_owner_state_keeps_main_hint_short_when_following_template():
    owner_state = scene_section_style_owner_state(
        style=StyleConfig(font_cn="黑体"),
        variant_label="参考文献",
        section_enabled=True,
        overridden=False,
    )

    assert owner_state.hint == "跟随模板 · 开启独立样式后可编辑"
    assert "参考文献：" not in owner_state.hint
    assert owner_state.surface_state.readonly_reason == (
        "参考文献：跟随模板。开启独立样式后可编辑。"
    )


def test_scene_section_style_restore_all_service_clears_known_overrides():
    template = create_builtin_template("thesis_gbt")
    scene = SceneWorkspace(scene_id="thesis", template_id="thesis_gbt")
    scene.format_scope.sections["references"] = True
    scene.format_scope.sections["appendix"] = True

    set_scene_section_style_override(scene, template, "references_body", True)
    set_scene_section_style_override(scene, template, "appendix_body", True)

    restored = restore_all_scene_section_styles_to_template(scene)

    assert restored == ("references_body", "appendix_body")
    assert "references_body" not in scene.section_styles
    assert "appendix_body" not in scene.section_styles
    assert restore_all_scene_section_styles_to_template(scene) == ()


def test_scene_section_style_override_service_preserves_format_exceptions_when_scope_changes():
    template = create_builtin_template("thesis_gbt")
    scene = SceneWorkspace(scene_id="thesis", template_id="thesis_gbt")
    scene.format_scope.sections["references"] = True
    scene.format_scope.sections["appendix"] = False

    set_scene_section_style_override(scene, template, "references_body", True)
    set_scene_section_style_override(scene, template, "appendix_body", True)

    dropped = sync_disabled_section_style_overrides(scene)

    assert dropped == ()
    assert "references_body" in scene.section_styles
    assert "appendix_body" in scene.section_styles


def test_scene_style_variants_respect_exam_paper_boundary_and_legacy_overrides():
    template = create_builtin_template("default")
    scene = create_exam_scene()

    assert scene_style_variants_for_scene(scene, template) == ()

    scene.section_styles["appendix_body"] = StyleConfig(font_cn="仿宋")

    assert [
        variant.key for variant in scene_style_variants_for_scene(scene, template)
    ] == ["appendix_body"]

    example_scene = SceneWorkspace(scene_id="example_custom", template_id="default")

    assert scene_style_variants_for_scene(example_scene, template) == STYLE_VARIANTS


def test_scene_scope_service_applies_zone_states_without_cleaning_format_exceptions():
    template = create_builtin_template("thesis_gbt")
    scene = SceneWorkspace(scene_id="thesis", template_id="thesis_gbt")
    scene.format_scope.sections["references"] = True
    scene.format_scope.sections["appendix"] = True

    set_scene_section_style_override(scene, template, "references_body", True)
    set_scene_section_style_override(scene, template, "appendix_body", True)

    dropped = apply_scene_scope_zone_states(
        scene,
        {
            "references": False,
            "appendix": True,
        },
    )

    assert dropped == ()
    assert scene.format_scope.sections["references"] is False
    assert scene.format_scope.sections["appendix"] is True
    assert "references_body" in scene.section_styles
    assert "appendix_body" in scene.section_styles


def test_scene_panel_does_not_mount_template_page_number_summary_in_scene():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(
        scene_id="thesis",
        template_id="thesis_gbt",
        default_template_id="thesis_gbt",
        compatible_template_ids=["thesis_gbt"],
    )
    scene.header_footer.page_number_enabled = False
    template = create_builtin_template("thesis_gbt")
    bridge.set_current_scene(scene, config_id="thesis", emit_signal=False)
    bridge.set_current_template(template, config_id="thesis_gbt", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        assert hasattr(panel, "_page_elem") is False
        assert "scn_page_elem" not in panel._detail_map
        assert "scn_page_elem" not in panel._nav_cards
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_scope_style_override_editor_writes_section_styles():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="thesis", template_id="thesis_gbt")
    scene.format_scope.sections["acknowledgment"] = True
    template = create_builtin_template("thesis_gbt")
    bridge.set_current_scene(scene, config_id="thesis", emit_signal=False)
    bridge.set_current_template(template, config_id="thesis_gbt", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()
        scope_detail = panel._scope
        scope = panel._style_rules
        font_cn_widget = scope._style_rules_block.editor_widget_for_field("font_cn")
        special_indent_widget = scope._style_rules_block.editor_widget_for_field(
            "special_indent"
        )
        line_value_widget = scope._style_rules_block.editor_widget_for_field(
            "line_spacing_pt"
        )
        assert font_cn_widget is not None
        assert special_indent_widget is not None
        assert line_value_widget is not None

        assert "acknowledgment_body" not in scene.section_styles
        assert font_cn_widget.isEnabled() is False
        assert special_indent_widget.isEnabled() is False
        assert scope._style_editor_hint.text() == "跟随模板 · 开启独立样式后可编辑"
        assert "致谢：" not in scope._style_editor_hint.text()
        assert not scope._restore_section_style_btn.isEnabled()
        assert scope._section_style_preview.isEnabled()
        assert "致谢样式预览" in scope._section_style_preview.text()
        assert "跟随模板" in scope._section_style_preview.toolTip()
        assert scope._section_style_preview.property("style_preview_source_label") == (
            "跟随模板"
        )
        assert scope._section_style_preview.property("style_presentation_kind") == (
            "section_paragraph"
        )
        assert scope._section_style_preview.property("style_presentation_title") == (
            "致谢"
        )
        assert scope._section_style_preview.property("style_presentation_summary") == (
            "跟随模板"
        )
        assert scope._section_style_preview.property("style_presentation_detail") == (
            "使用模板样式。"
        )
        assert scope._section_style_preview.property(
            "style_presentation_action_label"
        ) == "调例外"
        assert scope._style_comparison_strip.property("style_compare_template_status") == (
            "模板基线"
        )
        assert scope._style_comparison_strip.property("style_compare_current_status") == (
            "跟随模板"
        )
        assert scope._style_comparison_strip.property("style_compare_difference_status") == (
            "无差异"
        )
        assert scope._style_override_summary.value_for("override_status") == "无格式例外"
        assert (
            scope._style_override_summary.value_for("current_variant_status")
            == "致谢 · 跟随模板"
        )
        assert scope._style_override_summary.value_for("owner_boundary") == "仅当前场景"
        assert scope._style_owner_status.property("style_owner_source_status") == (
            "跟随模板"
        )
        assert scope._style_owner_status.property("style_owner_scope_status") == (
            "来自模板"
        )
        assert scope._style_owner_status.property("style_owner_edit_status") == (
            "开启独立样式后可编辑"
        )
        assert scope._style_surface.property("style_surface_owner_kind") == (
            "scene_section_style"
        )
        assert scope._style_surface.property("style_surface_active_label") == (
            "致谢"
        )
        assert scope._style_surface.property("style_surface_source_label") == (
            "跟随模板"
        )
        assert scope._style_surface.property("style_surface_editable") is False
        assert "开启独立样式后可编辑" in scope._style_surface.property(
            "style_surface_readonly_reason"
        )
        assert scope.focus_navigation_field("section_styles.acknowledgment_body.font_cn") is True
        acknowledgment_toggle = scope._style_rules_block.policy_toggle_for_key(
            "acknowledgment_body"
        )
        assert acknowledgment_toggle is not None
        assert scope._style_rules_block.current_policy_key() == "acknowledgment_body"
        assert scope._style_rules_block.rows["acknowledgment_body"].property(
            "style_policy_row_current"
        ) is True
        assert bool(acknowledgment_toggle.property("navigation_field_highlight"))
        assert scope.focus_navigation_field("scene.section_styles.acknowledgment_body") is True
        assert scope._style_variant_combo.currentData() == "acknowledgment_body"
        assert scope._style_rules_block.current_policy_key() == "acknowledgment_body"
        assert bool(acknowledgment_toggle.property("navigation_field_highlight"))
        assert scope.focus_navigation_field("scene.section_styles.*.font_cn") is True
        assert scope._style_variant_combo.currentData() == "acknowledgment_body"
        assert scope._style_rules_block.current_policy_key() == "acknowledgment_body"
        assert bool(acknowledgment_toggle.property("navigation_field_highlight"))
        assert scope_detail.focus_navigation_field("format_scope.sections.acknowledgment") is True
        assert bool(scope_detail._zone_checks["acknowledgment"].property("navigation_field_highlight"))

        assert scope._style_rules_block.set_policy_checked("acknowledgment_body", True)
        scope._on_variant_toggled("acknowledgment_body", True)
        app.processEvents()

        assert "acknowledgment_body" in scene.section_styles
        assert font_cn_widget.isEnabled() is True
        assert special_indent_widget.isEnabled() is True
        assert scope._restore_section_style_btn.isEnabled()
        assert "与模板一致" in scope._style_editor_hint.text()
        assert "已开启独立样式" in scope._section_style_preview.toolTip()
        assert scope._section_style_preview.property("style_preview_source_label") == (
            "已开启独立样式"
        )
        assert scope._section_style_preview.property("style_presentation_summary") == (
            "已开启独立样式"
        )
        assert "与模板一致" in scope._section_style_preview.property(
            "style_preview_detail"
        )
        assert scope._style_comparison_strip.property("style_compare_current_status") == (
            "独立样式"
        )
        assert scope._style_comparison_strip.property("style_compare_difference_status") == (
            "未改字段"
        )
        assert scope._style_comparison_strip.property("style_compare_detail") == (
            "已独立，但字段仍与模板一致。"
        )
        assert scope._style_override_summary.value_for("override_status") == "1 个格式例外"
        assert "致谢" in scope._style_override_summary.detail_for("override_status")
        assert (
            scope._style_override_summary.value_for("current_variant_status")
            == "致谢 · 已开启独立样式"
        )
        assert scope._style_surface.property("style_surface_source_label") == (
            "已开启独立样式"
        )
        assert scope._style_owner_status.property("style_owner_source_status") == (
            "已开启独立样式"
        )
        assert scope._style_owner_status.property("style_owner_scope_status") == (
            "仅当前场景"
        )
        assert scope._style_owner_status.property("style_owner_edit_status") == "可编辑"
        assert scope._style_surface.property("style_surface_editable") is True
        assert scope._style_surface.property("style_surface_readonly_reason") == ""
        assert scope.focus_navigation_field("scene.section_styles.acknowledgment_body.font_cn") is True
        assert scope._style_variant_combo.currentData() == "acknowledgment_body"
        assert scope._style_rules_block.current_policy_key() == "acknowledgment_body"
        assert scope._style_rules_block.rows["acknowledgment_body"].property(
            "style_policy_row_current"
        ) is True
        assert bool(font_cn_widget.property("navigation_field_highlight"))
        assert "致谢" in font_cn_widget.toolTip()
        assert "中文字体" in font_cn_widget.toolTip()
        assert "scene.section_styles.acknowledgment_body.font_cn" not in font_cn_widget.toolTip()
        assert font_cn_widget.property("navigation_field_raw_label") == (
            "scene.section_styles.acknowledgment_body.font_cn"
        )

        scope._style_rules_block.set_editor_values(
            font_cn="黑体",
            font_en="Arial",
            size_pt=14.0,
            bold=True,
            italic=True,
            alignment="center",
            special_indent=("first_line", 2.0, "chars"),
            left_indent=(1.0, "cm"),
            right_indent=(12.0, "pt"),
            space_before=(6.0, "pt"),
            space_after=(1.0, "lines"),
            line_spacing_type="single",
        )
        scope._on_style_editor_edited()

        style = scene.section_styles["acknowledgment_body"]
        assert style.font_cn == "黑体"
        assert style.font_en == "Arial"
        assert style.size_pt == 14.0
        assert style.bold is True
        assert style.italic is True
        assert style.alignment == "center"
        assert style.special_indent_mode == "first_line"
        assert style.special_indent_value == 2.0
        assert style.special_indent_unit == "chars"
        assert style.left_indent_chars == 1.0
        assert style.left_indent_unit == "cm"
        assert style.right_indent_chars == 12.0
        assert style.right_indent_unit == "pt"
        assert style.space_before_pt == 6.0
        assert style.space_before_unit == "pt"
        assert style.space_after_pt == 1.0
        assert style.space_after_unit == "lines"
        assert style.line_spacing_type == "single"
        assert line_value_widget.isEnabled() is False
        assert "正在编辑" in scope._style_editor_hint.text()
        assert scope._restore_section_style_btn.isEnabled()
        assert "已调整" in scope._section_style_preview.toolTip()
        assert "不同" in scope._section_style_preview.toolTip()
        assert scope._section_style_preview.property("style_presentation_kind") == (
            "section_paragraph"
        )
        assert scope._section_style_preview.property("style_presentation_title") == (
            "致谢"
        )
        assert str(
            scope._section_style_preview.property("style_presentation_summary")
        ).startswith("已调整 ")
        assert "中文字体" in scope._style_override_summary.detail_for("current_variant_status")
        assert "行距" in scope._style_override_summary.detail_for("current_variant_status")
        assert scope._style_comparison_strip.property(
            "style_compare_difference_status"
        ).startswith("已调整 ")
        assert "中文字体" in scope._style_comparison_strip.property("style_compare_detail")
        assert "行距" in scope._style_comparison_strip.property("style_compare_detail")

        scope._style_rules_block.set_editor_values(line_spacing_type="exact")
        app.processEvents()
        assert line_value_widget.isEnabled() is True
        scope._set_style_editor_variant("appendix_body")
        assert scope._style_variant_combo.currentData() == "appendix_body"
        assert scope.focus_navigation_field("scene.section_styles.*.line_spacing_pt") is True
        assert scope._style_variant_combo.currentData() == "acknowledgment_body"
        assert bool(line_value_widget.property("navigation_field_highlight"))
        assert "行距与段距：所有处理分区行距" in line_value_widget.toolTip()
        assert "所有处理分区行距" in line_value_widget.toolTip()
        assert "scene.section_styles.*.line_spacing_pt" not in line_value_widget.toolTip()
        assert line_value_widget.property("navigation_field_raw_label") == (
            "scene.section_styles.*.line_spacing_pt"
        )

        scope._restore_section_style_btn.click()
        app.processEvents()
        assert "acknowledgment_body" not in scene.section_styles
        assert acknowledgment_toggle.isChecked() is False
        assert font_cn_widget.isEnabled() is False
        assert special_indent_widget.isEnabled() is False
        assert not scope._restore_section_style_btn.isEnabled()
        assert "致谢样式预览" in scope._section_style_preview.text()
        assert "跟随模板" in scope._section_style_preview.toolTip()
        assert scope._style_override_summary.value_for("override_status") == "无格式例外"
        assert (
            scope._style_override_summary.value_for("current_variant_status")
            == "致谢 · 跟随模板"
        )
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_restore_all_section_styles_returns_every_partition_to_template():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="thesis", template_id="thesis_gbt")
    scene.format_scope.sections["references"] = True
    scene.format_scope.sections["appendix"] = True
    template = create_builtin_template("thesis_gbt")
    references_style = set_scene_section_style_override(
        scene,
        template,
        "references_body",
        True,
    )
    appendix_style = set_scene_section_style_override(
        scene,
        template,
        "appendix_body",
        True,
    )
    references_style.font_cn = "黑体"
    appendix_style.font_cn = "仿宋"
    bridge.set_current_scene(scene, config_id="thesis", emit_signal=False)
    bridge.set_current_template(template, config_id="thesis_gbt", emit_signal=False)

    panel = ScenePanel(bridge)
    changed: list[bool] = []
    panel._style_rules.style_rules_changed.connect(lambda: changed.append(True))
    try:
        app.processEvents()
        scope = panel._style_rules
        references_toggle = scope._style_rules_block.policy_toggle_for_key(
            "references_body"
        )
        appendix_toggle = scope._style_rules_block.policy_toggle_for_key(
            "appendix_body"
        )
        assert references_toggle is not None
        assert appendix_toggle is not None

        assert scope._style_override_summary.value_for("override_status") == (
            "1 个格式例外"
        )
        assert scope._restore_all_section_styles_btn.isEnabled() is True
        assert scope._undo_restore_all_section_styles_btn.isEnabled() is False
        assert "参考文献" not in scope._restore_all_section_styles_btn.toolTip()
        assert "附录" in scope._restore_all_section_styles_btn.toolTip()
        assert references_toggle.isChecked() is True
        assert appendix_toggle.isChecked() is True

        scope._restore_all_section_styles_btn.click()
        app.processEvents()

        assert changed == [True]
        assert "references_body" in scene.section_styles
        assert "appendix_body" not in scene.section_styles
        assert references_toggle.isChecked() is True
        assert appendix_toggle.isChecked() is False
        assert scope._restore_all_section_styles_btn.isEnabled() is False
        assert scope._undo_restore_all_section_styles_btn.isEnabled() is True
        assert "参考文献" not in scope._undo_restore_all_section_styles_btn.toolTip()
        assert "附录" in scope._undo_restore_all_section_styles_btn.toolTip()
        assert scope._style_override_summary.value_for("override_status") == (
            "无格式例外"
        )
        assert scope._style_owner_status.property("style_owner_scope_status") == (
            "来自模板"
        )

        scope._undo_restore_all_section_styles_btn.click()
        app.processEvents()

        assert changed == [True, True]
        assert scene.section_styles["references_body"].font_cn == "黑体"
        assert scene.section_styles["appendix_body"].font_cn == "仿宋"
        assert references_toggle.isChecked() is True
        assert appendix_toggle.isChecked() is True
        assert scope._restore_all_section_styles_btn.isEnabled() is True
        assert scope._undo_restore_all_section_styles_btn.isEnabled() is False
        assert scope._style_override_summary.value_for("override_status") == (
            "1 个格式例外"
        )
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_template_change_skips_removed_page_number_detail():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(
        scene_id="thesis",
        template_id="thesis_gbt",
        default_template_id="thesis_gbt",
        compatible_template_ids=["thesis_gbt"],
    )
    template = create_builtin_template("thesis_gbt")
    bridge.set_current_scene(scene, config_id="thesis", emit_signal=False)
    bridge.set_current_template(template, config_id="thesis_gbt", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        updated_template = create_builtin_template("thesis_gbt")
        updated_template.header_footer.page_number_enabled = False
        bridge.set_current_template(updated_template, config_id="thesis_gbt")
        app.processEvents()

        assert hasattr(panel, "_page_elem") is False
        assert "scn_page_elem" not in panel._detail_map
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_profile_summaries_reflect_current_scene():
    app = _app()
    bridge = PanelBridge()
    scene = create_bidding_scene()
    template = create_builtin_template("bid_engineering")
    bridge.set_current_scene(scene, config_id="bidding", emit_signal=False)
    bridge.set_current_template(template, config_id="bid_engineering", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        assert panel._overview._profile_summary.value_for("input_profile") == "Word 文档 / Excel 表格"
        assert panel._overview._profile_summary.value_for("parameter_ownership") == "归属清楚"
        ownership_detail = panel._overview._profile_summary.detail_for(
            "parameter_ownership"
        )
        assert "模板管样式" in ownership_detail
        assert "场景管流程" in ownership_detail
        assert "资料管输入" in ownership_detail
        assert "输出管版本" in ownership_detail
        assert panel._overview._profile_summary.value_for("parameter_boundary") == (
            "按字段应用"
        )
        parameter_boundary_detail = panel._overview._profile_summary.detail_for(
            "parameter_boundary"
        )
        assert "固定行高" in parameter_boundary_detail
        assert "固定版式" in parameter_boundary_detail
        assert "待裁决" not in parameter_boundary_detail
        assert panel._overview._profile_summary.value_for("control_contract") == "已统一"
        control_contract_detail = panel._overview._profile_summary.detail_for(
            "control_contract"
        )
        assert "缩进" in control_contract_detail
        assert "固定版式行高" in control_contract_detail
        assert "特殊缩进" not in control_contract_detail
        assert panel._overview._profile_summary.value_for("control_contract_scope") == (
            "16 类控件"
        )
        assert panel._overview._profile_summary.value_for("bidding_archive_evidence") == (
            "已打通"
        )
        bidding_detail = panel._overview._profile_summary.detail_for(
            "bidding_archive_evidence"
        )
        assert "标书资料" in bidding_detail
        assert "资质归档资料" in bidding_detail
        bidding_tooltip = panel._overview._profile_summary.tooltip_for(
            "bidding_archive_evidence"
        )
        assert "bid_materials_v1" in bidding_tooltip
        assert "qualification_archive_assets_v1" in bidding_tooltip
        assert "seal_position_residue_report" in bidding_tooltip
        assert "bidding_materials_consortium_seal_residue_degraded" in bidding_tooltip
        assert panel._content._input_summary.value_for("materials") == "必需"
        material_detail = panel._content._input_summary.detail_for("materials")
        assert "标书资料" in material_detail
        assert "bid_materials_v1" not in material_detail
        input_projection = {
            item.key: item for item in build_input_profile_summary_items(scene)
        }
        assert "bid_materials_v1" in input_projection["materials"].tooltip
        assert panel._content._input_summary.value_for("material_fields") == "3 个字段"
        assert "公司名称" in panel._content._input_summary.detail_for("material_fields")
        assert panel._content._input_summary.value_for("image_roles") == "2 个角色"
        assert "印章" in panel._content._input_summary.detail_for("image_roles")
        assert panel._cleanup._compliance_summary.value_for("object_policy") == "启用"
        assert "严格" in panel._cleanup._compliance_summary.detail_for("object_policy")
        assert panel._cleanup._compliance_summary.value_for("scan_targets") == "11 个目标"
        assert "content_controls" in panel._cleanup._compliance_summary.detail_for("scan_targets")
        assert "hidden_text" in panel._cleanup._compliance_summary.detail_for("scan_targets")
        assert panel._output._delivery_summary.value_for("preset_count") == "3 个输出版本"
    finally:
        panel.close()
        app.processEvents()


def test_scene_overview_summary_projects_planning_family_governance():
    scene = SceneWorkspace(scene_id="contract_delivery")
    scene.input_source_profile.material_schema_id = "contract_parties_v1"

    items = {item.key: item for item in build_scene_overview_summary_items(scene)}

    assert items["planning_family"].value == "合同交付"
    assert "P1" in items["planning_family"].detail
    assert "核对字段一致性" in items["planning_workflows"].detail
    assert "修订保护" in items["planning_first_slice"].detail
    assert "批注" in items["planning_ooxml"].detail
    assert "修订" in items["planning_ooxml"].detail
    assert "revision" in items["planning_ooxml"].tooltip


def test_scene_overview_summary_projects_parameter_ownership_registry():
    scene = SceneWorkspace(scene_id="contract_delivery")
    items = {item.key: item for item in build_scene_overview_summary_items(scene)}
    ownership_items = {
        item.key: item for item in build_parameter_ownership_summary_items(scene)
    }

    assert ownership_items["parameter_ownership"].value == "归属清楚"
    assert items["parameter_ownership"].value == "归属清楚"
    assert "模板管样式" in items["parameter_ownership"].detail
    assert "场景管流程" in items["parameter_ownership"].detail
    assert "资料管输入" in items["parameter_ownership"].detail
    assert "输出管版本" in items["parameter_ownership"].detail
    assert "13" not in items["parameter_ownership"].detail
    assert "37" not in items["parameter_ownership"].detail
    assert "归属计数" in items["parameter_ownership"].tooltip
    assert "SceneWorkspace" in items["parameter_ownership"].tooltip
    assert items["parameter_boundary"].value == "按字段应用"
    assert "固定行高" in items["parameter_boundary"].detail
    assert "固定版式" in items["parameter_boundary"].detail
    assert "待裁决" not in items["parameter_boundary"].detail


def test_scene_overview_summary_projects_control_contract_registry():
    scene = SceneWorkspace(scene_id="contract_delivery")
    items = {item.key: item for item in build_scene_overview_summary_items(scene)}
    control_items = {
        item.key: item for item in build_control_contract_summary_items()
    }

    assert control_items["control_contract"].value == "已统一"
    assert items["control_contract"].value == "已统一"
    assert items["control_contract"].detail == (
        "缩进、段落间距、固定版式行高、公式、水印等已归一"
    )
    assert "左缩进" in items["control_contract"].tooltip
    assert "右缩进" in items["control_contract"].tooltip
    assert "特殊缩进" in items["control_contract"].tooltip
    assert "段前" in items["control_contract"].tooltip
    assert "段后" in items["control_contract"].tooltip
    assert "固定版位行高" in items["control_contract"].tooltip
    assert "公式策略" in items["control_contract"].tooltip
    assert "水印状态" in items["control_contract"].tooltip
    assert "资料规则" in items["control_contract"].tooltip
    assert "输出版本" in items["control_contract"].tooltip
    assert "内容显隐" in items["control_contract"].tooltip
    assert "插件人工确认" in items["control_contract"].tooltip
    assert items["control_contract_scope"].value == "16 类控件"
    assert items["control_contract_scope"].detail == "5 类控件归属已分开"
    assert "模板管样式 9" in items["control_contract_scope"].tooltip
    assert "场景管流程 3" in items["control_contract_scope"].tooltip
    assert "资料管输入 1" in items["control_contract_scope"].tooltip
    assert "输出管版本 2" in items["control_contract_scope"].tooltip
    assert "插件管人工确认 1" in items["control_contract_scope"].tooltip
    assert "同名格式参数" in items["control_contract_scope"].tooltip


def test_scene_panel_content_watermark_controls_write_scene_contracts():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="technical")
    bridge.set_current_scene(scene, config_id="technical", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        assert not hasattr(panel, "_formula")

        panel._content._watermark_enabled.setChecked(True)
        panel._content._watermark_text.setText("征求意见")
        panel._content._on_edited()

        assert scene.watermark.enabled is True
        assert scene.watermark.text == "征求意见"
        assert panel._content._watermark_text.isEnabled() is True

        panel._content._watermark_enabled.setChecked(False)
        panel._content._on_edited()

        assert scene.watermark.enabled is False
        assert scene.watermark.text == "征求意见"
        assert panel._content._watermark_text.isEnabled() is False
    finally:
        panel.close()
        app.processEvents()


def test_scene_overview_summary_omits_completed_coverage_closure_tasks():
    scene = SceneWorkspace(scene_id="contract_delivery")
    scene.input_source_profile.material_schema_id = "contract_parties_v1"

    items = {item.key: item for item in build_scene_overview_summary_items(scene)}
    coverage_items = {item.key: item for item in build_coverage_summary_items(scene)}

    assert coverage_items["coverage_pack"].value == "合同交付"
    assert "不提供法律意见" in coverage_items["coverage_pack"].detail
    assert items["coverage_pack"].value == "合同交付"
    assert "coverage_next_closure" not in items


def test_scene_overview_summary_projects_sample_fixture_coverage():
    scene = SceneWorkspace(scene_id="contract_delivery", category="contract_delivery")
    sample_items = {
        item.key: item for item in build_scene_sample_fixture_summary_items(scene)
    }
    request_items = {
        item.key: item for item in build_scene_request_cell_summary_items(scene)
    }
    overview = {item.key: item for item in build_scene_overview_summary_items(scene)}
    detail_text = build_scene_sample_fixture_detail_text(scene)
    request_cell_specs = scene_request_cell_fixture_specs_for_scene(scene)

    assert sample_items["sample_fixture_coverage"].value == "已有样本文档"
    assert "2 个样本" in sample_items["sample_fixture_coverage"].detail
    assert "修订" in sample_items["sample_fixture_coverage"].tooltip
    assert "scene_sample_fixture_registry" not in sample_items["sample_fixture_coverage"].tooltip
    assert "覆盖 pack" not in sample_items["sample_fixture_coverage"].tooltip
    assert overview["sample_fixture_coverage"].value == "已有样本文档"
    assert overview["sample_fixture_boundary"].value == "有边界说明"
    assert "法律审查" in overview["sample_fixture_boundary"].detail
    assert request_items["request_cell_coverage"].value == "常见说法已覆盖"
    assert "4 个请求" in request_items["request_cell_coverage"].detail
    assert "0 个借用样本" in request_items["request_cell_coverage"].detail
    assert "常见说法登记：高频用户说法" in request_items["request_cell_coverage"].tooltip
    assert "scene_request_cell_fixture_registry" not in request_items["request_cell_coverage"].tooltip
    assert "fixture-backed" not in request_items["request_cell_coverage"].tooltip
    assert overview["request_cell_coverage"].value == "常见说法已覆盖"
    assert "4 个请求" in overview["request_cell_coverage"].detail
    assert "资料包：合同交付" in detail_text
    assert "合同交付样本 1" in detail_text
    assert "常见说法：" in detail_text
    assert "样本：contract_delivery_revisions" not in detail_text
    assert "样本：contract_signing_consistency" not in detail_text
    assert "contract_delivery_revisions" not in detail_text
    assert "contract_signing_consistency" not in detail_text
    assert "用户说法：合同签署包字段一致性" in detail_text
    assert "覆盖方式：直接证据" in detail_text
    assert "证据样本：1 个" in detail_text
    assert "request-cells:" not in detail_text
    assert "fixture=" not in detail_text
    assert "cell=" not in detail_text
    assert "level=" not in detail_text
    assert {cell.sample_id for cell in request_cell_specs} == {
        "contract_signing_consistency",
        "contract_review_revisions",
        "contract_signature_package_fields",
        "ambiguous_contract_legal_review",
    }
    assert {cell.coverage_level for cell in request_cell_specs} == {
        "direct_family_fixture",
        "ambiguous_fixture_set",
    }
    assert (
        "Word 对象：正文片段 / 域 / 批注 / 修订 / 隐藏文字 / 嵌入附件"
    ) in (
        detail_text
    )
    assert "边界：合同样本只验证格式和字段，不代表法律审查" in detail_text


def test_scene_overview_summary_projects_contract_green_with_field_evidence():
    scene = SceneWorkspace(scene_id="contract_delivery", category="contract_delivery")

    readiness_items = {
        item.key: item for item in build_product_readiness_summary_items(scene)
    }
    field_items = {
        item.key: item for item in build_contract_field_evidence_summary_items(scene)
    }
    overview = {item.key: item for item in build_scene_overview_summary_items(scene)}

    assert readiness_items["product_readiness"].value == "可直接使用"
    assert readiness_items["product_readiness_family"].value == "可直接使用"
    assert "product_readiness_gaps" not in readiness_items
    assert field_items["contract_field_evidence"].value == "已打通"
    assert "合同方字段资料" in field_items["contract_field_evidence"].detail
    assert "字段一致性报告" in field_items["contract_field_evidence"].detail
    assert "contract_parties_v1" in field_items["contract_field_evidence"].tooltip
    assert "contract_field_consistency_report" in (
        field_items["contract_field_evidence"].tooltip
    )
    assert "contract_delivery_signature_fields_degraded" in (
        field_items["contract_field_evidence"].tooltip
    )
    assert overview["product_readiness"].value == "可直接使用"
    assert "product_readiness_gaps" not in overview
    assert overview["contract_field_evidence"].value == "已打通"


def test_scene_overview_summary_projects_plugin_boundary_for_exam_family():
    scene = SceneWorkspace(scene_id="exam_teaching")
    scene.category = "exam_teaching"

    items = {item.key: item for item in build_scene_overview_summary_items(scene)}

    assert items["coverage_pack"].value == "试卷/教学资料"
    assert "coverage_next_closure" not in items
    assert items["coverage_plugin_boundary"].value == "1 项需确认"
    assert "AI 内容质量" in items["coverage_plugin_boundary"].detail


def test_scene_family_application_uses_shared_content_visibility_rule_labels():
    scene = SceneWorkspace(scene_id="exam_teaching", category="exam_teaching")

    result = apply_planned_scene_family_defaults(scene)

    assert result.applied is True
    student_version = next(
        preset
        for preset in scene.delivery_presets
        if preset.preset_id == "student_version"
    )
    assert student_version.label == "学生版"
    assert [
        (rule.selector, rule.label, rule.action)
        for rule in student_version.content_visibility_rules
    ] == [
        ("answer", "答案", "remove"),
        ("analysis", "解析", "remove"),
        ("solution", "解题过程", "remove"),
        ("teacher_note", "教师备注", "remove"),
        ("knowledge_points", "知识点", "remove"),
    ]

    answer_sheet = next(
        preset for preset in scene.delivery_presets if preset.preset_id == "answer_sheet"
    )
    assert answer_sheet.label == "答题卡"
    assert [
        rule.label for rule in answer_sheet.content_visibility_rules
    ] == [
        "答案",
        "解析",
        "解题过程",
        "教师备注",
        "知识点",
        "题干正文",
    ]
    assert all(":" not in rule.label for rule in answer_sheet.content_visibility_rules)


def test_scene_panel_family_delivery_combo_uses_shared_display_labels():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(
        scene_id="exam_teaching",
        name="试卷/教学资料",
        category="exam_teaching",
        template_id="default",
        default_template_id="default",
        compatible_template_ids=["default"],
    )
    template = create_builtin_template("default")
    bridge.set_current_scene(scene, config_id="exam_teaching", emit_signal=False)
    bridge.set_current_template(template, config_id="default", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        family_delivery_tooltip = panel._output._apply_family_delivery_btn.toolTip()
        assert "将新增：学生版、教师版、答案速查等 5 个" in family_delivery_tooltip
        assert "Student version" not in family_delivery_tooltip

        panel._output._apply_family_delivery_btn.click()
        app.processEvents()

        student_index = panel._output._default_delivery.findData("student_version")
        answer_index = panel._output._default_delivery.findData("answer_key")
        assert student_index >= 0
        assert answer_index >= 0
        assert panel._output._default_delivery.itemText(student_index) == "学生版"
        assert panel._output._default_delivery.itemText(answer_index) == "答案速查"
        assert panel._output._delivery_label.text() == "学生版"
        assert "Student version" not in panel._output._delivery_label.text()
        student_preset = next(
            preset
            for preset in scene.delivery_presets
            if preset.preset_id == "student_version"
        )
        assert student_preset.label == "学生版"
    finally:
        panel.close()
        app.processEvents()


def test_scene_overview_summary_projects_official_archive_profile_defaults():
    scene = create_official_scene()
    apply_planned_scene_family_defaults(scene)

    overview = {item.key: item for item in build_scene_overview_summary_items(scene)}
    compliance = {item.key: item for item in build_compliance_summary_items(scene)}
    delivery = {item.key: item for item in build_delivery_summary_items(scene)}

    assert overview["planning_family"].value == "公文/会议材料"
    assert "正式归档交付" in overview["planning_workflows"].detail
    assert "归档信息" in overview["planning_first_slice"].detail
    assert "公文/会议纪要" in overview["coverage_pack"].detail
    assert "coverage_next_closure" not in overview
    assert overview["official_policy_evidence"].label == "公文元数据证据"
    assert overview["official_policy_evidence"].value == "已打通"
    assert "公文字段资料" in overview["official_policy_evidence"].detail
    assert "报告 4 项" in overview["official_policy_evidence"].detail
    assert "official_metadata_report" in overview["official_policy_evidence"].tooltip
    assert "formal_internal_archive_manifest" in (
        overview["official_policy_evidence"].tooltip
    )
    assert "official_policy_metadata_archive_report" in (
        overview["official_policy_evidence"].tooltip
    )
    assert "Official metadata evidence" not in overview["official_policy_evidence"].label
    assert "ready" not in overview["official_policy_evidence"].value
    assert overview["product_readiness"].value == "可直接使用"
    assert "product_readiness_gaps" not in overview
    assert delivery["default_delivery"].value == "正式纪要"
    assert delivery["default_delivery"].detail == "执行时默认生成"
    assert "formal_minutes" in delivery["default_delivery"].tooltip
    assert "资料清单" in delivery["default_artifacts"].value
    assert "政策资料归档" in delivery["preset_count"].detail
    assert "归档清单" in delivery["preset_count"].detail
    assert "policy_collection" in delivery["preset_count"].tooltip
    assert "archive_manifest" in delivery["preset_count"].tooltip
    assert compliance["count_profile"].value == "administrative_sections"
    assert "Administrative section" in compliance["count_profile"].detail
    assert compliance["planning_scan_targets"].value in {"已应用", "已覆盖"}


def test_scene_overview_summary_projects_academic_rule_source_evidence():
    scene = create_thesis_scene()
    apply_planned_scene_family_defaults(scene)

    evidence = {
        item.key: item
        for item in build_academic_rule_source_evidence_summary_items(scene)
    }
    overview = {item.key: item for item in build_scene_overview_summary_items(scene)}

    assert overview["planning_family"].value == "中文论文/课程论文"
    assert "中文论文/课程论文" in overview["coverage_pack"].detail
    assert evidence["academic_rule_source_evidence"].label == "学术规则证据"
    assert evidence["academic_rule_source_evidence"].value == "已打通"
    assert "学校论文规则资料" in evidence["academic_rule_source_evidence"].detail
    assert "thesis_school_rule_context_v1" in evidence["academic_rule_source_evidence"].tooltip
    assert "school_rule_source_selection" in (
        evidence["academic_rule_source_evidence"].tooltip
    )
    assert "section_classifier_confirmation" in (
        evidence["academic_rule_source_evidence"].tooltip
    )
    assert "chinese_academic_school_rule_section_confirmation" in (
        evidence["academic_rule_source_evidence"].tooltip
    )
    assert overview["academic_rule_source_evidence"].value == "已打通"
    assert "Academic rule evidence" not in evidence["academic_rule_source_evidence"].label
    assert overview["product_readiness"].value == "可直接使用"
    assert "product_readiness_gaps" not in overview


def test_scene_overview_summary_projects_journal_submission_evidence():
    scene = SceneWorkspace(scene_id="journal_en", category="journal_en")
    apply_planned_scene_family_defaults(scene)

    evidence = {
        item.key: item
        for item in build_journal_submission_evidence_summary_items(scene)
    }
    overview = {item.key: item for item in build_scene_overview_summary_items(scene)}
    input_items = {item.key: item for item in build_input_profile_summary_items(scene)}

    assert overview["planning_family"].value == "英文期刊投稿"
    assert overview["coverage_pack"].value == "英文期刊投稿"
    assert evidence["journal_submission_evidence"].label == "期刊投稿证据"
    assert evidence["journal_submission_evidence"].value == "已打通"
    assert "期刊投稿资料" in evidence["journal_submission_evidence"].detail
    assert "期刊资料" in evidence["journal_submission_evidence"].detail
    assert "journal_submission_materials_v1" in evidence["journal_submission_evidence"].tooltip
    assert "journal_materials_v1" in evidence["journal_submission_evidence"].tooltip
    assert "journal_submission_reviewed_generic_rules" in (
        evidence["journal_submission_evidence"].tooltip
    )
    assert "reviewed_journal_profile_update" in (
        evidence["journal_submission_evidence"].tooltip
    )
    assert "submission_artifact_manifest" in (
        evidence["journal_submission_evidence"].tooltip
    )
    assert "english_journal_bibtex_csl_degraded" in (
        evidence["journal_submission_evidence"].tooltip
    )
    assert overview["journal_submission_evidence"].value == "已打通"
    assert "Journal submission evidence" not in evidence["journal_submission_evidence"].label
    assert overview["product_readiness"].value == "可直接使用"
    assert "product_readiness_gaps" not in overview
    assert input_items["materials"].detail == "期刊投稿资料"
    assert "journal_submission_materials_v1" in input_items["materials"].tooltip


def test_scene_overview_summary_projects_technical_long_doc_evidence():
    scene = create_technical_scene()
    apply_planned_scene_family_defaults(scene)

    overview = {item.key: item for item in build_scene_overview_summary_items(scene)}

    assert overview["planning_family"].value == "技术长文档"
    assert "技术长文档" in overview["coverage_pack"].detail
    assert overview["technical_long_doc_evidence"].label == "技术长文档证据"
    assert overview["technical_long_doc_evidence"].value == "已打通"
    assert "技术文档资料" in overview["technical_long_doc_evidence"].detail
    assert "长文档元数据" in overview["technical_long_doc_evidence"].detail
    assert "technical_document_v1" in overview["technical_long_doc_evidence"].tooltip
    assert "long_document_metadata_v1" in overview["technical_long_doc_evidence"].tooltip
    assert "index_appendix_inventory" in overview["technical_long_doc_evidence"].tooltip
    assert "multi_file_merge_boundary_report" in (
        overview["technical_long_doc_evidence"].tooltip
    )
    assert "technical_long_docs_index_appendix_merge_boundary" in (
        overview["technical_long_doc_evidence"].tooltip
    )
    assert "Technical long-doc evidence" not in overview["technical_long_doc_evidence"].label
    assert overview["product_readiness"].value == "可直接使用"
    assert "product_readiness_gaps" not in overview


def test_scene_overview_summary_projects_fixed_layout_batch_evidence():
    scene = SceneWorkspace(
        scene_id="form_batch_documents",
        category="form_batch_documents",
    )
    apply_planned_scene_family_defaults(scene)

    evidence = {
        item.key: item
        for item in build_fixed_layout_batch_evidence_summary_items(scene)
    }
    overview = {item.key: item for item in build_scene_overview_summary_items(scene)}
    input_items = {item.key: item for item in build_input_profile_summary_items(scene)}

    assert overview["planning_family"].value == "批量表单/套打"
    assert overview["coverage_pack"].value == "批量表单/套打"
    assert evidence["fixed_layout_batch_evidence"].label == "固定版式批量证据"
    assert evidence["fixed_layout_batch_evidence"].value == "已打通"
    assert "表单字段资料" in evidence["fixed_layout_batch_evidence"].detail
    assert "人员记录资料" in evidence["fixed_layout_batch_evidence"].detail
    assert "form_batch_fields_v1" in evidence["fixed_layout_batch_evidence"].tooltip
    assert "personnel_records_v1" in evidence["fixed_layout_batch_evidence"].tooltip
    assert "fixed_layout_profile_browser" in (
        evidence["fixed_layout_batch_evidence"].tooltip
    )
    assert "answer_sheet_reuse_path" in evidence["fixed_layout_batch_evidence"].tooltip
    assert "batch_forms_fixed_layout" in evidence["fixed_layout_batch_evidence"].tooltip
    assert "通道：12/12" in evidence["fixed_layout_batch_evidence"].detail
    assert "channels=" not in evidence["fixed_layout_batch_evidence"].detail
    assert overview["fixed_layout_batch_evidence"].value == "已打通"
    assert "Fixed-layout batch evidence" not in evidence["fixed_layout_batch_evidence"].label
    assert overview["product_readiness"].value == "可直接使用"
    assert "product_readiness_gaps" not in overview
    assert input_items["materials"].detail == "表单字段资料"
    assert "form_batch_fields_v1" in input_items["materials"].tooltip


def test_scene_overview_summary_projects_product_sales_package_defaults():
    scene = SceneWorkspace(
        scene_id="product_sales_documents",
        category="product_sales_documents",
    )
    apply_planned_scene_family_defaults(scene)

    overview = {item.key: item for item in build_scene_overview_summary_items(scene)}
    input_items = {item.key: item for item in build_input_profile_summary_items(scene)}
    compliance = {item.key: item for item in build_compliance_summary_items(scene)}
    delivery = {item.key: item for item in build_delivery_summary_items(scene)}

    assert overview["planning_family"].value == "产品/售前材料"
    assert "客户/内部版本交付" in overview["planning_workflows"].detail
    assert overview["coverage_pack"].value == "项目申报/产品材料"
    assert "coverage_next_closure" not in overview
    assert input_items["materials"].value == "必需"
    assert "产品资料" in input_items["materials"].detail
    assert "案例资料" in input_items["materials"].detail
    assert "product_assets_v1" in input_items["materials"].tooltip
    assert "case_study_assets_v1" in input_items["materials"].tooltip
    assert "产品图片" in input_items["image_roles"].detail
    assert compliance["count_profile"].value == "product_asset_inventory"
    assert "Product and pre-sales asset" in compliance["count_profile"].detail
    assert compliance["planning_scan_targets"].value in {"已应用", "已覆盖"}
    assert delivery["default_delivery"].value == "客户版"
    assert "customer_copy" in delivery["default_delivery"].tooltip
    assert "售前资料包" in delivery["preset_count"].detail
    assert "pre_sales_package" in delivery["preset_count"].tooltip
    assert "资料清单" in delivery["default_artifacts"].value


def test_scene_overview_summary_projects_application_report_evidence():
    scene = SceneWorkspace(
        scene_id="product_sales_documents",
        category="product_sales_documents",
    )
    apply_planned_scene_family_defaults(scene)

    evidence = {
        item.key: item
        for item in build_application_report_evidence_summary_items(scene)
    }
    overview = {item.key: item for item in build_scene_overview_summary_items(scene)}
    input_items = {item.key: item for item in build_input_profile_summary_items(scene)}

    assert overview["coverage_pack"].value == "项目申报/产品材料"
    assert evidence["application_report_evidence"].label == "申报/材料证据"
    assert evidence["application_report_evidence"].value == "已打通"
    assert "项目申报资料" in evidence["application_report_evidence"].detail
    assert "产品资料" in evidence["application_report_evidence"].detail
    assert "案例资料" in evidence["application_report_evidence"].detail
    assert "project_application_materials_v1" in (
        evidence["application_report_evidence"].tooltip
    )
    assert "product_assets_v1" in evidence["application_report_evidence"].tooltip
    assert "case_study_assets_v1" in evidence["application_report_evidence"].tooltip
    assert "project_application_rule_defaults" in (
        evidence["application_report_evidence"].tooltip
    )
    assert "submission_system_boundary_report" in (
        evidence["application_report_evidence"].tooltip
    )
    assert "asset_consistency_report" in (
        evidence["application_report_evidence"].tooltip
    )
    assert "quote_body_disambiguation" in (
        evidence["application_report_evidence"].tooltip
    )
    assert "application_reports_product_sales_assets" in (
        evidence["application_report_evidence"].tooltip
    )
    assert overview["application_report_evidence"].value == "已打通"
    assert "Application/report evidence" not in evidence["application_report_evidence"].label
    assert overview["product_readiness"].value == "可直接使用"
    assert "product_readiness_gaps" not in overview
    assert "产品资料" in input_items["materials"].detail
    assert "product_assets_v1" in input_items["materials"].tooltip


def test_scene_overview_summary_projects_regulated_disclosure_archive_defaults():
    scene = SceneWorkspace(
        scene_id="regulated_disclosure_documents",
        category="regulated_disclosure_documents",
    )
    apply_planned_scene_family_defaults(scene)

    overview = {item.key: item for item in build_scene_overview_summary_items(scene)}
    input_items = {item.key: item for item in build_input_profile_summary_items(scene)}
    compliance = {item.key: item for item in build_compliance_summary_items(scene)}
    delivery = {item.key: item for item in build_delivery_summary_items(scene)}

    assert overview["planning_family"].value == "披露/审阅材料"
    assert "归档打包" in overview["planning_workflows"].detail
    assert overview["coverage_pack"].value == "专业披露/审阅"
    assert "coverage_next_closure" not in overview
    assert input_items["materials"].value == "必需"
    assert input_items["materials"].detail == "披露材料资料"
    assert "regulated_disclosure_materials_v1" in input_items["materials"].tooltip
    assert compliance["count_profile"].value == "disclosure_section_inventory"
    assert "Regulated disclosure section" in compliance["count_profile"].detail
    assert compliance["planning_scan_targets"].value in {"已应用", "已覆盖"}
    assert "hidden_text" in compliance["planning_scan_targets"].detail
    assert delivery["default_delivery"].value == "董事会审阅稿"
    assert "board_review_copy" in delivery["default_delivery"].tooltip
    assert "披露归档包" in delivery["preset_count"].detail
    assert "归档清单" in delivery["preset_count"].detail
    assert "disclosure_archive_package" in delivery["preset_count"].tooltip
    assert "archive_manifest" in delivery["preset_count"].tooltip
    assert "资料清单" in delivery["default_artifacts"].value


def test_scene_overview_summary_projects_n2128_family_application_parity_defaults():
    cases = (
        (
            "hr_batch_documents",
            "batch_forms",
            "personnel_records_v1",
            "batch_item_inventory",
            "per_person_docx",
            "failed_items_report",
            "content_controls",
        ),
        (
            "form_batch_documents",
            "batch_forms",
            "form_batch_fields_v1",
            "batch_item_inventory",
            "per_record_docx",
            "residue_check_report",
            "textboxes",
        ),
        (
            "finance_quote_documents",
            "professional_disclosure",
            "finance_quote_fields_v1",
            "finance_attachment_inventory",
            "customer_quote",
            "attachment_report",
            "embedded_workbooks",
        ),
        (
            "bilingual_translation_documents",
            "professional_disclosure",
            "bilingual_terms_v1",
            "bilingual_parallel_text",
            "bilingual_review_copy",
            "term_consistency_report",
            "tracked_changes",
        ),
    )

    for (
        family_id,
        coverage_pack,
        schema_id,
        count_profile_id,
        default_preset_id,
        extra_preset_id,
        scan_target,
    ) in cases:
        scene = SceneWorkspace(scene_id=family_id, category=family_id)
        apply_planned_scene_family_defaults(scene)

        overview = {item.key: item for item in build_scene_overview_summary_items(scene)}
        input_items = {item.key: item for item in build_input_profile_summary_items(scene)}
        compliance = {item.key: item for item in build_compliance_summary_items(scene)}
        delivery = {item.key: item for item in build_delivery_summary_items(scene)}

        family_labels = {
            "hr_batch_documents": "人事批量文档",
            "form_batch_documents": "批量表单/套打",
            "finance_quote_documents": "报价/财务材料",
            "bilingual_translation_documents": "双语审阅材料",
        }
        coverage_labels = {
            "batch_forms": "批量表单/套打",
            "professional_disclosure": "专业披露/审阅",
        }
        schema_labels = {
            "personnel_records_v1": "人员记录资料",
            "form_batch_fields_v1": "表单字段资料",
            "finance_quote_fields_v1": "报价字段资料",
            "bilingual_terms_v1": "双语术语资料",
        }
        delivery_labels = {
            "per_person_docx": "按人员生成",
            "per_record_docx": "按记录生成",
            "customer_quote": "客户报价稿",
            "bilingual_review_copy": "双语审阅稿",
            "failed_items_report": "失败项报告",
            "residue_check_report": "残留检查报告",
            "attachment_report": "附件报告",
            "term_consistency_report": "术语一致性报告",
        }
        assert overview["planning_family"].value == family_labels[family_id]
        assert overview["coverage_pack"].value == coverage_labels[coverage_pack]
        assert "coverage_next_closure" not in overview
        assert input_items["materials"].value == "必需"
        assert schema_labels[schema_id] in input_items["materials"].detail
        assert schema_id in input_items["materials"].tooltip
        assert compliance["count_profile"].value == count_profile_id
        assert compliance["planning_scan_targets"].value in {"已应用", "已覆盖"}
        assert scan_target in compliance["planning_scan_targets"].detail
        assert delivery["default_delivery"].value == delivery_labels[default_preset_id]
        assert default_preset_id in delivery["default_delivery"].tooltip
        assert delivery_labels[extra_preset_id] in delivery["preset_count"].detail
        assert extra_preset_id in delivery["preset_count"].tooltip


def test_scene_overview_summary_keeps_ip_patent_as_plugin_manual_boundary():
    scene = SceneWorkspace(
        scene_id="ip_patent_documents",
        category="ip_patent_documents",
    )
    result = apply_planned_scene_family_defaults(scene)

    overview = {item.key: item for item in build_scene_overview_summary_items(scene)}

    assert result.applied is False
    assert overview["planning_family"].value == "知识产权/专利材料"
    assert overview["coverage_pack"].value == "专业披露/审阅"
    assert overview["coverage_plugin_boundary"].value == "1 项需确认"
    assert "审计、法律、专利" in overview["coverage_plugin_boundary"].detail
    assert overview["product_readiness"].value == "需人工/插件把关"
    assert overview["product_readiness_family"].value == "需人工/插件把关"
    assert "知识产权/专利插件" in overview["product_readiness_gaps"].detail


def test_scene_compliance_summary_recommends_planning_family_scan_targets():
    scene = SceneWorkspace(scene_id="contract_delivery")
    scene.input_source_profile.material_schema_id = "contract_parties_v1"
    scene.compliance_profile.object_preflight.scan_targets = ["fields"]

    recommended = recommended_object_preflight_targets_for_scene(scene)
    items = {item.key: item for item in build_compliance_summary_items(scene)}

    assert "tracked_changes" in recommended
    assert "ole_objects" in recommended
    assert items["planning_scan_targets"].value == "需同步"
    assert "tracked_changes" in items["planning_scan_targets"].detail

    scene.compliance_profile.object_preflight.scan_targets = list(recommended)
    items = {item.key: item for item in build_compliance_summary_items(scene)}

    assert items["planning_scan_targets"].value == "已应用"


def test_scene_panel_overview_shows_planning_family_governance(tmp_path):
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(
        scene_id="contract_delivery",
        name="合同交付",
        description="字段一致性、审阅稿和签署稿规划族。",
        category="contract_delivery",
        template_id="default",
        default_template_id="default",
        compatible_template_ids=["default"],
    )
    scene.input_source_profile.material_schema_id = "contract_parties_v1"
    template = create_builtin_template("default")
    bridge.set_current_scene(scene, config_id="contract_delivery", emit_signal=False)
    bridge.set_current_template(template, config_id="default", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        overview_layout = panel._overview.layout()
        assert overview_layout.indexOf(panel._overview._scene_card) < overview_layout.indexOf(
            panel._overview._settings_card
        )
        assert overview_layout.indexOf(panel._overview._settings_card) < overview_layout.indexOf(
            panel._overview._run_preview_card
        )
        assert panel._overview._combo.property("fullWidthMode") is True
        assert panel._overview._new_scene_btn.text() == "新建场景"
        assert panel._overview._duplicate_scene_btn.text() == "创建副本"
        assert panel._overview._open_scene_folder_btn.text() == "打开场景文件夹"
        assert panel._overview._rename_scene_btn.isEnabled() is False
        assert panel._overview._delete_scene_btn.isEnabled() is False
        assert panel._overview._execute_btn.parent() is not panel._overview._scene_card
        assert panel._overview._task_title.isHidden()
        assert panel._overview._task_meta.isHidden()
        assert panel._overview._task_title.text() == "合同交付"
        assert "模板：默认格式" in panel._overview._task_meta.text()
        assert "读取文件" in panel._overview._run_steps_label.text()
        assert "检查风险" in panel._overview._run_steps_label.text()
        assert "统一主要样式" in panel._overview._run_steps_label.text()
        assert "统一页面、正文、标题、表格和页眉页脚" not in (
            panel._overview._run_steps_label.text()
        )
        assert panel._overview._summary.isHidden()
        assert "按模板默认" in panel._overview._summary.text()
        assert "/" not in panel._overview._summary.text()
        assert panel._overview._run_steps_label.isHidden()
        run_step_texts = [
            row.step_text()
            for row in panel._overview._run_step_rows
            if not row.isHidden()
        ]
        assert len(run_step_texts) == 5
        assert any("读取文件" in text for text in run_step_texts)
        assert any("检查风险" in text for text in run_step_texts)
        assert any("统一主要样式" in text for text in run_step_texts)
        assert all("\n" not in text for text in run_step_texts)
        assert "materials" in panel._overview._setting_rows
        assert "已开启" in panel._overview._setting_rows[
            "materials"
        ].summary_text()
        template_preview = build_template_preview_context(template)
        style_source_row = panel._overview._setting_rows["style_source"]
        assert style_source_row._label.text() == "套用模板"
        assert style_source_row.summary_text() == "使用默认格式，无格式例外"
        assert template_preview.action == "核对页面、正文、标题、表格、页眉页脚、目录和题注"
        assert style_source_row._status.text() == "同源预览"
        assert style_source_row._jump_btn.text() == "设置"
        assert style_source_row._secondary_jump_btn.isHidden()
        assert "编号：" not in style_source_row.summary_text()
        assert "risk_confirmation" not in panel._overview._setting_rows
        assert "manual_confirmation" not in panel._overview._setting_rows
        first_screen_text = "\n".join(
            [
                panel._overview._task_title.text(),
                panel._overview._task_meta.text(),
                panel._overview._task_suitable.text(),
                panel._overview._task_boundary.text(),
                panel._overview._run_steps_label.text(),
                *(
                    row.summary_text()
                    for row in panel._overview._setting_rows.values()
                    if not row.isHidden()
                ),
            ]
        ).lower()
        assert not [
            term for term in FIRST_SCREEN_BANNED_TERMS
            if term.lower() in first_screen_text
        ]
        assert "scn_evidence" not in panel._nav_cards
        assert "scn_evidence" not in panel._navigation_card_snapshots(scene)
        assert panel._overview._advanced_evidence_card.isHidden() is True
        assert panel._overview._advanced_evidence_content.isHidden() is True
        assert panel._overview._advanced_evidence_hint.isHidden() is True
        assert panel._overview._advanced_evidence_toggle_btn.text() == "展开"
        assert panel._details.current_detail is panel._overview
        panel._overview.show_advanced_evidence()
        app.processEvents()
        assert panel._overview._advanced_evidence_card.isHidden() is True
        assert panel._overview._advanced_evidence_content.isHidden() is False
        assert panel._overview._advanced_evidence_hint.isHidden() is False
        assert "常见说法" in panel._overview._advanced_evidence_hint.text()
        assert "请求样本" not in panel._overview._advanced_evidence_hint.text()
        assert panel._overview._advanced_evidence_toggle_btn.text() == "收起"
        assert (
            panel._overview._profile_summary.value_for("planning_family")
            == "合同交付"
        )
        assert "核对字段一致性" in panel._overview._profile_summary.detail_for(
            "planning_workflows"
        )
        assert "修订保护" in panel._overview._profile_summary.detail_for(
            "planning_first_slice"
        )
        assert "批注" in panel._overview._profile_summary.detail_for("planning_ooxml")
        assert "修订" in panel._overview._profile_summary.detail_for("planning_ooxml")
        assert panel._overview._profile_summary.value_for("coverage_pack") == (
            "合同交付"
        )
        assert panel._overview._profile_summary.value_for("contract_field_evidence") == (
            "已打通"
        )
        assert "contract_field_consistency_report" in (
            panel._overview._profile_summary.tooltip_for("contract_field_evidence")
        )
        assert panel._overview._profile_summary.value_for("sample_fixture_coverage") == (
            "已有样本文档"
        )
        assert "Word 对象" in panel._overview._profile_summary.detail_for(
            "sample_fixture_coverage"
        )
        assert panel._overview._profile_summary.value_for("sample_fixture_boundary") == (
            "有边界说明"
        )
        assert panel._overview._profile_summary.value_for("request_cell_coverage") == (
            "常见说法已覆盖"
        )
        assert "4 个请求" in panel._overview._profile_summary.detail_for(
            "request_cell_coverage"
        )
        assert panel._overview._sample_fixture_detail_row.isHidden() is False
        sample_detail = panel._overview._sample_fixture_detail.get_text()
        assert "合同交付样本 1" in sample_detail
        assert "常见说法：" in sample_detail
        assert "用户说法：合同审阅稿甲方乙方金额修订批注" in sample_detail
        assert "修订" in sample_detail
        assert "边界：合同样本只验证格式和字段，不代表法律审查" in sample_detail
        assert "contract_delivery_revisions" not in sample_detail
        assert "contract_review_revisions" not in sample_detail
        assert "fixture=" not in sample_detail
        assert "request-cells:" not in sample_detail
        assert "boundary=" not in sample_detail
        assert panel._overview._sample_fixture_detail._text_edit.isReadOnly() is True
        assert panel._overview._sample_fixture_list_row.isHidden() is False
        assert panel._overview._sample_fixture_list.count() == 2
        assert (
            panel._overview._sample_fixture_list.currentItem().data(Qt.UserRole)
            == "contract_delivery_revisions"
        )
        assert "合同交付样本 1" in panel._overview._sample_fixture_list.currentItem().text()
        assert (
            "contract_delivery_revisions"
            not in panel._overview._sample_fixture_list.currentItem().text()
        )
        sample_tooltip = panel._overview._sample_fixture_list.currentItem().toolTip()
        assert "样本编号：contract_delivery_revisions" in sample_tooltip
        assert "Word 对象：" in sample_tooltip
        assert panel._overview._request_cell_filter_row.isHidden() is False
        assert tuple(
            (
                str(panel._overview._request_cell_filter.itemData(index)),
                panel._overview._request_cell_filter.itemText(index),
            )
            for index in range(panel._overview._request_cell_filter.count())
        ) == scene_request_cell_filter_options()
        assert panel._overview._request_cell_list_row.isHidden() is False
        assert panel._overview._request_cell_list.count() == 4
        assert panel._overview._request_cell_filter_status.text() == "4 条说法"
        assert "当前筛选：全部说法" in (
            panel._overview._request_cell_filter_status.toolTip()
        )
        assert (
            panel._overview._request_cell_list.currentItem().data(Qt.UserRole)
            == "contract_signing_consistency"
        )
        assert "直接证据" in panel._overview._request_cell_list.currentItem().text()
        assert (
            "contract_signing_consistency"
            not in panel._overview._request_cell_list.currentItem().text()
        )
        tooltip = panel._overview._request_cell_list.currentItem().toolTip()
        assert "证据编号：contract_delivery_revisions" in tooltip
        assert "fixture：" not in tooltip
        _set_combo_by_data(
            panel._overview._request_cell_filter,
            "manual_boundary_fixture",
        )
        app.processEvents()
        assert panel._overview._request_cell_list.count() == 0
        assert panel._overview._request_cell_filter_status.text() == "无匹配说法"
        assert "当前筛选：人工确认" in (
            panel._overview._request_cell_filter_status.toolTip()
        )
        _set_combo_by_data(
            panel._overview._request_cell_filter,
            "ambiguous_fixture_set",
        )
        app.processEvents()
        assert panel._overview._request_cell_list.count() == 1
        assert panel._overview._request_cell_filter_status.text() == "1 条 / 共 4 条"
        _set_combo_by_data(panel._overview._request_cell_filter, "all")
        app.processEvents()
        assert panel._overview._request_cell_list.count() == 4
        assert panel._overview._request_cell_filter_status.text() == "4 条说法"
        panel._overview._sample_fixture_output_dir = tmp_path / "scene_samples"
        panel._overview._refresh_sample_fixture_library_state()
        assert panel._overview._open_sample_fixture_dir_btn.isEnabled() is False
        assert panel._overview._open_sample_fixture_file_btn.isEnabled() is False
        assert panel._overview._open_request_cell_fixture_btn.isEnabled() is False
        assert "证据文件未生成" in (
            panel._overview._open_request_cell_fixture_btn.toolTip()
        )
        assert "尚未生成样本库" in panel._overview._sample_fixture_manifest.text()
        assert "manifest" not in panel._overview._sample_fixture_manifest.text()
        assert "生成样本库后" in panel._overview._sample_fixture_manifest.toolTip()
        assert "样本文件未生成" in (
            panel._overview._open_sample_fixture_file_btn.toolTip()
        )

        panel._overview._generate_sample_fixture_btn.click()
        app.processEvents()

        manifest_path = tmp_path / "scene_samples" / "manifest.json"
        fixture_path = tmp_path / "scene_samples" / "contract_delivery_revisions.docx"
        assert manifest_path.exists()
        assert fixture_path.exists()
        assert "样本库已生成" in panel._overview._sample_fixture_manifest.text()
        assert "manifest" not in panel._overview._sample_fixture_manifest.text()
        assert "42 个样本" in panel._overview._sample_fixture_manifest.text()
        assert "位置：" in panel._overview._sample_fixture_manifest.toolTip()
        assert panel._overview._open_sample_fixture_dir_btn.isEnabled() is True
        assert panel._overview._open_sample_fixture_file_btn.isEnabled() is True
        assert "样本库已生成" in panel._overview._open_sample_fixture_file_btn.toolTip()
        assert panel._overview._open_request_cell_fixture_btn.isEnabled() is True
        assert "可以打开说法依据" in (
            panel._overview._open_request_cell_fixture_btn.toolTip()
        )

        opened_paths = []
        panel._overview._open_local_path_handler = (
            lambda path: opened_paths.append(Path(path)) or True
        )
        panel._overview._open_request_cell_fixture_btn.click()
        app.processEvents()

        assert opened_paths == [fixture_path]
        assert "已打开说法依据" in panel._overview._request_cell_evidence_status.text()
        assert str(fixture_path) not in panel._overview._request_cell_evidence_status.text()
        assert "位置：" in panel._overview._request_cell_evidence_status.toolTip()

        panel._overview._open_sample_fixture_file_btn.click()
        app.processEvents()

        assert opened_paths == [fixture_path, fixture_path]
        assert "已打开样本" in panel._overview._sample_fixture_manifest.text()
        assert str(fixture_path) not in panel._overview._sample_fixture_manifest.text()
        assert "位置：" in panel._overview._sample_fixture_manifest.toolTip()

        panel._overview._open_sample_fixture_dir_btn.click()
        app.processEvents()

        assert opened_paths == [fixture_path, fixture_path, tmp_path / "scene_samples"]
        assert "已打开样本目录" in panel._overview._sample_fixture_manifest.text()
        assert str(tmp_path / "scene_samples") not in panel._overview._sample_fixture_manifest.text()
        assert "位置：" in panel._overview._sample_fixture_manifest.toolTip()
        assert panel._overview._profile_summary.value_for("coverage_next_closure") == ""
    finally:
        panel.close()


def test_scene_panel_overview_actions_emit_contextual_navigation_intents():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    bridge.set_current_scene(scene, config_id="custom", emit_signal=False)
    panel = ScenePanel(bridge)
    intents: list[object] = []
    bridge.navigate_to_intent.connect(intents.append)
    try:
        app.processEvents()

        panel._overview._execute_btn.click()

        assert intents[-1]["panel_id"] == "workbench"
        assert intents[-1]["card_id"] == "quick_execute"
        assert intents[-1]["return_panel_id"] == "scene"

        panel._show_detail_from_overview("tpl_overview")

        assert intents[-1]["panel_id"] == "template"
        assert intents[-1]["card_id"] == "tpl_overview"
        assert intents[-1]["return_panel_id"] == "scene"
        assert intents[-1]["payload"]["entry_context_title"] == "来自场景：核对模板与样式"
        assert "模板：" in intents[-1]["payload"]["entry_context_detail"]
        assert intents[-1]["payload"]["entry_context_action"] == (
            "核对页面、正文、标题、表格、页眉页脚、目录和题注"
        )
        assert intents[-1]["payload"]["template_preview_coverage"] == (
            "页面",
            "正文",
            "标题",
            "表格",
            "页眉页脚",
            "目录",
            "题注",
        )
        assert intents[-1]["payload"]["template_preview_groups"] == (
            "tpl_page",
            "tpl_style",
            "tpl_heading",
            "tpl_table",
            "tpl_header_footer",
            "tpl_toc",
            "tpl_caption",
        )
        style_source_row = panel._overview._setting_rows["style_source"]
        style_source_row._jump_btn.click()
        assert panel._nav_rail.selected_card_id() == "scn_rules"
        assert style_source_row._secondary_jump_btn.isHidden()
    finally:
        panel.close()


def test_scene_overview_duplicate_creates_saved_scene_and_selects_it(tmp_path, monkeypatch):
    monkeypatch.setattr(config_library, "SCENE_LIBRARY_DIR", tmp_path / "scenes")
    app = _app()
    bridge = PanelBridge()
    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        original_scene_id = bridge.current_scene_id()
        panel._overview._duplicate_scene_btn.click()
        app.processEvents()

        duplicated_scene_id = bridge.current_scene_id()
        assert duplicated_scene_id
        assert duplicated_scene_id != original_scene_id
        assert (tmp_path / "scenes" / f"{duplicated_scene_id}.json").exists()
        assert panel._overview._combo.currentData() == duplicated_scene_id
        assert panel._overview._rename_scene_btn.isEnabled() is True
        assert panel._overview._delete_scene_btn.isEnabled() is True
    finally:
        panel.close()
        app.processEvents()


def test_scene_overview_strategy_edit_stays_local(tmp_path, monkeypatch):
    monkeypatch.setattr(config_library, "SCENE_LIBRARY_DIR", tmp_path / "scenes")
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    bridge.set_current_scene(scene, config_id="custom", source="library", emit_signal=False)
    bridge.set_current_template(create_builtin_template("default"), config_id="default", emit_signal=False)
    panel = ScenePanel(bridge)
    scene_changed: list[SceneWorkspace] = []
    apply_calls: list[SceneWorkspace] = []
    bridge.scene_changed.connect(scene_changed.append)
    try:
        app.processEvents()
        monkeypatch.setattr(
            panel,
            "_apply_scene",
            lambda updated_scene: apply_calls.append(updated_scene),
        )

        panel._overview._on_strategy_changed(True)
        app.processEvents()

        assert bridge.is_scene_dirty() is True
        assert scene_changed == []
        assert apply_calls == []
    finally:
        panel.close()
        app.processEvents()


def test_scene_overview_shows_exam_assembly_strategy_without_workbench_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(config_library, "SCENE_LIBRARY_DIR", tmp_path / "scenes")
    app = _app()
    bridge = PanelBridge()
    scene = create_exam_scene()
    bridge.set_current_scene(scene, config_id="exam", emit_signal=False)
    bridge.set_current_template(create_builtin_template("default"), config_id="default", emit_signal=False)
    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        assert panel._overview._setting_rows["exam_blank_style"].isHidden() is False
        assert panel._overview._setting_rows["exam_runtime_fields"].isHidden() is False
        assert "exam_question_structure" not in panel._overview._setting_rows
        assert "exam_answer_handling" not in panel._overview._setting_rows
        assert panel._overview._setting_rows["materials"].isHidden() is True
        assert panel._overview._setting_rows["scope"].isHidden() is True
        assert panel._overview._setting_rows["style_source"].isHidden() is True
        assert panel._nav_cards["scn_content"].isHidden() is True
        assert panel._nav_section_headers["input_material"].isHidden() is True
        assert panel._style_rules.isHidden() is True
        assert panel._style_rules._style_variant_combo.count() == 0
        assert panel._style_rules._style_rules_block.current_variant_key() == ""
        assert panel._style_rules._style_rules_block.current_policy_key() == ""
        assert all(
            panel._style_rules._style_rules_block.rows[variant.key].isHidden()
            for variant in STYLE_VARIANTS
        )
        assert "无格式例外" not in panel._navigation_card_snapshots(scene)["scn_rules"][
            "subtitle"
        ]

        assert panel._overview._setting_rows["exam_blank_style"]._label.text() == "试卷母版"
        assert panel._overview._setting_rows["exam_runtime_fields"]._label.text() == "本次信息"
        assert panel._nav_cards["scn_exam_paper"].isHidden() is False
        assert panel._overview._setting_rows["exam_runtime_fields"]._jump_btn.isHidden() is False
        assert "工作台" in panel._overview._setting_rows["exam_runtime_fields"].summary_text()
        panel._overview._setting_rows["exam_blank_style"]._jump_btn.click()
        assert panel._nav_rail.selected_card_id() == "scn_exam_paper"

        run_step_texts = [
            row.step_text()
            for row in panel._overview._run_step_rows
            if not row.isHidden()
        ]
        assert any("导入试卷内容" in text for text in run_step_texts)
        assert any("填写考试信息" in text for text in run_step_texts)
        assert any("生成 Word 试卷" in text for text in run_step_texts)
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_keeps_material_card_for_exam_with_material_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(config_library, "SCENE_LIBRARY_DIR", tmp_path / "scenes")
    app = _app()
    bridge = PanelBridge()
    scene = create_exam_scene()
    scene.input_source_profile.required_material_fields = ["exam_title"]
    bridge.set_current_scene(scene, config_id="exam", emit_signal=False)
    bridge.set_current_template(create_builtin_template("default"), config_id="default", emit_signal=False)
    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        assert panel._nav_cards["scn_content"].isHidden() is False
        assert panel._nav_section_headers["input_material"].isHidden() is False
        assert panel._navigation_card_snapshots(scene)["scn_content"]["badge_text"] == "已配置"
    finally:
        panel.close()
        app.processEvents()


def test_scene_exam_paper_detail_updates_config_and_answer_delivery(tmp_path, monkeypatch):
    monkeypatch.setattr(config_library, "SCENE_LIBRARY_DIR", tmp_path / "scenes")
    monkeypatch.setattr("src.ui.panels.scene_panel.Toast.show_success", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.ui.panels.scene_panel.Toast.show_warning", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.ui.panels.scene_panel.Toast.show_error", lambda *args, **kwargs: None)
    app = _app()
    bridge = PanelBridge()
    scene = create_exam_scene()
    bridge.set_current_scene(scene, config_id="exam", emit_signal=False)
    bridge.set_current_template(create_builtin_template("default"), config_id="default", emit_signal=False)
    panel = ScenePanel(bridge)
    try:
        panel.resize(1330, 1120)
        panel.show()
        app.processEvents()
        panel._nav_rail.select_card("scn_exam_paper")
        app.processEvents()
        app.processEvents()

        detail = panel._exam_paper
        expected_gap = get_theme().template_detail_section_gap
        assert detail.layout().spacing() == expected_gap
        assert detail._preview_card.y() - (
            detail._master_card.y() + detail._master_card.height()
        ) == expected_gap
        assert detail._prompt_card.y() - (
            detail._preview_card.y() + detail._preview_card.height()
        ) == expected_gap

        assert detail._card.isHidden()
        assert detail._detail_summary.isHidden()
        assert detail._master_card.isHidden() is False
        assert detail._master_card._title_label.text() == "试卷装配"
        assert detail._master_card._sep.isHidden()
        assert not hasattr(detail, "_master_intro")
        assert not hasattr(detail, "_style_status")
        assert detail._live_summary.isHidden()
        assert not hasattr(detail, "_question_structure")
        assert not hasattr(detail, "_answer_policy")
        assert detail._blank_style.findData("compact_exam") == -1
        assert detail._blank_style.property("fullWidthMode") is True
        assert detail._default_master_btn.text() == "默认母版"
        assert detail._open_master_btn.text() == "打开母版"
        assert detail._sample_docx_btn.text() == "生成样张"
        assert detail._copy_style_btn.text() == "创建副本"
        assert detail._open_master_folder_btn.text() == "打开母版文件夹"
        assert detail._import_style_btn.text() == "导入母版"
        assert detail._preview_card.isHidden() is False
        assert detail._preview_card._title_label.text() == "母版预览"
        assert detail._preview_mode_control.current_data() == "student"
        assert "学生卷：答案与解析不显示" not in detail._preview_page.text()
        assert "下列词语中加点字读音" in detail._preview_page.text()
        assert "答案速查" not in detail._preview_page.text()
        assert detail._prompt_card.isHidden() is False
        assert detail._prompt_card._title_label.text() == "AI 提示词"
        assert detail._prompt_mode_control.current_data() == "markdown"
        assert "只输出 Markdown 正文" in detail._prompt_area.get_text()
        assert "不要编写页眉、页脚、页码、密封线" in detail._prompt_area.get_text()
        assert "{{af_questions}}" not in detail._prompt_area.get_text()

        detail._prompt_mode_control.set_current_index(1)
        app.processEvents()
        assert detail._prompt_mode_control.current_data() == "master"
        assert "{{af_title}}" in detail._prompt_area.get_text()
        assert "{{af_questions}}" in detail._prompt_area.get_text()
        assert "页眉页脚只作为母版版式存在" in detail._prompt_area.get_text()
        detail._copy_prompt_btn.click()
        assert app.clipboard().text() == detail._prompt_area.get_text()

        detail._preview_mode_control.set_current_index(1)
        app.processEvents()
        assert detail._preview_mode_control.current_data() == "answer"
        assert "答案速查" in detail._preview_page.text()
        assert "注意事项" not in detail._preview_page.text()
        assert "下列词语中加点字读音" not in detail._preview_page.text()
        assert bridge.current_scene().exam_paper.answer_policy == "student_plus_answer"

        opened_paths = []
        detail._open_sample_path_handler = lambda path: opened_paths.append(path) or True
        detail._open_master_btn.click()
        assert opened_paths
        assert opened_paths[-1].exists()
        assert opened_paths[-1].name == "default_exam_v20.docx"
        assert opened_paths[-1].parent.name == "builtin"

        detail._open_master_folder_btn.click()
        assert opened_paths[-1].exists()
        assert opened_paths[-1].name == "builtin"

        detail._sample_docx_btn.click()
        assert opened_paths[-1].exists()
        assert "样张" in opened_paths[-1].name

        detail._copy_style_btn.click()
        app.processEvents()
        current_scene = bridge.current_scene()
        assert current_scene.exam_paper.custom_blank_styles
        copied_style = current_scene.exam_paper.custom_blank_styles[-1]
        assert current_scene.exam_paper.blank_style_id == copied_style.style_id
        assert detail._blank_style.currentData() == copied_style.style_id
        assert copied_style.label in detail._preview_page.text()
        copied_path = Path(copied_style.master_docx_path)
        if not copied_path.is_absolute():
            copied_path = ROOT / copied_path
        assert copied_path.exists()
        assert not hasattr(detail, "_master_intro")

        monkeypatch.setattr(
            "src.ui.panels.scene_panel.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: (str(opened_paths[0]), "Word 文档 (*.docx)"),
        )
        detail._import_style_btn.click()
        app.processEvents()
        current_scene = bridge.current_scene()
        imported_style = current_scene.exam_paper.custom_blank_styles[-1]
        assert imported_style.style_id == "user_imported_exam"
        assert current_scene.exam_paper.blank_style_id == imported_style.style_id
        assert detail._blank_style.currentData() == imported_style.style_id
        assert imported_style.label in detail._preview_page.text()
        imported_path = Path(imported_style.master_docx_path)
        if not imported_path.is_absolute():
            imported_path = ROOT / imported_path
        assert imported_path.exists()
        assert not hasattr(detail, "_master_intro")

        detail._default_master_btn.click()
        app.processEvents()

        current_scene = bridge.current_scene()
        assert current_scene.exam_paper.blank_style_id == "default_exam"
        assert current_scene.exam_paper.question_structure_mode == "markdown_headings"
        assert current_scene.exam_paper.answer_policy == "student_plus_answer"
        assert "默认试卷" in detail._preview_page.text()
        assert not hasattr(detail, "_master_intro")
        assert not hasattr(detail, "_style_status")
        preset_ids = {
            str(getattr(preset, "preset_id", "") or "")
            for preset in current_scene.delivery_presets
        }
        assert "student" in preset_ids

        detail._default_master_btn.click()
        app.processEvents()
        current_scene = bridge.current_scene()
        assert current_scene.exam_paper.blank_style_id == "default_exam"
        assert current_scene.exam_paper.question_structure_mode == "markdown_headings"
        assert current_scene.exam_paper.answer_policy == "student_plus_answer"
        preset_ids = {
            str(getattr(preset, "preset_id", "") or "")
            for preset in current_scene.delivery_presets
        }
        assert "student" in preset_ids
    finally:
        panel.close()
        app.processEvents()


def test_scene_overview_selector_groups_user_scenes_above_builtin_scenes(tmp_path, monkeypatch):
    monkeypatch.setattr(config_library, "SCENE_LIBRARY_DIR", tmp_path / "scenes")
    config_library.ensure_config_library()
    config_library.save_scene_to_library(
        SceneWorkspace(
            scene_id="exam_default_copy",
            name="试卷-期中",
            template_id="default",
            default_template_id="default",
            compatible_template_ids=["default"],
        ),
        scene_id="exam_default_copy",
    )
    app = _app()
    bridge = PanelBridge()
    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        combo = panel._overview._combo
        texts = [combo.itemText(index) for index in range(combo.count())]
        assert texts.index("我的场景") < texts.index("试卷-期中")
        assert texts.index("试卷-期中") < texts.index("内置场景")
        assert texts.index("内置场景") < texts.index("通用-默认")

        group_index = texts.index("我的场景")
        combo.setCurrentIndex(group_index)
        panel._on_scene_changed(group_index)
        app.processEvents()

        assert bridge.current_scene_id() == "custom"
        assert combo.currentData() == "custom"
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_template_preview_summary_renders_without_overlap_at_narrow_width():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(
        scene_id="contract_delivery",
        name="合同交付",
        category="contract_delivery",
        template_id="default",
        default_template_id="default",
        compatible_template_ids=["default"],
    )
    template = create_builtin_template("default")
    bridge.set_current_scene(scene, config_id="contract_delivery", emit_signal=False)
    bridge.set_current_template(template, config_id="default", emit_signal=False)
    panel = ScenePanel(bridge)
    try:
        panel.resize(620, 900)
        panel.show()
        app.processEvents()
        app.processEvents()

        row = panel._overview._setting_rows["style_source"]
        summary = row._summary
        button = row._jump_btn
        summary_right = summary.mapTo(row, QPoint(summary.width(), 0)).x()
        button_left = button.mapTo(row, QPoint(0, 0)).x()
        button_right = button.mapTo(row, QPoint(button.width(), 0)).x()
        required_summary_height = summary.heightForWidth(summary.width())
        if required_summary_height < 0:
            required_summary_height = summary.sizeHint().height()

        assert row.summary_text() == "使用默认格式，无格式例外"
        assert build_template_preview_context(template).action == (
            "核对页面、正文、标题、表格、页眉页脚、目录和题注"
        )
        assert summary.wordWrap() is True
        assert summary.width() > 0
        assert summary.height() >= required_summary_height
        assert summary_right <= button_left - 8
        assert button_right <= row.width()
        assert row.height() >= row.sizeHint().height()
        assert panel._detail_scroll.horizontalScrollBar().maximum() == 0

        image = row.grab().toImage()
        dark_samples = 0
        for y in range(0, image.height(), max(1, image.height() // 12)):
            for x in range(0, image.width(), max(1, image.width() // 24)):
                color = image.pixelColor(x, y)
                if color.alpha() and color.red() + color.green() + color.blue() < 600:
                    dark_samples += 1
        assert dark_samples >= 8
    finally:
        panel.close()


def test_scene_panel_output_advanced_naming_and_reports_are_collapsed_by_default():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="contract_delivery", template_id="default")
    bridge.set_current_scene(scene, config_id="contract_delivery", emit_signal=False)
    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        output = panel._output
        assert output._advanced_output_title.text() == "高级命名、规则与报告"
        assert output._advanced_output_container.isHidden() is True
        assert output._advanced_output_toggle_btn.text() == "展开"
        assert output._final_docx.isHidden() is False
        assert output._material_package.isHidden() is False

        output._advanced_output_toggle_btn.click()
        app.processEvents()

        assert output._advanced_output_container.isHidden() is False
        assert output._advanced_output_toggle_btn.text() == "收起"
    finally:
        panel.close()


def test_scene_panel_output_rules_card_edits_delivery_artifacts_directly():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="contract_delivery", template_id="default")
    bridge.set_current_scene(scene, config_id="contract_delivery", emit_signal=False)
    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        output_rules = panel._rules._output_rules
        assert panel._output.isHidden() is True
        assert output_rules._general_checks["final_docx"].isHidden() is False
        assert output_rules._exam_student_check.isHidden() is True
        assert output_rules._general_checks["report"].isChecked() is True

        output_rules._general_checks["report"].click()
        app.processEvents()

        assert scene.output.report_json is False
        assert scene.output.report_markdown is False
        assert scene.delivery_presets[0].artifacts.report_json is False
        assert scene.delivery_presets[0].artifacts.report_markdown is False

        output_rules._general_checks["material_package"].click()
        app.processEvents()

        assert scene.output.material_package is True
        assert scene.delivery_presets[0].artifacts.material_package is True
    finally:
        panel.close()


def test_scene_panel_output_rules_card_controls_exam_answer_delivery():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="exam_default", category="exam", template_id="default")
    bridge.set_current_scene(scene, config_id="exam_default", emit_signal=False)
    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        output_rules = panel._rules._output_rules
        assert output_rules._exam_student_check.isHidden() is False
        assert output_rules._general_checks["final_docx"].isHidden() is True
        assert output_rules._exam_student_check.isChecked() is True
        assert output_rules._exam_student_check.isEnabled() is True
        assert output_rules._exam_answer_check.isChecked() is True
        assert scene.exam_paper.answer_policy == "student_plus_answer"
        assert {
            preset.preset_id
            for preset in scene.delivery_presets
        } == {"student", "answer_key"}

        output_rules._exam_answer_check.click()
        app.processEvents()

        assert scene.exam_paper.answer_policy == "student_only"
        assert {
            preset.preset_id
            for preset in scene.delivery_presets
        } == {"student"}

        output_rules._exam_answer_check.click()
        app.processEvents()
        output_rules._exam_student_check.click()
        app.processEvents()

        assert scene.exam_paper.answer_policy == "answer_only"
        assert {
            preset.preset_id
            for preset in scene.delivery_presets
        } == {"answer_key"}
        assert scene.default_delivery_preset_id == "answer_key"
    finally:
        panel.close()


def test_scene_panel_navigation_intent_shows_return_to_execution_action():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="contract_delivery", template_id="default")
    bridge.set_current_scene(scene, config_id="contract_delivery", emit_signal=False)
    panel = ScenePanel(bridge)
    intents: list[object] = []
    bridge.navigate_to_intent.connect(intents.append)
    try:
        app.processEvents()

        panel.handle_navigation_intent(
            {
                "panel_id": "scene",
                "card_id": "scn_output",
                "return_panel_id": "workbench",
                "return_card_id": "quick_execute",
            }
        )

        assert panel._return_bar.isHidden() is False
        assert panel._nav_rail.selected_card_id() == "scn_rules"

        panel._return_btn.click()

        assert intents[-1] == {
            "panel_id": "workbench",
            "card_id": "quick_execute",
        }
        assert panel._return_bar.isHidden() is True

        panel.handle_navigation_intent(
            {
                "panel_id": "scene",
                "card_id": "scn_output",
                "field_id": "review",
                "active_issue_id": "output_target.review.warning",
                "return_panel_id": "workbench",
                "return_card_id": "quick_execute",
                "payload": {
                    "issue_title": "输出目标预检",
                    "issue_item_id": "output_target.review.warning",
                },
            }
        )

        assert panel._return_label.text() == "从执行问题进入：输出目标预检"
        assert panel._output.isHidden() is False

        panel._return_btn.click()

        assert intents[-1]["panel_id"] == "workbench"
        assert intents[-1]["card_id"] == "quick_execute"
        assert intents[-1]["active_issue_id"] == "output_target.review.warning"
        assert intents[-1]["payload"]["active_issue_id"] == (
            "output_target.review.warning"
        )

        panel.handle_navigation_intent(
            {
                "panel_id": "scene",
                "card_id": "scn_output",
                "field_id": "filename_template",
                "return_panel_id": "workbench",
                "return_card_id": "quick_execute",
            }
        )
        app.processEvents()

        assert panel._nav_rail.selected_card_id() == "scn_rules"
        assert panel._output._advanced_output_container.isHidden() is False
        assert panel._output._delivery_filename.property("navigation_field_highlight") is True
        assert "文件名规则" in panel._output._delivery_filename.toolTip()
        assert "filename_template" not in panel._output._delivery_filename.toolTip()
        assert panel._output._delivery_filename.property("navigation_field_raw_label") == (
            "filename_template"
        )
        assert panel._output._delivery_filename.objectName() == (
            "scn_output_filename_template"
        )

        panel._output._advanced_output_expanded = False
        panel._output._sync_advanced_output_visibility()
        assert panel._output._advanced_output_container.isHidden() is True

        panel.handle_navigation_intent(
            {
                "panel_id": "scene",
                "card_id": "scn_output",
                "field_id": "preset_id",
                "return_panel_id": "workbench",
                "return_card_id": "quick_execute",
            }
        )
        app.processEvents()

        assert panel._nav_rail.selected_card_id() == "scn_rules"
        assert panel._output._advanced_output_container.isHidden() is False
        assert panel._output._delivery_preset_id.property("navigation_field_highlight") is True
        assert "交付编号" in panel._output._delivery_preset_id.toolTip()
        assert panel._output._delivery_preset_id.property("navigation_field_raw_label") == (
            "preset_id"
        )
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_request_cell_list_filters_boundary_levels():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(
        scene_id="professional_disclosure",
        name="专业披露",
        category="professional_disclosure",
        template_id="default",
        default_template_id="default",
        compatible_template_ids=["default"],
    )
    template = create_builtin_template("default")
    bridge.set_current_scene(scene, config_id="professional_disclosure", emit_signal=False)
    bridge.set_current_template(template, config_id="default", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        assert panel._overview._request_cell_list_row.isHidden() is False
        assert panel._overview._request_cell_list.count() == 9

        _set_combo_by_data(
            panel._overview._request_cell_filter,
            "manual_boundary_fixture",
        )
        app.processEvents()
        assert panel._overview._request_cell_list.count() == 6
        assert panel._overview._request_cell_filter_status.text() == "6 条 / 共 9 条"
        assert "人工确认" in panel._overview._request_cell_list.currentItem().text()
        assert "professional_disclosure_review_gate" in (
            panel._overview._request_cell_list.currentItem().toolTip()
        )

        _set_combo_by_data(panel._overview._request_cell_filter, "ambiguous_fixture_set")
        app.processEvents()
        assert panel._overview._request_cell_list.count() == 3
        assert panel._overview._request_cell_filter_status.text() == "3 条 / 共 9 条"
        assert "容易误解" in panel._overview._request_cell_list.currentItem().text()
        assert "需要先澄清" in panel._overview._request_cell_list.currentItem().toolTip()
        assert "候选资料包" in panel._overview._request_cell_list.currentItem().toolTip()
        assert "候选路由" not in panel._overview._request_cell_list.currentItem().toolTip()

        _set_combo_by_data(panel._overview._request_cell_filter, "direct_family_fixture")
        app.processEvents()
        assert panel._overview._request_cell_list.count() == 0
        assert panel._overview._request_cell_filter_status.text() == "无匹配说法"
        assert "当前筛选：直接证据" in (
            panel._overview._request_cell_filter_status.toolTip()
        )
        assert "先选择一条请求说法" in (
            panel._overview._open_request_cell_fixture_btn.toolTip()
        )
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_can_apply_planning_family_preflight_targets():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(
        scene_id="contract_delivery",
        name="合同交付",
        category="contract_delivery",
        template_id="default",
        default_template_id="default",
        compatible_template_ids=["default"],
    )
    scene.input_source_profile.material_schema_id = "contract_parties_v1"
    scene.compliance_profile.object_preflight.scan_targets = ["fields"]
    template = create_builtin_template("default")
    bridge.set_current_scene(scene, config_id="contract_delivery", emit_signal=False)
    bridge.set_current_template(template, config_id="default", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        recommended = recommended_object_preflight_targets_for_scene(scene)
        assert panel._cleanup._apply_family_preflight_btn.isEnabled() is True
        assert panel._cleanup._compliance_summary.value_for("planning_scan_targets") == "需同步"

        panel._cleanup._apply_family_preflight_btn.click()
        app.processEvents()

        assert scene.compliance_profile.object_preflight.scan_targets == list(recommended)
        assert "tracked_changes" in scene.compliance_profile.object_preflight.scan_targets
        assert panel._cleanup._scan_target_checks["tracked_changes"].isChecked() is True
        assert panel._cleanup._scan_target_checks["fields"].isChecked() is True
        assert panel._cleanup._compliance_summary.value_for("planning_scan_targets") == "已应用"
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_scan_target_checkboxes_write_back_to_scene():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(
        scene_id="contract_delivery",
        name="合同交付",
        category="contract_delivery",
        template_id="default",
        default_template_id="default",
        compatible_template_ids=["default"],
    )
    scene.compliance_profile.object_preflight.scan_targets = ["comments", "fields"]
    template = create_builtin_template("default")
    bridge.set_current_scene(scene, config_id="contract_delivery", emit_signal=False)
    bridge.set_current_template(template, config_id="default", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        assert panel._cleanup._scan_target_checks["fields"].isChecked() is True
        assert panel._cleanup._scan_target_checks["macros"].isChecked() is False
        assert panel._cleanup._compliance_summary.value_for("scan_targets") == "2 个目标"

        panel._cleanup._scan_target_checks["fields"].click()
        panel._cleanup._scan_target_checks["tracked_changes"].click()
        app.processEvents()

        assert scene.compliance_profile.object_preflight.scan_targets == [
            "tracked_changes",
            "comments",
        ]
        assert panel._cleanup._compliance_summary.value_for("scan_targets") == "2 个目标"
        target_detail = panel._cleanup._compliance_summary.detail_for("scan_targets")
        assert "tracked_changes" in target_detail
        assert "fields" not in target_detail
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_profile_controls_write_back_to_scene():
    app = _app()
    bridge = PanelBridge()
    scene = create_thesis_scene()
    template = create_builtin_template("thesis_gbt")
    bridge.set_current_scene(scene, config_id="thesis", emit_signal=False)
    bridge.set_current_template(template, config_id="thesis_gbt", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        disabled_index = panel._content._markdown_policy.findData("disabled")
        panel._content._markdown_policy.setCurrentIndex(disabled_index)
        app.processEvents()
        assert scene.input_source_profile.markdown_policy == "disabled"
        assert "MD 禁用" in panel._content._input_summary.value_for("input_policy")

        panel._cleanup._skip_high_risk.click()
        app.processEvents()
        assert scene.compliance_profile.object_preflight.skip_high_risk_modules is False
        assert panel._cleanup._compliance_summary.value_for("skip_policy") == "关闭"

        review_index = panel._output._default_delivery.findData("review")
        panel._output._default_delivery.setCurrentIndex(review_index)
        app.processEvents()
        assert scene.default_delivery_preset_id == "review"
        assert scene.output.compare_docx is True
        assert panel._output._delivery_summary.value_for("default_delivery") == "审阅稿"

        panel._output._delivery_label.setText("Review package")
        panel._output._delivery_output_dir.setText("review/{preset_id}")
        panel._output._delivery_filename.setText("{stem}_reviewed")
        app.processEvents()

        review_preset = next(preset for preset in scene.delivery_presets if preset.preset_id == "review")
        assert review_preset.label == "Review package"
        assert review_preset.output_dir_template == "review/{preset_id}"
        assert review_preset.filename_template == "{stem}_reviewed"
        assert panel._output._default_delivery.itemText(
            panel._output._default_delivery.currentIndex()
        ) == "Review package"
        assert panel._output._delivery_summary.value_for("default_delivery") == "Review package"
        assert panel._output._delivery_summary.detail_for("default_delivery") == "执行时默认生成"
        assert panel._output._delivery_validation_summary.value_for(
            "delivery_template_status"
        ) == "通过"
        variable_detail = panel._output._delivery_validation_summary.detail_for(
            "delivery_variables"
        )
        assert "交付编号" in variable_detail
        assert "{preset_id}" not in variable_detail
        assert "{preset_id}" in panel._output._delivery_validation_summary.tooltip_for(
            "delivery_variables"
        )
        assert "review/review" in panel._output._delivery_validation_summary.detail_for(
            "delivery_template_status"
        )

        panel._output._material_manifest.click()
        panel._output._material_package.click()
        app.processEvents()

        assert scene.output.material_manifest is True
        assert scene.output.material_package is True
        assert review_preset.artifacts.material_manifest is True
        assert review_preset.artifacts.material_package is True
        assert "资料清单" in panel._output._delivery_summary.value_for("default_artifacts")
        assert "资料包" in panel._output._delivery_summary.value_for("default_artifacts")

        panel._output._visibility_rules.set_text("answer=remove\nanalysis=hide")
        app.processEvents()

        assert [rule.selector for rule in review_preset.content_visibility_rules] == [
            "answer",
            "analysis",
        ]
        assert [rule.label for rule in review_preset.content_visibility_rules] == [
            "答案",
            "解析",
        ]
        assert [rule.action for rule in review_preset.content_visibility_rules] == [
            "remove",
            "hide",
        ]
        rule_status_detail = panel._output._delivery_validation_summary.detail_for(
            "delivery_rule_status"
        )
        assert "答案：删除块" in rule_status_detail
        assert "解析：隐藏块" in rule_status_detail
        rule_status_tooltip = panel._output._delivery_validation_summary.tooltip_for(
            "delivery_rule_status"
        )
        assert "answer=remove" in rule_status_tooltip
        assert "analysis=hide" in rule_status_tooltip
        assert "显隐规则 2 条" in panel._output._delivery_summary.detail_for("default_artifacts")

        original_count = len(scene.delivery_presets)
        panel._output._copy_preset_btn.click()
        app.processEvents()

        copied_preset = scene.delivery_presets[-1]
        assert len(scene.delivery_presets) == original_count + 1
        assert copied_preset.preset_id == "review_copy"
        assert copied_preset.label == "Review package Copy"
        assert copied_preset.output_dir_template == "review/{preset_id}"
        assert copied_preset.filename_template == "{stem}_reviewed"
        assert copied_preset.artifacts.material_package is True
        assert [rule.selector for rule in copied_preset.content_visibility_rules] == [
            "answer",
            "analysis",
        ]
        assert [rule.label for rule in copied_preset.content_visibility_rules] == [
            "答案",
            "解析",
        ]
        assert scene.default_delivery_preset_id == "review_copy"
        assert panel._output._delivery_summary.value_for("default_delivery") == "Review package Copy"
        assert (
            panel._output._delivery_summary.detail_for("default_delivery")
            == "执行时默认生成"
        )

        panel._output._delivery_preset_id.setText("review public")
        panel._output._delivery_preset_id.editingFinished.emit()
        panel._output._delivery_target_template.setText("thesis_review_template")
        app.processEvents()

        assert copied_preset.preset_id == "review_public"
        assert copied_preset.target_template_id == "thesis_review_template"
        assert scene.default_delivery_preset_id == "review_public"
        assert panel._output._default_delivery.currentData() == "review_public"
        assert panel._output._delivery_preset_id.text() == "review_public"
        assert panel._output._delivery_summary.value_for("default_delivery") == "Review package Copy"
        assert (
            panel._output._delivery_summary.detail_for("default_delivery")
            == "执行时默认生成"
        )

        panel._output._move_up_preset_btn.click()
        app.processEvents()
        assert [preset.preset_id for preset in scene.delivery_presets][-2] == "review_public"
        assert scene.default_delivery_preset_id == "review_public"
        assert panel._output._move_down_preset_btn.isEnabled()

        panel._output._move_down_preset_btn.click()
        app.processEvents()
        assert [preset.preset_id for preset in scene.delivery_presets][-1] == "review_public"
        assert scene.default_delivery_preset_id == "review_public"

        panel._output._add_preset_btn.click()
        app.processEvents()

        added_preset = scene.delivery_presets[-1]
        assert added_preset.preset_id == "delivery"
        assert added_preset.output_dir_template == "{preset_id}"
        assert added_preset.filename_template == "{stem}_{preset_id}"
        assert scene.default_delivery_preset_id == "delivery"

        panel._output._remove_preset_btn.click()
        app.processEvents()

        assert all(preset.preset_id != "delivery" for preset in scene.delivery_presets)
        assert scene.default_delivery_preset_id == "review_public"
        assert panel._output._delivery_summary.value_for("default_delivery") == "Review package Copy"
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_content_detail_edits_material_schema_contract():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(
        scene_id="contract_delivery",
        name="合同交付",
        category="contract_delivery",
        template_id="default",
        default_template_id="default",
        compatible_template_ids=["default"],
    )
    template = create_builtin_template("default")
    bridge.set_current_scene(scene, config_id="contract_delivery", emit_signal=False)
    bridge.set_current_template(template, config_id="default", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        contract_index = panel._content._schema_registry_combo.findData("contract_parties_v1")
        assert contract_index >= 0
        panel._content._schema_registry_combo.setCurrentIndex(contract_index)
        panel._content._set_primary_schema_btn.click()
        app.processEvents()

        assert scene.input_source_profile.material_schema_id == "contract_parties_v1"
        assert scene.input_source_profile.material_schema_ids == []
        assert "合同方字段资料" in panel._content._input_summary.detail_for("materials")
        assert panel._content._schema_validation_summary.value_for(
            "schema_registry_status"
        ) == "通过"
        assert "合同方字段资料" in panel._content._schema_validation_summary.detail_for(
            "schema_labels"
        )
        assert "Contract party fields" in panel._content._schema_validation_summary.tooltip_for(
            "schema_labels"
        )

        signature_index = panel._content._schema_registry_combo.findData("signature_assets_v1")
        assert signature_index >= 0
        panel._content._schema_registry_combo.setCurrentIndex(signature_index)
        panel._content._append_schema_btn.click()
        panel._content._required_material_fields.set_text("contract_no")
        panel._content._required_image_roles.set_text("legal_signature")
        app.processEvents()

        assert scene.input_source_profile.material_schema_ids == [
            "contract_parties_v1",
            "signature_assets_v1",
        ]
        assert scene.input_source_profile.required_material_fields == ["contract_no"]
        assert scene.input_source_profile.required_image_roles == ["legal_signature"]
        material_detail = panel._content._input_summary.detail_for("materials")
        assert "合同方字段资料" in material_detail
        assert "签章资料" in material_detail
        assert panel._content._schema_validation_summary.value_for(
            "schema_registry_status"
        ) == "通过"
        assert panel._content._schema_validation_summary.value_for(
            "schema_rule_overview"
        ) == "已识别 2 个资料规则"
        overview_detail = panel._content._schema_validation_summary.detail_for(
            "schema_rule_overview"
        )
        assert "字段：5 个必填项" in overview_detail
        assert "图片/签章：2 必填 / 3 全部" in overview_detail
        assert "附件：无" in overview_detail
        assert "contract_parties_v1" not in overview_detail
        assert "contract_no" not in overview_detail
        overview_tooltip = panel._content._schema_validation_summary.tooltip_for(
            "schema_rule_overview"
        )
        assert "contract_parties_v1" in overview_tooltip
        assert "contract_no" in overview_tooltip
        assert "签章资料" in panel._content._schema_validation_summary.detail_for(
            "schema_labels"
        )
        assert "Signature and seal assets" in panel._content._schema_validation_summary.tooltip_for(
            "schema_labels"
        )
        assert "合同交付" in panel._content._schema_validation_summary.detail_for(
            "schema_families"
        )
        assert "contract_delivery" in panel._content._schema_validation_summary.tooltip_for(
            "schema_families"
        )
        assert panel._content._schema_validation_summary.value_for(
            "schema_fields"
        ) == "5 个必填项"
        field_detail = panel._content._schema_validation_summary.detail_for("schema_fields")
        assert "合同编号（必填）" in field_detail
        assert "contract_no" not in field_detail
        assert "profile override" not in field_detail
        assert "本场景补充要求" not in field_detail
        field_tooltip = panel._content._schema_validation_summary.tooltip_for("schema_fields")
        assert "contract_no · Contract number · 必填" in field_tooltip
        assert "本场景补充要求" in field_tooltip
        assert "profile override" not in field_tooltip
        assert panel._content._schema_validation_summary.value_for(
            "schema_image_roles"
        ) == "2 必填 / 3 全部"
        image_detail = panel._content._schema_validation_summary.detail_for(
            "schema_image_roles"
        )
        assert "印章（必填）" in image_detail
        assert "法定代表签名（必填）" in image_detail
        image_tooltip = panel._content._schema_validation_summary.tooltip_for(
            "schema_image_roles"
        )
        assert "seal · Seal · 必填 · image" in image_tooltip
        assert "legal_signature · Legal representative signature · 必填 · image" in image_tooltip
        assert "本场景补充要求" in image_tooltip
        assert "profile override" not in image_tooltip
        assert panel._content._schema_validation_summary.value_for(
            "schema_attachment_roles"
        ) == "无"
        assert panel._content._input_summary.value_for("material_fields") == "5 个字段"
        assert "合同编号" in panel._content._input_summary.detail_for("material_fields")
        assert panel._content._input_summary.value_for("image_roles") == "2 个角色"
        image_role_detail = panel._content._input_summary.detail_for("image_roles")
        assert "印章" in image_role_detail
        assert "法定代表签名" in image_role_detail

        panel._content._material_schema_ids.set_text(
            "contract_parties_v1\nmissing_schema_v1"
        )
        app.processEvents()

        assert panel._content._schema_validation_summary.value_for(
            "schema_registry_status"
        ) == "未识别 1 个"
        assert panel._content._schema_validation_summary.value_for(
            "schema_rule_overview"
        ) == "已识别 1 个，未识别 1 个"
        assert panel._content._remove_unknown_schema_btn.isEnabled() is True
        assert "missing_schema_v1" not in panel._content._schema_validation_summary.detail_for(
            "schema_rule_overview"
        )
        assert "missing_schema_v1" in panel._content._schema_validation_summary.tooltip_for(
            "schema_rule_overview"
        )
        assert "missing_schema_v1" not in panel._content._schema_validation_summary.detail_for(
            "schema_registry_status"
        )
        assert "missing_schema_v1" in panel._content._schema_validation_summary.tooltip_for(
            "schema_registry_status"
        )

        panel._content._remove_unknown_schema_btn.click()
        app.processEvents()

        assert scene.input_source_profile.material_schema_id == "contract_parties_v1"
        assert scene.input_source_profile.material_schema_ids == ["contract_parties_v1"]
        assert "missing_schema_v1" not in panel._content._material_schema_ids.get_text()
        assert panel._content._schema_validation_summary.value_for(
            "schema_registry_status"
        ) == "通过"
        assert panel._content._remove_unknown_schema_btn.isEnabled() is False
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_content_detail_focuses_material_schema_contract_controls():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(
        scene_id="contract_delivery",
        name="鍚堝悓浜や粯",
        category="contract_delivery",
        template_id="default",
        default_template_id="default",
        compatible_template_ids=["default"],
    )
    scene.input_source_profile.material_schema_id = "contract_parties_v1"
    scene.input_source_profile.material_schema_ids = [
        "contract_parties_v1",
        "signature_assets_v1",
    ]
    scene.input_source_profile.required_material_fields = ["contract_no"]
    scene.input_source_profile.required_image_roles = ["legal_signature"]
    template = create_builtin_template("default")
    bridge.set_current_scene(scene, config_id="contract_delivery", emit_signal=False)
    bridge.set_current_template(template, config_id="default", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        assert panel._content.focus_navigation_field(
            "input_source_profile.material_schema_id"
        )
        assert (
            panel._content._material_schema_id.property("navigation_field_highlight")
            is True
        )
        assert "主资料规则" in panel._content._material_schema_id.toolTip()
        assert (
            "input_source_profile.material_schema_id"
            not in panel._content._material_schema_id.toolTip()
        )
        assert (
            panel._content._material_schema_id.property("navigation_field_raw_label")
            == "input_source_profile.material_schema_id"
        )

        assert panel._content.focus_navigation_field("signature_assets_v1")
        assert (
            panel._content._material_schema_ids.property("navigation_field_highlight")
            is True
        )

        assert panel._content.focus_navigation_field("contract_no")
        assert (
            panel._content._required_material_fields.property(
                "navigation_field_highlight"
            )
            is True
        )

        assert panel._content.focus_navigation_field("legal_signature")
        assert (
            panel._content._required_image_roles.property("navigation_field_highlight")
            is True
        )

        assert panel._content.focus_navigation_field("input_source_profile.unknown") is False
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_content_detail_repairs_unknown_primary_material_schema():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(
        scene_id="contract_delivery",
        name="合同交付",
        category="contract_delivery",
        template_id="default",
        default_template_id="default",
        compatible_template_ids=["default"],
    )
    scene.input_source_profile.material_schema_id = "missing_primary_schema_v1"
    scene.input_source_profile.material_schema_ids = [
        "missing_primary_schema_v1",
        "contract_parties_v1",
        "missing_extra_schema_v1",
    ]
    template = create_builtin_template("default")
    bridge.set_current_scene(scene, config_id="contract_delivery", emit_signal=False)
    bridge.set_current_template(template, config_id="default", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        assert panel._content._schema_validation_summary.value_for(
            "schema_registry_status"
        ) == "未识别 2 个"
        assert panel._content._remove_unknown_schema_btn.isEnabled() is True

        panel._content._remove_unknown_schema_btn.click()
        app.processEvents()

        assert scene.input_source_profile.material_schema_id == "contract_parties_v1"
        assert scene.input_source_profile.material_schema_ids == ["contract_parties_v1"]
        assert panel._content._material_schema_id.text() == "contract_parties_v1"
        assert panel._content._material_schema_ids.get_text() == "contract_parties_v1"
        assert panel._content._schema_validation_summary.value_for(
            "schema_registry_status"
        ) == "通过"
        assert "合同方字段资料" in panel._content._schema_validation_summary.detail_for(
            "schema_labels"
        )
        assert "Contract party fields" in panel._content._schema_validation_summary.tooltip_for(
            "schema_labels"
        )
        assert panel._content._remove_unknown_schema_btn.isEnabled() is False
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_content_detail_replaces_unknown_material_schema_with_selected_registry_item():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(
        scene_id="contract_delivery",
        name="合同交付",
        category="contract_delivery",
        template_id="default",
        default_template_id="default",
        compatible_template_ids=["default"],
    )
    scene.input_source_profile.material_schema_id = "missing_primary_schema_v1"
    scene.input_source_profile.material_schema_ids = [
        "missing_primary_schema_v1",
        "contract_parties_v1",
        "missing_extra_schema_v1",
    ]
    template = create_builtin_template("default")
    bridge.set_current_scene(scene, config_id="contract_delivery", emit_signal=False)
    bridge.set_current_template(template, config_id="default", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        assert panel._content._schema_validation_summary.value_for(
            "schema_registry_status"
        ) == "未识别 2 个"
        assert panel._content._replace_unknown_schema_btn.isEnabled() is True
        assert "（推荐）" in panel._content._replace_unknown_schema_btn.toolTip()

        signature_index = panel._content._schema_registry_combo.findData("signature_assets_v1")
        assert signature_index >= 0
        panel._content._schema_registry_combo.setCurrentIndex(signature_index)
        app.processEvents()

        assert panel._content._replace_unknown_schema_btn.isEnabled() is True
        assert "signature_assets_v1" in panel._content._replace_unknown_schema_btn.toolTip()

        panel._content._replace_unknown_schema_btn.click()
        app.processEvents()

        assert scene.input_source_profile.material_schema_id == "signature_assets_v1"
        assert scene.input_source_profile.material_schema_ids == [
            "signature_assets_v1",
            "contract_parties_v1",
        ]
        assert panel._content._material_schema_id.text() == "signature_assets_v1"
        assert panel._content._material_schema_ids.get_text() == (
            "signature_assets_v1\ncontract_parties_v1"
        )
        assert panel._content._schema_validation_summary.value_for(
            "schema_registry_status"
        ) == "通过"
        assert "签章资料" in panel._content._schema_validation_summary.detail_for(
            "schema_labels"
        )
        assert "合同方字段资料" in panel._content._schema_validation_summary.detail_for(
            "schema_labels"
        )
        labels_tooltip = panel._content._schema_validation_summary.tooltip_for(
            "schema_labels"
        )
        assert "Signature and seal assets" in labels_tooltip
        assert "Contract party fields" in labels_tooltip
        assert panel._content._replace_unknown_schema_btn.isEnabled() is False
        assert panel._content._remove_unknown_schema_btn.isEnabled() is False
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_content_detail_recommends_replacement_for_unknown_material_schema():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(
        scene_id="contract_delivery",
        name="合同交付",
        category="contract_delivery",
        template_id="default",
        default_template_id="default",
        compatible_template_ids=["default"],
    )
    scene.input_source_profile.material_schema_id = "contract_parties_v1"
    scene.input_source_profile.material_schema_ids = [
        "contract_parties_v1",
        "signature_assets_v2",
    ]
    template = create_builtin_template("default")
    bridge.set_current_scene(scene, config_id="contract_delivery", emit_signal=False)
    bridge.set_current_template(template, config_id="default", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        assert panel._content._schema_registry_combo.currentData() == ""
        assert panel._content._schema_validation_summary.value_for(
            "schema_registry_status"
        ) == "未识别 1 个"
        assert panel._content._replace_unknown_schema_btn.isEnabled() is True
        assert "signature_assets_v1" in panel._content._replace_unknown_schema_btn.toolTip()
        assert "（推荐）" in panel._content._replace_unknown_schema_btn.toolTip()

        panel._content._replace_unknown_schema_btn.click()
        app.processEvents()

        assert scene.input_source_profile.material_schema_id == "contract_parties_v1"
        assert scene.input_source_profile.material_schema_ids == [
            "contract_parties_v1",
            "signature_assets_v1",
        ]
        assert panel._content._material_schema_ids.get_text() == (
            "contract_parties_v1\nsignature_assets_v1"
        )
        assert panel._content._schema_validation_summary.value_for(
            "schema_registry_status"
        ) == "通过"
        assert "签章资料" in panel._content._schema_validation_summary.detail_for(
            "schema_labels"
        )
        assert "Signature and seal assets" in panel._content._schema_validation_summary.tooltip_for(
            "schema_labels"
        )
        assert panel._content._replace_unknown_schema_btn.isEnabled() is False
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_content_detail_previews_attachment_schema_roles():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(
        scene_id="qualification_archive_packages",
        name="资质附件包",
        category="qualification_archive_packages",
        template_id="default",
        default_template_id="default",
        compatible_template_ids=["default"],
    )
    template = create_builtin_template("default")
    bridge.set_current_scene(scene, config_id="qualification_archive_packages", emit_signal=False)
    bridge.set_current_template(template, config_id="default", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        schema_index = panel._content._schema_registry_combo.findData(
            "qualification_archive_assets_v1"
        )
        assert schema_index >= 0
        panel._content._schema_registry_combo.setCurrentIndex(schema_index)
        panel._content._set_primary_schema_btn.click()
        app.processEvents()

        assert scene.input_source_profile.material_schema_id == "qualification_archive_assets_v1"
        assert panel._content._schema_validation_summary.value_for(
            "schema_registry_status"
        ) == "通过"
        assert "标书/资质归档" in panel._content._schema_validation_summary.detail_for(
            "schema_families"
        )
        assert "qualification_archive_packages" in panel._content._schema_validation_summary.tooltip_for(
            "schema_families"
        )
        assert panel._content._schema_validation_summary.value_for(
            "schema_fields"
        ) == "2 必填 / 9 全部"
        field_detail = panel._content._schema_validation_summary.detail_for("schema_fields")
        assert "机构名称（必填）" in field_detail
        assert "资料包名称（必填）" in field_detail
        assert "还有 4 项" in field_detail
        field_tooltip = panel._content._schema_validation_summary.tooltip_for("schema_fields")
        assert "organization · Organization · 必填" in field_tooltip
        assert "valid_until · Valid until · 可选" in field_tooltip
        assert "consortium_member_name · Consortium member name · 可选" in field_tooltip
        assert panel._content._schema_validation_summary.value_for(
            "schema_image_roles"
        ) == "无"
        assert panel._content._schema_validation_summary.value_for(
            "schema_attachment_roles"
        ) == "2 必填 / 3 全部"
        attachment_detail = panel._content._schema_validation_summary.detail_for(
            "schema_attachment_roles"
        )
        assert "资质证书（必填，图片 / PDF）" in attachment_detail
        assert "营业执照（必填，图片 / PDF）" in attachment_detail
        assert "附件（可选，图片 / PDF）" in attachment_detail
        attachment_tooltip = panel._content._schema_validation_summary.tooltip_for(
            "schema_attachment_roles"
        )
        assert "assets/01_certificates" in attachment_tooltip
        assert "assets/02_business_license" in attachment_tooltip
        assert "certificate · Qualification certificate · 必填 · image/pdf" in attachment_tooltip
        assert "business_license · Business license · 必填 · image/pdf" in attachment_tooltip
        assert "attachment · Supporting attachment · 可选 · image/pdf" in attachment_tooltip
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_delivery_validation_summary_flags_template_and_rule_issues():
    app = _app()
    bridge = PanelBridge()
    scene = create_thesis_scene()
    template = create_builtin_template("thesis_gbt")
    bridge.set_current_scene(scene, config_id="thesis", emit_signal=False)
    bridge.set_current_template(template, config_id="thesis_gbt", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        review_index = panel._output._default_delivery.findData("review")
        panel._output._default_delivery.setCurrentIndex(review_index)
        app.processEvents()

        panel._output._delivery_filename.setText("{stem}:{unknown}")
        panel._output._visibility_rules.set_text("answer=drop\n=remove\nanswer=hide")
        app.processEvents()

        assert panel._output._delivery_validation_summary.value_for(
            "delivery_template_status"
        ) == "需处理"
        template_detail = panel._output._delivery_validation_summary.detail_for(
            "delivery_template_status"
        )
        assert "未知变量: unknown" in template_detail
        assert "包含非法字符: :" in template_detail

        assert panel._output._delivery_validation_summary.value_for(
            "delivery_rule_status"
        ) == "需处理"
        rule_detail = panel._output._delivery_validation_summary.detail_for(
            "delivery_rule_status"
        )
        assert "未知处理动作: drop" in rule_detail
        assert "缺少内容块名" in rule_detail
        assert "重复内容块: 答案 (answer)" in rule_detail
        assert "selector" not in rule_detail

        panel._output._delivery_output_dir.setText("CON/{preset_id}.")
        panel._output._delivery_filename.setText("folder/{stem}")
        app.processEvents()

        path_detail = panel._output._delivery_validation_summary.detail_for(
            "delivery_template_status"
        )
        assert "包含 Windows 保留名: CON" in path_detail
        assert "路径段不能以空格或点结尾: preview." in path_detail
        assert "文件命名不应包含路径分隔符" in path_detail
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_delivery_business_preset_templates_create_common_versions():
    app = _app()
    bridge = PanelBridge()
    scene = create_thesis_scene()
    template = create_builtin_template("thesis_gbt")
    bridge.set_current_scene(scene, config_id="thesis", emit_signal=False)
    bridge.set_current_template(template, config_id="thesis_gbt", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        student_template_index = panel._output._delivery_preset_template_combo.findData(
            "student_version"
        )
        assert student_template_index >= 0
        panel._output._delivery_preset_template_combo.setCurrentIndex(student_template_index)
        panel._output._add_preset_template_btn.click()
        app.processEvents()

        student_preset = scene.delivery_presets[-1]
        assert student_preset.preset_id == "student_version"
        assert student_preset.label == "学生版"
        assert student_preset.output_dir_template == "{preset_id}"
        assert student_preset.filename_template == "{stem}_{preset_id}"
        assert scene.default_delivery_preset_id == "student_version"
        assert scene.output.compare_docx is False
        assert panel._output._visibility_rules.get_text() == (
            "answer=remove\nanalysis=remove\nsolution=remove"
        )
        assert [
            (rule.selector, rule.action)
            for rule in student_preset.content_visibility_rules
        ] == [
            ("answer", "remove"),
            ("analysis", "remove"),
            ("solution", "remove"),
        ]
        assert [
            rule.label
            for rule in student_preset.content_visibility_rules
        ] == [
            "答案",
            "解析",
            "解题过程",
        ]
        assert "显隐规则 3 条" in panel._output._delivery_summary.detail_for(
            "default_artifacts"
        )

        panel._output._add_preset_template_btn.click()
        app.processEvents()

        duplicate_student = scene.delivery_presets[-1]
        assert duplicate_student.preset_id == "student_version_2"
        assert duplicate_student.label == "学生版 2"
        assert scene.default_delivery_preset_id == "student_version_2"

        archive_template_index = panel._output._delivery_preset_template_combo.findData(
            "material_archive"
        )
        assert archive_template_index >= 0
        archive_template_tooltip = panel._output._delivery_preset_template_combo.itemData(
            archive_template_index,
            Qt.ToolTipRole,
        )
        assert "新增交付版本：资料归档包" in archive_template_tooltip
        assert "资料清单" in archive_template_tooltip
        assert "资料包" in archive_template_tooltip
        assert "详细报告" in archive_template_tooltip
        assert "模板编号：material_archive" in archive_template_tooltip
        panel._output._delivery_preset_template_combo.setCurrentIndex(archive_template_index)
        panel._output._add_preset_template_btn.click()
        app.processEvents()

        archive_preset = scene.delivery_presets[-1]
        assert archive_preset.preset_id == "material_archive"
        assert archive_preset.artifacts.material_manifest is True
        assert archive_preset.artifacts.material_package is True
        assert archive_preset.report_level == "detailed"
        assert scene.output.material_manifest is True
        assert scene.output.material_package is True
        assert "资料清单" in panel._output._delivery_summary.value_for("default_artifacts")
        assert "资料包" in panel._output._delivery_summary.value_for("default_artifacts")
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_applies_contract_family_recommended_delivery_defaults():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(
        scene_id="contract_delivery",
        name="合同交付",
        category="contract_delivery",
        template_id="default",
        default_template_id="default",
        compatible_template_ids=["default"],
    )
    template = create_builtin_template("default")
    bridge.set_current_scene(scene, config_id="contract_delivery", emit_signal=False)
    bridge.set_current_template(template, config_id="default", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        assert panel._output._apply_family_delivery_btn.isEnabled() is True
        family_delivery_tooltip = panel._output._apply_family_delivery_btn.toolTip()
        assert "场景类型：合同交付" in family_delivery_tooltip
        assert "将新增：合同审阅稿、合同签署稿、字段一致性报告" in family_delivery_tooltip
        assert "默认版本：合同审阅稿" in family_delivery_tooltip
        assert "版本 ID：review_copy, signing_copy, field_consistency_report" in family_delivery_tooltip

        panel._output._apply_family_delivery_btn.click()
        app.processEvents()

        preset_ids = [preset.preset_id for preset in scene.delivery_presets]
        assert "review_copy" in preset_ids
        assert "signing_copy" in preset_ids
        assert "field_consistency_report" in preset_ids
        assert scene.default_delivery_preset_id == "review_copy"
        assert scene.output.compare_docx is True

        assert scene.input_source_profile.material_schema_id == "contract_parties_v1"
        assert scene.input_source_profile.material_schema_ids == [
            "contract_parties_v1",
            "signature_assets_v1",
        ]
        assert "seal" in scene.input_source_profile.required_image_roles
        assert panel._content._input_summary.value_for("materials") == "必需"
        material_detail = panel._content._input_summary.detail_for("materials")
        assert "合同方字段资料" in material_detail
        assert "签章资料" in material_detail
        assert panel._content._input_summary.value_for("image_roles") == "1 个角色"
        assert "印章" in panel._content._input_summary.detail_for("image_roles")
        assert panel._cleanup._compliance_summary.value_for("count_profile") == "contract_fields"
        assert panel._cleanup._compliance_summary.value_for("planning_scan_targets") == "已应用"
        assert panel._output._delivery_summary.value_for("default_delivery") == "合同审阅稿"
        assert "对比稿" in panel._output._delivery_summary.value_for("default_artifacts")

        signing_index = panel._output._default_delivery.findData("signing_copy")
        assert signing_index >= 0
        panel._output._default_delivery.setCurrentIndex(signing_index)
        app.processEvents()

        assert scene.default_delivery_preset_id == "signing_copy"
        assert scene.output.material_manifest is True
        assert scene.output.material_package is True
        assert "资料清单" in panel._output._delivery_summary.value_for("default_artifacts")
        assert "资料包" in panel._output._delivery_summary.value_for("default_artifacts")
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_delivery_variable_picker_inserts_into_templates():
    app = _app()
    bridge = PanelBridge()
    scene = create_thesis_scene()
    template = create_builtin_template("thesis_gbt")
    bridge.set_current_scene(scene, config_id="thesis", emit_signal=False)
    bridge.set_current_template(template, config_id="thesis_gbt", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        review_index = panel._output._default_delivery.findData("review")
        panel._output._default_delivery.setCurrentIndex(review_index)
        app.processEvents()

        review_preset = next(preset for preset in scene.delivery_presets if preset.preset_id == "review")
        panel._output._delivery_output_dir.setText("review/")
        panel._output._delivery_output_dir.setCursorPosition(len("review/"))
        variable_index = panel._output._delivery_variable_combo.findData("preset_label")
        assert "preset_label" not in panel._output._delivery_variable_combo.itemText(
            variable_index
        )
        assert "{preset_label}" in panel._output._delivery_variable_combo.itemData(
            variable_index,
            Qt.ToolTipRole,
        )
        panel._output._delivery_variable_combo.setCurrentIndex(variable_index)
        panel._output._insert_output_variable_btn.click()
        app.processEvents()

        assert review_preset.output_dir_template == "review/{preset_label}"
        assert "review/审阅稿" in panel._output._delivery_validation_summary.detail_for(
            "delivery_template_status"
        )

        panel._output._delivery_filename.setText("{stem}_")
        panel._output._delivery_filename.setCursorPosition(len("{stem}_"))
        variable_index = panel._output._delivery_variable_combo.findData("preset_id")
        panel._output._delivery_variable_combo.setCurrentIndex(variable_index)
        panel._output._insert_filename_variable_btn.click()
        app.processEvents()

        assert review_preset.filename_template == "{stem}_{preset_id}"
        assert "document_review" in panel._output._delivery_validation_summary.detail_for(
            "delivery_template_status"
        )
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_delivery_visibility_rule_inserter_updates_current_preset():
    app = _app()
    bridge = PanelBridge()
    scene = create_thesis_scene()
    template = create_builtin_template("thesis_gbt")
    bridge.set_current_scene(scene, config_id="thesis", emit_signal=False)
    bridge.set_current_template(template, config_id="thesis_gbt", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        review_index = panel._output._default_delivery.findData("review")
        panel._output._default_delivery.setCurrentIndex(review_index)
        app.processEvents()

        review_preset = next(
            preset for preset in scene.delivery_presets if preset.preset_id == "review"
        )
        selector_index = panel._output._visibility_selector_combo.findData("answer")
        assert selector_index >= 0
        assert panel._output._visibility_selector_combo.itemText(selector_index) == "答案"
        assert "answer" in panel._output._visibility_selector_combo.itemData(
            selector_index,
            Qt.ToolTipRole,
        )
        panel._output._visibility_selector_combo.setCurrentIndex(selector_index)
        app.processEvents()
        assert panel._output._visibility_selector_input.text() == "answer"

        action_index = panel._output._visibility_action_combo.findData("hide")
        assert action_index >= 0
        panel._output._visibility_action_combo.setCurrentIndex(action_index)
        panel._output._insert_visibility_rule_btn.click()
        app.processEvents()

        assert panel._output._visibility_rules.get_text() == "answer=hide"
        assert panel._output._visibility_selector_combo.currentData() in ("", None)
        assert [
            (rule.selector, rule.action)
            for rule in review_preset.content_visibility_rules
        ] == [("answer", "hide")]
        assert [rule.label for rule in review_preset.content_visibility_rules] == ["答案"]
        assert panel._output._delivery_validation_summary.value_for(
            "delivery_rule_status"
        ) == "1 条"
        assert "显隐规则 1 条" in panel._output._delivery_summary.detail_for(
            "default_artifacts"
        )

        panel._output._visibility_selector_input.setText("{{#visibility:Answer}}")
        panel._output._insert_visibility_rule_btn.click()
        app.processEvents()

        assert panel._output._visibility_rules.get_text() == "answer=hide"
        assert len(review_preset.content_visibility_rules) == 1
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_delivery_target_template_combo_and_status():
    app = _app()
    bridge = PanelBridge()
    scene = create_thesis_scene()
    template = create_builtin_template("thesis_gbt")
    bridge.set_current_scene(scene, config_id="thesis", emit_signal=False)
    bridge.set_current_template(template, config_id="thesis_gbt", emit_signal=False)

    panel = ScenePanel(bridge)
    try:
        app.processEvents()

        review_index = panel._output._default_delivery.findData("review")
        panel._output._default_delivery.setCurrentIndex(review_index)
        app.processEvents()

        review_preset = next(preset for preset in scene.delivery_presets if preset.preset_id == "review")
        thesis_template_index = panel._output._delivery_target_template_combo.findData(
            "thesis_gbt"
        )
        assert thesis_template_index >= 0
        assert (
            "thesis_gbt"
            not in panel._output._delivery_target_template_combo.itemText(
                thesis_template_index
            )
        )
        thesis_template_tooltip = panel._output._delivery_target_template_combo.itemData(
            thesis_template_index,
            Qt.ToolTipRole,
        )
        assert "thesis_gbt" in thesis_template_tooltip

        panel._output._delivery_target_template_combo.setCurrentIndex(thesis_template_index)
        app.processEvents()

        assert review_preset.target_template_id == "thesis_gbt"
        assert panel._output._delivery_target_template.text() == "thesis_gbt"
        assert panel._output._delivery_validation_summary.value_for(
            "delivery_target_template"
        ) == "兼容模板"
        assert "thesis_gbt" in panel._output._delivery_validation_summary.detail_for(
            "delivery_target_template"
        )

        panel._output._delivery_target_template.setText("default")
        app.processEvents()

        assert panel._output._delivery_validation_summary.value_for(
            "delivery_target_template"
        ) == "非兼容"
        assert "default" in panel._output._delivery_validation_summary.detail_for(
            "delivery_target_template"
        )
        default_template_index = panel._output._delivery_target_template_combo.findData(
            "default"
        )
        assert default_template_index >= 0
        assert (
            "default"
            not in panel._output._delivery_target_template_combo.itemText(
                default_template_index
            )
        )
        default_template_tooltip = panel._output._delivery_target_template_combo.itemData(
            default_template_index,
            Qt.ToolTipRole,
        )
        assert "default" in default_template_tooltip

        panel._output._delivery_target_template.setText("missing_template_id")
        app.processEvents()

        assert panel._output._delivery_validation_summary.value_for(
            "delivery_target_template"
        ) == "需处理"
        assert "模板不存在: missing_template_id" in panel._output._delivery_validation_summary.detail_for(
            "delivery_target_template"
        )
    finally:
        panel.close()
        app.processEvents()
