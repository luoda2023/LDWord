import inspect
import sys
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from docx import Document
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.config.asset_resolution import file_content_revision
from src.config.builtin_templates import create_builtin_template
from src.config.entity import EntityArchive, EntityProfile
from src.config.library import load_scene_from_library
from src.config.material_batch import MaterialBatchSelection
from src.config.material_context import MaterialExecutionContext
from src.config.object_preflight_evidence import build_object_preflight_evidence
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig
from src.ui.bridge import PanelBridge
from src.ui.panel_registry import PANEL_SPECS
from src.ui.panels.scene_panel import ScenePanel
from src.ui.panels.workbench import execution_session_controller as session_controller_module
from src.ui.panels.workbench.execution_session_controller import WorkbenchExecutionSessionController
from src.ui.panels.workbench.panel_v2 import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


def _object_preflight_evidence_stub(
    payload: dict[str, object],
    *,
    key: str = "test-object-preflight-evidence",
):
    return SimpleNamespace(
        source_revision=str(payload.get("source_revision") or ""),
        evidence_digest="sha256:" + "d" * 64,
        canonical_key=key,
        to_payload=lambda: dict(payload),
    )


def test_workbench_panel_uses_execution_session_controller_for_worker_lifecycle():
    panel_source = inspect.getsource(WorkbenchPanel)
    module_source = (ROOT / "src/ui/panels/workbench/panel_v2.py").read_text(encoding="utf-8")

    assert "from .execution_session_controller import WorkbenchExecutionSessionController" in module_source
    assert "self._execution_session = WorkbenchExecutionSessionController(" in panel_source
    assert "return self._execution_session.active_worker" in panel_source
    assert "self._execution_session.shutdown_active_execution(" in panel_source
    assert "build = self._execution_session.build_worker(" in panel_source
    assert "session_overrides=self._quick_execution_detail.runtime_template_overrides()," in panel_source
    assert "self._execution_session.start_worker(worker)" in panel_source


def test_execution_session_controller_owns_handle_build_start_and_shutdown_logic():
    module_source = (ROOT / "src/ui/panels/workbench/execution_session_controller.py").read_text(encoding="utf-8")
    controller_source = inspect.getsource(WorkbenchExecutionSessionController)

    assert "class ExecutionBuildResult" in module_source
    assert "def build_worker" in controller_source
    assert "def build_batch_worker" in controller_source
    assert "ThreadedExecutionHandle(" in module_source
    assert "session_overrides=session_overrides" in module_source
    assert "def start_worker" in controller_source
    assert "def shutdown_active_execution" in controller_source
    assert "def clear_active_worker" in controller_source


def test_execution_session_blocks_missing_material_before_resolving_source_document():
    resolve_calls = []
    controller = WorkbenchExecutionSessionController(
        resolve_document_path=lambda: resolve_calls.append(True) or "D:/source.docx",
    )
    scene = SceneWorkspace(scene_id="official", mode_id="official")
    scene.input_source_profile.failure_policy = "block"
    scene.input_source_profile.required_material_fields = ["title"]

    build = controller.build_worker(
        template=create_builtin_template("official_gbt"),
        scene=scene,
        material_context=MaterialExecutionContext(),
        mode_id="official",
    )

    assert build.worker is None
    assert build.cancelled is False
    assert build.error_text
    assert resolve_calls == []


def test_execution_session_batch_gate_checks_all_profiles_when_ids_are_implicit():
    resolve_calls = []
    controller = WorkbenchExecutionSessionController(
        resolve_document_path=lambda: resolve_calls.append(True) or "D:/source.docx",
    )
    scene = SceneWorkspace(scene_id="official", mode_id="official")
    scene.input_source_profile.failure_policy = "block"
    scene.input_source_profile.required_material_fields = ["title"]

    build = controller.build_batch_worker(
        template=create_builtin_template("official_gbt"),
        scene=scene,
        archive=EntityArchive(
            profiles=[
                EntityProfile(
                    profile_id="row_1",
                    profile_name="Missing title",
                )
            ]
        ),
        profile_ids=None,
        source_kind="official_document_table",
    )

    assert build.worker is None
    assert build.cancelled is False
    assert "Missing title" in build.error_text
    assert resolve_calls == []


def test_execution_session_rejects_non_table_official_batch_source():
    resolve_calls = []
    controller = WorkbenchExecutionSessionController(
        resolve_document_path=lambda: resolve_calls.append(True) or "D:/source.docx",
    )
    build = controller.build_batch_worker(
        template=create_builtin_template("official_gbt"),
        scene=SceneWorkspace(scene_id="official", mode_id="official"),
        archive=EntityArchive(
            profiles=[
                EntityProfile(
                    profile_id="row_1",
                    profile_name="Notice",
                    fields={"document_type": "notice"},
                )
            ]
        ),
        profile_ids=["row_1"],
        source_kind="legacy_generic_batch",
        mode_id="official",
    )

    assert build.worker is None
    assert build.error_text == (
        "official_batch_source_not_supported:official_document_table_required"
    )
    assert resolve_calls == []


def test_execution_session_rejects_non_table_batch_for_custom_official_mode_scene():
    resolve_calls = []
    controller = WorkbenchExecutionSessionController(
        resolve_document_path=lambda: resolve_calls.append(True) or "D:/source.docx",
    )

    build = controller.build_batch_worker(
        template=create_builtin_template("official_gbt"),
        scene=SceneWorkspace(scene_id="custom_official_plan", mode_id="official"),
        archive=EntityArchive(
            profiles=[
                EntityProfile(
                    profile_id="row_1",
                    profile_name="Notice",
                    fields={"document_type": "notice"},
                )
            ]
        ),
        profile_ids=["row_1"],
        source_kind="legacy_generic_batch",
        mode_id="official",
    )

    assert build.worker is None
    assert build.error_text == (
        "official_batch_source_not_supported:official_document_table_required"
    )
    assert resolve_calls == []


def test_controller_clears_stale_official_document_type_in_non_official_modes(
    monkeypatch,
):
    captured_requests = []
    not_ready = SimpleNamespace(ready=False, issues=("test_stop",))

    def capture_snapshot(**kwargs):
        captured_requests.append(dict(kwargs))
        return not_ready

    monkeypatch.setattr(
        session_controller_module,
        "build_execution_session_snapshot",
        capture_snapshot,
    )

    for mode_id in ("custom", "exam"):
        controller = WorkbenchExecutionSessionController(
            resolve_document_path=lambda: "D:/source.docx",
        )
        build = controller.build_worker(
            template=create_builtin_template("default"),
            scene=load_scene_from_library(mode_id, mode_id=mode_id),
            material_context=MaterialExecutionContext(mode_id=mode_id),
            document_type_id="notice",
            mode_id=mode_id,
            plan_id=mode_id,
            template_id="default",
        )

        assert build.worker is None
        assert build.session_snapshot is not_ready

    assert [
        request["document_type_id"] for request in captured_requests
    ] == ["", ""]


def test_execution_worker_alias_tracks_session_controller_state():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        handle = object()

        panel._execution_worker = handle

        assert panel._execution_worker is handle
        assert panel._execution_session.active_worker is handle

        panel._clear_execution_worker()

        assert panel._execution_worker is None
        assert panel._execution_session.active_worker is None
    finally:
        panel.close()


def test_worker_prepare_failure_discards_handle_and_clears_active_state(monkeypatch):
    _app()
    panel = WorkbenchPanel(PanelBridge())

    class _Worker:
        def __init__(self) -> None:
            self.shutdown_calls = 0

        def shutdown(self, timeout_ms=None) -> None:
            self.shutdown_calls += 1

    worker = _Worker()
    build = SimpleNamespace(
        worker=worker,
        cancelled=False,
        already_running=False,
        error_text="",
        session_snapshot=None,
    )
    results = []
    monkeypatch.setattr(
        panel._execution,
        "prepare_worker",
        lambda _worker: (_ for _ in ()).throw(RuntimeError("prepare boom")),
    )
    monkeypatch.setattr(panel, "apply_execution_result", results.append)
    try:
        panel._start_worker_from_build(build)

        assert panel._execution_session.active_worker is None
        assert worker.shutdown_calls == 1
        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert "execution_worker_start_failed:RuntimeError:prepare boom" in results[0][
            "error_text"
        ]
    finally:
        panel.close()


def test_worker_start_failure_discards_handle_and_clears_active_state(monkeypatch):
    _app()
    panel = WorkbenchPanel(PanelBridge())

    class _Worker:
        def __init__(self) -> None:
            self.shutdown_calls = 0

        def shutdown(self, timeout_ms=None) -> None:
            self.shutdown_calls += 1

    worker = _Worker()
    build = SimpleNamespace(
        worker=worker,
        cancelled=False,
        already_running=False,
        error_text="",
        session_snapshot=None,
    )
    results = []
    monkeypatch.setattr(panel._execution, "prepare_worker", lambda _worker: None)
    monkeypatch.setattr(
        panel._execution_session,
        "start_worker",
        lambda _worker: (_ for _ in ()).throw(RuntimeError("start boom")),
    )
    monkeypatch.setattr(panel, "apply_execution_result", results.append)
    try:
        panel._start_worker_from_build(build)

        assert panel._execution_session.active_worker is None
        assert worker.shutdown_calls == 1
        assert len(results) == 1
        assert "execution_worker_start_failed:RuntimeError:start boom" in results[0][
            "error_text"
        ]
    finally:
        panel.close()


def test_start_batch_execution_passes_material_batch_selection_into_session_build_worker():
    _app()
    bridge = PanelBridge()
    bridge.set_current_work_mode("official", emit_signal=False)
    panel = WorkbenchPanel(bridge)
    try:
        expected_overrides = {"header_footer.suppress_header_footer_selectors": ["cover"]}
        selection = MaterialBatchSelection(
            archive=EntityArchive(
                archive_id="archive",
                profiles=[
                    EntityProfile(
                        profile_id="a",
                        profile_name="Entity A",
                        fields={"company_name": "Company A"},
                    )
                ],
            ),
            profile_ids=["a"],
            output_dir_template="{profile_id}-{entity_name}",
            base_context=MaterialExecutionContext(
                field_aliases={"company": "company_name"}
            ),
            source_kind="official_document_table",
            source_path="D:/materials/official_batch.csv",
            item_metadata={"a": {"official_profile_id": "notice"}},
        )
        bridge.set_current_material_batch_selection(selection, emit_signal=False)

        class _BuildResult:
            def __init__(self, worker):
                self.worker = worker
                self.cancelled = False
                self.already_running = False

        class _FakeSession:
            def __init__(self):
                self.active_worker = None
                self.batch_kwargs = None
                self.start_calls = []

            def set_active_worker(self, worker):
                self.active_worker = worker

            def build_batch_worker(self, **kwargs):
                self.batch_kwargs = dict(kwargs)
                return _BuildResult(worker=object())

            def start_worker(self, worker):
                self.start_calls.append(worker)

            def shutdown_active_execution(self, timeout_ms=1000):
                return True

        class _FakeExecution:
            def __init__(self):
                self.prepared = []

            def prepare_worker(self, worker):
                self.prepared.append(worker)

        fake_session = _FakeSession()
        fake_execution = _FakeExecution()

        panel._execution_session = fake_session
        panel._execution = fake_execution
        official_scene = SceneWorkspace(scene_id="official", mode_id="official")
        panel._current_scene = official_scene
        panel._quick_execution_detail.set_scene_context(official_scene)
        panel._quick_execution_detail.runtime_template_overrides = lambda: dict(expected_overrides)
        panel._batch_generation_detail.output_dir = lambda: "D:/batch"

        panel._start_batch_execution()

        assert fake_session.batch_kwargs is not None
        assert fake_session.batch_kwargs["archive"].archive_id == "archive"
        assert fake_session.batch_kwargs["profile_ids"] == ["a"]
        assert fake_session.batch_kwargs["base_output_dir"] == "D:/batch"
        assert fake_session.batch_kwargs["output_dir_template"] == "{profile_id}-{entity_name}"
        assert fake_session.batch_kwargs["session_overrides"] == expected_overrides
        assert fake_session.batch_kwargs["base_context"].field_aliases == {
            "company": "company_name"
        }
        assert fake_session.batch_kwargs["source_kind"] == "official_document_table"
        assert fake_session.batch_kwargs["source_path"] == "D:/materials/official_batch.csv"
        assert fake_session.batch_kwargs["item_metadata"] == {
            "a": {"official_profile_id": "notice"}
        }
        assert fake_session.start_calls
        assert fake_execution.prepared
    finally:
        panel.close()


def test_execution_session_official_table_batch_does_not_require_source_document():
    _app()
    resolve_calls = []
    controller = WorkbenchExecutionSessionController(
        resolve_document_path=lambda: resolve_calls.append(True) or None,
    )

    build = controller.build_batch_worker(
        template=create_builtin_template("official_gbt"),
        scene=load_scene_from_library("official", mode_id="official"),
        archive=EntityArchive(
            profiles=[
                EntityProfile(
                    profile_id="row_1",
                    profile_name="Notice A",
                    fields={"document_type": "notice"},
                )
            ]
        ),
        profile_ids=["row_1"],
        source_kind="official_document_table",
        source_path="D:/materials/official_batch.csv",
        mode_id="official",
        plan_id="official",
        template_id="official_gbt",
    )

    assert build.cancelled is False
    assert build.worker is not None
    assert build.session_snapshot.document_type_id == "per_item"
    assert resolve_calls == []
    build.worker.shutdown()


def test_execution_session_official_table_batch_freezes_each_selected_document_type_master():
    _app()
    controller = WorkbenchExecutionSessionController(
        resolve_document_path=lambda: None,
    )

    build = controller.build_batch_worker(
        template=create_builtin_template("official_gbt"),
        scene=load_scene_from_library("official", mode_id="official"),
        archive=EntityArchive(
            profiles=[
                EntityProfile(
                    profile_id="letter_row",
                    profile_name="Letter",
                    fields={"document_type": "letter"},
                ),
                EntityProfile(
                    profile_id="minutes_row",
                    profile_name="Minutes",
                ),
                EntityProfile(
                    profile_id="not_selected",
                    profile_name="Notice",
                    fields={"document_type": "notice"},
                ),
            ]
        ),
        profile_ids=["letter_row", "minutes_row"],
        source_kind="official_document_table",
        source_path="D:/materials/official_batch.csv",
        item_metadata={
            "minutes_row": {"official_profile_id": "minutes"},
        },
        mode_id="official",
        plan_id="official",
        template_id="official_gbt",
    )

    assert build.cancelled is False
    assert build.worker is not None
    snapshot = build.session_snapshot
    assert snapshot is not None
    assert snapshot.document_type_id == "per_item"
    assert dict(snapshot.official_master_ids_by_document_type) == {
        "letter": "official_gbt_letter",
        "minutes": "official_gbt_minutes",
    }
    master_refs = {
        resource_ref.resource_id: resource_ref
        for resource_ref in (
            snapshot.master_ref,
            *snapshot.dependent_resource_refs,
        )
        if resource_ref.kind == "master"
    }
    assert set(master_refs) == {
        "official_gbt_letter",
        "official_gbt_minutes",
    }
    assert all(resource_ref.frozen_path for resource_ref in master_refs.values())
    assert all(
        Path(resource_ref.frozen_path).is_relative_to(
            Path(snapshot.output_namespace)
        )
        for resource_ref in master_refs.values()
    )
    build.worker.shutdown()


def test_execution_session_freezes_runtime_resolved_official_batch_type():
    _app()
    controller = WorkbenchExecutionSessionController(
        resolve_document_path=lambda: None,
    )

    build = controller.build_batch_worker(
        template=create_builtin_template("official_gbt"),
        scene=load_scene_from_library("official", mode_id="official"),
        archive=EntityArchive(
            profiles=[
                EntityProfile(
                    profile_id="row_1",
                    profile_name="Letter",
                    fields={"document_type": ""},
                )
            ]
        ),
        profile_ids=["row_1"],
        base_context=MaterialExecutionContext(
            mode_id="official",
            entity_data={"document_type": "notice"},
        ),
        source_kind="official_document_table",
        item_metadata={"row_1": {"official_profile_id": "letter"}},
        mode_id="official",
        plan_id="official",
        template_id="official_gbt",
    )

    assert build.worker is not None
    assert build.session_snapshot is not None
    assert dict(
        build.session_snapshot.official_master_ids_by_document_type
    ) == {"letter": "official_gbt_letter"}
    build.worker.shutdown()


def _ready_fake_snapshot(tmp_path):
    return SimpleNamespace(
        ready=True,
        issues=(),
        input_ref=SimpleNamespace(frozen_revision=""),
        output_namespace=str(tmp_path / "session"),
    )


def test_execution_session_cleans_snapshot_when_frozen_input_lookup_raises(
    tmp_path,
    monkeypatch,
):
    snapshot = _ready_fake_snapshot(tmp_path)
    cleanup_calls = []
    monkeypatch.setattr(
        session_controller_module,
        "build_execution_session_snapshot",
        lambda **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        session_controller_module,
        "execution_session_frozen_input_path",
        lambda _snapshot: (_ for _ in ()).throw(RuntimeError("frozen path boom")),
    )
    monkeypatch.setattr(
        session_controller_module,
        "cleanup_execution_session_resources",
        lambda value: cleanup_calls.append(value) or (),
    )
    controller = WorkbenchExecutionSessionController(
        resolve_document_path=lambda: str(tmp_path / "source.txt"),
    )

    build = controller.build_worker(
        template=TemplateConfig(),
        scene=SceneWorkspace(scene_id="custom", mode_id="custom"),
        mode_id="custom",
    )

    assert build.worker is None
    assert "execution_worker_build_failed:RuntimeError:frozen path boom" in build.error_text
    assert cleanup_calls == [snapshot]


def test_execution_session_cleans_snapshot_when_runner_construction_raises(
    tmp_path,
    monkeypatch,
):
    from src.services.production_runtime import execution_runtime

    snapshot = _ready_fake_snapshot(tmp_path)
    cleanup_calls = []
    monkeypatch.setattr(
        session_controller_module,
        "build_execution_session_snapshot",
        lambda **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        session_controller_module,
        "execution_session_frozen_input_path",
        lambda _snapshot: tmp_path / "source.txt",
    )
    monkeypatch.setattr(
        session_controller_module,
        "cleanup_execution_session_resources",
        lambda value: cleanup_calls.append(value) or (),
    )
    monkeypatch.setattr(
        execution_runtime,
        "WorkbenchProductionRunner",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("runner boom")),
    )
    controller = WorkbenchExecutionSessionController(
        resolve_document_path=lambda: str(tmp_path / "source.txt"),
    )

    build = controller.build_worker(
        template=TemplateConfig(),
        scene=SceneWorkspace(scene_id="custom", mode_id="custom"),
        mode_id="custom",
    )

    assert build.worker is None
    assert "execution_worker_build_failed:RuntimeError:runner boom" in build.error_text
    assert cleanup_calls == [snapshot]


def test_batch_execution_session_cleans_snapshot_when_preflight_raises(
    tmp_path,
    monkeypatch,
):
    snapshot = _ready_fake_snapshot(tmp_path)
    cleanup_calls = []
    monkeypatch.setattr(
        session_controller_module,
        "build_execution_session_snapshot",
        lambda **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        session_controller_module,
        "execution_session_frozen_input_path",
        lambda _snapshot: tmp_path / "source.txt",
    )
    monkeypatch.setattr(
        session_controller_module,
        "check_material_batch_preflight",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("batch preflight boom")
        ),
    )
    monkeypatch.setattr(
        session_controller_module,
        "cleanup_execution_session_resources",
        lambda value: cleanup_calls.append(value) or (),
    )
    controller = WorkbenchExecutionSessionController(
        resolve_document_path=lambda: str(tmp_path / "source.txt"),
    )

    build = controller.build_batch_worker(
        template=TemplateConfig(),
        scene=SceneWorkspace(scene_id="custom", mode_id="custom"),
        archive=EntityArchive(
            profiles=[EntityProfile(profile_id="row_1", profile_name="Row")]
        ),
        profile_ids=["row_1"],
        mode_id="custom",
    )

    assert build.worker is None
    assert (
        "batch_execution_worker_build_failed:RuntimeError:batch preflight boom"
        in build.error_text
    )
    assert cleanup_calls == [snapshot]


@pytest.mark.parametrize(
    ("mode_id", "expected_document_type_id"),
    (
        ("custom", ""),
        ("exam", ""),
        ("official", "letter"),
    ),
)
def test_start_execution_scopes_document_type_and_passes_runtime_overrides(
    mode_id,
    expected_document_type_id,
):
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        expected_overrides = {"header_footer.suppress_header_footer_selectors": ["cover", "toc"]}

        class _BuildResult:
            def __init__(self, worker):
                self.worker = worker
                self.cancelled = False
                self.already_running = False

        class _FakeSession:
            def __init__(self):
                self.active_worker = None
                self.build_kwargs = None
                self.start_calls = []

            def set_active_worker(self, worker):
                self.active_worker = worker

            def build_worker(self, **kwargs):
                self.build_kwargs = dict(kwargs)
                return _BuildResult(worker=object())

            def start_worker(self, worker):
                self.start_calls.append(worker)

            def shutdown_active_execution(self, timeout_ms=1000):
                return True

        class _FakeExecution:
            def __init__(self):
                self.prepared = []

            def prepare_worker(self, worker):
                self.prepared.append(worker)

        fake_session = _FakeSession()
        fake_execution = _FakeExecution()

        panel._execution_session = fake_session
        panel._execution = fake_execution
        panel._current_work_mode_id = lambda: mode_id
        panel._resolve_document_path_for_execution = lambda: "D:/source.docx"
        panel._ensure_object_preflight_confirmed = lambda: True
        ready_gate = SimpleNamespace(can_run=True, requires_confirmation=False)
        panel._quick_execution_detail.current_execution_gate_decision = (
            lambda: ready_gate
        )
        panel._quick_execution_detail.runtime_template_overrides = lambda: dict(expected_overrides)
        panel.bridge.set_current_material_context(
            MaterialExecutionContext(entity_data={"company_name": "测试公司"})
        )
        panel.bridge.set_current_official_document_type_id("letter")

        panel._start_execution()

        assert fake_session.build_kwargs is not None
        assert fake_session.build_kwargs["session_overrides"] == expected_overrides
        assert fake_session.build_kwargs["material_context"].entity_data == {"company_name": "测试公司"}
        assert (
            fake_session.build_kwargs["document_type_id"]
            == expected_document_type_id
        )
        assert fake_session.start_calls
        assert fake_execution.prepared
        assert fake_session.active_worker is fake_execution.prepared[0]
    finally:
        panel.close()


def test_start_execution_reads_material_context_from_shared_bridge_not_widget_cache():
    panel_source = inspect.getsource(WorkbenchPanel._start_execution)

    assert "material_context=self.bridge.current_material_context()" in panel_source
    assert "_content_fill_detail.material_context()" not in panel_source


def test_workbench_panel_syncs_material_context_into_quick_readiness():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        context = MaterialExecutionContext(entity_data={"company_name": "测试公司"})

        panel._sync_material_context_from_detail(context)

        assert bridge.current_material_context().entity_data == {"company_name": "测试公司"}
        assert panel._quick_execution_detail._material_context.entity_data == {
            "company_name": "测试公司"
        }
    finally:
        panel.close()


def test_workbench_panel_routes_quick_material_repair_to_content_fill_card():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    opened: list[str] = []
    try:
        panel._navigation.open_feature_card = lambda feature_id: opened.append(feature_id)

        panel._quick_execution_detail.feature_config_requested.emit("content_fill")

        assert opened == ["content_fill"]
    finally:
        panel.close()


def test_workbench_panel_routes_quick_asset_repair_to_core_content_fill():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    navigated: list[int] = []
    try:
        bridge.navigate_to_panel.connect(lambda index: navigated.append(index))

        panel._quick_execution_detail.material_repair_requested.emit("asset", "seal")

        assert bridge.current_material_repair_target() == ("asset", "seal")
        assert navigated == []
        assert panel._current_detail is panel._content_fill_detail
    finally:
        panel.close()


def test_workbench_panel_routes_quick_field_repair_to_core_content_fill():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    navigated: list[int] = []
    try:
        bridge.navigate_to_panel.connect(lambda index: navigated.append(index))

        panel._quick_execution_detail.material_repair_requested.emit("field", "company_name")

        assert bridge.current_material_repair_target() == ("field", "company_name")
        assert navigated == []
        assert panel._current_detail is panel._content_fill_detail
    finally:
        panel.close()


def test_workbench_panel_routes_schema_issue_repair_to_scene_content():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    opened: list[str] = []
    navigated: list[int] = []
    intents: list[object] = []
    scene_index = next(index for index, spec in enumerate(PANEL_SPECS) if spec.id == "scene")
    try:
        bridge.navigate_to_panel.connect(lambda index: navigated.append(index))
        bridge.navigate_to_intent.connect(intents.append)
        panel._navigation.open_feature_card = lambda feature_id: opened.append(feature_id)

        panel._open_issue_repair_target("schema", "signature_assets_v2")

        assert navigated == [scene_index]
        assert intents[-1]["panel_id"] == "scene"
        assert intents[-1]["card_id"] == "scn_content"
        assert intents[-1]["issue_id"] == "schema"
        assert intents[-1]["field_id"] == "signature_assets_v2"
        assert opened == []
    finally:
        panel.close()


def test_workbench_panel_routes_template_field_issue_repair_to_template_panel():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    navigated: list[int] = []
    intents: list[object] = []
    template_index = next(
        index for index, spec in enumerate(PANEL_SPECS) if spec.id == "template"
    )
    try:
        bridge.navigate_to_panel.connect(lambda index: navigated.append(index))
        bridge.navigate_to_intent.connect(intents.append)

        panel._open_issue_repair_target(
            "template_style_field",
            "template.styles.body.left_indent_chars",
        )

        assert navigated == [template_index]
        assert intents[-1]["panel_id"] == "template"
        assert intents[-1]["card_id"] == "tpl_style"
        assert intents[-1]["issue_id"] == "template_style_field"
        assert intents[-1]["field_id"] == "template.styles.body.left_indent_chars"
        assert intents[-1]["payload"]["issue_display_name"] == (
            "对齐与缩进：正文左缩进"
        )

        panel._open_issue_repair_target(
            "template_page_field",
            "template.page_setup.margin.left_cm",
        )

        assert navigated == [template_index, template_index]
        assert intents[-1]["panel_id"] == "template"
        assert intents[-1]["card_id"] == "tpl_page"
        assert intents[-1]["issue_id"] == "template_page_field"
        assert intents[-1]["field_id"] == "template.page_setup.margin.left_cm"
    finally:
        panel.close()


def test_workbench_panel_routes_document_scope_issue_repair_to_scope_detail():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    navigated: list[int] = []
    intents: list[object] = []
    scene_index = next(
        index for index, spec in enumerate(PANEL_SPECS) if spec.id == "scene"
    )
    try:
        bridge.navigate_to_panel.connect(lambda index: navigated.append(index))
        bridge.navigate_to_intent.connect(intents.append)

        panel._open_issue_repair_target(
            "scene_document_scope_field",
            "scene.document_scope.mode",
        )

        assert navigated == [scene_index]
        assert intents[-1]["panel_id"] == "scene"
        assert intents[-1]["card_id"] == "scn_rules"
        assert intents[-1]["issue_id"] == "scene_document_scope_field"
        assert intents[-1]["field_id"] == "scene.document_scope.mode"
        assert intents[-1]["payload"]["issue_display_name"] == "处理范围"
        assert intents[-1]["return_panel_id"] == "workbench"
        assert intents[-1]["return_card_id"] == "quick_execute"

        panel._open_issue_repair_target(
            "scene_document_scope_field",
            "scene.document_scope.selected_roles",
        )

        assert navigated == [scene_index, scene_index]
        assert intents[-1]["panel_id"] == "scene"
        assert intents[-1]["card_id"] == "scn_rules"
        assert intents[-1]["issue_id"] == "scene_document_scope_field"
        assert intents[-1]["field_id"] == "scene.document_scope.selected_roles"
    finally:
        panel.close()


def test_workbench_scene_field_repair_intent_reaches_scene_rule_widgets():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="thesis", template_id="thesis_gbt")
    bridge.set_current_scene(scene, config_id="thesis", emit_signal=False)
    bridge.set_current_template(
        create_builtin_template("thesis_gbt"),
        config_id="thesis_gbt",
        emit_signal=False,
    )
    workbench = WorkbenchPanel(bridge)
    scene_panel = ScenePanel(bridge)
    bridge.navigate_to_intent.connect(scene_panel.handle_navigation_intent)
    try:
        app.processEvents()

        workbench._open_issue_repair_target(
            "scene_document_scope_field",
            "scene.document_scope.mode",
        )
        app.processEvents()

        assert scene_panel._nav_rail.selected_card_id() == "scn_rules"
        assert scene_panel._return_bar.isHidden() is False
        assert scene_panel._return_label.text() == "从执行问题进入：处理范围"
        assert (
            scene_panel._scope._document_scope_section.mode_control.property(
                "navigation_field_highlight"
            )
            is True
        )

        workbench._open_issue_repair_target(
            "scene_document_scope_field",
            "scene.document_scope.selected_roles",
        )
        app.processEvents()

        assert scene_panel._nav_rail.selected_card_id() == "scn_rules"
        assert (
            scene_panel._scope._document_scope_section.mode_control.property(
                "navigation_field_highlight"
            )
            is True
        )
    finally:
        workbench.close()
        scene_panel.close()
        app.processEvents()


def test_workbench_schema_repair_intent_reaches_scene_content_schema_controls():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="contract_delivery", template_id="default")
    scene.input_source_profile.material_schema_id = "signature_assets_v2"
    bridge.set_current_scene(scene, config_id="contract_delivery", emit_signal=False)
    bridge.set_current_template(
        create_builtin_template("default"),
        config_id="default",
        emit_signal=False,
    )
    workbench = WorkbenchPanel(bridge)
    scene_panel = ScenePanel(bridge)
    bridge.navigate_to_intent.connect(scene_panel.handle_navigation_intent)
    try:
        app.processEvents()

        workbench._open_issue_repair_target("schema", "signature_assets_v2")
        app.processEvents()

        assert scene_panel._nav_rail.selected_card_id() == "scn_content"
        assert scene_panel._return_label.text() == (
            "从执行问题进入：资料规则：signature_assets_v2"
        )
        assert scene_panel._return_bar.isHidden() is False
        assert (
            scene_panel._content._material_schema_id.property(
                "navigation_field_highlight"
            )
            is True
        )
    finally:
        workbench.close()
        scene_panel.close()
        app.processEvents()


def test_start_execution_requires_object_preflight_confirmation_before_worker():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        expected_overrides = {"header_footer.suppress_header_footer_selectors": ["cover"]}
        preview_payload = {
            "enabled": True,
            "source_revision": "sha256:" + "a" * 64,
            "preservation_mode": "warn",
            "scan_targets": ["comments", "ole_objects"],
            "findings_count": 1,
            "findings": [
                {
                    "kind": "comments",
                    "severity": "warning",
                    "location": "word/comments.xml",
                    "message": "Comments are present.",
                }
            ],
            "blocking_findings_count": 0,
            "blocked": False,
            "module_skips_count": 1,
            "module_skips": [
                {
                    "module_name": "section_format",
                    "finding_kinds": ["ole_objects"],
                    "reason": "Skipped because object preflight found ole_objects.",
                }
            ],
        }

        class _BuildResult:
            def __init__(self, worker):
                self.worker = worker
                self.cancelled = False
                self.already_running = False

        class _FakeSession:
            def __init__(self):
                self.active_worker = None
                self.build_kwargs = None
                self.start_calls = []

            def set_active_worker(self, worker):
                self.active_worker = worker

            def build_worker(self, **kwargs):
                self.build_kwargs = dict(kwargs)
                return _BuildResult(worker=object())

            def start_worker(self, worker):
                self.start_calls.append(worker)

            def shutdown_active_execution(self, timeout_ms=1000):
                return True

        class _FakeExecution:
            def __init__(self):
                self.prepared = []

            def prepare_worker(self, worker):
                self.prepared.append(worker)

        fake_session = _FakeSession()
        fake_execution = _FakeExecution()
        panel._execution_session = fake_session
        panel._execution = fake_execution
        panel._resolve_document_path_for_execution = lambda: "D:/source.docx"
        panel._quick_execution_detail.runtime_template_overrides = lambda: dict(expected_overrides)
        preview_evidence = _object_preflight_evidence_stub(preview_payload)
        panel._build_object_preflight_preview_evidence = lambda: preview_evidence

        panel._start_execution()

        assert fake_session.build_kwargs is None
        assert fake_session.start_calls == []
        assert panel._quick_execution_detail._execute_btn.text() == "确认并继续"
        log_text = panel._quick_execution_detail._exec_log.toPlainText()
        assert "对象预检发现风险，再次点击将继续执行。" in log_text
        assert "对象预检明细：风险[warning] comments @ word/comments.xml: Comments are present." in log_text
        assert "对象预检明细：跳过模块 section_format <- ole_objects" in log_text

        panel._start_execution()

        assert fake_session.build_kwargs is not None
        assert fake_session.build_kwargs["session_overrides"] == expected_overrides
        assert fake_session.build_kwargs["expected_input_revision"] == (
            "sha256:" + "a" * 64
        )
        assert fake_session.build_kwargs[
            "object_preflight_confirmation_digest"
        ] == preview_evidence.evidence_digest
        assert fake_session.start_calls
        assert fake_execution.prepared
    finally:
        panel.close()


def test_object_preflight_confirmation_can_be_cancelled_without_running_worker(
    tmp_path,
):
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        preview_payload = {
            "enabled": True,
            "source_path": str(tmp_path / "source.docx"),
            "source_revision": "sha256:" + "a" * 64,
            "preservation_mode": "warn",
            "findings_count": 1,
            "findings": [
                {
                    "kind": "comments",
                    "severity": "warning",
                    "location": "word/comments.xml",
                    "message": "Comments are present.",
                }
            ],
            "blocking_findings_count": 0,
            "blocked": False,
            "module_skips_count": 0,
            "module_skips": [],
        }
        preview_evidence = _object_preflight_evidence_stub(preview_payload)
        panel._build_object_preflight_preview_evidence = lambda: preview_evidence

        assert panel._ensure_object_preflight_confirmed() is False
        assert panel._pending_object_preflight_confirmation_key
        assert panel._quick_execution_detail._execute_btn.text() == "确认并继续"
        assert (
            panel._quick_execution_detail._object_preflight_cancel_btn.isHidden()
            is False
        )

        panel._quick_execution_detail._object_preflight_cancel_btn.click()

        assert panel._pending_object_preflight_confirmation_key == ""
        assert panel._quick_execution_detail._last_result_status == "idle"
        assert (
            panel._quick_execution_detail._object_preflight_cancel_btn.isHidden()
            is True
        )
    finally:
        panel.close()


def test_warning_preflight_reuses_owner_evidence_and_exact_digest(tmp_path):
    _app()
    source = tmp_path / "warning.docx"
    Document().save(source)
    with ZipFile(source, "a") as package:
        package.writestr("word/embeddings/oleObject1.bin", b"ole")
    scene = SceneWorkspace(scene_id=" custom ", mode_id="custom")
    scene.strict_mode = False
    policy = scene.compliance_profile.object_preflight
    policy.scan_targets = ["ole_objects"]
    policy.preservation_mode = "warn"
    policy.block_on = []
    expected = build_object_preflight_evidence(scene, source)

    panel = WorkbenchPanel(PanelBridge())
    try:
        panel._current_scene = scene
        panel._quick_execution_detail.set_scene_context(scene)
        panel._document_paths.apply_loaded_document(str(source))
        build_calls = []
        real_build = panel._build_object_preflight_preview_evidence

        def _counted_build():
            build_calls.append(True)
            return real_build()

        panel._build_object_preflight_preview_evidence = _counted_build

        assert panel._ensure_object_preflight_confirmed() is False
        assert panel._ensure_object_preflight_confirmed() is True

        assert build_calls == [True]
        assert panel._confirmed_object_preflight_source_revision == (
            expected.source_revision
        )
        assert panel._confirmed_object_preflight_digest == expected.evidence_digest
        assert panel._pending_object_preflight_evidence is None
    finally:
        panel.close()


def test_start_execution_scans_picked_document_before_object_preflight_confirmation(
    tmp_path,
):
    _app()
    source = tmp_path / "picked-after-click.docx"
    Document().save(source)
    with ZipFile(source, "a") as package:
        package.writestr("word/embeddings/oleObject1.bin", b"ole")

    panel = WorkbenchPanel(PanelBridge())
    try:
        scene = SceneWorkspace(scene_id="custom", mode_id="custom")
        scene.strict_mode = False
        scene.compliance_profile.failure_policy = "warn"
        policy = scene.compliance_profile.object_preflight
        policy.enabled = True
        policy.preservation_mode = "warn"
        policy.scan_targets = ["ole_objects"]
        policy.block_on = []
        panel._current_scene = scene
        panel._quick_execution_detail.set_scene_context(scene)

        class _BuildResult:
            worker = object()
            cancelled = False
            already_running = False
            error_text = ""

        class _FakeSession:
            def __init__(self):
                self.active_worker = None
                self.build_kwargs = None
                self.start_calls = []

            def set_active_worker(self, worker):
                self.active_worker = worker

            def build_worker(self, **kwargs):
                self.build_kwargs = dict(kwargs)
                return _BuildResult()

            def start_worker(self, worker):
                self.start_calls.append(worker)

            def shutdown_active_execution(self, timeout_ms=1000):
                return True

        class _FakeExecution:
            def __init__(self):
                self.prepared = []

            def prepare_worker(self, worker):
                self.prepared.append(worker)

        fake_session = _FakeSession()
        fake_execution = _FakeExecution()
        pick_calls = []
        structure_scan_calls = []

        def _record_structure_scan(source_path, *, force=False):
            scope = panel._document_scope
            if (
                scope._scan_source_path == source_path
                and scope._scan_request_id in scope._scans
            ):
                return
            structure_scan_calls.append((source_path, force))
            scope._scan_source_path = source_path
            scope._scan_request_id = "test-scan"
            scope._scans["test-scan"] = SimpleNamespace(
                shutdown=lambda _timeout_ms: True
            )

        panel._execution_session = fake_session
        panel._execution = fake_execution
        panel._document_paths._pick_document_path = (
            lambda: pick_calls.append(True) or str(source)
        )
        panel._document_scope.start_scan = _record_structure_scan

        panel._start_execution()

        assert pick_calls == [True]
        assert fake_session.build_kwargs is None
        assert structure_scan_calls == [(str(source), True)]
        assert panel._pending_object_preflight_confirmation_key == ""
        assert fake_session.start_calls == []
    finally:
        panel.close()


def test_material_blocker_precedes_object_preflight_confirmation():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        scene = SceneWorkspace(scene_id="official", mode_id="official")
        scene.input_source_profile.failure_policy = "block"
        scene.input_source_profile.required_material_fields = ["title"]
        panel._current_scene = scene
        panel._quick_execution_detail.set_scene_context(scene)
        panel._quick_execution_detail.set_material_context(MaterialExecutionContext())
        object_preflight_calls = []
        panel._ensure_object_preflight_confirmed = (
            lambda: object_preflight_calls.append(True) or True
        )

        panel._start_execution()

        assert object_preflight_calls == []
        assert panel._quick_execution_detail.current_execution_gate_decision().state == (
            "blocked"
        )
    finally:
        panel.close()


def test_start_execution_blocks_on_strict_object_preflight_findings():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        preview_payload = {
            "enabled": True,
            "preservation_mode": "strict",
            "scan_targets": ["ole_objects"],
            "findings_count": 1,
            "findings": [
                {
                    "kind": "ole_objects",
                    "severity": "error",
                    "location": "word/document.xml",
                    "message": "OLE object markup is present.",
                }
            ],
            "blocking_findings_count": 1,
            "blocked": True,
            "module_skips_count": 0,
            "module_skips": [],
        }

        class _FakeSession:
            def __init__(self):
                self.active_worker = None
                self.build_kwargs = None
                self.start_calls = []

            def build_worker(self, **kwargs):
                self.build_kwargs = dict(kwargs)
                raise AssertionError("worker should not be built for blocking preflight")

            def shutdown_active_execution(self, timeout_ms=1000):
                return True

        panel._execution_session = _FakeSession()
        panel._resolve_document_path_for_execution = lambda: "D:/source.docx"
        preview_evidence = _object_preflight_evidence_stub(preview_payload)
        panel._build_object_preflight_preview_evidence = lambda: preview_evidence

        panel._start_execution()

        assert panel._execution_session.build_kwargs is None
        assert panel._quick_execution_detail._execute_btn.text() == "重新检查"
        assert panel._quick_execution_detail._object_preflight_cancel_btn.isHidden() is True
        log_text = panel._quick_execution_detail._exec_log.toPlainText()
        assert "对象预检发现阻断风险，已停止执行。" in log_text
        assert "对象预检明细：风险[error] ole_objects @ word/document.xml: OLE object markup is present." in log_text
    finally:
        panel.close()
