import sys
from pathlib import Path

import pytest
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QFont, QRect, QSize, Qt
from src.shared.ui import Badge, DynamicNavigationRail, NavigationCard
from src.shared.ui.theme import get_theme
from src.shared.ui.tooltip import (
    TOOLTIP_PLACEMENT_PROPERTY,
    TOOLTIP_ROLE_PROPERTY,
    tooltip_position_for,
)


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
        assert home._title.font().weight() == QFont.Weight.Bold
        assert settings._title.font().weight() == QFont.Weight.Normal

        rail.select_card("settings")

        assert rail.selected_card_id() == "settings"
        assert rail.selected_card is settings
        assert home.is_selected() is False
        assert settings.is_selected() is True
        assert home._title.font().weight() == QFont.Weight.Normal
        assert settings._title.font().weight() == QFont.Weight.Bold
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


def test_navigation_subtitle_only_exposes_right_tooltip_when_elided(qapp):
    card = NavigationCard("report", "正文排版")
    full_text = "宋体/Times New Roman 小四，首行缩进2字符，固定行距28磅"
    try:
        card.resize(180, 70)
        card.show()
        qapp.processEvents()
        card.set_subtitle(full_text)

        assert card._subtitle.text() != full_text
        assert card._subtitle.toolTip() == full_text
        assert card._subtitle.property(TOOLTIP_PLACEMENT_PROPERTY) == "right"
        assert card._subtitle.property(TOOLTIP_ROLE_PROPERTY) == "nav"
        assert card._subtitle.font().pixelSize() == 12
        assert card._subtitle.font().weight() == QFont.Weight.Normal

        card.resize(720, 70)
        qapp.processEvents()
        card._update_elided_subtitle()

        assert card._subtitle.text() == full_text
        assert card._subtitle.toolTip() == ""
    finally:
        card.close()


def test_right_anchored_navigation_tooltip_does_not_cover_next_title(qapp):
    rail = DynamicNavigationRail()
    first = NavigationCard("style", "正文排版")
    second = NavigationCard("heading", "标题编号")
    try:
        rail.resize(320, 240)
        rail.add_card("style", first)
        rail.add_card("heading", second)
        first.set_subtitle("宋体/Times New Roman 小四，首行缩进2字符")
        rail.show()
        qapp.processEvents()

        popup_size = QSize(260, 40)
        popup_pos = tooltip_position_for(
            first._subtitle,
            popup_size,
            placement="right",
        )
        popup_rect = QRect(popup_pos, popup_size)
        next_title_rect = QRect(
            second._title.mapToGlobal(second._title.rect().topLeft()),
            second._title.size(),
        )

        assert popup_rect.intersects(next_title_rect) is False
    finally:
        rail.close()


def test_badge_supports_variant_state():
    _app()
    badge = Badge("5")
    try:
        assert badge.variant() == "neutral"
        badge.set_variant("danger")
        assert badge.variant() == "danger"
    finally:
        badge.close()


def test_dynamic_navigation_rail_rejects_duplicate_card_id():
    _app()
    rail = DynamicNavigationRail()
    try:
        rail.add_card("home", NavigationCard("home", "Home"))
        with pytest.raises(ValueError, match="duplicate card_id"):
            rail.add_card("home", NavigationCard("home", "Home duplicate"))
        assert rail.item_count == 1
    finally:
        rail.close()


def test_dynamic_navigation_rail_rejects_card_id_key_mismatch():
    _app()
    rail = DynamicNavigationRail()
    try:
        with pytest.raises(ValueError, match="card.key.*card_id"):
            rail.add_card("home", NavigationCard("settings", "Settings"))
    finally:
        rail.close()


def test_navigation_card_clicked_uses_left_button_only():
    app = _app()
    card = NavigationCard("home", "Home")
    try:
        events = []
        card.clicked.connect(lambda: events.append("clicked"))
        card.show()
        app.processEvents()

        QTest.mouseClick(card, Qt.RightButton)
        assert events == []

        QTest.mouseClick(card, Qt.LeftButton)
        assert events == ["clicked"]
    finally:
        card.close()


def test_badge_supports_error_variant():
    _app()
    badge = Badge("5")
    try:
        badge.set_variant("error")
        assert badge.variant() == "error"
        assert get_theme().error in badge._label.styleSheet()
    finally:
        badge.close()
