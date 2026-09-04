"""Conversation viewport behavior shared by assistant panel shells."""

from src.assistant.ui.design_tokens import TOKENS
from src.assistant.ui.interaction_card import AssistantInteractionCard
from src.qt_api import QTimer


class AssistantViewportMixin:
    def _scroll_to_bottom(self) -> None:
        bar = self._message_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        self._jump_latest_button.hide()

    def _begin_follow_latest_layout_settle(self) -> None:
        """Keep the viewport pinned while deferred Qt layouts update the range."""

        self._follow_latest_layout_pending = True
        if hasattr(self, "_follow_latest_settle_timer"):
            self._follow_latest_settle_timer.start()
        QTimer.singleShot(0, self._scroll_to_bottom_while_layout_settles)

    def _scroll_to_bottom_while_layout_settles(self) -> None:
        if not self._follow_latest_layout_pending:
            return
        self._scroll_to_bottom()

    def _finish_follow_latest_layout_settle(self) -> None:
        if not self._follow_latest_layout_pending:
            return
        self._scroll_to_bottom()
        self._follow_latest_layout_pending = False
        self._sync_jump_to_latest(self._message_scroll.verticalScrollBar().value())

    def _cancel_follow_latest_layout_settle(self) -> None:
        self._follow_latest_layout_pending = False
        if hasattr(self, "_follow_latest_settle_timer"):
            self._follow_latest_settle_timer.stop()

    def _on_message_scroll_range_changed(
        self,
        _minimum: int,
        _maximum: int,
    ) -> None:
        if self._follow_latest_layout_pending:
            self._scroll_to_bottom_while_layout_settles()
            if hasattr(self, "_follow_latest_settle_timer"):
                self._follow_latest_settle_timer.start()
            return
        self._sync_jump_to_latest(self._message_scroll.verticalScrollBar().value())

    def _restore_scroll_value(self, value: int) -> None:
        bar = self._message_scroll.verticalScrollBar()
        bar.setValue(min(max(0, int(value)), bar.maximum()))
        self._sync_jump_to_latest(bar.value())

    def _is_near_latest(self) -> bool:
        bar = self._message_scroll.verticalScrollBar()
        return bar.maximum() - bar.value() <= 64

    def _sync_jump_to_latest(self, _value: int) -> None:
        if self._conversation_stack.currentWidget() is not self._active_page:
            self._jump_latest_button.hide()
            return
        if self._follow_latest_layout_pending:
            self._jump_latest_button.hide()
            return
        self._jump_latest_button.setVisible(not self._is_near_latest())
        self._position_jump_latest_button()

    def _position_jump_latest_button(self) -> None:
        if not self._jump_latest_button.isVisible():
            return
        viewport = self._message_scroll.viewport()
        self._jump_latest_button.adjustSize()
        x = max(8, (viewport.width() - self._jump_latest_button.width()) // 2)
        y = max(8, viewport.height() - self._jump_latest_button.height() - 12)
        self._jump_latest_button.move(x, y)
        self._jump_latest_button.raise_()

    def _interaction_card_available_width(self) -> int:
        viewport_width = max(0, self._message_scroll.viewport().width())
        if viewport_width <= 0:
            viewport_width = max(
                0,
                self._active_page.width()
                - self._message_scroll.verticalScrollBar().sizeHint().width(),
            )
        # 与对话消息共用 3/4 阅读列，保证卡片与消息同轴对齐。卡片是结构化
        # 交互面（事实行/按钮组），铺满整条 3/4 列会拉出超宽行；因此卡片
        # 可用宽在 3/4 阅读列内收敛到自身舒适上限（默认与 AI 文本一致，
        # 不再被 820 单独截断即可让宽屏卡片适度加宽）。
        reading_cap = max(420, int(viewport_width * 0.75))
        return reading_cap

    def _sync_active_reading_widths(self) -> None:
        page_width = max(0, self._active_page.width())
        if page_width > 48:
            self._composer.setFixedWidth(page_width - 48)
        card_width = self._interaction_card_available_width()
        for card in self._message_host.findChildren(AssistantInteractionCard):
            target_width = card.preferred_width(card_width)
            if (
                card.minimumWidth() != target_width
                or card.maximumWidth() != target_width
            ):
                card.setFixedWidth(target_width)
        self._position_jump_latest_button()


__all__ = ["AssistantViewportMixin"]
