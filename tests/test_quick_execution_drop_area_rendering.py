import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.panels.workbench.quick_execution_drop_area import QuickExecutionDropArea


def _app():
    return QApplication.instance() or QApplication([])


def test_quick_execution_drop_area_paints_border_on_all_four_sides():
    app = _app()
    area = QuickExecutionDropArea()
    try:
        area.resize(1100, 130)
        area.show()
        app.processEvents()

        pixmap = area.grab()
        image = pixmap.toImage()
        width = image.width()
        height = image.height()
        center = image.pixelColor(width // 2, height // 2).name()
        top_mid = image.pixelColor(width // 2, 0).name()
        left_mid = image.pixelColor(0, height // 2).name()
        right_mid = image.pixelColor(width - 1, height // 2).name()
        bottom_mid = image.pixelColor(width // 2, height - 1).name()

        assert top_mid != center
        assert left_mid != center
        assert right_mid != center
        assert bottom_mid != center
    finally:
        area.close()
        app.processEvents()
