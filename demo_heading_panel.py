import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QFont, QMainWindow, QVBoxLayout, QWidget, Qt

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
try:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
except AttributeError:
    pass

app = QApplication(sys.argv)

from src.shared.ui.theme import get_theme
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.config.template import TemplateConfig

t = get_theme()
font = QFont(t.font_family.split(",")[0].strip("' "))
font.setPointSize(10)
app.setFont(font)

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
        self.panel = HeadingNumberingPanel(self)
        l.addWidget(self.panel)
        self.setCentralWidget(w)
        
        # Load dummy template config to active it
        dummy_template = TemplateConfig()
        self.panel.on_template_changed(dummy_template)
        
win = DemoWindow()
win.show()
sys.exit(app.exec())
