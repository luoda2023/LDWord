import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.ui import dialogs
from src.shared.ui.base_dialog import BaseDialog
from src.shared.ui.form_row import FormRow
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.theme import LIGHT
from src.ui.adapters.heading_numbering_adapter import HeadingNumberingAdapter
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel


def test_theme_exposes_dialog_form_and_heading_metric_tokens():
    assert LIGHT.dialog_icon_container_size > 0
    assert LIGHT.dialog_icon_size > 0
    assert LIGHT.dialog_close_button_size > 0
    assert LIGHT.form_row_label_width > 0
    assert LIGHT.form_row_height > 0
    assert LIGHT.spacing_input_unit_width > 0
    assert LIGHT.heading_panel_levels_width > 0
    assert LIGHT.heading_panel_sidebar_width > 0
    assert LIGHT.heading_panel_short_input_width > 0
    assert LIGHT.heading_panel_tiny_input_width > 0
    assert LIGHT.heading_panel_preset_width > 0
    assert LIGHT.heading_panel_preview_row_height > 0
    assert LIGHT.heading_panel_preview_tag_width > 0
    assert LIGHT.heading_panel_editor_combo_width > 0
    assert LIGHT.heading_panel_reference_combo_width > 0
    assert LIGHT.heading_panel_raw_template_width > 0


def test_form_row_uses_theme_tokens_instead_of_local_constants():
    source = inspect.getsource(FormRow)

    assert 'LABEL_WIDTH = 120' not in source
    assert 'ROW_HEIGHT = 36' not in source
    assert 'form_row_label_width' in source
    assert 'form_row_height' in source


def test_base_dialog_uses_theme_tokens_for_icon_and_close_metrics():
    source = inspect.getsource(BaseDialog)

    assert 'setFixedSize(40, 40)' not in source
    assert 'setFixedSize(24, 24)' not in source
    assert 'setFixedSize(32, 32)' not in source
    assert 'dialog_icon_container_size' in source
    assert 'dialog_icon_size' in source
    assert 'dialog_close_button_size' in source


def test_dialogs_module_has_no_placeholder_question_marks_and_uses_dialog_detail_tokens():
    source = inspect.getsource(dialogs)

    assert '??' not in source
    assert 'LOG_PATH_PREFIX' in source
    assert 'OK_TEXT' in source
    assert 'OK_TEXT' in source
    assert 'dialog_detail_max_height' in source or 'dialog_detail_min_height' in source


def test_dialogs_module_source_keeps_readable_utf8_literals():
    source = (ROOT / 'src/shared/ui/dialogs.py').read_text(encoding='utf-8')

    assert 'OK_TEXT = "确定"' in source
    assert 'CONFIRM_TEXT = "确认"' in source
    assert 'CANCEL_TEXT = "取消"' in source
    assert 'LOG_PATH_PREFIX = "日志路径："' in source
    assert '\ufffd' not in source


def test_spacing_input_uses_theme_binding_and_tokenized_widths():
    source = inspect.getsource(SpacingInput)

    assert 'bind_theme' in source
    assert 'setFixedWidth(60)' not in source
    assert 'spacing_input_unit_width' in source


def test_heading_numbering_panel_uses_heading_metric_tokens_for_fixed_widths():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    stylesheet_source = inspect.getsource(HeadingNumberingPanel._build_stylesheet)
    source = panel_source + stylesheet_source

    for literal in [
        'setFixedWidth(100)',
        'setFixedWidth(200)',
        'setFixedWidth(80)',
        'setFixedWidth(40)',
        'setMinimumWidth(220)',
        'setFixedHeight(40)',
        'setFixedWidth(45)',
        'setFixedHeight(36)',
        'QSize(200, 36)',
    ]:
        assert literal not in source
    assert 'heading_panel_sidebar_width' in source
    assert 'radius_xs' in source
    assert 'control_height_md' in source


def test_heading_numbering_panel_does_not_touch_adapter_private_template_state():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    adapter_source = inspect.getsource(HeadingNumberingAdapter)

    assert '._template' not in panel_source
    assert 'has_template' in panel_source
    assert 'def has_template' in adapter_source
    assert 'return self._template is not None' in adapter_source


def test_heading_numbering_panel_delegates_stylesheet_to_shared_builder():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    stylesheet_source = inspect.getsource(HeadingNumberingPanel._build_stylesheet)

    assert '_build_stylesheet' in panel_source
    assert 'setStyleSheet(f"""' not in panel_source
    assert 'build_text_input_stylesheet' in stylesheet_source
    assert 'build_checkbox_stylesheet' in stylesheet_source
