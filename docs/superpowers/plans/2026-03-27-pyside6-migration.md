# PySide6 Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace PyQt5 with PySide6 across the 1.0 codebase, add MIT-source-release notice files, and align the repository’s release posture with 0.2 LTS.

**Architecture:** Add a single Qt compatibility module at `src/qt_api.py`, migrate code in verified batches, and enforce the migration with source-scanning tests. Keep behavior stable by treating this as a binding swap plus release-compliance cleanup, not a UI redesign.

**Tech Stack:** Python, PySide6, pytest, shared UI theme/QSS helpers

---

## File map

- Create: `src/qt_api.py` — single import surface for QtCore / QtGui / QtWidgets / QtSvg
- Create: `requirements.txt` — explicit runtime/test dependency manifest using `PySide6`
- Create: `LICENSE` — MIT project license
- Create: `THIRD_PARTY_NOTICES.md` — third-party license disclosure aligned with 0.2 LTS wording
- Create: `tests/test_qt_api_migration.py` — migration guard + compatibility tests
- Modify: `main.py` — entrypoint migration from PyQt5 to `src.qt_api`
- Modify: `src/shared/ui/*.py` — shared widget layer migration
- Modify: `src/ui/*.py` — main window, panels, adapters, icon catalog migration
- Modify: `demo_*.py` — demo scripts migration
- Modify: `test_*.py` and `tests/test_phase4_ui.py` — local helper/test imports migration

> Note: this workspace is **not** a git repository, so normal “commit after each task” steps cannot be executed here. Keep each task isolated in the diff and verify before moving on.

### Task 1: Add release-compliance files and the Qt compatibility layer

**Files:**
- Create: `LICENSE`
- Create: `THIRD_PARTY_NOTICES.md`
- Create: `requirements.txt`
- Create: `src/qt_api.py`
- Test: `tests/test_qt_api_migration.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from src import qt_api


def test_qt_api_uses_pyside6_symbols():
    assert "PySide6" in qt_api.__file__ or hasattr(qt_api, "Signal")
    assert qt_api.Signal.__name__ == "Signal"
    assert qt_api.Property.__name__ == "Property"


def test_runtime_source_tree_no_longer_references_pyqt5():
    runtime_targets = [
        Path("main.py"),
        Path("src"),
    ]
    for target in runtime_targets:
        files = [target] if target.is_file() else list(target.rglob("*.py"))
        for path in files:
            text = path.read_text(encoding="utf-8")
            assert "PyQt5" not in text, f"{path} still references PyQt5"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_qt_api_migration.py -v`
Expected: FAIL because `src/qt_api.py` does not exist and the runtime tree still contains `PyQt5`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/qt_api.py
from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QRectF,
    QSize,
    Qt,
    QPropertyAnimation,
    QTimer,
    Signal,
    Property,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QIcon,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import *
```

```text
# LICENSE
MIT License
...
```

```text
# THIRD_PARTY_NOTICES.md
Project source code is MIT.
Third-party dependencies keep their own licenses.
PySide6 / Qt are not MIT and packaged desktop distributions must satisfy their license obligations.
```

```text
# requirements.txt
python-docx>=1.1.0
PySide6>=6.6.0
lxml>=5.0.0
PyYAML>=6.0
pywin32>=306; platform_system == "Windows"
pytest>=8.0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_qt_api_migration.py::test_qt_api_uses_pyside6_symbols -v`
Expected: PASS

- [ ] **Step 5: Local checkpoint**

Run: `python -m compileall src/qt_api.py tests/test_qt_api_migration.py`
Expected: compile succeeds

### Task 2: Migrate the runtime entrypoint and shared UI layer

**Files:**
- Modify: `main.py`
- Modify: `src/shared/ui/base_dialog.py`
- Modify: `src/shared/ui/button_style.py`
- Modify: `src/shared/ui/card.py`
- Modify: `src/shared/ui/collapsible_section.py`
- Modify: `src/shared/ui/color_picker.py`
- Modify: `src/shared/ui/dialogs.py`
- Modify: `src/shared/ui/error_dialog.py`
- Modify: `src/shared/ui/folder_picker.py`
- Modify: `src/shared/ui/font_combo.py`
- Modify: `src/shared/ui/form_row.py`
- Modify: `src/shared/ui/icon_button.py`
- Modify: `src/shared/ui/input_guard.py`
- Modify: `src/shared/ui/module_step_list.py`
- Modify: `src/shared/ui/numbering_preset.py`
- Modify: `src/shared/ui/override_badge.py`
- Modify: `src/shared/ui/placeholder_edit.py`
- Modify: `src/shared/ui/progress_indicator.py`
- Modify: `src/shared/ui/search_input.py`
- Modify: `src/shared/ui/size_combo.py`
- Modify: `src/shared/ui/spacing_input.py`
- Modify: `src/shared/ui/status_indicator.py`
- Modify: `src/shared/ui/style_preview.py`
- Modify: `src/shared/ui/styled_combo_box.py`
- Modify: `src/shared/ui/theme.py`
- Modify: `src/shared/ui/toggle_switch.py`
- Test: `tests/test_qt_api_migration.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_shared_ui_tree_uses_qt_api_or_pyside6_but_not_pyqt5():
    for path in Path("src/shared/ui").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "PyQt5" not in text, f"{path} still references PyQt5"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_qt_api_migration.py::test_shared_ui_tree_uses_qt_api_or_pyside6_but_not_pyqt5 -v`
Expected: FAIL because `src/shared/ui` still imports `PyQt5`.

- [ ] **Step 3: Write minimal implementation**

```python
# Example import rewrite
from src.qt_api import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QObject,
    QPoint,
    QPropertyAnimation,
    QPushButton,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QWidget,
    QColor,
    QPainter,
    QPen,
    Signal,
    Property,
)
```

```python
# Example API rewrite
search_changed = Signal(str)
search_submitted = Signal(str)
result = dialog.exec()
return app.exec()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_qt_api_migration.py::test_shared_ui_tree_uses_qt_api_or_pyside6_but_not_pyqt5 -v`
Expected: PASS

- [ ] **Step 5: Local checkpoint**

Run: `pytest tests/test_button_style.py tests/test_search_input_styles.py tests/test_combo_architecture.py tests/test_dialog_architecture.py tests/test_small_widget_architecture.py tests/test_widget_architecture.py tests/test_theme_binding_architecture.py tests/test_tail_architecture.py tests/test_ui_exports.py -v`
Expected: shared UI related tests pass

### Task 3: Migrate main UI modules and icon rendering

**Files:**
- Modify: `src/ui/base_panel.py`
- Modify: `src/ui/bridge.py`
- Modify: `src/ui/icons/catalog.py`
- Modify: `src/ui/main_window.py`
- Modify: `src/ui/panels/heading_numbering_panel.py`
- Modify: `src/ui/adapters/heading_numbering_adapter.py`
- Modify: `src/ui/sidebar.py`
- Modify: `src/ui/title_bar.py`
- Modify: `main.py`
- Test: `tests/test_qt_api_migration.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_main_ui_tree_no_longer_references_pyqt5():
    targets = [
        Path("main.py"),
        Path("src/ui"),
    ]
    for target in targets:
        files = [target] if target.is_file() else list(target.rglob("*.py"))
        for path in files:
            text = path.read_text(encoding="utf-8")
            assert "PyQt5" not in text, f"{path} still references PyQt5"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_qt_api_migration.py::test_main_ui_tree_no_longer_references_pyqt5 -v`
Expected: FAIL because `main.py` and `src/ui/*` still reference `PyQt5`.

- [ ] **Step 3: Write minimal implementation**

```python
from src.qt_api import QApplication, QBrush, QColor, QCursor, QFont, QIcon, QPainter, QPixmap, QSvgRenderer, Qt, Signal
```

```python
# Signal rewrite examples
scene_changed = Signal(object)
numbering_changed = Signal()
panel_selected = Signal(int)
```

```python
# main.py
return app.exec()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_qt_api_migration.py::test_main_ui_tree_no_longer_references_pyqt5 -v`
Expected: PASS

- [ ] **Step 5: Local checkpoint**

Run: `pytest tests/test_phase4_ui.py tests/test_demo_gallery_architecture.py tests/test_input_architecture.py tests/test_combo_architecture.py -v`
Expected: main UI related tests pass

### Task 4: Migrate demos and helper scripts, then enforce repo-wide guard

**Files:**
- Modify: `demo_dialogs.py`
- Modify: `demo_heading_panel.py`
- Modify: `demo_style_gallery.py`
- Modify: `test_audit_fix.py`
- Modify: `test_combo.py`
- Modify: `test_crash.py`
- Modify: `test_crash_trace.py`
- Modify: `tests/test_phase4_ui.py`
- Modify: `tests/test_qt_api_migration.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_repository_python_files_no_longer_reference_pyqt5_outside_vendor_dirs():
    skip_parts = {".venv", "__pycache__", ".agents"}
    for path in Path(".").rglob("*.py"):
        if any(part in skip_parts for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "PyQt5" not in text, f"{path} still references PyQt5"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_qt_api_migration.py::test_repository_python_files_no_longer_reference_pyqt5_outside_vendor_dirs -v`
Expected: FAIL because demos and helper scripts still reference `PyQt5`.

- [ ] **Step 3: Write minimal implementation**

```python
# Rewrite remaining demo/helper imports to src.qt_api or direct PySide6
from src.qt_api import QApplication, QBrush, QComboBox, QEvent, QFont, QImage, QListView, QObject, QPoint, QPropertyAnimation, QSize, Qt, QTimer, QWidget
```

```python
# Replace final exec_() calls
sys.exit(app.exec())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_qt_api_migration.py::test_repository_python_files_no_longer_reference_pyqt5_outside_vendor_dirs -v`
Expected: PASS

- [ ] **Step 5: Local checkpoint**

Run: `pytest tests -v`
Expected: all repository tests pass

### Task 5: Final verification for MIT-source-release posture

**Files:**
- Verify: `LICENSE`
- Verify: `THIRD_PARTY_NOTICES.md`
- Verify: `requirements.txt`
- Verify: `src/qt_api.py`
- Verify: migrated runtime/demo files

- [ ] **Step 1: Run focused migration verification**

Run: `pytest tests/test_qt_api_migration.py -v`
Expected: all migration guard tests pass

- [ ] **Step 2: Run compile verification**

Run: `python -m compileall main.py src demo_dialogs.py demo_heading_panel.py demo_style_gallery.py tests`
Expected: compile succeeds without syntax errors

- [ ] **Step 3: Run full test suite**

Run: `pytest tests -v`
Expected: full suite passes

- [ ] **Step 4: Perform manual launch smoke test**

Run: `python main.py --gui`
Expected: main window opens successfully under `PySide6`

- [ ] **Step 5: Record delivery note**

Document in the final handoff that:

```text
Project source license: MIT
Third-party dependencies: their own licenses
Desktop binary distributions must still satisfy Qt / PySide6 license obligations
```
