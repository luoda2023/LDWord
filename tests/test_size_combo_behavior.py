import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui.size_combo import SizeCombo


def _app():
    return QApplication.instance() or QApplication([])


def test_size_combo_includes_named_and_numeric_font_size_sections():
    _app()
    combo = SizeCombo()

    try:
        item_texts = [combo.itemText(index) for index in range(combo.count())]

        assert "小四 (12磅)" in item_texts
        assert "10.5" in item_texts
        assert "72" in item_texts
    finally:
        combo.close()


def test_size_combo_popup_target_prefers_matching_numeric_section_for_pt_input():
    _app()
    combo = SizeCombo()

    try:
        combo.setEditText("12磅")

        target_index = combo._find_popup_target_index()

        assert combo.itemText(target_index) == "12"
    finally:
        combo.close()


def test_size_combo_popup_target_inserts_custom_numeric_value_when_missing():
    _app()
    combo = SizeCombo()

    try:
        initial_count = combo.count()
        combo.setEditText("13")

        target_index = combo._find_popup_target_index()

        assert combo.itemText(target_index) == "13"
        assert combo.itemData(target_index) == 13.0
        assert combo.count() == initial_count + 1
    finally:
        combo.close()
