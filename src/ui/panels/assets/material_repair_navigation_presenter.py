"""Presenter mixin for material repair navigation and focus behavior."""

from __future__ import annotations

from typing import Mapping

from src.qt_api import QAbstractItemView, QTimer, QWidget
from src.services.material_assets import (
    parse_question_figure_repair_target,
    question_figure_item_matches_repair_target,
    question_figure_items,
    question_figure_target_value,
)
from src.shared.ui.card import Card
from src.shared.ui.theme import get_theme
from src.ui.adapters.field_display_names import navigation_issue_hint
from src.ui.bridge import navigation_intent_value
from src.ui.panels.assets.fields import _asset_role_label, _placeholder_key
from src.ui.panels.assets.roles import _asset_slot_role_for_token


class MaterialRepairNavigationMixin:
    """Coordinate repair target routing, focus, and attention state."""

    def _focus_missing_content(self) -> None:
        target_type, target_key = self._next_missing_target()
        if self.focus_material_repair_target(target_type, target_key):
            return
        if target_type == "custom":
            self._show_missing_target(self._fields_edit, self._profile_card)
            self._fields_edit.setFocus()
            return
        preview_target = self._preview_table if getattr(self, "_preview_table", None) is not None else self._preview_label
        self._show_missing_target(preview_target, self._preview_card)
        self._preview_label.setFocus()

    def focus_material_repair_target(self, target_type: str, target_key: str) -> bool:
        target_type = str(target_type or "").strip()
        target_key = str(target_key or "").strip()
        if target_type == "field":
            widget = self._field_inputs.get(target_key)
            if widget is not None:
                self._show_missing_target(widget, self._profile_card)
                widget.setFocus()
                return True
            return False
        if target_type == "asset":
            if self._focus_asset_slot(target_key):
                return True
            if self._focus_attachment_role(target_key):
                return True
            return False
        if target_type == "question_figure_item":
            return self._focus_question_figure_item(target_key)
        return False

    def handle_navigation_intent(self, intent) -> None:
        self._set_return_navigation_intent(intent)
        payload = navigation_intent_value(intent, "payload", {}) or {}
        if not isinstance(payload, dict):
            payload = {}
        target_type = str(
            navigation_intent_value(intent, "issue_id", "")
            or payload.get("issue_type")
            or payload.get("repair_target_type")
            or ""
        ).strip()
        target_key = str(
            navigation_intent_value(intent, "field_id", "")
            or payload.get("issue_key")
            or payload.get("repair_target_key")
            or ""
        ).strip()
        if target_type in {"field", "asset", "question_figure_item"} and target_key:
            self.focus_material_repair_target(target_type, target_key)

    def _set_return_navigation_intent(self, intent) -> None:
        panel_id = str(navigation_intent_value(intent, "return_panel_id", "") or "").strip()
        card_id = str(navigation_intent_value(intent, "return_card_id", "") or "").strip()
        if not panel_id:
            self._return_navigation_intent = None
            self._return_label.setText("浠庢墽琛岄棶棰樿繘鍏?")
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
            or payload.get("repair_target_key")
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
            if active_issue_id and not self._return_navigation_intent["payload"].get("active_issue_id"):
                self._return_navigation_intent["payload"]["active_issue_id"] = active_issue_id
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

    def _navigate_return_target(self) -> None:
        if not self._return_navigation_intent:
            return
        self.bridge.navigate_to_intent.emit(dict(self._return_navigation_intent))
        self._return_bar.setVisible(False)

    def focus_material_profile_repair_target(
        self,
        profile_id: str,
        profile_name: str,
        target_type: str,
        target_key: str,
    ) -> bool:
        selected = self._select_profile_for_repair(profile_id, profile_name)
        if target_type in {"field", "asset", "question_figure_item"} and target_key:
            if self.focus_material_repair_target(target_type, target_key):
                return True
        if selected:
            self._jump_to_card(self._profile_card)
            return True
        return self.focus_material_repair_target(target_type, target_key)

    def apply_material_profile_question_figure_repair_candidate(
        self,
        profile_id: str,
        profile_name: str,
        candidate: Mapping[str, object],
        *,
        confirmed: bool = True,
    ) -> bool:
        selected = self._select_profile_for_repair(profile_id, profile_name)
        if not isinstance(candidate, Mapping):
            if selected:
                self._jump_to_card(self._profile_card)
            return False
        target_key = str(candidate.get("repair_target_key") or "").strip()
        if target_key:
            self.focus_material_repair_target("question_figure_item", target_key)
        applied = self.apply_question_figure_repair_candidate(
            candidate,
            confirmed=confirmed,
        )
        if applied:
            return True
        if selected:
            self._jump_to_card(self._profile_card)
        return False

    def _on_material_repair_target_requested(self, target_type: str, target_key: str) -> None:
        self._refresh_summary()
        self.focus_material_repair_target(target_type, target_key)

    def _on_material_profile_repair_target_requested(
        self,
        profile_id: str,
        profile_name: str,
        target_type: str,
        target_key: str,
    ) -> None:
        self._refresh_summary()
        self.focus_material_profile_repair_target(profile_id, profile_name, target_type, target_key)

    def _on_material_profile_repair_candidate_requested(
        self,
        profile_id: str,
        profile_name: str,
        candidate,
    ) -> None:
        self._refresh_summary()
        self.apply_material_profile_question_figure_repair_candidate(
            profile_id,
            profile_name,
            candidate if isinstance(candidate, Mapping) else {},
            confirmed=True,
        )

    def _focus_pending_material_repair_target(self) -> None:
        profile_id, profile_name, candidate = (
            self.bridge.consume_material_profile_repair_candidate()
        )
        if profile_id or profile_name or candidate:
            self._on_material_profile_repair_candidate_requested(
                profile_id,
                profile_name,
                candidate,
            )
            return
        profile_id, profile_name, target_type, target_key = (
            self.bridge.consume_material_profile_repair_target()
        )
        if profile_id or profile_name or target_type or target_key:
            self._on_material_profile_repair_target_requested(
                profile_id,
                profile_name,
                target_type,
                target_key,
            )
            return
        target_type, target_key = self.bridge.consume_material_repair_target()
        if target_type or target_key:
            self._on_material_repair_target_requested(target_type, target_key)

    def _next_missing_target(self) -> tuple[str, str]:
        state = self._current_preview_state()
        for key in state["missing_required_fields"]:
            return ("field", key)
        if not state["fields"]:
            default_required = self._default_required_field_keys()
            if default_required:
                return ("field", default_required[0])
        for role in state["missing_asset_roles"]:
            return ("asset", role)
        for token in state["unmatched_placeholders"]:
            field_widget = self._field_inputs.get(token)
            if field_widget is not None:
                return ("field", token)
            role = _asset_slot_role_for_token(token, self._asset_slot_specs)
            if role:
                return ("asset", role)
            attachment_role = self._attachment_role_for_token(token)
            if attachment_role:
                return ("asset", attachment_role)
        if state["unmatched_placeholders"]:
            return ("custom", state["unmatched_placeholders"][0])
        return ("preview", "")

    def _focus_asset_slot(self, role: str) -> bool:
        button = self._asset_slot_choose_buttons.get(role)
        if button is None:
            return False
        target_widget = self._asset_slot_rows.get(role, button)
        self._show_missing_target(target_widget, self._image_card)
        button.setFocus()
        status = self._asset_slot_status_labels.get(role)
        if status is not None:
            status.setText(f"请先选择{_asset_role_label(role, self._asset_slot_specs)}。")
        return True

    def _focus_attachment_role(self, role: str) -> bool:
        button = self._attachment_role_choose_buttons.get(role)
        if button is None:
            return False
        target_widget = self._attachment_role_rows.get(role, button)
        self._show_missing_target(target_widget, self._image_card)
        button.setFocus()
        status = self._attachment_role_status_labels.get(role)
        spec = self._attachment_role_spec(role)
        if status is not None:
            status.setText(f"请先选择{spec.label if spec is not None else role}。")
        return True

    def _attachment_role_for_token(self, token: str) -> str:
        normalized = _placeholder_key(token)
        for spec in self._attachment_role_specs:
            if normalized == spec.role:
                return spec.role
        return ""

    def _focus_question_figure_item(self, target_key: str) -> bool:
        table = getattr(self, "_question_figure_items_table", None)
        if table is None:
            return False
        row_index = self._question_figure_item_row_for_target(target_key)
        if row_index < 0:
            return self._focus_asset_slot("question_figure")
        self._show_missing_target(table, self._image_card)
        table.setCurrentCell(row_index, 0)
        table.selectRow(row_index)
        table.setFocus()
        item = table.item(row_index, 0)
        if item is not None:
            table.scrollToItem(item, QAbstractItemView.PositionAtCenter)
        return True

    def _question_figure_item_row_for_target(self, target_key: str) -> int:
        target = parse_question_figure_repair_target(target_key)
        if not target:
            return -1
        for index, item in enumerate(question_figure_items(self._current_asset_items())):
            if question_figure_item_matches_repair_target(item, target):
                return index
        return -1

    def _question_figure_item_row_for_repair_audit_record(
        self,
        audit_record: Mapping[str, object],
    ) -> int:
        target_key = str(audit_record.get("repair_target_key") or "").strip()
        row_index = self._question_figure_item_row_for_target(target_key)
        if row_index >= 0:
            return row_index
        item_id = str(audit_record.get("item_id") or "").strip()
        question_index = str(audit_record.get("question_index") or "").strip()
        applied_path = str(audit_record.get("applied_path") or "").strip()
        for index, item in enumerate(question_figure_items(self._current_asset_items())):
            current_item_id = str(getattr(item, "item_id", "") or "").strip()
            if item_id and current_item_id == item_id:
                return index
            metadata = dict(getattr(item, "metadata", {}) or {})
            current_question_index = question_figure_target_value(metadata)
            if question_index and current_question_index == question_index:
                return index
            current_path = str(getattr(item, "path", "") or "").strip()
            if applied_path and current_path == applied_path:
                return index
        return -1

    def _material_role_label(self, role: str) -> str:
        spec = self._attachment_role_spec(role)
        if spec is not None:
            return spec.label
        return _asset_role_label(role, self._asset_slot_specs)

    def _show_missing_target(self, widget: QWidget, card: Card) -> None:
        self._select_section_for_card(card)
        self._highlight_attention_card(card)
        self._ensure_widget_visible(widget)

    def _jump_to_card(self, card: Card) -> None:
        self._select_section_for_card(card)
        self._highlight_attention_card(card)
        self._ensure_widget_visible(card)
        card.setFocus()

    def _select_section_for_card(self, card: Card) -> None:
        section_id = self._card_section_ids.get(card)
        if section_id:
            self._select_section(section_id)

    def _select_section(self, section_id: str) -> None:
        if section_id not in self._section_pages:
            return
        previous = self._active_section_id
        self._section_nav.select_card(section_id)
        if previous == self._active_section_id and self._active_section_id != section_id:
            self._on_section_selected(section_id)

    def _highlight_attention_card(self, card: Card) -> None:
        if self._active_attention_card is not None and self._active_attention_card is not card:
            self._active_attention_card.set_card_surface()
        self._active_attention_card = card
        theme = get_theme()
        self._attention_pulse_card = card
        card.set_card_surface(border_color=theme.primary, border_width=3.0, shadow=True)
        QTimer.singleShot(180, lambda target=card: self._settle_attention_card(target))

    def _settle_attention_card(self, card: Card) -> None:
        if self._active_attention_card is not card:
            return
        self._attention_pulse_card = None
        theme = get_theme()
        card.set_card_surface(border_color=theme.primary, border_width=2.0, shadow=True)

    def _ensure_widget_visible(self, widget: QWidget) -> None:
        if not hasattr(self, "_section_scrolls"):
            return
        scroll = self._section_scrolls.get(self._active_section_id)
        if scroll is not None:
            scroll.ensureWidgetVisible(widget, 24, 24)


__all__ = ["MaterialRepairNavigationMixin"]
