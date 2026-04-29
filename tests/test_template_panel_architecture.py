import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.config.scene import SceneWorkspace
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.ui.panels.template_format import TEMPLATE_PREVIEW_SPECS
from src.ui.panels.template_panel import TemplatePanel


def _app():
    return QApplication.instance() or QApplication([])


def test_template_panel_uses_shared_detail_controller_for_detail_switching():
    panel_source = inspect.getsource(TemplatePanel)
    module_source = (ROOT / "src/ui/panels/template_panel.py").read_text(encoding="utf-8")

    assert "from src.ui.panels.workbench.detail_controller import WorkbenchDetailController" in module_source
    assert "self._details = WorkbenchDetailController(" in panel_source
    assert "self._details.register_details(self._detail_map)" in panel_source
    assert "self._details.show_detail(card_id)" in panel_source


def test_template_panel_hides_unselected_details_inside_detail_container():
    _app()
    panel = TemplatePanel(PanelBridge())
    try:
        assert panel._current_detail is panel._overview_detail

        for card_id, detail in panel._detail_map.items():
            assert detail.parent() is panel._detail_container
            if card_id == "tpl_overview":
                assert detail.isHidden() is False
            else:
                assert detail.isHidden() is True
    finally:
        panel.close()


def test_template_panel_builtin_selection_loads_real_template_config():
    _app()
    panel = TemplatePanel(PanelBridge())
    try:
        combo_index = next(
            index
            for index in range(panel._overview_detail._combo.count())
            if panel._overview_detail._combo.itemData(index) == "thesis_gbt"
        )
        thesis_name = panel._overview_detail._combo.itemText(combo_index)

        panel._on_template_selected(combo_index)

        assert panel._current_template_id == "thesis_gbt"
        assert panel._current_template.name == thesis_name
        assert panel._current_template.page_setup.margin.top_cm == 3.8
        assert "body" in panel._current_template.styles
        assert panel._current_template.styles["body"].font_cn == "宋体"
        assert "heading1" in panel._current_template.heading_numbering.level_bindings
    finally:
        panel.close()


def test_template_panel_selector_uses_primary_scene_templates_when_no_scene_context():
    _app()
    panel = TemplatePanel(PanelBridge())
    try:
        option_ids = [
            panel._overview_detail._combo.itemData(index)
            for index in range(panel._overview_detail._combo.count())
        ]

        assert option_ids == [
            "default",
            "thesis_gbt",
            "bid_engineering",
            "official_gbt",
            "tech_standard",
            "report_default",
        ]
    finally:
        panel.close()


def test_template_panel_selector_scopes_to_current_scene_compatible_templates():
    _app()
    bridge = PanelBridge()
    bridge.set_current_scene(
        SceneWorkspace(
            scene_id="thesis",
            template_id="thesis_gbt",
            default_template_id="thesis_gbt",
            compatible_template_ids=["thesis_gbt", "thesis_custom"],
        ),
        config_id="thesis",
        source="library",
        emit_signal=False,
    )
    panel = TemplatePanel(bridge)
    try:
        option_ids = [
            panel._overview_detail._combo.itemData(index)
            for index in range(panel._overview_detail._combo.count())
        ]

        assert option_ids == ["thesis_gbt", "thesis_custom"]
    finally:
        panel.close()


def test_template_panel_registers_overview_rows_and_details_for_every_preview_group():
    _app()
    panel = TemplatePanel(PanelBridge())
    try:
        expected_detail_ids = {spec.detail_card_id for spec in TEMPLATE_PREVIEW_SPECS}

        assert set(panel._overview_detail._rows) == {spec.group_id for spec in TEMPLATE_PREVIEW_SPECS}
        assert expected_detail_ids.issubset(panel._detail_map)
        assert expected_detail_ids.issubset(panel._nav_cards)
    finally:
        panel.close()


def test_template_panel_reuses_heading_numbering_panel_for_heading_detail():
    _app()
    panel = TemplatePanel(PanelBridge())
    try:
        assert isinstance(panel._heading_detail, HeadingNumberingPanel)
        assert panel._heading_detail._adapter.has_template is True
    finally:
        panel.close()


def test_template_panel_reformat_toggle_updates_scene_module_switches():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    bridge.set_current_scene(scene, config_id="custom", source="library", emit_signal=False)
    panel = TemplatePanel(bridge)
    toggled: list[tuple[str, bool]] = []
    bridge.module_toggled.connect(lambda module_name, enabled: toggled.append((module_name, enabled)))

    try:
        panel._ensure_detail_loaded("tpl_page")
        card = panel._reformat_toggle_cards["tpl_page"]

        card._toggle.click()
        app.processEvents()

        assert scene.module_switches["page_setup"] is False
        assert scene.module_switches["section_format"] is False
        assert bridge.is_scene_dirty() is True
        assert ("page_setup", False) in toggled
        assert ("section_format", False) in toggled
        assert card._status_label.text() == "当前场景：已跳过"
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_heading_reformat_toggle_keeps_heading_recognition_available():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    bridge.set_current_scene(scene, config_id="custom", source="library", emit_signal=False)
    panel = TemplatePanel(bridge)

    try:
        panel._ensure_detail_loaded("tpl_heading")
        panel._reformat_toggle_cards["tpl_heading"]._toggle.click()
        app.processEvents()

        assert scene.module_switches["heading_numbering"] is False
        assert scene.module_switches["heading_recognition"] is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_reformat_toggle_disables_without_scene_context():
    app = _app()
    panel = TemplatePanel(PanelBridge())

    try:
        panel._ensure_detail_loaded("tpl_caption")
        card = panel._reformat_toggle_cards["tpl_caption"]

        assert card._toggle.isEnabled() is False
        assert card._status_label.text() == "未绑定当前场景"
    finally:
        panel.close()
        app.processEvents()
