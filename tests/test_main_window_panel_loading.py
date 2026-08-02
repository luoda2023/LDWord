from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from src.qt_api import QApplication, QWidget
from src.ui import main_window as main_window_module
from src.ui.main_window import MainWindow, _PlaceholderPanel
from src.ui.panel_loading import PanelLoadState


def _app():
    return QApplication.instance() or QApplication([])


def _panel_index(window: MainWindow, panel_id: str) -> int:
    return next(
        index
        for index, spec in enumerate(window._panel_specs)
        if spec.id == panel_id
    )


class _IntentPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.intents: list[object] = []

    def handle_navigation_intent(self, intent) -> None:
        self.intents.append(intent)


def test_startup_does_not_construct_hidden_top_level_panels():
    _app()
    window = MainWindow()
    try:
        _app().processEvents()

        assert window._loaded_panel_indexes == {0}
        assert not hasattr(window, "_preload_queue")
        assert not hasattr(window, "_idle_preload_timer")
        for index in range(1, window.panel_stack.count()):
            assert isinstance(window.panel_stack.widget(index), _PlaceholderPanel)
            assert window._panel_load_states[index] is PanelLoadState.UNLOADED
    finally:
        window.close()


def test_navigation_intent_is_replayed_after_shared_panel_loader(monkeypatch):
    _app()
    window = MainWindow()
    created: list[_IntentPanel] = []

    def create_panel(panel_id, bridge, **_kwargs):
        del bridge
        assert panel_id == "scene"
        panel = _IntentPanel()
        created.append(panel)
        return panel

    monkeypatch.setattr(main_window_module, "create_panel", create_panel)
    try:
        scene_index = _panel_index(window, "scene")
        intent = {"panel_id": "scene", "card_id": "rules"}

        window._navigate_intent(intent)

        assert window.panel_stack.currentIndex() == scene_index
        assert window.panel_load_state("scene") is PanelLoadState.SCHEDULED
        assert scene_index not in window._loaded_panel_indexes

        window._finish_panel_load(scene_index)

        assert window.panel_load_state("scene") is PanelLoadState.READY
        assert created[0].intents == [intent]
    finally:
        window.close()


def test_leaving_a_scheduled_destination_cancels_unstarted_load(monkeypatch):
    _app()
    window = MainWindow()
    created: list[str] = []

    def create_panel(panel_id, _bridge, **_kwargs):
        created.append(panel_id)
        return _IntentPanel()

    monkeypatch.setattr(main_window_module, "create_panel", create_panel)
    try:
        scene_index = _panel_index(window, "scene")
        template_index = _panel_index(window, "template")

        window._show_panel(scene_index)
        assert window.panel_load_state("scene") is PanelLoadState.SCHEDULED

        window._show_panel(template_index)

        assert window.panel_load_state("scene") is PanelLoadState.UNLOADED
        assert scene_index not in window._panel_load_timers
        assert window.panel_load_state("template") is PanelLoadState.SCHEDULED

        window._finish_panel_load(scene_index)

        assert created == []
        assert window.panel_load_state("scene") is PanelLoadState.UNLOADED
    finally:
        window.close()


def test_rejected_leave_does_not_move_sidebar_or_queue_deep_link(monkeypatch):
    _app()
    window = MainWindow()
    try:
        workbench = window.panel_stack.widget(0)
        monkeypatch.setattr(
            workbench,
            "request_leave_pending_changes",
            lambda _reason: False,
            raising=False,
        )
        scene_index = _panel_index(window, "scene")

        window._navigate_intent({"panel_id": "scene", "card_id": "rules"})

        assert window.panel_stack.currentIndex() == 0
        assert window.sidebar._active_index == 0
        assert window.panel_load_state("scene") is PanelLoadState.UNLOADED
        assert scene_index not in window._pending_panel_intents
    finally:
        window.close()


def test_failed_panel_load_stays_in_place_and_can_retry(monkeypatch):
    _app()
    window = MainWindow()
    attempts = 0
    intent = {"panel_id": "scene", "card_id": "rules"}

    def create_panel(panel_id, bridge, **_kwargs):
        nonlocal attempts
        del bridge
        assert panel_id == "scene"
        attempts += 1
        if attempts == 1:
            raise RuntimeError("expected panel failure")
        return _IntentPanel()

    monkeypatch.setattr(main_window_module, "create_panel", create_panel)
    try:
        scene_index = _panel_index(window, "scene")
        window._navigate_intent(intent)
        window._finish_panel_load(scene_index)

        placeholder = window.panel_stack.widget(scene_index)
        assert window.panel_load_state("scene") is PanelLoadState.FAILED
        assert isinstance(placeholder, _PlaceholderPanel)
        assert not placeholder._retry_button.isHidden()
        assert placeholder.toolTip() == "expected panel failure"
        assert window._panel_load_errors[scene_index] == "expected panel failure"
        assert window._pending_panel_intents[scene_index] == intent

        placeholder.retry_requested.emit()
        window._finish_panel_load(scene_index)

        assert attempts == 2
        assert window.panel_load_state("scene") is PanelLoadState.READY
        assert scene_index in window._loaded_panel_indexes
        assert window.panel_stack.widget(scene_index).intents == [intent]
    finally:
        window.close()


def test_register_panel_completes_scheduled_lifecycle_and_replays_intent():
    _app()
    window = MainWindow()
    try:
        scene_index = _panel_index(window, "scene")
        intent = {"panel_id": "scene", "card_id": "rules"}
        window._navigate_intent(intent)
        assert window.panel_load_state("scene") is PanelLoadState.SCHEDULED

        panel = _IntentPanel()
        window.register_panel(scene_index, panel)

        assert window.panel_load_state("scene") is PanelLoadState.READY
        assert scene_index in window._loaded_panel_indexes
        assert scene_index not in window._panel_load_timers
        assert scene_index not in window._pending_panel_intents
        assert panel.intents == [intent]
    finally:
        window.close()


def test_cold_workbench_does_not_import_deferred_execution_domains():
    root = Path(__file__).resolve().parent.parent
    script = """
import sys
from src.qt_api import QApplication
app = QApplication.instance() or QApplication([])
from src.ui.main_window import MainWindow
window = MainWindow()
deferred = (
    "openpyxl",
    "src.services.production_runtime.material_preflight",
    "src.ui.panels.workbench.document_scope_controller",
    "src.ui.panels.workbench.execution_session_controller",
    "src.ui.panels.workbench.material_suite_generation_detail",
)
unexpected = [name for name in deferred if name in sys.modules]
window.close()
if unexpected:
    raise SystemExit("unexpected startup imports: " + ", ".join(unexpected))
print("OK")
"""
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "offscreen"

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "OK"
