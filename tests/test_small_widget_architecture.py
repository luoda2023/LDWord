import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.ui.card import Card
from src.shared.ui.design_system_card import DesignSystemCard
from src.shared.ui.collapsible_section import CollapsibleSection
from src.shared.ui.icon_button import IconButton
from src.shared.ui.module_step_list import ModuleStepItem, ModuleStepList
from src.shared.ui.override_badge import OverrideBadge
from src.shared.ui.placeholder_edit import PlaceholderEdit
from src.shared.ui.style_preview import StylePreview
from src.shared.ui.theme import LIGHT


def test_theme_exposes_small_widget_metric_tokens():
    assert LIGHT.icon_button_size > 0
    assert LIGHT.icon_button_icon_size > 0
    assert LIGHT.override_badge_height > 0
    assert LIGHT.override_badge_icon_size > 0
    assert LIGHT.module_step_item_height > 0
    assert LIGHT.module_step_status_size > 0
    assert LIGHT.collapsible_toggle_height > 0
    assert LIGHT.style_preview_min_height > 0
    assert LIGHT.card_padding_x > 0
    assert LIGHT.card_padding_y > 0


def test_icon_button_defaults_are_tokenized():
    source = inspect.getsource(IconButton)

    assert 'ICON_SIZE = 20' not in source
    assert 'BUTTON_SIZE = 36' not in source
    assert 'icon_button_size' in source
    assert 'icon_button_icon_size' in source


def test_override_badge_restore_button_uses_shared_button_variant_helper():
    source = inspect.getsource(OverrideBadge)

    assert 'apply_button_variant' in source
    assert 'build_button_stylesheet' in source
    assert 'background:transparent' not in source.replace(' ', '')


def test_override_badge_uses_readable_copy_and_single_label_formatter():
    module_source = (ROOT / "src/shared/ui/override_badge.py").read_text(encoding="utf-8")
    source = inspect.getsource(OverrideBadge)

    assert 'ORIGINAL_VALUE_PREFIX = "原值"' in module_source
    assert 'RESTORE_BUTTON_TEXT = "恢复"' in module_source
    assert "def _format_original_label" in source
    assert "self._format_original_label(original_value)" in source
    assert "self._format_original_label(value)" in source
    assert "RESTORE_BUTTON_TEXT" in source
    assert "??" not in module_source


def test_override_badge_further_decomposes_constructor_and_theme_helpers():
    source = inspect.getsource(OverrideBadge)
    init_source = inspect.getsource(OverrideBadge.__init__)
    theme_source = inspect.getsource(OverrideBadge._apply_theme)

    assert "def _build_badge_icon" in source
    assert "def _build_original_value_label" in source
    assert "def _build_restore_button" in source
    assert "def _apply_badge_icon_theme" in source
    assert "def _apply_restore_button_theme" in source

    assert "self._build_badge_icon" in init_source
    assert "self._build_original_value_label" in init_source
    assert "self._build_restore_button" in init_source
    assert "self._apply_badge_icon_theme" in theme_source
    assert "self._apply_restore_button_theme" in theme_source

    assert "QLabel()" not in init_source
    assert "QPushButton(RESTORE_BUTTON_TEXT)" not in init_source
    assert "build_button_stylesheet(" not in theme_source


def test_module_step_widgets_bind_theme_and_use_tokenized_metrics():
    item_source = inspect.getsource(ModuleStepItem)
    list_source = inspect.getsource(ModuleStepList)

    assert 'bind_theme' in item_source or 'bind_theme' in list_source
    assert 'setFixedSize(16, 16)' not in item_source
    assert 'setFixedHeight(32)' not in item_source
    assert 'module_step_status_size' in item_source
    assert 'module_step_item_height' in item_source


def test_card_and_collapsible_section_layout_metrics_are_tokenized():
    card_source = inspect.getsource(DesignSystemCard)
    section_source = inspect.getsource(CollapsibleSection)

    assert issubclass(Card, DesignSystemCard)
    assert '20, 16, 20, 20' not in card_source
    assert 'setFixedHeight(32)' not in section_source
    assert 'card_padding_x' in card_source or 'card_padding_y' in card_source
    assert 'collapsible_toggle_height' in section_source


def test_style_preview_uses_tokenized_metrics():
    source = inspect.getsource(StylePreview)

    assert 'setMinimumHeight(60)' not in source
    assert 'padding: 12px;' not in source
    assert 'style_preview_min_height' in source


def test_style_preview_uses_readable_sample_text():
    assert StylePreview.SAMPLE_TEXT == "样式预览示例 AaBbCc 123"


def test_placeholder_edit_uses_readable_default_placeholder():
    source = (ROOT / "src/shared/ui/placeholder_edit.py").read_text(encoding="utf-8")
    init_source = inspect.getsource(PlaceholderEdit.__init__)

    assert 'DEFAULT_PLACEHOLDER_TEMPLATE = "{{占位符}}"' in source
    assert "placeholder: str = DEFAULT_PLACEHOLDER_TEMPLATE" in init_source
    assert "??" not in source
