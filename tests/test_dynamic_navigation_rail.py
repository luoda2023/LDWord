import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui import DynamicNavigationRail


def _app():
    return QApplication.instance() or QApplication([])


def test_dynamic_navigation_rail_add_select_and_selected_card_state():
    _app()
    rail = DynamicNavigationRail()
    try:
        home = rail.add_item("home", "Home")
        settings = rail.add_item("settings", "Settings")

        assert rail.selected_key == "home"
        assert rail.selected_card is home
        assert home.is_selected() is True
        assert settings.is_selected() is False

        rail.select_item("settings")

        assert rail.selected_key == "settings"
        assert rail.selected_card is settings
        assert home.is_selected() is False
        assert settings.is_selected() is True
    finally:
        rail.close()


def test_dynamic_navigation_rail_remove_selected_reselects_first_available():
    _app()
    rail = DynamicNavigationRail()
    try:
        home = rail.add_item("home", "Home")
        settings = rail.add_item("settings", "Settings")

        rail.select_item("settings")
        rail.remove_item("settings")

        assert rail.selected_key == "home"
        assert rail.selected_card is home
        assert home.is_selected() is True
        assert rail.item_count == 1
    finally:
        rail.close()
