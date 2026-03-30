# Self-Drawn Selection Controls Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current Radio / Slider geometry-by-QSS approach with project-owned self-drawn controls that keep true circular geometry under DPI scaling.

**Architecture:** Keep `QCheckBox` on the existing shared stylesheet path, but add a new self-drawn Radio / Slider stack in `src/shared/ui/` built from `QAbstractButton` / `QAbstractSlider`, shared metrics clamps, and shared painter helpers. The current repository has no real business panel that uses Radio / Slider beyond the gallery, so this phase lands the reusable controls, updates the gallery and guard-rail tests, and leaves a clean import path for the first future business page.

**Tech Stack:** Python, PySide6, pytest, `PySide6.QtTest`, shared UI theme/token infrastructure

---

> [!IMPORTANT]
> **Post-implementation status update (2026-03-28):**
> - The runtime cleanup is complete: `selection_control_style.py` is now Checkbox-only in active code.
> - Any references below to `build_radio_stylesheet()` or `build_selection_control_stylesheet()` should be read as historical execution context from before the final Checkbox-boundary cleanup.
> - The current live split is: Checkbox -> `build_checkbox_stylesheet()`; Radio / Slider -> `ThemedRadioButton` / `ThemedSlider`.

## File map

- Create: `src/shared/ui/selection_control_metrics.py`
  - Geometry-first dataclasses and clamp helpers for Radio / Slider metrics
- Create: `src/shared/ui/selection_control_painter.py`
  - Shared paint helpers for focus rings, radio rings/dots, slider track, and slider handle
- Create: `src/shared/ui/themed_radio_button.py`
  - `QAbstractButton`-based self-drawn radio control
- Create: `src/shared/ui/themed_slider.py`
  - `QAbstractSlider`-based self-drawn horizontal slider
- Modify: `src/shared/ui/theme.py`
  - Add geometry-first Radio / Slider tokens while keeping Checkbox and transitional QSS tokens intact
- Modify: `src/shared/ui/__init__.py`
  - Export the new controls
- Modify: `src/shared/ui/input_guard.py`
  - Treat any `QAbstractSlider` subclass, including `ThemedSlider`, as wheel-guarded
- Modify: `src/qt_api.py`
  - Export `QAbstractSlider` so the new control stack stays on the repository’s single Qt entrypoint
- Modify: `demo_style_gallery.py`
  - Replace `QRadioButton` / `QSlider` showcase usage with `ThemedRadioButton` / `ThemedSlider`
- Modify: `tests/test_demo_gallery_architecture.py`
  - Remove old `QSlider::handle` expectations and assert the new shared controls are used
- Modify: `tests/test_ui_exports.py`
  - Export smoke coverage for `ThemedRadioButton` / `ThemedSlider`
- Modify: `tests/test_input_guard.py`
  - Cover wheel guarding for the new slider path
- Modify: `tests/test_phase4_ui.py`
  - Count and import the two new shared UI controls
- Create: `tests/test_selection_control_metrics.py`
  - Token and clamp coverage
- Create: `tests/test_themed_radio_button.py`
  - Geometry, signal, and rendering coverage for the self-drawn radio
- Create: `tests/test_themed_slider.py`
  - Geometry, interaction, input-guard, and rendering coverage for the self-drawn slider

### Task 1: Add geometry-first tokens, Qt exports, and metrics clamps

**Files:**
- Modify: `src/qt_api.py`
- Modify: `src/shared/ui/theme.py`
- Create: `src/shared/ui/selection_control_metrics.py`
- Create: `tests/test_selection_control_metrics.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_selection_control_metrics.py
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QAbstractSlider
from src.shared.ui.selection_control_metrics import (
    RadioMetrics,
    SliderMetrics,
    build_radio_metrics,
    build_slider_metrics,
)
from src.shared.ui.theme import LIGHT


def test_qt_api_exports_qabstractslider_for_shared_controls():
    assert QAbstractSlider.__name__ == "QAbstractSlider"


def test_theme_exposes_geometry_first_selection_control_tokens():
    assert LIGHT.radio_indicator_diameter == 18
    assert LIGHT.radio_ring_width == 1
    assert LIGHT.radio_dot_diameter == 7
    assert LIGHT.radio_hit_padding_x >= 4
    assert LIGHT.radio_hit_padding_y >= 4
    assert LIGHT.slider_track_height == 4
    assert LIGHT.slider_handle_diameter == 20
    assert LIGHT.slider_handle_ring_width == 1
    assert LIGHT.slider_hit_extra_radius >= 4


def test_build_radio_metrics_clamps_invalid_values():
    metrics = build_radio_metrics(
        LIGHT.merge(
            {
                "radio_indicator_diameter": 4,
                "radio_ring_width": 9,
                "radio_dot_diameter": 99,
                "radio_focus_ring_width": 50,
            }
        )
    )

    assert isinstance(metrics, RadioMetrics)
    assert metrics.indicator_diameter >= 12
    assert metrics.ring_width <= metrics.indicator_diameter / 2
    assert metrics.dot_diameter < metrics.indicator_diameter
    assert metrics.focus_ring_width <= metrics.indicator_diameter / 2


def test_build_slider_metrics_clamps_invalid_values():
    metrics = build_slider_metrics(
        LIGHT.merge(
            {
                "slider_track_height": 0,
                "slider_handle_diameter": 6,
                "slider_handle_ring_width": 12,
                "slider_focus_ring_width": 40,
                "slider_hit_extra_radius": -5,
            }
        )
    )

    assert isinstance(metrics, SliderMetrics)
    assert metrics.track_height >= 2
    assert metrics.handle_diameter >= 12
    assert metrics.handle_ring_width <= metrics.handle_diameter / 2
    assert metrics.focus_ring_width <= metrics.handle_diameter / 2
    assert metrics.hit_extra_radius >= 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_selection_control_metrics.py -v`

Expected: FAIL because `QAbstractSlider` is not exported from `src/qt_api.py`, the new theme tokens do not exist, and `selection_control_metrics.py` does not exist.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/qt_api.py
from PySide6.QtWidgets import QAbstractSlider

__all__.append("QAbstractSlider")
```

```python
# src/shared/ui/theme.py  (inside AppTheme)
radio_indicator_diameter: int = 18
radio_dot_diameter: int = 7
radio_hit_padding_x: int = 6
radio_hit_padding_y: int = 4
radio_color_ring: str = ""
radio_color_ring_hover: str = ""
radio_color_ring_checked: str = ""
radio_color_ring_disabled: str = ""
radio_color_dot: str = ""
radio_color_dot_disabled: str = ""
radio_color_bg: str = ""
radio_color_bg_disabled: str = ""
radio_focus_ring_color: str = ""
radio_focus_ring_width: int = 2

slider_track_height: int = 4
slider_handle_diameter: int = 20
slider_handle_ring_width: int = 1
slider_active_track_color: str = ""
slider_inactive_track_color: str = ""
slider_handle_color: str = ""
slider_handle_border_color: str = ""
slider_handle_hover_border_color: str = ""
slider_handle_pressed_border_color: str = ""
slider_handle_disabled_color: str = ""
slider_focus_ring_color: str = ""
slider_focus_ring_width: int = 2
slider_hit_extra_radius: int = 6
```

```python
# src/shared/ui/theme.py  (inside __post_init__)
if not self.radio_color_ring:
    self.radio_color_ring = self.border
if not self.radio_color_ring_hover:
    self.radio_color_ring_hover = self.border_focus
if not self.radio_color_ring_checked:
    self.radio_color_ring_checked = self.primary
if not self.radio_color_ring_disabled:
    self.radio_color_ring_disabled = self.border_light
if not self.radio_color_dot:
    self.radio_color_dot = self.primary
if not self.radio_color_dot_disabled:
    self.radio_color_dot_disabled = self.text_disabled
if not self.radio_color_bg:
    self.radio_color_bg = self.bg_input
if not self.radio_color_bg_disabled:
    self.radio_color_bg_disabled = self.bg_hover
if not self.radio_focus_ring_color:
    self.radio_focus_ring_color = self.primary

if not self.slider_active_track_color:
    self.slider_active_track_color = self.primary
if not self.slider_inactive_track_color:
    self.slider_inactive_track_color = self.progress_track
if not self.slider_handle_color:
    self.slider_handle_color = self.bg_card
if not self.slider_handle_border_color:
    self.slider_handle_border_color = self.border
if not self.slider_handle_hover_border_color:
    self.slider_handle_hover_border_color = self.border_focus
if not self.slider_handle_pressed_border_color:
    self.slider_handle_pressed_border_color = self.primary_pressed
if not self.slider_handle_disabled_color:
    self.slider_handle_disabled_color = self.bg_hover
if not self.slider_focus_ring_color:
    self.slider_focus_ring_color = self.primary
```

```python
# src/shared/ui/selection_control_metrics.py
from __future__ import annotations

from dataclasses import dataclass

from src.shared.ui.theme import AppTheme


@dataclass(frozen=True)
class RadioMetrics:
    indicator_diameter: float
    ring_width: float
    dot_diameter: float
    label_gap: int
    hit_padding_x: int
    hit_padding_y: int
    focus_ring_width: float


@dataclass(frozen=True)
class SliderMetrics:
    track_height: float
    handle_diameter: float
    handle_ring_width: float
    hit_extra_radius: int
    focus_ring_width: float


def build_radio_metrics(theme: AppTheme) -> RadioMetrics:
    indicator = max(12.0, float(theme.radio_indicator_diameter))
    ring_width = min(indicator / 2.0, max(1.0, float(theme.radio_ring_width)))
    inner_limit = max(2.0, indicator - ring_width * 2.0)
    dot = min(inner_limit, max(2.0, float(theme.radio_dot_diameter)))
    focus = min(indicator / 2.0, max(1.0, float(theme.radio_focus_ring_width)))
    return RadioMetrics(
        indicator_diameter=indicator,
        ring_width=ring_width,
        dot_diameter=dot,
        label_gap=int(max(0, theme.radio_label_gap)),
        hit_padding_x=int(max(0, theme.radio_hit_padding_x)),
        hit_padding_y=int(max(0, theme.radio_hit_padding_y)),
        focus_ring_width=focus,
    )


def build_slider_metrics(theme: AppTheme) -> SliderMetrics:
    handle = max(12.0, float(theme.slider_handle_diameter))
    ring_width = min(handle / 2.0, max(1.0, float(theme.slider_handle_ring_width)))
    focus = min(handle / 2.0, max(1.0, float(theme.slider_focus_ring_width)))
    return SliderMetrics(
        track_height=max(2.0, float(theme.slider_track_height)),
        handle_diameter=handle,
        handle_ring_width=ring_width,
        hit_extra_radius=int(max(0, theme.slider_hit_extra_radius)),
        focus_ring_width=focus,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_selection_control_metrics.py -v`

Expected: PASS

- [ ] **Step 5: Local checkpoint**

Run: `python -m compileall src/qt_api.py src/shared/ui/theme.py src/shared/ui/selection_control_metrics.py tests/test_selection_control_metrics.py`

Expected: all files compile without syntax errors.

### Task 2: Implement shared painter helpers and `ThemedRadioButton`

**Files:**
- Create: `src/shared/ui/selection_control_painter.py`
- Create: `src/shared/ui/themed_radio_button.py`
- Modify: `src/shared/ui/__init__.py`
- Create: `tests/test_themed_radio_button.py`
- Modify: `tests/test_ui_exports.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_themed_radio_button.py
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui.themed_radio_button import ThemedRadioButton


def _non_transparent_bounds(image):
    xs = []
    ys = []
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).alpha() > 0:
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def test_themed_radio_indicator_rect_is_square():
    app = QApplication.instance() or QApplication([])
    button = ThemedRadioButton("选项 A")
    button.resize(button.sizeHint())

    rect = button._indicator_rect()

    assert abs(rect.width() - rect.height()) <= 0.01


def test_themed_radio_click_emits_checked_state():
    app = QApplication.instance() or QApplication([])
    button = ThemedRadioButton("选项 A")
    states = []
    button.toggled.connect(states.append)

    button.click()

    assert button.isChecked() is True
    assert states == [True]


def test_themed_radio_rendered_indicator_stays_visually_square():
    app = QApplication.instance() or QApplication([])
    button = ThemedRadioButton("选项 A")
    button.setChecked(True)
    button.resize(button.sizeHint())
    button.show()
    app.processEvents()

    image = button.grab().toImage()
    left, top, right, bottom = _non_transparent_bounds(image)
    indicator_rect = button._indicator_rect().toAlignedRect()

    assert abs(indicator_rect.width() - indicator_rect.height()) <= 1
    assert abs((right - left) - (bottom - top)) <= indicator_rect.width() + 10
```

```python
# tests/test_ui_exports.py
from src.shared.ui import (
    FontCombo,
    NumberingPreset,
    SearchInput,
    SizeCombo,
    StyledComboBox,
    ThemedRadioButton,
    apply_button_variant,
    build_button_stylesheet,
    build_checkbox_stylesheet,
    build_radio_stylesheet,
    build_selection_control_stylesheet,
)


def test_shared_ui_exports_include_self_drawn_selection_controls():
    assert ThemedRadioButton.__name__ == "ThemedRadioButton"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_themed_radio_button.py tests/test_ui_exports.py -v`

Expected: FAIL because `ThemedRadioButton` and the shared painter helpers do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/shared/ui/selection_control_painter.py
from __future__ import annotations

from src.qt_api import QBrush, QColor, QPainter, QPen, QRectF, Qt


def draw_focus_ring(painter: QPainter, rect: QRectF, *, color: str, width: float) -> None:
    painter.save()
    painter.setPen(QPen(QColor(color), width))
    painter.setBrush(Qt.NoBrush)
    painter.drawEllipse(rect)
    painter.restore()


def draw_radio_indicator(
    painter: QPainter,
    outer_rect: QRectF,
    *,
    ring_color: str,
    bg_color: str,
    ring_width: float,
    dot_color: str | None = None,
    dot_diameter: float = 0.0,
) -> None:
    painter.save()
    painter.setPen(QPen(QColor(ring_color), ring_width))
    painter.setBrush(QBrush(QColor(bg_color)))
    painter.drawEllipse(outer_rect)
    if dot_color and dot_diameter > 0:
        inset = (outer_rect.width() - dot_diameter) / 2.0
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(dot_color)))
        painter.drawEllipse(outer_rect.adjusted(inset, inset, -inset, -inset))
    painter.restore()
```

```python
# src/shared/ui/themed_radio_button.py
from __future__ import annotations

from src.qt_api import QAbstractButton, QPainter, QRectF, QSize, Qt

from src.shared.ui.selection_control_metrics import build_radio_metrics
from src.shared.ui.selection_control_painter import draw_focus_ring, draw_radio_indicator
from src.shared.ui.theme import bind_theme, get_theme


class ThemedRadioButton(QAbstractButton):
    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._hovered = False
        self._pressed = False
        bind_theme(self, self.update)

    def sizeHint(self) -> QSize:
        metrics = build_radio_metrics(get_theme())
        fm = self.fontMetrics()
        width = int(
            metrics.hit_padding_x * 2
            + metrics.indicator_diameter
            + metrics.label_gap
            + max(0, fm.horizontalAdvance(self.text()))
        )
        height = int(
            max(metrics.indicator_diameter, fm.height()) + metrics.hit_padding_y * 2
        )
        return QSize(width, height)

    def _indicator_rect(self) -> QRectF:
        metrics = build_radio_metrics(get_theme())
        top = (self.height() - metrics.indicator_diameter) / 2.0
        return QRectF(
            float(metrics.hit_padding_x),
            top,
            metrics.indicator_diameter,
            metrics.indicator_diameter,
        )

    def paintEvent(self, event) -> None:
        theme = get_theme()
        metrics = build_radio_metrics(theme)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        indicator = self._indicator_rect()
        if self.hasFocus():
            draw_focus_ring(
                painter,
                indicator.adjusted(-3, -3, 3, 3),
                color=theme.radio_focus_ring_color,
                width=metrics.focus_ring_width,
            )

        ring_color = theme.radio_color_ring_disabled if not self.isEnabled() else theme.radio_color_ring
        if self.isEnabled() and self._hovered:
            ring_color = theme.radio_color_ring_hover
        if self.isChecked():
            ring_color = theme.radio_color_ring_checked if self.isEnabled() else theme.radio_color_ring_disabled

        bg_color = theme.radio_color_bg if self.isEnabled() else theme.radio_color_bg_disabled
        dot_color = None
        if self.isChecked():
            dot_color = theme.radio_color_dot if self.isEnabled() else theme.radio_color_dot_disabled

        draw_radio_indicator(
            painter,
            indicator,
            ring_color=ring_color,
            bg_color=bg_color,
            ring_width=metrics.ring_width,
            dot_color=dot_color,
            dot_diameter=metrics.dot_diameter,
        )

        text_left = int(indicator.right() + metrics.label_gap)
        text_rect = self.rect().adjusted(text_left, 0, 0, 0)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._pressed = False
        self.update()
        super().leaveEvent(event)
```

```python
# src/shared/ui/__init__.py
from .themed_radio_button import ThemedRadioButton

__all__.append("ThemedRadioButton")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_themed_radio_button.py tests/test_ui_exports.py -v`

Expected: PASS

- [ ] **Step 5: Local checkpoint**

Run: `python -m compileall src/shared/ui/selection_control_painter.py src/shared/ui/themed_radio_button.py src/shared/ui/__init__.py tests/test_themed_radio_button.py tests/test_ui_exports.py`

Expected: all files compile without syntax errors.

### Task 3: Implement `ThemedSlider` and make wheel guarding slider-class-based

**Files:**
- Create: `src/shared/ui/themed_slider.py`
- Modify: `src/shared/ui/input_guard.py`
- Modify: `tests/test_input_guard.py`
- Create: `tests/test_themed_slider.py`
- Modify: `src/shared/ui/__init__.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_themed_slider.py
import sys
from pathlib import Path

from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, Qt
from src.shared.ui.themed_slider import ThemedSlider


def test_themed_slider_handle_rect_is_square():
    app = QApplication.instance() or QApplication([])
    slider = ThemedSlider(Qt.Horizontal)
    slider.resize(220, 36)

    rect = slider._handle_rect_for_value(slider.value())

    assert abs(rect.width() - rect.height()) <= 0.01


def test_themed_slider_keyboard_and_click_update_value():
    app = QApplication.instance() or QApplication([])
    slider = ThemedSlider(Qt.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(25)
    slider.resize(220, 36)
    slider.show()
    slider.setFocus()
    app.processEvents()

    QTest.keyClick(slider, Qt.Key_Right)
    QTest.mouseClick(slider, Qt.LeftButton, pos=QPoint(slider.width() - 12, slider.height() // 2))
    app.processEvents()

    assert slider.value() > 25


def test_themed_slider_drag_emits_slider_lifecycle_signals():
    app = QApplication.instance() or QApplication([])
    slider = ThemedSlider(Qt.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(10)
    slider.resize(220, 36)
    slider.show()
    app.processEvents()

    pressed = []
    released = []
    slider.sliderPressed.connect(lambda: pressed.append(True))
    slider.sliderReleased.connect(lambda: released.append(True))

    start = slider._handle_rect_for_value(slider.value()).center().toPoint()
    end = QPoint(slider.width() - 10, slider.height() // 2)
    QTest.mousePress(slider, Qt.LeftButton, pos=start)
    QTest.mouseMove(slider, end)
    QTest.mouseRelease(slider, Qt.LeftButton, pos=end)
    app.processEvents()

    assert pressed == [True]
    assert released == [True]
    assert slider.value() > 10
```

```python
# tests/test_input_guard.py
from src.qt_api import QApplication, Qt
from src.shared.ui.input_guard import GlobalInputGuard
from src.shared.ui.themed_slider import ThemedSlider


def test_global_input_guard_blocks_themed_slider_wheel_changes():
    _app = QApplication.instance() or QApplication([])
    guard = GlobalInputGuard()
    slider = ThemedSlider(Qt.Horizontal)
    event = QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.NoButton,
        Qt.NoModifier,
        Qt.ScrollUpdate,
        False,
    )

    handled = guard.eventFilter(slider, event)

    assert handled is True
    assert event.isAccepted() is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_themed_slider.py tests/test_input_guard.py -v`

Expected: FAIL because `ThemedSlider` does not exist and the input guard only recognizes `QSlider`.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/shared/ui/input_guard.py
from src.qt_api import QAbstractItemView, QAbstractSlider, QAbstractSpinBox, QComboBox, QEvent, QObject, Qt

# inside GlobalInputGuard.eventFilter():
if isinstance(curr, (QComboBox, QAbstractSpinBox, QAbstractSlider)):
    event.ignore()
    return True
```

```python
# src/shared/ui/themed_slider.py
from __future__ import annotations

from src.qt_api import QAbstractSlider, QBrush, QColor, QPainter, QPen, QRectF, QSize, Qt

from src.shared.ui.selection_control_metrics import build_slider_metrics
from src.shared.ui.selection_control_painter import draw_focus_ring
from src.shared.ui.theme import bind_theme, get_theme


class ThemedSlider(QAbstractSlider):
    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(parent)
        self.setOrientation(orientation)
        self.setRange(0, 100)
        self.setSingleStep(1)
        self.setPageStep(10)
        self.setFocusPolicy(Qt.StrongFocus)
        self._hovered = False
        self._pressed = False
        bind_theme(self, self.update)

    def sizeHint(self) -> QSize:
        metrics = build_slider_metrics(get_theme())
        height = int(metrics.handle_diameter + metrics.hit_extra_radius * 2)
        return QSize(160, max(32, height))

    def _track_rect(self) -> QRectF:
        metrics = build_slider_metrics(get_theme())
        y = (self.height() - metrics.track_height) / 2.0
        margin = metrics.handle_diameter / 2.0
        return QRectF(margin, y, max(1.0, self.width() - margin * 2.0), metrics.track_height)

    def _handle_rect_for_value(self, value: int) -> QRectF:
        metrics = build_slider_metrics(get_theme())
        track = self._track_rect()
        span = max(1, self.maximum() - self.minimum())
        ratio = (value - self.minimum()) / span
        center_x = track.left() + track.width() * ratio
        top = (self.height() - metrics.handle_diameter) / 2.0
        half = metrics.handle_diameter / 2.0
        return QRectF(center_x - half, top, metrics.handle_diameter, metrics.handle_diameter)

    def _value_from_pos(self, x: float) -> int:
        track = self._track_rect()
        if track.width() <= 0:
            return self.minimum()
        ratio = min(1.0, max(0.0, (x - track.left()) / track.width()))
        return int(round(self.minimum() + ratio * (self.maximum() - self.minimum())))

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        self._pressed = True
        self.setSliderDown(True)
        self.sliderPressed.emit()
        self.setValue(self._value_from_pos(event.position().x()))
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if self.isSliderDown():
            self.setValue(self._value_from_pos(event.position().x()))
            self.sliderMoved.emit(self.value())
            self.update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self.isSliderDown() and event.button() == Qt.LeftButton:
            self._pressed = False
            self.setSliderDown(False)
            self.sliderReleased.emit()
            self.update()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Right:
            self.setValue(min(self.maximum(), self.value() + self.singleStep()))
            return
        if event.key() == Qt.Key_Left:
            self.setValue(max(self.minimum(), self.value() - self.singleStep()))
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:
        theme = get_theme()
        metrics = build_slider_metrics(theme)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        track = self._track_rect()
        handle = self._handle_rect_for_value(self.value())
        active = QRectF(track.left(), track.top(), max(0.0, handle.center().x() - track.left()), track.height())

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(theme.slider_inactive_track_color)))
        painter.drawRoundedRect(track, track.height() / 2.0, track.height() / 2.0)
        painter.setBrush(QBrush(QColor(theme.slider_active_track_color)))
        painter.drawRoundedRect(active, track.height() / 2.0, track.height() / 2.0)

        if self.hasFocus():
            draw_focus_ring(
                painter,
                handle.adjusted(-3, -3, 3, 3),
                color=theme.slider_focus_ring_color,
                width=metrics.focus_ring_width,
            )

        border = theme.slider_handle_border_color
        if self._hovered:
            border = theme.slider_handle_hover_border_color
        if self._pressed:
            border = theme.slider_handle_pressed_border_color

        painter.setPen(QPen(QColor(border), metrics.handle_ring_width))
        painter.setBrush(QBrush(QColor(theme.slider_handle_color if self.isEnabled() else theme.slider_handle_disabled_color)))
        painter.drawEllipse(handle)
```

```python
# src/shared/ui/__init__.py
from .themed_slider import ThemedSlider

__all__.append("ThemedSlider")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_themed_slider.py tests/test_input_guard.py -v`

Expected: PASS

- [ ] **Step 5: Local checkpoint**

Run: `python -m compileall src/shared/ui/themed_slider.py src/shared/ui/input_guard.py tests/test_themed_slider.py tests/test_input_guard.py`

Expected: all files compile without syntax errors.

### Task 4: Integrate the new controls into shared exports, gallery, and architecture tests

**Files:**
- Modify: `demo_style_gallery.py`
- Modify: `tests/test_demo_gallery_architecture.py`
- Modify: `tests/test_ui_exports.py`
- Modify: `tests/test_phase4_ui.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_demo_gallery_architecture.py
def test_demo_gallery_uses_self_drawn_radio_and_slider_controls():
    source = inspect.getsource(dsg)

    assert "from src.shared.ui import ThemedRadioButton, ThemedSlider" in source
    assert "ThemedRadioButton(" in source
    assert "ThemedSlider(" in source
    assert "QSlider::handle:horizontal" not in source


def test_demo_gallery_no_longer_uses_qradiobutton_for_round_geometry():
    source = inspect.getsource(dsg)

    assert "QRadioButton(" not in source
```

```python
# tests/test_ui_exports.py
from src.shared.ui import ThemedRadioButton, ThemedSlider


def test_shared_ui_exports_include_self_drawn_selection_controls():
    assert ThemedRadioButton.__name__ == "ThemedRadioButton"
    assert ThemedSlider.__name__ == "ThemedSlider"
```

```python
# tests/test_phase4_ui.py
def _get_atomic_classes():
    from src.shared.ui.themed_radio_button import ThemedRadioButton
    from src.shared.ui.themed_slider import ThemedSlider
    from src.shared.ui.toggle_switch import ToggleSwitch
    from src.shared.ui.icon_button import IconButton
    from src.shared.ui.search_input import SearchInput
    from src.shared.ui.status_indicator import StatusIndicator
    from src.shared.ui.confirm_dialog import ConfirmDialog
    from src.shared.ui.form_row import FormRow
    return [
        ThemedRadioButton,
        ThemedSlider,
        ToggleSwitch,
        IconButton,
        SearchInput,
        StatusIndicator,
        ConfirmDialog,
        FormRow,
    ]


def test_atomic_imports():
    classes = _get_atomic_classes()
    assert len(classes) == 8


def test_all_unique():
    all_classes = _get_atomic_classes() + _get_layout_classes() + _get_domain_classes()
    names = [cls.__name__ for cls in all_classes]
    assert len(names) == 21
    assert len(set(names)) == 21
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_demo_gallery_architecture.py tests/test_ui_exports.py tests/test_phase4_ui.py -v`

Expected: FAIL because the gallery still uses `QRadioButton` / `QSlider` and the shared export/count tests do not know about the new controls yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# demo_style_gallery.py  (imports)
from src.shared.ui import ThemedRadioButton, ThemedSlider
```

```python
# demo_style_gallery.py  (selection showcase helper)
def _build_selection_showcase_row() -> QWidget:
    cb1 = QCheckBox("默认未选")
    cb2 = QCheckBox("已选中")
    cb2.setChecked(True)
    cb3 = QCheckBox("禁用")
    cb3.setEnabled(False)
    cb4 = QCheckBox("禁用且已选")
    cb4.setChecked(True)
    cb4.setEnabled(False)

    rb1 = ThemedRadioButton("选项 A")
    rb2 = ThemedRadioButton("选项 B")
    rb2.setChecked(True)
    rb3 = ThemedRadioButton("禁用")
    rb3.setEnabled(False)

    return _hbox(cb1, cb2, cb3, cb4, "stretch", rb1, rb2, rb3)
```

```python
# demo_style_gallery.py  (slider showcase helper)
def _build_slider_showcase_row() -> QWidget:
    slider = ThemedSlider(Qt.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(60)
    slider.setFixedHeight(get_theme().control_height_md)

    pb = QProgressBar()
    pb.setRange(0, 100)
    pb.setValue(75)
    pb.setFixedHeight(16)
    return _hbox(slider, pb)
```

```python
# demo_style_gallery.py  (_build_focus_preview / _build_section_native)
self._main_layout.addWidget(_subsection_title("✅ QCheckBox / ThemedRadioButton（共享 selection controls）"))
self._main_layout.addWidget(_build_selection_showcase_row())

self._main_layout.addWidget(_subsection_title("✅ ThemedSlider / QProgressBar（共享 selection controls）"))
self._main_layout.addWidget(_build_slider_showcase_row())
```

```python
# demo_style_gallery.py  (_apply_theme)
selection_qss = build_checkbox_stylesheet(t)

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
    {button_qss}
    {selection_qss}
""")
```

Implementation note: remove the inline `QSlider::groove:horizontal`, `QSlider::handle:horizontal`, and `QSlider::sub-page:horizontal` rules entirely. The slider showcase must no longer depend on QSS geometry.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_demo_gallery_architecture.py tests/test_ui_exports.py tests/test_phase4_ui.py -v`

Expected: PASS

- [ ] **Step 5: Local checkpoint**

Run: `python -m compileall demo_style_gallery.py tests/test_demo_gallery_architecture.py tests/test_ui_exports.py tests/test_phase4_ui.py`

Expected: all files compile without syntax errors.

### Task 5: Run the focused regressions and manual UI verification

**Files:**
- No new code files; verify the full self-drawn selection-controls slice

- [ ] **Step 1: Run the focused regression suite**

Run: `pytest tests/test_selection_control_metrics.py tests/test_themed_radio_button.py tests/test_themed_slider.py tests/test_input_guard.py tests/test_demo_gallery_architecture.py tests/test_ui_exports.py tests/test_phase4_ui.py -v`

Expected: PASS

- [ ] **Step 2: Run the full automated test suite**

Run: `pytest tests -q`

Expected: PASS with no regressions from the new Radio / Slider control stack.

- [ ] **Step 3: Launch the gallery for manual verification**

Run: `python demo_style_gallery.py`

Expected:
- the Radio showcase now uses the self-drawn `ThemedRadioButton`
- the Slider showcase now uses the self-drawn `ThemedSlider`
- no `QSlider::handle`-driven ellipse / capsule distortion remains
- hover, focus, checked, pressed, and disabled states look consistent with the existing theme language

- [ ] **Step 4: Manual acceptance checklist**

Confirm all of the following before marking the phase complete:
- `ThemedRadioButton` and `ThemedSlider` are both exported from `src/shared/ui`
- the gallery no longer relies on `QRadioButton::indicator` or `QSlider::handle:horizontal` for round geometry
- wheel guarding still blocks accidental slider wheel changes through `GlobalInputGuard`
- Radio and Slider geometry remains square/circular at 100% and 125% DPI smoke checks
- Checkbox shared QSS support remains intact and isolated from the new self-drawn Radio / Slider path

---

## Self-review

- **Spec coverage:** This plan covers the 2026-03-28 spec’s required route change: geometry-first tokens, shared metrics/painter helpers, `ThemedRadioButton`, `ThemedSlider`, gallery migration, input-guard compatibility, and geometry/render-focused tests.
- **Placeholder scan:** No `TODO`, `TBD`, or “similar to above” shortcuts remain in task steps.
- **Type consistency:** The plan keeps `QCheckBox` on the existing QSS path, adds `ThemedRadioButton` / `ThemedSlider` as new shared controls, and consistently routes slider guarding through `QAbstractSlider`.

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-03-28-self-drawn-selection-controls-phase1.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, and keep the Radio / Slider rollout isolated
2. **Inline Execution** - Execute tasks in this session using the plan as the checkpoint list
