"""Tests for heading panel locking — per-level override/inherit model.

Replaces old global-mode locking tests with per-level source-action tests.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.template import TemplateConfig
from src.qt_api import QApplication
from src.ui.adapters.heading_numbering_adapter import HeadingNumberingAdapter
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel

_PRESET_KEY = "thesis_standard"


def _build_panel():
    app = QApplication.instance() or QApplication([])
    panel = HeadingNumberingPanel(PanelBridge())
    panel.on_template_changed(TemplateConfig())
    panel.show()
    app.processEvents()
    return app, panel


def _select_builtin_preset(panel: HeadingNumberingPanel) -> None:
    for index in range(panel._preset_cb.count()):
        data = panel._preset_cb.itemData(index)
        if data == _PRESET_KEY:
            panel._preset_cb.setCurrentIndex(index)
            return
    raise AssertionError("built-in preset not found")


def test_heading_numbering_panel_preset_combo_contains_only_real_presets():
    app, panel = _build_panel()

    try:
        values = [panel._preset_cb.itemData(index) for index in range(panel._preset_cb.count())]
        assert "__custom__" not in values
        assert panel._preset_cb.placeholderText() == "当前配置（自定义）"
    finally:
        panel.close()
        app.processEvents()


def test_heading_numbering_adapter_detects_preset_mismatch_for_enabled_and_toc_flags():
    adapter = HeadingNumberingAdapter()
    adapter.set_template(TemplateConfig())

    adapter.apply_preset(_PRESET_KEY)
    assert adapter.detect_active_preset() == _PRESET_KEY

    adapter.set_binding_field(1, "enabled", False)
    assert adapter.detect_active_preset() is None

    adapter.apply_preset(_PRESET_KEY)
    assert adapter.detect_active_preset() == _PRESET_KEY

    adapter.set_binding_field(1, "include_in_toc", False)
    assert adapter.detect_active_preset() is None


def test_heading_numbering_adapter_detects_preset_mismatch_when_visible_levels_expand_beyond_preset():
    adapter = HeadingNumberingAdapter()
    adapter.set_template(TemplateConfig())

    adapter.apply_preset(_PRESET_KEY)
    assert adapter.detect_active_preset() == _PRESET_KEY

    adapter.set_max_levels(6)
    assert adapter.detect_active_preset() is None


def test_adapter_per_level_binding_override():
    """New: is_level_binding_from_preset + reset_level_binding_to_preset."""
    adapter = HeadingNumberingAdapter()
    adapter.set_template(TemplateConfig())
    adapter.apply_preset(_PRESET_KEY)

    # Level 1 should initially match preset
    assert adapter.is_level_binding_from_preset(1) is True

    # After modifying, it should depart
    adapter.set_binding_field(1, "display_core_style", "roman_upper")
    assert adapter.is_level_binding_from_preset(1) is False

    # Reset should restore it
    assert adapter.reset_level_binding_to_preset(1) is True
    assert adapter.is_level_binding_from_preset(1) is True


def test_adapter_per_level_heading_style_override():
    """New: has_heading_style_override + remove_heading_style_override."""
    adapter = HeadingNumberingAdapter()
    adapter.set_template(TemplateConfig())

    # Initially no override
    assert adapter.has_heading_style_override(1) is False

    # Create override via set_heading_style_field
    adapter.set_heading_style_field(1, "font_cn", "宋体")
    assert adapter.has_heading_style_override(1) is True

    # Remove override
    assert adapter.remove_heading_style_override(1) is True
    assert adapter.has_heading_style_override(1) is False

    # Removing again returns False
    assert adapter.remove_heading_style_override(1) is False


def test_adapter_numbering_source_text():
    """New: numbering_source_text returns correct labels."""
    adapter = HeadingNumberingAdapter()
    adapter.set_template(TemplateConfig())
    adapter.apply_preset(_PRESET_KEY)

    text = adapter.numbering_source_text(1)
    assert "预设" in text

    adapter.set_binding_field(1, "display_core_style", "roman_upper")
    text = adapter.numbering_source_text(1)
    assert "自定义" in text


def test_adapter_last_applied_preset_key_preserved():
    """_last_applied_preset_key should survive individual binding edits."""
    adapter = HeadingNumberingAdapter()
    adapter.set_template(TemplateConfig())
    adapter.apply_preset(_PRESET_KEY)

    assert adapter._last_applied_preset_key == _PRESET_KEY

    # Editing a binding does not clear the key
    adapter.set_binding_field(1, "display_core_style", "roman_upper")
    assert adapter._last_applied_preset_key == _PRESET_KEY

    # So reset_level_binding_to_preset still works
    assert adapter.reset_level_binding_to_preset(1) is True
    assert adapter.is_level_binding_from_preset(1) is True


def test_panel_preset_selection_changes_levels():
    """Selecting a preset should update level bindings."""
    app, panel = _build_panel()

    try:
        _select_builtin_preset(panel)
        app.processEvents()

        assert panel._adapter.detect_active_preset() == _PRESET_KEY
        assert panel._preset_cb.currentData() == _PRESET_KEY
    finally:
        panel.close()
        app.processEvents()


def test_panel_levels_change_clears_preset_when_mismatched():
    """Changing max levels should make preset display show custom."""
    app, panel = _build_panel()

    try:
        _select_builtin_preset(panel)
        app.processEvents()

        panel._levels_input.set_value(6, "")
        panel._on_levels_changed()
        app.processEvents()

        assert panel._preset_cb.currentIndex() == -1
    finally:
        panel.close()
        app.processEvents()
