from __future__ import annotations

import os
import sys
from pathlib import Path
from shutil import copytree

import pytest
from PySide6.QtCore import QCoreApplication
from shiboken6 import isValid

# Most widget tests only need deterministic layout/rendering, not a native
# Windows top-level surface. Forcing offscreen avoids Windows COM tail noise
# during pytest shutdown while preserving grab()/render()-based assertions.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QEvent
from src.shared.ui.typography_policy import (
    apply_application_typography,
    register_windows_ui_fonts_for_freetype,
)


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    qpa_platform = os.environ.get("QT_QPA_PLATFORM", "")
    font_engine = "freetype" if "fontengine=freetype" in qpa_platform else None
    register_windows_ui_fonts_for_freetype(font_engine)
    apply_application_typography(app)
    yield app


@pytest.fixture(autouse=True)
def isolate_user_material_package_libraries(tmp_path_factory, monkeypatch):
    """Isolate the canonical library while retaining read-only built-in samples."""
    from src.config import material_package_library

    builtin_sources = tuple(
        path
        for path in material_package_library.CANONICAL_MATERIAL_PACKAGE_LIBRARY_DIR.glob(
            "*/builtin"
        )
        if path.is_dir()
    )
    material_root = (
        tmp_path_factory.mktemp("isolated_config_library") / "material_packages"
    )
    for builtin_source in builtin_sources:
        mode_id = builtin_source.parent.name
        copytree(
            builtin_source,
            material_root / mode_id / "builtin",
        )
    monkeypatch.setattr(
        material_package_library,
        "MATERIAL_PACKAGE_LIBRARY_DIR",
        material_root,
    )


@pytest.fixture(autouse=True)
def isolate_workspace_preferences(tmp_path, monkeypatch):
    """Keep restart-preference tests away from the developer's real profile."""

    from src.ui import workspace_preferences

    monkeypatch.setattr(
        workspace_preferences,
        "workspace_preferences_path",
        lambda: tmp_path / "workspace-preferences.json",
    )


def _new_valid_top_level_widgets(protected: tuple[object, ...]) -> list[object]:
    return [
        widget
        for widget in QApplication.topLevelWidgets()
        if isValid(widget)
        and not any(widget is protected_widget for protected_widget in protected)
    ]


def _dispose_test_top_level_widgets(
    app: QApplication,
    protected: tuple[object, ...],
) -> None:
    """Destroy widgets created by one test and drain their deferred callbacks."""

    tooltip_controller = getattr(app, "_alavette_global_tooltip_controller", None)
    if tooltip_controller is not None:
        tooltip_controller.hide_tooltip()
        popup = getattr(tooltip_controller, "popup", None)
        if popup is not None and isValid(popup):
            protected = (*protected, popup)

    # First let zero-delay layout/visibility work settle while every receiver
    # is still alive. Closing a popup can enqueue one more dismissal callback,
    # so settle again before scheduling object destruction.
    app.processEvents()
    app.processEvents()

    for _attempt in range(4):
        widgets = _new_valid_top_level_widgets(protected)
        if not widgets:
            break
        for widget in widgets:
            if not isValid(widget):
                continue
            widget.close()
        app.processEvents()
        app.processEvents()
        widgets = _new_valid_top_level_widgets(protected)
        for widget in widgets:
            if isValid(widget):
                widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    # A test can schedule deleteLater() itself without leaving a top-level
    # widget in the list above. Flush that queue before the next test too.
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    residual = _new_valid_top_level_widgets(protected)
    assert not residual, (
        "Qt widgets survived per-test teardown: "
        + ", ".join(
            f"{type(widget).__name__}({widget.objectName()!r})"
            for widget in residual
        )
    )


@pytest.fixture(autouse=True)
def dispose_test_qt_widgets(qapp, isolate_user_material_package_libraries):
    """Keep the session QApplication without retaining each test's widget tree."""

    protected = tuple(
        widget for widget in QApplication.topLevelWidgets() if isValid(widget)
    )
    yield
    _dispose_test_top_level_widgets(qapp, protected)
