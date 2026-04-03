import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_theme_panel_cards_use_shared_rounded_surface_and_tokenized_radii():
    source = (ROOT / "src/ui/panels/theme_panel.py").read_text(encoding="utf-8")

    assert "from src.shared.ui.rounded_surface import RoundedSurfaceFrame" in source
    assert "class _ThemeSwatchCard(RoundedSurfaceFrame):" in source
    assert "class _AddThemeCard(RoundedSurfaceFrame):" in source
    assert "configure_surface(" in source
    assert "border-radius: 18px;" not in source
    assert "t.radius_full" in source
