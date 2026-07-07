# UI Control Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify button, search-input, and combo-box styling under `src/shared/ui/`, remove demo-only formal widget implementations, and migrate all affected call sites onto tokenized shared controls without changing visible behavior.

**Architecture:** Expand `AppTheme` into the single source of visual tokens, move reusable styling helpers into dedicated shared modules, and make all combo-derived widgets inherit one shared base class. Convert `demo_style_gallery.py` into a pure showcase that imports shared widgets and shared button styling instead of defining its own implementations.

**Tech Stack:** Python, PyQt5, pytest, shared UI theme/QSS helpers

---

## File map

- Create: `src/shared/ui/button_style.py` — button variant helper + shared button QSS builder
- Create: `src/shared/ui/styled_combo_box.py` — shared combo base with popup shell styling and arrow painting
- Create: `tests/test_button_style.py` — shared button helper/unit tests
- Create: `tests/test_search_input_styles.py` — search input architecture/style tests
- Create: `tests/test_combo_architecture.py` — combo inheritance/migration tests
- Create: `tests/test_demo_gallery_architecture.py` — demo-only architecture regression tests
- Create: `tests/test_ui_exports.py` — shared UI export smoke tests
- Modify: `src/shared/ui/theme.py` — token expansion
- Modify: `src/shared/ui/search_input.py` — single canonical search control
- Modify: `src/shared/ui/font_combo.py` — inherit shared combo base
- Modify: `src/shared/ui/size_combo.py` — inherit shared combo base
- Modify: `src/shared/ui/numbering_preset.py` — inherit shared combo base
- Modify: `src/shared/ui/spacing_input.py` — replace raw unit combo with shared combo base
- Modify: `src/shared/ui/__init__.py` — shared UI exports
- Modify: `src/ui/panels/heading_numbering_panel.py` — migrate raw combos/button variant usage
- Modify: `demo_style_gallery.py` — display-only showcase
- Modify: `tests/test_combo_popup_styles.py` — point at shared combo base
- Modify: `tests/test_phase4_ui.py` — include new shared combo base/export expectations

### Task 1: Expand theme tokens and add shared button variant helper

**Files:**
- Create: `src/shared/ui/button_style.py`
- Modify: `src/shared/ui/theme.py`
- Test: `tests/test_button_style.py`

- [ ] **Step 1: Write the failing tests**

```python
from src.shared.ui.button_style import build_button_stylesheet
from src.shared.ui.theme import LIGHT


def test_button_stylesheet_uses_theme_tokens():
    qss = build_button_stylesheet(LIGHT)

    assert "QPushButton[variant=\"primary\"]" in qss
    assert f"border-radius: {LIGHT.button_radius}px;" in qss
    assert f"min-height: {LIGHT.button_height_md}px;" in qss
    assert f"padding: {LIGHT.button_padding_y}px {LIGHT.button_padding_x}px;" in qss


def test_theme_exposes_combo_and_input_tokens():
    assert LIGHT.input_radius > 0
    assert LIGHT.combo_arrow_zone_width > 0
    assert LIGHT.spin_button_width > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_button_style.py -v`
Expected: FAIL because `button_style.py` does not exist and new theme tokens are missing.

- [ ] **Step 3: Write minimal implementation**

```python
# src/shared/ui/button_style.py
def build_button_stylesheet(theme):
    return f'''
        QPushButton[variant="primary"] {{
            border-radius: {theme.button_radius}px;
            min-height: {theme.button_height_md}px;
            padding: {theme.button_padding_y}px {theme.button_padding_x}px;
        }}
    '''
```

```python
# src/shared/ui/theme.py
button_radius: int = 6
button_padding_x: int = 16
button_padding_y: int = 6
button_height_md: int = 36
button_font_weight: int = 500
input_radius: int = 6
input_padding_x: int = 8
input_padding_y: int = 4
input_icon_size: int = 16
input_clear_button_size: int = 20
input_separator_width: int = 1
input_separator_height: int = 16
combo_arrow_zone_width: int = 28
combo_arrow_size: int = 10
combo_popup_padding: int = 4
combo_popup_item_padding_x: int = 12
combo_popup_item_padding_y: int = 6
combo_popup_offset_y: int = 2
combo_popup_radius: int = 10
spin_button_width: int = 24
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_button_style.py -v`
Expected: PASS

- [ ] **Step 5: Local checkpoint**

Run: `python -m compileall src/shared/ui/theme.py src/shared/ui/button_style.py tests/test_button_style.py`
Expected: files compile without syntax errors.

### Task 2: Refactor `SearchInput` into the only formal search widget

**Files:**
- Modify: `src/shared/ui/search_input.py`
- Test: `tests/test_search_input_styles.py`
- Modify: `demo_style_gallery.py`

- [ ] **Step 1: Write the failing tests**

```python
import inspect

from src.shared.ui.search_input import SearchInput
from src.shared.ui.theme import LIGHT


def test_search_input_uses_theme_tokens_in_stylesheet():
    qss = SearchInput.build_container_stylesheet("SearchInput", LIGHT, focused=False)

    assert f"border-radius: {LIGHT.input_radius}px;" in qss
    assert f"padding: 0 {LIGHT.input_padding_x}px;" in qss or LIGHT.input_padding_x >= 0


def test_search_input_module_has_no_duplicate_clear_button_stylesheet_calls():
    source = inspect.getsource(SearchInput._apply_theme)
    assert source.count("setStyleSheet") <= 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_search_input_styles.py -v`
Expected: FAIL because helper methods/tests do not match current implementation.

- [ ] **Step 3: Write minimal implementation**

```python
class SearchInput(QWidget):
    @staticmethod
    def build_container_stylesheet(object_name, theme, *, focused):
        border_color = theme.border_focus if focused else theme.border
        background = theme.bg_window if focused else theme.bg_input
        return f"""
            #{object_name} {{
                background: {background};
                border: 1px solid {border_color};
                border-radius: {theme.input_radius}px;
            }}
        """
```

```python
self.setAttribute(Qt.WA_StyledBackground, True)
layout.setContentsMargins(theme.input_padding_x, 0, theme.input_padding_x // 2, 0)
self._icon.setFixedSize(theme.input_clear_button_size, theme.input_clear_button_size)
self._clear_btn.setFixedSize(theme.input_clear_button_size, theme.input_clear_button_size)
self._separator.setFixedSize(theme.input_separator_width, theme.input_separator_height)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_search_input_styles.py -v`
Expected: PASS

- [ ] **Step 5: Local checkpoint**

Run: `pytest tests/test_search_input_styles.py tests/test_phase4_ui.py -v`
Expected: search-input regression stays green.

### Task 3: Extract `StyledComboBox` shared base and migrate popup tests

**Files:**
- Create: `src/shared/ui/styled_combo_box.py`
- Modify: `tests/test_combo_popup_styles.py`
- Test: `tests/test_combo_architecture.py`

- [ ] **Step 1: Write the failing tests**

```python
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import LIGHT


def test_popup_container_qss_paints_surface_instead_of_transparent_shell():
    qss = StyledComboBox.build_popup_container_qss("popup_shell", LIGHT)
    assert f"background: {LIGHT.bg_card};" in qss
    assert "background: transparent;" not in qss.lower()


def test_styled_combo_box_uses_combo_tokens():
    qss = StyledComboBox.build_combo_stylesheet("combo_id", LIGHT)
    assert f"padding-right: {LIGHT.combo_arrow_zone_width}px;" in qss
    assert f"width: {LIGHT.combo_arrow_zone_width}px;" in qss
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_combo_popup_styles.py tests/test_combo_architecture.py -v`
Expected: FAIL because shared combo base does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
class StyledComboBox(QComboBox):
    @staticmethod
    def build_popup_container_qss(popup_id, theme):
        ...

    @staticmethod
    def build_popup_view_qss(view_id, theme):
        ...

    @staticmethod
    def build_combo_stylesheet(object_name, theme):
        ...
```

```python
def showPopup(self):
    super().showPopup()
    popup = self.view().window()
    popup.setStyleSheet(self._popup_shell_qss)
    QTimer.singleShot(0, self._sync_popup_geometry)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_combo_popup_styles.py tests/test_combo_architecture.py -v`
Expected: PASS

- [ ] **Step 5: Local checkpoint**

Run: `python -m compileall src/shared/ui/styled_combo_box.py tests/test_combo_popup_styles.py tests/test_combo_architecture.py`
Expected: files compile without syntax errors.

### Task 4: Migrate combo-derived widgets and raw combo call sites

**Files:**
- Modify: `src/shared/ui/font_combo.py`
- Modify: `src/shared/ui/size_combo.py`
- Modify: `src/shared/ui/numbering_preset.py`
- Modify: `src/shared/ui/spacing_input.py`
- Modify: `src/ui/panels/heading_numbering_panel.py`
- Test: `tests/test_combo_architecture.py`

- [ ] **Step 1: Write the failing tests**

```python
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.numbering_preset import NumberingPreset
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.styled_combo_box import StyledComboBox


def test_combo_widgets_inherit_shared_base():
    assert issubclass(FontCombo, StyledComboBox)
    assert issubclass(SizeCombo, StyledComboBox)
    assert issubclass(NumberingPreset, StyledComboBox)


def test_spacing_input_uses_shared_unit_combo():
    widget = SpacingInput()
    assert isinstance(widget._unit, StyledComboBox)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_combo_architecture.py -v`
Expected: FAIL because widgets still inherit raw `QComboBox`.

- [ ] **Step 3: Write minimal implementation**

```python
class FontCombo(StyledComboBox):
    ...


class SizeCombo(StyledComboBox):
    ...


class NumberingPreset(StyledComboBox):
    ...
```

```python
self._unit = StyledComboBox()
self._preset_cb = StyledComboBox()
self._levels_cb = StyledComboBox()
self._core_style_cb = StyledComboBox()
self._chain_cb = StyledComboBox()
self._ref_style_cb = StyledComboBox()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_combo_architecture.py -v`
Expected: PASS

- [ ] **Step 5: Local checkpoint**

Run: `pytest tests/test_combo_architecture.py tests/test_phase4_ui.py -v`
Expected: combo migration stays green.

### Task 5: Convert `demo_style_gallery.py` into a display-only showcase

**Files:**
- Modify: `demo_style_gallery.py`
- Modify: `src/shared/ui/button_style.py`
- Test: `tests/test_demo_gallery_architecture.py`

- [ ] **Step 1: Write the failing tests**

```python
import inspect

import demo_style_gallery as dsg


def test_demo_gallery_no_longer_defines_private_formal_combo_or_search_widgets():
    source = inspect.getsource(dsg)
    assert "class _StyledComboBox" not in source
    assert "class _SearchLineEdit" not in source


def test_demo_gallery_uses_button_variant_helper_instead_of_button_object_names():
    source = inspect.getsource(dsg)
    assert 'setObjectName("btn_primary")' not in source
    assert 'setProperty("variant", "primary")' in source or "apply_button_variant" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_demo_gallery_architecture.py -v`
Expected: FAIL because the demo still defines private widgets and button IDs.

- [ ] **Step 3: Write minimal implementation**

```python
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.search_input import SearchInput
from src.shared.ui.styled_combo_box import StyledComboBox
```

```python
button = QPushButton("Primary 主按钮")
apply_button_variant(button, "primary")

search = SearchInput("请输入关键词…")
combo = StyledComboBox()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_demo_gallery_architecture.py -v`
Expected: PASS

- [ ] **Step 5: Local checkpoint**

Run: `python -m compileall demo_style_gallery.py tests/test_demo_gallery_architecture.py`
Expected: files compile without syntax errors.

### Task 6: Export shared UI API and run verification

**Files:**
- Modify: `src/shared/ui/__init__.py`
- Test: `tests/test_ui_exports.py`
- Run: targeted pytest suite + broader regression suite

- [ ] **Step 1: Write the failing tests**

```python
from src.shared.ui import (
    SearchInput,
    StyledComboBox,
    FontCombo,
    SizeCombo,
    NumberingPreset,
)


def test_shared_ui_exports_include_unified_controls():
    assert SearchInput.__name__ == "SearchInput"
    assert StyledComboBox.__name__ == "StyledComboBox"
    assert FontCombo.__name__ == "FontCombo"
    assert SizeCombo.__name__ == "SizeCombo"
    assert NumberingPreset.__name__ == "NumberingPreset"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ui_exports.py -v`
Expected: FAIL because `src/shared/ui/__init__.py` is empty.

- [ ] **Step 3: Write minimal implementation**

```python
from .button_style import apply_button_variant, build_button_stylesheet
from .font_combo import FontCombo
from .numbering_preset import NumberingPreset
from .search_input import SearchInput
from .size_combo import SizeCombo
from .styled_combo_box import StyledComboBox
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ui_exports.py -v`
Expected: PASS

- [ ] **Step 5: Final verification**

Run: `pytest tests/test_button_style.py tests/test_search_input_styles.py tests/test_combo_popup_styles.py tests/test_combo_architecture.py tests/test_demo_gallery_architecture.py tests/test_ui_exports.py tests/test_phase4_ui.py -v`
Expected: PASS

Run: `pytest tests/test_phase0_smoke.py tests/test_phase1_config.py tests/test_phase2_engine.py tests/test_phase3_basic.py tests/test_phase3_fill.py tests/test_phase3_special.py tests/test_phase3_structure.py tests/test_phase3_table.py tests/test_phase4_ui.py tests/test_phase5_e2e.py -v`
Expected: no regressions introduced by the UI refactor.

## Self-review

- **Spec coverage:** theme token expansion, shared button helper, shared `SearchInput`, shared `StyledComboBox`, combo-family migration, raw combo migration, demo display-only conversion, and export cleanup are all covered by Tasks 1-6.
- **Placeholder scan:** no `TODO`/`TBD` placeholders remain; each task lists concrete files, tests, and commands.
- **Type consistency:** all combo migration tasks target the same shared base name `StyledComboBox`; button variants consistently use the `variant` property and `apply_button_variant`.
