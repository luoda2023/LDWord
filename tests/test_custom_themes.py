import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.ui.custom_themes import CustomThemeStore
from src.shared.ui.theme import LIGHT, derive_theme_from_core
from src.ui.panels.theme_panel import _themes_match


_VALID_CORE = {
    "primary": "#4A7FC5",
    "accent": "#D4883A",
    "bg_window": "#F2F4F6",
    "bg_card": "#FFFFFF",
    "bg_sidebar": "#E2E6EA",
    "text_primary": "#1A2030",
}


def test_custom_theme_store_writes_to_injected_path(tmp_path):
    target = tmp_path / "custom_themes.json"

    store = CustomThemeStore(target)
    entry = store.add("My Theme", dict(_VALID_CORE))

    assert target.exists()
    assert store.path == target

    reloaded = CustomThemeStore(target)
    reloaded.load()

    assert len(reloaded.entries) == 1
    assert reloaded.entries[0].id == entry.id
    assert reloaded.entries[0].name == "My Theme"
    assert reloaded.entries[0].core == _VALID_CORE


def test_custom_theme_store_skips_invalid_entries(tmp_path):
    target = tmp_path / "custom_themes.json"
    payload = [
        {"id": "ok", "name": "OK", "core": dict(_VALID_CORE)},
        {"id": "missing", "name": "Missing", "core": {"primary": "#111111"}},
        {"id": "bad", "name": "Bad", "core": None},
        "junk",
    ]
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    store = CustomThemeStore(target)
    store.load()

    assert [entry.id for entry in store.entries] == ["ok"]
    assert store.entries[0].to_app_theme().primary == _VALID_CORE["primary"]


def test_theme_matching_uses_full_theme_payload_not_just_two_fields():
    custom = derive_theme_from_core(
        primary=LIGHT.primary,
        accent="#FF4D4F",
        bg_window=LIGHT.bg_window,
        bg_card="#FFF7E6",
        bg_sidebar="#E6F4FF",
        text_primary="#1F1F1F",
    )

    assert LIGHT.primary == custom.primary
    assert LIGHT.bg_window == custom.bg_window
    assert LIGHT.accent != custom.accent
    assert _themes_match(LIGHT, custom) is False
