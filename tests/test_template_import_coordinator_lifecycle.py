from __future__ import annotations

from types import SimpleNamespace
import threading
import time

from src.config.template_authoring_workspace import TemplateImportBatch
from src.qt_api import QWidget
from src.shared.engine.document_word_preview import (
    DocumentWordPreviewRequest,
    DocumentWordPreviewResult,
)
from src.ui.main_window import MainWindow
from src.ui.panel_registry import PANEL_SPECS
from src.ui.panels.document_word_preview_controller import (
    DocumentWordPreviewController,
)
from src.ui.template_import_coordinator import (
    CoordinatorPhase,
    TemplateImportCoordinator,
)


def _bridge_context(window: MainWindow) -> tuple[object, ...]:
    bridge = window.bridge
    return (
        bridge.current_work_mode_id(),
        bridge.current_scene_id(),
        bridge.current_scene(),
        bridge.current_template_id(),
        bridge.current_template(),
        bridge.current_scene_path(),
        bridge.current_template_path(),
        bridge.is_scene_dirty(),
        bridge.is_template_dirty(),
    )


def _wait_until(qapp, predicate, *, timeout_seconds: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("timed out waiting for coordinator")


def test_import_work_runs_off_application_thread(qapp, monkeypatch, tmp_path) -> None:
    import src.ui.template_import_coordinator as coordinator_module
    from src.config import library

    config_root = tmp_path / "config_library"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", config_root / "templates")
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", config_root / "plans")

    worker_threads: list[int] = []

    def fake_process(_mode_id: str) -> TemplateImportBatch:
        worker_threads.append(threading.get_ident())
        return TemplateImportBatch()

    monkeypatch.setattr(
        coordinator_module,
        "process_template_import_inbox",
        fake_process,
    )
    coordinator = TemplateImportCoordinator()
    try:
        coordinator.start("thesis")
        _wait_until(qapp, lambda: coordinator.is_idle)
        assert coordinator.phase == CoordinatorPhase.WATCHING
        assert coordinator.queue_mode("thesis")
        assert coordinator.phase == CoordinatorPhase.IMPORTING
        _wait_until(qapp, lambda: bool(worker_threads) and coordinator.is_idle)

        assert worker_threads[0] != threading.get_ident()
        assert coordinator.thread() is qapp.thread()
        assert coordinator.phase == CoordinatorPhase.WATCHING
    finally:
        coordinator.stop()
    assert coordinator.phase == CoordinatorPhase.STOPPED


def test_foreign_import_batch_does_not_mutate_active_window_context(qapp) -> None:
    window = MainWindow(enable_background_services=False)
    broadcasts: list[tuple[str, object]] = []
    window.bridge.template_library_events.import_completed.connect(
        lambda mode_id, batch: broadcasts.append((mode_id, batch))
    )
    before = _bridge_context(window)
    batch = TemplateImportBatch(
        successes=(SimpleNamespace(entry=SimpleNamespace(name="论文版后台导入模板")),),
    )
    try:
        window._on_template_import_batch_processed("thesis", batch)
        qapp.processEvents()

        assert broadcasts == [("thesis", batch)]
        assert _bridge_context(window) == before
    finally:
        window.close()
        qapp.processEvents()


def test_close_before_startup_callback_cannot_restart_background_service(
    qapp,
    monkeypatch,
) -> None:
    window = MainWindow(enable_background_services=True)
    start_calls: list[bool] = []
    monkeypatch.setattr(
        window._template_import_coordinator,
        "start",
        lambda _mode_id=None: start_calls.append(True),
    )

    assert window._startup_ready_emitted is False
    assert window.close() is True
    qapp.processEvents()

    assert start_calls == []


def test_close_veto_keeps_coordinator_alive_until_close_is_accepted(
    qapp,
    monkeypatch,
) -> None:
    window = MainWindow(enable_background_services=False)
    lifecycle: list[str] = []

    class _VetoPanel(QWidget):
        allow_close = False

        def shutdown_active_execution(self, timeout_ms=None) -> bool:
            lifecycle.append(f"panel:{timeout_ms}")
            return self.allow_close

    panel = _VetoPanel()
    window.register_panel(0, panel)
    monkeypatch.setattr(
        window._template_import_coordinator,
        "stop",
        lambda: lifecycle.append("coordinator:stop"),
    )

    try:
        window.show()
        qapp.processEvents()
        assert window.close() is False
        assert lifecycle == ["panel:1000"]

        lifecycle.clear()
        panel.allow_close = True
        assert window.close() is True
        assert lifecycle == ["panel:1000", "coordinator:stop"]
    finally:
        panel.allow_close = True
        window.close()
        qapp.processEvents()


def test_coordinator_stop_is_bounded_and_daemon_worker_is_reapable(
    qapp,
    monkeypatch,
) -> None:
    import src.ui.template_import_coordinator as coordinator_module

    started = threading.Event()
    release = threading.Event()

    def blocked_prepare(_mode_id: str):
        started.set()
        release.wait()
        return object()

    monkeypatch.setattr(
        coordinator_module,
        "ensure_template_authoring_workspace",
        blocked_prepare,
    )
    coordinator = TemplateImportCoordinator()
    try:
        coordinator.start("thesis")
        assert started.wait(1.0)
        worker = coordinator.worker_thread
        assert worker is not None
        assert worker.daemon is True

        before = time.monotonic()
        stopped = coordinator.stop(timeout_ms=25)
        elapsed = time.monotonic() - before

        assert stopped is False
        assert elapsed < 0.25
        assert coordinator.phase == CoordinatorPhase.STOPPED
        assert coordinator.is_running is False
        assert coordinator.has_live_worker is True
    finally:
        release.set()
        assert coordinator.wait_for_stopped(timeout_ms=1000)
        coordinator.deleteLater()
        qapp.processEvents()

    assert not any(
        thread.name == "template-import" and thread.is_alive()
        for thread in threading.enumerate()
    )


def test_preview_shutdown_signals_cancellation_and_joins_worker(qapp) -> None:
    started = threading.Event()
    cancelled = threading.Event()
    delivered: list[DocumentWordPreviewResult] = []

    def cooperative_renderer(
        request: DocumentWordPreviewRequest,
        *,
        force: bool,
        cancel_event: threading.Event,
    ) -> DocumentWordPreviewResult:
        assert force is True
        started.set()
        assert cancel_event.wait(1.0)
        cancelled.set()
        return DocumentWordPreviewResult(
            status="cancelled",
            provider_id=request.provider_id,
            variant_id=request.variant_id,
        )

    controller = DocumentWordPreviewController(
        renderer=cooperative_renderer,
        debounce_ms=0,
    )
    controller.result_ready.connect(delivered.append)
    request = DocumentWordPreviewRequest(
        provider_id="official_plan",
        variant_id="plan-a",
        cache_payload={},
        build_document=lambda _output_dir: None,  # renderer owns this test path
    )
    controller.request_preview(request, force=True)
    controller.refresh_now()
    assert started.wait(1.0)
    worker = controller.worker_thread
    assert worker is not None and worker.daemon

    assert controller.shutdown(timeout_ms=500) is True
    assert cancelled.is_set()
    assert controller.has_live_worker is False
    qapp.processEvents()
    assert delivered == []
    assert not any(
        thread.name == "document-word-preview" and thread.is_alive()
        for thread in threading.enumerate()
    )


def test_preview_shutdown_is_bounded_for_uncooperative_renderer(qapp) -> None:
    started = threading.Event()
    release = threading.Event()

    def blocked_renderer(
        request: DocumentWordPreviewRequest,
        *,
        force: bool,
    ) -> DocumentWordPreviewResult:
        del force
        started.set()
        release.wait()
        return DocumentWordPreviewResult(
            status="cancelled",
            provider_id=request.provider_id,
            variant_id=request.variant_id,
        )

    controller = DocumentWordPreviewController(
        renderer=blocked_renderer,
        debounce_ms=0,
    )
    request = DocumentWordPreviewRequest(
        provider_id="official_plan",
        variant_id="plan-b",
        cache_payload={},
        build_document=lambda _output_dir: None,
    )
    try:
        controller.request_preview(request)
        controller.refresh_now()
        assert started.wait(1.0)

        before = time.monotonic()
        assert controller.shutdown(timeout_ms=20) is False
        assert time.monotonic() - before < 0.25
        worker = controller.worker_thread
        assert worker is not None and worker.daemon
    finally:
        release.set()
        assert controller.wait_for_stopped(timeout_ms=1000)
        controller.deleteLater()
        qapp.processEvents()

    assert not any(
        thread.name == "document-word-preview" and thread.is_alive()
        for thread in threading.enumerate()
    )


def test_scene_close_finalization_shuts_document_preview_controller() -> None:
    from src.ui.panels.scene_panel import ScenePanel

    lifecycle: list[str] = []

    class _ExamDetail:
        def _shutdown_document_word_preview(self, timeout_ms: int) -> bool:
            lifecycle.append(f"preview:{timeout_ms}")
            return True

    panel = SimpleNamespace(
        _exam_paper=_ExamDetail(),
        finalize_prepared_scene_changes=lambda: lifecycle.append("scene:finalize"),
    )
    panel._shutdown_loaded_document_previews = (  # type: ignore[attr-defined]
        lambda: ScenePanel._shutdown_loaded_document_previews(panel)
    )

    ScenePanel.finalize_close_pending_changes(panel)

    assert lifecycle == ["scene:finalize", "preview:250"]


def test_accepted_close_cancels_delayed_panel_creation(qapp, monkeypatch) -> None:
    import src.ui.main_window as main_window_module

    window = MainWindow(
        enable_background_services=False,
    )
    created_panel_ids: list[str] = []

    def record_create(panel_id: str, _bridge):
        created_panel_ids.append(panel_id)
        return QWidget()

    monkeypatch.setattr(main_window_module, "create_panel", record_create)
    assets_index = next(
        index
        for index, spec in enumerate(window._panel_specs)
        if spec.id == "assets"
    )
    window._show_panel(assets_index)
    panel_timer = window._panel_load_timers[assets_index]
    startup_timeouts: list[bool] = []
    panel_timeouts: list[bool] = []
    window._startup_ready_timer.timeout.connect(lambda: startup_timeouts.append(True))
    panel_timer.timeout.connect(lambda: panel_timeouts.append(True))
    loaded_before_close = set(window._loaded_panel_indexes)

    assert panel_timer.isActive()
    assert window.close() is True
    assert not panel_timer.isActive()
    assert window._panel_load_timers == {}
    assert window._panel_loads_in_progress == set()

    deadline = time.monotonic() + 0.15
    while time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)

    # Even an escaped/stale callback is lifecycle-gated after close acceptance.
    window._finish_panel_load(assets_index)
    assert window._show_panel(assets_index) is None
    assert startup_timeouts == []
    assert panel_timeouts == []
    assert created_panel_ids == []
    assert window._loaded_panel_indexes == loaded_before_close
