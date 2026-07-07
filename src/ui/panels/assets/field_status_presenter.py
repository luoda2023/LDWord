"""Presenter mixin for field status and unknown placeholder suggestions."""

from __future__ import annotations

from src.qt_api import QFrame, QHBoxLayout, QLabel, QPushButton
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.layout_sync import (
    refresh_layout_chain,
    refresh_layout_chain_later,
    updates_suspended,
)
from src.shared.ui.theme import get_theme
from src.ui.panels.assets.fields import (
    _field_label,
    _field_validation_hint,
    _parse_fields_text,
    _placeholder_key,
)
from src.ui.panels.assets.roles import _asset_slot_role_for_token


class FieldStatusPresenterMixin:
    """Refresh local field status rows and unknown-placeholder helpers."""

    def _refresh_field_statuses(self, state: dict[str, object]) -> None:
        if not hasattr(self, "_field_status_labels"):
            return
        fields = dict(state.get("fields") or {})
        more_fields = _parse_fields_text(self._fields_edit.get_text())
        placeholder_tokens = [
            _placeholder_key(token)
            for token in list(state.get("placeholder_tokens") or [])
        ]
        placeholder_set = set(placeholder_tokens)
        required_missing_labels = [
            _field_label(key)
            for key in state.get("missing_required_fields", [])
        ]
        template_missing_labels: list[str] = []

        for key, label in self._field_status_labels.items():
            value = str(fields.get(key, "") or "").strip()
            in_template = key in placeholder_set
            from_more_fields = bool(str(more_fields.get(key, "") or "").strip())
            required_fields = set(
                state.get("required_fields")
                if state.get("required_fields") is not None
                else self._default_required_field_keys()
            )
            if not value:
                if in_template:
                    template_missing_labels.append(_field_label(key))
                if key in required_fields:
                    status = "蹇呭～"
                    if in_template:
                        status += "，模板会用到"
                    status += "，生成前要补齐。"
                elif in_template:
                    status = "模板会用到，建议填写。"
                else:
                    status = "选填。"
            else:
                if key in self._imported_field_keys:
                    status = "来自导入资料表"
                elif from_more_fields:
                    status = "来自更多资料"
                else:
                    status = "已填写"
                if in_template:
                    status += "，模板会用到"
                validation_hint = _field_validation_hint(key, value)
                if validation_hint:
                    status += f"，{validation_hint}"
                status += "。"
            label.setText(status)

        if not hasattr(self, "_fields_hint_label"):
            return
        unmatched = [
            token
            for token in list(state.get("unmatched_placeholders") or [])
            if token not in self._field_inputs
            and not _asset_slot_role_for_token(token, self._asset_slot_specs)
            and not self._attachment_role_for_token(token)
        ]
        source_path = self._placeholder_source_path()
        if not source_path:
            self._fields_hint_label.setText("选择文档后，会按模板占位符提示要补的资料。")
            self._refresh_unknown_field_suggestions([])
            return
        if not placeholder_tokens:
            self._fields_hint_label.setText("当前文档没有发现需要填写的 {{...}} 占位符。")
            self._refresh_unknown_field_suggestions([])
            return

        parts: list[str] = []
        if required_missing_labels:
            parts.append("必填资料：" + "、".join(required_missing_labels))
        recommended = [
            label
            for label in template_missing_labels
            if label not in required_missing_labels
        ]
        if recommended:
            parts.append("模板建议补充：" + "、".join(recommended))
        if unmatched:
            parts.append("未识别占位符：" + "、".join(unmatched[:4]) + "，可在“更多资料”中按 key=value 补充")
        self._fields_hint_label.setText("；".join(parts) if parts else "模板里的常用资料已匹配。")
        self._refresh_unknown_field_suggestions(unmatched)

    def _refresh_unknown_field_suggestions(self, tokens: list[str]) -> None:
        if not hasattr(self, "_unknown_fields_container"):
            return
        self._unknown_placeholder_buttons = {}
        while self._unknown_fields_layout.count():
            item = self._unknown_fields_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        visible_tokens = list(dict.fromkeys(tokens))[:6]
        with updates_suspended(self._unknown_fields_container, getattr(self, "_detail_shell", self)):
            self._unknown_fields_container.setVisible(bool(visible_tokens))
            refresh_layout_chain(self._unknown_fields_container)
        for token in visible_tokens:
            row = QFrame(self._unknown_fields_container)
            row.setObjectName("unknown_field_suggestion")
            layout = QHBoxLayout(row)
            layout.setContentsMargins(10, 8, 10, 8)
            layout.setSpacing(10)
            label = QLabel("妯℃澘閲屾湁 {{" + token + "}}", row)
            button = QPushButton("鍔犲叆鏇村璧勬枡", row)
            button.clicked.connect(
                lambda *_args, field_key=token: self._add_unknown_placeholder_field(field_key)
            )
            layout.addWidget(label, 1)
            layout.addWidget(button)
            theme = get_theme()
            row.setStyleSheet(
                f"""
                QFrame#unknown_field_suggestion {{
                    background: {theme.bg_input};
                    border: 1px solid {theme.border_light};
                    border-radius: {theme.input_radius}px;
                }}
                """
            )
            label.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};")
            apply_button_variant(button, "secondary")
            button.setStyleSheet(build_button_stylesheet(theme))
            self._unknown_placeholder_buttons[token] = button
            self._unknown_fields_layout.addWidget(row)
        refresh_layout_chain(self._unknown_fields_container)
        refresh_layout_chain_later(self._unknown_fields_container)

    def _add_unknown_placeholder_field(self, token: str, *, value: str = "") -> None:
        key = _placeholder_key(token)
        if not key:
            return
        current_fields = _parse_fields_text(self._fields_edit.get_text())
        if key in current_fields:
            self._fields_edit.setFocus()
            return
        lines = [line for line in self._fields_edit.get_text().splitlines() if line.strip()]
        lines.append(f"{key}={str(value or '').strip()}")
        self._fields_edit.set_text("\n".join(lines))
        self._fields_edit.setFocus()
        self._refresh_summary()


__all__ = ["FieldStatusPresenterMixin"]
