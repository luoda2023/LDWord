"""Presenter mixin for placeholder preview table rows and row actions."""

from __future__ import annotations

from pathlib import Path

from src.config.material_preview import scan_docx_placeholders
from src.config.materials import (
    AssetInsertionRule,
    missing_required_asset_roles,
    parse_asset_insertion_rules,
)
from src.config.resolved import ReplacementRule
from src.qt_api import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    Qt,
    QWidget,
)
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.theme import get_theme
from src.ui.panels.assets.fields import (
    _asset_role_label,
    _field_alias_for_token,
    _field_label,
    _learned_field_alias_for_token,
    _normalized_field_aliases,
    _placeholder_key,
)
from src.ui.panels.assets.roles import _asset_slot_role_for_token
from src.ui.panels.assets.text_helpers import _parse_replacements_text


def _preview_row(
    *,
    token: str,
    placeholder: str,
    value: object,
    source: str,
    status: str,
    issue: bool,
    summary: str,
    action: str = "",
    action_type: str = "",
    action_key: str = "",
    action_source: str = "",
) -> dict[str, object]:
    return {
        "token": token,
        "placeholder": placeholder,
        "value": value,
        "source": source,
        "status": status,
        "issue": issue,
        "action": action,
        "action_type": action_type,
        "action_key": action_key,
        "action_source": action_source,
        "summary": summary,
    }


class PreviewTablePresenterMixin:
    """Render placeholder preview rows and dispatch local fix actions."""

    def _setup_placeholder_preview_card(self) -> None:
        preview_card = Card(parent=self._section_contents["preview"])
        self._preview_card = preview_card
        preview_card.set_header("鐢熸垚棰勮", icon_name="eye")
        self._preview_label = QLabel(preview_card)
        self._preview_label.setWordWrap(True)
        preview_actions = QWidget(preview_card)
        preview_actions_layout = QHBoxLayout(preview_actions)
        preview_actions_layout.setContentsMargins(0, 0, 0, 0)
        preview_actions_layout.setSpacing(10)
        self._preview_filter_btn = QPushButton("鍙湅闂椤?", preview_actions)
        self._preview_auto_match_btn = QPushButton("鑷姩鍖归厤", preview_actions)
        self._preview_auto_match_btn.clicked.connect(self._on_preview_auto_match)
        self._preview_filter_btn.clicked.connect(self._toggle_preview_filter)
        preview_actions_layout.addWidget(self._preview_auto_match_btn)
        preview_actions_layout.addWidget(self._preview_filter_btn)
        preview_actions_layout.addStretch(1)
        self._preview_table = QTableWidget(preview_card)
        self._preview_table.setObjectName("asset_placeholder_preview_table")
        self._preview_table.setColumnCount(5)
        self._preview_table.setHorizontalHeaderLabels(
            ["占位符", "将替换为", "来源", "状态", "处理"]
        )
        self._preview_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._preview_table.setSelectionMode(QTableWidget.SingleSelection)
        self._preview_table.setAlternatingRowColors(True)
        self._preview_table.setShowGrid(False)
        self._preview_table.setWordWrap(True)
        self._preview_table.setMinimumHeight(180)
        self._preview_table.setMaximumHeight(320)
        self._preview_table.verticalHeader().setVisible(False)
        header = self._preview_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        preview_card.add_widget(preview_actions)
        preview_card.add_widget(self._preview_label)
        preview_card.add_widget(self._preview_table)
        self._section_layouts["preview"].addWidget(preview_card)

    def _toggle_preview_filter(self) -> None:
        self._preview_only_issues = not self._preview_only_issues
        self._preview_filter_btn.setText(
            "鏄剧ず鍏ㄩ儴" if self._preview_only_issues else "鍙湅闂椤?"
        )
        self._refresh_summary()

    def _on_preview_auto_match(self) -> None:
        self._placeholder_cache_path = ""
        self._placeholder_cache_mtime = None
        self._placeholder_cache_tokens = []
        self._refresh_summary()

    def _on_document_loaded(self, file_path: str) -> None:
        self._current_document_path = str(file_path or "").strip()
        self._placeholder_cache_path = ""
        self._placeholder_cache_mtime = None
        self._placeholder_cache_tokens = []
        self._refresh_summary()

    def _visible_placeholder_preview_rows(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        if not self._preview_only_issues:
            return rows
        return [row for row in rows if bool(row.get("issue"))]

    def _placeholder_preview_text(
        self,
        tokens: list[str],
        fields: dict[str, str],
        replacements: list,
        asset_items,
        image_rules: list,
        *,
        preview_rows: list[dict[str, object]] | None = None,
    ) -> str:
        if not tokens:
            source_path = self._placeholder_source_path()
            if source_path:
                return "??????? {{...}} ????"
            preview_pairs = [
                f"{_field_label(key)} -> {value}"
                for key, value in list(fields.items())[:4]
            ]
            if preview_pairs:
                preview_text = "?".join(preview_pairs)
                if len(fields) > 4:
                    preview_text += f"?? {len(fields)} ???"
            else:
                preview_text = "?????????????????????????????"
            if replacements:
                preview_text += f"??? {len(replacements)} ??????"
            return preview_text

        rows = preview_rows
        if rows is None:
            rows = self._placeholder_preview_rows(tokens, fields, replacements, asset_items, image_rules)
        visible_rows = self._visible_placeholder_preview_rows(rows)
        lines = [str(row["summary"]) for row in visible_rows[:12]]
        if len(visible_rows) > 12:
            lines.append(f"?? {len(visible_rows) - 12} ?????????")
        if self._preview_only_issues and not lines:
            return "?????????????"
        return "\n".join(lines)

    def _placeholder_source_path(self) -> str:
            document_path = str(self._current_document_path or self.bridge.current_document_path() or "").strip()
            if document_path:
                return document_path
            template_path = str(self.bridge.current_template_path() or "").strip()
            return template_path if template_path.lower().endswith(".docx") else ""

    def _scanned_placeholders(self) -> list[str]:
            source_path = self._placeholder_source_path()
            if not source_path:
                return []
            path = Path(source_path)
            try:
                mtime = path.stat().st_mtime
            except OSError:
                return []
            if (
                self._placeholder_cache_path == str(path)
                and self._placeholder_cache_mtime == mtime
            ):
                return list(self._placeholder_cache_tokens)
            try:
                tokens = scan_docx_placeholders(path)
            except Exception:
                tokens = []
            self._placeholder_cache_path = str(path)
            self._placeholder_cache_mtime = mtime
            self._placeholder_cache_tokens = list(tokens)
            return list(tokens)

    def _current_preview_state(self) -> dict[str, object]:
            fields = self._editor_fields()
            replacements = _parse_replacements_text(self._replacement_rules_edit.get_text())
            asset_items = self._current_asset_items()
            image_rules = self._image_rules_for_asset_items(asset_items)
            advanced_rules = parse_asset_insertion_rules(self._image_rules_edit.get_text())
            placeholder_tokens = self._scanned_placeholders()
            missing_image_roles = missing_required_asset_roles(asset_items, image_rules)
            missing_attachment_roles = self._missing_attachment_roles(asset_items)
            missing_asset_roles = [*missing_image_roles, *missing_attachment_roles]
            unmatched_placeholders = self._unmatched_placeholders(
                placeholder_tokens,
                fields,
                replacements,
                asset_items,
                image_rules,
            )
            missing_required_fields = [
                key
                for key in self._required_field_keys()
                if not fields.get(key)
            ]
            return {
                "fields": fields,
                "replacements": replacements,
                "asset_items": asset_items,
                "image_rules": image_rules,
                "advanced_rules": advanced_rules,
                "placeholder_tokens": placeholder_tokens,
                "missing_asset_roles": missing_asset_roles,
                "missing_image_roles": missing_image_roles,
                "missing_attachment_roles": missing_attachment_roles,
                "unmatched_placeholders": unmatched_placeholders,
                "required_fields": list(self._required_field_keys()),
                "missing_required_fields": missing_required_fields,
            }

    def _missing_attachment_roles(self, asset_items) -> list[str]:
            available = {item.role for item in asset_items if item.role and item.path}
            return [
                spec.role
                for spec in self._attachment_role_specs
                if spec.required and spec.role not in available
            ]

    def _unmatched_placeholders(
            self,
            tokens: list[str],
            fields: dict[str, str],
            replacements: list[ReplacementRule],
            asset_items,
            image_rules: list[AssetInsertionRule],
        ) -> list[str]:
            replacement_keys = {_placeholder_key(rule.old) for rule in replacements if rule.old}
            available_roles = {item.role for item in asset_items if item.role and item.path}
            image_targets = {
                _placeholder_key(rule.target): rule.asset_role
                for rule in image_rules
                if rule.target and rule.asset_role
            }
            unmatched: list[str] = []
            for token in tokens:
                if token in fields and fields[token]:
                    continue
                if token in replacement_keys:
                    continue
                role = (
                    image_targets.get(token)
                    or _asset_slot_role_for_token(token, self._asset_slot_specs)
                    or self._attachment_role_for_token(token)
                )
                if role and role in available_roles:
                    continue
                unmatched.append(token)
            return unmatched

    def _placeholder_preview_rows(
        self,
        tokens: list[str],
        fields: dict[str, str],
        replacements: list[ReplacementRule],
        asset_items,
        image_rules: list[AssetInsertionRule],
    ) -> list[dict[str, object]]:
        replacement_map = {
            _placeholder_key(rule.old): rule.new
            for rule in replacements
            if rule.old
        }
        asset_by_role = {item.role: item for item in asset_items if item.role and item.path}
        image_targets = {
            _placeholder_key(rule.target): rule.asset_role
            for rule in image_rules
            if rule.target and rule.asset_role
        }
        rows: list[dict[str, object]] = []
        learned_aliases = _normalized_field_aliases(self._selected_profile().field_aliases)
        for token in tokens:
            display_token = "{{" + token + "}}"
            learned_alias_key = _learned_field_alias_for_token(token, learned_aliases)
            if learned_alias_key:
                alias_label = _field_label(learned_alias_key)
                alias_value = str(fields.get(learned_alias_key, "") or "").strip()
                if alias_value:
                    rows.append(
                        _preview_row(
                            token=token,
                            placeholder=display_token,
                            value=alias_value,
                            source=f"????{alias_label}",
                            status="???",
                            issue=False,
                            summary=f"{display_token} -> {alias_value}??????{alias_label}?",
                        )
                    )
                    continue
                rows.append(
                    _preview_row(
                        token=token,
                        placeholder=display_token,
                        value="???",
                        source=f"????{alias_label}",
                        status="???",
                        issue=True,
                        action="???",
                        action_type="field",
                        action_key=learned_alias_key,
                        summary=f"{display_token} -> ???{alias_label}",
                    )
                )
                continue
            if token in fields and fields[token]:
                field_label = _field_label(token)
                rows.append(
                    _preview_row(
                        token=token,
                        placeholder=display_token,
                        value=fields[token],
                        source=f"????{field_label}",
                        status="???",
                        issue=False,
                        summary=f"{display_token} -> {fields[token]}?{field_label}?",
                    )
                )
                continue
            if token in replacement_map:
                rows.append(
                    _preview_row(
                        token=token,
                        placeholder=display_token,
                        value=replacement_map[token],
                        source="?????",
                        status="???",
                        issue=False,
                        summary=f"{display_token} -> {replacement_map[token]}???????",
                    )
                )
                continue
            if token in self._field_inputs:
                field_label = _field_label(token)
                rows.append(
                    _preview_row(
                        token=token,
                        placeholder=display_token,
                        value="???",
                        source=f"????{field_label}",
                        status="???",
                        issue=True,
                        action="???",
                        action_type="field",
                        action_key=token,
                        summary=f"{display_token} -> ???{field_label}",
                    )
                )
                continue
            alias_key = _field_alias_for_token(token)
            if alias_key:
                alias_label = _field_label(alias_key)
                alias_value = str(fields.get(alias_key, "") or "").strip()
                rows.append(
                    _preview_row(
                        token=token,
                        placeholder=display_token,
                        value=alias_value or "???",
                        source=f"????{alias_label}",
                        status="???",
                        issue=True,
                        action="????" if alias_value else "???",
                        action_type="alias" if alias_value else "field",
                        action_key=token if alias_value else alias_key,
                        action_source=alias_key if alias_value else "",
                        summary=(
                            f"{display_token} -> ???{alias_value}?{alias_label}?"
                            if alias_value
                            else f"{display_token} -> ???{alias_label}"
                        ),
                    )
                )
                continue
            role = image_targets.get(token) or _asset_slot_role_for_token(token, self._asset_slot_specs)
            asset = asset_by_role.get(role or "")
            if asset is not None:
                role_label = _asset_role_label(role, self._asset_slot_specs)
                value = f"{role_label}?{Path(asset.path).name}"
                rows.append(
                    _preview_row(
                        token=token,
                        placeholder=display_token,
                        value=value,
                        source=f"????{role_label}",
                        status="???",
                        issue=False,
                        summary=f"{display_token} -> {value}",
                    )
                )
                continue
            attachment_role = self._attachment_role_for_token(token)
            attachment = asset_by_role.get(attachment_role or "")
            if attachment is not None:
                spec = self._attachment_role_spec(attachment_role)
                role_label = spec.label if spec is not None else attachment_role
                value = f"{role_label}?{Path(attachment.path).name}"
                rows.append(
                    _preview_row(
                        token=token,
                        placeholder=display_token,
                        value=value,
                        source=f"?????{role_label}",
                        status="???",
                        issue=False,
                        summary=f"{display_token} -> {value}",
                    )
                )
                continue
            if attachment_role:
                spec = self._attachment_role_spec(attachment_role)
                role_label = spec.label if spec is not None else attachment_role
                rows.append(
                    _preview_row(
                        token=token,
                        placeholder=display_token,
                        value=f"??{role_label}",
                        source=f"?????{role_label}",
                        status="???",
                        issue=True,
                        action="???",
                        action_type="asset",
                        action_key=attachment_role,
                        summary=f"{display_token} -> ??{role_label}",
                    )
                )
                continue
            if role:
                role_label = _asset_role_label(role, self._asset_slot_specs)
                rows.append(
                    _preview_row(
                        token=token,
                        placeholder=display_token,
                        value=f"??{role_label}",
                        source=f"????{role_label}",
                        status="???",
                        issue=True,
                        action="????",
                        action_type="asset",
                        action_key=role,
                        summary=f"{display_token} -> ??{role_label}",
                    )
                )
                continue
            rows.append(
                _preview_row(
                    token=token,
                    placeholder=display_token,
                    value="???",
                    source="?",
                    status="???",
                    issue=True,
                    action="??????",
                    action_type="custom",
                    action_key=token,
                    summary=f"{display_token} -> ???",
                )
            )
        return rows


    def _refresh_preview_table(self, rows: list[dict[str, object]]) -> None:
        if not hasattr(self, "_preview_table"):
            return
        visible_rows = self._visible_placeholder_preview_rows(rows)
        self._preview_action_buttons = {}
        self._preview_table.setVisible(bool(rows))
        self._preview_table.clearContents()
        self._preview_table.setRowCount(len(visible_rows))
        for row_index, row in enumerate(visible_rows):
            values = [
                row.get("placeholder", ""),
                row.get("value", ""),
                row.get("source", ""),
                row.get("status", ""),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self._preview_table.setItem(row_index, column, item)
            action = str(row.get("action", "") or "")
            if action:
                button = QPushButton(action, self._preview_table)
                apply_button_variant(button, "secondary")
                button.setStyleSheet(build_button_stylesheet(get_theme()))
                action_type = str(row.get("action_type", "") or "")
                action_key = str(row.get("action_key", "") or "")
                action_source = str(row.get("action_source", "") or "")
                button.clicked.connect(
                    lambda *_args, row_action=action_type, key=action_key, source=action_source: self._handle_preview_row_action(
                        row_action,
                        key,
                        source,
                    )
                )
                self._preview_table.setCellWidget(row_index, 4, button)
                self._preview_action_buttons[str(row.get("placeholder", ""))] = button
            else:
                item = QTableWidgetItem("")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self._preview_table.setItem(row_index, 4, item)
        self._preview_table.resizeRowsToContents()

    def _handle_preview_row_action(self, action_type: str, action_key: str, action_source: str = "") -> None:
        if action_type == "field":
            widget = self._field_inputs.get(action_key)
            if widget is not None:
                self._show_missing_target(widget, self._profile_card)
                widget.setFocus()
            return
        if action_type == "asset":
            if not self._focus_asset_slot(action_key):
                self._focus_attachment_role(action_key)
            return
        if action_type == "custom":
            self._add_unknown_placeholder_field(action_key)
            self._show_missing_target(self._fields_edit, self._profile_card)
            return
        if action_type == "alias":
            value = str(self._editor_fields().get(action_source, "") or "").strip()
            profile = self._selected_profile()
            profile.field_aliases[_placeholder_key(action_key)] = action_source
            self._add_unknown_placeholder_field(action_key, value=value)
            self._show_missing_target(self._fields_edit, self._profile_card)
            return


__all__ = ["PreviewTablePresenterMixin"]
