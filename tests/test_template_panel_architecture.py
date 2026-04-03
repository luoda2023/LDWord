import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.ui.panels.template_format import TEMPLATE_PREVIEW_SPECS
from src.ui.panels.template_panel import TemplatePanel
from src.ui.panels.workbench.scene_presets import SCENE_METAS


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
        thesis_index = next(
            index
            for index, scene_meta in enumerate(SCENE_METAS)
            if scene_meta.default_template_id == "thesis_gbt"
        )
        thesis_name = SCENE_METAS[thesis_index].compatible_templates[0].name

        combo_index = next(
            index
            for index in range(panel._overview_detail._combo.count())
            if panel._overview_detail._combo.itemText(index) == thesis_name
        )

        panel._on_template_selected(combo_index)

        assert panel._current_template.name == thesis_name
        assert panel._current_template.page_setup.margin.top_cm == 3.8
        assert panel._current_template.header_footer.header_mode == "styleref"
        assert panel._current_template.toc.mode == "word_native"
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
