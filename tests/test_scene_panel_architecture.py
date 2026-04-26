import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.config.scene import SceneWorkspace
from src.config.builtin_templates import create_builtin_template
from src.ui.bridge import PanelBridge
from src.ui.panels.scene_panel import ScenePanel


def _app():
    return QApplication.instance() or QApplication([])


def test_scene_panel_page_elements_detail_defers_page_number_editing_to_template():
    source = (ROOT / "src/ui/panels/scene_panel.py").read_text(encoding="utf-8")

    assert "self._page_number = ToggleSwitch" not in source
    assert "hf.page_number_enabled =" not in source
    assert "self._page_elem.set_scene(scene, template)" in source
    assert "self._page_elem.set_scene(self._current_scene, template)" in source


def test_scene_panel_uses_shared_card_header_and_flow_scope_layout():
    source = (ROOT / "src/ui/panels/scene_panel.py").read_text(encoding="utf-8")

    assert "_make_card_header" not in source
    assert "_apply_cached_header_theme" not in source
    assert "QGridLayout" not in source
    assert "FlowLayout" in source
    assert '.set_header("当前场景", icon_name="target")' in source
    assert '.set_header("处理范围", icon_name="map-pin")' in source
    assert '.set_header("功能开关", icon_name="toggle-right")' in source


def test_scene_panel_page_elements_detail_shows_template_owned_page_number_summary():
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

        assert hasattr(panel._page_elem, "_page_number") is False
        assert panel._page_elem._page_number_owner.text().startswith("模板控制")
        assert "前置部分" in panel._page_elem._page_number_summary.text()
        assert panel._page_elem._page_number_compat_note.isHidden() is False
    finally:
        panel.close()
        app.processEvents()


def test_scene_panel_template_change_refreshes_page_number_summary():
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
        before = panel._page_elem._page_number_summary.text()

        updated_template = create_builtin_template("thesis_gbt")
        updated_template.header_footer.page_number_enabled = False
        bridge.set_current_template(updated_template, config_id="thesis_gbt")
        app.processEvents()

        after = panel._page_elem._page_number_summary.text()
        assert before != after
        assert "不显示页码" in after
    finally:
        panel.close()
        app.processEvents()
