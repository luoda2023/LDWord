from __future__ import annotations

import ast
from pathlib import Path

from src.assistant.ui.conversation_presentation import (
    build_question_response,
    interaction_is_active,
    project_file_reference,
    project_interaction,
    project_output_references,
)
from src.assistant.ui.conversation_view import AssistantConversationMessage
from src.assistant.ui.creative_home import AssistantHeroComposer
from src.assistant.ui.interaction_card import AssistantInteractionCard
from src.assistant.ui.message_body_renderer import AssistantMessageBodyRenderer
from src.assistant.ui.message_components import (
    AssistantComposerAttachmentChip,
    AssistantMessageFileCard,
)
from src.qt_api import QImage
from src.ui.bridge import PanelBridge


def test_conversation_projection_has_no_qt_or_panel_dependency():
    path = Path("src/assistant/ui/conversation_presentation.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imported.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert not any(name.startswith("src.qt_api") for name in imported)
    assert not any(name.endswith("assistant_panel") for name in imported)


def test_file_projection_distinguishes_available_missing_and_external(tmp_path):
    available = tmp_path / "source.docx"
    available.write_bytes(b"docx")

    projected = project_file_reference({"path": str(available)})
    missing = project_file_reference({"path": str(tmp_path / "missing.pdf")})
    external = project_file_reference(
        {"title": "产品资料", "url": "https://example.com/source"}
    )

    assert projected.title == "source.docx"
    assert projected.suffix == "DOCX"
    assert projected.state == "available"
    assert missing.suffix == "PDF"
    assert missing.state == "missing"
    assert external.kind == "link"
    assert external.state == "external"


def test_question_projection_and_response_are_provider_neutral():
    presentation = project_interaction(
        interaction_type="question",
        title="选择输出范围",
        body="请选择一个或多个范围。",
        payload={
            "confirmation_request": {
                "options": [
                    {"id": "student", "label": "学生卷"},
                    {"id": "answer", "label": "答案卷"},
                ],
                "multiple": True,
                "allow_other": True,
                "allow_skip": True,
            }
        },
    )

    assert presentation.multiple is True
    assert presentation.allow_other is True
    assert presentation.can_skip is True
    assert [item.choice_id for item in presentation.choices] == ["student", "answer"]
    assert build_question_response(("学生卷", "答案卷")) == "学生卷；答案卷"


def test_interaction_activity_comes_from_persisted_form_state():
    assert interaction_is_active(
        interaction_type="question",
        payload={},
        pending_continuation={"continuation_id": "q-1"},
        active_plan={},
        document_job={},
    )
    assert not interaction_is_active(
        interaction_type="question",
        payload={},
        pending_continuation={},
        active_plan={},
        document_job={},
    )
    assert interaction_is_active(
        interaction_type="approval",
        payload={"preflight_id": "preflight-1"},
        pending_continuation={},
        active_plan={},
        document_job={
            "status": "needs_execution_approval",
            "preflight": {"preflight_id": "preflight-1"},
        },
    )


def test_output_projection_keeps_every_execution_artifact(tmp_path):
    student = tmp_path / "学生卷.docx"
    answer = tmp_path / "答案卷.docx"
    student.write_bytes(b"student")
    answer.write_bytes(b"answer")

    references = project_output_references(
        {
            "output_path": str(student),
            "output_paths": {
                "student": str(student),
                "answer_key": str(answer),
            },
        }
    )

    assert [item["artifact_key"] for item in references] == [
        "student",
        "answer_key",
    ]
    assert [item["title"] for item in references] == ["学生卷.docx", "答案卷.docx"]


def test_design_file_components_render_composer_attachment_and_message_card(
    qapp,
    tmp_path,
):
    source = tmp_path / "材料.docx"
    source.write_bytes(b"docx")
    reference = {"title": source.name, "path": str(source), "type": "file"}
    chip = AssistantComposerAttachmentChip(reference)
    message = AssistantConversationMessage(
        text="请按附件生成。",
        role="user",
        source_refs=(reference,),
    )
    try:
        qapp.processEvents()
        assert chip.height() == 34
        assert chip.maximumWidth() == 268
        cards = message.findChildren(AssistantMessageFileCard)
        assert len(cards) == 1
        assert cards[0].variant == "attachment"
        assert cards[0].size().width() == 138
        assert cards[0].size().height() == 108
    finally:
        chip.close()
        message.close()


def test_composer_exposes_design_drop_overlay_without_changing_submission_owner(qapp):
    composer = AssistantHeroComposer(PanelBridge(), mode="compact")
    try:
        composer.resize(960, 154)
        composer.show()
        qapp.processEvents()
        assert composer.acceptDrops()
        assert composer._drop_overlay.isHidden()
        assert composer._drop_overlay.geometry() == composer.rect()
        assert composer._submission_handler is None
        assert composer._attachment_slot.height() == 0
        assert composer._text_edit.geometry().y() == 33
        assert composer._text_edit.height() == 52
        assert composer._send_btn.geometry().y() == 100
        assert composer._send_btn.size().width() == 32
    finally:
        composer.close()


def test_hero_composer_uses_design_editor_and_footer_geometry(qapp):
    composer = AssistantHeroComposer(PanelBridge(), mode="hero")
    try:
        composer.resize(1180, 220)
        composer.show()
        qapp.processEvents()
        assert composer.layout().spacing() == 10
        assert composer._attachment_slot.height() == 0
        assert composer._text_edit.geometry().y() == 30
        assert composer._text_edit.height() == 84
        assert composer._send_btn.geometry().y() == 166
        assert composer._send_btn.size().width() == 36
    finally:
        composer.close()


def test_assistant_body_applies_runtime_markdown_typography(qapp):
    message = AssistantConversationMessage(
        text=(
            "# 一级标题\n\n正文内容\n\n## 二级标题\n\n"
            "### 三级标题\n\n> 引用\n\n```text\ncode\n```\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |"
        ),
        role="assistant",
    )
    try:
        qapp.processEvents()
        document = message._markdown.document()
        css = document.defaultStyleSheet()
        for selector in ("h1", "blockquote", "pre", "table", "th", "td"):
            assert selector in css

        blocks = []
        block = document.begin()
        while block.isValid():
            fragment = block.begin().fragment()
            blocks.append(
                (
                    block.text(),
                    block.blockFormat(),
                    fragment.charFormat().font() if fragment.isValid() else None,
                )
            )
            block = block.next()

        heading1 = next(item for item in blocks if item[0] == "一级标题")
        body = next(item for item in blocks if item[0] == "正文内容")
        heading2 = next(item for item in blocks if item[0] == "二级标题")
        heading3 = next(item for item in blocks if item[0] == "三级标题")
        quote = next(item for item in blocks if item[0] == "引用")
        code = next(item for item in blocks if item[0] == "code")

        assert heading1[2].pixelSize() == 28
        assert heading2[2].pixelSize() == 21
        assert heading3[2].pixelSize() == 17
        assert body[2].pixelSize() == 14
        assert heading1[1].lineHeight() == 134
        assert body[1].lineHeight() == 146
        assert heading1[1].leftMargin() == 12
        assert heading1[1].bottomMargin() == 6
        assert body[1].bottomMargin() == 9
        assert quote[1].leftMargin() == 25
        assert quote[1].rightMargin() == 12
        assert code[1].nonBreakableLines() is False
    finally:
        message.close()


def test_assistant_message_geometry_keeps_compact_rows_on_one_reading_axis(qapp):
    assistant = AssistantConversationMessage(
        text="已完成结构检查。",
        role="assistant",
    )
    user = AssistantConversationMessage(
        text="请检查结构。",
        role="user",
    )
    try:
        for message in (assistant, user):
            message.resize(746, 100)
            message.show()
        qapp.processEvents()

        assistant_origin = assistant._assistant_body.mapTo(
            assistant,
            assistant._assistant_body.rect().topLeft(),
        )
        bubble_origin = user._bubble.mapTo(
            user,
            user._bubble.rect().topLeft(),
        )
        assert assistant_origin.x() == 48
        assert assistant._assistant_body.width() == 650
        assert bubble_origin.x() + user._bubble.width() == 698
    finally:
        assistant.close()
        user.close()


def test_assistant_markdown_geometry_wraps_code_scales_images_and_extends_heading_axis(
    qapp,
    tmp_path,
):
    image_path = tmp_path / "wide.png"
    image = QImage(1200, 600, QImage.Format_RGB32)
    image.fill("#2F7CF6")
    assert image.save(str(image_path))

    renderer = AssistantMessageBodyRenderer()
    try:
        renderer.resize(480, 40)
        renderer.set_markdown(
            "# 这是一个用于验证多行标题强调轴高度的很长很长很长很长的标题\n\n"
            "```text\n"
            "THIS_IS_A_VERY_LONG_UNBROKEN_CODE_LINE_0123456789_"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz_END\n"
            "```\n\n"
            f"![预览]({image_path.as_uri()})"
        )
        renderer.show()
        qapp.processEvents()

        document = renderer.document()
        assert document.documentLayout().documentSize().width() <= 480
        assert renderer.horizontalScrollBar().maximum() == 0

        heading_block = document.begin()
        assert heading_block.layout().lineCount() > 1
        heading_rect = document.documentLayout().blockBoundingRect(heading_block)
        axis_rect = renderer._heading_axis_rects()[0][1]
        assert axis_rect.height() == heading_rect.height()

        image_width = 0
        block = document.begin()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid() and fragment.charFormat().isImageFormat():
                    image_width = round(fragment.charFormat().toImageFormat().width())
                iterator += 1
            block = block.next()
        assert image_width == 420
    finally:
        renderer.close()


def test_artifact_card_renders_all_files_and_opens_selected_reference(qapp, tmp_path):
    first = tmp_path / "学生卷.docx"
    second = tmp_path / "答案卷.docx"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    card = AssistantInteractionCard(
        interaction_type="artifact",
        title="文档已生成",
        body="全部产物已通过检查。",
        payload={
            "references": [
                {"path": str(first), "title": first.name},
                {"path": str(second), "title": second.name},
            ],
            "actions": [],
        },
    )
    emitted: list[tuple[str, object]] = []
    card.action_requested.connect(
        lambda action, payload: emitted.append((action, payload))
    )
    try:
        qapp.processEvents()
        assert len(card._file_cards) == 2
        assert all(item.height() == 92 for item in card._file_cards)
        card._file_cards[1]._open.click()
        qapp.processEvents()
        assert emitted[0][0] == "runtime_open_reference"
        assert emitted[0][1]["reference"]["path"] == str(second)
    finally:
        card.close()


def test_question_card_submits_selected_values_through_existing_turn_path(qapp):
    card = AssistantInteractionCard(
        interaction_type="question",
        title="选择交付物",
        body="请选择。",
        payload={
            "confirmation_request": {
                "options": [
                    {"id": "student", "label": "学生卷"},
                    {"id": "answer", "label": "答案卷"},
                ],
                "multiple": True,
            }
        },
    )
    emitted: list[tuple[str, object]] = []
    card.action_requested.connect(
        lambda action, payload: emitted.append((action, payload))
    )
    try:
        card._choice_buttons[0].click()
        card._choice_buttons[1].click()
        qapp.processEvents()
        assert card._question_submit is not None
        assert card._question_submit.isEnabled()
        card._question_submit.click()
        qapp.processEvents()
        assert emitted[0][0] == "submit_question_answer"
        assert emitted[0][1]["response"] == "学生卷；答案卷"
    finally:
        card.close()
