import json
import logging
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.object_preflight_evidence import ObjectPreflightEvidence
from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.main_window import MainWindow
from src.ui.panel_loading import PanelLoadState
from src.ui.panel_registry import PANEL_SPECS, create_panel
from src.ui.panels.workbench import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


def _object_preflight_evidence(*, blocked: bool) -> ObjectPreflightEvidence:
    payload = {
        "findings_count": 1,
        "module_skips_count": 0,
        "blocking_findings_count": 1 if blocked else 0,
        "blocked": blocked,
        "findings": [
            {
                "kind": "embedded_object",
                "location": "word/document.xml",
                "message": "embedded object requires confirmation",
                "severity": "error" if blocked else "warning",
            }
        ],
        "module_skips": [],
    }
    return ObjectPreflightEvidence(
        applicable=True,
        scene_id="scene-test",
        source_path="C:/fixtures/object-preflight.docx",
        source_revision="revision-1",
        context_revision="context-1",
        evidence_digest=f"digest-{'blocked' if blocked else 'warning'}",
        canonical_key=f"key-{'blocked' if blocked else 'warning'}",
        payload_json=json.dumps(payload),
    )


def _prepare_object_preflight_start(panel, monkeypatch, *, evidence):
    build_calls = []
    start_calls = []
    monkeypatch.setattr(panel, "_current_work_mode_id", lambda: "standard")
    monkeypatch.setattr(
        panel._quick_execution_detail,
        "execution_scene",
        lambda scene: scene or panel._quick_execution_detail.current_scene(),
    )
    monkeypatch.setattr(
        panel._quick_execution_detail,
        "execution_template",
        lambda template: template,
    )
    monkeypatch.setattr(
        panel._quick_execution_detail,
        "execution_material_selection",
        lambda: None,
    )
    monkeypatch.setattr(
        panel._quick_execution_detail,
        "current_execution_gate_decision",
        lambda: SimpleNamespace(can_run=True),
    )
    monkeypatch.setattr(
        panel._quick_execution_detail,
        "runtime_template_overrides",
        dict,
    )
    monkeypatch.setattr(
        panel._quick_execution_detail,
        "set_object_preflight_confirmation",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        panel._document_execution_detail,
        "set_object_preflight_confirmation",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        panel,
        "_resolve_document_path_for_execution",
        lambda: Path("C:/fixtures/object-preflight.docx"),
    )
    monkeypatch.setattr(panel._document_scope, "ensure_confirmed", lambda: True)
    monkeypatch.setattr(
        panel._document_paths,
        "selected_existing_document",
        lambda: Path("C:/fixtures/object-preflight.docx"),
    )
    monkeypatch.setattr(
        panel,
        "_build_object_preflight_preview_evidence",
        lambda: evidence,
    )
    monkeypatch.setattr(panel, "_refresh_quick_execute_card", lambda: None)

    def _build_document_worker(**kwargs):
        build_calls.append(kwargs)
        return "worker-build"

    monkeypatch.setattr(
        panel._execution_session,
        "build_document_worker",
        _build_document_worker,
    )
    monkeypatch.setattr(panel, "_start_worker_from_build", start_calls.append)
    return build_calls, start_calls


def test_main_window_registers_real_workbench_panel():
    _app()
    window = MainWindow()
    try:
        expected_index = next(i for i, spec in enumerate(PANEL_SPECS) if spec.id == "workbench")
        workbench_panel = window.panel_stack.widget(expected_index)
        assert isinstance(workbench_panel, WorkbenchPanel)
        assert workbench_panel._batch_generation_detail is not None
        assert list(workbench_panel._navigation_cards) == ["quick_execute"]
        assert "material_suite_generate" not in workbench_panel._detail_map
        assert workbench_panel._suite_generation_detail is None
        assert "batch_generate" not in workbench_panel._navigation_cards
    finally:
        window.close()


def test_main_window_exposes_assets_as_lazy_core_navigation():
    _app()
    window = MainWindow()
    try:
        panel_ids = tuple(spec.id for spec in PANEL_SPECS)
        assert panel_ids[:5] == (
            "workbench",
            "scene",
            "template",
            "assets",
            "assistant",
        )
        assert panel_ids[-2:] == ("theme", "preferences")
        assert window.panel_stack.count() == len(PANEL_SPECS)

        assets_index = panel_ids.index("assets")
        assets_spec = PANEL_SPECS[assets_index]
        assert assets_spec.title == "资料包"
        assert assets_index not in window._loaded_panel_indexes
        assert window.panel_load_state("assets") is PanelLoadState.UNLOADED
        assert window.sidebar._buttons[assets_index].nav_id == "assets"

        theme_index = panel_ids.index("theme")
        theme_panel = window._show_panel(theme_index, allow_async=False)
        assert theme_panel.__class__.__name__ == "ThemePanel"
    finally:
        window.close()


def test_workbench_panel_exposes_navigation_components():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel._nav_rail.selected_card_id() == "quick_execute"
        assert panel._current_detail is panel._document_execution_detail
        assert "batch_generate" not in panel._navigation_cards
        assert (
            panel._batch_generation_detail
            in panel._document_execution_detail._details.values()
        )
    finally:
        panel.close()


def test_assets_sidebar_destination_loads_panel_on_demand():
    _app()
    window = MainWindow()
    try:
        _app().processEvents()
        assets_index = next(
            index
            for index, spec in enumerate(window._panel_specs)
            if spec.id == "assets"
        )
        assets_button = window.sidebar._buttons[assets_index]

        assets_button.click()

        assert window.panel_stack.currentIndex() == assets_index
        assert assets_index not in window._loaded_panel_indexes
        assert assets_index in window._panel_loads_in_progress

        window._finish_panel_load(assets_index)

        assert assets_index in window._loaded_panel_indexes
        assert window.panel_stack.widget(assets_index).__class__.__name__ == "AssetsPanel"
    finally:
        window.close()


def test_unreleased_material_suite_cannot_be_opened_by_navigation_intent():
    _app()
    window = MainWindow()
    try:
        _app().processEvents()
        workbench_panel = window.panel_stack.widget(0)
        assert isinstance(workbench_panel, WorkbenchPanel)
        workbench_panel.handle_navigation_intent(
            {"card_id": "material_suite_generate"}
        )
        _app().processEvents()

        assert workbench_panel._nav_rail.selected_card_id() == "quick_execute"
        assert (
            workbench_panel._current_detail
            is workbench_panel._document_execution_detail
        )
        assert "material_suite_generate" not in workbench_panel._navigation_cards
        assert "material_suite_generate" not in workbench_panel._detail_map
    finally:
        window.close()


def test_workbench_registry_keeps_record_execution_inside_document_execution():
    _app()
    panel = create_panel("workbench", PanelBridge())
    try:
        assert isinstance(panel, WorkbenchPanel)
        assert panel._batch_generation_detail is not None
        assert "batch_generate" not in panel._navigation_cards
        assert panel._batch_generation_detail is not None
    finally:
        panel.close()


def test_workbench_removes_ai_shortcut_from_quick_execution():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        ids = [spec.id for spec in PANEL_SPECS]
        assert "assistant" in ids
        assert "assistant_home" not in panel._detail_map
        assert not hasattr(panel, "_assistant_panel")
        assert not hasattr(panel._quick_execution_detail, "_assistant_btn")
        assert not hasattr(panel._quick_execution_detail, "assistant_requested")
    finally:
        panel.close()


def test_workbench_quick_execution_hides_advanced_scene_controls():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        detail = panel._quick_execution_detail

        assert not hasattr(detail, "_advanced_card")
        assert not hasattr(detail, "_zone_checks")
        assert not hasattr(detail, "_strategy_rebuild")
        assert not hasattr(detail.current_scene(), "format_scope")

        detail.set_feature_enabled("content_fill", True)

        assert detail.current_scene().is_module_enabled("entity_fill") is True
    finally:
        panel.close()


def test_workbench_panel_uses_bridge_reference_without_task_2_behavior():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        assert panel.bridge is bridge
        assert panel.objectName() == "WorkbenchPanel"
    finally:
        panel.close()


def test_start_execution_requires_object_preflight_confirmation_before_worker(
    monkeypatch,
):
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        build_calls, start_calls = _prepare_object_preflight_start(
            panel,
            monkeypatch,
            evidence=_object_preflight_evidence(blocked=False),
        )

        panel._start_execution()

        assert build_calls == []
        assert start_calls == []
        assert panel._pending_object_preflight_confirmation_key == "key-warning"

        panel._start_execution()

        assert len(build_calls) == 1
        assert start_calls == ["worker-build"]
        assert panel._pending_object_preflight_confirmation_key == ""
        assert panel._confirmed_object_preflight_digest == "digest-warning"
    finally:
        panel.close()


def test_start_execution_blocks_on_strict_object_preflight_findings(monkeypatch):
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        build_calls, start_calls = _prepare_object_preflight_start(
            panel,
            monkeypatch,
            evidence=_object_preflight_evidence(blocked=True),
        )

        panel._start_execution()
        panel._start_execution()

        assert build_calls == []
        assert start_calls == []
        assert panel._pending_object_preflight_confirmation_key == ""
        assert panel._confirmed_object_preflight_digest == ""
    finally:
        panel.close()


def test_workbench_execution_adapter_import_is_not_blocked_by_panels_package_reexports():
    script = (
        "import sys; "
        f"sys.path.insert(0, r'{ROOT}'); "
        "from src.ui.adapters.workbench_execution_adapter import WorkbenchExecutionAdapter; "
        "print(WorkbenchExecutionAdapter.__name__)"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "WorkbenchExecutionAdapter"


def test_main_window_close_ignored_when_panel_shutdown_fails():
    app = _app()
    window = MainWindow()
    failing_panel = None
    try:
        from src.qt_api import QWidget

        class _FailingPanel(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.calls = []

            def shutdown_active_execution(self, timeout_ms: int | None = None) -> bool:
                self.calls.append(timeout_ms)
                return False

        failing_panel = _FailingPanel()
        window.register_panel(0, failing_panel)

        window.show()
        app.processEvents()
        assert window.isVisible()

        assert window.close() is False
        app.processEvents()
        assert window.isVisible()
    finally:
        # Ensure the test can clean up the window even if the close was blocked.
        if failing_panel is not None:
            failing_panel.shutdown_active_execution = lambda timeout_ms=None: True
        window.close()


def test_main_window_close_requests_workbench_shutdown_before_closing():
    app = _app()
    window = MainWindow()
    workbench_panel = None
    try:
        expected_index = next(i for i, spec in enumerate(PANEL_SPECS) if spec.id == "workbench")
        workbench_panel = window.panel_stack.widget(expected_index)
        assert isinstance(workbench_panel, WorkbenchPanel)

        class _FakeThread:
            def isRunning(self) -> bool:
                return False

        class _FakeExecutionHandle:
            def __init__(self):
                self._thread = _FakeThread()
                self.cancel_requests = 0
                self.shutdown_calls = []

            def request_cancel(self) -> None:
                self.cancel_requests += 1

            def shutdown(self, timeout_ms: int | None = 1000) -> None:
                self.shutdown_calls.append(timeout_ms)

        handle = _FakeExecutionHandle()
        workbench_panel._execution_worker = handle

        window.show()
        app.processEvents()

        assert window.close() is True
        assert handle.cancel_requests == 1
        assert handle.shutdown_calls
    finally:
        if workbench_panel is not None:
            workbench_panel._execution_worker = None
        window.close()


def test_main_window_close_logs_shutdown_exception_before_blocking_close(caplog):
    app = _app()
    window = MainWindow()
    failing_panel = None
    try:
        from src.qt_api import QWidget

        class _ExplodingPanel(QWidget):
            def shutdown_active_execution(self, timeout_ms: int | None = None) -> bool:
                raise RuntimeError("shutdown boom")

        failing_panel = _ExplodingPanel()
        window.register_panel(0, failing_panel)

        window.show()
        app.processEvents()

        with caplog.at_level(logging.WARNING):
            assert window.close() is False
            app.processEvents()

        assert any("panel shutdown at index 0" in record.getMessage() for record in caplog.records)
    finally:
        if failing_panel is not None:
            failing_panel.shutdown_active_execution = lambda timeout_ms=None: True
        window.close()


def test_main_window_close_logs_panel_stack_count_failure_and_still_closes(caplog):
    app = _app()
    window = MainWindow()
    original_stack = window.panel_stack
    try:
        class _BrokenStack:
            def count(self):
                raise RuntimeError("count boom")

        window.panel_stack = _BrokenStack()
        window.show()
        app.processEvents()

        with caplog.at_level(logging.WARNING):
            assert window.close() is True
            app.processEvents()

        assert any("panel stack count" in record.getMessage() for record in caplog.records)
    finally:
        window.panel_stack = original_stack
        window.close()
