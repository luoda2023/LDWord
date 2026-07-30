from src.config.entity import EntityArchive, EntityProfile
from src.config.material_batch import MaterialBatchSelection
from src.config.scene import SceneWorkspace
from src.qt_api import QApplication
from src.shared.ui import ThemedRadioButton
from src.shared.ui.styled_combo_box import StyledComboBox
from src.ui.bridge import PanelBridge
from src.ui.panels.assets_panel import AssetsPanel
from src.ui.panels.workbench.batch_generation_detail import BatchGenerationDetail
from src.ui.panels.workbench.batch_generation_source_area import (
    BatchGenerationSourceArea,
)
from src.ui.panels.workbench.panel_v2 import WorkbenchPanel
from src.ui.panels.workbench.quick_execution_detail import QuickExecutionDetail
from src.ui.panels.workbench.state import ExecutionProgressState, ExecutionResultState


def _app():
    return QApplication.instance() or QApplication([])


def _official_selection() -> MaterialBatchSelection:
    return MaterialBatchSelection(
        mode_id="official",
        scene_id="official",
        archive=EntityArchive(
            archive_id="notice_batch",
            archive_name="通知批次",
            profiles=[
                EntityProfile(profile_id="row_1", profile_name="通知 A"),
                EntityProfile(profile_id="row_2", profile_name="通知 B"),
            ],
        ),
        profile_ids=["row_1", "row_2"],
        output_dir_template="{profile_name}",
        source_kind="official_document_table",
        source_path="C:/docs/official_batch.csv",
    )


def test_batch_generation_detail_owns_complete_batch_actions():
    app = _app()
    detail = BatchGenerationDetail()
    execute_requests = []
    retry_requests = []
    try:
        detail.execute_requested.connect(lambda: execute_requests.append(True))
        detail.retry_requested.connect(lambda: retry_requests.append(True))
        detail.set_work_mode("official")
        detail.set_scene_context(
            SceneWorkspace(scene_id="official", mode_id="official")
        )
        detail.set_strategy_context(
            plan_label="公文通知方案",
            template_label="通知模板",
        )
        detail.set_material_batch_selection(_official_selection())
        app.processEvents()

        assert detail._execute_btn.text() == "批量生成 2 份"
        assert detail._execute_btn.isEnabled()
        assert "通知 A" in detail.source_hint_text()
        assert "公文通知方案" in detail.binding_summary()
        assert "official_batch.csv" in detail.navigation_snapshot()["subtitle"]

        detail._execute_btn.click()
        assert execute_requests == [True]

        detail.set_execution_result(
            ExecutionResultState(
                status="partial_success",
                summary="1 份成功，1 份失败",
                batch_isolation={
                    "history_run_id": "run_1",
                    "attempt_number": 1,
                    "retry_eligible_profile_ids": ["row_2"],
                },
                batch_isolation_summary="批次隔离完成",
            )
        )
        app.processEvents()

        assert detail._retry_btn.isHidden() is False
        assert detail._retry_btn.text() == "重试失败项 1 份"
        assert detail.failed_batch_profile_ids() == ["row_2"]
        assert detail.last_batch_run_id() == "run_1"
        assert detail.next_batch_attempt_number() == 2
        detail._retry_btn.click()
        assert retry_requests == [True]
    finally:
        detail.close()


def test_batch_generation_detail_blocks_missing_profile_material():
    app = _app()
    detail = BatchGenerationDetail()
    try:
        scene = SceneWorkspace(scene_id="official", mode_id="official")
        scene.input_source_profile.failure_policy = "block"
        scene.input_source_profile.required_material_fields = ["title"]
        detail.set_work_mode("official")
        detail.set_scene_context(scene)
        selection = _official_selection()
        selection.profile_ids = ["row_1"]
        detail.set_material_batch_selection(selection)
        app.processEvents()

        assert detail.current_batch_execution_gate_decision().state == "blocked"
        assert detail.can_start_execution() is False
        assert detail._execute_btn.isEnabled() is False
        assert "通知 A" in detail._execute_btn.toolTip()
    finally:
        detail.close()


def test_batch_generation_uses_quick_execution_visual_grammar():
    app = _app()
    quick = QuickExecutionDetail()
    batch = BatchGenerationDetail()
    try:
        quick.resize(1200, 900)
        batch.resize(1200, 900)
        quick.show()
        batch.show()
        app.processEvents()

        assert isinstance(batch._source_area, BatchGenerationSourceArea)
        assert batch._source_area.height() == quick._drop_area.height()
        assert isinstance(batch._scene_combo, StyledComboBox)
        assert isinstance(batch._template_combo, StyledComboBox)
        assert isinstance(batch._output_default_radio, ThemedRadioButton)
        assert isinstance(batch._output_custom_radio, ThemedRadioButton)
        assert batch._output_default_radio.isChecked() is True
        assert batch._exec_status_area.minimumHeight() == batch._execute_btn.minimumHeight()
        assert batch._exec_status_area.maximumHeight() == batch._execute_btn.maximumHeight()
        assert batch._layout.spacing() == quick._layout.spacing()
        assert batch._binding_card.__class__ is quick._scene_card.__class__
        assert batch._output_card.__class__ is quick._output_card.__class__
        assert batch._execution_card.__class__ is quick._execution_card.__class__
        # The two pages share one control/card grammar, but their natural
        # heights must remain content-driven. Quick execution owns an extra
        # live material-preview card, so exact total-height equality would
        # require a meaningless spacer or duplicate content on the batch page.
        assert batch.sizeHint().height() < quick.sizeHint().height()
        assert not hasattr(batch, "_prepare_btn")
        assert not hasattr(batch._source_area, "_prepare_button")
        assert batch._scene_combo.width() == batch._template_combo.width()
        assert not hasattr(batch, "_title")

        batch._output_custom_radio.setChecked(True)
        app.processEvents()
        assert batch._output_browse_btn.isVisible() is True
    finally:
        quick.close()
        batch.close()


def test_batch_cards_remain_ordered_after_live_batch_selection():
    app = _app()
    detail = BatchGenerationDetail()
    try:
        detail.resize(1200, 900)
        detail.show()
        detail.set_work_mode("official")
        detail.set_scene_context(
            SceneWorkspace(scene_id="official", mode_id="official")
        )
        detail.set_material_batch_selection(_official_selection())
        detail._layout.activate()
        app.processEvents()

        cards = (
            detail._source_area,
            detail._binding_card,
            detail._output_card,
            detail._execution_card,
        )
        assert all(card.isVisible() for card in cards)
        for previous, following in zip(cards, cards[1:]):
            assert previous.geometry().bottom() < following.geometry().top()
    finally:
        detail.close()


def test_batch_source_document_can_be_selected_on_its_own_page():
    _app()
    detail = BatchGenerationDetail()
    selected = []
    try:
        detail.source_document_selected.connect(selected.append)
        detail._on_source_document_selected("C:/docs/source.docx")

        assert selected == ["C:/docs/source.docx"]
        assert detail._source_document_path == "C:/docs/source.docx"
        assert "快速执行" not in "\n".join(detail.execution_blocking_reasons())
    finally:
        detail.close()


def test_batch_empty_source_is_read_only_and_has_no_prepare_action():
    _app()
    detail = BatchGenerationDetail()
    try:
        assert detail.source_title_text() == "尚未选择批次资料"
        assert "本页仅负责生成" in detail.source_hint_text()
        assert not hasattr(detail, "prepare_requested")
        assert not hasattr(detail._source_area, "prepare_requested")
        assert not hasattr(detail._source_area, "prepare_button")
        assert hasattr(detail._source_area, "document_button")
    finally:
        detail.close()


def test_batch_source_document_is_published_to_shared_workbench_state(tmp_path):
    _app()
    source = tmp_path / "source.docx"
    source.write_bytes(b"placeholder")
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        panel._batch_generation_detail.source_document_selected.emit(str(source))

        expected = str(source.resolve())
        assert bridge.current_document_path() == expected
        assert panel._quick_execution_detail.document_path() == expected
        assert panel._batch_generation_detail._source_document_path == expected
    finally:
        panel.close()


def test_batch_execution_feedback_matches_quick_execution_state_rhythm():
    app = _app()
    detail = BatchGenerationDetail()
    cancel_requests = []
    try:
        detail.set_work_mode("official")
        detail.set_scene_context(
            SceneWorkspace(scene_id="official", mode_id="official")
        )
        detail.set_material_batch_selection(_official_selection())
        detail.cancel_requested.connect(lambda: cancel_requests.append(True))
        detail.show()

        detail.set_execution_progress(
            ExecutionProgressState(
                stage_text="生成文档",
                current_step=1,
                total_steps=2,
                percent=50,
            )
        )
        app.processEvents()

        assert detail._exec_bar.isVisible() is True
        assert detail._exec_bar.value() == 50
        assert detail._cancel_btn.isVisible() is True
        assert detail._execute_btn.isEnabled() is False

        detail._cancel_btn.click()
        detail._cancel_btn.click()
        assert cancel_requests == [True]
        assert detail._exec_status_label.text() == "正在取消，请稍候…"

        detail.set_execution_result(
            ExecutionResultState(
                status="cancelled",
                summary="用户取消",
            )
        )
        app.processEvents()

        assert detail._exec_bar.isHidden() is True
        assert detail._cancel_btn.isHidden() is True
        assert detail._exec_status_label.text() == "已取消"
    finally:
        detail.close()


def test_batch_generation_is_fixed_workbench_secondary_function():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert tuple(panel._navigation_cards)[:2] == (
            "quick_execute",
            "batch_generate",
        )
        assert panel.CARD_DEFINITIONS["batch_generate"] == ("批量生成", "layers")
        assert panel._detail_map["batch_generate"] is panel._batch_generation_detail
    finally:
        panel.close()


def test_assets_navigation_intent_opens_batch_preparation_surface():
    _app()
    panel = AssetsPanel(PanelBridge())
    try:
        panel.handle_navigation_intent(
            {
                "panel_id": "assets",
                "card_id": "batch",
                "return_panel_id": "workbench",
                "return_card_id": "batch_generate",
                "payload": {"section_id": "batch"},
            }
        )

        assert panel._active_section_id == "batch"
        assert panel._detail_stack.currentWidget() is panel._section_pages["batch"]
        assert panel._return_navigation_intent is not None
    finally:
        panel.close()


def test_assets_batch_confirmation_returns_to_workbench_batch_page():
    _app()
    bridge = PanelBridge()
    intents = []
    bridge.navigate_to_intent.connect(intents.append)
    panel = AssetsPanel(bridge)
    try:
        panel._apply_current_profile = lambda: True

        assert panel._open_batch_generation() is True
        assert intents == [
            {
                "panel_id": "workbench",
                "card_id": "batch_generate",
            }
        ]
    finally:
        panel.close()
