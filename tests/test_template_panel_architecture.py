import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QComboBox, QSizePolicy
from src.config.scene import SceneWorkspace
from src.config.template import StyleConfig
from src.shared.ui.style_management_block import StyleManagementBlock
from src.shared.ui.style_preview_surface import StylePreviewSurface
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.ui.panels.template_format import (
    TEMPLATE_PREVIEW_SPECS,
    build_template_page_presentation_envelope,
)
from src.ui.panels.template_panel import TemplatePanel
from src.ui.panels.template_style_preview import TemplateStylePreview


def _app():
    return QApplication.instance() or QApplication([])


def test_template_panel_uses_shared_detail_controller_for_detail_switching():
    panel_source = inspect.getsource(TemplatePanel)
    module_source = (ROOT / "src/ui/panels/template_panel.py").read_text(encoding="utf-8")

    assert "DetailPaneController" in module_source
    assert "self._details = DetailPaneController(" in panel_source
    assert "self._details.register_details(self._detail_map)" in panel_source
    assert "self._details.show_detail(card_id)" in panel_source


def test_template_panel_uses_extracted_template_style_preview_widget():
    _app()
    module_source = (ROOT / "src/ui/panels/template_panel.py").read_text(encoding="utf-8")
    preview_source = (
        ROOT / "src/ui/panels/template_style_preview.py"
    ).read_text(encoding="utf-8")
    panel = TemplatePanel(PanelBridge())
    try:
        assert "from src.ui.panels.template_style_preview import TemplateStylePreview" in module_source
        assert "class TemplateStylePreview" not in module_source
        assert "class TemplateStylePreview" in preview_source
        assert "self._preview_card = Card(parent=self)" not in module_source
        assert "mode=\"template_overview_preview\"" in module_source
        assert "StylePreviewSurface(" in module_source
        assert isinstance(panel._overview_detail._preview, TemplateStylePreview)
        assert isinstance(panel._overview_detail._preview_slot, StylePreviewSurface)
        assert isinstance(
            panel._overview_detail._preview_management_block,
            StyleManagementBlock,
        )
        assert panel._overview_detail._preview_management_block.property(
            "style_management_mode"
        ) == "template_overview_preview"
        assert panel._overview_detail._preview_management_block.property(
            "style_management_content_plan"
        ) == "preview"
        assert panel._overview_detail._preview_management_block.preview_slot is (
            panel._overview_detail._preview_slot
        )
        assert panel._overview_detail._preview_management_block.property(
            "style_management_preview_slot_protocol"
        ) == "preview_projection"
        assert panel._overview_detail._preview_management_block.property(
            "style_management_preview_slot_ready"
        ) is True
        assert panel._overview_detail._preview_management_block.effective_preview_slot is (
            panel._overview_detail._preview_slot
        )
        assert panel._overview_detail._preview_management_block.property(
            "style_management_effective_preview_protocol"
        ) == "preview_projection"
        assert panel._overview_detail._preview_management_block.property(
            "style_management_effective_preview_ready"
        ) is True
        assert panel._overview_detail._preview_slot.renderer_widget is (
            panel._overview_detail._preview
        )
        assert panel._overview_detail._preview_slot.property(
            "style_preview_surface_renderer_kind"
        ) == "template_page"
        assert panel._overview_detail._preview_slot.property(
            "style_preview_surface_renderer_protocol"
        ) == "presentation_envelope"
        assert panel._overview_detail._preview_slot.property(
            "style_preview_surface_renderer_ready"
        ) is True
        assert panel._overview_detail._preview_management_block.property(
            "style_management_has_editor"
        ) is False
        preview_header = panel._overview_detail._preview_management_block._card.header
        assert preview_header._compact is True
        assert preview_header.icon_label.width() == 18
        assert panel._overview_detail._preview_slot.property(
            "style_preview_surface_show_metadata"
        ) is False
        assert panel._overview_detail._cached_preview_desc.isHidden() is True
        assert panel._overview_detail._preview_slot.detail_label.isHidden() is True
        assert panel._overview_detail._cached_preview_desc.text() == (
            panel._overview_detail._preview.presentation_envelope.summary
        )
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
    panel = TemplatePanel(PanelBridge())
    try:
        combo_index = next(
            index
            for index in range(panel._overview_detail._combo.count())
            if panel._overview_detail._combo.itemData(index) == "thesis_gbt"
        )
        thesis_name = panel._overview_detail._combo.itemText(combo_index)

        panel._on_template_selected(combo_index)
        envelope = build_template_page_presentation_envelope(panel._current_template)

        assert panel._current_template_id == "thesis_gbt"
        assert panel._current_template.name == thesis_name
        assert panel._overview_detail._preview.presentation_envelope == envelope
        assert panel._overview_detail._cached_preview_desc.text() == envelope.summary
        assert panel._current_template.page_setup.margin.top_cm == 3.8
        assert "body" in panel._current_template.styles
        assert panel._current_template.styles["body"].font_cn == "宋体"
        assert "heading1" in panel._current_template.heading_numbering.level_bindings
    finally:
        panel.close()


EXPECTED_BUILTIN_TEMPLATE_IDS = [
    "default",
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

        assert option_ids[:len(EXPECTED_BUILTIN_TEMPLATE_IDS)] == EXPECTED_BUILTIN_TEMPLATE_IDS
    finally:
        panel.close()


def test_template_panel_selector_ignores_scene_compatible_template_filter():
    _app()
    bridge = PanelBridge()
    bridge.set_current_scene(
        SceneWorkspace(
            scene_id="thesis",
            template_id="thesis_gbt",
            default_template_id="thesis_gbt",
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

        assert option_ids[:len(EXPECTED_BUILTIN_TEMPLATE_IDS)] == EXPECTED_BUILTIN_TEMPLATE_IDS
    finally:
        panel.close()


def test_template_panel_keeps_scene_style_overrides_out_of_template_body_detail():
    _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    scene.section_styles["references_body"] = StyleConfig(font_cn="黑体")
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
        assert detail._style_management_block.property(
            "style_management_has_policy"
        ) is False
        assert not hasattr(detail, "_template_policy_deck")
        assert detail._style_owner_status is None

        scene.section_styles.clear()
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
        expected_detail_ids = {spec.detail_card_id for spec in TEMPLATE_PREVIEW_SPECS}

        assert set(panel._overview_detail._rows) == {spec.group_id for spec in TEMPLATE_PREVIEW_SPECS}
        assert expected_detail_ids.issubset(panel._detail_map)
        assert expected_detail_ids.issubset(panel._nav_cards)
    finally:
        panel.close()


def test_template_panel_overview_uses_expanded_template_management_actions():
    _app()
    panel = TemplatePanel(PanelBridge())
    try:
        detail = panel._overview_detail

        assert detail._new_template_btn.text() == "新建模板"
        assert detail._duplicate_template_btn.text() == "创建副本"
        assert detail._rename_template_btn.text() == "重命名模板"
        assert detail._open_template_folder_btn.text() == "打开模板文件夹"
        assert detail._delete_template_btn.text() == "删除模板"
        assert detail._new_template_btn.isEnabled() is True
        assert detail._duplicate_template_btn.isEnabled() is True
        assert detail._open_template_folder_btn.isEnabled() is True
        assert detail._rename_template_btn.isEnabled() is False
        assert detail._delete_template_btn.isEnabled() is False
        assert detail._new_template_btn.property("variant") == "secondary"
        assert detail._duplicate_template_btn.property("variant") == "secondary"
        assert detail._new_template_btn.font().bold() is True
        assert detail._duplicate_template_btn.font().bold() is True
        assert detail._rename_template_btn.font().bold() is True
        assert detail._open_template_folder_btn.font().bold() is True
        assert detail._delete_template_btn.font().bold() is True
        assert detail._new_template_btn.icon().isNull() is False
        assert detail._duplicate_template_btn.icon().isNull() is False
        assert detail._new_template_btn.iconSize().width() == 16
        assert detail._new_template_btn.iconSize().height() == 16
        assert detail._duplicate_template_btn.iconSize().width() == 16
        assert detail._duplicate_template_btn.iconSize().height() == 16
        assert detail._combo.property("fullWidthMode") is True
        assert detail._combo.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
        assert detail._combo.sizeAdjustPolicy() == QComboBox.AdjustToMinimumContentsLengthWithIcon
        assert detail._status_chip.isHidden() is True
        assert not hasattr(detail, "_style_source_slot")
        assert not hasattr(detail, "_style_source_row")

        source = (ROOT / "src/ui/panels/template_panel.py").read_text(encoding="utf-8")
        assert "StyleSourceSlot(" not in source
        assert "样式来源" not in source
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
        assert panel._io_detail._status.text() == ""
    finally:
        panel.close()


def test_template_panel_duplicate_template_creates_file_and_switches_to_copy(tmp_path, monkeypatch):
    import src.config.library as library
    import src.ui.panels.template_panel as panel_module

    _app()
    template_dir = tmp_path / "templates"
    scene_dir = tmp_path / "scenes"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_dir)
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", scene_dir)
    monkeypatch.setattr(panel_module, "TEMPLATE_LIBRARY_DIR", template_dir)
    monkeypatch.setattr(panel_module.Toast, "show_success", staticmethod(lambda *args, **kwargs: None))

    panel = TemplatePanel(PanelBridge())
    try:
        panel._on_duplicate_template_requested()

        saved_path = Path(panel._current_template_path)
        assert saved_path.exists()
        assert saved_path.parent == template_dir
        assert saved_path.name == "默认格式 副本.json"
        assert panel._current_template.name == "默认格式 副本"
        assert panel._current_template_id == saved_path.stem
        assert panel._current_template_source == "library"
        assert panel._overview_detail._combo.currentData() == saved_path.stem
        assert panel.bridge.current_template_id() == saved_path.stem
        assert "已创建副本" in panel._io_detail._status.text()
    finally:
        panel.close()


def test_template_panel_refresh_drops_deleted_current_template(tmp_path):
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
        assert panel._current_template_id == "default"
        assert panel._current_template.name == "默认格式"
        assert "deleted_template" not in option_ids
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
                    "entry_context_title": "来自场景：核对模板与样式",
                    "entry_context_detail": "场景：合同交付；模板：默认格式 (default)",
                    "entry_context_action": (
                        "核对页面、正文、标题、表格、页眉页脚、目录和题注"
                    ),
                },
            }
        )
        app.processEvents()

        assert panel._nav_rail.selected_card_id() == "tpl_overview"
        assert panel._entry_context_bar.isHidden() is False
        assert panel._entry_context_title.text() == "来自场景：核对模板与样式"
        assert panel._entry_context_detail.text() == (
            "场景：合同交付；模板：默认格式 (default)；"
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


def test_template_panel_reformat_toggle_updates_scene_module_switches(monkeypatch):
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    bridge.set_current_scene(scene, config_id="custom", source="library", emit_signal=False)
    panel = TemplatePanel(bridge)
    toggled: list[tuple[str, bool]] = []
    scene_changed: list[SceneWorkspace] = []
    detail_scene_syncs: list[SceneWorkspace] = []
    bridge.module_toggled.connect(lambda module_name, enabled: toggled.append((module_name, enabled)))
    bridge.scene_changed.connect(scene_changed.append)

    try:
        panel._ensure_detail_loaded("tpl_page")
        monkeypatch.setattr(
            panel,
            "_set_detail_scenes",
            lambda updated_scene: detail_scene_syncs.append(updated_scene),
        )
        card = panel._reformat_toggle_cards["tpl_page"]

        card._toggle.click()
        app.processEvents()

        assert scene.module_switches["page_setup"] is False
        assert scene.module_switches["section_format"] is False
        assert bridge.is_scene_dirty() is True
        assert scene_changed == []
        assert detail_scene_syncs == []
        assert ("page_setup", False) in toggled
        assert ("section_format", False) in toggled
        assert card._status_label.text() == "当前场景：已跳过"
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_heading_reformat_toggle_keeps_heading_recognition_available():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    bridge.set_current_scene(scene, config_id="custom", source="library", emit_signal=False)
    panel = TemplatePanel(bridge)

    try:
        panel._ensure_detail_loaded("tpl_heading")
        panel._reformat_toggle_cards["tpl_heading"]._toggle.click()
        app.processEvents()

        assert scene.module_switches["heading_numbering"] is False
        assert scene.module_switches["heading_recognition"] is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_reformat_toggle_disables_without_scene_context():
    app = _app()
    panel = TemplatePanel(PanelBridge())

    try:
        panel._ensure_detail_loaded("tpl_caption")
        card = panel._reformat_toggle_cards["tpl_caption"]

        assert card._toggle.isEnabled() is False
        assert card._status_label.text() == "未绑定当前场景"
    finally:
        panel.close()
        app.processEvents()
