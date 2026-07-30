from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.qt_api import QFont, QImage, QPainter
from src.shared.ui.design_system_card import DesignSystemCard
from src.shared.ui.navigation_card import NavigationCard
from src.shared.ui.paint_geometry import snapped_pen_width
from src.shared.ui.theme import LIGHT
from src.shared.ui.typography_policy import (
    DEFAULT_TYPOGRAPHY,
    UI_FONT_FAMILIES,
    build_font,
)


ROOT = Path(__file__).resolve().parent.parent


def test_production_and_test_application_share_integer_pixel_typography(qapp):
    font = qapp.font()

    assert tuple(font.families()) == UI_FONT_FAMILIES
    assert font.pixelSize() == 13
    assert font.pointSizeF() == -1.0
    assert font.hintingPreference() == QFont.HintingPreference.PreferDefaultHinting


def test_theme_compatibility_sizes_derive_from_single_typography_scale():
    assert (
        LIGHT.font_size_xs,
        LIGHT.font_size_sm,
        LIGHT.font_size_md,
        LIGHT.font_size_lg,
        LIGHT.font_size_xl,
        LIGHT.font_size_xxl,
    ) == (
        DEFAULT_TYPOGRAPHY.micro_px,
        DEFAULT_TYPOGRAPHY.caption_px,
        DEFAULT_TYPOGRAPHY.body_px,
        DEFAULT_TYPOGRAPHY.subtitle_px,
        DEFAULT_TYPOGRAPHY.title_px,
        DEFAULT_TYPOGRAPHY.page_title_px,
    )


def test_font_builder_rejects_fractional_or_non_positive_logical_sizes():
    with pytest.raises(TypeError):
        build_font(UI_FONT_FAMILIES, pixel_size=13.87)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        build_font(UI_FONT_FAMILIES, pixel_size=0)


def test_navigation_title_role_restores_selected_emphasis_without_geometry_change(qapp):
    card = NavigationCard("tpl_heading", "标题编号", icon_name="list-ordered")
    try:
        before = card._title.font()
        assert before.pixelSize() == DEFAULT_TYPOGRAPHY.navigation_title_px == 13
        assert before.weight() == QFont.Weight.Normal
        assert before.hintingPreference() == QFont.HintingPreference.PreferDefaultHinting
        assert tuple(before.families()) == UI_FONT_FAMILIES

        card.set_selected(True)
        after = card._title.font()
        assert after.pixelSize() == before.pixelSize()
        assert after.weight() == QFont.Weight.Bold
        assert tuple(after.families()) == tuple(before.families())
        assert after.hintingPreference() == before.hintingPreference()

        card.set_selected(False)
        card._hovered = True
        card._apply_navigation_theme()
        assert card._title.font().weight() == QFont.Weight.Normal
    finally:
        card.deleteLater()


def test_fractional_dpr_stroke_maps_to_integer_physical_pixels():
    image = QImage(175, 100, QImage.Format.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(1.75)
    painter = QPainter(image)
    try:
        logical_width = snapped_pen_width(1.0, painter)
    finally:
        painter.end()

    assert logical_width == 2 / 1.75
    assert logical_width * 1.75 == 2.0


def test_content_card_has_no_descendant_graphics_effect(qapp):
    card = DesignSystemCard("字体与边线")
    try:
        assert card.graphicsEffect() is None
    finally:
        card.deleteLater()


def test_main_window_shadow_effect_is_attached_to_background_only_sibling():
    source = (ROOT / "src/ui/main_window.py").read_text(encoding="utf-8")

    assert "self._shadow_surface.setGraphicsEffect(self._shadow)" in source
    assert "self._container.setGraphicsEffect(self._shadow)" not in source


def test_icon_catalog_does_not_bind_pixmaps_to_application_dpr():
    source = (ROOT / "src/shared/ui/icons/catalog.py").read_text(encoding="utf-8")

    assert "app.devicePixelRatio()" not in source
    assert "_SUPPORTED_DPRS" in source
    assert "pixmap.setDevicePixelRatio(dpr)" in source


def test_ui_sources_do_not_reintroduce_fractional_font_sizes_or_500_600_weights():
    roots = (ROOT / "src/ui", ROOT / "src/shared/ui")
    fractional_font_size = re.compile(r"font-size\s*:\s*\d+\.\d+px")
    ambiguous_weight = re.compile(r"font-weight\s*:\s*(?:500|600)\s*;")
    violations: list[str] = []

    for root in roots:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if fractional_font_size.search(source) or ambiguous_weight.search(source):
                violations.append(str(path.relative_to(ROOT)))

    assert violations == []
