import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QSizePolicy
from src.shared.ui.option_toggle_chip import OptionToggleChip
from src.shared.ui.toggle_switch import ToggleSwitch


def _app():
    return QApplication.instance() or QApplication([])


def test_option_toggle_chip_wraps_existing_toggle():
    app = _app()
    toggle = ToggleSwitch(checked=True)
    chip = OptionToggleChip("Bold", toggle)

    try:
        chip.show()
        app.processEvents()

        assert chip.toggle() is toggle
        assert chip.label_widget().text() == "Bold"
        assert toggle.parent() is chip
        assert chip.layout().contentsMargins().left() == 12
    finally:
        chip.close()
        app.processEvents()


def test_option_toggle_chip_supports_inline_non_filling_mode():
    _app()
    chip = OptionToggleChip("Bold", variant="inline", fill=False)

    try:
        assert chip.sizePolicy().horizontalPolicy() == QSizePolicy.Fixed
        assert chip.layout().contentsMargins().left() == 0
        assert chip.layout().spacing() == 8
    finally:
        chip.close()


def test_template_style_panels_reuse_shared_option_toggle_chip():
    panel_paths = [
        ROOT / "src/ui/panels/template_style_detail.py",
        ROOT / "src/ui/panels/template_reference_detail.py",
        ROOT / "src/ui/panels/template_elements_toc.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in panel_paths)

    assert "OptionToggleChip(" in source
    assert "_build_toggle_chip" not in source
    assert "tpl_inline_label" not in source
    assert "tpl_style_toggle_chip" not in source
