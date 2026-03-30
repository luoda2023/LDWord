import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import demo_style_gallery as dsg


def test_demo_gallery_no_longer_defines_private_formal_combo_or_search_widgets():
    source = inspect.getsource(dsg)

    assert "class _StyledComboBox" not in source
    assert "class _SearchLineEdit" not in source


def test_demo_gallery_uses_button_variant_helper_instead_of_button_object_names():
    source = inspect.getsource(dsg)

    assert 'setObjectName("btn_primary")' not in source
    assert 'setObjectName("btn_secondary")' not in source
    assert 'setObjectName("btn_danger")' not in source
    assert "apply_button_variant" in source
    assert "build_button_stylesheet" in source


def test_demo_gallery_imports_shared_search_and_combo_controls():
    source = inspect.getsource(dsg)

    assert "from src.shared.ui.search_input import SearchInput" in source
    assert "from src.shared.ui.styled_combo_box import StyledComboBox" in source


def test_demo_gallery_uses_shared_selection_builder_for_checkbox_and_radio():
    source = inspect.getsource(dsg)

    assert "from src.shared.ui.selection_control_style import build_checkbox_stylesheet" in source
    assert "build_checkbox_stylesheet(" in source
    assert "build_selection_control_stylesheet(" not in source
    assert "QCheckBox::indicator" not in source
    assert "QRadioButton::indicator" not in source


def test_demo_gallery_uses_self_drawn_radio_and_slider_controls():
    source = inspect.getsource(dsg)

    assert "from src.shared.ui import ThemedRadioButton, ThemedSlider" in source
    assert "ThemedRadioButton(" in source
    assert "ThemedSlider(" in source
    assert "QSlider::handle:horizontal" not in source


def test_demo_gallery_selection_copy_is_no_longer_marked_pending_theme_work():
    source = inspect.getsource(dsg)

    assert "QCheckBox / QRadioButton (待主题化)" not in source
    assert "QCheckBox / QRadioButton（共享 selection theme）" in source


def test_demo_gallery_no_longer_uses_qradiobutton_for_round_geometry():
    source = inspect.getsource(dsg)

    assert "QRadioButton(" not in source


def test_demo_gallery_showcase_copy_has_no_placeholder_question_marks():
    source = inspect.getsource(dsg)

    assert '"Primary ???"' not in source
    assert '"Secondary ???"' not in source
    assert '"?? Phase 2 ? ??????? (Focus Preview)"' not in source
    assert '"??????..."' not in source
    assert '"??????"' not in source
