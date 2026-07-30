"""Tests for heading panel locking — per-level override/inherit model.

Replaces old global-mode locking tests with per-level source-action tests.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.template import HeadingLevelBindingConfig, TemplateConfig
from src.qt_api import QApplication, Qt
from src.ui.adapters.heading_numbering_adapter import HeadingNumberingAdapter
from src.ui.bridge import PanelBridge
from src.ui.heading_numbering_logic import TEMPLATE_MODE_CUSTOM
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
        assert "__current_scheme_display__" not in values
        assert panel._preset_cb.placeholderText() == "当前配置（自定义）"
        assert panel._preset_cb.currentData() is None
        assert panel._adapter.detect_active_preset() is None
    finally:
        panel.close()
        app.processEvents()


def test_heading_numbering_adapter_binding_is_read_only_for_empty_scheme():
    template = TemplateConfig()
    before = template.heading_numbering.level_bindings.copy()
    adapter = HeadingNumberingAdapter()

    adapter.set_template(template)

    assert template.heading_numbering.level_bindings == before == {}
    assert adapter.detect_active_preset() is None


def test_heading_numbering_panel_scheme_actions_are_third_row_and_use_project_button_variants():
    app, panel = _build_panel()

    try:
        items = panel._scheme_form._items
        assert items.index(panel._preset_row) < items.index(panel._levels_row) < items.index(panel._scheme_actions_row)
        assert panel._scheme_open_folder_btn.property("variant") == "secondary"
        assert panel._scheme_open_folder_btn.text() == "打开方案文件夹"
        assert not hasattr(panel, "_scheme_save_as_btn")
        assert not hasattr(panel, "_scheme_update_btn")
        assert not hasattr(panel, "_scheme_delete_btn")
    finally:
        panel.close()
        app.processEvents()


def test_heading_numbering_panel_scheme_action_row_keeps_buttons_fully_visible():
    app, panel = _build_panel()

    try:
        panel.resize(960, 900)
        app.processEvents()

        buttons = (panel._scheme_open_folder_btn,)

        assert all(button.property("sizeClass") == "md" for button in buttons)
        assert panel._scheme_actions.layout().alignment() & Qt.AlignVCenter
        assert panel._scheme_actions.minimumHeight() >= max(
            button.sizeHint().height() for button in buttons
        )
        assert panel._scheme_actions_row.minimumHeight() > panel._scheme_actions.minimumHeight()
    finally:
        panel.close()
        app.processEvents()


def test_heading_numbering_panel_opens_user_scheme_folder(tmp_path, monkeypatch):
    import src.config.heading_presets as heading_presets
    from src.ui.panels import heading_numbering_panel as panel_module

    target_dir = tmp_path / "heading_numbering_schemes"
    opened_paths: list[str] = []

    def _fake_open_url(url):
        opened_paths.append(url.toLocalFile())
        return True

    monkeypatch.setattr(heading_presets, "USER_SCHEME_DIR", target_dir)
    monkeypatch.setattr(panel_module.QDesktopServices, "openUrl", _fake_open_url)

    app, panel = _build_panel()

    try:
        panel._on_scheme_open_folder_requested()
        app.processEvents()

        assert target_dir.is_dir()
        assert len(opened_paths) == 1
        assert Path(opened_paths[0]).resolve() == target_dir.resolve()
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


def test_panel_scheme_management_is_folder_only():
    app, panel = _build_panel()

    try:
        assert panel._scheme_open_folder_btn.text() == "打开方案文件夹"
        assert not hasattr(panel, "_on_scheme_save_as_requested")
        assert not hasattr(panel, "_on_scheme_update_requested")
        assert not hasattr(panel, "_on_scheme_delete_requested")
        assert not hasattr(panel, "_scheme_update_btn")
        assert not hasattr(panel, "_scheme_delete_btn")
    finally:
        panel.close()
        app.processEvents()


def test_panel_custom_template_mode_survives_rebuild_and_validates():
    app, panel = _build_panel()

    try:
        panel.set_save_enabled(True)
        panel._expert_editor_expanded = True
        panel._refresh_expert_summary()
        app.processEvents()

        panel._use_raw_cb.setChecked(True)
        app.processEvents()

        binding = panel._adapter.get_binding(1)
        assert binding.display_template_mode == TEMPLATE_MODE_CUSTOM
        assert panel._use_raw_cb.isChecked() is True
        assert panel._raw_template_edit.isEnabled() is True

        panel._rebuild_level_list()
        app.processEvents()

        binding = panel._adapter.get_binding(1)
        assert binding.display_template_mode == TEMPLATE_MODE_CUSTOM
        assert panel._use_raw_cb.isChecked() is True
        assert panel._raw_template_edit.isEnabled() is True

        panel._raw_template_edit.setText("{parent.nn}-{cn}")
        panel._on_raw_template_edited("{parent.nn}-{cn}")
        app.processEvents()

        assert panel._adapter.get_binding(1).display_template == "{parent.nn}-{cn}"
        assert panel._raw_template_error_label.text()
        assert panel._save_btn.isEnabled() is False
        assert not hasattr(panel, "_scheme_save_as_btn")

        panel._raw_template_edit.setText("第{cn}章")
        panel._on_raw_template_edited("第{cn}章")
        app.processEvents()

        assert panel._adapter.get_binding(1).display_template == "第{cn}章"
        assert panel._raw_template_error_label.text() == ""
        assert panel._save_btn.isEnabled() is True
    finally:
        panel.close()
        app.processEvents()


def test_panel_levels_change_shows_modified_scheme_state():
    """Changing max levels keeps the last applied scheme visible as modified."""
    app, panel = _build_panel()

    try:
        _select_builtin_preset(panel)
        app.processEvents()

        panel._levels_input.set_value(6, "")
        panel._on_levels_changed()
        app.processEvents()

        assert panel._adapter.detect_active_preset() is None
        assert panel._preset_cb.currentIndex() == -1
        assert panel._preset_cb.display_text() == "论文标准（内置，已修改）"
        assert "论文标准（内置，已修改）" not in [
            panel._preset_cb.itemText(index) for index in range(panel._preset_cb.count())
        ]
        assert panel._summary_grid.value_for("scheme") == "论文标准（内置，已修改）"
    finally:
        panel.close()
        app.processEvents()


def test_panel_custom_template_shows_custom_state_without_preset_compatibility():
    app, panel = _build_panel()
    custom_template = TemplateConfig()
    custom_template.heading_numbering.level_bindings = {
        "heading1": HeadingLevelBindingConfig(
            enabled=True,
            display_core_style="circled_decimal",
            display_template="第{cc}章",
        )
    }

    try:
        _select_builtin_preset(panel)
        panel._adapter.set_binding_field(1, "display_core_style", "roman_upper")
        panel._mark_dirty()
        app.processEvents()

        assert panel._preset_cb.display_text() == "论文标准（内置，已修改）"

        panel.on_template_changed(custom_template)
        app.processEvents()

        assert panel._adapter.detect_active_preset() is None
        assert panel._adapter.active_scheme_key() is None
        assert panel._preset_cb.currentIndex() == -1
        assert panel._preset_cb.display_text() == "当前配置（自定义）"
        assert panel._summary_grid.value_for("scheme") == "当前配置（自定义）"
    finally:
        panel.close()
        app.processEvents()
