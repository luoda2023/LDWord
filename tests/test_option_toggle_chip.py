import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QSizePolicy
from src.shared.ui.feature_toggle_row import FeatureToggleRow
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


def test_option_toggle_chip_compact_variant_keeps_contained_chrome_shorter():
    _app()
    chip = OptionToggleChip("Bold", variant="compact")
    default_chip = OptionToggleChip("Bold")

    try:
        margins = chip.layout().contentsMargins()
        assert margins.left() == 10
        assert margins.top() == 4
        assert chip.layout().spacing() == 8
        assert chip.sizeHint().height() < default_chip.sizeHint().height()
    finally:
        chip.close()
        default_chip.close()


def test_binary_toggle_primitives_document_their_roles():
    assert "OptionToggleChip" in (ToggleSwitch.__doc__ or "")
    assert "FeatureToggleRow" in (ToggleSwitch.__doc__ or "")
    assert "form row" in (OptionToggleChip.__doc__ or "")
    assert "feature" in (FeatureToggleRow.__doc__ or "").lower()


def test_template_style_panels_reuse_shared_option_toggle_chip():
    panel_paths = [
        ROOT / "src/ui/panels/template_style_detail.py",
        ROOT / "src/ui/panels/template_reference_detail.py",
        ROOT / "src/ui/panels/template_elements_toc.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in panel_paths)
    helper_source = (ROOT / "src/shared/ui/typography_controls.py").read_text(encoding="utf-8")

    assert "build_emphasis_widget" in source
    assert "OptionToggleChip(" in helper_source
    assert "_build_toggle_chip" not in source
    assert "tpl_inline_label" not in source
    assert "tpl_style_toggle_chip" not in source
