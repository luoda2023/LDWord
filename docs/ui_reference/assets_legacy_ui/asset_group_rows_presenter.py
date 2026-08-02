"""Presenter mixin for role-bound recursive image folders."""

from __future__ import annotations

import copy
from pathlib import Path

from src.config.asset_resolution import resolve_asset_binding, refresh_asset_binding
from src.config.entity import AssetBinding
from src.qt_api import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QSize,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    Qt,
)
from src.shared.ui.keyed_widget_list import KeyedWidgetListController
from src.shared.ui.asset_column_guide import AssetColumnMetrics
from src.shared.ui.compact_row_actions import CompactRowActions
from src.shared.ui.deferred_call import defer_qt_method
from src.shared.ui.layout_sync import refresh_layout_chain_later
from src.shared.ui.material_token_edit import MaterialTokenEdit
from src.shared.ui.material_name_edit import MaterialNameEdit
from src.shared.ui.material_text_views import ElidedPathEdit
from src.shared.ui.path_action_semantics import PathAction, path_action_presentation
from src.shared.ui.path_drop import PathAcceptancePolicy, attach_path_drop
from src.shared.ui.theme import get_theme
from src.shared.ui.text_projection import ElidedTextLabel
from src.shared.ui.toast import Toast
from src.shared.ui.token_row_style import apply_token_row_style
from src.ui.panels.assets.image_helpers import _load_scaled_pixmap
from src.ui.panels.assets.mutation_transaction import (
    capture_material_mutation_snapshot,
    publish_or_rollback_material_mutation,
)


_ASSET_GROUP_PATH_POLICY = PathAcceptancePolicy(
    path_kind="directory",
    dialog_label="图片文件夹",
)


class AssetGroupRowsPresenterMixin:
    """Build, select, rescan, preview, and clear multi-image folder rows."""

    def _sync_asset_group_rows(self) -> None:
        if not hasattr(self, "_asset_groups_layout"):
            return
        specs = tuple(getattr(self, "_asset_group_specs", ()))
        self._asset_groups_container.setVisible(bool(specs))
        self._asset_groups_header.setVisible(True)
        controller = getattr(self, "_asset_groups_controller", None)
        if controller is None:
            controller = KeyedWidgetListController(
                layout=self._asset_groups_layout,
                create_widget=lambda spec: self._build_asset_group_row(
                    spec,
                    parent=self._asset_groups_container,
                ),
                update_widget=lambda widget, spec, index: self._update_asset_group_row(
                    widget,
                    spec,
                    index,
                ),
                dispose_widget=self._dispose_asset_group_row,
                key=self._asset_group_row_key,
            )
            self._asset_groups_controller = controller
        change = controller.reconcile(specs)
        self._asset_groups_count.setText(f"{len(specs)} 项")
        self._refresh_asset_group_rows()
        if change.added:
            apply_row_theme = getattr(self, "_apply_asset_row_theme", None)
            if callable(apply_row_theme):
                apply_row_theme(get_theme())
        guide = getattr(self, "_asset_groups_column_guide", None)
        if guide is not None:
            self._apply_asset_group_column_metrics(guide.metrics())
        refresh_layout_chain_later(self._asset_groups_container)
        sync_rules = getattr(self, "_sync_image_material_rule_rows", None)
        if callable(sync_rules):
            sync_rules()

    def _build_asset_group_row(self, spec, *, parent: QWidget) -> QWidget:
        role = spec.role
        row = QFrame(parent)
        row.setObjectName("asset_group_row")
        row.setProperty("asset_group_role", role)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        row.setMinimumHeight(get_theme().token_row_min_height)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(4, get_theme().token_row_padding_y, 4, get_theme().token_row_padding_y)
        layout.setSpacing(6)

        top = QWidget(row)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(get_theme().token_row_column_gap)

        index_label = QLabel("1", top)
        index_label.setObjectName("asset_row_index")
        index_label.setFixedWidth(34)
        index_label.setAlignment(Qt.AlignCenter)

        thumbnail = QLabel("未选", top)
        thumbnail.setObjectName("asset_group_thumbnail")
        thumbnail.setFixedSize(52, 52)
        thumbnail.setAlignment(Qt.AlignCenter)
        thumbnail.setCursor(Qt.PointingHandCursor)
        thumbnail.setProperty("asset_group_role", role)
        thumbnail.installEventFilter(self)

        token = MaterialTokenEdit(spec.target, top)
        token.setObjectName("asset_group_token")
        token.setProperty("asset_group_role", role)
        token.setMinimumWidth(220)
        token.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        token.editingFinished.connect(
            lambda selected_role=role, widget=token: self._commit_asset_group_token(
                selected_role,
                widget.text(),
            )
        )
        token.copied.connect(lambda _text: Toast.show_success("复制成功"))

        name_edit = MaterialNameEdit(spec.label, top)
        name_edit.setObjectName("asset_group_name")
        name_edit.setProperty("asset_group_role", role)
        name_edit.setPlaceholderText("例如：ISO9001质量管理体系认证证书")
        name_edit.editingFinished.connect(
            lambda selected_role=role, widget=name_edit: self._commit_asset_group_label(
                selected_role,
                widget.text(),
            )
        )
        name_edit.copied.connect(lambda _text: Toast.show_success("复制成功"))

        path_widget = QWidget(top)
        path_layout = QVBoxLayout(path_widget)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(2)
        path_label = ElidedPathEdit(parent=path_widget)
        path_label.setObjectName("asset_group_path")
        path_label.setPlaceholderText("尚未选择文件夹")
        path_label.setClearButtonEnabled(False)
        status = ElidedTextLabel("尚未选择文件夹", path_widget)
        status.setObjectName("asset_group_status")
        status.setVisible(False)
        status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        path_layout.addWidget(path_label)
        path_layout.addWidget(status)

        actions = CompactRowActions(top)
        actions.setObjectName("asset_group_actions")
        clear = actions.add_action(
            "clear",
            icon_name="x",
            tooltip=f"清除{spec.label}文件夹",
            variant="ghost-danger",
            callback=lambda *_args, selected_role=role: self._clear_asset_group_binding(selected_role),
        )
        choose_action = path_action_presentation(PathAction.CHOOSE_DIRECTORY)
        choose = actions.add_action(
            "choose",
            icon_name=choose_action.icon_name,
            tooltip=f"选择{spec.label}文件夹",
            callback=lambda *_args, selected_role=role: self._select_asset_group_directory(selected_role),
        )
        choose.setProperty("pathAction", PathAction.CHOOSE_DIRECTORY.value)
        refresh = actions.add_action(
            "refresh",
            icon_name="refresh-ccw",
            tooltip=f"重新扫描{spec.label}",
            callback=lambda *_args, selected_role=role: self._refresh_asset_group_binding(selected_role),
        )
        open_action = path_action_presentation(PathAction.REVEAL_IN_FOLDER)
        open_button = actions.add_action(
            "open",
            icon_name=open_action.icon_name,
            tooltip=f"打开{spec.label}文件夹",
            callback=lambda *_args, selected_role=role: self._open_asset_group_directory(selected_role),
        )
        open_button.setProperty("pathAction", PathAction.REVEAL_IN_FOLDER.value)
        add = actions.add_action(
            "add",
            icon_name="plus",
            tooltip=f"新增一项{spec.label}",
            variant="outlined-primary",
            callback=lambda *_args, selected_role=role: defer_qt_method(
                self,
                "_add_asset_group_series",
                selected_role,
            ),
        )
        remove = actions.add_action(
            "remove",
            icon_name="trash-2",
            tooltip=f"删除{spec.target}",
            variant="outlined-danger",
            callback=lambda *_args, selected_role=role: defer_qt_method(
                self,
                "_remove_asset_group",
                selected_role,
            ),
        )

        actions_cell = QWidget(top)
        actions_cell_layout = QHBoxLayout(actions_cell)
        actions_cell_layout.setContentsMargins(0, 0, 0, 0)
        actions_cell_layout.setSpacing(0)
        actions_cell_layout.addStretch(1)
        actions_cell_layout.addWidget(actions)

        top_layout.addWidget(index_label, 0, Qt.AlignVCenter)
        top_layout.addWidget(thumbnail, 0, Qt.AlignTop)
        top_layout.addWidget(token, 0, Qt.AlignVCenter)
        top_layout.addWidget(name_edit, 0, Qt.AlignVCenter)
        top_layout.addWidget(path_widget, 1, Qt.AlignVCenter)
        top_layout.addWidget(actions_cell, 0)
        layout.addWidget(top)

        table = QTableWidget(row)
        table.setObjectName("asset_group_items_table")
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(("序号", "包内名称", "原相对路径", "状态"))
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setMinimumHeight(0)
        table.setMaximumHeight(220)
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        table.itemSelectionChanged.connect(
            lambda selected_role=role: self._preview_selected_asset_group_item(selected_role)
        )
        table.setVisible(False)
        layout.addWidget(table)

        self._asset_group_rows[role] = row
        if not hasattr(self, "_asset_group_index_labels"):
            self._asset_group_index_labels = {}
        if not hasattr(self, "_asset_group_thumbnail_labels"):
            self._asset_group_thumbnail_labels = {}
        if not hasattr(self, "_asset_group_token_edits"):
            self._asset_group_token_edits = {}
        if not hasattr(self, "_asset_group_name_edits"):
            self._asset_group_name_edits = {}
        if not hasattr(self, "_asset_group_path_widgets"):
            self._asset_group_path_widgets = {}
        if not hasattr(self, "_asset_group_action_cells"):
            self._asset_group_action_cells = {}
        if not hasattr(self, "_asset_group_column_layouts"):
            self._asset_group_column_layouts = {}
        if not hasattr(self, "_asset_group_add_buttons"):
            self._asset_group_add_buttons = {}
        if not hasattr(self, "_asset_group_remove_buttons"):
            self._asset_group_remove_buttons = {}
        self._asset_group_index_labels[role] = index_label
        self._asset_group_thumbnail_labels[role] = thumbnail
        self._asset_group_token_edits[role] = token
        self._asset_group_name_edits[role] = name_edit
        self._asset_group_path_labels[role] = path_label
        self._asset_group_path_widgets[role] = path_widget
        self._asset_group_action_cells[role] = actions_cell
        self._asset_group_column_layouts[role] = top_layout
        self._asset_group_status_labels[role] = status
        self._asset_group_tables[role] = table
        self._asset_group_choose_buttons[role] = choose
        self._asset_group_refresh_buttons[role] = refresh
        self._asset_group_open_buttons[role] = open_button
        self._asset_group_clear_buttons[role] = clear
        self._asset_group_add_buttons[role] = add
        self._asset_group_remove_buttons[role] = remove
        if not hasattr(self, "_asset_group_drop_controllers"):
            self._asset_group_drop_controllers = {}
        drop_controller = attach_path_drop(
            parent=row,
            surface=row,
            policy=_ASSET_GROUP_PATH_POLICY,
            on_paths=lambda paths, selected_role=role: self._apply_asset_group_directory(
                selected_role,
                paths[0],
            ),
        )
        self._asset_group_drop_controllers[role] = drop_controller
        return row

    def _update_asset_group_row(self, row: QWidget, spec, index: int) -> None:
        row.setVisible(True)
        role = spec.role
        index_label = getattr(self, "_asset_group_index_labels", {}).get(role)
        if index_label is not None:
            index_label.setText(str(index + 1))
        token = self._asset_group_token_edits.get(role)
        if token is not None and not token.hasFocus() and token.text() != spec.target:
            blocked = token.blockSignals(True)
            token.setText(spec.target)
            token.blockSignals(blocked)
        name_edit = self._asset_group_name_edits.get(role)
        if name_edit is not None and not name_edit.hasFocus() and name_edit.text() != spec.label:
            blocked = name_edit.blockSignals(True)
            name_edit.setText(spec.label)
            name_edit.blockSignals(blocked)
        tooltip_specs = (
            (self._asset_group_clear_buttons, f"清除{spec.label}文件夹"),
            (self._asset_group_choose_buttons, f"选择{spec.label}文件夹"),
            (self._asset_group_refresh_buttons, f"重新扫描{spec.label}"),
            (self._asset_group_open_buttons, f"打开{spec.label}文件夹"),
            (self._asset_group_add_buttons, f"新增一项{spec.label}"),
        )
        for buttons, tooltip in tooltip_specs:
            button = buttons.get(role)
            if button is not None:
                button.setToolTip(tooltip)
        remove = self._asset_group_remove_buttons.get(role)
        if remove is not None:
            remove.setToolTip(f"删除{spec.target}")
        apply_token_row_style(
            row,
            object_name="asset_group_row",
            is_last=index == len(self._asset_group_specs) - 1,
        )
        self._refresh_asset_group_row(role)

    def _apply_asset_group_column_metrics(self, metrics: AssetColumnMetrics) -> None:
        if not isinstance(metrics, AssetColumnMetrics):
            return
        for spec in tuple(getattr(self, "_asset_group_specs", ())):
            role = spec.role
            layout = self._asset_group_column_layouts.get(role)
            index = self._asset_group_index_labels.get(role)
            token = self._asset_group_token_edits.get(role)
            name = self._asset_group_name_edits.get(role)
            path_widget = self._asset_group_path_widgets.get(role)
            actions_cell = self._asset_group_action_cells.get(role)
            if any(
                item is None
                for item in (layout, index, token, name, path_widget, actions_cell)
            ):
                continue
            layout.setSpacing(metrics.column_gap)
            index.setFixedWidth(metrics.index_width)
            token.setMinimumWidth(0)
            token.setFixedWidth(metrics.token_width)
            name.setMinimumWidth(0)
            name.setFixedWidth(metrics.name_width)
            path_widget.setVisible(metrics.source_visible)
            actions_cell.setFixedWidth(metrics.actions_width)

    def _refresh_asset_group_rows(self) -> None:
        for spec in tuple(getattr(self, "_asset_group_specs", ())):
            self._refresh_asset_group_row(spec.role)

    def _refresh_asset_group_row(self, role: str) -> None:
        binding = self._asset_bindings.get(role)
        path_label = self._asset_group_path_labels.get(role)
        status_label = self._asset_group_status_labels.get(role)
        thumbnail = getattr(self, "_asset_group_thumbnail_labels", {}).get(role)
        table = self._asset_group_tables.get(role)
        has_binding = binding is not None and bool(str(binding.source_path or "").strip())
        for buttons in (
            self._asset_group_refresh_buttons,
            self._asset_group_open_buttons,
        ):
            button = buttons.get(role)
            if button is not None:
                button.setEnabled(has_binding)
                button.setVisible(has_binding)
        clear_button = self._asset_group_clear_buttons.get(role)
        if clear_button is not None:
            clear_button.setEnabled(has_binding)
            clear_button.setVisible(True)
        if not has_binding:
            row = self._asset_group_rows.get(role)
            if row is not None:
                row.setMaximumHeight(96)
            if path_label is not None:
                path_label.clear()
                path_label.setAccessibleName("")
                path_label.setVisible(True)
            if thumbnail is not None:
                thumbnail.clear()
                thumbnail.setText("未选")
            if status_label is not None:
                status_label.clear()
                status_label.setVisible(False)
            if table is not None:
                table.setRowCount(0)
                table.setVisible(False)
            return

        row = self._asset_group_rows.get(role)
        if row is not None:
            row.setMaximumHeight(360)
        resolution = resolve_asset_binding(binding)
        if path_label is not None:
            path_label.setText(str(binding.source_path))
            path_label.setAccessibleName(str(binding.source_path))
        errors = [item for item in resolution.diagnostics if item.severity == "error"]
        warnings = [item for item in resolution.diagnostics if item.severity != "error"]
        if status_label is not None:
            diagnostics: list[str] = []
            if errors:
                diagnostics.append(f"{len(errors)} 个错误")
            elif warnings:
                diagnostics.append(f"{len(warnings)} 个提醒")
            if self._asset_role_has_source_conflict(role):
                diagnostics.append("图片来源冲突")
            status_label.setText(" · ".join(diagnostics))
            status_label.setVisible(bool(diagnostics))
        first_path = resolution.items[0].path if resolution.items else ""
        if thumbnail is not None:
            pixmap = _load_scaled_pixmap(first_path, QSize(52, 52))
            if pixmap is None:
                thumbnail.clear()
                thumbnail.setText("空" if not resolution.items else f"{len(resolution.items)} 张")
            else:
                thumbnail.setText("")
                thumbnail.setPixmap(pixmap)
                thumbnail.setToolTip(f"预览首图，共 {len(resolution.items)} 张")
        if table is None:
            return
        table.setRowCount(len(resolution.items))
        for row_index, item in enumerate(resolution.items):
            values = (
                str(item.sequence or row_index + 1),
                item.normalized_name or Path(item.path).name,
                item.original_relative_path or Path(item.path).name,
                "可用" if Path(item.path).is_file() else "缺失",
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(32, item.path)
                table.setItem(row_index, column, cell)
            table.setRowHeight(row_index, 34)
        if resolution.items:
            header_height = max(28, table.horizontalHeader().sizeHint().height())
            content_height = sum(table.rowHeight(index) for index in range(table.rowCount()))
            resolved_height = min(220, header_height + content_height + 6)
            table.setMinimumHeight(resolved_height)
            table.setMaximumHeight(resolved_height)
        table.setVisible(bool(resolution.items))

    def _select_asset_group_directory(self, role: str) -> None:
        spec = self._asset_group_spec(role)
        directory = QFileDialog.getExistingDirectory(
            self,
            f"选择{getattr(spec, 'label', role)}文件夹",
            str(getattr(self._asset_bindings.get(role), "source_path", "") or ""),
        )
        if not directory:
            return
        self._apply_asset_group_directory(role, directory)

    def _apply_asset_group_directory(self, role: str, directory: str) -> bool:
        source = Path(str(directory or "").strip())
        if not source.is_dir():
            Toast.show_warning("所选路径不是可用文件夹，请重新选择。")
            return False
        spec = self._asset_group_spec(role)
        binding = AssetBinding(
            role=role,
            cardinality="multiple",
            source_kind="directory",
            source_path=str(source),
            recursive=bool(getattr(spec, "recursive", True)),
            order_policy=str(getattr(spec, "order_policy", "natural_path") or "natural_path"),
            naming_template=str(
                getattr(spec, "naming_template", "{role}_{sequence:03d}")
                or "{role}_{sequence:03d}"
            ),
            min_items=int(getattr(spec, "min_items", 0) or 0),
            max_items=getattr(spec, "max_items", None),
        )
        snapshot = self._capture_asset_group_mutation_snapshot()
        if snapshot is None:
            return False
        refreshed, _resolution = refresh_asset_binding(binding)
        self._asset_bindings[role] = refreshed
        if not publish_or_rollback_material_mutation(
            snapshot,
            publish=self._sync_material_batch_selection,
            restore_selection=self._restore_asset_group_mutation_selection,
            restore_profile=self._restore_asset_group_mutation_profile,
            restore_local=self._restore_asset_group_mutation_local,
            refresh=lambda: self._refresh_asset_group_mutation_ui(role),
        ):
            return False
        self._refresh_asset_group_mutation_ui(role)
        return True

    def _refresh_asset_group_binding(self, role: str) -> bool:
        binding = self._asset_bindings.get(role)
        if binding is None:
            return False
        snapshot = self._capture_asset_group_mutation_snapshot()
        if snapshot is None:
            return False
        refreshed, _resolution = refresh_asset_binding(binding)
        self._asset_bindings[role] = refreshed
        if not publish_or_rollback_material_mutation(
            snapshot,
            publish=self._sync_material_batch_selection,
            restore_selection=self._restore_asset_group_mutation_selection,
            restore_profile=self._restore_asset_group_mutation_profile,
            restore_local=self._restore_asset_group_mutation_local,
            refresh=lambda: self._refresh_asset_group_mutation_ui(role),
        ):
            return False
        self._refresh_asset_group_mutation_ui(role)
        return True

    def _clear_asset_group_binding(self, role: str) -> bool:
        snapshot = self._capture_asset_group_mutation_snapshot()
        if snapshot is None:
            return False
        self._asset_bindings.pop(role, None)
        if not publish_or_rollback_material_mutation(
            snapshot,
            publish=self._sync_material_batch_selection,
            restore_selection=self._restore_asset_group_mutation_selection,
            restore_profile=self._restore_asset_group_mutation_profile,
            restore_local=self._restore_asset_group_mutation_local,
            refresh=lambda: self._refresh_asset_group_mutation_ui(role),
        ):
            return False
        self._refresh_asset_group_mutation_ui(role)
        return True

    def _capture_asset_group_mutation_snapshot(self):
        if not self._persist_current_profile_editor():
            return None
        return capture_material_mutation_snapshot(
            local_state={"asset_bindings": self._asset_bindings},
            profile_state=self._selected_profile(),
            profile_index=self._current_profile_index,
            batch_selection=self.bridge.current_material_batch_selection(),
        )

    def _restore_asset_group_mutation_selection(self, selection) -> None:
        self.bridge.set_current_material_batch_selection(selection)

    def _restore_asset_group_mutation_profile(self, index: int, profile) -> None:
        self._profiles[index] = profile
        self._update_profile_item(index)

    def _restore_asset_group_mutation_local(self, state) -> None:
        self._asset_bindings = state["asset_bindings"]

    def _refresh_asset_group_mutation_ui(self, role: str) -> None:
        self._refresh_asset_group_row(role)
        self._refresh_summary()

    def _open_asset_group_directory(self, role: str) -> None:
        binding = self._asset_bindings.get(role)
        if binding is not None and binding.source_path:
            self._open_file_path(binding.source_path)

    def _preview_selected_asset_group_item(self, role: str) -> None:
        table = self._asset_group_tables.get(role)
        if table is None or table.currentRow() < 0:
            return
        item = table.item(table.currentRow(), 0)
        path = str(item.data(32) or "") if item is not None else ""
        if path:
            self._set_image_preview(path, role=role)

    def _preview_asset_group_first_item(self, role: str) -> None:
        binding = self._asset_bindings.get(role)
        if binding is None:
            return
        resolution = resolve_asset_binding(binding)
        if resolution.items:
            self._set_image_preview(resolution.items[0].path, role=role)

    def _asset_group_spec(self, role: str):
        for spec in tuple(getattr(self, "_asset_group_specs", ())):
            if spec.role == role:
                return spec
        return None

    @staticmethod
    def _asset_group_row_key(spec) -> str:
        """Use the durable material role; the updater owns mutable display data."""

        return spec.role

    def _dispose_asset_group_row(self, widget) -> None:
        role = str(widget.property("asset_group_role") or "")
        if self._asset_group_rows.get(role) is widget:
            self._asset_group_rows.pop(role, None)
            getattr(self, "_asset_group_index_labels", {}).pop(role, None)
            getattr(self, "_asset_group_thumbnail_labels", {}).pop(role, None)
            self._asset_group_token_edits.pop(role, None)
            self._asset_group_name_edits.pop(role, None)
            self._asset_group_path_labels.pop(role, None)
            self._asset_group_path_widgets.pop(role, None)
            self._asset_group_action_cells.pop(role, None)
            self._asset_group_column_layouts.pop(role, None)
            self._asset_group_status_labels.pop(role, None)
            self._asset_group_tables.pop(role, None)
            self._asset_group_choose_buttons.pop(role, None)
            self._asset_group_refresh_buttons.pop(role, None)
            self._asset_group_open_buttons.pop(role, None)
            self._asset_group_clear_buttons.pop(role, None)
            self._asset_group_add_buttons.pop(role, None)
            self._asset_group_remove_buttons.pop(role, None)
            getattr(self, "_asset_group_drop_controllers", {}).pop(role, None)
        widget.setParent(None)
        widget.deleteLater()

    def _copy_asset_bindings(self) -> dict[str, AssetBinding]:
        return {
            role: copy.deepcopy(binding)
            for role, binding in dict(getattr(self, "_asset_bindings", {}) or {}).items()
        }


__all__ = ["AssetGroupRowsPresenterMixin"]
