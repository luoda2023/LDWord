# -*- coding: utf-8 -*-
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig
from src.qt_api import QApplication, QHBoxLayout, QLabel, QVBoxLayout
from src.shared.ui.theme import DARK, get_theme, set_theme
from src.ui.bridge import PanelBridge
from src.ui.panels.workbench import WorkbenchPanel as PackageWorkbenchPanel
from src.ui.panels.workbench.command_bar import TaskCommandBar
from src.ui.panels.workbench.recent_run_panel import RecentRunPanel
from src.ui.panels.workbench_panel import WorkbenchPanel
from src.ui.panels.workbench.state import CurrentTaskState
from src.ui.panels.workbench.styles import build_workbench_stylesheet


def _app():
    return QApplication.instance() or QApplication([])


def test_workbench_panel_import_path_stays_stable_after_package_split():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel.__class__.__name__ == "WorkbenchPanel"
        assert panel.objectName() == "WorkbenchPanel"
        assert PackageWorkbenchPanel is WorkbenchPanel
    finally:
        panel.close()


def test_workbench_panel_exposes_command_center_regions():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert hasattr(panel, "_command_bar")
        assert hasattr(panel, "_strategy_card")
        assert hasattr(panel, "_capability_grid")
        assert hasattr(panel, "_execution_center")
        assert hasattr(panel, "_recent_run_panel")
        assert panel._strategy_card is not None
        assert panel._capability_grid is not None
        assert getattr(panel, "_heading_quick_card", None) is not None
        assert panel._execution_center is not None
        assert panel._recent_run_panel is not None
    finally:
        panel.close()


def test_workbench_panel_mounts_recent_run_panel_in_bottom_region():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel._recent_run_panel is not None
        assert isinstance(panel._recent_run_panel, RecentRunPanel)
        assert panel.layout().itemAt(2).widget() is panel._recent_run_panel
    finally:
        panel.close()


def test_workbench_panel_re_emits_heading_advanced_request():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        advanced_calls = []
        panel.heading_advanced_requested.connect(lambda: advanced_calls.append(True))

        panel._heading_quick_card._advanced_btn.click()

        assert advanced_calls == [True]
    finally:
        panel.close()


def test_heading_quick_card_is_hosted_in_capability_grid_slot():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel._capability_grid.card_at(0, 0) is panel._heading_quick_card
        assert panel._heading_quick_card.parent() is panel._capability_grid
    finally:
        panel.close()


def test_workbench_panel_sets_strategy_card_from_summary():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        template = TemplateConfig(name="论文模板")
        scene = SceneWorkspace(
            name="论文标准",
            description="结构优先",
            category_label="结构化",
            strict_mode=False,
        )
        for module_name in list(scene.module_switches.keys()):
            scene.module_switches[module_name] = False
        scene.module_switches["page_setup"] = True

        panel.set_strategy_summary(template, scene)

        assert panel._strategy_card._name_value.text() == "策略: 论文标准"
        assert panel._strategy_card._template_value.text() == "模板: 论文模板"
        assert panel._strategy_card._scene_value.text() == "场景: 结构优先"
        assert panel._strategy_card._modules_value.text() == "模块数: 1"
    finally:
        panel.close()


def test_workbench_panel_updates_strategy_card_via_bridge():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        template = TemplateConfig(name="桥接模板")
        scene = SceneWorkspace(
            name="桥接场景",
            description="桥接描述",
            category_label="桥接分类",
            strict_mode=False,
        )
        for module_name in list(scene.module_switches.keys()):
            scene.module_switches[module_name] = False
        scene.module_switches["page_setup"] = True

        bridge.template_changed.emit(template)

        assert panel._strategy_card._template_value.text() == "模板: 桥接模板"
        assert panel._strategy_card._scene_value.text() == "场景: 未绑定场景"
        assert panel._strategy_card._source_value.text() == "来源: 模板"
        assert panel._strategy_card._strict_mode_value.text() == "严格模式: 未适用"

        bridge.scene_changed.emit(scene)

        assert panel._strategy_card._name_value.text() == "策略: 桥接场景"
        assert panel._strategy_card._scene_value.text() == "场景: 桥接描述"
        assert panel._strategy_card._template_value.text() == "模板: 桥接模板"
        assert panel._strategy_card._modules_value.text() == "模块数: 1"
        assert panel._strategy_card._source_value.text() == "来源: 场景"
        assert panel._strategy_card._strict_mode_value.text() == "严格模式: 否"
    finally:
        panel.close()


def test_workbench_panel_preserves_cached_template_on_later_scene_bridge_update():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        template = TemplateConfig(name="混合模板")
        scene = SceneWorkspace(
            name="起始场景",
            description="起始描述",
            category_label="起始分类",
            strict_mode=False,
        )
        for module_name in list(scene.module_switches.keys()):
            scene.module_switches[module_name] = False
        scene.module_switches["page_setup"] = True

        panel.set_strategy_summary(template, scene)

        updated_scene = SceneWorkspace(
            name="更新场景",
            description="更新描述",
            category_label="更新分类",
            strict_mode=True,
        )
        for module_name in list(updated_scene.module_switches.keys()):
            updated_scene.module_switches[module_name] = False
        updated_scene.module_switches["page_setup"] = True

        bridge.scene_changed.emit(updated_scene)

        assert panel._strategy_card._scene_value.text() == "场景: 更新描述"
        assert panel._strategy_card._template_value.text() == "模板: 混合模板"
        assert panel._strategy_card._modules_value.text() == "模块数: 1"
    finally:
        panel.close()


def test_workbench_panel_set_strategy_summary_allows_clearing_scene():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        template = TemplateConfig(name="初始模板")
        scene = SceneWorkspace(
            name="起始场景",
            description="起始描述",
            category_label="起始分类",
            strict_mode=False,
        )
        panel.set_strategy_summary(template, scene)

        new_template = TemplateConfig(name="清除模板")
        panel.set_strategy_summary(new_template, None)

        assert panel._strategy_card._template_value.text() == "模板: 清除模板"
        assert panel._strategy_card._scene_value.text() == "场景: 未绑定场景"
    finally:
        panel.close()


def test_command_bar_is_first_root_widget():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel._root_layout.itemAt(0).widget() is panel._command_bar
    finally:
        panel.close()


def test_panel_can_forward_current_task_state_to_command_bar():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        state = CurrentTaskState(
            document_label="thesis.docx",
            strategy_label="论文标准",
            ready=True,
            status_text="待执行",
        )
        panel.set_current_task_state(state)
        assert panel._command_bar._doc_value.text() == "thesis.docx"
        assert panel._command_bar._run_button.isEnabled()
    finally:
        panel.close()


def test_current_task_state_defaults_to_not_ready():
    state = CurrentTaskState()

    assert state.document_label == "未选择文档"
    assert state.strategy_label == "未选择策略"
    assert state.ready is False
    assert state.status_text == "待执行"


def test_task_command_bar_renders_document_strategy_and_ready_status(qtbot=None):
    _app()
    bar = TaskCommandBar()
    assert bar.objectName() == "wb_command_bar"
    assert not bar._run_button.isEnabled()
    assert bar._status_value.text() == "待执行"
    state = CurrentTaskState(
        document_label="thesis.docx",
        strategy_label="论文标准",
        ready=True,
        status_text="待执行",
    )

    bar.set_state(state)

    assert bar._doc_value.text() == "thesis.docx"
    assert bar._strategy_value.text() == "论文标准"
    assert bar._status_value.text() == "待执行"
    assert bar._run_button.isEnabled()


def test_workbench_panel_uses_top_middle_bottom_page_skeleton():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert isinstance(panel.layout(), QVBoxLayout)
        assert panel.layout().count() == 3
        assert panel.layout().itemAt(0).widget() is panel._command_bar
        assert panel.layout().itemAt(2).widget() is panel._recent_run_panel
    finally:
        panel.close()


def test_workbench_panel_middle_region_absorbs_extra_height():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        layout = panel.layout()
        middle_index = layout.indexOf(panel._middle_container)
        bottom_index = layout.indexOf(panel._recent_run_panel)
        assert layout.stretch(middle_index) == 1
        assert layout.stretch(bottom_index) == 0
    finally:
        panel.close()


def test_workbench_panel_middle_region_is_left_right_split():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        middle = panel._middle_container
        assert middle is not None
        assert isinstance(middle.layout(), QHBoxLayout)
        assert panel._left_column is not None
        assert panel._right_column is not None
    finally:
        panel.close()


def test_workbench_panel_left_column_orders_strategy_before_capability_grid():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        left_layout = panel._left_column.layout()
        assert left_layout.itemAt(0).widget() is panel._strategy_card
        assert left_layout.itemAt(1).widget() is panel._capability_grid
    finally:
        panel.close()


def test_workbench_panel_right_column_hosts_execution_center_only():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        right_layout = panel._right_column.layout()
        assert right_layout.itemAt(0).widget() is panel._execution_center
        assert right_layout.count() == 1
    finally:
        panel.close()


def test_workbench_panel_bottom_region_is_not_part_of_middle_columns():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel._recent_run_panel.parent() is panel
        assert panel._recent_run_panel.parent() is not panel._left_column
        assert panel._recent_run_panel.parent() is not panel._right_column
    finally:
        panel.close()


def test_workbench_stylesheet_contains_expected_workbench_selectors():
    theme = get_theme()
    stylesheet = build_workbench_stylesheet(theme)

    assert "#wb_command_bar," in stylesheet
    assert "#wb_strategy_card {" in stylesheet
    assert "#wb_execution_center {" in stylesheet
    assert "#wb_recent_run {" in stylesheet
    assert "#wb_command_center_label," in stylesheet
    assert "#wb_execution_title {" in stylesheet
    assert "#wb_ready_badge {" in stylesheet
    assert f"background: {theme.bg_card};" in stylesheet
    assert f"border-radius: {theme.radius_md}px;" in stylesheet


def test_workbench_stylesheet_exposes_strategy_summary_roles():
    stylesheet = build_workbench_stylesheet(get_theme())

    assert "#wb_strategy_headline {" in stylesheet
    assert "#wb_strategy_binding {" in stylesheet
    assert "#wb_strategy_meta {" in stylesheet


def test_workbench_ready_copy_uses_chinese_operational_language():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel._command_bar._status_value.text() == "待执行"
        assert panel._execution_center._ready_label.text() == "待执行"
    finally:
        panel.close()


def test_workbench_stylesheet_encodes_surface_hierarchy():
    theme = get_theme()
    stylesheet = build_workbench_stylesheet(theme)

    assert "#wb_execution_center {" in stylesheet
    assert "border: 2px solid" in stylesheet
    assert "#wb_recent_run {" in stylesheet
    assert "#wb_heading_quick_card," in stylesheet
    assert "#wb_quick_fill_card {" in stylesheet


def test_workbench_stylesheet_marks_execution_center_as_primary_surface():
    theme = get_theme()
    stylesheet = build_workbench_stylesheet(theme)

    execution_start = stylesheet.index("#wb_execution_center {")
    execution_end = stylesheet.index("}", execution_start)
    execution_block = stylesheet[execution_start:execution_end]

    assert "border: 2px solid" in execution_block
    assert f"border-radius: {theme.radius_lg}px;" in execution_block
    assert "#wb_execution_title" in stylesheet
    assert "#wb_execution_section_title {" in stylesheet
    assert "#wb_execution_summary {" in stylesheet
    assert "#wb_execution_status {" in stylesheet


def test_workbench_panel_assigns_role_specific_object_names():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel._heading_quick_card.objectName() == "wb_heading_quick_card"
        assert panel._quick_fill_card.objectName() == "wb_quick_fill_card"
        assert panel._recent_run_panel.objectName() == "wb_recent_run"
        assert panel._strategy_card.objectName() == "wb_strategy_card"
    finally:
        panel.close()


def test_task_command_bar_uses_compact_strip_spacing():
    _app()
    bar = TaskCommandBar()
    try:
        margins = bar.layout().contentsMargins()

        assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (16, 10, 16, 10)
        assert bar.layout().spacing() == 12
    finally:
        bar.close()


def test_strategy_card_label_rule_is_dark_theme_safe():
    previous_theme = get_theme()
    try:
        set_theme(DARK)
        theme = get_theme()
        stylesheet = build_workbench_stylesheet(theme)

        assert "#wb_strategy_card QLabel" in stylesheet
        block_start = stylesheet.index("#wb_strategy_card QLabel")
        block_end = stylesheet.index("}", block_start)
        block = stylesheet[block_start:block_end]

        assert f"color: {theme.text_secondary};" in block
    finally:
        set_theme(previous_theme)


def test_workbench_panel_runtime_naming_and_text_path_matches_command_center_language():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel._command_bar.objectName() == "wb_command_bar"
        assert panel._strategy_card.objectName() == "wb_strategy_card"
        assert panel._execution_center.objectName() == "wb_execution_center"
        assert panel._recent_run_panel.objectName() == "wb_recent_run"
        assert panel._command_bar._center_label.text() == "任务中控"
        assert panel._strategy_card._title_label.text() == "执行策略"
        assert panel._execution_center._center_title.text() == "执行中心"
        assert panel.findChild(type(panel._command_bar), "wb_command_bar") is panel._command_bar
        assert panel.findChild(type(panel._strategy_card), "wb_strategy_card") is panel._strategy_card
        assert panel.findChild(type(panel._execution_center), "wb_execution_center") is panel._execution_center
        all_label_texts = [label.text() for label in panel.findChildren(QLabel)]
        assert "模板与场景" not in all_label_texts
    finally:
        panel.close()


def test_workbench_panel_execute_requested_runs_worker_and_syncs_result_panels():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        class _Signal:
            def __init__(self):
                self._callbacks = []

            def connect(self, callback):
                self._callbacks.append(callback)

            def emit(self, *args):
                for cb in list(self._callbacks):
                    cb(*args)

        class _StubWorker:
            def __init__(self):
                self.progress_changed = _Signal()
                self.execution_started = _Signal()
                self.execution_succeeded = _Signal()
                self.execution_partial = _Signal()
                self.execution_failed = _Signal()
                self.execution_cancelled = _Signal()
                self.execution_finished = _Signal()
                self.run_calls = 0

            def run(self) -> None:
                self.run_calls += 1
                self.execution_started.emit()
                self.progress_changed.emit(1, 2, "处理中")
                self.execution_succeeded.emit(
                    {
                        "status": "success",
                        "output_path": "out.docx",
                        "report_paths": ["report.json"],
                        "failed_count": 0,
                        "error_text": "",
                    }
                )
                self.execution_finished.emit()

        worker = _StubWorker()
        panel._build_execution_worker = lambda: worker

        panel._execution_center.execute_requested.emit()

        assert worker.run_calls == 1
        assert panel._execution_center._progress_stage_label.text() == "处理中"
        assert panel._execution_center._progress_bar.value() == 50
        assert panel._execution_center._summary_box.toPlainText() == "本次执行已完成"
        assert panel._execution_center._status_label.text() == panel._execution_center._friendly_status("success")
        assert panel._recent_run_panel._summary.text() == "本次执行已完成"
    finally:
        panel.close()


def test_workbench_panel_cancel_forwards_to_current_worker_when_present():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        class _DummyWorker:
            def __init__(self):
                self.cancel_calls = 0

            def request_cancel(self) -> None:
                self.cancel_calls += 1

        panel._execution_worker = _DummyWorker()

        panel._execution_center.cancel_requested.emit()

        assert panel._execution_worker.cancel_calls == 1
    finally:
        panel.close()


def test_workbench_panel_mirrors_current_task_readiness_into_execution_center():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        # Shipped path should be reachable without preloading state: the panel
        # starts in a default-ready state (document still unset).
        assert panel._execution_center._execute_button.isEnabled()
        assert panel._command_bar._run_button.isEnabled()
        assert panel._command_bar._doc_value.text() == "未选择文档"
        assert panel._command_bar._strategy_value.text() == "默认策略"
        assert panel._command_bar._status_value.text() == "待执行"

        state = CurrentTaskState(
            document_label="thesis.docx",
            strategy_label="论文标准",
            ready=True,
            status_text="待执行",
        )
        panel.set_current_task_state(state)

        assert panel._execution_center._execute_button.isEnabled()
    finally:
        panel.close()


def test_workbench_panel_document_loaded_updates_visible_document_label_and_preserves_ready_state(
    tmp_path,
):
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        doc_path = tmp_path / "picked.docx"
        doc_path.write_bytes(b"stub")

        bridge.document_loaded.emit(str(doc_path))

        assert panel._command_bar._doc_value.text() == "picked.docx"
        assert panel._command_bar._run_button.isEnabled()
        assert panel._execution_center._execute_button.isEnabled()
    finally:
        panel.close()


def test_workbench_panel_run_click_with_no_preloaded_doc_uses_file_picker_and_updates_label(
    tmp_path, monkeypatch
):
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        picked = tmp_path / "from_picker.docx"
        picked.write_bytes(b"stub")

        import src.ui.panels.workbench.panel as panel_module

        calls = {"open_calls": 0}

        def _fake_get_open_file_name(*args, **kwargs):
            calls["open_calls"] += 1
            return (str(picked), "Word Documents (*.docx)")

        monkeypatch.setattr(
            panel_module.QFileDialog,
            "getOpenFileName",
            staticmethod(_fake_get_open_file_name),
        )

        class _Signal:
            def __init__(self):
                self._callbacks = []

            def connect(self, callback):
                self._callbacks.append(callback)

            def emit(self, *args):
                for cb in list(self._callbacks):
                    cb(*args)

        thread_calls = {"start": 0}

        class _FakeThread:
            def __init__(self, *args, **kwargs):
                self.started = _Signal()
                self.finished = _Signal()
                self._running = False

            def start(self):
                thread_calls["start"] += 1
                self._running = True
                # Intentionally do not emit started; we only assert the panel uses start().

            def quit(self):
                self._running = False
                return

            def isRunning(self):
                return bool(self._running)

            def wait(self, timeout_ms=None):
                # Keep the fake thread fast: always "finish" immediately.
                return True

            def deleteLater(self):
                return

        class _FakeExecutionWorker:
            def __init__(self, runner, parent=None):
                self._runner = runner
                self.progress_changed = _Signal()
                self.execution_started = _Signal()
                self.execution_succeeded = _Signal()
                self.execution_partial = _Signal()
                self.execution_failed = _Signal()
                self.execution_cancelled = _Signal()
                self.execution_finished = _Signal()
                self.run_calls = 0

            def moveToThread(self, thread):
                return

            def request_cancel(self):
                return

            def run(self):
                self.run_calls += 1

            def deleteLater(self):
                return

        monkeypatch.setattr(panel_module, "QThread", _FakeThread)
        monkeypatch.setattr(panel_module, "ExecutionWorker", _FakeExecutionWorker)

        assert panel._command_bar._run_button.isEnabled()

        panel._command_bar._run_button.click()

        assert calls["open_calls"] == 1
        assert panel._command_bar._doc_value.text() == "from_picker.docx"
        assert thread_calls["start"] == 1
    finally:
        panel.close()


def test_command_bar_run_button_click_prefers_worker_start_and_triggers_lifecycle():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        class _Signal:
            def __init__(self):
                self._callbacks = []

            def connect(self, callback):
                self._callbacks.append(callback)

            def emit(self, *args):
                for cb in list(self._callbacks):
                    cb(*args)

        class _StubWorker:
            def __init__(self):
                self.progress_changed = _Signal()
                self.execution_started = _Signal()
                self.execution_succeeded = _Signal()
                self.execution_partial = _Signal()
                self.execution_failed = _Signal()
                self.execution_cancelled = _Signal()
                self.execution_finished = _Signal()
                self.start_calls = 0
                self.run_calls = 0

            def start(self) -> None:
                self.start_calls += 1
                self.execution_started.emit()
                self.progress_changed.emit(1, 2, "处理中")
                self.execution_succeeded.emit(
                    {
                        "status": "success",
                        "output_path": "out.docx",
                        "report_paths": ["report.json"],
                        "failed_count": 0,
                        "error_text": "",
                    }
                )
                self.execution_finished.emit()

            def run(self) -> None:
                self.run_calls += 1

        worker = _StubWorker()
        panel._build_execution_worker = lambda: worker
        panel.set_current_task_state(
            CurrentTaskState(
                document_label="thesis.docx",
                strategy_label="论文标准",
                ready=True,
                status_text="待执行",
            )
        )

        panel._command_bar._run_button.click()

        assert worker.start_calls == 1
        assert worker.run_calls == 0
        assert panel._execution_center._progress_stage_label.text() == "处理中"
        assert panel._execution_center._progress_bar.value() == 50
        assert panel._execution_center._summary_box.toPlainText() == "本次执行已完成"
        assert panel._recent_run_panel._summary.text() == "本次执行已完成"
    finally:
        panel.close()


def test_workbench_panel_guards_against_repeated_starts_while_worker_active():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        class _Signal:
            def __init__(self):
                self._callbacks = []

            def connect(self, callback):
                self._callbacks.append(callback)

            def emit(self, *args):
                for cb in list(self._callbacks):
                    cb(*args)

        class _ActiveWorker:
            def __init__(self):
                self.progress_changed = _Signal()
                self.execution_started = _Signal()
                self.execution_succeeded = _Signal()
                self.execution_partial = _Signal()
                self.execution_failed = _Signal()
                self.execution_cancelled = _Signal()
                self.execution_finished = _Signal()
                self.start_calls = 0

            def start(self) -> None:
                self.start_calls += 1
                self.execution_started.emit()
                # Intentionally do NOT emit finished; worker stays "active".

        worker = _ActiveWorker()
        build_calls = {"count": 0}

        def _build():
            build_calls["count"] += 1
            return worker

        panel._build_execution_worker = _build
        panel.set_current_task_state(
            CurrentTaskState(
                document_label="thesis.docx",
                strategy_label="论文标准",
                ready=True,
                status_text="待执行",
            )
        )

        panel._command_bar._run_button.click()
        panel._command_bar._run_button.click()

        assert build_calls["count"] == 1
        assert worker.start_calls == 1
    finally:
        panel.close()


def test_workbench_panel_no_worker_path_surfaces_deterministic_failure_state():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        panel._build_execution_worker = lambda: None
        panel.set_current_task_state(
            CurrentTaskState(
                document_label="thesis.docx",
                strategy_label="论文标准",
                ready=True,
                status_text="待执行",
            )
        )

        panel._command_bar._run_button.click()

        assert panel._execution_center._status_label.text() == panel._execution_center._friendly_status("failed")
        assert panel._execution_center._summary_box.toPlainText() == "执行失败"
        assert panel._recent_run_panel._summary.text() == "执行失败"
    finally:
        panel.close()


def test_workbench_panel_disables_execute_until_execution_finished_even_after_result():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        class _Signal:
            def __init__(self):
                self._callbacks = []

            def connect(self, callback):
                self._callbacks.append(callback)

            def emit(self, *args):
                for cb in list(self._callbacks):
                    cb(*args)

        class _DelayedFinishWorker:
            def __init__(self):
                self.progress_changed = _Signal()
                self.execution_started = _Signal()
                self.execution_succeeded = _Signal()
                self.execution_partial = _Signal()
                self.execution_failed = _Signal()
                self.execution_cancelled = _Signal()
                self.execution_finished = _Signal()
                self.start_calls = 0

            def start(self) -> None:
                self.start_calls += 1
                # Do not emit any callbacks yet; panel must lock affordances immediately.

        worker = _DelayedFinishWorker()
        panel._build_execution_worker = lambda: worker
        panel.set_current_task_state(
            CurrentTaskState(
                document_label="thesis.docx",
                strategy_label="论文标准",
                ready=True,
                status_text="待执行",
            )
        )

        panel._command_bar._run_button.click()

        assert worker.start_calls == 1
        assert not panel._command_bar._run_button.isEnabled()
        assert not panel._execution_center._execute_button.isEnabled()

        worker.execution_succeeded.emit(
            {
                "status": "success",
                "output_path": "out.docx",
                "report_paths": ["report.json"],
                "failed_count": 0,
                "error_text": "",
            }
        )

        assert panel._execution_center._status_label.text() == panel._execution_center._friendly_status("success")
        assert panel._execution_center._summary_box.toPlainText() == "本次执行已完成"
        assert panel._recent_run_panel._summary.text() == "本次执行已完成"
        assert not panel._command_bar._run_button.isEnabled()
        assert not panel._execution_center._execute_button.isEnabled()

        worker.execution_finished.emit()

        assert panel._command_bar._run_button.isEnabled()
        assert panel._execution_center._execute_button.isEnabled()
    finally:
        panel.close()


def test_workbench_panel_no_worker_path_resets_stale_progress_before_failed_result():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        panel.set_current_task_state(
            CurrentTaskState(
                document_label="thesis.docx",
                strategy_label="论文标准",
                ready=True,
                status_text="待执行",
            )
        )

        # Simulate a previous run leaving progress/stage visible.
        panel._execution_center.set_progress_state(
            panel._execution_adapter.build_progress_state(
                stage_text="处理中",
                current_step=1,
                total_steps=2,
            )
        )
        panel.apply_execution_result(
            {
                "status": "failed",
                "output_path": "",
                "report_paths": [],
                "failed_count": 0,
                "error_text": "boom",
            }
        )
        assert panel._execution_center._progress_stage_label.text() == "处理中"

        panel._build_execution_worker = lambda: None

        panel._command_bar._run_button.click()

        assert panel._execution_center._progress_stage_label.text() == "等待执行"
        assert panel._execution_center._progress_bar.value() == 0
        assert panel._execution_center._status_label.text() == panel._execution_center._friendly_status("failed")
    finally:
        panel.close()


def test_workbench_panel_execute_button_click_recovers_after_worker_finishes_without_result():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        class _Signal:
            def __init__(self):
                self._callbacks = []

            def connect(self, callback):
                self._callbacks.append(callback)

            def emit(self, *args):
                for cb in list(self._callbacks):
                    cb(*args)

        class _FinishOnlyWorker:
            def __init__(self):
                self.progress_changed = _Signal()
                self.execution_started = _Signal()
                self.execution_succeeded = _Signal()
                self.execution_partial = _Signal()
                self.execution_failed = _Signal()
                self.execution_cancelled = _Signal()
                self.execution_finished = _Signal()
                self.start_calls = 0

            def start(self) -> None:
                self.start_calls += 1

        worker = _FinishOnlyWorker()
        panel._build_execution_worker = lambda: worker
        panel.set_current_task_state(
            CurrentTaskState(
                document_label="thesis.docx",
                strategy_label="论文标准",
                ready=True,
                status_text="待执行",
            )
        )

        assert panel._execution_center._execute_button.isEnabled()

        panel._execution_center._execute_button.click()

        assert worker.start_calls == 1
        assert not panel._execution_center._execute_button.isEnabled()
        assert not panel._command_bar._run_button.isEnabled()

        worker.execution_finished.emit()

        assert panel._execution_center._execute_button.isEnabled()
        assert panel._command_bar._run_button.isEnabled()
    finally:
        panel.close()


def test_workbench_panel_build_execution_worker_returns_real_worker_when_cached_doc_path_available(
    tmp_path, monkeypatch
):
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        doc_path = tmp_path / "input.docx"
        doc_path.write_bytes(b"stub")
        bridge.document_loaded.emit(str(doc_path))

        worker = panel._build_execution_worker()
        assert worker is not None
        assert callable(getattr(worker, "start", None))
        assert callable(getattr(worker, "request_cancel", None))
        assert getattr(worker, "execution_started", None) is not None
        assert getattr(worker, "execution_finished", None) is not None
    finally:
        panel.close()


def test_workbench_panel_build_execution_worker_prompts_for_doc_path_when_missing(tmp_path, monkeypatch):
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        picked = tmp_path / "picked.docx"
        picked.write_bytes(b"stub")

        calls = {"open_calls": 0}

        def _fake_get_open_file_name(*args, **kwargs):
            calls["open_calls"] += 1
            return (str(picked), "Word Documents (*.docx)")

        import src.ui.panels.workbench.panel as panel_module

        monkeypatch.setattr(
            panel_module.QFileDialog,
            "getOpenFileName",
            staticmethod(_fake_get_open_file_name),
        )

        worker = panel._build_execution_worker()

        assert calls["open_calls"] == 1
        assert worker is not None
    finally:
        panel.close()


def test_workbench_panel_production_runner_uses_defaults_and_emits_normalized_payload(
    tmp_path, monkeypatch
):
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        doc_path = tmp_path / "input.docx"
        doc_path.write_bytes(b"stub")
        bridge.document_loaded.emit(str(doc_path))

        import src.ui.panels.workbench.panel as panel_module
        from src.pipeline.result import PipelineResult

        captured = {"template": None, "scene": None}

        class _DummyConfig:
            def is_module_enabled(self, module_name: str) -> bool:
                return True

        def _fake_resolve_config(template, scene, *args, **kwargs):
            captured["template"] = template
            captured["scene"] = scene
            return _DummyConfig()

        monkeypatch.setattr(panel_module, "resolve_config", _fake_resolve_config)
        monkeypatch.setattr(panel_module, "create_all_modules", lambda: ["m1"])
        monkeypatch.setattr(
            panel_module,
            "select_enabled_modules",
            lambda modules, is_enabled: (modules, {}),
        )

        pipeline_calls = {"doc_path": None, "output_suffix": None}

        class _FakePipeline:
            def __init__(
                self,
                *,
                modules,
                config,
                output_dir=None,
                output_suffix="_new",
                progress_callback=None,
                cancel_check=None,
            ):
                pipeline_calls["output_suffix"] = output_suffix
                self._progress_callback = progress_callback

            def execute(self, doc_path_raw: str):
                pipeline_calls["doc_path"] = doc_path_raw
                if self._progress_callback:
                    self._progress_callback(1, 1, "done")
                return PipelineResult(
                    success=True,
                    status="success",
                    output_paths={"final": str(tmp_path / "out.docx")},
                )

        monkeypatch.setattr(panel_module, "Pipeline", _FakePipeline)

        report_calls = []

        def _fake_write_json_report(*args, **kwargs):
            report_calls.append(("json", kwargs))

        def _fake_write_markdown_report(*args, **kwargs):
            report_calls.append(("md", kwargs))

        monkeypatch.setattr(panel_module, "write_json_report", _fake_write_json_report)
        monkeypatch.setattr(panel_module, "write_markdown_report", _fake_write_markdown_report)

        runner = panel_module._WorkbenchProductionRunner(
            doc_path=str(doc_path),
            template=None,
            scene=None,
        )
        payload = runner.run(lambda *_: None, lambda: False)

        assert isinstance(captured["template"], TemplateConfig)
        assert isinstance(captured["scene"], SceneWorkspace)
        assert pipeline_calls["output_suffix"] == "_formatted"
        assert pipeline_calls["doc_path"] == str(doc_path)

        assert payload["status"] == "success"
        assert payload["output_path"].endswith("out.docx")
        assert len(payload["report_paths"]) == 2
        assert payload["failed_count"] == 0
        assert payload["error_text"] == ""
        assert [kind for kind, _ in report_calls] == ["json", "md"]
    finally:
        panel.close()


def test_workbench_panel_production_worker_uses_thread_start_path_not_sync_run(
    tmp_path, monkeypatch
):
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        picked = tmp_path / "threaded.docx"
        picked.write_bytes(b"stub")

        import src.ui.panels.workbench.panel as panel_module

        def _fake_get_open_file_name(*args, **kwargs):
            return (str(picked), "Word Documents (*.docx)")

        monkeypatch.setattr(
            panel_module.QFileDialog,
            "getOpenFileName",
            staticmethod(_fake_get_open_file_name),
        )

        class _Signal:
            def __init__(self):
                self._callbacks = []

            def connect(self, callback):
                self._callbacks.append(callback)

            def emit(self, *args):
                for cb in list(self._callbacks):
                    cb(*args)

        thread_calls = {"start": 0}

        class _FakeThread:
            def __init__(self, *args, **kwargs):
                self.started = _Signal()
                self.finished = _Signal()
                self._running = False

            def start(self):
                thread_calls["start"] += 1
                self._running = True
                # Do not emit started, so worker.run is never invoked.

            def quit(self):
                self._running = False
                return

            def isRunning(self):
                return bool(self._running)

            def wait(self, timeout_ms=None):
                return True

            def deleteLater(self):
                return

        class _FakeExecutionWorker:
            def __init__(self, runner, parent=None):
                self._runner = runner
                self.progress_changed = _Signal()
                self.execution_started = _Signal()
                self.execution_succeeded = _Signal()
                self.execution_partial = _Signal()
                self.execution_failed = _Signal()
                self.execution_cancelled = _Signal()
                self.execution_finished = _Signal()
                self.run_calls = 0

            def moveToThread(self, thread):
                return

            def request_cancel(self):
                return

            def run(self):
                self.run_calls += 1

            def deleteLater(self):
                return

        monkeypatch.setattr(panel_module, "QThread", _FakeThread)
        monkeypatch.setattr(panel_module, "ExecutionWorker", _FakeExecutionWorker)

        panel._command_bar._run_button.click()

        assert thread_calls["start"] == 1
        assert getattr(panel._execution_worker, "_worker", None) is not None
        assert panel._execution_worker._worker.run_calls == 0
    finally:
        panel.close()


def test_workbench_panel_close_with_active_execution_handle_invokes_handle_shutdown():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        calls = []

        class _FakeHandle:
            def shutdown(self, timeout_ms=None):
                calls.append(timeout_ms)

        panel._execution_worker = _FakeHandle()

        panel.close()

        assert len(calls) >= 1

        # Avoid double-counting if test cleanup also closes the widget.
        panel._execution_worker = None
    finally:
        panel.close()


def test_threaded_execution_handle_shutdown_requests_cancel_quits_and_waits(monkeypatch):
    _app()
    import src.ui.panels.workbench.panel as panel_module

    class _Signal:
        def __init__(self):
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)

        def emit(self, *args):
            for cb in list(self._callbacks):
                cb(*args)

    calls = {"request_cancel": 0, "quit": 0, "wait": []}

    class _FakeThread:
        def __init__(self, *args, **kwargs):
            self.started = _Signal()
            self.finished = _Signal()
            self._running = True

        def isRunning(self):
            return bool(self._running)

        def quit(self):
            calls["quit"] += 1
            self._running = False

        def wait(self, timeout_ms=None):
            calls["wait"].append(timeout_ms)
            return True

        def deleteLater(self):
            return

    class _FakeExecutionWorker:
        def __init__(self, runner, parent=None):
            self.progress_changed = _Signal()
            self.execution_started = _Signal()
            self.execution_succeeded = _Signal()
            self.execution_partial = _Signal()
            self.execution_failed = _Signal()
            self.execution_cancelled = _Signal()
            self.execution_finished = _Signal()

        def moveToThread(self, thread):
            return

        def request_cancel(self):
            calls["request_cancel"] += 1

        def run(self):
            return

        def deleteLater(self):
            return

    monkeypatch.setattr(panel_module, "QThread", _FakeThread)

    handle = panel_module._ThreadedExecutionHandle(_FakeExecutionWorker(None))

    handle.shutdown(timeout_ms=25)

    assert calls["request_cancel"] == 1
    assert calls["quit"] == 1
    assert calls["wait"] == [25]


def test_threaded_execution_handle_wires_thread_finished_delete_later_cleanup(monkeypatch):
    _app()
    import src.ui.panels.workbench.panel as panel_module

    class _Signal:
        def __init__(self):
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)

        def emit(self, *args):
            for cb in list(self._callbacks):
                cb(*args)

    class _FakeThread:
        def __init__(self, *args, **kwargs):
            self.started = _Signal()
            self.finished = _Signal()

        def start(self):
            return

        def quit(self):
            return

        def wait(self, timeout_ms=None):
            return True

        def isRunning(self):
            return False

        def deleteLater(self):
            return

    class _FakeExecutionWorker:
        def __init__(self, runner, parent=None):
            self.progress_changed = _Signal()
            self.execution_started = _Signal()
            self.execution_succeeded = _Signal()
            self.execution_partial = _Signal()
            self.execution_failed = _Signal()
            self.execution_cancelled = _Signal()
            self.execution_finished = _Signal()

        def moveToThread(self, thread):
            return

        def request_cancel(self):
            return

        def run(self):
            return

        def deleteLater(self):
            return

    monkeypatch.setattr(panel_module, "QThread", _FakeThread)

    worker = _FakeExecutionWorker(None)
    handle = panel_module._ThreadedExecutionHandle(worker)
    thread = getattr(handle, "_thread", None)

    assert thread is not None
    finished_callbacks = list(getattr(thread.finished, "_callbacks", []))

    def _has_delete_later_for(obj) -> bool:
        for cb in finished_callbacks:
            if getattr(cb, "__name__", "") != "deleteLater":
                continue
            if getattr(cb, "__self__", None) is obj:
                return True
        return False

    assert _has_delete_later_for(worker)
    assert _has_delete_later_for(thread)
    assert _has_delete_later_for(handle)


def test_workbench_panel_file_picker_cancel_is_noop_and_does_not_surface_failure(monkeypatch):
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        import src.ui.panels.workbench.panel as panel_module

        def _fake_get_open_file_name(*args, **kwargs):
            return ("", "")

        monkeypatch.setattr(
            panel_module.QFileDialog,
            "getOpenFileName",
            staticmethod(_fake_get_open_file_name),
        )

        before_status = panel._execution_center._status_label.text()
        before_summary = panel._execution_center._summary_box.toPlainText()
        before_recent = panel._recent_run_panel._summary.text()

        panel._command_bar._run_button.click()

        assert panel._execution_worker is None
        assert panel._execution_center._status_label.text() == before_status
        assert panel._execution_center._summary_box.toPlainText() == before_summary
        assert panel._recent_run_panel._summary.text() == before_recent
        assert panel._command_bar._run_button.isEnabled()
        assert panel._execution_center._execute_button.isEnabled()
    finally:
        panel.close()


def test_workbench_production_runner_failed_result_preserves_failed_count(tmp_path, monkeypatch):
    _app()
    doc_path = tmp_path / "failed.docx"
    doc_path.write_bytes(b"stub")

    import src.ui.panels.workbench.panel as panel_module
    from src.pipeline.result import PipelineResult

    class _DummyConfig:
        def is_module_enabled(self, module_name: str) -> bool:
            return True

    monkeypatch.setattr(panel_module, "resolve_config", lambda *a, **k: _DummyConfig())
    monkeypatch.setattr(panel_module, "create_all_modules", lambda: ["m1", "m2"])
    monkeypatch.setattr(
        panel_module,
        "select_enabled_modules",
        lambda modules, is_enabled: (modules, {}),
    )

    class _FakePipeline:
        def __init__(self, *args, **kwargs):
            pass

        def execute(self, doc_path_raw: str):
            assert doc_path_raw == str(doc_path)
            return PipelineResult(
                success=False,
                status="failed",
                failed_items=[{"rule_name": "a"}, {"rule_name": "b"}],
                error="boom",
            )

    monkeypatch.setattr(panel_module, "Pipeline", _FakePipeline)

    runner = panel_module._WorkbenchProductionRunner(
        doc_path=str(doc_path),
        template=TemplateConfig(),
        scene=SceneWorkspace(),
    )
    payload = runner.run(lambda *_: None, lambda: False)

    assert payload["status"] == "failed"
    assert payload["failed_count"] == 2
    assert payload["error_text"] == "boom"


def test_workbench_panel_shutdown_active_execution_returns_false_when_worker_still_running():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        class _FakeThread:
            def __init__(self):
                self.quit_calls = 0
                self.wait_calls = []

            def isRunning(self) -> bool:
                return True

            def quit(self) -> None:
                self.quit_calls += 1

            def wait(self, timeout_ms: int | None = None) -> bool:
                self.wait_calls.append(timeout_ms)
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
                self._thread.quit()
                self._thread.wait(timeout_ms)

        handle = _FakeExecutionHandle()
        panel._execution_worker = handle

        assert panel.shutdown_active_execution(timeout_ms=5) is False
        assert handle.cancel_requests == 1
        assert handle.shutdown_calls == [5]
        assert handle._thread.quit_calls >= 1
        assert handle._thread.wait_calls == [5]
    finally:
        panel._execution_worker = None
        panel.close()


def test_workbench_panel_close_ignored_when_active_execution_shutdown_fails():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        class _FakeThread:
            def isRunning(self) -> bool:
                return True

            def quit(self) -> None:
                return

            def wait(self, timeout_ms: int | None = None) -> bool:
                return False

        class _FakeExecutionHandle:
            def __init__(self):
                self._thread = _FakeThread()

            def request_cancel(self) -> None:
                return

            def shutdown(self, timeout_ms: int | None = 1000) -> None:
                return

        panel._execution_worker = _FakeExecutionHandle()

        assert panel.close() is False

        panel._execution_worker = None
        assert panel.close() is True
    finally:
        panel._execution_worker = None
        panel.close()
