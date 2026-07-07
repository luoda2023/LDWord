import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main
from src.qt_api import Qt


def test_gui_startup_keeps_pass_through_high_dpi_policy():
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "Qt.HighDpiScaleFactorRoundingPolicy.PassThrough" in source
    assert "RoundPreferFloor" not in source


def test_gui_startup_prefers_windows_cjk_font_with_full_hinting():
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert 'QFont("Microsoft YaHei")' in source
    assert 'QFont("Microsoft YaHei UI")' not in source
    assert "PreferFullHinting" in source


def test_gui_startup_wires_splash_to_main_window_readiness_signals():
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "from src.ui.startup_splash import StartupSplash" in source
    assert "splash = StartupSplash()" in source
    assert "splash.show()" in source
    assert "win.startup_status_changed.connect(splash.set_status)" in source
    assert "win.startup_ready.connect(_show_main_window)" in source
    assert "QTimer.singleShot(80, _reveal_main_window)" in source
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


def test_theme_font_family_prefers_windows_cjk_fonts_before_ui_variant():
    source = (ROOT / "src/shared/ui/theme.py").read_text(encoding="utf-8")

    assert "'Microsoft YaHei', 'Microsoft YaHei UI'" in source
    assert "'Microsoft YaHei UI'" in source
    assert "'Segoe UI Variable'" in source


def test_theme_exposes_explicit_emphasis_weights_for_windows_cjk_ui():
    source = (ROOT / "src/shared/ui/theme.py").read_text(encoding="utf-8")

    assert "font_weight_medium: int = 500" in source
    assert "font_weight_emphasis: int = 700" in source
    assert "button_font_weight: int = 700" in source


def test_high_frequency_panels_use_emphasis_weight_instead_of_hardcoded_600():
    quick_source = (ROOT / "src/ui/panels/workbench/quick_execution_detail.py").read_text(encoding="utf-8")
    scene_source = (ROOT / "src/ui/panels/scene_panel.py").read_text(encoding="utf-8")

    assert "font-weight: 600" not in quick_source
    assert "font-weight: 600" not in scene_source
    assert "t.font_weight_emphasis" in quick_source
    assert "t.font_weight_emphasis" in scene_source


def test_shared_navigation_surfaces_use_explicit_emphasis_weight():
    rail_source = (ROOT / "src/shared/ui/dynamic_navigation_rail.py").read_text(encoding="utf-8")
    card_source = (ROOT / "src/shared/ui/navigation_card.py").read_text(encoding="utf-8")
    detail_source = (ROOT / "src/ui/panels/workbench/feature_detail_panes.py").read_text(encoding="utf-8")

    assert "t.font_weight_emphasis" in rail_source
    assert "t.font_weight_emphasis" in card_source
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
