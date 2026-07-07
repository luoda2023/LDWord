import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.config.builtin_templates import create_builtin_template
from src.config.entity import EntityArchive, EntityProfile
from src.config.material_batch import MaterialBatchSelection
from src.config.material_context import MaterialExecutionContext
from src.config.resolved import ReplacementRule
from src.config.scene import SceneWorkspace
from src.ui.bridge import PanelBridge
from src.ui.panel_registry import PANEL_SPECS
from src.ui.panels.scene_panel import ScenePanel
from src.ui.panels.workbench.execution_session_controller import WorkbenchExecutionSessionController
from src.ui.panels.workbench.panel_v2 import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


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


def test_start_batch_execution_passes_material_batch_selection_into_session_build_worker():
    _app()
    bridge = PanelBridge()
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
                replacements=[ReplacementRule(old="{{project}}", new="Project")]
            ),
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
        panel._quick_execution_detail.runtime_template_overrides = lambda: dict(expected_overrides)
        panel._quick_execution_detail.custom_output_dir = lambda: "D:/batch"

        panel._start_batch_execution()

        assert fake_session.batch_kwargs is not None
        assert fake_session.batch_kwargs["archive"].archive_id == "archive"
        assert fake_session.batch_kwargs["profile_ids"] == ["a"]
        assert fake_session.batch_kwargs["base_output_dir"] == "D:/batch"
        assert fake_session.batch_kwargs["output_dir_template"] == "{profile_id}-{entity_name}"
        assert fake_session.batch_kwargs["session_overrides"] == expected_overrides
        assert fake_session.batch_kwargs["base_context"].replacements == [
            ReplacementRule(old="{{project}}", new="Project")
        ]
        assert fake_session.start_calls
        assert fake_execution.prepared
    finally:
        panel.close()


def test_start_execution_passes_runtime_overrides_into_session_build_worker():
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
        panel._quick_execution_detail.runtime_template_overrides = lambda: dict(expected_overrides)
        panel._content_fill_detail.set_material_context(
            MaterialExecutionContext(entity_data={"company_name": "测试公司"}),
            emit_signal=False,
        )

        panel._start_execution()

        assert fake_session.build_kwargs is not None
        assert fake_session.build_kwargs["session_overrides"] == expected_overrides
        assert fake_session.build_kwargs["material_context"].entity_data == {"company_name": "测试公司"}
        assert fake_session.start_calls
        assert fake_execution.prepared
        assert fake_session.active_worker is fake_execution.prepared[0]
    finally:
        panel.close()


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


def test_workbench_panel_routes_quick_asset_repair_to_assets_panel_target():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    navigated: list[int] = []
    assets_index = next(index for index, spec in enumerate(PANEL_SPECS) if spec.id == "assets")
    try:
        bridge.navigate_to_panel.connect(lambda index: navigated.append(index))

        panel._quick_execution_detail.material_repair_requested.emit("asset", "seal")

        assert bridge.current_material_repair_target() == ("asset", "seal")
        assert navigated == [assets_index]
    finally:
        panel.close()


def test_workbench_panel_routes_quick_field_repair_to_assets_panel_target():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    navigated: list[int] = []
    assets_index = next(index for index, spec in enumerate(PANEL_SPECS) if spec.id == "assets")
    try:
        bridge.navigate_to_panel.connect(lambda index: navigated.append(index))

        panel._quick_execution_detail.material_repair_requested.emit("field", "company_name")

        assert bridge.current_material_repair_target() == ("field", "company_name")
        assert navigated == [assets_index]
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


def test_workbench_panel_routes_scene_field_issue_repair_to_scene_scope_detail():
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
            "scene_style_field",
            "scene.section_styles.references_body.font_cn",
        )

        assert navigated == [scene_index]
        assert intents[-1]["panel_id"] == "scene"
        assert intents[-1]["card_id"] == "scn_rules"
        assert intents[-1]["issue_id"] == "scene_style_field"
        assert intents[-1]["field_id"] == "scene.section_styles.references_body.font_cn"
        assert intents[-1]["payload"]["issue_display_name"] == (
            "文字样式：参考文献正文中文字体"
        )
        assert intents[-1]["return_panel_id"] == "workbench"
        assert intents[-1]["return_card_id"] == "quick_execute"

        panel._open_issue_repair_target(
            "scene_scope_field",
            "format_scope.sections.references",
        )

        assert navigated == [scene_index, scene_index]
        assert intents[-1]["panel_id"] == "scene"
        assert intents[-1]["card_id"] == "scn_rules"
        assert intents[-1]["issue_id"] == "scene_scope_field"
        assert intents[-1]["field_id"] == "format_scope.sections.references"
    finally:
        panel.close()


def test_workbench_scene_field_repair_intent_reaches_scene_scope_widgets():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="thesis", template_id="thesis_gbt")
    scene.format_scope.sections["references"] = True
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
            "scene_style_field",
            "scene.section_styles.references_body.font_cn",
        )
        app.processEvents()

        assert scene_panel._nav_rail.selected_card_id() == "scn_rules"
        assert scene_panel._return_bar.isHidden() is False
        assert scene_panel._return_label.text() == (
            "从执行问题进入：文字样式：参考文献正文中文字体"
        )
        assert (
            scene_panel._reference._font_cn_row.property(
                "navigation_field_highlight"
            )
            is True
        )

        workbench._open_issue_repair_target(
            "scene_scope_field",
            "format_scope.sections.references",
        )
        app.processEvents()

        assert scene_panel._nav_rail.selected_card_id() == "scn_rules"
        assert (
            scene_panel._scope._zone_checks["references"].property(
                "navigation_field_highlight"
            )
            is True
        )

        workbench._open_issue_repair_target(
            "scene_style_field",
            "scene.section_styles.*.line_spacing_pt",
        )
        app.processEvents()

        assert scene_panel._nav_rail.selected_card_id() == "scn_rules"
        current_variant = scene_panel._style_rules._style_variant_combo.currentData()
        assert current_variant != "references_body"
        assert any(
            toggle.property("navigation_field_highlight") is True
            for toggle in scene_panel._style_rules._variant_toggles.values()
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
        panel._quick_execution_detail.runtime_template_overrides = lambda: dict(expected_overrides)
        panel._build_object_preflight_preview_payload = lambda: dict(preview_payload)

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
        assert fake_session.start_calls
        assert fake_execution.prepared
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
        panel._build_object_preflight_preview_payload = lambda: dict(preview_payload)

        panel._start_execution()

        assert panel._execution_session.build_kwargs is None
        assert panel._quick_execution_detail._execute_btn.text() == "重新检查"
        log_text = panel._quick_execution_detail._exec_log.toPlainText()
        assert "对象预检发现阻断风险，已停止执行。" in log_text
        assert "对象预检明细：风险[error] ole_objects @ word/document.xml: OLE object markup is present." in log_text
    finally:
        panel.close()
