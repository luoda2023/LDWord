"""
Test script to preview Workbench V2 panel.
"""

import sys

try:
    from ._bootstrap import ensure_project_root
except ImportError:
    from _bootstrap import ensure_project_root

ensure_project_root()

from src.qt_api import QApplication
from src.ui.panels.workbench.panel_v2 import WorkbenchPanelV2
from src.ui.bridge import PanelBridge


def main():
    app = QApplication(sys.argv)

    # Create bridge and panel
    bridge = PanelBridge()
    panel = WorkbenchPanelV2(bridge)
    panel.setWindowTitle('Workbench V2 Preview')
    panel.resize(1200, 800)
    panel.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
