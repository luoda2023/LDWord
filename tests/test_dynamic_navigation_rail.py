import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui import Badge, DynamicNavigationRail, NavigationCard


def _app():
    return QApplication.instance() or QApplication([])


def test_dynamic_navigation_rail_public_api_selects_and_emits_selected_card_id():
    _app()
    rail = DynamicNavigationRail()
    try:
        selected_ids = []
        rail.card_selected.connect(selected_ids.append)

        home = NavigationCard("home", "Home")
        settings = NavigationCard("settings", "Settings")
        rail.add_card("home", home)
        rail.add_card("settings", settings)

        assert rail.selected_card_id() == "home"
        assert rail.selected_card is home
        assert home.is_selected() is True
        assert settings.is_selected() is False

        rail.select_card("settings")

        assert rail.selected_card_id() == "settings"
        assert rail.selected_card is settings
        assert home.is_selected() is False
        assert settings.is_selected() is True
        assert selected_ids[-1] == "settings"
    finally:
        rail.close()


def test_dynamic_navigation_rail_remove_card_reselects_first_available():
    _app()
    rail = DynamicNavigationRail()
    try:
        home = NavigationCard("home", "Home")
        settings = NavigationCard("settings", "Settings")
        rail.add_card("home", home)
        rail.add_card("settings", settings)

        rail.select_card("settings")
        rail.remove_card("settings")

        assert rail.selected_card_id() == "home"
        assert rail.selected_card is home
        assert home.is_selected() is True
        assert rail.item_count == 1
    finally:
        rail.close()


def test_navigation_card_mutators_update_subtitle_and_badge():
    _app()
    card = NavigationCard("report", "Report")
    try:
        card.set_subtitle("Latest run summary")
        card.set_badge("3", variant="info")

        assert card._subtitle.text() == "Latest run summary"
        assert card._badge.text() == "3"
        assert card._badge.variant() == "info"
    finally:
        card.close()


def test_badge_supports_variant_state():
    _app()
    badge = Badge("5")
    try:
        assert badge.variant() == "neutral"
        badge.set_variant("danger")
        assert badge.variant() == "danger"
    finally:
        badge.close()
