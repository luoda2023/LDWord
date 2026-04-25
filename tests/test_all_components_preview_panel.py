import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import test_all_components as tac
from src.qt_api import QApplication
from src.shared.ui.calendar_month import CalendarMonth
from src.shared.ui.date_picker import DatePicker


def test_all_components_exposes_grouped_phase_metadata():
    assert hasattr(tac, "PHASE_COMPONENTS")

    phase_components = tac.PHASE_COMPONENTS
    phase_titles = [phase["title"] for phase in phase_components]

    assert phase_titles == ["Phase A", "Phase B", "Phase C", "Phase D"]
    assert sum(len(phase["components"]) for phase in phase_components) == 28
    assert phase_components[0]["components"] == ["Typography", "Divider", "TagChip", "Spin"]
    assert "CommandPalette" in phase_components[-1]["components"]
    assert "Form" in phase_components[-1]["components"]


def test_all_components_defines_navigation_preview_panel():
    assert hasattr(tac, "AllComponentsPreviewPanel")

    source = inspect.getsource(tac.AllComponentsPreviewPanel)

    assert "QListWidget" in source
    assert "QStackedWidget" in source
    assert "bind_theme(self, self._apply_theme)" in source
    assert "self._nav_list" in source
    assert "self._preview_stack" in source
    assert "self._theme_group" in source


def test_all_components_main_uses_preview_panel_window():
    source = (ROOT / "test_all_components.py").read_text(encoding="utf-8")

    assert "AllComponentsPreviewPanel" in source
    assert "window = AllComponentsPreviewPanel()" in source


def test_calendar_widgets_and_preview_panel_construct_successfully():
    app = QApplication.instance() or QApplication([])

    picker = DatePicker()
    calendar = CalendarMonth()
    panel = tac.AllComponentsPreviewPanel()

    assert picker.get_date() is not None
    assert calendar.get_selected() is None
    assert panel._preview_stack.count() == tac.TOTAL_COMPONENTS

    panel.close()
    calendar.close()
    picker.close()
    app.quit()
