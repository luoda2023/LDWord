import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, Qt
from src.ui.bridge import PanelBridge
from src.ui.panels.workbench.panel_v2 import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


def test_workbench_navigation_rail_renders_its_own_surface_background():
    app = _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        panel.resize(1200, 800)
        panel.show()
        app.processEvents()

        assert panel._nav_rail.testAttribute(Qt.WA_StyledBackground) is True

        image = panel.grab().toImage()
        left_bg = image.pixelColor(120, 350).name()
        right_bg = image.pixelColor(520, 350).name()

        assert left_bg != right_bg
    finally:
        panel.close()
        app.processEvents()
