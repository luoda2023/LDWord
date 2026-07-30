import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.ui.custom_themes import CustomThemeStore, CustomThemeStoreError
from src.shared.ui.theme import LIGHT, derive_theme_from_core
from src.shared.ui.theme import get_theme, set_theme
from src.qt_api import QDialog
from src.ui.panels import theme_panel
from src.ui.panels.theme_panel import ThemePanel, _themes_match


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


def test_custom_theme_store_rejects_invalid_entries_without_partial_load(tmp_path):
    target = tmp_path / "custom_themes.json"
    payload = [
        {"id": "ok", "name": "OK", "core": dict(_VALID_CORE)},
        {"id": "missing", "name": "Missing", "core": {"primary": "#111111"}},
        {"id": "bad", "name": "Bad", "core": None},
        "junk",
    ]
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    store = CustomThemeStore(target)
    with pytest.raises(CustomThemeStoreError, match=r"\$\[1\]"):
        store.load()

    assert store.entries == []
    assert json.loads(target.read_text(encoding="utf-8")) == payload


def test_custom_theme_store_blocks_writes_after_corrupt_json(tmp_path):
    target = tmp_path / "custom_themes.json"
    store = CustomThemeStore(target)
    existing = store.add("Existing", dict(_VALID_CORE))
    store.load()
    corrupt_bytes = b'{"not": "valid"'
    target.write_bytes(corrupt_bytes)

    with pytest.raises(CustomThemeStoreError, match="custom_theme_file_unreadable"):
        store.load()

    assert [entry.id for entry in store.entries] == [existing.id]
    with pytest.raises(CustomThemeStoreError, match="write_blocked"):
        store.add("Must not overwrite", dict(_VALID_CORE))
    with pytest.raises(CustomThemeStoreError, match="write_blocked"):
        store.save()
    assert target.read_bytes() == corrupt_bytes


def test_custom_theme_store_rejects_semantically_invalid_colors(tmp_path):
    target = tmp_path / "custom_themes.json"
    invalid_core = dict(_VALID_CORE, primary="not-a-color")
    target.write_text(
        json.dumps([{"id": "bad", "name": "Bad", "core": invalid_core}]),
        encoding="utf-8",
    )

    store = CustomThemeStore(target)
    with pytest.raises(CustomThemeStoreError, match="contains an invalid color"):
        store.load()


def test_theme_panel_surfaces_corrupt_store_and_disables_writes(
    tmp_path,
    monkeypatch,
    qapp,
):
    target = tmp_path / "custom_themes.json"
    corrupt_bytes = b"not-json"
    target.write_bytes(corrupt_bytes)
    store = CustomThemeStore(target)
    monkeypatch.setattr(theme_panel, "CustomThemeStore", lambda: store)

    panel = ThemePanel(None)
    try:
        assert panel._custom_theme_error.isHidden() is False
        assert "已停止自定义主题写入" in panel._custom_theme_error.text()
        assert panel._add_card.isEnabled() is False
        assert target.read_bytes() == corrupt_bytes
    finally:
        panel.close()
        panel.deleteLater()
        qapp.processEvents()


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


def _flow_widgets(flow):
    return [
        flow.itemAt(index).widget()
        for index in range(flow.count())
    ]


def test_theme_panel_add_and_delete_reconcile_only_target_card(
    tmp_path,
    monkeypatch,
    qapp,
):
    store = CustomThemeStore(tmp_path / "custom_themes.json")
    first = store.add("First", dict(_VALID_CORE))
    second_core = dict(_VALID_CORE, primary="#356AA0")
    second = store.add("Second", second_core)
    third_core = dict(_VALID_CORE, primary="#2F7657")

    monkeypatch.setattr(theme_panel, "CustomThemeStore", lambda: store)

    class _AcceptedThemeDialog:
        def __init__(self, _parent=None):
            pass

        def exec(self):
            return QDialog.Accepted

        def get_result(self):
            return "Third", third_core

    monkeypatch.setattr(theme_panel, "_ThemeEditorDialog", _AcceptedThemeDialog)

    previous_theme = get_theme()
    panel = ThemePanel(None)
    try:
        original_cards = dict(panel._custom_cards)
        original_add_card = panel._add_card

        panel._on_add_clicked()

        added = store.entries[-1]
        assert list(panel._custom_cards) == [first.id, second.id, added.id]
        assert panel._custom_cards[first.id] is original_cards[first.id]
        assert panel._custom_cards[second.id] is original_cards[second.id]
        assert panel._add_card is original_add_card
        assert _flow_widgets(panel._custom_flow) == [
            original_cards[first.id],
            original_cards[second.id],
            panel._custom_cards[added.id],
            original_add_card,
        ]

        added_card = panel._custom_cards[added.id]
        removed_card = panel._custom_cards[second.id]
        panel._on_delete_clicked(second.id)

        assert list(panel._custom_cards) == [first.id, added.id]
        assert panel._custom_cards[first.id] is original_cards[first.id]
        assert panel._custom_cards[added.id] is added_card
        assert panel._add_card is original_add_card
        assert removed_card not in _flow_widgets(panel._custom_flow)
        assert _flow_widgets(panel._custom_flow) == [
            original_cards[first.id],
            added_card,
            original_add_card,
        ]
    finally:
        set_theme(previous_theme)
        panel.close()
        panel.deleteLater()
        qapp.processEvents()
