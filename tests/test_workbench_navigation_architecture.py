import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ui.panels.workbench.navigation_controller import WorkbenchNavigationController
from src.ui.panels.workbench.panel_v2 import WorkbenchPanel
from src.config.scene_presets import (
    CAPABILITY_FEATURE_CARD_DEFINITIONS,
    CAPABILITY_FEATURE_CARD_ORDER,
    UI_GROUP_MAP,
)


def test_workbench_panel_uses_navigation_controller_for_card_coordination():
    panel_source = inspect.getsource(WorkbenchPanel)
    module_source = (ROOT / "src/ui/panels/workbench/panel_v2.py").read_text(encoding="utf-8")

    assert "from .navigation_controller import WorkbenchNavigationController" in module_source
    assert "self._navigation = WorkbenchNavigationController(" in panel_source
    assert "self._navigation_cards = self._navigation.navigation_cards" in panel_source
    assert "self._dynamic_cards = self._navigation.dynamic_cards" in panel_source
    assert "self._navigation.refresh_fixed_cards(" in panel_source
    assert "self._navigation.sync_dynamic_cards()" in panel_source


def test_navigation_controller_owns_snapshot_and_dynamic_card_logic():
    controller_source = inspect.getsource(WorkbenchNavigationController)

    assert "def build_quick_execute_snapshot" in controller_source
    assert "config_management" not in controller_source
    assert "def refresh_fixed_cards" in controller_source
    assert "def sync_dynamic_cards" in controller_source
    assert "def open_feature_card" in controller_source
    assert "NavigationCard(" in controller_source


def test_workbench_panel_uses_shared_capability_feature_card_registry():
    module_source = (ROOT / "src/ui/panels/workbench/panel_v2.py").read_text(encoding="utf-8")
    detail_source = (
        ROOT / "src/ui/panels/workbench/feature_detail_panes.py"
    ).read_text(encoding="utf-8")

    assert CAPABILITY_FEATURE_CARD_ORDER == (
        "table_chart",
        "citation",
    )
    assert CAPABILITY_FEATURE_CARD_DEFINITIONS["table_chart"] == ("图表处理", "table")
    assert "content_fill" not in CAPABILITY_FEATURE_CARD_DEFINITIONS
    assert "content_fill" in UI_GROUP_MAP
    assert "cleanup" not in CAPABILITY_FEATURE_CARD_DEFINITIONS
    assert "cleanup" not in UI_GROUP_MAP
    assert "page_elements" not in CAPABILITY_FEATURE_CARD_DEFINITIONS
    assert "page_elements" not in UI_GROUP_MAP
    assert "figure_table_center" in UI_GROUP_MAP["table_chart"].module_names
    assert all(
        "validation" not in group.module_names
        for group in UI_GROUP_MAP.values()
    )
    assert "CAPABILITY_FEATURE_CARD_ORDER" in module_source
    assert "CAPABILITY_FEATURE_CARD_DEFINITIONS" in module_source
    assert "ContentDataDetailPane" not in module_source
    assert '"content_fill"' not in module_source
    assert "ContentDataDetailPane" not in detail_source
    assert "默认填充流程" not in detail_source
