from __future__ import annotations

import ast
from pathlib import Path

import pytest
from PySide6.QtGui import QInputMethodEvent

from src.assistant.ui.conversation_presentation import (
    build_interaction_action_scope,
    build_question_response,
    interaction_action_scope_is_current,
    interaction_is_active,
    project_file_reference,
    project_interaction,
    project_output_references,
)
from src.assistant.ui.conversation_view import AssistantConversationMessage
from src.assistant.ui.creative_home import (
    AssistantCreativeHome,
    AssistantHeroComposer,
)
from src.assistant.ui.interaction_card import AssistantInteractionCard
from src.assistant.ui.message_body_renderer import AssistantMessageBodyRenderer
from src.assistant.ui.message_components import (
    AssistantComposerAttachmentChip,
    AssistantMessageFileCard,
)
from src.assistant.ui.turn_completion_mixin import (
    _provider_reference_is_openable,
)
from src.qt_api import QImage, Qt
from src.shared.ui.icons.catalog import is_icon_registered
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


@pytest.mark.parametrize(
    "reference",
    (
        {"path": "C:/Windows/System32/calc.exe"},
        {"url": "file:///C:/Windows/System32/calc.exe"},
        {"local_path": "C:/tmp/provider.docx"},
    ),
)
def test_provider_side_channel_cannot_open_local_shell_targets(reference):
    assert not _provider_reference_is_openable(reference)


@pytest.mark.parametrize(
    "url",
    ("https://example.com/result", "http://example.com/help", "mailto:a@example.com"),
)
def test_provider_side_channel_may_offer_supported_remote_links(url):
    assert _provider_reference_is_openable({"url": url})


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


def test_question_projection_supports_structured_intake_fields():
    presentation = project_interaction(
        interaction_type="question",
        title="确认公文基本要求",
        body="请选择文种并填写必要信息。",
        payload={
            "confirmation_request": {
                "options": [{"id": "notice", "label": "通知"}],
                "allow_other": True,
                "other_placeholder": "其他文种",
                "choice_columns": 2,
                "initial_choice_count": 1,
                "expand_choices_label": "更多文种（1）",
                "collapse_choices_label": "收起更多文种",
                "input_columns": 2,
                "choices_label": "选择文种",
                "inputs_label": "填写基本信息",
                "submit_label": "生成计划",
                "compact_heading": True,
                "requires_choice": True,
                "inputs": [
                    {
                        "id": "organization",
                        "label": "发文机关",
                        "required": True,
                    },
                    {
                        "id": "purpose",
                        "label": "核心事项",
                        "required": True,
                        "column_span": 2,
                    },
                ],
            }
        },
    )

    assert presentation.other_placeholder == "其他文种"
    assert presentation.choice_columns == 2
    assert presentation.question_input_columns == 2
    assert presentation.initial_choice_count == 1
    assert presentation.choices_label == "选择文种"
    assert presentation.expand_choices_label == "更多文种（1）"
    assert presentation.collapse_choices_label == "收起更多文种"
    assert presentation.inputs_label == "填写基本信息"
    assert presentation.submit_label == "生成计划"
    assert presentation.compact_heading is True
    assert presentation.requires_choice is True
    assert [item.input_id for item in presentation.question_inputs] == [
        "organization",
        "purpose",
    ]
    assert all(item.required for item in presentation.question_inputs)
    assert presentation.question_inputs[-1].column_span == 2


@pytest.mark.parametrize(
    (
        "action_id",
        "label",
        "expected_alignment",
        "expected_variant",
        "expected_icon",
    ),
    (
        ("generate_content_draft", "生成并校验内容", "right", "primary", "sparkles"),
        ("generate_content_draft", "继续生成内容草稿", "right", "primary", "sparkles"),
        ("generate_content_draft", "重新生成", "left", "secondary", "refresh-ccw"),
        ("preflight", "检查并继续", "right", "primary", "file-check-2"),
        ("approve_execute", "确认并生成 Word", "right", "primary", "file-output"),
        ("focus_continuation_response", "填写回复", "right", "primary", "message-circle"),
        (
            "edit_official_plan_requirements",
            "填写公文信息",
            "right",
            "primary",
            "pencil-line",
        ),
        (
            "edit_official_plan_requirements",
            "修改公文信息",
            "left",
            "secondary",
            "pencil-line",
        ),
        ("retry_preflight", "重新检查", "left", "secondary", "refresh-ccw"),
        ("open_workbench", "返回工作台", "left", "secondary", "chevron-left"),
        (
            "runtime_open_reference",
            "打开文档",
            "left",
            "secondary",
            "square-arrow-out-up-right",
        ),
        ("deny_provider_disclosure", "不发送", "left", "secondary", "x"),
    ),
)
def test_ai_card_actions_use_semantic_alignment_and_variant(
    action_id,
    label,
    expected_alignment,
    expected_variant,
    expected_icon,
):
    presentation = project_interaction(
        interaction_type="plan",
        title="动作语义",
        body="",
        payload={"actions": [{"id": action_id, "label": label}]},
    )

    assert len(presentation.actions) == 1
    action = presentation.actions[0]
    assert action.alignment == expected_alignment
    assert action.variant == expected_variant
    assert action.icon_name == expected_icon
    assert is_icon_registered(action.icon_name)


def test_ai_card_explicit_alignment_overrides_generation_semantics():
    presentation = project_interaction(
        interaction_type="artifact",
        title="内容草稿",
        body="",
        payload={
            "actions": [
                {
                    "id": "generate_content_draft",
                    "label": "重新生成",
                    "variant": "primary",
                    "alignment": "left",
                }
            ]
        },
    )

    action = presentation.actions[0]
    assert action.alignment == "left"
    assert action.variant == "secondary"
    assert action.icon_name == "refresh-ccw"


def test_execution_and_artifact_projection_suppress_legacy_explanatory_text():
    progress = project_interaction(
        interaction_type="progress",
        title="正在生成文档",
        body="旧版执行说明",
        payload={"progress_kind": "execution"},
    )
    artifact = project_interaction(
        interaction_type="artifact",
        title="文档已生成",
        body="旧版质量检查说明",
        payload={"execution_id": "execution-1"},
    )
    provider_artifact = project_interaction(
        interaction_type="artifact",
        title="模型返回的参考文件",
        body="这段产物说明有实际含义。",
        payload={
            "reference": {"type": "file", "path": "C:/tmp/reference.docx"},
            "actions": [
                {"id": "runtime_open_reference", "label": "打开产物"}
            ],
        },
    )

    assert progress.body == ""
    assert artifact.body == ""
    assert provider_artifact.body == "这段产物说明有实际含义。"


def test_interaction_activity_comes_from_persisted_form_state():
    assert interaction_is_active(
        interaction_type="question",
        payload={"continuation_ref": {"continuation_id": "q-1"}},
        pending_continuation={"continuation_id": "q-1"},
        active_plan={},
        document_job={},
    )
    assert not interaction_is_active(
        interaction_type="question",
        payload={"continuation_ref": {"continuation_id": "q-1"}},
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
    for running_status in (
        "content_generation_running",
        "content_draft_ready",
        "preflight_running",
        "needs_execution_approval",
        "execution_queued",
        "execution_running",
    ):
        assert not interaction_is_active(
            interaction_type="plan",
            payload={"plan_id": "plan-1", "revision": 2},
            pending_continuation={},
            active_plan={"plan_id": "plan-1", "revision": 2},
            document_job={"status": running_status},
        )


def test_old_question_does_not_reactivate_for_a_new_pending_continuation():
    assert not interaction_is_active(
        interaction_type="question",
        payload={"clarification_id": "question-old"},
        pending_continuation={
            "kind": "local_route_clarification",
            "clarification_id": "question-new",
        },
        active_plan={},
        document_job={"status": "needs_route_clarification"},
    )


def test_action_scope_rejects_state_changes_after_render():
    plan = {"plan_id": "plan-1", "revision": 2}
    job = {
        "job_id": "job-1",
        "status": "content_draft_ready",
        "plan_id": "plan-1",
        "plan_revision": 2,
        "generated_content_draft_id": "draft-1",
    }
    scope = build_interaction_action_scope(
        pending_continuation={},
        active_plan=plan,
        document_job=job,
    )
    assert interaction_action_scope_is_current(
        scope,
        pending_continuation={},
        active_plan=plan,
        document_job=job,
    )
    assert not interaction_action_scope_is_current(
        scope,
        pending_continuation={},
        active_plan=plan,
        document_job={**job, "status": "preflight_running"},
    )
    assert not interaction_action_scope_is_current(
        scope,
        pending_continuation={},
        active_plan=plan,
        document_job=job,
        turn_status="provider_running",
    )


@pytest.mark.parametrize(
    "status",
    (
        "preflight_running",
        "needs_execution_approval",
        "execution_running",
        "success",
        "partial_success",
    ),
)
def test_content_draft_artifact_freezes_after_the_draft_stage(status):
    payload = {"draft_id": "draft-current"}

    assert interaction_is_active(
        interaction_type="artifact",
        payload=payload,
        pending_continuation={},
        active_plan={},
        document_job={
            "status": "content_draft_ready",
            "generated_content_draft_id": "draft-current",
        },
    )
    assert not interaction_is_active(
        interaction_type="artifact",
        payload=payload,
        pending_continuation={},
        active_plan={},
        document_job={
            "status": status,
            "generated_content_draft_id": "draft-current",
        },
    )


def test_only_the_latest_completed_artifact_keeps_output_actions_active():
    current_job = {
        "status": "success",
        "execution_id": "execution-current",
    }

    assert interaction_is_active(
        interaction_type="artifact",
        payload={"execution_id": "execution-current"},
        pending_continuation={},
        active_plan={},
        document_job=current_job,
    )
    assert not interaction_is_active(
        interaction_type="artifact",
        payload={"execution_id": "execution-old"},
        pending_continuation={},
        active_plan={},
        document_job=current_job,
    )
    assert not interaction_is_active(
        interaction_type="artifact",
        payload={},
        pending_continuation={},
        active_plan={},
        document_job=current_job,
    )


def test_provider_artifacts_remain_readable_but_legacy_workflow_actions_do_not():
    provider_payload = {
        "reference": {"type": "file", "path": "C:/tmp/provider.docx"},
        "actions": [
            {"id": "runtime_open_reference", "label": "打开产物"}
        ],
    }
    assert interaction_is_active(
        interaction_type="artifact",
        payload=provider_payload,
        pending_continuation={},
        active_plan={},
        document_job={"status": "response_ready"},
    )
    assert not interaction_is_active(
        interaction_type="artifact",
        payload={
            "reference": {"type": "file", "path": "C:/tmp/legacy.docx"},
            "actions": [{"id": "open_artifact", "label": "打开文档"}],
        },
        pending_continuation={},
        active_plan={},
        document_job={"status": "success", "execution_id": "new"},
    )


def test_only_latest_recovery_card_can_offer_retry_actions():
    base = {
        "interaction_type": "recovery",
        "pending_continuation": {},
        "active_plan": {},
        "document_job": {"status": "failed"},
    }
    assert interaction_is_active(
        payload={
            "_is_latest_recovery": True,
            "actions": [{"id": "retry_provider_request"}],
        },
        **base,
    )
    assert not interaction_is_active(
        payload={
            "_is_latest_recovery": False,
            "actions": [{"id": "retry_provider_request"}],
        },
        **base,
    )


def test_completed_job_renders_the_content_draft_actions_as_frozen(qapp):
    payload = {
        "draft_id": "draft-current",
        "actions": [
            {
                "id": "open_content_draft",
                "label": "打开内容草稿",
                "variant": "primary",
            },
            {
                "id": "regenerate_content_draft",
                "label": "重新生成",
                "variant": "secondary",
            },
        ],
    }
    payload["active"] = interaction_is_active(
        interaction_type="artifact",
        payload=payload,
        pending_continuation={},
        active_plan={},
        document_job={
            "status": "success",
            "generated_content_draft_id": "draft-current",
            "execution_id": "execution-current",
        },
    )
    card = AssistantInteractionCard(
        interaction_type="artifact",
        title="内容草稿已生成",
        body="",
        payload=payload,
    )
    try:
        qapp.processEvents()
        assert card._buttons
        assert all(not button.isEnabled() for button in card._buttons)
    finally:
        card.close()


def test_read_only_reference_action_remains_enabled_on_a_frozen_card(qapp):
    card = AssistantInteractionCard(
        interaction_type="artifact",
        title="历史参考产物",
        body="仍可回看这个文件。",
        payload={
            "active": False,
            "reference": {"type": "file", "path": "C:/tmp/reference.docx"},
            "actions": [
                {"id": "runtime_open_reference", "label": "打开产物"},
                {"id": "preflight", "label": "继续执行"},
            ],
        },
    )
    try:
        qapp.processEvents()
        assert card._buttons[0].isEnabled()
        assert not card._buttons[1].isEnabled()
    finally:
        card.close()


def test_content_generation_progress_is_bound_to_one_generation_attempt():
    current_job = {
        "status": "content_generation_running",
        "content_generation_id": "generation-new",
    }

    assert interaction_is_active(
        interaction_type="progress",
        payload={
            "progress_kind": "content_generation",
            "generation_id": "generation-new",
        },
        pending_continuation={},
        active_plan={},
        document_job=current_job,
    )
    assert not interaction_is_active(
        interaction_type="progress",
        payload={
            "progress_kind": "content_generation",
            "generation_id": "generation-old",
        },
        pending_continuation={},
        active_plan={},
        document_job=current_job,
    )
    assert not interaction_is_active(
        interaction_type="recovery",
        payload={},
        pending_continuation={},
        active_plan={},
        document_job=current_job,
    )
    assert not interaction_is_active(
        interaction_type="progress",
        payload={"ephemeral": True},
        pending_continuation={},
        active_plan={},
        document_job=current_job,
    )
    assert interaction_is_active(
        interaction_type="progress",
        payload={
            "progress_kind": "preflight",
            "preflight_run_id": "preflight-new",
        },
        pending_continuation={},
        active_plan={},
        document_job={
            "status": "preflight_running",
            "preflight_run_id": "preflight-new",
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
        assert not composer._text_edit.acceptDrops()
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


def test_composer_accumulates_docx_and_markdown_as_material_chips(
    qapp,
    tmp_path,
):
    docx_path = tmp_path / "参考材料.docx"
    markdown_path = tmp_path / "补充要求.md"
    docx_path.write_bytes(b"placeholder")
    markdown_path.write_text("# 补充要求", encoding="utf-8")
    composer = AssistantHeroComposer(PanelBridge(), mode="hero")
    emitted: list[tuple[str, ...]] = []
    composer.document_paths_changed.connect(
        lambda paths: emitted.append(tuple(paths))
    )
    try:
        composer._add_document_paths((str(docx_path), str(markdown_path)))
        qapp.processEvents()

        expected = (str(docx_path.resolve()), str(markdown_path.resolve()))
        assert composer.document_paths() == expected
        assert composer.document_path() == expected[0]
        assert len(composer._attachment_chips) == 2
        assert emitted == [expected]
        assert composer._attachment_button.text() == "添加材料"

        composer._clear_attachment(expected[0])
        qapp.processEvents()

        assert composer.document_paths() == (expected[1],)
        assert len(composer._attachment_chips) == 1
        assert emitted[-1] == (expected[1],)
    finally:
        composer.close()


def test_composer_keeps_six_material_chips_reachable_in_narrow_layout(
    qapp,
    tmp_path,
):
    paths: list[str] = []
    for index in range(6):
        path = tmp_path / f"material-with-long-name-{index}.md"
        path.write_text(f"# Material {index}", encoding="utf-8")
        paths.append(str(path))
    composer = AssistantHeroComposer(PanelBridge(), mode="hero")
    try:
        composer.resize(560, 220)
        composer.show()
        composer._add_document_paths(tuple(paths))
        qapp.processEvents()
        qapp.processEvents()

        bar = composer._attachment_scroll.horizontalScrollBar()
        assert len(composer._attachment_chips) == 6
        assert bar.maximum() > 0
        assert composer._attachment_previous.isVisible()
        assert composer._attachment_next.isVisible()
        assert bar.value() == bar.maximum()

        composer._attachment_previous.click()
        qapp.processEvents()

        assert bar.value() < bar.maximum()
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


def test_creative_home_caches_grid_and_pauses_animation_while_editing(qapp):
    home = AssistantCreativeHome(PanelBridge())
    try:
        home.resize(1450, 1000)
        home.show()
        home.composer._model_settings_button.setFocus()
        qapp.processEvents()

        first = home._grid_static_pixmap(home.width(), home.height())
        second = home._grid_static_pixmap(home.width(), home.height())
        assert first is second

        home.set_grid_animation_active(True)
        assert home._grid_timer.isActive()
        home.composer._text_edit.setFocus()
        qapp.processEvents()
        assert home._grid_interaction_suspended is True
        assert not home._grid_timer.isActive()

        home.composer._model_settings_button.setFocus()
        qapp.processEvents()
        assert home._grid_interaction_suspended is False
        assert home._grid_timer.isActive()

        home._invalidate_grid_static_cache()
        assert home._grid_static_cache is None
        assert home._grid_static_pixmap(home.width(), home.height()) is not first
    finally:
        home.close()


def test_creative_home_treats_ime_preedit_as_active_editing(qapp):
    home = AssistantCreativeHome(PanelBridge())
    try:
        home.resize(960, 720)
        home.show()
        home.composer._model_settings_button.setFocus()
        qapp.processEvents()
        assert home._grid_interaction_suspended is False

        home.composer._text_edit.inputMethodEvent(
            QInputMethodEvent("正在拼写", [])
        )
        assert home._grid_interaction_suspended is True

        home.composer._text_edit.inputMethodEvent(QInputMethodEvent("", []))
        assert home._grid_interaction_suspended is False
    finally:
        home.close()


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


def test_user_message_uses_natural_text_width_before_wrapping(qapp):
    chinese_request = "帮我生成一份小学六年级的期中英语考试试卷"
    spaced_request = (
        "Please create a midterm English exam paper for sixth-grade "
        "primary school students"
    )
    chinese_message = AssistantConversationMessage(
        text=chinese_request,
        role="user",
    )
    spaced_message = AssistantConversationMessage(
        text=spaced_request,
        role="user",
    )
    try:
        chinese_message.resize(1408, 100)
        spaced_message.resize(1408, 100)
        chinese_message.show()
        spaced_message.show()
        qapp.processEvents()

        chinese_metrics = chinese_message._body_label.fontMetrics()
        chinese_text_width = chinese_metrics.horizontalAdvance(chinese_request)
        assert chinese_message._bubble.width() == chinese_text_width + 28
        assert (
            spaced_message._body_label.fontMetrics().horizontalAdvance(spaced_request)
            > 640
        )
        assert spaced_message._bubble.width() == 640
    finally:
        chinese_message.close()
        spaced_message.close()


def test_user_message_width_stays_compact_and_respects_narrow_reading_area(qapp):
    short_message = AssistantConversationMessage(text="好的", role="user")
    long_message = AssistantConversationMessage(
        text="Please create a complete examination paper with answers. " * 6,
        role="user",
    )
    try:
        short_message.resize(1408, 100)
        long_message.resize(520, 160)
        short_message.show()
        long_message.show()
        qapp.processEvents()

        assert short_message._bubble.width() < 120
        assert long_message._bubble.width() == 424
        bubble_origin = long_message._bubble.mapTo(
            long_message,
            long_message._bubble.rect().topLeft(),
        )
        assert bubble_origin.x() + long_message._bubble.width() == 472
    finally:
        short_message.close()
        long_message.close()


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
        assert not card._body.isHidden()
        assert card._body.text() == "全部产物已通过检查。"
        assert len(card._file_cards) == 2
        assert all(item.height() == 92 for item in card._file_cards)
        card._file_cards[1]._open.click()
        qapp.processEvents()
        assert emitted[0][0] == "runtime_open_reference"
        assert emitted[0][1]["reference"]["path"] == str(second)
    finally:
        card.close()


def test_artifact_card_hides_empty_body_and_generic_file_description(qapp, tmp_path):
    output = tmp_path / "数学期中考试试卷_学生卷.docx"
    output.write_bytes(b"docx")
    card = AssistantInteractionCard(
        interaction_type="artifact",
        title="文档已生成",
        body="",
        payload={
            "references": [{"path": str(output), "title": output.name}],
            "actions": [],
        },
    )
    try:
        qapp.processEvents()
        assert card._body.isHidden()
        assert len(card._file_cards) == 1
        assert card._file_cards[0]._subtitle.isHidden()
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


def test_question_card_preserves_manual_official_field_text(qapp):
    card = AssistantInteractionCard(
        interaction_type="question",
        title="请补充发文机关",
        body="可采用建议，也可填写准确值。",
        payload={
            "completion_id": "official-field-1",
            "confirmation_request": {
                "kind": "official_field_completion",
                "options": [
                    {
                        "id": "auto_suggestion",
                        "label": "采用建议：本单位（待确认）",
                    }
                ],
                "selection_mode": "single",
                "allow_other": True,
            },
        },
    )
    emitted: list[tuple[str, object]] = []
    card.action_requested.connect(
        lambda action, payload: emitted.append((action, payload))
    )
    try:
        assert card._other_input is not None
        card._other_input.setText("示例市档案局")
        qapp.processEvents()
        assert card._question_submit is not None
        assert card._question_submit.isEnabled()
        card._question_submit.click()
        qapp.processEvents()
        assert emitted[0][0] == "submit_question_answer"
        assert emitted[0][1]["other_text"] == "示例市档案局"
        assert emitted[0][1]["completion_id"] == "official-field-1"
    finally:
        card.close()


def test_question_card_requires_and_submits_structured_official_intake(qapp):
    card = AssistantInteractionCard(
        interaction_type="question",
        title="确认公文基本要求",
        body="",
        payload={
            "clarification_id": "official-intake-1",
            "confirmation_request": {
                "options": [
                    {"id": "notice", "label": "通知"},
                    {"id": "report", "label": "报告"},
                ],
                "allow_other": True,
                "other_placeholder": "其他文种",
                "choice_columns": 2,
                "input_columns": 2,
                "choices_label": "选择文种",
                "inputs_label": "填写基本信息",
                "submit_label": "生成计划",
                "compact_heading": True,
                "requires_choice": True,
                "inputs": [
                    {
                        "id": "organization",
                        "label": "发文机关",
                        "required": True,
                    },
                    {
                        "id": "recipient",
                        "label": "主送对象",
                    },
                    {
                        "id": "purpose",
                        "label": "核心事项",
                        "required": True,
                        "column_span": 2,
                    },
                ],
            },
        },
    )
    emitted: list[tuple[str, object]] = []
    card.action_requested.connect(
        lambda action, payload: emitted.append((action, payload))
    )
    try:
        card.setFixedWidth(760)
        card.show()
        qapp.processEvents()
        assert card._uses_compact_heading is True
        assert card._type_icon.size().width() == 30
        assert card._type_icon.alignment() == Qt.AlignCenter
        assert card._body.isHidden()
        assert card._other_input is not None
        assert card._other_input.placeholderText() == "其他文种"
        assert card._question_submit is not None
        assert card._question_submit.text() == "生成计划"
        assert card._choice_buttons[0].y() == card._choice_buttons[1].y()
        organization = card._question_inputs["organization"]
        recipient = card._question_inputs["recipient"]
        purpose = card._question_inputs["purpose"]
        assert organization.mapTo(card, organization.rect().topLeft()).y() == (
            recipient.mapTo(card, recipient.rect().topLeft()).y()
        )
        assert purpose.width() > organization.width()
        assert purpose.mapTo(card, purpose.rect().topLeft()).y() > (
            organization.mapTo(card, organization.rect().topLeft()).y()
        )
        assert card._question_submit.mapTo(
            card,
            card._question_submit.rect().topLeft(),
        ).x() > card.width() // 2
        card._choice_buttons[0].click()
        assert not card._question_submit.isEnabled()
        card._question_inputs["organization"].setText("示例市教育局")
        card._question_inputs["purpose"].setText("开展秋季校园安全检查")
        qapp.processEvents()
        assert card._question_submit.isEnabled()
        card._question_submit.click()
        qapp.processEvents()

        assert emitted[0][0] == "submit_question_answer"
        assert emitted[0][1]["selected_choice_ids"] == ["notice"]
        assert emitted[0][1]["field_values"] == {
            "organization": "示例市教育局",
            "purpose": "开展秋季校园安全检查",
        }
    finally:
        card.close()


def test_question_card_collapses_infrequent_choices_until_requested(qapp):
    card = AssistantInteractionCard(
        interaction_type="question",
        title="确认公文基本要求",
        body="",
        payload={
            "confirmation_request": {
                "options": [
                    {"id": "notice", "label": "通知"},
                    {"id": "report", "label": "报告"},
                    {"id": "resolution", "label": "决议"},
                    {"id": "order", "label": "命令（令）"},
                ],
                "choice_columns": 2,
                "initial_choice_count": 2,
                "expand_choices_label": "更多文种（2）",
                "collapse_choices_label": "收起更多文种",
            }
        },
    )
    try:
        card.show()
        qapp.processEvents()
        assert [button.isVisible() for button in card._choice_buttons] == [
            True,
            True,
            False,
            False,
        ]
        assert card._choice_toggle is not None
        assert card._choice_toggle.text() == "更多文种（2）"

        card._choice_toggle.click()
        qapp.processEvents()
        assert all(button.isVisible() for button in card._choice_buttons)
        assert card._choice_toggle.text() == "收起更多文种"

        card._choice_toggle.click()
        qapp.processEvents()
        assert [button.isVisible() for button in card._choice_buttons] == [
            True,
            True,
            False,
            False,
        ]
    finally:
        card.close()


def test_plan_and_progress_cards_use_task_specific_visual_density(qapp):
    plan = AssistantInteractionCard(
        interaction_type="plan",
        title="小学六年级英语期中考试",
        body="",
        payload={
            "facts": [
                {"label": "年级", "value": "小学六年级"},
                {"label": "学科", "value": "英语"},
            ],
            "notices": ["发现一项需要确认的格式设置。"],
        },
    )
    progress = AssistantInteractionCard(
        interaction_type="progress",
        title="正在起草文档内容",
        body="",
        payload={"ephemeral": True},
    )
    try:
        plan.show()
        progress.show()
        qapp.processEvents()

        assert plan.preferred_width(820) == 760
        assert progress.preferred_width(820) == 760
        assert plan.preferred_width(424) == 424
        assert plan._type_icon.size().width() == 30
        assert plan._fact_host is not None
        assert plan._fact_host.testAttribute(Qt.WA_StyledBackground)
        assert plan._body.property("variant") == "notice"
        assert plan._body.text() == "发现一项需要确认的格式设置。"
        assert progress._progress is not None
        assert progress._progress.maximumWidth() == 180
        assert progress._type_icon.size().width() == 30
        assert progress._body.isHidden()
        assert {
            card._type_icon.mapTo(card, card._type_icon.rect().topLeft()).x()
            for card in (plan, progress)
        } == {15}
    finally:
        plan.close()
        progress.close()


def test_preflight_card_keeps_blockers_visible_when_facts_and_notices_exist(qapp):
    card = AssistantInteractionCard(
        interaction_type="preflight",
        title="执行前检查未通过",
        body="• 内容草稿缺少发文机关，请在当前对话中补充。",
        payload={
            "facts": [{"label": "输出目录", "value": "C:/Outputs"}],
            "notices": ["成文日期已暂按当天日期填写。"],
            "actions": [],
        },
    )
    try:
        card.show()
        qapp.processEvents()

        assert card.presentation.tone == "danger"
        assert card._uses_compact_heading is True
        assert "内容草稿缺少发文机关" in card._body.text()
        assert "成文日期已暂按当天日期填写" in card._body.text()
    finally:
        card.close()


def test_preflight_card_keeps_blockers_visible_when_no_notice_exists(qapp):
    card = AssistantInteractionCard(
        interaction_type="preflight",
        title="执行前检查未通过",
        body="• 当前模板不可用，请重新选择模板。",
        payload={
            "facts": [{"label": "输出目录", "value": "C:/Outputs"}],
            "actions": [],
        },
    )
    try:
        card.show()
        qapp.processEvents()

        assert card._body.isVisible()
        assert "当前模板不可用" in card._body.text()
    finally:
        card.close()


def test_workflow_cards_share_width_heading_alignment_and_action_freeze(qapp):
    plan = AssistantInteractionCard(
        interaction_type="plan",
        title="小学六年级英语期中考试",
        body="",
        payload={
            "active": True,
            "actions": [
                {
                    "id": "generate_content_draft",
                    "label": "生成并校验题稿",
                    "variant": "primary",
                },
                {
                    "id": "edit_exam_plan_requirements",
                    "label": "修改要求",
                    "variant": "secondary",
                },
            ],
        },
    )
    artifact = AssistantInteractionCard(
        interaction_type="artifact",
        title="内容草稿已生成",
        body="",
        payload={"actions": []},
    )
    progress = AssistantInteractionCard(
        interaction_type="progress",
        title="正在起草文档内容",
        body="",
        payload={"actions": []},
    )
    recovery = AssistantInteractionCard(
        interaction_type="recovery",
        title="当前操作未执行",
        body="当前任务状态已经变化。",
        payload={"actions": []},
    )
    emitted: list[str] = []
    plan.action_requested.connect(
        lambda action, _payload: emitted.append(action)
    )
    try:
        cards = (plan, progress, artifact, recovery)
        for card in cards:
            card.setFixedWidth(card.preferred_width(820))
            card.show()
        qapp.processEvents()

        assert {
            card.preferred_width(820) for card in cards
        } == {760}
        assert artifact._type_icon.width() == 30
        assert recovery._type_icon.width() == 30
        assert artifact._body.isHidden()
        icon_left_edges = {
            card._type_icon.mapTo(card, card._type_icon.rect().topLeft()).x()
            for card in cards
        }
        assert icon_left_edges == {15}
        for card in cards:
            assert card._type_icon.alignment() == Qt.AlignCenter
            centers = {
                widget.mapTo(card, widget.rect().center()).y()
                for widget in (
                    card._type_icon,
                    card._eyebrow,
                    card._title,
                )
            }
            assert max(centers) - min(centers) <= 1
            title_right = card._title.mapTo(
                card,
                card._title.rect().topRight(),
            ).x()
            assert title_right == card.width() - 16
            assert card._title.fontMetrics().height() < (
                card._eyebrow.fontMetrics().height()
            )
            assert card._title.font().weight() < card._eyebrow.font().weight()

        buttons = {
            str(button.property("actionId")): button
            for button in plan._buttons
        }
        generate_button = buttons["generate_content_draft"]
        edit_button = buttons["edit_exam_plan_requirements"]
        assert edit_button.x() < plan.width() // 2
        assert generate_button.x() > plan.width() // 2
        assert edit_button.property("variant") == "secondary"
        assert generate_button.property("variant") == "primary"

        generate_button.click()
        qapp.processEvents()
        assert emitted == ["generate_content_draft"]
        assert all(not button.isEnabled() for button in plan._buttons)
    finally:
        plan.close()
        progress.close()
        artifact.close()
        recovery.close()


def test_content_draft_actions_split_secondary_left_and_primary_right(qapp):
    card = AssistantInteractionCard(
        interaction_type="artifact",
        title="内容草稿已生成",
        body="",
        payload={
            "active": True,
            "draft_id": "draft-current",
            "actions": [
                {
                    "id": "open_content_draft",
                    "label": "打开草稿",
                    "variant": "secondary",
                    "alignment": "left",
                },
                {
                    "id": "generate_content_draft",
                    "label": "重新生成",
                    "variant": "secondary",
                    "alignment": "left",
                },
                {
                    "id": "preflight",
                    "label": "生成 Word",
                    "variant": "primary",
                    "alignment": "right",
                },
            ],
        },
    )
    try:
        card.setFixedWidth(760)
        card.show()
        qapp.processEvents()

        buttons = {
            str(button.property("actionId")): button
            for button in card._buttons
        }
        open_button = buttons["open_content_draft"]
        regenerate_button = buttons["generate_content_draft"]
        word_button = buttons["preflight"]

        assert open_button.text() == "打开草稿"
        assert regenerate_button.text() == "重新生成"
        assert word_button.text() == "生成 Word"
        assert open_button.property("variant") == "secondary"
        assert regenerate_button.property("variant") == "secondary"
        assert word_button.property("variant") == "primary"
        assert open_button.property("iconName") == "file-text"
        assert regenerate_button.property("iconName") == "refresh-ccw"
        assert word_button.property("iconName") == "file-output"
        assert all(not button.icon().isNull() for button in card._buttons)
        assert open_button.x() < regenerate_button.x() < card.width() // 2
        assert word_button.x() > card.width() // 2
        assert word_button.geometry().right() >= card.width() - 16
    finally:
        card.close()


def test_question_card_keeps_skip_left_and_submit_right(qapp):
    card = AssistantInteractionCard(
        interaction_type="question",
        title="请选择下一步",
        body="",
        payload={
            "active": True,
            "confirmation_request": {
                "options": [{"id": "continue", "label": "继续"}],
                "allow_skip": True,
                "submit_label": "下一步",
            },
        },
    )
    try:
        card.setFixedWidth(760)
        card.show()
        qapp.processEvents()

        assert card._question_skip is not None
        assert card._question_submit is not None
        assert card._question_skip.x() < card.width() // 2
        assert card._question_submit.x() > card.width() // 2
        assert card._question_submit.property("variant") == "primary"
        assert card._question_skip.property("iconName") == "skip-forward"
        assert card._question_submit.property("iconName") == "chevron-right"
        assert not card._question_skip.icon().isNull()
        assert not card._question_submit.icon().isNull()
    finally:
        card.close()
