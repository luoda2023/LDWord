import inspect
import sys
from pathlib import Path

from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QComboBox, QLabel, QSizePolicy, Qt
from src.shared.ui.preview_dialog import PreviewDialog
from src.config.builtin_templates import create_builtin_template
from src.config.scene import SceneWorkspace
from src.config.template import StyleConfig
from src.shared.ui.style_management_block import StyleManagementBlock
from src.ui.bridge import PanelBridge
from src.ui.template_close_prompt import TemplateClosePrompt
from src.ui.template_close_transaction import TemplateCloseTransaction
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.ui.panels.template_feature_specs import (
    TEMPLATE_DETAIL_CARD_IDS,
    TEMPLATE_FEATURE_SPECS,
)
from src.ui.panels.template_detail_lifecycle import (
    TemplateDetailLifecycleMixin,
)
from src.ui.panels.template_library_management_mixin import (
    TemplateLibraryManagementMixin,
)
from src.ui.panels.template_navigation_context_mixin import (
    TemplateNavigationContextMixin,
)
from src.ui.panels.template_overview_projection_mixin import (
    TemplateOverviewProjectionMixin,
)
from src.ui.panels.template_panel import TemplatePanel
from src.ui.panels.template_session_persistence_mixin import (
    TemplateSessionPersistenceMixin,
)
from src.ui.panels.template_preview.model import TemplatePreviewMode
from src.ui.panels.template_preview.widget import TemplateStylePreview


def _app():
    return QApplication.instance() or QApplication([])


def test_template_panel_uses_shared_detail_controller_for_detail_switching():
    panel_source = inspect.getsource(TemplatePanel)
    lifecycle_source = inspect.getsource(TemplateDetailLifecycleMixin)
    module_source = (ROOT / "src/ui/panels/template_panel.py").read_text(encoding="utf-8")

    assert "DetailPaneController" in module_source
    assert "self._details = DetailPaneController(" in panel_source
    assert "self._details.register_details(self._detail_map)" in panel_source
    assert issubclass(TemplatePanel, TemplateDetailLifecycleMixin)
    assert "self._details.show_detail(card_id)" in lifecycle_source
    for method_name in (
        "_show_detail",
        "_ensure_detail_loaded",
        "preload_one_detail_for_startup",
        "_show_refresh_overlay",
    ):
        assert f"def {method_name}(" not in panel_source
        assert f"def {method_name}(" in lifecycle_source
    for forbidden_owner in (
        "_draft_store",
        "_draft_save_coordinator",
        "_write_current_template_to_path",
        "_persist_draft_context",
        "TemplateDraft",
    ):
        assert forbidden_owner not in lifecycle_source


def test_template_panel_delegates_two_phase_close_state_to_one_transaction():
    panel_source = inspect.getsource(TemplatePanel)
    prompt_source = inspect.getsource(TemplateClosePrompt)
    transaction_source = inspect.getsource(TemplateCloseTransaction)

    assert "self._close_prompt = TemplateClosePrompt(self)" in panel_source
    assert "self._close_transaction = TemplateCloseTransaction(self)" in panel_source
    assert "return self._close_prompt.ask(count)" in panel_source
    assert "BaseDialog(" not in panel_source
    assert "BaseDialog(" in prompt_source
    for protocol_method, transaction_method in (
        ("prepare_close_pending_changes", "prepare"),
        ("commit_close_pending_changes", "commit"),
        ("rollback_close_pending_changes", "rollback"),
        ("finalize_close_pending_changes", "finalize"),
        ("cancel_prepared_close", "cancel"),
    ):
        assert (
            f"return self._close_transaction.{transaction_method}()"
            in panel_source
            or (
                protocol_method == "finalize_close_pending_changes"
                and "self._close_transaction.finalize()" in panel_source
            )
            or (
                protocol_method == "cancel_prepared_close"
                and "self._close_transaction.cancel()" in panel_source
            )
        )
    for leaked_state in (
        "_prepared_close_action",
        "_prepared_close_saves",
        "_prepared_close_snapshot",
        "_prepared_close_committed",
        "_prepared_close_files_published",
    ):
        assert leaked_state not in panel_source
    for owned_behavior in (
        "def _capture_snapshot(",
        "def _restore_snapshot(",
        "def _restore_files(",
        "def _commit_prepared_saves(",
    ):
        assert owned_behavior in transaction_source
    for forbidden_owner in (
        "BaseDialog",
        "_write_current_template_to_path",
        "_activate_template",
        "_refresh_template_library_from_disk",
    ):
        assert forbidden_owner not in transaction_source


def test_template_panel_delegates_session_persistence_to_bounded_owner():
    panel_source = inspect.getsource(TemplatePanel)
    persistence_source = inspect.getsource(TemplateSessionPersistenceMixin)

    assert issubclass(TemplatePanel, TemplateSessionPersistenceMixin)
    for method_name in (
        "_sync_template_dirty_state",
        "_prepare_draft_context_saves",
        "_write_current_template_to_path",
        "_activate_template",
        "_save_current_template",
        "_confirm_shared_template_write_for_context",
    ):
        assert f"def {method_name}(" not in panel_source
        assert f"def {method_name}(" in persistence_source
    for injected_seam in (
        "_template_persistence_confirm",
        "_template_dependency_resolver",
        "_template_library_path_predicate",
    ):
        assert injected_seam in panel_source
    for forbidden_owner in (
        "def _capture_snapshot(",
        "QFileSystemWatcher",
        "handle_navigation_intent",
        "_refresh_template_library_from_disk",
        "_on_delete_template_requested",
    ):
        assert forbidden_owner not in persistence_source


def test_template_panel_delegates_library_management_to_bounded_owner():
    panel_source = inspect.getsource(TemplatePanel)
    library_source = inspect.getsource(TemplateLibraryManagementMixin)

    assert issubclass(TemplatePanel, TemplateLibraryManagementMixin)
    for method_name in (
        "_template_overview_status_text",
        "_setup_template_library_watcher",
        "_refresh_template_library_from_disk",
        "_refresh_template_selector_options",
        "_on_new_template_requested",
        "_on_delete_template_requested",
        "_on_template_selected",
    ):
        assert f"def {method_name}(" not in panel_source
        assert f"def {method_name}(" in library_source
    for injected_seam in (
        "_template_text_request",
        "_template_persistence_confirm",
    ):
        assert injected_seam in panel_source
        assert injected_seam in library_source
    for forbidden_owner in (
        "_prepare_draft_context_saves",
        "_capture_snapshot",
        "handle_navigation_intent",
        "_attach_participation_section",
    ):
        assert forbidden_owner not in library_source


def test_template_panel_delegates_navigation_context_to_bounded_owner():
    panel_source = inspect.getsource(TemplatePanel)
    navigation_source = inspect.getsource(TemplateNavigationContextMixin)

    assert issubclass(TemplatePanel, TemplateNavigationContextMixin)
    for method_name in (
        "handle_navigation_intent",
        "_focus_navigation_field",
        "_set_return_navigation_intent",
        "_set_entry_context",
        "_scene_template_context_detail",
        "_navigate_return_target",
    ):
        assert f"def {method_name}(" not in panel_source
        assert f"def {method_name}(" in navigation_source
    for forbidden_owner in (
        "_draft_store",
        "_persist_draft_context",
        "_refresh_template_library_from_disk",
        "_capture_snapshot",
        "_attach_participation_section",
    ):
        assert forbidden_owner not in navigation_source


def test_template_panel_delegates_overview_projection_to_bounded_owner():
    panel_source = inspect.getsource(TemplatePanel)
    projection_source = inspect.getsource(TemplateOverviewProjectionMixin)

    assert issubclass(TemplatePanel, TemplateOverviewProjectionMixin)
    for method_name in (
        "_refresh_overview_projection",
        "_build_overview_projection_state",
        "_build_overview_failure_projection_state",
        "_apply_overview_projection_state",
    ):
        assert f"def {method_name}(" not in panel_source
        assert f"def {method_name}(" in projection_source
    for injected_seam in (
        "_template_preview_config_resolver",
        "_template_preview_baseline_resolver",
    ):
        assert injected_seam in panel_source
        assert injected_seam in projection_source
    for forbidden_owner in (
        "_draft_store",
        "_persist_draft_context",
        "_refresh_template_library_from_disk",
        "handle_navigation_intent",
        "_capture_snapshot",
    ):
        assert forbidden_owner not in projection_source


def test_template_panel_uses_clickable_projected_preview_without_a_text_button():
    _app()
    module_source = (ROOT / "src/ui/panels/template_panel.py").read_text(encoding="utf-8")
    preview_source = (
        ROOT / "src/ui/panels/template_preview/widget.py"
    ).read_text(encoding="utf-8")
    panel = TemplatePanel(PanelBridge())
    try:
        assert "template_overview_detail import TemplateOverviewDetail" in module_source
        assert "class TemplateStylePreview" not in module_source
        assert "class TemplateStylePreview" in preview_source
        assert isinstance(panel._overview_detail._preview, TemplateStylePreview)
        preview_header = panel._overview_detail._preview_card.header
        assert preview_header._compact is True
        assert preview_header.icon_label.width() == 18
        assert panel._overview_detail._preview_mode_chip.text() == "模板基线"
        assert panel._overview_detail._preview_status.text()
        assert panel._overview_detail._preview.toolTip() == ""
        assert panel._overview_detail._preview.focusPolicy() == Qt.StrongFocus
        assert panel._overview_detail._preview.cursor().shape() == Qt.PointingHandCursor
        assert not hasattr(panel._overview_detail, "_open_preview_btn")
        assert hasattr(panel._overview_detail, "_open_template_preview_dialog")
        assert panel._overview_detail._preview_dialog is None
        assert not hasattr(panel._overview_detail, "preview_navigate")
        assert not hasattr(panel, "_on_preview_navigate")
        assert not hasattr(panel._overview_detail, "_preview_slot")
        assert not hasattr(panel._overview_detail, "_preview_management_block")
    finally:
        panel.close()


def test_template_panel_hides_unselected_details_inside_detail_container():
    _app()
    panel = TemplatePanel(PanelBridge())
    try:
        assert panel._current_detail is panel._overview_detail

        for card_id, detail in panel._detail_map.items():
            assert detail.parent() is panel._detail_container
            if card_id == "tpl_overview":
                assert detail.isHidden() is False
            else:
                assert detail.isHidden() is True
    finally:
        panel.close()


def test_template_panel_builtin_selection_loads_real_template_config():
    _app()
    bridge = PanelBridge()
    bridge.set_current_work_mode("thesis", emit_signal=False)
    panel = TemplatePanel(bridge)
    try:
        combo_index = next(
            index
            for index in range(panel._overview_detail._combo.count())
            if panel._overview_detail._combo.itemData(index) == "thesis_gbt"
        )
        thesis_name = panel._overview_detail._combo.itemText(combo_index)

        panel._on_template_selected(combo_index)
        assert panel._current_template_id == "thesis_gbt"
        assert panel._current_template.name == thesis_name
        assert panel._overview_detail._preview.projection.mode is TemplatePreviewMode.TEMPLATE_BASELINE
        assert panel._overview_detail._preview.projection.page_geometry.margin_top_cm == 3.8
        assert panel._current_template.page_setup.margin.top_cm == 3.8
        assert "body" in panel._current_template.styles
        assert panel._current_template.styles["body"].font_cn == "宋体"
        assert "heading1" in panel._current_template.heading_numbering.level_bindings
    finally:
        panel.close()


EXPECTED_CUSTOM_TEMPLATE_IDS = [
    "default",
]

EXPECTED_THESIS_TEMPLATE_IDS = [
    "thesis_gbt",
]


def test_template_panel_selector_shows_complete_template_library():
    _app()
    panel = TemplatePanel(PanelBridge())
    try:
        option_ids = [
            panel._overview_detail._combo.itemData(index)
            for index in range(panel._overview_detail._combo.count())
        ]

        assert option_ids[:len(EXPECTED_CUSTOM_TEMPLATE_IDS)] == EXPECTED_CUSTOM_TEMPLATE_IDS
        assert "thesis_gbt" not in option_ids
    finally:
        panel.close()


def test_template_panel_selector_ignores_scene_compatible_template_filter():
    _app()
    bridge = PanelBridge()
    bridge.set_current_work_mode("thesis", emit_signal=False)
    bridge.set_current_scene(
        SceneWorkspace(
            scene_id="thesis",
            template_id="thesis_gbt",
            compatible_template_ids=["thesis_gbt", "thesis_custom"],
        ),
        config_id="thesis",
        source="library",
        emit_signal=False,
    )
    panel = TemplatePanel(bridge)
    try:
        option_ids = [
            panel._overview_detail._combo.itemData(index)
            for index in range(panel._overview_detail._combo.count())
        ]

        assert option_ids[:len(EXPECTED_THESIS_TEMPLATE_IDS)] == EXPECTED_THESIS_TEMPLATE_IDS
        assert "default" not in option_ids
    finally:
        panel.close()


def test_template_panel_keeps_plan_scope_out_of_template_body_detail():
    _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    scene.document_scope.mode = "body"
    bridge.set_current_scene(
        scene,
        config_id="custom",
        source="library",
        emit_signal=False,
    )
    panel = TemplatePanel(bridge)
    try:
        panel._show_detail("tpl_style")
        detail = panel._style_detail

        assert isinstance(detail._style_management_block, StyleManagementBlock)
        assert detail._style_management_block.property(
            "style_management_slot_plan"
        ) == "source|scope|editor"
        assert not hasattr(detail, "_template_policy_deck")
        assert detail._style_owner_status is None

        scene.document_scope.mode = "all"
        bridge.set_current_scene(
            scene,
            config_id="custom",
            source="library",
        )
        assert not hasattr(detail, "_template_policy_deck")
    finally:
        panel.close()


def test_template_panel_registers_overview_rows_and_details_for_every_preview_group():
    _app()
    panel = TemplatePanel(PanelBridge())
    try:
        expected_detail_ids = set(TEMPLATE_DETAIL_CARD_IDS)

        assert set(panel._overview_detail._rows) == {
            spec.feature_id for spec in TEMPLATE_FEATURE_SPECS
        }
        assert expected_detail_ids.issubset(panel._detail_map)
        assert expected_detail_ids.issubset(panel._nav_cards)
        assert {"tpl_formula", "tpl_reference", "tpl_other"}.isdisjoint(
            panel._nav_cards
        )
        assert {"tpl_formula", "tpl_reference", "tpl_other"}.isdisjoint(
            panel._detail_map
        )
    finally:
        panel.close()


def test_template_panel_scene_does_not_replace_baseline_until_user_switches_mode():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    scene.module_switches["table_format"] = False
    bridge.set_current_scene(scene, emit_signal=False)
    panel = TemplatePanel(bridge)
    try:
        baseline = panel._overview_detail._preview.projection
        assert baseline.mode is TemplatePreviewMode.TEMPLATE_BASELINE
        assert any(block.kind.value == "table" for block in baseline.blocks)

        panel._on_preview_mode_requested(TemplatePreviewMode.CURRENT_PLAN.value)
        app.processEvents()

        current = panel._overview_detail._preview.projection
        assert current.mode is TemplatePreviewMode.CURRENT_PLAN
        assert all(block.kind.value != "table" for block in current.blocks)
        assert panel._overview_detail._preview_mode_chip.text() == "当前方案"
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_preview_activation_opens_one_whole_window_preview():
    app = _app()
    panel = TemplatePanel(PanelBridge())
    try:
        panel.resize(1280, 900)
        panel.show()
        app.processEvents()
        selected_before = panel._nav_rail.selected_card_id()

        preview = panel._overview_detail._preview
        click_point = preview.layout_snapshot.pages[0].page_rect.center().toPoint()
        QTest.mouseClick(preview, Qt.LeftButton, pos=click_point)
        app.processEvents()

        dialog = panel._overview_detail._preview_dialog
        renderer = panel._overview_detail._preview_dialog_renderer
        assert isinstance(dialog, PreviewDialog)
        assert dialog.isVisible() is True
        assert isinstance(renderer, TemplateStylePreview)
        assert renderer.presentation == "dialog"
        assert renderer.projection is panel._overview_detail._preview.projection
        assert dialog.content.widget is renderer
        assert panel._nav_rail.selected_card_id() == selected_before

        QTest.mouseClick(preview, Qt.LeftButton, pos=click_point)
        app.processEvents()
        assert panel._overview_detail._preview_dialog is dialog

        dialog.close()
        app.processEvents()
        assert panel._overview_detail._preview_dialog is None
    finally:
        dialog = panel._overview_detail._preview_dialog
        if dialog is not None:
            dialog.close()
        panel.close()
        app.processEvents()


def test_template_panel_module_switches_are_compact_summary_header_controls():
    app = _app()
    bridge = PanelBridge()
    bridge.set_current_scene(SceneWorkspace(scene_id="custom"), emit_signal=False)
    panel = TemplatePanel(bridge)
    try:
        detail = panel._ensure_detail_loaded("tpl_page")
        controls = panel._participation_sections["tpl_page"]

        assert controls.parent() is detail._summary_card.header
        assert set(controls.toggles) == {"page_setup", "section_format"}
        assert not hasattr(controls, "_rows")
        assert controls.isHidden() is False
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_overview_exposes_only_template_library_actions():
    _app()
    panel = TemplatePanel(PanelBridge())
    try:
        detail = panel._overview_detail

        assert detail._new_template_btn.text() == "新建模板"
        assert detail._duplicate_template_btn.text() == "创建副本"
        assert detail._rename_template_btn.text() == "重命名模板"
        assert detail._open_template_folder_btn.text() == "打开模板文件夹"
        assert detail._delete_template_btn.text() == "删除模板"
        assert not hasattr(detail, "_import_template_btn")
        assert not hasattr(detail, "_export_template_btn")
        assert not hasattr(detail, "_reset_template_btn")
        assert detail._new_template_btn.isEnabled() is True
        assert detail._duplicate_template_btn.isEnabled() is True
        assert detail._open_template_folder_btn.isEnabled() is True
        assert detail._open_template_folder_btn.font().bold() is True
        panel._activate_template(
            create_builtin_template("default"),
            template_id="default",
            source="builtin",
            source_type="builtin",
        )
        assert detail._rename_template_btn.isEnabled() is False
        assert detail._delete_template_btn.isEnabled() is False
        for action_button in (
            detail._new_template_btn,
            detail._duplicate_template_btn,
            detail._rename_template_btn,
            detail._open_template_folder_btn,
            detail._delete_template_btn,
        ):
            assert action_button.icon().isNull() is False
            assert action_button.iconSize().width() == 16
            assert action_button.iconSize().height() == 16
        assert "tpl_io" not in panel._nav_cards
        assert "tpl_io" not in panel._detail_map
        assert detail._combo.property("fullWidthMode") is True
        assert detail._combo.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
        assert detail._combo.sizeAdjustPolicy() == QComboBox.AdjustToMinimumContentsLengthWithIcon
        assert detail._status_chip.isHidden() is True
        assert not hasattr(detail, "_style_source_slot")
        assert not hasattr(detail, "_style_source_row")

        source = (ROOT / "src/ui/panels/template_panel.py").read_text(encoding="utf-8")
        overview_source = (
            ROOT / "src/ui/panels/template_overview_detail.py"
        ).read_text(encoding="utf-8")
        assert "StyleSourceSlot(" not in source
        assert "样式来源" not in source
        for forbidden in (
            "QFileDialog",
            "_save_current_template_as",
            "def _on_import(",
            "def _on_reset(",
        ):
            assert forbidden not in source
        for forbidden in (
            "import_template_requested",
            "export_template_requested",
            "reset_template_requested",
            "tpl_overview_import_template_btn",
            "tpl_overview_export_template_btn",
            "tpl_overview_reset_template_btn",
        ):
            assert forbidden not in overview_source
    finally:
        panel.close()


def test_template_panel_selector_keeps_session_custom_template_without_file():
    _app()
    panel = TemplatePanel(PanelBridge())
    try:
        panel._current_template.name = "会话临时模板"
        panel._current_template_id = "__session_only_template__"
        panel._current_template_path = ""
        panel._current_template_source = ""
        panel._refresh_template_selector_options()

        index = next(
            item_index
            for item_index in range(panel._overview_detail._combo.count())
            if panel._overview_detail._combo.itemData(item_index) == "__session_only_template__"
        )

        panel._on_template_selected(index)

        assert panel._current_template_id == "__session_only_template__"
        assert panel._current_template.name == "会话临时模板"
        assert panel._current_template_path == ""
        assert panel._last_template_management_status == ""
    finally:
        panel.close()


def test_template_panel_connects_template_management_handlers():
    _app()
    panel = TemplatePanel(PanelBridge())
    try:
        assert callable(panel._on_new_template_requested)
        assert callable(panel._on_duplicate_template_requested)
        assert callable(panel._on_rename_template_requested)
        assert callable(panel._on_delete_template_requested)
    finally:
        panel.close()


def test_open_template_folder_opens_current_mode_unified_workbench_board(
    tmp_path,
    monkeypatch,
):
    import src.config.library as library
    import src.ui.panels.template_panel as panel_module

    template_dir = tmp_path / "templates"
    scene_dir = tmp_path / "plans"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_dir)
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", scene_dir)
    opened_paths: list[Path] = []
    monkeypatch.setattr(
        panel_module.QDesktopServices,
        "openUrl",
        staticmethod(
            lambda url: opened_paths.append(Path(url.toLocalFile())) or True
        ),
    )

    app = _app()
    bridge = PanelBridge()
    bridge.set_current_work_mode("thesis", emit_signal=False)
    panel = TemplatePanel(bridge)
    try:
        panel._on_open_template_folder_requested()
        app.processEvents()

        assert opened_paths == [tmp_path / "template_workbench" / "thesis"]
        workspace = opened_paths[0]
        assert sorted(
            path.name
            for path in workspace.parent.iterdir()
            if path.is_dir()
        ) == ["thesis"]
        assert not workspace.resolve().is_relative_to(template_dir.resolve())
        assert (workspace / "AI模板生成提示词.md").is_file()
        assert (workspace / "模板配置基准.json").is_file()
        inbox = workspace / "待导入"
        assert inbox.is_dir()
        assert {path.name for path in workspace.iterdir()} == {
            "AI模板生成提示词.md",
            "模板配置基准.json",
            "待导入",
        }
        assert str(inbox) not in panel._template_library_watcher.directories()
        assert all(
            Path(path).resolve().is_relative_to(template_dir.resolve())
            for path in panel._template_library_watcher.directories()
        )
        assert str(workspace) in panel._overview_detail._open_template_folder_btn.toolTip()
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_refresh_does_not_consume_authoring_inbox(
    tmp_path,
    monkeypatch,
):
    import src.config.library as library
    from src.config.loader import save_template
    from src.config.template_authoring_workspace import (
        ensure_template_authoring_workspace,
    )

    template_dir = tmp_path / "templates"
    scene_dir = tmp_path / "plans"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_dir)
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", scene_dir)
    app = _app()
    bridge = PanelBridge()
    bridge.set_current_work_mode("thesis", emit_signal=False)
    panel = TemplatePanel(bridge)
    try:
        workspace = ensure_template_authoring_workspace("thesis")
        generated = create_builtin_template("default")
        generated.name = "重庆人文科技学院毕业设计说明格式"
        source = workspace.inbox_path / "default_format (1).json"
        save_template(generated, source)
        current_template_id = panel._current_template_id
        current_template_name = panel._current_template.name

        panel._refresh_template_library_from_disk()
        app.processEvents()

        assert source.exists()
        assert not list(workspace.archive_dir.glob("*.json"))
        assert not list((template_dir / "thesis" / "user").glob("*.json"))
        assert panel._current_template_id == current_template_id
        assert panel._current_template.name == current_template_name
        assert str(workspace.inbox_path) not in (
            panel._template_library_watcher.directories()
        )
    finally:
        panel.close()
        app.processEvents()


def test_template_library_change_refreshes_selector_without_activating_import(
    tmp_path,
    monkeypatch,
):
    import src.config.library as library
    import src.ui.panels.template_panel as panel_module
    from src.config.loader import save_template
    from src.config.template_authoring_workspace import (
        ensure_template_authoring_workspace,
        process_template_import_inbox,
    )

    template_dir = tmp_path / "templates"
    scene_dir = tmp_path / "plans"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_dir)
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", scene_dir)
    success_messages: list[str] = []
    monkeypatch.setattr(
        panel_module.Toast,
        "show_success",
        staticmethod(lambda message, *args, **kwargs: success_messages.append(message)),
    )

    app = _app()
    bridge = PanelBridge()
    bridge.set_current_work_mode("thesis", emit_signal=False)
    panel = TemplatePanel(bridge)
    try:
        current_template_id = panel._current_template_id
        current_template_name = panel._current_template.name
        workspace = ensure_template_authoring_workspace("thesis")
        generated = create_builtin_template("thesis_gbt")
        generated.name = "重庆人文科技学院毕业设计说明格式"
        save_template(generated, workspace.inbox_path / "ai-result.json")
        batch = process_template_import_inbox("thesis", settle_seconds=0)
        imported_id = batch.successes[0].entry.config_id

        bridge.template_library_events.import_completed.emit("thesis", batch)
        app.processEvents()

        assert panel._overview_detail._combo.findData(imported_id) >= 0
        assert panel._current_template_id == current_template_id
        assert panel._current_template.name == current_template_name
        assert panel._overview_detail._combo.currentData() == current_template_id
        assert success_messages == [
            f"已导入模板: {generated.name}；当前编辑保持不变"
        ]
    finally:
        panel.close()
        app.processEvents()


def test_template_copy_is_saved_to_current_mode_user_library(tmp_path, monkeypatch):
    import src.config.library as library
    import src.ui.panels.template_panel as panel_module

    template_dir = tmp_path / "templates"
    scene_dir = tmp_path / "scenes"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_dir)
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", scene_dir)
    monkeypatch.setattr(
        panel_module.Toast,
        "show_success",
        staticmethod(lambda *args, **kwargs: None),
    )

    bridge = PanelBridge()
    bridge.set_current_work_mode("exam", emit_signal=False)
    panel = TemplatePanel(bridge)
    try:
        assert panel._create_template_copy("校级试卷副本", action_label="创建副本")

        saved_path = Path(panel._current_template_path)
        assert saved_path.exists()
        assert saved_path.parent == template_dir / "exam" / "user"
        assert panel._current_template.name == "校级试卷副本"
        assert panel._current_template_source_type == "user"
        assert panel._overview_detail._rename_template_btn.isEnabled() is True
        assert panel._overview_detail._delete_template_btn.isEnabled() is True
        assert not (template_dir / "custom" / "user" / saved_path.name).exists()
    finally:
        panel.close()


def test_user_template_can_be_renamed_and_deleted(tmp_path, monkeypatch):
    import src.config.library as library
    import src.ui.panels.template_panel as panel_module
    from src.config.loader import load_template

    template_dir = tmp_path / "templates"
    scene_dir = tmp_path / "scenes"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_dir)
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", scene_dir)
    monkeypatch.setattr(
        panel_module.Toast,
        "show_success",
        staticmethod(lambda *args, **kwargs: None),
    )
    monkeypatch.setattr(panel_module, "confirm", lambda *args, **kwargs: True)

    bridge = PanelBridge()
    bridge.set_current_work_mode("exam", emit_signal=False)
    panel = TemplatePanel(bridge)
    try:
        assert panel._create_template_copy("待管理模板", action_label="创建副本")
        managed_path = Path(panel._current_template_path)
        rename_prompt: dict[str, object] = {}

        def accept_rename(*_args, **kwargs):
            rename_prompt.update(kwargs)
            return "已重命名模板"

        monkeypatch.setattr(
            panel_module,
            "input_text",
            accept_rename,
        )
        panel._current_template.page_setup.margin.top_cm = 7.7
        panel._on_template_edited(panel._current_template)

        panel._on_rename_template_requested()

        assert managed_path.exists()
        assert load_template(managed_path).name == "待管理模板"
        assert load_template(managed_path).page_setup.margin.top_cm != 7.7
        assert panel._current_template.name == "已重命名模板"
        assert panel._current_template.page_setup.margin.top_cm == 7.7
        assert panel.pending_template_draft_count() == 1
        assert rename_prompt["ok_text"] == "暂存名称"

        assert panel._save_current_template() is True
        assert load_template(managed_path).name == "已重命名模板"
        assert load_template(managed_path).page_setup.margin.top_cm == 7.7
        panel._current_template.name = "即将删除的草稿"
        panel._on_template_edited(panel._current_template)
        assert panel.pending_template_draft_count() == 1
        panel._on_delete_template_requested()
        assert not managed_path.exists()
        assert panel.pending_template_draft_count() == 0
        assert panel._current_template_id != managed_path.stem
        assert panel._current_template_source_type == "builtin"
    finally:
        panel.close()


def test_template_panel_unique_user_template_keeps_user_management_permissions(
    tmp_path,
    monkeypatch,
):
    import src.config.library as library
    from src.config.builtin_templates import create_builtin_template

    template_dir = tmp_path / "templates"
    scene_dir = tmp_path / "scenes"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_dir)
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", scene_dir)
    user_template = create_builtin_template("default")
    user_template.name = "校级试卷格式"
    saved = library.save_template_to_library(
        user_template,
        template_id="school_exam_format",
        mode_id="exam",
    )

    app = _app()
    bridge = PanelBridge()
    bridge.set_current_work_mode("exam", emit_signal=False)
    panel = TemplatePanel(bridge)
    try:
        app.processEvents()

        index = panel._overview_detail._combo.findData("school_exam_format")
        assert index >= 0
        panel._on_template_selected(index)
        app.processEvents()

        entry = library.get_template_entry("school_exam_format", mode_id="exam")
        assert entry is not None
        assert entry.source_type == "user"
        assert entry.path == saved.path
        assert panel._current_template_id == "school_exam_format"
        assert panel._current_template.name == "校级试卷格式"
        assert panel._overview_detail._combo.currentText() == "校级试卷格式"
        assert panel._current_template_is_builtin() is False
        assert bridge.current_template_source() == "library"
        assert bridge.current_template_source_type() == "user"
        assert panel._overview_detail._rename_template_btn.isEnabled() is True
        assert panel._overview_detail._delete_template_btn.isEnabled() is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_marks_broken_unique_user_template_unavailable(
    tmp_path,
    monkeypatch,
):
    import src.config.library as library
    import src.ui.panels.template_panel as panel_module
    from src.config.builtin_templates import create_builtin_template

    template_dir = tmp_path / "templates"
    scene_dir = tmp_path / "scenes"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_dir)
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", scene_dir)
    monkeypatch.setattr(
        panel_module.Toast,
        "show_error",
        staticmethod(lambda *args, **kwargs: None),
    )
    user_template = create_builtin_template("default")
    user_template.name = "校级试卷格式"
    saved = library.save_template_to_library(
        user_template,
        template_id="school_exam_format",
        mode_id="exam",
    )

    app = _app()
    bridge = PanelBridge()
    bridge.set_current_work_mode("exam", emit_signal=False)
    panel = TemplatePanel(bridge)
    try:
        index = panel._overview_detail._combo.findData("school_exam_format")
        assert index >= 0
        panel._on_template_selected(index)
        app.processEvents()

        saved.path.write_text("{broken", encoding="utf-8")
        panel._refresh_template_library_from_disk()
        app.processEvents()

        index = panel._overview_detail._combo.findData("school_exam_format")
        item = panel._overview_detail._combo.model().item(index)
        assert index >= 0
        assert (
            panel._overview_detail._combo.itemText(index)
            == "school_exam_format (Unavailable)"
        )
        assert item is not None
        assert item.isEnabled() is False
        assert panel._overview_detail._combo.itemData(index, Qt.ToolTipRole)

        panel._on_template_selected(index)
        assert panel._current_template.name == "校级试卷格式"
        assert "模板加载失败" in panel._last_template_management_status
        assert "不可用" in panel._last_template_management_status
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_refresh_preserves_dirty_draft_when_source_is_deleted(tmp_path):
    _app()
    panel = TemplatePanel(PanelBridge())
    try:
        missing_path = tmp_path / "deleted_template.json"
        panel._current_template.name = "已删除模板"
        panel._current_template_id = "deleted_template"
        panel._current_template_path = str(missing_path)
        panel._current_template_source = "file"

        panel._refresh_template_library_from_disk()

        option_ids = [
            panel._overview_detail._combo.itemData(index)
            for index in range(panel._overview_detail._combo.count())
        ]
        assert panel._current_template_id == "deleted_template"
        assert panel._current_template.name == "已删除模板"
        assert "deleted_template" not in option_ids
        assert "草稿仍保留" in panel._last_template_management_status
    finally:
        panel.close()


def test_template_panel_dirty_draft_protects_committed_bridge_snapshot():
    _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    try:
        committed_name = bridge.current_template().name
        panel._current_template.name = "Unsaved draft name"
        panel._on_template_edited(panel._current_template)

        assert bridge.is_template_dirty() is True
        assert panel._current_template.name == "Unsaved draft name"
        assert bridge.current_template().name == committed_name

        disk_reload = create_builtin_template("default")
        disk_reload.name = "Reloaded disk value"
        accepted = bridge.set_current_template(
            disk_reload,
            config_id=bridge.current_template_id(),
            path=bridge.current_template_path(),
            source=bridge.current_template_source(),
            source_type=bridge.current_template_source_type(),
        )

        assert accepted is False
        assert bridge.current_template().name == committed_name
        assert panel._current_template.name == "Unsaved draft name"
    finally:
        panel.close()


def test_template_panel_selector_refreshes_before_popup_opens():
    _app()
    panel = TemplatePanel(PanelBridge())
    called: list[bool] = []
    panel._overview_detail.selector_open_requested.connect(lambda: called.append(True))
    try:
        panel._overview_detail._combo.popup_about_to_show.emit()

        assert called == [True]
    finally:
        panel.close()


def test_template_panel_navigation_intent_shows_return_to_execution_action():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    intents: list[object] = []
    bridge.navigate_to_intent.connect(intents.append)
    try:
        panel.handle_navigation_intent(
            {
                "panel_id": "template",
                "card_id": "tpl_style",
                "return_panel_id": "workbench",
                "return_card_id": "quick_execute",
            }
        )
        app.processEvents()

        assert panel._return_bar.isHidden() is False
        assert panel._entry_context_bar.isHidden() is True
        assert panel._nav_rail.selected_card_id() == "tpl_style"

        panel._return_btn.click()

        assert intents[-1] == {
            "panel_id": "workbench",
            "card_id": "quick_execute",
        }
        assert panel._return_bar.isHidden() is True

        panel.handle_navigation_intent(
            {
                "panel_id": "template",
                "card_id": "tpl_style",
                "field_id": "body.font_name",
                "active_issue_id": "template.body.font_name",
                "return_panel_id": "workbench",
                "return_card_id": "quick_execute",
                "payload": {
                    "issue_title": "模板字体不一致",
                    "issue_item_id": "template.body.font_name",
                },
            }
        )
        app.processEvents()

        assert panel._return_label.text() == "从执行问题进入：模板字体不一致"
        assert panel._entry_context_bar.isHidden() is False
        assert panel._entry_context_title.text() == "来自执行问题：模板字体不一致"
        assert panel._entry_context_detail.text() == "调整后返回执行页复检"

        panel._return_btn.click()

        assert intents[-1]["panel_id"] == "workbench"
        assert intents[-1]["card_id"] == "quick_execute"
        assert intents[-1]["active_issue_id"] == "template.body.font_name"
        assert intents[-1]["payload"]["active_issue_id"] == "template.body.font_name"
        assert panel._entry_context_bar.isHidden() is True
        for _ in range(4):
            app.processEvents()

        style_detail = panel._detail_map["tpl_style"]
        assert style_detail._font_cn.objectName() == "tpl_style_body_font_cn"
        assert style_detail._font_cn.property("navigation_field_highlight") is True
        assert "文字样式：正文中文字体" in style_detail._font_cn.toolTip()
        assert "正文中文字体" in style_detail._font_cn.toolTip()
        assert "body.font_name" not in style_detail._font_cn.toolTip()
        assert style_detail._font_cn.property("navigation_field_raw_label") == (
            "body.font_name"
        )
    finally:
        panel.close()


def test_template_panel_shows_scene_entry_context_for_template_preview_jump():
    app = _app()
    bridge = PanelBridge()
    bridge.set_current_scene(
        SceneWorkspace(scene_id="contract_delivery", template_id="default"),
        config_id="contract_delivery",
        emit_signal=False,
    )
    panel = TemplatePanel(bridge)
    try:
        panel.handle_navigation_intent(
            {
                "panel_id": "template",
                "card_id": "tpl_overview",
                "return_panel_id": "scene",
                "return_card_id": "scn_overview",
                "payload": {
                    "entry_context_title": "来自方案：核对模板与样式",
                    "entry_context_detail": "方案：合同交付；模板：默认格式 (default)",
                    "entry_context_action": (
                        "核对页面、正文、标题、表格、页眉页脚、目录和题注"
                    ),
                },
            }
        )
        app.processEvents()

        assert panel._nav_rail.selected_card_id() == "tpl_overview"
        assert panel._entry_context_bar.isHidden() is False
        assert panel._entry_context_title.text() == "来自方案：核对模板与样式"
        assert panel._entry_context_detail.text() == (
            "方案：合同交付；模板：默认格式 (default)；"
            "核对页面、正文、标题、表格、页眉页脚、目录和题注"
        )
    finally:
        panel.close()


def test_template_panel_reuses_heading_numbering_panel_for_heading_detail():
    _app()
    panel = TemplatePanel(PanelBridge())
    try:
        assert isinstance(panel._heading_detail, HeadingNumberingPanel)
        assert panel._heading_detail._adapter.has_template is True
    finally:
        panel.close()


def test_fresh_builtin_heading_level_two_is_enabled_and_not_visually_muted():
    app = _app()
    panel = TemplatePanel(PanelBridge())
    try:
        detail = panel._heading_detail
        detail._adv_list.setCurrentRow(1)
        app.processEvents()

        binding = detail._adapter.get_binding(2)
        row = detail._adv_list.itemWidget(detail._adv_list.item(1))
        preview_label = row.findChild(QLabel, "hn_list_txt")

        assert binding.enabled is True
        assert detail._level_enabled_switch.isChecked() is True
        assert preview_label.text() != "未启用"
        assert bool(preview_label.property("muted")) is False
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_page_participation_rows_update_independently_once():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    bridge.set_current_scene(scene, config_id="custom", source="library", emit_signal=False)
    panel = TemplatePanel(bridge)
    scene_changed: list[SceneWorkspace] = []
    bridge.scene_changed.connect(scene_changed.append)

    try:
        panel._ensure_detail_loaded("tpl_page")
        section = panel._participation_sections["tpl_page"]
        page_toggle = section.toggles["page_setup"]
        section_toggle = section.toggles["section_format"]
        before_refreshes = panel._projection_refresh_count

        page_toggle.click()
        app.processEvents()

        updated = bridge.current_scene()
        assert updated is not scene
        assert scene.module_switches["page_setup"] is True
        assert updated.module_switches["page_setup"] is False
        assert updated.module_switches["section_format"] is True
        assert bridge.is_scene_dirty() is True
        assert scene_changed == [updated]
        assert panel._projection_refresh_count == before_refreshes + 1
        assert page_toggle.isChecked() is False
        assert section_toggle.isChecked() is True
        assert panel._nav_cards["tpl_page"]._badge.text() == "部分"
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_heading_participation_keeps_recognition_request():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    bridge.set_current_scene(scene, config_id="custom", source="library", emit_signal=False)
    panel = TemplatePanel(bridge)

    try:
        panel._ensure_detail_loaded("tpl_heading")
        section = panel._participation_sections["tpl_heading"]
        assert section._labels["heading_numbering"].text() == "应用标题编号"
        section.toggles[
            "heading_numbering"
        ].click()
        app.processEvents()

        updated = bridge.current_scene()
        assert updated.module_switches["heading_numbering"] is False
        assert updated.module_switches["heading_recognition"] is True
        assert bridge.is_scene_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_participation_is_hidden_without_scene_context():
    app = _app()
    panel = TemplatePanel(PanelBridge())

    try:
        panel._ensure_detail_loaded("tpl_caption")
        section = panel._participation_sections["tpl_caption"]

        assert section.isHidden() is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_dirty_only_signal_does_not_refresh_projection():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    try:
        before = panel._projection_refresh_count
        bridge.mark_template_dirty()
        app.processEvents()
        assert panel._projection_refresh_count == before
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_one_template_edit_refreshes_projection_once():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    try:
        before = panel._projection_refresh_count
        panel._current_template.page_setup.margin.top_cm = 4.1

        panel._on_template_edited(panel._current_template)
        app.processEvents()

        assert panel._projection_refresh_count == before + 1
        assert bridge.is_template_dirty() is True
        assert panel._overview_detail._preview.projection.page_geometry.margin_top_cm == 4.1
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_auto_pruned_request_stays_checked_with_visible_warning():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    scene.module_switches["heading_recognition"] = False
    scene.module_switches["toc"] = True
    bridge.set_current_scene(scene, emit_signal=False)
    panel = TemplatePanel(bridge)
    try:
        panel._ensure_detail_loaded("tpl_toc")
        toggle = panel._participation_sections["tpl_toc"].toggles["toc"]

        assert toggle.isChecked() is True
        assert "依赖未满足" in toggle.toolTip()
        assert panel._nav_cards["tpl_toc"]._badge.text() == "受限"
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_projection_failure_stays_inside_visible_safe_state(monkeypatch):
    app = _app()
    bridge = PanelBridge()
    bridge.set_current_scene(SceneWorkspace(scene_id="broken"), emit_signal=False)

    def _raise_resolver_error(*_args, **_kwargs):
        raise ValueError("invalid preview config")

    monkeypatch.setattr(
        "src.ui.panels.template_panel.resolve_config",
        _raise_resolver_error,
    )
    panel = TemplatePanel(bridge)
    try:
        assert panel._overview_detail._preview.projection.is_empty is True
        assert panel._overview_detail._preview_status.text() == (
            "预览暂不可用；模板参数仍可编辑"
        )
        assert "invalid preview config" not in panel._overview_detail._preview_status.text()
    finally:
        panel.close()
        app.processEvents()
