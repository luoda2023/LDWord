import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.ui.base_dialog import BaseDialog
from src.shared.ui.color_picker import ColorPicker
from src.shared.ui.error_dialog import ErrorDialog
from src.shared.ui.progress_indicator import ProgressIndicator
from src.shared.ui.theme import LIGHT
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel


def test_theme_exposes_progress_and_color_picker_tokens():
    assert LIGHT.color_picker_swatch_size > 0
    assert LIGHT.color_picker_height >= LIGHT.color_picker_swatch_size
    assert LIGHT.progress_bar_height > 0
    assert LIGHT.progress_indicator_height > LIGHT.progress_bar_height
    assert LIGHT.progress_cancel_min_width > 0


def test_color_picker_uses_theme_binding_and_tokenized_swatch_helper():
    source = inspect.getsource(ColorPicker)

    assert "bind_theme" in source
    assert "build_swatch_stylesheet" in source
    assert "setFixedSize(28, 28)" not in source
    assert "setFixedHeight(32)" not in source


def test_color_picker_uses_readable_dialog_title_constant():
    source = (ROOT / "src/shared/ui/color_picker.py").read_text(encoding="utf-8")

    assert 'COLOR_DIALOG_TITLE = "选择颜色"' in source
    assert "QColorDialog.getColor(QColor(self._color), self, COLOR_DIALOG_TITLE)" in source
    assert "??" not in source


def test_progress_indicator_uses_shared_button_variant_helper():
    source = inspect.getsource(ProgressIndicator)

    assert "apply_button_variant" in source
    assert "build_button_stylesheet" in source
    assert 'font-size:{t.font_size_sm}px; color:{t.error}; border:none;' not in source


def test_progress_indicator_uses_readable_status_copy():
    module_source = (ROOT / "src/shared/ui/progress_indicator.py").read_text(encoding="utf-8")
    source = inspect.getsource(ProgressIndicator)

    assert 'DEFAULT_STEP_TEXT = "处理中..."' in module_source
    assert 'CANCEL_BUTTON_TEXT = "取消"' in module_source
    assert 'DONE_STEP_TEXT = "已完成"' in module_source
    assert "DEFAULT_STEP_TEXT" in source
    assert "CANCEL_BUTTON_TEXT" in source
    assert "DONE_STEP_TEXT" in source
    assert "??" not in module_source


def test_progress_indicator_further_decomposes_constructor_helpers():
    source = inspect.getsource(ProgressIndicator)
    init_source = inspect.getsource(ProgressIndicator.__init__)

    assert "def _build_step_label" in source
    assert "def _build_progress_row" in source
    assert "def _build_percentage_label" in source
    assert "self._build_step_label" in init_source
    assert "self._build_progress_row" in init_source
    assert "self._build_percentage_label" in init_source
    assert "QLabel(DEFAULT_STEP_TEXT)" not in init_source
    assert "QProgressBar()" not in init_source
    assert "QPushButton(CANCEL_BUTTON_TEXT)" not in init_source


def test_progress_indicator_further_decomposes_theme_helpers():
    source = inspect.getsource(ProgressIndicator)
    theme_source = inspect.getsource(ProgressIndicator._apply_theme)

    assert "def _apply_progress_bar_theme" in source
    assert "def _apply_cancel_button_theme" in source
    assert "def _apply_progress_label_theme" in source
    assert "self._apply_progress_bar_theme" in theme_source
    assert "self._apply_cancel_button_theme" in theme_source
    assert "self._apply_progress_label_theme" in theme_source
    assert "QProgressBar {" not in theme_source
    assert "build_button_stylesheet(" not in theme_source


def test_error_dialog_builds_on_base_dialog_without_local_ok_button_qss():
    assert issubclass(ErrorDialog, BaseDialog)

    source = inspect.getsource(ErrorDialog)
    assert "#error_ok_btn" not in source


def test_heading_numbering_panel_disabled_visuals_are_property_driven():
    preview_source = inspect.getsource(HeadingNumberingPanel._rebuild_simple_preview)
    list_source = inspect.getsource(HeadingNumberingPanel._rebuild_advanced_list)
    theme_source = inspect.getsource(HeadingNumberingPanel._apply_theme)
    stylesheet_source = (ROOT / "src/ui/panels/heading_numbering_styles.py").read_text(encoding="utf-8")

    assert ".setStyleSheet" not in preview_source
    assert ".setStyleSheet" not in list_source
    assert "build_heading_numbering_panel_stylesheet" in theme_source
    assert '[muted="true"]' in stylesheet_source or '[disabled_visual="true"]' in stylesheet_source


def test_heading_numbering_panel_selection_visuals_are_delegated_to_shared_builder():
    stylesheet_source = (ROOT / "src/ui/panels/heading_numbering_styles.py").read_text(encoding="utf-8")

    assert "build_checkbox_stylesheet" in stylesheet_source
    assert 'selector="#HeadingNumberingPanel QCheckBox"' in stylesheet_source
    assert "build_selection_control_stylesheet" not in stylesheet_source
    assert 'QRadioButton' not in stylesheet_source
    assert "QCheckBox::indicator" not in stylesheet_source
    assert "QRadioButton::indicator" not in stylesheet_source
