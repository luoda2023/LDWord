import inspect
import sys
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QSize, QScrollArea, QVBoxLayout, QWidget, Qt
from src.config.material_context import MaterialExecutionContext
from src.config.materials import AssetItem
from src.config.scene import SceneWorkspace
from src.shared.ui.detail_pane_controller import DetailPaneController
from src.shared.ui.form_row import FormRow
from src.shared.ui.template_form_layout import TemplateFormStack
from src.ui.bridge import PanelBridge
from src.ui.panel_registry import PANEL_SPECS
from src.ui.panels.workbench.feature_detail_panes import (
    CitationDetailPane,
    CleanupDetailPane,
    ContentDataDetailPane,
    FormulaDetailPane,
    TableChartDetailPane,
)
from src.ui.panels.workbench.scene_presets import create_bidding_scene
from src.ui.panels.workbench.state import ExecutionResultState
from src.ui.adapters.workbench_execution_adapter import WorkbenchIssueItem
import src.ui.panels.workbench.panel_v2 as panel_v2_module
from src.ui.panels.workbench.panel_v2 import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


def _panel_index(panel_id: str) -> int:
    for index, spec in enumerate(PANEL_SPECS):
        if spec.id == panel_id:
            return index
    return -1


class _SizedDetail(QWidget):
    def __init__(self, height: int, parent=None):
        super().__init__(parent)
        self._height = int(height)

    def sizeHint(self):  # noqa: N802
        return QSize(320, self._height)


class _WidthSensitiveDetail(QWidget):
    def __init__(
        self,
        *,
        width_threshold: int,
        narrow_height: int,
        wide_height: int,
        parent=None,
    ):
        super().__init__(parent)
        self._width_threshold = int(width_threshold)
        self._narrow_height = int(narrow_height)
        self._wide_height = int(wide_height)

    def sizeHint(self):  # noqa: N802
        height = (
            self._wide_height
            if self.width() >= self._width_threshold
            else self._narrow_height
        )
        return QSize(320, height)


class _ExpandableDetail(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._base = QWidget(self)
        self._base.setMinimumHeight(80)
        layout.addWidget(self._base)
        self._extra = QWidget(self)
        self._extra.setMinimumHeight(560)
        self._extra.hide()
        layout.addWidget(self._extra)

    def expand(self) -> None:
        self._extra.show()
        self.updateGeometry()


def test_workbench_panel_uses_detail_controller_for_detail_switching():
    panel_source = inspect.getsource(WorkbenchPanel)
    module_source = (ROOT / "src/ui/panels/workbench/panel_v2.py").read_text(encoding="utf-8")

    assert "from src.shared.ui import DetailPaneController, MasterDetailShell" in module_source
    assert "self._details = DetailPaneController(" in panel_source
    assert "self._details.register_details(detail_map)" in panel_source
    assert "self._details.show_detail(card_id)" in panel_source


def test_detail_controller_owns_registration_and_visible_pane_switching():
    controller_source = inspect.getsource(DetailPaneController)

    assert "def register_details" in controller_source
    assert "def show_detail" in controller_source
    assert "self._detail_layout.removeWidget" in controller_source
    assert "self._detail_scroll.verticalScrollBar().setValue(0)" in controller_source
    assert "ScrollableDetailGeometrySync(" in controller_source


def test_workbench_panel_keeps_current_detail_alias_in_sync():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel._current_detail is panel._details.current_detail

        panel._nav_rail.select_card("config_management")

        assert panel._current_detail is panel._config_management_detail
        assert panel._current_detail is panel._details.current_detail
    finally:
        panel.close()


def test_workbench_panel_routes_issue_repair_targets_to_existing_surfaces(monkeypatch):
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    navigated: list[int] = []
    intents: list[object] = []
    opened_artifacts: list[tuple[str, str]] = []
    bridge.navigate_to_panel.connect(navigated.append)
    bridge.navigate_to_intent.connect(intents.append)
    monkeypatch.setattr(
        panel_v2_module.recent_run_panel_module,
        "_open_artifact_file",
        lambda path, *, fragment="": opened_artifacts.append((path, fragment)) or True,
    )
    try:
        panel._open_issue_repair_target("field", "company_name")

        assert bridge.current_material_repair_target() == ("field", "company_name")
        assert navigated[-1] == _panel_index("assets")
        assert intents[-1]["panel_id"] == "assets"

        panel._open_issue_repair_target(
            "profile_field",
            json.dumps(
                {
                    "profile_id": "missing",
                    "profile_name": "Missing Employee",
                    "target_key": "employee_id",
                }
            ),
        )

        assert bridge.current_material_profile_repair_target() == (
            "missing",
            "Missing Employee",
            "field",
            "employee_id",
        )
        assert navigated[-1] == _panel_index("assets")
        assert intents[-1]["panel_id"] == "assets"

        question_target = json.dumps(
            {
                "role": "question_figure",
                "item_id": "question_figure_2",
                "question_index": "2",
                "path": "missing_question_2.png",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        panel._open_issue_repair_target(
            "profile_question_figure_item",
            json.dumps(
                {
                    "profile_id": "exam_a",
                    "profile_name": "Exam A",
                    "target_key": question_target,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )

        assert bridge.current_material_profile_repair_target() == (
            "exam_a",
            "Exam A",
            "question_figure_item",
            question_target,
        )
        assert navigated[-1] == _panel_index("assets")
        assert intents[-1]["panel_id"] == "assets"

        replacement_candidate = {
            "confirmation_status": "ready",
            "confirmation_apply_supported": True,
            "replacement_source_path": "C:/exam/question_2_expected.png",
        }
        panel._open_issue_repair_target(
            "profile_question_figure_repair_candidate",
            json.dumps(
                {
                    "profile_id": "exam_a",
                    "profile_name": "Exam A",
                    "target_key": question_target,
                    "candidate": replacement_candidate,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )

        candidate_profile_id, candidate_profile_name, candidate = (
            bridge.current_material_profile_repair_candidate()
        )
        assert candidate_profile_id == "exam_a"
        assert candidate_profile_name == "Exam A"
        assert candidate["repair_target_key"] == question_target
        assert candidate["replacement_source_path"] == "C:/exam/question_2_expected.png"
        assert navigated[-1] == _panel_index("assets")
        assert intents[-1]["panel_id"] == "assets"

        panel._open_issue_repair_target("template_style_field", "body.font_name")

        assert navigated[-1] == _panel_index("template")
        assert intents[-1]["panel_id"] == "template"
        assert intents[-1]["card_id"] == "tpl_style"

        conflict_candidate = {
            "queue_id": "repair:question_figure:exam_a:q2:conflict-a",
            "confirmation_status": "ready",
            "confirmation_action": "confirm_question_figure_replacement",
            "confirmation_apply_supported": True,
            "replacement_source_path": "C:/exam/question_2_expected_a.png",
            "conflict_resolution_status": "selected",
            "conflict_selected_queue_id": (
                "repair:question_figure:exam_a:q2:conflict-a"
            ),
            "conflict_resolution_rejected_queue_ids": [
                "repair:question_figure:exam_a:q2:conflict-b"
            ],
        }
        panel._open_issue_repair_target(
            "profile_question_figure_repair_conflict_selection",
            json.dumps(
                {
                    "profile_id": "exam_a",
                    "profile_name": "Exam A",
                    "target_key": question_target,
                    "candidate": conflict_candidate,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )

        conflict_profile_id, conflict_profile_name, conflict_payload = (
            bridge.current_material_profile_repair_candidate()
        )
        assert conflict_profile_id == "exam_a"
        assert conflict_profile_name == "Exam A"
        assert conflict_payload["repair_target_key"] == question_target
        assert conflict_payload["conflict_resolution_status"] == "selected"
        assert conflict_payload["replacement_source_path"] == (
            "C:/exam/question_2_expected_a.png"
        )
        assert navigated[-1] == _panel_index("assets")

        panel._nav_rail.select_card("config_management")
        assert panel._current_detail is panel._config_management_detail
        before_count = len(navigated)
        panel._open_issue_repair_target(
            "question_figure_batch_apply_transaction_task_summary",
            json.dumps(
                {
                    "status": "active",
                    "next_action": "review_active_transaction",
                    "report_path": (
                        "C:/tmp/question_figure_batch_apply_transaction_manifest.md"
                    ),
                    "fragment": (
                        "question-figure-batch-apply-transaction-task-summary"
                    ),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )

        assert len(navigated) == before_count
        assert panel._current_detail is panel._quick_execution_detail
        assert opened_artifacts[-1] == (
            "C:/tmp/question_figure_batch_apply_transaction_manifest.md",
            "question-figure-batch-apply-transaction-task-summary",
        )

        panel._open_issue_repair_target("output_target", "review")

        assert navigated[-1] == _panel_index("scene")
        assert intents[-1]["panel_id"] == "scene"
        assert intents[-1]["card_id"] == "scn_rules"

        panel._open_issue_repair_target("coverage_boundary", "exam_education")

        assert navigated[-1] == _panel_index("scene")
        assert intents[-1]["panel_id"] == "scene"
        assert intents[-1]["card_id"] == "scn_overview"

        before_count = len(navigated)
        panel._open_issue_repair_target("control_contract", "body.special_indent")

        assert len(navigated) == before_count + 1
        assert navigated[-1] == _panel_index("scene")
        assert intents[-1]["card_id"] == "scn_cleanup"

        before_count = len(navigated)
        panel._open_issue_repair_target("parameter_ownership", "registry")

        assert len(navigated) == before_count + 1
        assert navigated[-1] == _panel_index("scene")
        assert intents[-1]["card_id"] == "scn_overview"

        before_count = len(navigated)
        panel._open_issue_repair_target("sample_fixture", "contract_delivery")

        assert len(navigated) == before_count + 1
        assert navigated[-1] == _panel_index("scene")
        assert intents[-1]["card_id"] == "scn_overview"

        before_count = len(navigated)
        panel._open_issue_repair_target(
            "row_height",
            "form_batch_documents.table.row_height_pt",
        )

        assert len(navigated) == before_count + 1
        assert navigated[-1] == _panel_index("scene")
        assert intents[-1]["card_id"] == "scn_cleanup"

        before_count = len(navigated)
        panel._open_issue_repair_target("content_controls", "w:sdt")

        assert len(navigated) == before_count + 1
        assert navigated[-1] == _panel_index("scene")
        assert intents[-1]["card_id"] == "scn_cleanup"
    finally:
        panel.close()


def test_workbench_panel_round_trips_active_issue_from_repair_navigation():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    intents: list[object] = []
    bridge.navigate_to_intent.connect(intents.append)
    try:
        detail = panel._quick_execution_detail
        detail._apply_scene(create_bidding_scene())
        detail.set_document_path("C:/docs/bid.docx")
        detail.set_issue_queue_filter("material_asset")

        assert detail.current_filtered_issue_items()[0].issue_id == (
            "material.assets.missing"
        )

        detail._issue_action_btn.click()

        assert intents[-1]["panel_id"] == "assets"
        assert intents[-1]["active_issue_id"] == "material.assets.missing"
        assert intents[-1]["payload"]["issue_item_id"] == "material.assets.missing"

        detail.set_issue_queue_filter("material_field")
        assert detail.current_filtered_issue_items()[0].issue_id == (
            "material.fields.missing"
        )

        panel.handle_navigation_intent(
            {
                "panel_id": "workbench",
                "card_id": "quick_execute",
                "active_issue_id": "material.assets.missing",
                "payload": {"issue_item_id": "material.assets.missing"},
            }
        )

        assert panel._nav_rail.selected_card_id() == "quick_execute"
        assert detail.current_active_issue_id() == "material.assets.missing"
        assert detail.current_filtered_issue_items()[0].issue_id == (
            "material.assets.missing"
        )
        assert detail._issue_list.currentItem().data(Qt.UserRole) == (
            "material.assets.missing"
        )
    finally:
        panel.close()


def test_workbench_panel_auto_rechecks_config_issue_on_scene_dirty():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        detail = panel._quick_execution_detail
        detail._apply_scene(create_bidding_scene())
        detail.set_document_path("C:/docs/bid.docx")
        detail.set_issue_queue_filter("material_asset")

        assert detail.current_filtered_issue_items()[0].issue_id == (
            "material.assets.missing"
        )

        detail._material_context = MaterialExecutionContext(
            entity_data={
                "company_name": "测试公司",
                "project_name": "示例项目",
                "legal_person": "张三",
            },
            asset_items=[
                AssetItem(role="logo", path="C:/assets/logo.png"),
                AssetItem(role="seal", path="C:/assets/seal.png"),
            ],
        )

        bridge.mark_scene_dirty()

        assert detail.current_issue_items() == []
        assert detail._issue_panel.isHidden() is True
    finally:
        panel.close()


def test_workbench_panel_does_not_auto_clear_execution_result_issues_on_dirty():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        detail = panel._quick_execution_detail
        result_issue = WorkbenchIssueItem(
            issue_id="execution.template.warning",
            category="batch_issue",
            severity="warning",
            title="执行结果问题",
            summary="模板字段仍需确认",
            repair_target_type="template_style_field",
            repair_target_key="body.font_name",
            owner="template",
        )
        detail.set_execution_result(
            ExecutionResultState(
                status="partial_success",
                summary="部分完成",
                issue_items=[result_issue],
            )
        )

        bridge.mark_template_dirty()

        assert [item.issue_id for item in detail.current_issue_items()] == [
            "execution.template.warning"
        ]
        assert detail._issue_queue_source == "execution_result"
    finally:
        panel.close()


def test_workbench_panel_applies_external_scene_to_quick_execution_detail():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        scene = SceneWorkspace(scene_id="external_sync", template_id="default")
        scene.strict_mode = False
        scene.format_scope.sections = {
            "body": True,
            "references": False,
            "appendix": True,
        }

        panel.on_scene_changed(scene)

        detail = panel._quick_execution_detail
        assert detail.current_scene() is scene
        assert detail.current_scene_id() == "external_sync"
        assert detail.current_strategy() == "preserve"
        assert not hasattr(detail, "_zone_checks")
    finally:
        panel.close()


def test_workbench_quick_execution_does_not_expose_zone_toggles(monkeypatch):
    app = _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        detail = panel._quick_execution_detail
        app.processEvents()

        apply_calls = []
        style_source_calls = []
        recheck_calls = []

        monkeypatch.setattr(
            detail,
            "_apply_scene",
            lambda scene: apply_calls.append(scene),
        )
        monkeypatch.setattr(
            detail,
            "_sync_style_prereview_state",
            lambda: style_source_calls.append(True),
        )
        monkeypatch.setattr(
            detail,
            "recheck_current_context",
            lambda *args, **kwargs: recheck_calls.append((args, kwargs)),
        )

        assert not hasattr(detail, "_zone_checks")
        app.processEvents()

        assert bridge.is_scene_dirty() is False
        assert apply_calls == []
        assert style_source_calls == []
        assert recheck_calls == []
    finally:
        panel.close()


def test_workbench_quick_feature_toggle_does_not_reapply_scene(monkeypatch):
    app = _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        detail = panel._quick_execution_detail
        app.processEvents()

        apply_calls = []
        recheck_calls = []
        monkeypatch.setattr(
            detail,
            "_apply_scene",
            lambda scene: apply_calls.append(scene),
        )
        monkeypatch.setattr(
            detail,
            "recheck_current_context",
            lambda *args, **kwargs: recheck_calls.append((args, kwargs)),
        )

        before = detail.is_feature_enabled("table_chart")
        detail.set_feature_enabled("table_chart", not before)
        app.processEvents()

        assert detail.is_feature_enabled("table_chart") is (not before)
        assert bridge.is_scene_dirty() is True
        assert apply_calls == []
        assert recheck_calls == []
    finally:
        panel.close()


def test_workbench_suppressed_scene_dirty_does_not_recheck(monkeypatch):
    app = _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        detail = panel._quick_execution_detail
        recheck_calls = []
        monkeypatch.setattr(
            detail,
            "recheck_current_context",
            lambda *args, **kwargs: recheck_calls.append((args, kwargs)),
        )

        bridge.mark_scene_dirty(recheck=False)
        app.processEvents()

        assert bridge.is_scene_dirty() is True
        assert recheck_calls == []

        bridge.clear_scene_dirty()
        bridge.mark_scene_dirty()
        app.processEvents()

        assert len(recheck_calls) == 1
    finally:
        panel.close()


def test_detail_controller_reparents_and_hides_registered_details():
    app = _app()

    host = QWidget()
    scroll = QScrollArea(host)
    container = QWidget(scroll)
    layout = QVBoxLayout(container)
    scroll.setWidget(container)

    detail_a = QWidget(host)
    detail_b = QWidget(host)

    controller = DetailPaneController(container, layout, scroll)
    controller.register_details({"a": detail_a, "b": detail_b})

    try:
        assert controller.current_detail is None
        assert detail_a.parent() is container
        assert detail_b.parent() is container
        assert detail_a.isHidden() is True
        assert detail_b.isHidden() is True

        controller.show_detail("a")
        app.processEvents()

        assert controller.current_detail is detail_a
        assert detail_a.parent() is container
        assert detail_b.parent() is container
        assert detail_a.isHidden() is False
        assert detail_b.isHidden() is True
    finally:
        host.close()


def test_detail_controller_syncs_scroll_content_size_on_same_frame_switch():
    app = _app()

    host = QWidget()
    scroll = QScrollArea(host)
    scroll.setWidgetResizable(True)
    scroll.setGeometry(0, 0, 400, 240)
    container = QWidget(scroll)
    layout = QVBoxLayout(container)
    scroll.setWidget(container)

    short_detail = _SizedDetail(80)
    tall_detail = _SizedDetail(720)
    controller = DetailPaneController(container, layout, scroll)
    controller.register_details({"short": short_detail, "tall": tall_detail})

    try:
        host.resize(420, 260)
        host.show()
        app.processEvents()

        controller.show_detail("tall")
        tall_height = container.height()
        assert tall_height == max(scroll.viewport().height(), container.sizeHint().height())
        assert tall_height > scroll.viewport().height()

        controller.show_detail("short")
        assert container.height() == max(scroll.viewport().height(), container.sizeHint().height())
        assert container.height() < tall_height
    finally:
        host.close()
        app.processEvents()


def test_detail_controller_remeasures_when_current_detail_is_selected_again():
    app = _app()

    host = QWidget()
    scroll = QScrollArea(host)
    scroll.setWidgetResizable(True)
    scroll.setGeometry(0, 0, 400, 240)
    container = QWidget(scroll)
    layout = QVBoxLayout(container)
    scroll.setWidget(container)

    detail = _SizedDetail(80)
    controller = DetailPaneController(container, layout, scroll)
    controller.register_details({"detail": detail})

    try:
        host.resize(420, 260)
        host.show()
        app.processEvents()

        controller.show_detail("detail")
        collapsed_height = container.minimumHeight()

        detail._height = 720
        controller.show_detail("detail")

        assert container.minimumHeight() > collapsed_height + 400
        assert container.height() == max(scroll.viewport().height(), container.sizeHint().height())
    finally:
        host.close()
        app.processEvents()


def test_detail_controller_remeasures_after_width_sensitive_detail_layout():
    app = _app()

    host = QWidget()
    scroll = QScrollArea(host)
    scroll.setWidgetResizable(True)
    scroll.setGeometry(0, 0, 760, 360)
    container = QWidget(scroll)
    layout = QVBoxLayout(container)
    scroll.setWidget(container)

    responsive_detail = _WidthSensitiveDetail(
        width_threshold=680,
        narrow_height=720,
        wide_height=260,
    )
    controller = DetailPaneController(container, layout, scroll)
    controller.register_details({"responsive": responsive_detail})

    try:
        host.resize(780, 380)
        host.show()
        app.processEvents()

        controller.show_detail("responsive")

        assert responsive_detail.width() >= responsive_detail._width_threshold
        assert responsive_detail.sizeHint().height() == responsive_detail._wide_height
        assert container.minimumHeight() == container.sizeHint().height()
        assert container.height() == max(
            scroll.viewport().height(),
            container.sizeHint().height(),
        )
        assert container.minimumHeight() < responsive_detail._narrow_height
    finally:
        host.close()
        app.processEvents()


def test_detail_controller_remeasures_after_visible_detail_expands():
    app = _app()

    host = QWidget()
    scroll = QScrollArea(host)
    scroll.setWidgetResizable(True)
    scroll.setGeometry(0, 0, 400, 240)
    container = QWidget(scroll)
    layout = QVBoxLayout(container)
    scroll.setWidget(container)

    detail = _ExpandableDetail()
    controller = DetailPaneController(container, layout, scroll)
    controller.register_details({"dynamic": detail})

    try:
        host.resize(420, 260)
        host.show()
        app.processEvents()

        controller.show_detail("dynamic")
        app.processEvents()
        collapsed_height = container.minimumHeight()

        detail.expand()
        for _ in range(4):
            app.processEvents()

        assert container.minimumHeight() > collapsed_height + 400
        assert container.minimumHeight() == container.sizeHint().height()
        assert container.height() == max(scroll.viewport().height(), container.sizeHint().height())
    finally:
        host.close()
        app.processEvents()


def test_workbench_panel_hides_unselected_details_inside_detail_container():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel._current_detail is panel._quick_execution_detail

        for card_id, detail in panel._detail_map.items():
            assert detail.parent() is panel._detail_container
            if card_id == "quick_execute":
                assert detail.isHidden() is False
            else:
                assert detail.isHidden() is True
    finally:
        panel.close()


def test_workbench_panel_uses_semantic_capability_detail_panes():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert isinstance(panel._table_chart_detail, TableChartDetailPane)
        assert hasattr(panel, "_page_elements_detail") is False
        assert isinstance(panel._formula_detail, FormulaDetailPane)
        assert isinstance(panel._citation_detail, CitationDetailPane)
        assert isinstance(panel._cleanup_detail, CleanupDetailPane)
        assert isinstance(panel._content_fill_detail, ContentDataDetailPane)
        assert panel._heading_numbering_detail is panel._table_chart_detail
        assert panel._quick_fill_detail is panel._content_fill_detail
    finally:
        panel.close()


def test_workbench_feature_detail_panes_use_shared_template_form_baseline():
    source = (ROOT / "src/ui/panels/workbench/feature_detail_panes.py").read_text(encoding="utf-8")

    assert "from src.shared.ui.form_row import FormRow" not in source
    assert "FormRow(" not in source
    assert "TemplateFormStack" in source
    assert "template_form_row(" in source
    assert '= Card("' not in source


def test_workbench_feature_detail_rows_share_card_label_baseline():
    app = _app()
    detail = TableChartDetailPane()

    try:
        detail.resize(1000, 700)
        detail.show()
        app.processEvents()

        assert detail.findChildren(TemplateFormStack)

        row_map = {row.label_text: row for row in detail.findChildren(FormRow)}
        for labels in (
            ("题注处理", "题注间距"),
            ("图表居中", "续表延续题注"),
        ):
            label_widths = {row_map[label].label_width for label in labels}
            assert len(label_widths) == 1
            for label in labels:
                row = row_map[label]
                assert row._label.alignment() & Qt.AlignLeft
                assert not (row._label.alignment() & Qt.AlignRight)
                assert row.layout().spacing() == 4
    finally:
        detail.close()
        app.processEvents()
