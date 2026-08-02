import os
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QTextLayout

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main
from src.qt_api import QFont, Qt
from src.shared.ui.theme import LIGHT
from src.shared.ui.typography_policy import (
    BRAND_FONT_FAMILIES,
    CJK_UI_FONT_FAMILIES,
    LATIN_UI_FONT_FAMILIES,
    UI_FONT_FAMILIES,
    UI_FONT_FAMILY_QSS,
    application_font,
    brand_font,
    font_for_role,
    register_windows_ui_fonts_for_freetype,
    windows_yahei_font_paths,
    TextRole,
)


def test_gui_startup_keeps_pass_through_high_dpi_policy():
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "Qt.HighDpiScaleFactorRoundingPolicy.PassThrough" in source
    assert "RoundPreferFloor" not in source


def test_gui_startup_uses_cjk_ui_stack_with_native_hinting():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    font = application_font()

    assert "apply_application_typography(app)" in source
    assert tuple(font.families()) == UI_FONT_FAMILIES
    assert font.pixelSize() == 13
    assert font.hintingPreference() == QFont.HintingPreference.PreferDefaultHinting


def test_gui_registers_freetype_yahei_faces_before_importing_ui_widgets():
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    registration = source.index("register_windows_ui_fonts_for_freetype(")
    app_font = source.index("apply_application_typography(app)")
    main_window_import = source.index("from src.ui.main_window import MainWindow")

    assert registration < app_font < main_window_import


def test_windows_yahei_registration_contract_is_explicit_and_backend_scoped():
    paths = windows_yahei_font_paths(windows_dir=Path("X:/Windows"))
    assert [path.name for path in paths] == ["msyh.ttc", "msyhbd.ttc", "msyhl.ttc"]

    skipped = register_windows_ui_fonts_for_freetype("directwrite")
    assert skipped.attempted is False
    assert skipped.complete is False


def test_gui_startup_wires_splash_to_main_window_readiness_signals():
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "from src.ui.startup_splash import StartupSplash" in source
    assert "splash = StartupSplash()" in source
    assert "splash.show()" in source
    assert "win.startup_status_changed.connect(splash.set_status)" in source
    assert "win.startup_ready.connect(_show_main_window)" in source
    assert source.index("splash.show()") < source.index(
        "from src.ui.main_window import MainWindow"
    )
    assert "QTimer.singleShot(80, _reveal_main_window)" not in source
    assert "win.setWindowOpacity(0.0)" not in source
    assert "splash.finish_and_close()" in source


def test_quick_execution_drop_area_avoids_richtext_title_path():
    source = (ROOT / "src/ui/panels/workbench/quick_execution_drop_area.py").read_text(encoding="utf-8")

    assert "Qt.RichText" not in source
    assert "_build_title_text" in source
    assert "_build_title_html" not in source


def test_windows_text_rendering_guidelines_doc_exists_and_mentions_change_guardrails():
    source = (ROOT / "docs/WINDOWS_TEXT_RENDERING_GUIDELINES.md").read_text(encoding="utf-8")

    assert "WA_TranslucentBackground" in source
    assert "PassThrough" in source
    assert "RichText" in source
    assert "last-resort shell decision" in source


def test_theme_separates_cjk_ui_and_latin_brand_font_stacks():
    assert CJK_UI_FONT_FAMILIES == ("Microsoft YaHei", "Microsoft YaHei UI", "Segoe UI")
    assert LATIN_UI_FONT_FAMILIES == ("Segoe UI", "Microsoft YaHei", "Microsoft YaHei UI")
    assert UI_FONT_FAMILIES == CJK_UI_FONT_FAMILIES
    assert BRAND_FONT_FAMILIES == LATIN_UI_FONT_FAMILIES
    assert LIGHT.font_family == UI_FONT_FAMILY_QSS


def _glyph_run_families(text: str, font: QFont) -> list[tuple[str, str, int]]:
    layout = QTextLayout(text, font)
    layout.beginLayout()
    line = layout.createLine()
    line.setLineWidth(1000)
    layout.endLayout()
    resolved: list[tuple[str, str, int]] = []
    for run in layout.glyphRuns():
        raw_font = run.rawFont()
        resolved.append(
            (raw_font.familyName(), raw_font.styleName(), len(run.glyphIndexes()))
        )
    return resolved


@pytest.mark.skipif(sys.platform != "win32", reason="Windows system-font contract")
@pytest.mark.skipif(
    os.environ.get("QT_QPA_PLATFORM") == "offscreen",
    reason="QRawFont glyph-run inspection requires the native Windows backend",
)
def test_runtime_glyph_runs_follow_cjk_ui_and_latin_brand_roles():
    ui_runs = _glyph_run_families("标题 A1", application_font())
    brand_latin_runs = _glyph_run_families("A1", brand_font(pixel_size=13, weight=400))
    brand_mixed_runs = _glyph_run_families("标题 A1", brand_font(pixel_size=13, weight=400))
    active_runs = _glyph_run_families(
        "标题编号",
        font_for_role(TextRole.NAVIGATION_TITLE_ACTIVE),
    )

    assert ui_runs == [("Microsoft YaHei", "Regular", 5)]
    assert brand_latin_runs == [("Segoe UI", "Regular", 2)]
    assert {family for family, _style, _count in brand_mixed_runs} == {
        "Microsoft YaHei",
        "Segoe UI",
    }
    assert active_runs == [("Microsoft YaHei", "Bold", 4)]


def test_theme_exposes_explicit_emphasis_weights_for_windows_cjk_ui():
    assert LIGHT.font_weight_medium == 400
    assert LIGHT.font_weight_emphasis == 700
    assert LIGHT.button_font_weight == 700


def test_high_frequency_panels_use_emphasis_weight_instead_of_hardcoded_600():
    quick_source = (ROOT / "src/ui/panels/workbench/quick_execution_detail.py").read_text(encoding="utf-8")
    scene_source = (ROOT / "src/ui/panels/scene_panel.py").read_text(encoding="utf-8")

    assert "font-weight: 600" not in quick_source
    assert "font-weight: 600" not in scene_source
    assert "t.font_weight_emphasis" in quick_source
    assert "t.font_weight_emphasis" in scene_source


def test_shared_navigation_surfaces_use_semantic_title_role():
    rail_source = (ROOT / "src/shared/ui/dynamic_navigation_rail.py").read_text(encoding="utf-8")
    card_source = (ROOT / "src/shared/ui/navigation_card.py").read_text(encoding="utf-8")
    detail_source = (ROOT / "src/ui/panels/workbench/feature_detail_panes.py").read_text(encoding="utf-8")

    assert "t.font_weight_emphasis" in rail_source
    assert "apply_text_role(self._title, TextRole.NAVIGATION_TITLE)" in card_source
    assert "TextRole.NAVIGATION_TITLE_ACTIVE" in card_source
    assert "font-size:" not in card_source.split("# --- Title ---", 1)[1].split("# --- Subtitle ---", 1)[0]
    assert "font-weight:" not in card_source.split("# --- Title ---", 1)[1].split("# --- Subtitle ---", 1)[0]
    subtitle_block = card_source.split("# --- Subtitle ---", 1)[1].split("# --- Badge", 1)[0]
    assert "font-size:" not in subtitle_block
    assert "font-weight:" not in subtitle_block
    assert "theme.font_weight_emphasis" in detail_source


def test_template_master_detail_surfaces_follow_emphasis_weight_policy():
    panel_source = (ROOT / "src/ui/panels/template_panel.py").read_text(encoding="utf-8")
    reference_source = (ROOT / "src/ui/panels/template_reference_detail.py").read_text(encoding="utf-8")
    style_source = (ROOT / "src/ui/panels/template_style_detail.py").read_text(encoding="utf-8")

    assert "font-weight: 600" not in panel_source
    assert "t.font_weight_emphasis" in panel_source
    assert "theme.font_weight_emphasis" in reference_source
    assert "theme.font_weight_emphasis" in style_source


def test_windows_text_rendering_guidelines_capture_cjk_font_and_500_weight_guardrails():
    source = (ROOT / "docs/WINDOWS_TEXT_RENDERING_GUIDELINES.md").read_text(encoding="utf-8")

    assert "Microsoft YaHei UI" in source
    assert "Microsoft YaHei" in source
    assert "`font-weight: 500`" in source
