import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.engine import font_resolver


def test_canonicalize_font_name_repairs_legacy_mojibake():
    assert font_resolver.canonicalize_font_name("瀹嬩綋") == "宋体"


def test_resolve_font_returns_actual_available_cn_alias_family(monkeypatch):
    monkeypatch.setattr(font_resolver, "qt_font_families", lambda: ())
    monkeypatch.setattr(font_resolver, "list_system_fonts", lambda: {"SimSun"})

    assert font_resolver.resolve_font("宋体", lang="cn") == "SimSun"


def test_resolve_font_falls_back_to_available_english_family(monkeypatch):
    monkeypatch.setattr(font_resolver, "qt_font_families", lambda: ())
    monkeypatch.setattr(font_resolver, "list_system_fonts", lambda: {"Arial"})

    assert font_resolver.resolve_font("Missing Font", lang="en") == "Arial"
