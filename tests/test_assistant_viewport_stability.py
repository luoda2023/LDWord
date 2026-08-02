from __future__ import annotations

from src.assistant.application.session_coordinator import (
    AssistantSessionCoordinator,
)
from src.assistant.contracts.messages import (
    ROLE_ASSISTANT,
    ROLE_USER,
    AssistantMessage,
)
from src.assistant.storage.session_store import AssistantSessionStore
from src.assistant.ui.assistant_panel import AssistantPanel
from src.assistant.ui.interaction_card import AssistantInteractionCard
from src.qt_api import Qt
from src.ui.bridge import PanelBridge


_PLAN_FACTS = (
    {"label": "任务", "value": "公文、会议或政策文档"},
    {"label": "操作", "value": "起草新文档"},
    {"label": "输入", "value": "由 AI 生成"},
    {"label": "模式", "value": "公文版"},
    {"label": "方案", "value": "公文基础方案"},
    {"label": "模板", "value": "GB/T 9704 公文格式"},
    {
        "label": "输出",
        "value": r"C:\Users\Example\Documents\Alavette-Form-Outputs",
    },
    {"label": "交付", "value": "最终文档、material_manifest"},
)


def _panel(tmp_path) -> tuple[AssistantPanel, AssistantSessionCoordinator]:
    coordinator = AssistantSessionCoordinator(
        AssistantSessionStore(tmp_path / "sessions")
    )
    panel = AssistantPanel(
        PanelBridge(),
        coordinator=coordinator,
        first_level=True,
    )
    panel.resize(1180, 620)
    panel.show()
    return panel, coordinator


def _session_with_plans(coordinator, *, count: int):
    session = coordinator.create_session(title="我要发一个公文")
    session = coordinator.append_message(
        session,
        AssistantMessage.text(
            role=ROLE_USER,
            text=(
                "公文文种：函；发文机关：芜湖教育局；"
                "主送机关：合肥教育局；核心事项：落实教材改革"
            ),
        ),
    )
    for _index in range(count):
        session = coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="plan",
                title="公文处理计划",
                body="",
                payload={"facts": list(_PLAN_FACTS), "actions": []},
            ),
        )
    return session


def _append_active_progress(coordinator, session):
    session = coordinator.update_state(
        session,
        document_job={
            "status": "content_generation_running",
            "content_generation_id": "generation-1",
        },
    )
    return coordinator.append_message(
        session,
        AssistantMessage.interaction(
            role=ROLE_ASSISTANT,
            interaction_type="progress",
            title="正在起草文档内容",
            body="",
            payload={
                "actions": [],
                "ephemeral": True,
                "progress_kind": "content_generation",
                "generation_id": "generation-1",
            },
        ),
    )


def _visible_cards(panel: AssistantPanel) -> list[AssistantInteractionCard]:
    return [
        card
        for card in panel._message_host.findChildren(AssistantInteractionCard)
        if card.isVisible()
    ]


def test_new_card_keeps_stable_width_and_follows_settled_bottom(
    qapp,
    tmp_path,
):
    panel, coordinator = _panel(tmp_path)
    try:
        session = _session_with_plans(coordinator, count=1)
        panel._active_session = session
        panel._render_active_session()
        qapp.processEvents()
        panel._follow_latest_settle_timer.stop()
        panel._finish_follow_latest_layout_settle()
        qapp.processEvents()

        scroll = panel._message_scroll
        bar = scroll.verticalScrollBar()
        assert scroll.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOn
        viewport_width = scroll.viewport().width()
        initial_cards = _visible_cards(panel)
        assert len(initial_cards) == 1
        initial_x = initial_cards[0].x()
        assert initial_cards[0].width() == 760

        panel._active_session = _append_active_progress(coordinator, session)
        panel._render_active_session()
        for _index in range(6):
            qapp.processEvents()
            visible = _visible_cards(panel)
            if visible:
                assert {card.width() for card in visible} == {760}

        panel._follow_latest_settle_timer.stop()
        panel._finish_follow_latest_layout_settle()
        qapp.processEvents()

        visible = _visible_cards(panel)
        assert len(visible) == 2
        assert {card.x() for card in visible} == {initial_x}
        assert scroll.viewport().width() == viewport_width
        assert bar.maximum() > 0
        assert bar.value() == bar.maximum()
        assert not panel._jump_latest_button.isVisible()
    finally:
        panel.close()


def test_user_scroll_position_is_preserved_and_jump_control_is_overlay(
    qapp,
    tmp_path,
):
    panel, coordinator = _panel(tmp_path)
    try:
        session = _session_with_plans(coordinator, count=4)
        panel._active_session = session
        panel._render_active_session()
        for _index in range(6):
            qapp.processEvents()
        panel._follow_latest_settle_timer.stop()
        panel._finish_follow_latest_layout_settle()
        qapp.processEvents()

        scroll = panel._message_scroll
        bar = scroll.verticalScrollBar()
        assert bar.maximum() > 64
        viewport_height = scroll.viewport().height()
        bar.setValue(0)
        qapp.processEvents()
        assert panel._jump_latest_button.isVisible()
        assert panel._jump_latest_button.parentWidget() is scroll.viewport()
        assert scroll.viewport().height() == viewport_height

        panel._active_session = _append_active_progress(coordinator, session)
        panel._render_active_session()
        for _index in range(8):
            qapp.processEvents()

        assert bar.value() == 0
        assert panel._jump_latest_button.isVisible()
        assert scroll.viewport().height() == viewport_height
    finally:
        panel.close()
