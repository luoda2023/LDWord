"""Presenter mixin for field status and unknown placeholder suggestions."""

from __future__ import annotations

import re

from src.config.material_field_inventory import (
    discard_material_field,
    normalize_material_field_inventory,
    rename_material_field,
)
from src.config.official_material_form import OFFICIAL_MATERIAL_FIELD_SPECS
from src.shared.engine.material_field_function import (
    describe_field_function,
    resolve_field_functions,
)
from src.shared.engine.material_timeline import timeline_owned_field_keys
from src.shared.engine.material_token_contract import (
    MaterialTokenKind,
    MaterialTokenNamespace,
    material_token,
    parse_material_token,
)
from src.qt_api import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTimer,
    Qt,
    QWidget,
)
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.compact_row_actions import (
    CompactRowActions,
    apply_compact_row_action,
)
from src.shared.ui.dialogs import confirm
from src.shared.ui.keyed_widget_list import KeyedWidgetListController
from src.shared.ui.material_token_edit import MaterialTokenEdit
from src.shared.ui.material_text_views import ElidedValueEdit
from src.shared.ui.official_field_value_edit import OfficialFieldValueEdit
from src.shared.ui.deferred_call import defer_qt_method
from src.shared.ui.layout_sync import (
    refresh_layout_chain,
    refresh_layout_chain_later,
    updates_suspended,
)
from src.shared.ui.theme import get_theme
from src.shared.ui.token_column_guide import TokenColumnMetrics
from src.shared.ui.token_row_style import apply_token_row_style
from src.shared.ui.toast import Toast
from src.shared.ui.viewport_mutation import viewport_mutation
from src.ui.panels.assets.fields import (
    MATERIAL_FIELD_DRAFT_PREFIX,
    _field_label,
    _placeholder_key,
)
from src.ui.panels.assets.field_function_dialog import choose_official_field_function
from src.ui.panels.assets.token_naming import (
    is_numbered_series_name,
    next_numbered_name,
    next_series_name,
    numbered_series_prefix,
)

class MaterialFieldCodeEdit(MaterialTokenEdit):
    """Editable field token whose braces are structural, not user text."""

    def __init__(self, parent=None) -> None:
        super().__init__(
            "",
            parent,
            editable=True,
            namespace=MaterialTokenNamespace.TEXT,
        )


OfficialFieldNameEdit = MaterialTokenEdit


class FieldStatusPresenterMixin:
    """Refresh local field status rows and unknown-placeholder helpers."""

    def _refresh_field_statuses(self, state: dict[str, object]) -> None:
        self._profile_card.set_header("字段资料", icon_name="type")
        self._profile_form.setVisible(False)
        self._field_mapping_example.setVisible(False)
        self._field_toolbar.setVisible(False)
        self._field_columns.setVisible(False)
        self._empty_fields_label.setVisible(False)
        self._unknown_fields_container.setVisible(False)
        legacy_controller = getattr(self, "_unknown_fields_controller", None)
        if legacy_controller is not None:
            legacy_controller.reconcile([])
        self._official_fields_panel.setVisible(True)
        self._refresh_official_field_editor()
        self._sync_field_conflict_hint()

    def _sync_field_conflict_hint(self) -> None:
        if not hasattr(self, "_fields_hint_label"):
            return
        conflicts = tuple(getattr(self, "_field_conflicts", ()) or ())
        self._fields_hint_label.setVisible(bool(conflicts))
        self._fields_hint_label.setText(
            "无法写入：字段重复或目标冲突：" + "、".join(conflicts)
            if conflicts
            else ""
        )

    def _refresh_unknown_field_suggestions(
        self,
        tokens: list[str],
        *,
        capture_live_values: bool = True,
    ) -> None:
        if not hasattr(self, "_unknown_fields_container"):
            return
        document_tokens = list(dict.fromkeys(tokens))
        self._document_field_order = document_tokens
        self._document_field_keys = set(document_tokens)
        visible_tokens = document_tokens + [
            key for key in self._manual_field_keys if key not in self._document_field_keys
        ]
        if capture_live_values:
            for old_token, old_edit in self._template_field_inputs.items():
                if bool(old_edit.property("timelineOwned")):
                    continue
                old_value = old_edit.text().strip()
                if old_value:
                    self._template_field_values[old_token] = old_value
                else:
                    self._template_field_values.pop(old_token, None)
        current_values = {
            token: str(self._template_field_values.get(token, "") or "")
            for token in visible_tokens
        }
        timeline_fields = set(
            getattr(self, "_timeline_output_field_keys", lambda: set())()
        )
        timeline_values = dict(
            getattr(getattr(self, "_timeline_resolution", None), "values", {})
            or {}
        )
        for token in visible_tokens:
            if token in timeline_fields:
                current_values[token] = str(timeline_values.get(token, "") or "")
        self._unknown_field_render_values = current_values
        controller = getattr(self, "_unknown_fields_controller", None)
        if controller is None:
            controller = KeyedWidgetListController[str, str](
                layout=self._unknown_fields_layout,
                create_widget=self._create_unknown_field_row,
                update_widget=self._update_unknown_field_row,
                dispose_widget=self._dispose_unknown_field_row,
                key=str,
            )
            self._unknown_fields_controller = controller
        with updates_suspended(self._unknown_fields_container, getattr(self, "_detail_shell", self)):
            self._unknown_fields_container.setVisible(bool(visible_tokens))
            if hasattr(self, "_empty_fields_label"):
                self._empty_fields_label.setVisible(not visible_tokens)
            controller.reconcile(visible_tokens)
            refresh_layout_chain(self._unknown_fields_container, passes=2)

    def _refresh_unknown_fields_preserving_view(
        self,
        tokens: list[str],
        *,
        anchor: QWidget | None = None,
        capture_live_values: bool = True,
    ) -> None:
        scroll = getattr(self, "_detail_scroll", None)
        detail_page = getattr(self, "_section_contents", {}).get("fields")
        if scroll is None or detail_page is None:
            self._refresh_unknown_field_suggestions(
                tokens,
                capture_live_values=capture_live_values,
            )
            return
        with viewport_mutation(
            scroll=scroll,
            content=detail_page,
            anchor=anchor,
            layout_roots=(self._unknown_fields_container,),
            geometry_sync=getattr(self, "_detail_geometry", None),
            geometry_detail=detail_page,
            paint_targets=(self._unknown_fields_container,),
        ):
            self._refresh_unknown_field_suggestions(
                tokens,
                capture_live_values=capture_live_values,
            )

    def _surviving_unknown_field_anchor(self, key: str) -> QWidget | None:
        controller = getattr(self, "_unknown_fields_controller", None)
        keys = list(controller.keys()) if controller is not None else []
        if key in keys:
            index = keys.index(key)
            for candidate_index in (index + 1, index - 1):
                if 0 <= candidate_index < len(keys):
                    candidate = self._unknown_field_rows.get(keys[candidate_index])
                    if candidate is not None:
                        return candidate
        return getattr(self, "_add_material_field_btn", None)
    def _create_unknown_field_row(self, token: str) -> QFrame:
        row = QFrame(self._unknown_fields_container)
        row.setObjectName("unknown_field_suggestion")
        row.setProperty("materialFieldKey", token)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        code_edit = MaterialFieldCodeEdit(row)
        code_edit.setObjectName("material_field_code_input")
        code_edit.setProperty("materialFieldKey", token)
        code_edit.setPlaceholderText("例如：公司名称")
        code_edit.editingFinished.connect(
            lambda widget=code_edit: self._commit_material_field_key(
                str(widget.property("materialFieldKey") or ""),
                widget.text(),
            )
        )
        edit = ElidedValueEdit(parent=row)
        edit.setObjectName("material_field_value_input")
        edit.textChanged.connect(
            lambda value, field_key=token: self._on_template_field_input_changed(
                field_key,
                value,
            )
        )
        remove_btn = QPushButton("删除", row)
        remove_btn.setObjectName("material_field_remove_btn")
        apply_button_variant(remove_btn, "ghost-danger")
        remove_btn.clicked.connect(
            lambda _checked=False, field_key=token: defer_qt_method(
                self,
                "_remove_manual_field",
                field_key,
            )
        )
        layout.addWidget(code_edit, 2)
        layout.addWidget(edit, 3)
        layout.addWidget(remove_btn, 0)

        self._unknown_field_rows[token] = row
        self._template_field_key_inputs[token] = code_edit
        self._template_field_inputs[token] = edit
        self._unknown_field_remove_buttons[token] = remove_btn
        row.setVisible(True)
        return row

    def _update_unknown_field_row(
        self,
        row: QFrame,
        token: str,
        _index: int,
    ) -> None:
        code_edit = self._template_field_key_inputs[token]
        edit = self._template_field_inputs[token]
        remove_btn = self._unknown_field_remove_buttons[token]
        is_draft = token.startswith(MATERIAL_FIELD_DRAFT_PREFIX)
        target = self._current_execution_target()
        is_official_field = (
            str(getattr(target, "mode_id", "") or "") == "official"
            and str(self._selected_profile().field_scopes.get(token, ""))
            in {"fixed", "floating"}
        )
        timeline_owned = token in self._timeline_managed_field_keys()
        timeline_namespace_owned = token in set(
            timeline_owned_field_keys(
                self._selected_profile().timeline_plans,
                include_inactive=True,
            )
        )
        code_edit.setProperty("materialFieldKey", token)
        code_edit.setReadOnly(
            token in self._document_field_keys or is_official_field or timeline_owned
        )
        desired_code = (
            ""
            if is_draft
            else material_token(MaterialTokenNamespace.TEXT, _field_label(token))
            if is_official_field
            else material_token(
                MaterialTokenNamespace.TIME
                if timeline_namespace_owned
                else MaterialTokenNamespace.TEXT,
                token,
            )
        )
        if not code_edit.hasFocus() and code_edit.text() != desired_code:
            blocked = code_edit.blockSignals(True)
            code_edit.setText(desired_code)
            code_edit.blockSignals(blocked)
        code_edit.setAccessibleName(
            f"由当前公文文种确定；资料字段：{token}"
            if is_official_field
            else "来自当前文档，代码不可修改"
            if token in self._document_field_keys
            else "只输入名称即可，确认后生成 @text 占位符"
        )
        edit.setPlaceholderText(
            "由时间计划计算"
            if timeline_owned
            else f"请输入{_field_label(token)}"
            if is_official_field
            else "例如：阿拉维特科技"
        )
        edit.setProperty("timelineOwned", timeline_owned)
        edit.setReadOnly(timeline_owned)
        value = str(self._unknown_field_render_values.get(token, "") or "")
        if not edit.hasFocus() and edit.text() != value:
            blocked = edit.blockSignals(True)
            edit.setText(value)
            edit.blockSignals(blocked)
        remove_btn.setVisible(token not in self._document_field_keys)
        remove_btn.setEnabled(not timeline_owned)
        if timeline_owned:
            remove_btn.setToolTip("由时间计划管理")
        theme = get_theme()
        remove_btn.setStyleSheet(build_button_stylesheet(theme))
        row.setStyleSheet(
            f"""
            QFrame#unknown_field_suggestion {{
                background: {theme.bg_input};
                border: 1px solid {theme.border_light};
                border-radius: {theme.input_radius}px;
            }}
            """
        )
        row.setVisible(True)

    def _dispose_unknown_field_row(self, row: QFrame) -> None:
        token = str(row.property("materialFieldKey") or "")
        self._unknown_field_rows.pop(token, None)
        self._template_field_key_inputs.pop(token, None)
        self._template_field_inputs.pop(token, None)
        self._unknown_field_remove_buttons.pop(token, None)
        row.setParent(None)
        row.deleteLater()

    def _official_contract_field_keys(self) -> tuple[str, ...]:
        target = self._current_execution_target()
        return tuple(
            dict.fromkeys(
                str(getattr(binding, "field_key", "") or "").strip()
                for binding in tuple(getattr(target, "placeholder_bindings", ()) or ())
                if str(getattr(binding, "field_key", "") or "").strip()
            )
        )

    def _official_field_scope_projection(self) -> tuple[list[str], list[str]]:
        profile = self._selected_profile()
        inventory = normalize_material_field_inventory(profile)
        return list(inventory.fixed_keys), list(inventory.floating_keys)

    @staticmethod
    def _official_field_kind_label(key: str) -> str:
        kinds = {spec.field_key: spec.editor_kind for spec in OFFICIAL_MATERIAL_FIELD_SPECS}
        labels = {
            "single_line": "单行",
            "multiline": "多行",
            "date": "日期",
            "multi_value": "多值",
            "attachment_list": "附件",
        }
        return labels.get(kinds.get(key, "single_line"), "单行")

    @staticmethod
    def _official_editor_kind(key: str) -> str:
        if re.fullmatch(
            r"时间段(?:\d+(?:开始|结束)日期|(?:开始|结束)日期\d+)",
            str(key or ""),
        ):
            return "date"
        kinds = {spec.field_key: spec.editor_kind for spec in OFFICIAL_MATERIAL_FIELD_SPECS}
        return kinds.get(key, "single_line")

    @staticmethod
    def _is_timeline_anchor_field(key: str) -> bool:
        return bool(
            re.fullmatch(
                r"时间段(?:\d+(?:开始|结束)日期|(?:开始|结束)日期\d+)",
                str(key or ""),
            )
        )

    def _timeline_managed_field_keys(self) -> set[str]:
        """Return fields referenced by every non-deleted timeline plan."""

        plans = {
            plan_id: plan
            for plan_id, plan in dict(
                self._selected_profile().timeline_plans or {}
            ).items()
            if not isinstance(plan, dict) or not bool(plan.get("deleted", False))
        }
        return set(timeline_owned_field_keys(plans, include_inactive=True))

    def _official_editor_placeholder(
        self, key: str, *, read_only: bool = False
    ) -> str:
        if read_only:
            return "在工作台填写"
        kind = self._official_editor_kind(key)
        label = self._official_field_display_label(key)
        if kind == "date":
            return "例如：2026年7月11日"
        if kind == "multi_value":
            return f"填写{label}，使用顿号分隔"
        return f"填写{label}"

    def _official_series_label(self, key: str) -> str:
        """Return the canonical visible identifier for one package field.

        Generic and user-created fields retain their exact package identifier.
        The numbered Chinese label is only a compatibility projection for the
        legacy built-in official field IDs.
        """

        target = self._current_execution_target()
        official_keys = {spec.field_key for spec in OFFICIAL_MATERIAL_FIELD_SPECS}
        if (
            str(getattr(target, "mode_id", "") or "") == "official"
            and key in official_keys
        ):
            label = _field_label(key)
            if self._is_timeline_anchor_field(key):
                return label
            return label if re.search(r"\d+$", label) else f"{label}1"
        return str(key or "").strip()

    @staticmethod
    def _build_official_field_index(
        row: QFrame,
        index: int,
        _scope_label: str,
    ) -> QLabel:
        theme = get_theme()
        number = QLabel(str(index), row)
        number.setObjectName("official_material_field_index")
        number.setFixedSize(28, 28)
        number.setAlignment(Qt.AlignCenter)
        number.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; font-weight: {theme.font_weight_emphasis}; "
            f"color: {theme.primary}; background: transparent; border: none;"
        )
        return number

    def _refresh_official_field_editor(self) -> None:
        fixed, floating = self._official_field_scope_projection()
        repaired_aliases = self._repair_official_duplicate_display_names(
            [*fixed, *floating]
        )
        if repaired_aliases:
            defer_qt_method(self, "_apply_current_profile")
        self._official_fixed_field_keys = fixed
        self._official_floating_field_keys = floating
        self._recalculate_official_field_functions()
        self._official_fixed_count.setText(f"{len(fixed)} 项")
        self._official_floating_count.setText(f"{len(floating)} 项")

        if (
            tuple(fixed) == self._rendered_official_fixed_field_keys
            and tuple(floating) == self._rendered_official_floating_field_keys
        ):
            self._sync_existing_official_field_rows(fixed, floating)
            refresh_layout_chain_later(self._official_fields_panel, passes=3)
            return

        self._reconcile_official_field_section(fixed, scope="fixed")
        self._reconcile_official_field_section(floating, scope="floating")

        self._rendered_official_fixed_field_keys = tuple(fixed)
        self._rendered_official_floating_field_keys = tuple(floating)
        refresh_layout_chain(self._official_fields_panel, passes=2)
        refresh_layout_chain_later(self._official_fields_panel, passes=3)

    def _reconcile_official_field_section(
        self,
        keys: list[str],
        *,
        scope: str,
    ) -> None:
        layout = (
            self._official_fixed_layout
            if scope == "fixed"
            else self._official_floating_layout
        )
        controller_name = (
            "_official_fixed_fields_controller"
            if scope == "fixed"
            else "_official_floating_fields_controller"
        )
        controller = getattr(self, controller_name, None)
        if controller is None:
            controller = KeyedWidgetListController[tuple[str, bool], str](
                layout=layout,
                create_widget=lambda item, row_scope=scope: (
                    self._create_official_field_row(item[0], scope=row_scope)
                ),
                update_widget=lambda row, item, index, row_scope=scope: (
                    self._update_official_field_widget(
                        row,
                        item,
                        index,
                        scope=row_scope,
                    )
                ),
                dispose_widget=self._dispose_official_field_widget,
                key=lambda item: item[0],
            )
            setattr(self, controller_name, controller)
        controller.reconcile(
            [(key, index == len(keys) - 1) for index, key in enumerate(keys)]
        )
        guide = getattr(
            self,
            (
                "_official_fixed_column_guide"
                if scope == "fixed"
                else "_official_floating_column_guide"
            ),
            None,
        )
        if guide is not None:
            self._apply_official_field_column_metrics(scope, guide.metrics())

    def _apply_official_field_column_metrics(
        self,
        scope: str,
        metrics: TokenColumnMetrics,
    ) -> None:
        """Apply the same column contract used by the section guide."""

        if not isinstance(metrics, TokenColumnMetrics):
            return
        for key, row_scope in self._official_field_row_scopes.items():
            if row_scope != scope:
                continue
            row = self._official_field_rows.get(key)
            label = self._official_field_name_labels.get(key)
            index_label = self._official_field_index_labels.get(key)
            if row is None or label is None or index_label is None:
                continue
            layout = row.layout()
            if layout is not None:
                layout.setContentsMargins(
                    metrics.row_margin_x,
                    get_theme().token_row_padding_y,
                    metrics.row_margin_x,
                    get_theme().token_row_padding_y,
                )
                layout.setSpacing(metrics.column_gap)
            index_label.setFixedSize(metrics.index_width, metrics.index_width)
            label.setFixedWidth(metrics.token_width)
        container = (
            self._official_fixed_container
            if scope == "fixed"
            else self._official_floating_container
        )
        container.updateGeometry()

    def _create_official_field_row(self, key: str, *, scope: str) -> QFrame:
        parent = (
            self._official_fixed_container
            if scope == "fixed"
            else self._official_floating_container
        )
        row = QFrame(parent)
        row.setObjectName("official_material_field_row")
        row.setProperty("fieldKey", key)
        row.setAttribute(Qt.WA_StyledBackground)
        row.setMinimumHeight(get_theme().token_row_min_height)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(
            4,
            get_theme().token_row_padding_y,
            4,
            get_theme().token_row_padding_y,
        )
        row_layout.setSpacing(get_theme().token_row_column_gap)

        index_label = self._build_official_field_index(
            row,
            1,
            "固定" if scope == "fixed" else "自由",
        )
        row_layout.addWidget(index_label, 0)

        value = self._material_field_render_value(key, scope)
        label = OfficialFieldNameEdit(
            self._official_field_display_name(key, value),
            row,
        )
        label.setObjectName("official_material_field_name")
        label.setMinimumWidth(0)
        label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        label.editingFinished.connect(
            lambda field_key=key, widget=label: self._commit_official_field_name(
                field_key,
                widget.text(),
            )
        )
        label.copied.connect(lambda _text: Toast.show_success("复制成功"))
        row_layout.addWidget(label, 0)

        edit = OfficialFieldValueEdit(
            editor_kind=self._official_editor_kind(key),
            read_only=(
                scope == "floating"
                or key in self._selected_profile().field_functions
                or key in getattr(self, "_timeline_output_field_keys", lambda: set())()
            ),
            click_copy_double_edit=True,
            parent=row,
        )
        edit.setObjectName(
            "official_fixed_field_input"
            if scope == "fixed"
            else "official_floating_field_preview"
        )
        edit.setText(value)
        edit.copied.connect(lambda _text: Toast.show_success("复制成功"))
        if scope == "fixed":
            edit.textChanged.connect(
                lambda text, field_key=key: self._on_official_fixed_value_changed(
                    field_key,
                    text,
                )
            )
            self._official_fixed_field_inputs[key] = edit
            self._template_field_inputs[key] = edit
        else:
            self._official_floating_field_previews[key] = edit
        row_layout.addWidget(edit, 1)
        row_layout.addWidget(
            self._build_official_field_actions(row, key, scope),
            0,
        )

        self._official_field_rows[key] = row
        self._official_field_index_labels[key] = index_label
        self._official_field_name_labels[key] = label
        self._official_field_row_scopes[key] = scope
        return row

    def _update_official_field_widget(
        self,
        row: QWidget,
        item: tuple[str, bool],
        index: int,
        *,
        scope: str,
    ) -> None:
        key, is_last = item
        row.setVisible(True)
        self._sync_official_field_row(
            key,
            scope=scope,
            index=index,
            is_last=is_last,
        )

    def _sync_official_field_row(
        self,
        key: str,
        *,
        scope: str,
        index: int,
        is_last: bool,
    ) -> None:
        value = self._material_field_render_value(key, scope)
        index_label = self._official_field_index_labels.get(key)
        if index_label is not None:
            index_label.setText(str(index + 1))
        label = self._official_field_name_labels.get(key)
        if label is not None and not label.hasFocus():
            label.setText(self._official_field_display_name(key, value))
            self._style_official_field_name(label, value)
        edit = self._official_fixed_field_inputs.get(
            key
        ) or self._official_floating_field_previews.get(key)
        if edit is not None:
            if not edit.hasFocus() and edit.text() != value:
                blocked = edit.blockSignals(True)
                edit.setText(value)
                edit.blockSignals(blocked)
            edit.setPlaceholderText(
                self._official_editor_placeholder(
                    key,
                    read_only=scope == "floating",
                )
            )
            self._sync_official_function_edit_state(key, edit, scope)
        self._sync_official_function_button(key)
        row = self._official_field_rows.get(key)
        if row is not None:
            self._style_official_field_row(row, is_last=is_last)

    def _dispose_official_field_widget(self, row: QWidget) -> None:
        key = str(row.property("fieldKey") or "")
        if self._official_field_rows.get(key) is row:
            self._official_field_rows.pop(key, None)
            self._official_field_row_scopes.pop(key, None)
        for mapping in (
            self._official_field_index_labels,
            self._official_field_name_labels,
            self._official_function_buttons,
            self._official_fixed_field_inputs,
            self._official_floating_field_previews,
            self._template_field_inputs,
        ):
            widget = mapping.get(key)
            if widget is not None and (widget is row or row.isAncestorOf(widget)):
                mapping.pop(key, None)
        row.setParent(None)
        row.deleteLater()

    def _sync_existing_official_field_rows(
        self,
        fixed: list[str],
        floating: list[str],
    ) -> None:
        for key in (*fixed, *floating):
            scope = "fixed" if key in fixed else "floating"
            value = self._material_field_render_value(key, scope)
            edit = self._official_fixed_field_inputs.get(
                key
            ) or self._official_floating_field_previews.get(key)
            if edit is not None and not edit.hasFocus() and edit.text() != value:
                blocked = edit.blockSignals(True)
                edit.setText(value)
                edit.blockSignals(blocked)
            if edit is not None:
                edit.setPlaceholderText(
                    self._official_editor_placeholder(
                        key,
                        read_only=scope == "floating",
                    )
                )
                self._sync_official_function_edit_state(key, edit, scope)
            self._sync_official_function_button(key)
            label = self._official_field_name_labels.get(key)
            if label is not None:
                label.setText(self._official_field_display_name(key, value))
                self._style_official_field_name(label, value)

    def _official_field_display_name(self, key: str, _value: object = "") -> str:
        aliases = [
            str(alias)
            for alias, field_key in dict(
                self._selected_profile().field_aliases or {}
            ).items()
            if str(field_key or "").strip() == key and str(alias or "").strip()
        ]
        label = aliases[-1] if aliases else self._official_series_label(key)
        return material_token(MaterialTokenNamespace.TEXT, label)

    def _official_field_display_label(self, key: str) -> str:
        return parse_material_token(self._official_field_display_name(key)).identifier

    @staticmethod
    def _next_official_series_name(label: str, occupied: set[str]) -> str:
        return next_series_name(label, occupied)

    def _repair_official_duplicate_display_names(self, keys: list[str]) -> bool:
        """Migrate rows created before display aliases participated in numbering."""

        profile = self._selected_profile()
        occupied = self._official_field_occupied_names()
        used: set[str] = set()
        repaired = False
        for key in keys:
            display_name = self._official_field_display_label(key)
            if display_name not in used:
                used.add(display_name)
                continue
            replacement = self._next_official_series_name(
                display_name,
                occupied | used,
            )
            profile.field_aliases = {
                alias: target
                for alias, target in dict(profile.field_aliases or {}).items()
                if str(target or "").strip() != key
            }
            if replacement != self._official_series_label(key):
                profile.field_aliases[replacement] = key
            occupied.add(replacement)
            used.add(replacement)
            repaired = True
        return repaired

    def _official_field_occupied_names(self, *, exclude_key: str = "") -> set[str]:
        profile = self._selected_profile()
        keys = (
            set(profile.field_scopes)
            | set(profile.fields)
        ) - {exclude_key}
        aliases = {
            str(alias)
            for alias, target in dict(profile.field_aliases or {}).items()
            if str(alias or "").strip()
            and str(target or "").strip() != exclude_key
        }
        display_names = {
            self._official_field_display_label(field_key)
            for field_key in keys
            if str(field_key or "").strip()
        }
        return keys | aliases | display_names

    def _commit_official_field_name(self, key: str, raw_name: str) -> None:
        label = self._official_field_name_labels.get(key)
        current_display = self._official_field_display_name(key)
        name = self._exact_material_field_key(raw_name)
        if not name:
            if label is not None:
                label.setText(current_display)
            return

        profile = self._selected_profile()
        occupied_names = self._official_field_occupied_names(exclude_key=key)
        alias_owner = str(profile.field_aliases.get(name, "") or "")
        if name in occupied_names or (alias_owner and alias_owner != key):
            if label is not None:
                label.setText(current_display)
            return

        default_name = self._official_series_label(key)
        profile.field_aliases = {
            alias: target
            for alias, target in dict(profile.field_aliases or {}).items()
            if str(target or "").strip() != key
        }
        if name != default_name:
            profile.field_aliases[name] = key
        if label is not None:
            label.setText(self._official_field_display_name(key))
        self._schedule_summary_refresh(0, scope="fields")
        self._apply_current_profile()

    def _on_official_fixed_value_changed(self, key: str, value: str) -> None:
        label = self._official_field_name_labels.get(key)
        if label is not None:
            label.setText(self._official_field_display_name(key, value))
            self._style_official_field_name(label, value)
        self._on_template_field_input_changed(key, value)
        if self._selected_profile().field_functions:
            self._recalculate_official_field_functions()
            self._sync_existing_official_field_rows(
                self._official_fixed_field_keys,
                self._official_floating_field_keys,
            )

    def _style_official_field_name(
        self, label: OfficialFieldNameEdit, value: object
    ) -> None:
        completed = bool(str(value or "").strip())
        label.setCompleted(completed)

    @staticmethod
    def _style_official_field_row(row: QFrame, *, is_last: bool) -> None:
        # Keep the final row's visual height identical to its siblings.  The
        # section layout owns the inter-group gap; making the last divider
        # transparent visually merges that gap into the row and makes it look
        # taller even though its geometry is unchanged.
        apply_token_row_style(
            row,
            object_name="official_material_field_row",
            is_last=False,
        )

    def _build_official_field_actions(
        self,
        row: QFrame,
        key: str,
        scope: str,
    ) -> QWidget:
        actions = CompactRowActions(row)
        function_button = actions.add_action(
            "function",
            icon_name="clock",
            tooltip="字段函数",
            variant="secondary",
            callback=lambda _checked=False, field_key=key: self._open_official_field_function(
                field_key
            ),
        )
        self._official_function_buttons[key] = function_button
        self._sync_official_function_button(key)
        add_next = actions.add_action(
            "add",
            icon_name="plus",
            tooltip="新增同系列字段",
            variant="outlined-primary",
            callback=lambda _checked=False, source=key, field_scope=scope: (
                self._add_official_series_field(source, field_scope)
            ),
        )
        remove = actions.add_action(
            "remove",
            icon_name="trash-2",
            tooltip="删除字段",
            variant="outlined-danger",
            callback=lambda _checked=False, field_key=key: self._remove_official_field(
                field_key
            ),
        )
        if key in self._timeline_managed_field_keys():
            for button in (function_button, add_next, remove):
                button.setEnabled(False)
                button.setToolTip("由时间计划管理")
        return actions

    def _sync_official_function_button(self, key: str) -> None:
        button = getattr(self, "_official_function_buttons", {}).get(key)
        if button is None:
            return
        spec = dict(
            getattr(self._selected_profile(), "field_functions", {}).get(key, {}) or {}
        )
        description = describe_field_function(spec)
        timeline_owned = key in getattr(
            self,
            "_timeline_output_field_keys",
            lambda: set(),
        )()
        active = bool(description)
        apply_compact_row_action(
            button,
            icon_name="chart-no-axes-gantt" if timeline_owned else "clock",
            tooltip=(
                "来自时间计划；点击查看节点规则"
                if timeline_owned
                else "字段函数"
            ),
            variant="ghost-primary" if active or timeline_owned else "secondary",
        )

    def _sync_official_function_edit_state(
        self,
        key: str,
        edit: OfficialFieldValueEdit,
        scope: str,
    ) -> None:
        spec = dict(
            getattr(self._selected_profile(), "field_functions", {}).get(key, {}) or {}
        )
        description = describe_field_function(spec)
        timeline_owned = key in getattr(
            self,
            "_timeline_output_field_keys",
            lambda: set(),
        )()
        if description or timeline_owned:
            edit.setReadOnly(True)
        elif scope == "floating":
            edit.setReadOnly(True)
        else:
            edit.setReadOnly(False)

    def _open_official_field_function(self, key: str) -> None:
        if key in getattr(self, "_timeline_output_field_keys", lambda: set())():
            getattr(self, "_open_timeline_for_field", lambda _key: None)(key)
            return
        profile = self._selected_profile()
        keys = list(
            dict.fromkeys(
                (*self._official_fixed_field_keys, *self._official_floating_field_keys)
            )
        )
        values = {**profile.fields, **self._template_field_values}
        for field_key, edit in self._official_fixed_field_inputs.items():
            values[field_key] = edit.text().strip()
        action, spec = choose_official_field_function(
            parent=self,
            target_key=key,
            fields=[
                (field_key, self._official_field_display_label(field_key))
                for field_key in keys
            ],
            values=values,
            field_functions=profile.field_functions,
        )
        if action == "cancel":
            return
        if action == "clear":
            profile.field_functions.pop(key, None)
            self._sync_existing_official_field_rows(
                self._official_fixed_field_keys,
                self._official_floating_field_keys,
            )
            self._refresh_field_only_projection()
            Toast.show_success(f"已移除 {_field_label(key)} 的函数")
            return
        if spec is None:
            return
        profile.field_functions[key] = dict(spec)
        resolution = self._recalculate_official_field_functions()
        self._sync_existing_official_field_rows(
            self._official_fixed_field_keys,
            self._official_floating_field_keys,
        )
        self._refresh_field_only_projection()
        error = resolution.errors.get(key, "")
        if error:
            Toast.show_warning(f"函数已插入，但暂时无法获取实时值：{error}")
        else:
            Toast.show_success(
                f"已插入函数：{describe_field_function(spec)}"
            )

    def _recalculate_official_field_functions(self):
        profile = self._selected_profile()
        resolution = resolve_field_functions(
            {**profile.fields, **self._template_field_values},
            profile.field_functions,
        )
        for key in profile.field_functions:
            if key in resolution.errors:
                continue
            value = str(resolution.values.get(key, "") or "")
            profile.fields[key] = value
            self._template_field_values[key] = value
        return resolution

    def _request_official_field(self, scope: str) -> None:
        scope_label = "固定" if scope == "fixed" else "自由"
        profile = self._selected_profile()
        occupied = self._official_field_occupied_names()
        key = next_numbered_name(f"{scope_label}字段", occupied)
        profile.field_scopes[key] = scope
        self._declared_field_keys.add(key)
        if key not in self._manual_field_keys:
            self._manual_field_keys.append(key)
        self._refresh_official_fields_preserving_view(
            anchor_widget=(
                self._add_official_fixed_btn
                if scope == "fixed"
                else self._add_official_floating_btn
            )
        )
        Toast.show_success(f"已新增{scope_label}字段：{_field_label(key)}")

    def _refresh_official_fields_preserving_view(
        self,
        *,
        anchor_key: str = "",
        anchor_widget: QWidget | None = None,
    ) -> None:
        scroll = getattr(self, "_detail_scroll", None)
        detail_page = getattr(self, "_section_contents", {}).get("fields")
        anchor = (
            self._official_field_name_labels.get(anchor_key)
            if anchor_key
            else anchor_widget
        )
        if scroll is None or detail_page is None:
            self._refresh_official_field_editor()
        else:
            with viewport_mutation(
                scroll=scroll,
                content=detail_page,
                anchor=anchor,
                layout_roots=(self._official_fields_panel,),
                geometry_sync=getattr(self, "_detail_geometry", None),
                geometry_detail=detail_page,
                paint_targets=(self._official_fields_panel,),
            ):
                self._refresh_official_field_editor()
        self._schedule_summary_refresh(0, scope="fields")

    def _add_official_series_field(self, source_key: str, scope: str) -> None:
        source_label = self._official_field_display_label(source_key)
        profile = self._selected_profile()
        occupied = self._official_field_occupied_names()
        prefix = numbered_series_prefix(source_label)
        candidate = next_series_name(source_label, occupied)
        items = list(profile.field_scopes.items())
        family_indexes = [
            index
            for index, (key, _value) in enumerate(items)
            if key == source_key
            or is_numbered_series_name(
                self._official_field_display_label(key),
                prefix,
            )
        ]
        insert_at = max(family_indexes, default=len(items) - 1) + 1
        items.insert(insert_at, (candidate, scope))
        profile.field_scopes = dict(items)
        self._declared_field_keys.add(candidate)
        if candidate not in self._manual_field_keys:
            self._manual_field_keys.append(candidate)
        self._refresh_official_fields_preserving_view(anchor_key=source_key)
        Toast.show_success(f"已新增 {_field_label(candidate)}")

    def _remove_official_field(self, key: str) -> None:
        profile = self._selected_profile()
        if key in self._timeline_managed_field_keys():
            Toast.show_warning("该字段由时间计划引用，请先在时间计划中调整")
            return
        scope = str(profile.field_scopes.get(key, "") or "")
        if scope not in {"fixed", "floating"}:
            scope = "fixed" if key in self._official_fixed_field_keys else "floating"
        section_keys = list(
            self._official_fixed_field_keys
            if scope == "fixed"
            else self._official_floating_field_keys
        )
        anchor_key = ""
        if key in section_keys:
            removed_index = section_keys.index(key)
            if removed_index + 1 < len(section_keys):
                anchor_key = section_keys[removed_index + 1]
            elif removed_index > 0:
                anchor_key = section_keys[removed_index - 1]
        anchor_widget = (
            self._official_fixed_title
            if scope == "fixed"
            else self._official_floating_title
        )
        value = str(
            self._template_field_values.get(key, profile.fields.get(key, "")) or ""
        ).strip()
        if value and not confirm(
            "删除字段",
            f"“{_field_label(key)}”已有内容，删除后将同时移除该内容。",
            confirm_text="删除",
            destructive=True,
            parent=self,
        ):
            return
        scope_items = list(profile.field_scopes.items())
        original_index = next(
            (index for index, (field_key, _scope) in enumerate(scope_items) if field_key == key),
            len(scope_items),
        )
        self._last_removed_official_field = {
            "key": key,
            "scope": scope,
            "index": original_index,
            "profile_index": self._current_profile_index,
            "profile_value": profile.fields.get(key),
            "template_value": self._template_field_values.get(key),
            "field_function": dict(profile.field_functions.get(key, {}) or {}),
            "field_aliases": {
                alias: target
                for alias, target in dict(profile.field_aliases or {}).items()
                if str(target or "").strip() == key
            },
            "manual_index": (
                self._manual_field_keys.index(key)
                if key in self._manual_field_keys
                else None
            ),
            "imported": key in self._imported_field_keys,
            "declared": key in self._declared_field_keys,
        }
        discard_material_field(profile, key)
        self._template_field_values.pop(key, None)
        self._template_field_inputs.pop(key, None)
        self._official_fixed_field_keys = [
            item for item in self._official_fixed_field_keys if item != key
        ]
        self._official_floating_field_keys = [
            item for item in self._official_floating_field_keys if item != key
        ]
        self._manual_field_keys = [item for item in self._manual_field_keys if item != key]
        self._declared_field_keys.discard(key)
        self._imported_field_keys.discard(key)
        self._sync_official_remove_undo_buttons(scope)
        self._refresh_official_fields_preserving_view(
            anchor_key=anchor_key,
            anchor_widget=anchor_widget,
        )
        Toast.show_success(f"已删除字段：{_field_label(key)}；可在分区标题处撤销")

    def _sync_official_remove_undo_buttons(self, scope: str = "") -> None:
        for field_scope, name in (
            ("fixed", "_undo_official_fixed_remove_btn"),
            ("floating", "_undo_official_floating_remove_btn"),
        ):
            button = getattr(self, name, None)
            if button is not None:
                button.setVisible(bool(self._last_removed_official_field) and scope == field_scope)

    def _undo_last_official_field_removal(self) -> None:
        snapshot = dict(self._last_removed_official_field or {})
        key = str(snapshot.get("key", "") or "")
        scope = str(snapshot.get("scope", "") or "")
        if not key or scope not in {"fixed", "floating"}:
            return
        if int(snapshot.get("profile_index", -1)) != self._current_profile_index:
            self._last_removed_official_field = None
            self._sync_official_remove_undo_buttons()
            return
        profile = self._selected_profile()
        current_items = [
            (field_key, field_scope)
            for field_key, field_scope in profile.field_scopes.items()
            if field_key != key
        ]
        insert_at = min(max(0, int(snapshot.get("index", 0) or 0)), len(current_items))
        current_items.insert(insert_at, (key, scope))
        profile.field_scopes = dict(current_items)

        profile_value = snapshot.get("profile_value")
        if profile_value is not None:
            profile.fields[key] = str(profile_value)
        template_value = snapshot.get("template_value")
        if template_value is not None:
            self._template_field_values[key] = str(template_value)
        field_function = snapshot.get("field_function")
        if isinstance(field_function, dict) and field_function:
            profile.field_functions[key] = dict(field_function)
        field_aliases = snapshot.get("field_aliases")
        if isinstance(field_aliases, dict):
            occupied = self._official_field_occupied_names(exclude_key=key)
            for alias, target in field_aliases.items():
                restored_alias = str(alias or "").strip()
                if not restored_alias:
                    continue
                if restored_alias in occupied:
                    restored_alias = self._next_official_series_name(
                        restored_alias,
                        occupied,
                    )
                profile.field_aliases[restored_alias] = str(target or key)
                occupied.add(restored_alias)
        manual_index = snapshot.get("manual_index")
        if manual_index is not None and key not in self._manual_field_keys:
            self._manual_field_keys.insert(
                min(max(0, int(manual_index)), len(self._manual_field_keys)),
                key,
            )
        if bool(snapshot.get("imported")):
            self._imported_field_keys.add(key)
        if bool(snapshot.get("declared")):
            self._declared_field_keys.add(key)
        self._last_removed_official_field = None
        self._sync_official_remove_undo_buttons()
        self._refresh_official_fields_preserving_view(
            anchor_widget=(
                self._official_fixed_title
                if scope == "fixed"
                else self._official_floating_title
            )
        )
        Toast.show_success(f"已恢复字段：{_field_label(key)}")

    def _request_add_material_field(self) -> None:
        self._material_field_draft_counter += 1
        key = f"{MATERIAL_FIELD_DRAFT_PREFIX}{self._material_field_draft_counter}"
        self._manual_field_keys.append(key)
        self._refresh_unknown_fields_preserving_view(
            self._document_field_order,
            anchor=getattr(self, "_add_material_field_btn", None),
        )
        edit = self._template_field_key_inputs.get(key)
        if edit is not None:
            edit.setFocus()
        self._schedule_summary_refresh(scope="fields")

    def _commit_material_field_key(self, old_key: str, raw_key: str) -> None:
        if old_key in self._document_field_keys:
            return
        key = self._exact_material_field_key(raw_key)
        code_edit = self._template_field_key_inputs.get(old_key)
        if not key:
            if str(raw_key or "").strip():
                Toast.show_warning("字段代码不能包含不成对的大括号或换行")
            if code_edit is not None:
                defer_qt_method(code_edit, "setFocus")
            return
        occupied = (self._document_field_keys | set(self._manual_field_keys)) - {old_key}
        if key in occupied:
            Toast.show_warning(
                "字段已存在，不能重复写入："
                + material_token(MaterialTokenNamespace.TEXT, key)
            )
            if code_edit is not None:
                code_edit.setText(
                    ""
                    if old_key.startswith(MATERIAL_FIELD_DRAFT_PREFIX)
                    else material_token(MaterialTokenNamespace.TEXT, old_key)
                )
                defer_qt_method(code_edit, "setFocus")
            return
        if key == old_key:
            self._declared_field_keys.add(key)
            if code_edit is not None:
                code_edit.setText(material_token(MaterialTokenNamespace.TEXT, key))
            return
        if old_key in self._timeline_managed_field_keys():
            Toast.show_warning("该字段由时间计划引用，不能在字段列表中改名")
            if code_edit is not None:
                code_edit.setText(
                    material_token(MaterialTokenNamespace.TIME, old_key)
                )
            return
        profile = self._selected_profile()
        profile_owned_keys = (
            set(profile.field_scopes)
            | set(profile.fields)
            | set(profile.declared_field_keys)
            | set(profile.field_sources)
            | set(profile.field_functions)
            | set(profile.field_aliases)
        ) - {old_key}
        if key in profile_owned_keys:
            Toast.show_warning(
                "字段已存在，不能重复写入："
                + material_token(MaterialTokenNamespace.TEXT, key)
            )
            if code_edit is not None:
                code_edit.setText(material_token(MaterialTokenNamespace.TEXT, old_key))
            return
        persisted_old_key = bool(
            old_key in profile.field_scopes
            or old_key in profile.fields
            or old_key in profile.declared_field_keys
            or old_key in profile.field_sources
            or old_key in profile.field_functions
            or any(
                str(target or "").strip() == old_key
                for target in profile.field_aliases.values()
            )
        )
        if persisted_old_key and not rename_material_field(profile, old_key, key):
            Toast.show_warning("字段改名失败，请刷新后重试")
            if code_edit is not None:
                code_edit.setText(material_token(MaterialTokenNamespace.TEXT, old_key))
            return
        anchor = self._surviving_unknown_field_anchor(old_key)
        self._manual_field_keys = [
            key if item == old_key else item for item in self._manual_field_keys
        ]
        self._declared_field_keys.discard(old_key)
        self._declared_field_keys.add(key)
        value_edit = self._template_field_inputs.get(old_key)
        value = (
            value_edit.text().strip()
            if value_edit is not None
            else str(self._template_field_values.get(old_key, "") or "").strip()
        )
        self._template_field_values.pop(old_key, None)
        if value:
            self._template_field_values[key] = value
        if old_key in self._imported_field_keys:
            self._imported_field_keys.discard(old_key)
            self._imported_field_keys.add(key)
        # The field code is the stable list identity.  Renaming it is one
        # targeted remove+insert reconciliation: every unrelated row remains
        # alive, while the renamed row receives fresh callbacks bound to the
        # new key.  Reusing the old callbacks would leave delete/value changes
        # writing to the discarded draft key.
        self._refresh_unknown_fields_preserving_view(
            self._document_field_order,
            anchor=anchor,
            capture_live_values=False,
        )
        target = self._template_field_inputs.get(key)
        if target is not None:
            defer_qt_method(target, "setFocus")
        self._refresh_field_conflict_state()
        self._schedule_summary_refresh(scope="fields")

    @staticmethod
    def _exact_material_field_key(value: str) -> str:
        raw = str(value or "").strip()
        try:
            ref = parse_material_token(raw)
        except (TypeError, ValueError):
            try:
                ref = parse_material_token(
                    material_token(MaterialTokenNamespace.TEXT, raw)
                )
            except (TypeError, ValueError):
                return ""
        if ref.kind is not MaterialTokenKind.FIELD:
            return ""
        return ref.identifier

    def _remove_manual_field(self, key: str) -> None:
        if key in self._document_field_keys:
            return
        if key in self._timeline_managed_field_keys():
            Toast.show_warning("该字段由时间计划引用，请先在时间计划中调整")
            return
        discard_material_field(self._selected_profile(), key)
        anchor = self._surviving_unknown_field_anchor(key)
        self._manual_field_keys = [item for item in self._manual_field_keys if item != key]
        self._template_field_values.pop(key, None)
        self._template_field_inputs.pop(key, None)
        self._declared_field_keys.discard(key)
        self._imported_field_keys.discard(key)
        self._refresh_unknown_fields_preserving_view(
            self._document_field_order,
            anchor=anchor,
        )
        self._refresh_field_conflict_state()
        self._schedule_summary_refresh(scope="fields")

    def _add_unknown_placeholder_field(self, token: str, *, value: str = "") -> None:
        key = _placeholder_key(token)
        if not key:
            return
        profile = self._selected_profile()
        if key not in profile.field_scopes:
            # This is an explicit user repair action, not scan discovery.  A
            # newly accepted document Token is task-specific by default.
            profile.field_scopes[key] = "floating"
        if value:
            self._task_field_values[key] = str(value).strip()
        self._declared_field_keys.add(key)
        if key not in profile.declared_field_keys:
            profile.declared_field_keys.append(key)
        self._refresh_official_fields_preserving_view(
            anchor_widget=getattr(self, "_add_official_floating_btn", None),
        )
        self._refresh_field_only_projection()
        self._select_section("fields")
        row = self._official_field_rows.get(key)
        if row is not None:
            row.setFocus()

    def _on_template_field_input_changed(self, token: str, value: str) -> None:
        key = _placeholder_key(token)
        if not key:
            return
        cleaned = str(value or "").strip()
        self._declared_field_keys.add(key)
        if cleaned:
            self._template_field_values[key] = cleaned
            if key not in self._manual_field_keys:
                self._manual_field_keys.append(key)
        else:
            self._template_field_values.pop(key, None)
        if not self._preserve_import_sources:
            self._imported_field_keys.discard(key)
        self._refresh_field_conflict_state()
        self._update_preview_field_value(key, cleaned)
        self._schedule_summary_refresh(scope="fields")
        target = self._current_execution_target()
        if str(getattr(target, "mode_id", "") or "") == "official":
            timer = getattr(self, "_official_material_context_sync_timer", None)
            if timer is None:
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(self._apply_current_profile)
                self._official_material_context_sync_timer = timer
            timer.start(300)


__all__ = [
    "FieldStatusPresenterMixin",
    "MATERIAL_FIELD_DRAFT_PREFIX",
    "MaterialFieldCodeEdit",
]
