# Selection Controls Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the first phase of the next-generation Selection Controls system by turning `QCheckBox` / `QRadioButton` into shared themed primitives used by both the real heading-numbering panel and the gallery preview.

**Architecture:** Extend `AppTheme` with selection-control tokens, add a dedicated shared stylesheet builder module for checkbox/radio rules, then make `heading_numbering_styles.py` and `demo_style_gallery.py` consume that shared builder instead of carrying local QSS. Keep preview and real UI on the same rendering path so later Toggle / list-selection / sidebar-selection work can extend the same module.

**Tech Stack:** Python, PySide6, pytest, shared UI theme/QSS helpers

---

> [!IMPORTANT]
> **Status update (2026-03-28):**
> - This plan remains the historical implementation record for the **Checkbox-first shared QSS** phase and the already-landed Radio transitional styling work.
> - It is **no longer** the recommended execution entry for the Radio / Slider geometry route.
> - Starting from `2026-03-28-project-level-themed-selection-controls-design.md`, the formal direction for Radio / Slider is: project-owned self-drawn controls (`ThemedRadioButton` / `ThemedSlider`) instead of further extending `QRadioButton::indicator` / `QSlider::handle` QSS.
> - The current runtime code has already tightened the shared stylesheet boundary to Checkbox only via `build_checkbox_stylesheet()`.
> - Use `2026-03-28-self-drawn-selection-controls-phase1.md` for the new execution path. Keep this file only as Phase 1 archive context and Checkbox boundary reference.

## File map

- Create: `src/shared/ui/selection_control_style.py` — shared checkbox/radio stylesheet builders and tiny SVG helpers
- Create: `tests/test_selection_control_styles.py` — selection token + builder unit tests
- Modify: `src/shared/ui/theme.py` — add selection-control tokens and theme-side defaults
- Modify: `src/shared/ui/__init__.py` — export shared selection builders
- Modify: `src/ui/panels/heading_numbering_styles.py` — replace local checkbox styling with shared builder usage
- Modify: `demo_style_gallery.py` — consume shared selection builder and remove inline checkbox/radio QSS
- Modify: `tests/test_demo_gallery_architecture.py` — assert gallery no longer carries local checkbox/radio styling
- Modify: `tests/test_input_architecture.py` — assert heading panel stylesheet composes shared selection builder
- Modify: `tests/test_ui_exports.py` — export smoke tests for new builders
- Modify: `tests/test_widget_architecture.py` — heading-panel architecture regression for shared selection builder

### Task 1: Add selection-control tokens and shared builder API

**Files:**
- Create: `src/shared/ui/selection_control_style.py`
- Create: `tests/test_selection_control_styles.py`
- Modify: `src/shared/ui/theme.py`
- Modify: `src/shared/ui/__init__.py`
- Modify: `tests/test_ui_exports.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_selection_control_styles.py
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.ui import (
    build_checkbox_stylesheet,
    build_radio_stylesheet,
    build_selection_control_stylesheet,
)
from src.shared.ui.theme import LIGHT


def test_theme_exposes_selection_control_tokens():
    assert LIGHT.checkbox_size == 18
    assert LIGHT.checkbox_radius == 5
    assert LIGHT.checkbox_border_width == 1
    assert LIGHT.checkbox_border_color == LIGHT.border
    assert LIGHT.checkbox_hover_border_color == LIGHT.border_focus
    assert LIGHT.checkbox_checked_bg == LIGHT.primary
    assert LIGHT.radio_size == 18
    assert LIGHT.radio_ring_width == 1
    assert LIGHT.radio_dot_size == 7
    assert LIGHT.radio_checked_ring_color == LIGHT.primary
    assert LIGHT.selection_label_color == LIGHT.text_secondary
    assert LIGHT.selection_label_checked_color == LIGHT.text_primary
    assert LIGHT.selection_label_disabled_color == LIGHT.text_disabled


def test_selection_control_stylesheets_use_theme_tokens_and_selectors():
    checkbox_qss = build_checkbox_stylesheet(LIGHT, selector="#demo QCheckBox")
    radio_qss = build_radio_stylesheet(LIGHT, selector="#demo QRadioButton")
    merged_qss = build_selection_control_stylesheet(
        LIGHT,
        checkbox_selector="#demo QCheckBox",
        radio_selector="#demo QRadioButton",
    )

    assert "#demo QCheckBox" in checkbox_qss
    assert "#demo QRadioButton" in radio_qss
    assert f"width: {LIGHT.checkbox_size}px;" in checkbox_qss
    assert f"height: {LIGHT.checkbox_size}px;" in checkbox_qss
    assert f"border-radius: {LIGHT.checkbox_radius}px;" in checkbox_qss
    assert f"spacing: {LIGHT.checkbox_label_gap}px;" in checkbox_qss
    assert f"width: {LIGHT.radio_size}px;" in radio_qss
    assert f"height: {LIGHT.radio_size}px;" in radio_qss
    assert f"spacing: {LIGHT.radio_label_gap}px;" in radio_qss
    assert LIGHT.checkbox_checked_bg in merged_qss
    assert LIGHT.radio_checked_ring_color in merged_qss
```

```python
# tests/test_ui_exports.py
from src.shared.ui import (
    FontCombo,
    NumberingPreset,
    SearchInput,
    SizeCombo,
    StyledComboBox,
    apply_button_variant,
    build_button_stylesheet,
    build_checkbox_stylesheet,
    build_radio_stylesheet,
    build_selection_control_stylesheet,
)


def test_shared_ui_exports_include_unified_controls():
    assert SearchInput.__name__ == "SearchInput"
    assert StyledComboBox.__name__ == "StyledComboBox"
    assert FontCombo.__name__ == "FontCombo"
    assert SizeCombo.__name__ == "SizeCombo"
    assert NumberingPreset.__name__ == "NumberingPreset"
    assert callable(apply_button_variant)
    assert callable(build_button_stylesheet)
    assert callable(build_checkbox_stylesheet)
    assert callable(build_radio_stylesheet)
    assert callable(build_selection_control_stylesheet)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_selection_control_styles.py tests/test_ui_exports.py -v`

Expected: FAIL because `selection_control_style.py` does not exist, new exports are missing, and `AppTheme` does not expose the selection tokens yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/shared/ui/theme.py  (add these fields inside AppTheme)
checkbox_size: int = 18
checkbox_radius: int = 5
checkbox_border_width: int = 1
checkbox_border_color: str = ""
checkbox_hover_border_color: str = ""
checkbox_focus_border_color: str = ""
checkbox_bg: str = ""
checkbox_checked_bg: str = ""
checkbox_checked_border_color: str = ""
checkbox_checkmark_color: str = ""
checkbox_disabled_bg: str = ""
checkbox_disabled_border_color: str = ""
checkbox_disabled_checkmark_color: str = ""
checkbox_label_gap: int = 8

radio_size: int = 18
radio_ring_width: int = 1
radio_border_color: str = ""
radio_hover_border_color: str = ""
radio_focus_border_color: str = ""
radio_bg: str = ""
radio_checked_ring_color: str = ""
radio_dot_size: int = 7
radio_dot_color: str = ""
radio_disabled_bg: str = ""
radio_disabled_border_color: str = ""
radio_disabled_dot_color: str = ""
radio_label_gap: int = 8

selection_label_color: str = ""
selection_label_checked_color: str = ""
selection_label_disabled_color: str = ""
```

```python
# src/shared/ui/theme.py  (add this method inside AppTheme)
def __post_init__(self) -> None:
    if not self.checkbox_border_color:
        self.checkbox_border_color = self.border
    if not self.checkbox_hover_border_color:
        self.checkbox_hover_border_color = self.border_focus
    if not self.checkbox_focus_border_color:
        self.checkbox_focus_border_color = self.primary
    if not self.checkbox_bg:
        self.checkbox_bg = self.bg_input
    if not self.checkbox_checked_bg:
        self.checkbox_checked_bg = self.primary
    if not self.checkbox_checked_border_color:
        self.checkbox_checked_border_color = self.primary
    if not self.checkbox_checkmark_color:
        self.checkbox_checkmark_color = self.text_on_primary
    if not self.checkbox_disabled_bg:
        self.checkbox_disabled_bg = self.bg_hover
    if not self.checkbox_disabled_border_color:
        self.checkbox_disabled_border_color = self.border_light
    if not self.checkbox_disabled_checkmark_color:
        self.checkbox_disabled_checkmark_color = self.text_disabled

    if not self.radio_border_color:
        self.radio_border_color = self.border
    if not self.radio_hover_border_color:
        self.radio_hover_border_color = self.border_focus
    if not self.radio_focus_border_color:
        self.radio_focus_border_color = self.primary
    if not self.radio_bg:
        self.radio_bg = self.bg_input
    if not self.radio_checked_ring_color:
        self.radio_checked_ring_color = self.primary
    if not self.radio_dot_color:
        self.radio_dot_color = self.primary
    if not self.radio_disabled_bg:
        self.radio_disabled_bg = self.bg_hover
    if not self.radio_disabled_border_color:
        self.radio_disabled_border_color = self.border_light
    if not self.radio_disabled_dot_color:
        self.radio_disabled_dot_color = self.text_disabled

    if not self.selection_label_color:
        self.selection_label_color = self.text_secondary
    if not self.selection_label_checked_color:
        self.selection_label_checked_color = self.text_primary
    if not self.selection_label_disabled_color:
        self.selection_label_disabled_color = self.text_disabled
```

```python
# src/shared/ui/selection_control_style.py
"""
Shared selection-control stylesheet builders.

Phase 1 covers QCheckBox / QRadioButton.
Future phases should extend this module instead of adding page-local QSS.
"""

from __future__ import annotations

from urllib.parse import quote

from src.shared.ui.theme import AppTheme


def _checkbox_checkmark_image(color: str) -> str:
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' "
        f"stroke='{color}' stroke-width='2.6' stroke-linecap='round' stroke-linejoin='round'>"
        "<polyline points='20 6 9 17 4 12'/></svg>"
    )
    return f'url(\"data:image/svg+xml;utf8,{quote(svg)}\")'


def _radio_checked_background(theme: AppTheme, *, dot_color: str, base_bg: str) -> str:
    dot_stop = max(0.20, min(0.46, theme.radio_dot_size / theme.radio_size))
    edge_stop = min(0.49, dot_stop + 0.02)
    return (
        "qradialgradient("
        "cx: 0.5, cy: 0.5, fx: 0.5, fy: 0.5, radius: 0.5, "
        f"stop: 0 {dot_color}, "
        f"stop: {dot_stop:.3f} {dot_color}, "
        f"stop: {edge_stop:.3f} {base_bg}, "
        f"stop: 1 {base_bg})"
    )


def build_checkbox_stylesheet(theme: AppTheme, selector: str = "QCheckBox") -> str:
    return f"""
        {selector} {{
            font-size: {theme.font_size_md}px;
            color: {theme.selection_label_color};
            spacing: {theme.checkbox_label_gap}px;
        }}
        {selector}:checked {{
            color: {theme.selection_label_checked_color};
        }}
        {selector}:disabled {{
            color: {theme.selection_label_disabled_color};
        }}
        {selector}::indicator {{
            width: {theme.checkbox_size}px;
            height: {theme.checkbox_size}px;
            border: {theme.checkbox_border_width}px solid {theme.checkbox_border_color};
            border-radius: {theme.checkbox_radius}px;
            background: {theme.checkbox_bg};
        }}
        {selector}::indicator:hover {{
            border-color: {theme.checkbox_hover_border_color};
        }}
        {selector}::indicator:checked {{
            background: {theme.checkbox_checked_bg};
            border-color: {theme.checkbox_checked_border_color};
            image: {_checkbox_checkmark_image(theme.checkbox_checkmark_color)};
        }}
        {selector}::indicator:checked:hover {{
            border-color: {theme.checkbox_focus_border_color};
        }}
        {selector}::indicator:disabled {{
            background: {theme.checkbox_disabled_bg};
            border-color: {theme.checkbox_disabled_border_color};
            image: none;
        }}
        {selector}::indicator:disabled:checked {{
            background: {theme.checkbox_disabled_bg};
            border-color: {theme.checkbox_disabled_border_color};
            image: {_checkbox_checkmark_image(theme.checkbox_disabled_checkmark_color)};
        }}
    """


def build_radio_stylesheet(theme: AppTheme, selector: str = "QRadioButton") -> str:
    checked_bg = _radio_checked_background(
        theme,
        dot_color=theme.radio_dot_color,
        base_bg=theme.radio_bg,
    )
    disabled_checked_bg = _radio_checked_background(
        theme,
        dot_color=theme.radio_disabled_dot_color,
        base_bg=theme.radio_disabled_bg,
    )
    return f"""
        {selector} {{
            font-size: {theme.font_size_md}px;
            color: {theme.selection_label_color};
            spacing: {theme.radio_label_gap}px;
        }}
        {selector}:checked {{
            color: {theme.selection_label_checked_color};
        }}
        {selector}:disabled {{
            color: {theme.selection_label_disabled_color};
        }}
        {selector}::indicator {{
            width: {theme.radio_size}px;
            height: {theme.radio_size}px;
            border: {theme.radio_ring_width}px solid {theme.radio_border_color};
            border-radius: {theme.radio_size // 2}px;
            background: {theme.radio_bg};
        }}
        {selector}::indicator:hover {{
            border-color: {theme.radio_hover_border_color};
        }}
        {selector}::indicator:checked {{
            background: {checked_bg};
            border-color: {theme.radio_checked_ring_color};
        }}
        {selector}::indicator:checked:hover {{
            border-color: {theme.radio_focus_border_color};
        }}
        {selector}::indicator:disabled {{
            background: {theme.radio_disabled_bg};
            border-color: {theme.radio_disabled_border_color};
        }}
        {selector}::indicator:disabled:checked {{
            background: {disabled_checked_bg};
            border-color: {theme.radio_disabled_border_color};
        }}
    """


def build_selection_control_stylesheet(
    theme: AppTheme,
    *,
    checkbox_selector: str = "QCheckBox",
    radio_selector: str = "QRadioButton",
) -> str:
    return "\n".join(
        [
            build_checkbox_stylesheet(theme, selector=checkbox_selector),
            build_radio_stylesheet(theme, selector=radio_selector),
        ]
    )
```

```python
# src/shared/ui/__init__.py
from .button_style import apply_button_variant, build_button_stylesheet
from .font_combo import FontCombo
from .input_style import build_text_input_stylesheet
from .numbering_preset import NumberingPreset
from .search_input import SearchInput
from .selection_control_style import (
    build_checkbox_stylesheet,
    build_radio_stylesheet,
    build_selection_control_stylesheet,
)
from .size_combo import SizeCombo
from .spacing_input import SpacingInput
from .styled_combo_box import StyledComboBox
from .theme import bind_theme

__all__ = [
    "SearchInput",
    "StyledComboBox",
    "FontCombo",
    "SizeCombo",
    "NumberingPreset",
    "SpacingInput",
    "apply_button_variant",
    "build_button_stylesheet",
    "build_checkbox_stylesheet",
    "build_radio_stylesheet",
    "build_selection_control_stylesheet",
    "build_text_input_stylesheet",
    "bind_theme",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_selection_control_styles.py tests/test_ui_exports.py -v`

Expected: PASS

- [ ] **Step 5: Local checkpoint**

Run: `python -m compileall src/shared/ui/theme.py src/shared/ui/selection_control_style.py src/shared/ui/__init__.py tests/test_selection_control_styles.py tests/test_ui_exports.py`

Expected: all files compile without syntax errors.

### Task 2: Move heading-numbering panel onto the shared selection builder

**Files:**
- Modify: `src/ui/panels/heading_numbering_styles.py`
- Modify: `tests/test_input_architecture.py`
- Modify: `tests/test_widget_architecture.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_input_architecture.py
def test_heading_numbering_panel_uses_shared_text_input_and_selection_helpers():
    source = inspect.getsource(HeadingNumberingPanel._apply_theme)
    stylesheet_source = (ROOT / "src/ui/panels/heading_numbering_styles.py").read_text(encoding="utf-8")

    assert "build_heading_numbering_panel_stylesheet" in source
    assert "build_text_input_stylesheet" in stylesheet_source
    assert "build_selection_control_stylesheet" in stylesheet_source
    assert "QLineEdit {" not in source
```

```python
# tests/test_widget_architecture.py
def test_heading_numbering_panel_selection_visuals_are_delegated_to_shared_builder():
    stylesheet_source = (ROOT / "src/ui/panels/heading_numbering_styles.py").read_text(encoding="utf-8")

    assert "build_selection_control_stylesheet" in stylesheet_source
    assert 'checkbox_selector="#HeadingNumberingPanel QCheckBox"' in stylesheet_source
    assert 'radio_selector="#HeadingNumberingPanel QRadioButton"' in stylesheet_source
    assert "QCheckBox::indicator" not in stylesheet_source
    assert "QRadioButton::indicator" not in stylesheet_source
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_input_architecture.py tests/test_widget_architecture.py -v`

Expected: FAIL because `heading_numbering_styles.py` still carries local `QCheckBox` rules and does not import the new shared selection builder.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panels/heading_numbering_styles.py
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.selection_control_style import build_selection_control_stylesheet
from src.shared.ui.theme import AppTheme


def build_heading_numbering_panel_stylesheet(t: AppTheme) -> str:
    selection_qss = build_selection_control_stylesheet(
        t,
        checkbox_selector="#HeadingNumberingPanel QCheckBox",
        radio_selector="#HeadingNumberingPanel QRadioButton",
    )
    return f"""
        #HeadingNumberingPanel {{ background: transparent; }}

        #hn_label, #hn_form_label {{
            font-size: {t.font_size_md}px;
            color: {t.text_primary};
        }}
        #hn_form_label {{ font-weight: {t.font_weight_bold}; }}

        #hn_small_label {{
            font-size: {t.font_size_sm}px;
            color: {t.text_secondary};
        }}

        #hn_detail_title {{
            font-size: {t.font_size_lg}px;
            font-weight: {t.font_weight_bold};
            color: {t.text_primary};
        }}

        #hn_preset_frame, #hn_simple_frame, #hn_detail_frame {{
            background: {t.bg_card};
            border: 1px solid {t.border};
            border-radius: {t.radius_xs}px;
        }}

        #hn_nn_frame, #hn_expert_frame {{
            background: {t.bg_input};
            border: 1px solid {t.border};
            border-radius: {t.radius_xs}px;
        }}

        #hn_list_frame {{
            background: {t.bg_card};
            border: 1px solid {t.border};
            border-radius: {t.radius_xs}px;
        }}

        #hn_list_header {{
            font-size: {t.font_size_md}px;
            color: {t.text_secondary};
            background: {t.bg_input};
            border-bottom: 1px solid {t.border};
        }}

        #hn_preview_row {{
            background: transparent;
        }}

        #hn_preview_tag, #hn_list_lv {{
            font-size: {t.font_size_sm}px;
            color: {t.text_secondary};
        }}

        #hn_list_txt {{
            font-size: {t.font_size_md}px;
            color: {t.text_primary};
        }}

        #hn_preview_num {{
            font-size: {t.font_size_md}px;
            font-weight: {t.font_weight_bold};
            color: {t.text_primary};
        }}

        #hn_preview_demo {{
            font-size: {t.font_size_md}px;
            color: {t.text_secondary};
        }}

        #hn_preview_tag[muted="true"],
        #hn_preview_num[muted="true"],
        #hn_preview_demo[muted="true"],
        #hn_list_txt[muted="true"] {{
            color: {t.text_disabled};
        }}

        #hn_divider {{
            background-color: {t.border};
        }}

        #hn_section_toggle {{
            font-size: {t.font_size_sm}px;
            color: {t.primary};
            text-align: left;
            padding: 0;
        }}
        #hn_section_toggle:hover {{
            text-decoration: underline;
        }}

        #hn_mode_container {{
            background: {t.bg_input};
            border: 1px solid {t.border};
            border-radius: {t.radius_sm}px;
        }}

        #hn_mode_btn {{
            font-size: {t.font_size_md}px;
            border: none;
            border-radius: {t.radius_xs}px;
            padding: {t.spacing_xs}px {t.button_padding_x}px;
            background: transparent;
            color: {t.text_secondary};
        }}
        #hn_mode_btn:hover {{
            color: {t.text_primary};
        }}
        #hn_mode_btn:checked {{
            background: {t.bg_card};
            color: {t.text_primary};
            font-weight: {t.font_weight_bold};
            border: 1px solid {t.border};
        }}

        QListWidget#hn_level_list {{
            background: transparent;
            border: none;
            outline: none;
        }}
        QListWidget#hn_level_list::item {{
            border-bottom: 1px solid {t.border};
        }}
        QListWidget#hn_level_list::item:hover {{
            background: {t.bg_hover};
        }}
        QListWidget#hn_level_list::item:selected {{
            background: {t.bg_input};
            border-left: 3px solid {t.primary};
        }}

        {build_text_input_stylesheet(
            t,
            "#HeadingNumberingPanel QLineEdit",
            background=t.bg_card,
            focus_border_color=t.primary,
            padding_y=0,
        )}

        {selection_qss}
    """
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_input_architecture.py tests/test_widget_architecture.py -v`

Expected: PASS

- [ ] **Step 5: Local checkpoint**

Run: `python -m compileall src/ui/panels/heading_numbering_styles.py tests/test_input_architecture.py tests/test_widget_architecture.py`

Expected: all files compile without syntax errors.

### Task 3: Move `demo_style_gallery.py` onto the shared selection builder

**Files:**
- Modify: `demo_style_gallery.py`
- Modify: `tests/test_demo_gallery_architecture.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_demo_gallery_architecture.py
def test_demo_gallery_uses_shared_selection_builder_for_checkbox_and_radio():
    source = inspect.getsource(dsg)

    assert "from src.shared.ui.selection_control_style import build_selection_control_stylesheet" in source
    assert "build_selection_control_stylesheet(" in source
    assert "QCheckBox::indicator" not in source
    assert "QRadioButton::indicator" not in source


def test_demo_gallery_selection_copy_is_no_longer_marked_pending_theme_work():
    source = inspect.getsource(dsg)

    assert "QCheckBox / QRadioButton (待主题化)" not in source
    assert "QCheckBox / QRadioButton（共享 selection theme）" in source
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_demo_gallery_architecture.py -v`

Expected: FAIL because `demo_style_gallery.py` still contains inline checkbox/radio QSS and still labels the section as pending theming work.

- [ ] **Step 3: Write the minimal implementation**

```python
# demo_style_gallery.py  (imports)
from src.shared.ui.selection_control_style import build_selection_control_stylesheet
```

```python
# demo_style_gallery.py  (new helper)
def _build_selection_showcase_row() -> QWidget:
    cb1 = QCheckBox("默认未选")
    cb2 = QCheckBox("已选中")
    cb2.setChecked(True)
    cb3 = QCheckBox("禁用")
    cb3.setEnabled(False)
    cb4 = QCheckBox("禁用且已选")
    cb4.setChecked(True)
    cb4.setEnabled(False)

    rb1 = QRadioButton("选项 A")
    rb2 = QRadioButton("选项 B")
    rb2.setChecked(True)
    rb3 = QRadioButton("禁用")
    rb3.setEnabled(False)

    return _hbox(cb1, cb2, cb3, cb4, "stretch", rb1, rb2, rb3)
```

```python
# demo_style_gallery.py  (_build_focus_preview / _build_section_native)
self._main_layout.addWidget(_subsection_title("✅ QCheckBox / QRadioButton（共享 selection theme）"))
self._main_layout.addWidget(_build_selection_showcase_row())
```

```python
# demo_style_gallery.py  (_apply_theme)
selection_qss = build_selection_control_stylesheet(t)

self.setStyleSheet(f"""
    StyleGallery {{
        background: {t.bg_window};
    }}

    #gallery_toolbar {{
        background: {t.bg_sidebar};
        border-bottom: 1px solid {t.border_light};
    }}
    #gallery_title {{
        font-size: {t.font_size_xl}px;
        font-weight: {t.font_weight_bold};
        color: {t.text_primary};
    }}

    QPushButton[objectName^="theme_btn"] {{
        background: {t.bg_card};
        color: {t.text_primary};
        border: 1px solid {t.border};
        border-radius: {t.radius_sm}px;
        font-size: {t.font_size_sm}px;
        padding: 0 12px;
    }}
    QPushButton[objectName^="theme_btn"]:checked {{
        background: {t.primary};
        color: {t.text_on_primary};
        border-color: {t.primary};
    }}
    QPushButton[objectName^="theme_btn"]:hover {{
        border-color: {t.primary};
    }}

    #section_title {{
        font-size: {t.font_size_xxl}px;
        font-weight: {t.font_weight_bold};
        color: {t.text_primary};
        padding: 4px 0;
    }}
    #subsection_title {{
        font-size: {t.font_size_lg}px;
        font-weight: {t.font_weight_bold};
        color: {t.text_secondary};
        padding: 2px 0;
    }}
    #desc_label {{
        font-size: {t.font_size_sm}px;
        color: {t.text_hint};
    }}

    #gallery_hline {{
        background: {t.border_light};
        max-height: 1px;
        margin: 8px 0;
    }}

    #gallery_scroll {{
        border: none;
        background: {t.bg_window};
    }}
    #gallery_container {{
        background: {t.bg_window};
    }}

    {build_button_stylesheet(t)}
    {selection_qss}
""")
```

Implementation note: delete the old inline `QCheckBox { ... }`, `QCheckBox::indicator { ... }`, `QRadioButton { ... }`, and `QRadioButton::indicator { ... }` blocks entirely instead of leaving dead duplicate rules behind.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_demo_gallery_architecture.py -v`

Expected: PASS

- [ ] **Step 5: Local checkpoint**

Run: `python -m compileall demo_style_gallery.py tests/test_demo_gallery_architecture.py`

Expected: files compile without syntax errors.

### Task 4: Regressions and visual verification

**Files:**
- No new code files; verify the modifications above together

- [ ] **Step 1: Run the focused regression suite**

Run: `pytest tests/test_selection_control_styles.py tests/test_input_architecture.py tests/test_widget_architecture.py tests/test_demo_gallery_architecture.py tests/test_ui_exports.py -v`

Expected: PASS

- [ ] **Step 2: Run the full automated test suite**

Run: `pytest tests -q`

Expected: PASS with the suite staying green after the new shared selection builder lands.

- [ ] **Step 3: Launch the gallery preview for manual verification**

Run: `python demo_style_gallery.py`

Expected:
- a window titled `Lark Formatter — UI 控件样式全览`
- checkbox geometry is 18×18 small-radius square, no black corners
- checked checkbox uses restrained primary fill and a crisp thin checkmark
- radio uses a precise outer ring with a smaller center dot, not a fat blob
- disabled controls look inactive but clean, not dirty gray

- [ ] **Step 4: Launch the real heading-numbering panel for manual verification**

Run: `python demo_heading_panel.py`

Expected:
- the panel opens successfully
- TOC-related checkboxes and advanced-level enable checkboxes match the gallery’s geometry and state language
- there is no second private checkbox visual system hiding inside the panel

- [ ] **Step 5: Manual acceptance checklist**

Confirm all of the following before marking the phase complete:
- gallery and heading panel use the same checkbox/radio visual language
- `heading_numbering_styles.py` no longer defines local checkbox/radio indicator drawing
- `demo_style_gallery.py` no longer defines local checkbox/radio indicator drawing
- selection label color hierarchy is `default < checked < disabled` in the expected semantic direction
- the module naming (`selection_control_style.py`, `build_selection_control_stylesheet`) is ready to host Toggle / list-selection / sidebar-selection in phase 2

---

## Self-review

- **Spec coverage:** This plan covers theme token expansion, shared builder extraction, heading panel migration, gallery migration, shared exports, tests, and preview/manual verification.
- **Placeholder scan:** No `TODO`, `TBD`, or “similar to above” shortcuts were left in task steps.
- **Type consistency:** The same public API is used throughout: `build_checkbox_stylesheet`, `build_radio_stylesheet`, and `build_selection_control_stylesheet`.

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-03-27-selection-controls-phase1.md`.

Two execution options:

1. **Inline Execution (recommended here)** — I execute this plan in this session and给你看每一轮结果
2. **Subagent-Driven** — if you explicitly want delegation, I can按任务分发再整合

If you want me to start now, reply with **“执行”**.
