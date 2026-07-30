from __future__ import annotations

from content_artifact_test_utils import compile_content_binding
from src.qt_api import QLabel, QLineEdit
from src.services.material_content.import_contract import (
    ContentImportDisposition,
    ContentImportFinding,
)
from src.shared.ui.theme import get_theme
from src.ui.bridge import PanelBridge
from src.ui.panels.assets.content_materials_presenter import (
    _blocking_content_message,
)
from src.ui.panels.assets_panel import AssetsPanel


def _blocker(
    code: str,
    object_id: str,
    message: str,
    *,
    count: int = 1,
    scope: str = "main_body",
) -> ContentImportFinding:
    return ContentImportFinding(
        code=code,
        disposition=ContentImportDisposition.BLOCKER,
        scope=scope,
        object_id=object_id,
        cause_id=object_id,
        count=count,
        message_key=f"content.docx.{code}",
        user_message=message,
    )


def test_blocked_content_message_names_the_first_object_and_remaining_count() -> None:
    message = _blocking_content_message(
        (
            _blocker(
                "omml",
                "body-object:1",
                "DOCX 中有 1 个暂不支持的对象：公式。",
            ),
            _blocker(
                "text_box",
                "body-object:2",
                "DOCX 中有 1 个暂不支持的对象：文本框。",
            ),
            _blocker(
                "diagnostic_limit_exceeded",
                "diagnostic-overflow",
                "另有 2 个暂不支持的对象未展开。",
                count=2,
                scope="summary",
            ),
        )
    )

    assert message == (
        "DOCX 中有 1 个暂不支持的对象：公式；"
        "另有 3 个未展开的阻断对象。"
    )


def test_file_materials_use_the_compact_inventory_interaction(tmp_path, qapp):
    panel = AssetsPanel(PanelBridge())
    try:
        assert panel._content_card._header_widget is not None
        assert panel._content_materials_title.text() == "文件资料"
        assert panel._content_card._header_icon_name == "file-text"
        assert get_theme().primary in panel._content_materials_title.styleSheet()
        assert panel._add_content_material_btn.text() == "＋ 新增文件资料"
        assert panel._content_card._header_actions_layout.indexOf(
            panel._add_content_material_btn
        ) >= 0
        assert panel._content_card.findChild(
            QLabel, "content_materials_description"
        ) is None
        assert not hasattr(panel, "_content_materials_empty")

        panel._ensure_content_material_rule("technical_route")
        row = panel._content_material_rows["technical_route"]
        actions = panel._content_material_action_strips["technical_route"]

        assert len(panel._content_rules) == 1
        assert not panel._content_materials_container.isHidden()
        assert panel._content_material_index_labels["technical_route"].text() == "1"
        assert panel._content_material_token_edits["technical_route"].text() == (
            "{{@file:technical_route}}"
        )
        assert row.findChild(QLabel, "content_material_status") is None
        assert panel._content_material_path_edits[
            "technical_route"
        ].placeholderText() == "尚未选择文件"
        assert tuple(actions._buttons) == ("clear", "choose", "add", "remove")
        assert all(not button.icon().isNull() for button in actions.buttons())
        assert not panel._content_material_clear_buttons[
            "technical_route"
        ].isEnabled()

        source = tmp_path / "technical_route.md"
        source.write_text("# 技术路线\n\n正文", encoding="utf-8")
        panel._content_bindings["technical_route"] = compile_content_binding(
            source,
            panel._content_repository(),
            content_id="technical_route",
            label="技术路线",
        )
        panel._sync_content_material_rows()

        assert panel._content_material_path_edits["technical_route"].text() == source.name
        assert panel._content_material_thumbnail_labels["technical_route"].text() == (
            "MARKDOWN"
        )
        assert panel._content_material_clear_buttons[
            "technical_route"
        ].isEnabled()
    finally:
        panel.close()


def test_file_material_new_rows_are_numbered_without_a_dialog(qapp):
    panel = AssetsPanel(PanelBridge())
    try:
        panel._add_content_material_btn.click()
        panel._add_content_material_btn.click()
        qapp.processEvents()

        assert [rule.content_id for rule in panel._content_rules] == [
            "文件1",
            "文件2",
        ]
        assert panel._content_material_token_edits["文件1"].text() == (
            "{{@file:文件1}}"
        )
        assert panel._content_material_token_edits["文件1"].isTokenEditable()

        panel._add_content_material_series("文件1")

        assert [rule.content_id for rule in panel._content_rules] == [
            "文件1",
            "文件2",
            "文件3",
        ]
        assert panel._content_material_index_labels["文件3"].text() == "3"
    finally:
        panel.close()


def test_file_material_inline_rename_migrates_rule_and_binding(tmp_path, qapp):
    panel = AssetsPanel(PanelBridge())
    try:
        panel._request_add_content_material()
        source = tmp_path / "content.md"
        source.write_text("# 内容", encoding="utf-8")
        panel._content_bindings["文件1"] = compile_content_binding(
            source,
            panel._content_repository(),
            content_id="文件1",
            label="文件1",
        )
        panel._sync_content_material_rows()

        panel._commit_content_material_token(
            "文件1",
            "{{@file:技术路线1}}",
        )

        assert [rule.content_id for rule in panel._content_rules] == ["技术路线1"]
        assert panel._content_rules[0].rule_id == "content:技术路线1"
        assert panel._content_rules[0].anchor_token == "{{@file:技术路线1}}"
        assert "文件1" not in panel._content_bindings
        assert panel._content_bindings["技术路线1"].content_id == "技术路线1"
        assert panel._content_bindings["技术路线1"].label == "技术路线1"
        assert panel._content_material_token_edits["技术路线1"].text() == (
            "{{@file:技术路线1}}"
        )

        archive = panel.current_archive()
        exported = archive.profiles[0]
        assert [rule.content_id for rule in exported.content_rules] == ["技术路线1"]
        assert exported.content_bindings["技术路线1"].artifact_ref == (
            panel._content_bindings["技术路线1"].artifact_ref
        )

        restored = AssetsPanel(PanelBridge())
        try:
            restored.set_archive(archive)
            assert [rule.content_id for rule in restored._content_rules] == [
                "技术路线1"
            ]
            assert "技术路线1" in restored._content_bindings
            assert restored._content_material_token_edits["技术路线1"].text() == (
                "{{@file:技术路线1}}"
            )
        finally:
            restored.close()
    finally:
        panel.close()
