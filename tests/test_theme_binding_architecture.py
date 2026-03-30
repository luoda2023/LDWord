import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.ui.theme import bind_theme


def test_bind_theme_source_registers_auto_cleanup():
    source = inspect.getsource(bind_theme)

    assert "on_theme_changed" in source
    assert "off_theme_changed" in source
    assert "destroyed.connect" in source


def test_theme_aware_widgets_use_bind_theme_helper():
    target_files = [
        "src/shared/ui/card.py",
        "src/shared/ui/collapsible_section.py",
        "src/shared/ui/form_row.py",
        "src/shared/ui/icon_button.py",
        "src/shared/ui/override_badge.py",
        "src/shared/ui/placeholder_edit.py",
        "src/shared/ui/progress_indicator.py",
        "src/shared/ui/search_input.py",
        "src/shared/ui/status_indicator.py",
        "src/shared/ui/styled_combo_box.py",
        "src/shared/ui/style_preview.py",
        "src/shared/ui/toggle_switch.py",
        "src/ui/main_window.py",
        "src/ui/sidebar.py",
        "src/ui/title_bar.py",
        "src/ui/panels/heading_numbering_panel.py",
    ]

    for relative_path in target_files:
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "bind_theme(" in source, f"{relative_path} should use bind_theme()"
        assert "on_theme_changed(" not in source, f"{relative_path} should not subscribe directly"
