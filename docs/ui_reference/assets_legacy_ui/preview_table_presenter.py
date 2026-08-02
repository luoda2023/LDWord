"""Presenter mixin for placeholder preview table rows and row actions."""

from __future__ import annotations

from pathlib import Path

from src.config.library import CONFIG_LIBRARY_ROOT
from src.config.master_library import default_master
from src.config.master_preflight import check_master_preflight
from src.config.material_preview import scan_docx_placeholders
from src.config.materials import (
    AssetInsertionRule,
    missing_required_asset_roles,
)
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
from src.shared.ui.deferred_call import defer_qt_method
from src.shared.ui.card import Card
from src.shared.ui.theme import get_theme
from src.shared.engine.material_token_contract import (
    MaterialTokenKind,
    MaterialTokenNamespace,
    material_token,
    try_parse_material_token,
)
from src.ui.panels.assets.fields import (
    _asset_role_label,
    _field_label,
    _placeholder_key,
)
from src.ui.panels.assets.roles import _asset_slot_role_for_token
from src.services.material_content.artifact_repository import (
    ContentArtifactRepository,
    ContentArtifactRepositoryError,
)


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
        preview_card.set_header("资料预览", icon_name="eye")
        self._preview_label = QLabel(preview_card)
        self._preview_label.setWordWrap(True)
        preview_actions = QWidget(preview_card)
        preview_actions_layout = QHBoxLayout(preview_actions)
        preview_actions_layout.setContentsMargins(0, 0, 0, 0)
        preview_actions_layout.setSpacing(10)
        self._preview_filter_btn = QPushButton("只看未填写", preview_actions)
        self._preview_auto_match_btn = QPushButton("重新扫描当前文档", preview_actions)
        self._preview_auto_match_btn.clicked.connect(self._on_preview_auto_match)
        self._preview_filter_btn.clicked.connect(self._toggle_preview_filter)
        preview_actions_layout.addWidget(self._preview_auto_match_btn)
        preview_actions_layout.addWidget(self._preview_filter_btn)
        preview_actions_layout.addStretch(1)
        self._preview_table = QTableWidget(preview_card)
        self._preview_table.setObjectName("asset_placeholder_preview_table")
        self._preview_table.setColumnCount(5)
        self._preview_table.setHorizontalHeaderLabels(
            ["文档占位符", "本次内容", "资料来源", "状态", "处理"]
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
            "显示全部" if self._preview_only_issues else "只看未填写"
        )
        self._refresh_summary()

    def _on_preview_auto_match(self) -> None:
        self._placeholder_cache_path = ""
        self._placeholder_cache_mtime = None
        self._placeholder_cache_tokens = []
        target = self._current_execution_target()
        if str(getattr(target, "mode_id", "") or "") == "official":
            master = default_master("official")
            self._official_master_preflight = (
                check_master_preflight(master) if master is not None else None
            )
        self._refresh_summary()

    def _on_document_loaded(self, file_path: str) -> None:
        self._current_document_path = str(file_path or "").strip()
        self._clear_placeholder_preview_cache()
        self._refresh_summary()

    def _on_execution_target_changed(self, target) -> None:
        self._execution_target = target
        self._clear_placeholder_preview_cache()
        self._refresh_summary()

    def _clear_placeholder_preview_cache(self) -> None:
        self._placeholder_cache_path = ""
        self._placeholder_cache_mtime = None
        self._placeholder_cache_tokens = []

    def _visible_placeholder_preview_rows(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        if not self._preview_only_issues:
            return rows
        return [row for row in rows if bool(row.get("issue"))]

    def _placeholder_preview_text(
        self,
        tokens: list[str],
        fields: dict[str, str],
        asset_items,
        image_rules: list,
        *,
        preview_rows: list[dict[str, object]] | None = None,
    ) -> str:
        if not tokens:
            source_path = self._placeholder_source_path()
            if source_path:
                return "扫描来源中没有发现可填写的 {{字段}} 占位符。"
            if self._placeholder_source_kind() == "structured":
                return "当前模式由结构化资料装配，不使用通用 {{字段}} 预览。"
            return "尚未绑定执行文档；当前只能检查资料是否填写，不能判断文档占位符。"

        rows = preview_rows
        if rows is None:
            rows = self._placeholder_preview_rows(tokens, fields, asset_items, image_rules)
        visible_rows = self._visible_placeholder_preview_rows(rows)
        lines = [str(row["summary"]) for row in visible_rows[:12]]
        if len(visible_rows) > 12:
            lines.append(f"还有 {len(visible_rows) - 12} 项未显示")
        if self._preview_only_issues and not lines:
            return "当前没有需要处理的问题项。"
        return "\n".join(lines)

    def _placeholder_source_path(self) -> str:
        target = self._current_execution_target()
        source_path = str(
            getattr(target, "placeholder_source_path", "") or ""
        ).strip()
        if source_path:
            return source_path
        if str(getattr(target, "placeholder_source_kind", "") or "") == "structured":
            return ""
        # Compatibility for callers that emit document_loaded directly instead
        # of updating PanelBridge state first.
        return str(
            self._current_document_path
            or self.bridge.current_document_path()
            or ""
        ).strip()

    def _current_execution_target(self):
        target = getattr(self, "_execution_target", None)
        getter = getattr(self.bridge, "current_execution_target", None)
        if callable(getter):
            target = getter()
            self._execution_target = target
        return target

    def _placeholder_source_kind(self) -> str:
        target = self._current_execution_target()
        return str(getattr(target, "placeholder_source_kind", "") or "none")

    def _placeholder_source_label(self) -> str:
        target = self._current_execution_target()
        label = str(getattr(target, "placeholder_source_label", "") or "").strip()
        if label:
            return label
        source_path = self._placeholder_source_path()
        return Path(source_path).name if source_path else ""

    def _placeholder_field_key(self, token: str) -> str:
        target = self._current_execution_target()
        resolver = getattr(target, "binding_field_key", None)
        if callable(resolver):
            return str(resolver(token) or token)
        return token

    def _placeholder_binding_required(self, token: str) -> bool | None:
        target = self._current_execution_target()
        resolver = getattr(target, "binding_required", None)
        return resolver(token) if callable(resolver) else None

    def _scanned_placeholders(self) -> list[str]:
            target = self._current_execution_target()
            bindings = tuple(getattr(target, "placeholder_bindings", ()) or ())
            if (
                str(getattr(target, "mode_id", "") or "") == "official"
            ):
                # Official plan requirements and placeholder bindings belong
                # to workbench preflight.  The package page must not discover
                # or register tokens from the selected plan.
                return []
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
            if bindings:
                allowed = {
                    str(getattr(binding, "placeholder_key", "") or "")
                    for binding in bindings
                }
                tokens = [token for token in tokens if token in allowed]
            self._placeholder_cache_path = str(path)
            self._placeholder_cache_mtime = mtime
            self._placeholder_cache_tokens = list(tokens)
            return list(tokens)

    def _current_preview_state(self) -> dict[str, object]:
            fields = self._material_preview_fields()
            timeline_resolver = getattr(self, "_resolve_timeline_preview_fields", None)
            if callable(timeline_resolver):
                fields = timeline_resolver(fields)
            asset_items = self._current_asset_items()
            image_rules = self._image_rules_for_asset_items(asset_items)
            placeholder_tokens = self._scanned_placeholders()
            missing_image_roles = missing_required_asset_roles(asset_items, image_rules)
            missing_attachment_roles = self._missing_attachment_roles()
            missing_asset_roles = [*missing_image_roles, *missing_attachment_roles]
            unmatched_placeholders = self._unmatched_placeholders(
                placeholder_tokens,
                fields,
                asset_items,
                image_rules,
            )
            return {
                "fields": fields,
                "asset_items": asset_items,
                "image_rules": image_rules,
                "placeholder_tokens": placeholder_tokens,
                "missing_asset_roles": missing_asset_roles,
                "missing_image_roles": missing_image_roles,
                "missing_attachment_roles": missing_attachment_roles,
                "unmatched_placeholders": unmatched_placeholders,
            }

    def _missing_attachment_roles(self) -> list[str]:
            return [
                spec.role
                for spec in self._attachment_role_specs
                if spec.required
                and not tuple(
                    getattr(self._attachment_bindings.get(spec.role), "items", ())
                    or ()
                )
            ]

    def _unmatched_placeholders(
            self,
            tokens: list[str],
            fields: dict[str, str],
            asset_items,
            image_rules: list[AssetInsertionRule],
        ) -> list[str]:
            available_roles = {item.role for item in asset_items if item.role and item.path}
            image_targets = {
                _placeholder_key(rule.target): rule.asset_role
                for rule in image_rules
                if rule.target and rule.asset_role
            }
            unmatched: list[str] = []
            for token in tokens:
                ref = try_parse_material_token(token)
                if ref is not None and ref.kind is MaterialTokenKind.CONTENT:
                    content_id = ref.identifier
                    rule = next(
                        (
                            item
                            for item in self._content_rules
                            if item.content_id == content_id
                        ),
                        None,
                    )
                    if rule is not None and content_id in self._content_bindings:
                        continue
                    unmatched.append(token)
                    continue
                if ref is not None and ref.kind is MaterialTokenKind.ATTACHMENT:
                    binding = self._attachment_bindings.get(ref.identifier)
                    if binding is not None and binding.items:
                        continue
                    unmatched.append(token)
                    continue
                field_key = self._placeholder_field_key(token)
                if field_key in fields and fields[field_key]:
                    continue
                if self._placeholder_binding_required(token) is False:
                    continue
                role = (
                    image_targets.get(token)
                    or _asset_slot_role_for_token(token, self._asset_slot_specs)
                )
                if role and role in available_roles:
                    continue
                unmatched.append(token)
            return unmatched

    def _placeholder_preview_rows(
        self,
        tokens: list[str],
        fields: dict[str, str],
        asset_items,
        image_rules: list[AssetInsertionRule],
    ) -> list[dict[str, object]]:
        if not tokens:
            pending_status = (
                "结构化装配"
                if self._placeholder_source_kind() == "structured"
                else "待检测"
            )
            return [
                _preview_row(
                    token=key,
                    placeholder=material_token(MaterialTokenNamespace.TEXT, key),
                    value=value,
                    source="资料字段",
                    status=pending_status,
                    issue=False,
                    summary=(
                        material_token(MaterialTokenNamespace.TEXT, key)
                        + f" -> {value}（{pending_status}）"
                    ),
                )
                for key, value in fields.items()
                if str(key or "").strip() and str(value or "").strip()
            ]
        asset_by_role = {item.role: item for item in asset_items if item.role and item.path}
        image_targets = {
            _placeholder_key(rule.target): rule.asset_role
            for rule in image_rules
            if rule.target and rule.asset_role
        }
        rows: list[dict[str, object]] = []
        for token in tokens:
            ref = try_parse_material_token(token)
            display_token = (
                ref.token
                if ref is not None
                else material_token(MaterialTokenNamespace.TEXT, token)
            )
            if ref is not None and ref.kind is MaterialTokenKind.CONTENT:
                content_id = ref.identifier
                rule = next(
                    (
                        item
                        for item in self._content_rules
                        if item.content_id == content_id
                    ),
                    None,
                )
                binding = self._content_bindings.get(content_id)
                if rule is not None and binding is not None:
                    try:
                        value = ContentArtifactRepository(
                            CONFIG_LIBRARY_ROOT / "content_artifacts"
                        ).validate(binding.artifact_ref).manifest.source.original_name
                    except ContentArtifactRepositoryError:
                        value = binding.label
                    rows.append(
                        _preview_row(
                            token=token,
                            placeholder=display_token,
                            value=value,
                            source=f"文件资料：{binding.label}",
                            status="已匹配",
                            issue=False,
                            summary=f"{display_token} -> {value}",
                        )
                    )
                else:
                    rows.append(
                        _preview_row(
                            token=token,
                            placeholder=display_token,
                            value="未绑定 Markdown/DOCX",
                            source="文件资料",
                            status="缺少",
                            issue=True,
                            action="去选择",
                            action_type="content",
                            action_key=content_id,
                            summary=f"{display_token} -> 缺少文件资料",
                        )
                    )
                continue
            if ref is not None and ref.kind is MaterialTokenKind.ATTACHMENT:
                binding = self._attachment_bindings.get(ref.identifier)
                selected = binding is not None and bool(binding.items)
                rows.append(
                    _preview_row(
                        token=token,
                        placeholder=display_token,
                        value=(
                            " / ".join(
                                item.label or item.file_ref.original_name
                                for item in binding.items
                            )
                            if selected
                            else "未选择附件"
                        ),
                        source="附件资料",
                        status="已匹配" if selected else "缺少",
                        issue=not selected,
                        action="去选择" if not selected else "",
                        action_type="attachments" if not selected else "",
                        action_key=ref.identifier if not selected else "",
                        summary=display_token,
                    )
                )
                continue
            field_key = self._placeholder_field_key(token)
            contract_bound = field_key != token
            if field_key in fields and fields[field_key]:
                field_label = _field_label(field_key)
                source_label = (
                    f"母版合同：{field_label}"
                    if contract_bound
                    else f"资料字段：{field_label}"
                )
                rows.append(
                    _preview_row(
                        token=token,
                        placeholder=display_token,
                        value=fields[field_key],
                        source=source_label,
                        status="可写入",
                        issue=False,
                        summary=f"{display_token} -> {fields[field_key]}（{field_label}）",
                    )
                )
                continue
            binding_required = self._placeholder_binding_required(token)
            if contract_bound:
                field_label = _field_label(field_key)
                if binding_required is False:
                    rows.append(
                        _preview_row(
                            token=token,
                            placeholder=display_token,
                            value="空值时省略",
                            source=f"母版合同：{field_label}",
                            status="可省略",
                            issue=False,
                            summary=f"{display_token} -> 空值时省略（{field_label}）",
                        )
                    )
                    continue
                rows.append(
                    _preview_row(
                        token=token,
                        placeholder=display_token,
                        value="未填写",
                        source=f"母版合同：{field_label}",
                        status="未填写",
                        issue=True,
                        action="去填写",
                        action_type="field" if field_key in self._field_inputs else "custom",
                        action_key=field_key,
                        summary=f"{display_token} -> 未填写{field_label}",
                    )
                )
                continue
            if field_key in self._field_inputs:
                field_label = _field_label(field_key)
                rows.append(
                    _preview_row(
                        token=token,
                        placeholder=display_token,
                        value="待填写",
                        source=(
                            f"母版合同：{field_label}"
                            if contract_bound
                            else f"资料字段：{field_label}"
                        ),
                        status="缺少",
                        issue=True,
                        action="去填写",
                        action_type="field",
                        action_key=field_key,
                        summary=f"{display_token} -> 待填写{field_label}",
                    )
                )
                continue
            role = image_targets.get(token) or _asset_slot_role_for_token(token, self._asset_slot_specs)
            asset = asset_by_role.get(role or "")
            if asset is not None:
                role_label = _asset_role_label(role, self._asset_slot_specs)
                value = f"{role_label}：{Path(asset.path).name}"
                rows.append(
                    _preview_row(
                        token=token,
                        placeholder=display_token,
                        value=value,
                        source=f"图片资料：{role_label}",
                        status="已匹配",
                        issue=False,
                        summary=f"{display_token} -> {value}",
                    )
                )
                continue
            if role:
                role_label = _asset_role_label(role, self._asset_slot_specs)
                rows.append(
                    _preview_row(
                        token=token,
                        placeholder=display_token,
                        value=f"缺少{role_label}",
                        source=f"图片资料：{role_label}",
                        status="缺少",
                        issue=True,
                        action="去选图",
                        action_type="asset",
                        action_key=role,
                        summary=f"{display_token} -> 缺少{role_label}",
                    )
                )
                continue
            rows.append(
                _preview_row(
                    token=token,
                    placeholder=display_token,
                    value="未填写",
                    source="文档占位符",
                    status="未填写",
                    issue=True,
                    action="填写资料",
                    action_type="custom",
                    action_key=field_key,
                    summary=f"{display_token} -> 未填写",
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
                    lambda *_args, row_action=action_type, key=action_key, source=action_source: defer_qt_method(
                        self,
                        "_handle_preview_row_action",
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

    def _update_preview_field_value(self, field_key: str, value: str) -> None:
        """Update visible preview cells without rebuilding the whole panel."""

        cleaned_key = str(field_key or "").strip()
        cleaned_value = str(value or "").strip()
        if not cleaned_key:
            return
        for table, value_column, status_column in (
            (getattr(self, "_overview_preview_table", None), 1, 2),
            (getattr(self, "_preview_table", None), 1, 3),
        ):
            if table is None:
                continue
            for row_index in range(table.rowCount()):
                placeholder_item = table.item(row_index, 0)
                if placeholder_item is None:
                    continue
                token = _placeholder_key(placeholder_item.text())
                if self._placeholder_field_key(token) != cleaned_key:
                    continue
                required = self._placeholder_binding_required(token)
                if cleaned_value:
                    next_value, next_status = cleaned_value, "可写入"
                elif required is False:
                    next_value, next_status = "空值时省略", "可省略"
                else:
                    next_value, next_status = "未填写", "未填写"
                value_item = table.item(row_index, value_column)
                status_item = table.item(row_index, status_column)
                if value_item is not None:
                    value_item.setText(next_value)
                if status_item is not None:
                    status_item.setText(next_status)

    def _handle_preview_row_action(self, action_type: str, action_key: str, action_source: str = "") -> None:
        if action_type == "field":
            widget = (
                self._field_inputs.get(action_key)
                or self._official_fixed_field_inputs.get(action_key)
                or self._official_floating_field_previews.get(action_key)
                or self._official_field_rows.get(action_key)
                or self._template_field_inputs.get(action_key)
            )
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
            key = _placeholder_key(action_key)
            widget = (
                self._official_fixed_field_inputs.get(key)
                or self._official_floating_field_previews.get(key)
                or self._official_field_rows.get(key)
            )
            if widget is not None:
                self._show_missing_target(widget, self._profile_card)
            return
        if action_type == "content":
            self._focus_content_material(action_key)
            return
        if action_type == "alias":
            value = str(self._editor_fields().get(action_source, "") or "").strip()
            profile = self._selected_profile()
            profile.field_aliases[_placeholder_key(action_key)] = action_source
            self._add_unknown_placeholder_field(action_key, value=value)
            key = _placeholder_key(action_key)
            widget = (
                self._official_fixed_field_inputs.get(key)
                or self._official_floating_field_previews.get(key)
                or self._official_field_rows.get(key)
            )
            if widget is not None:
                self._show_missing_target(widget, self._profile_card)
            return


__all__ = ["PreviewTablePresenterMixin"]
