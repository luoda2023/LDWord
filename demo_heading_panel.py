import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QFont, QMainWindow, QVBoxLayout, QWidget, Qt
from src.shared.ui.theme import get_theme
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.config.template import TemplateConfig

class DemoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Heading Numbering Panel Demo")
        self.resize(1000, 700)
        
        # main widget
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(20, 20, 20, 20)
        
        # Instantiate panel
        self.bridge = PanelBridge(self)
        self.panel = HeadingNumberingPanel(self.bridge, self)
        l.addWidget(self.panel)
        self.setCentralWidget(w)
        
        # Load dummy template config to active it
        dummy_template = TemplateConfig()
        self.panel.on_template_changed(dummy_template)


def main() -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except AttributeError:
        pass

    app = QApplication(sys.argv)
    theme = get_theme()
    font = QFont(theme.font_family.split(",")[0].strip("' "))
    font.setPointSize(10)
    app.setFont(font)

    win = DemoWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
