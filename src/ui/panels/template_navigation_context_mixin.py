"""Navigation-intent projection for the template panel."""

from __future__ import annotations

from src.qt_api import QTimer
from src.ui.adapters.field_display_names import navigation_issue_hint
from src.ui.bridge import navigation_intent_value
from src.ui.panels.template_navigation_context import (
    build_template_navigation_context,
)


class TemplateNavigationContextMixin:
    """Own inbound navigation, field focus, and return-context presentation."""

    def handle_navigation_intent(self, intent) -> None:
        card_id = str(
            navigation_intent_value(intent, "card_id", "") or ""
        ).strip()
        self._set_return_navigation_intent(intent)
        self._set_entry_context(intent)
        if not card_id:
            return
        if card_id in self._detail_map or card_id in self._detail_factories:
            self._nav_rail.select_card(card_id)
            QTimer.singleShot(
                0,
                lambda: self._focus_navigation_field(card_id, intent),
            )

    def _focus_navigation_field(self, card_id: str, intent) -> None:
        field_id = str(
            navigation_intent_value(intent, "field_id", "") or ""
        ).strip()
        if not field_id:
            payload = navigation_intent_value(intent, "payload", {}) or {}
            if isinstance(payload, dict):
                field_id = str(
                    payload.get("issue_key")
                    or payload.get("repair_target_key")
                    or ""
                ).strip()
        if not field_id:
            return
        detail = self._detail_map.get(card_id)
        if detail is None or not hasattr(detail, "focus_navigation_field"):
            return
        detail.focus_navigation_field(field_id)

    def _set_return_navigation_intent(self, intent) -> None:
        panel_id = str(
            navigation_intent_value(intent, "return_panel_id", "") or ""
        ).strip()
        card_id = str(
            navigation_intent_value(intent, "return_card_id", "") or ""
        ).strip()
        if not panel_id:
            self._return_navigation_intent = None
            self._return_label.setText("从执行问题进入")
            self._return_bar.setVisible(False)
            return
        payload = navigation_intent_value(intent, "payload", {}) or {}
        if not isinstance(payload, dict):
            payload = {}
        active_issue_id = str(
            navigation_intent_value(intent, "active_issue_id", "")
            or payload.get("active_issue_id")
            or payload.get("issue_item_id")
            or ""
        ).strip()
        issue_key = str(
            navigation_intent_value(intent, "field_id", "")
            or payload.get("issue_key")
            or ""
        ).strip()
        issue_title = str(payload.get("issue_title") or "").strip()
        issue_type = str(
            navigation_intent_value(intent, "issue_id", "")
            or payload.get("issue_type")
            or ""
        ).strip()
        self._return_navigation_intent = {
            "panel_id": panel_id,
            "card_id": card_id,
        }
        if active_issue_id:
            self._return_navigation_intent["active_issue_id"] = active_issue_id
        if payload:
            self._return_navigation_intent["payload"] = dict(payload)
            if active_issue_id and not self._return_navigation_intent[
                "payload"
            ].get("active_issue_id"):
                self._return_navigation_intent["payload"][
                    "active_issue_id"
                ] = active_issue_id
        hint = str(payload.get("issue_display_name") or "").strip()
        if not hint:
            hint = navigation_issue_hint(
                issue_title,
                issue_key,
                issue_type=issue_type,
            )
        self._return_label.setText(
            f"从执行问题进入：{hint}" if hint else "从执行问题进入"
        )
        self._return_bar.setVisible(True)

    def _set_entry_context(self, intent) -> None:
        payload = navigation_intent_value(intent, "payload", {}) or {}
        if not isinstance(payload, dict):
            payload = {}

        title = str(payload.get("entry_context_title") or "").strip()
        detail = str(payload.get("entry_context_detail") or "").strip()
        action = str(payload.get("entry_context_action") or "").strip()

        if not title:
            issue_title = str(payload.get("issue_title") or "").strip()
            if issue_title:
                title = f"来自执行问题：{issue_title}"
                detail = detail or str(
                    payload.get("issue_summary") or ""
                ).strip()
                action = action or "调整后返回执行页复检"

        if not title:
            return_panel_id = str(
                navigation_intent_value(intent, "return_panel_id", "") or ""
            ).strip()
            if return_panel_id == "scene":
                preview_context = build_template_navigation_context(
                    detail=self._scene_template_context_detail(),
                )
                title = preview_context.title
                detail = detail or preview_context.detail
                action = action or preview_context.action

        if not title:
            self._entry_context_title.setText("")
            self._entry_context_detail.setText("")
            self._entry_context_bar.setVisible(False)
            return

        if action:
            detail = f"{detail}；{action}" if detail else action
        self._entry_context_title.setText(title)
        self._entry_context_detail.setText(detail)
        self._entry_context_bar.setVisible(True)

    def _scene_template_context_detail(self) -> str:
        scene = self.bridge.current_scene()
        scene_label = ""
        if scene is not None:
            scene_label = str(
                getattr(scene, "display_name", "")
                or getattr(scene, "name", "")
                or getattr(scene, "scene_id", "")
                or ""
            ).strip()
        template_label = str(
            getattr(self._current_template, "name", "") or ""
        ).strip()
        parts = []
        if scene_label:
            parts.append(f"方案：{scene_label}")
        if template_label:
            parts.append(f"模板：{template_label}")
        return "；".join(parts)

    def _navigate_return_target(self) -> None:
        if not self._return_navigation_intent:
            return
        self.bridge.navigate_to_intent.emit(
            dict(self._return_navigation_intent)
        )
        self._return_bar.setVisible(False)
        self._entry_context_bar.setVisible(False)
