"""Presenter mixin for asset slot and attachment row construction."""

from __future__ import annotations

from src.qt_api import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
)
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.asset_column_guide import AssetColumnMetrics
from src.shared.ui.compact_row_actions import CompactRowActions
from src.shared.ui.deferred_call import defer_qt_method
from src.shared.ui.icon_button import apply_icon_button_style
from src.shared.ui.theme import get_theme
from src.shared.ui.material_token_edit import MaterialTokenEdit
from src.shared.ui.material_name_edit import MaterialNameEdit
from src.shared.ui.material_text_views import ElidedPathEdit, ElidedValueEdit
from src.shared.ui.path_action_semantics import PathAction, path_action_presentation
from src.shared.ui.path_drop import attach_path_drop
from src.shared.ui.toast import Toast
from src.shared.ui.text_projection import ElidedTextLabel, TextElideMode
from src.shared.ui.token_row_style import apply_token_row_style
from src.shared.engine.material_token_contract import (
    MaterialTokenNamespace,
)
from src.shared.ui.icons.catalog import get_icon
from src.ui.panels.assets.roles import (
    _asset_slot_supports_alt_text,
    _attachment_path_policy,
)
from src.ui.panels.assets.image_helpers import _image_path_policy
from src.ui.panels.assets.attachment_preparation_summary import (
    AttachmentPreparationSummary,
)


class AssetRowsPresenterMixin:
    """Build retained local asset and attachment rows."""

    def _build_asset_slot_row(self, role: str, label: str, target: str, *, parent: QWidget) -> QWidget:
        row = QFrame(parent)
        row.setObjectName("asset_slot_row")
        row.setProperty("asset_role", role)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        row.setMinimumHeight(get_theme().token_row_min_height)
        row.setMaximumHeight(108)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(4, get_theme().token_row_padding_y, 4, get_theme().token_row_padding_y)
        layout.setSpacing(get_theme().compact_action_gap)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(get_theme().token_row_column_gap)

        index_label = QLabel("1", row)
        index_label.setObjectName("asset_row_index")
        index_label.setFixedWidth(34)
        index_label.setAlignment(Qt.AlignCenter)

        thumbnail = QLabel("未选", row)
        thumbnail.setObjectName("asset_slot_thumbnail")
        thumbnail.setFixedSize(52, 52)
        thumbnail.setAlignment(Qt.AlignCenter)
        thumbnail.setCursor(Qt.PointingHandCursor)

        target_edit = MaterialTokenEdit(target, row)
        target_edit.setObjectName("asset_slot_target")
        target_edit.setProperty("asset_role", role)
        target_edit.setMinimumWidth(220)
        target_edit.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        target_edit.editingFinished.connect(
            lambda slot_role=role, widget=target_edit: self._commit_asset_slot_token(
                slot_role,
                widget.text(),
            )
        )
        target_edit.copied.connect(lambda _text: Toast.show_success("复制成功"))

        name_edit = MaterialNameEdit(label, row)
        name_edit.setObjectName("asset_slot_name")
        name_edit.setProperty("asset_role", role)
        name_edit.setPlaceholderText("例如：ISO9001质量管理体系认证证书")
        name_edit.editingFinished.connect(
            lambda slot_role=role, widget=name_edit: self._commit_asset_slot_label(
                slot_role,
                widget.text(),
            )
        )
        name_edit.copied.connect(lambda _text: Toast.show_success("复制成功"))

        path_widget = QWidget(row)
        path_layout = QVBoxLayout(path_widget)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(2)
        path_edit = ElidedPathEdit(parent=path_widget)
        path_edit.setObjectName("asset_slot_path")
        path_edit.setPlaceholderText("尚未选择图片")
        path_edit.setClearButtonEnabled(False)
        status = ElidedTextLabel("未选择", path_widget)
        status.setObjectName("asset_slot_status")
        status.setVisible(False)
        path_layout.addWidget(path_edit)
        path_layout.addWidget(status)
        status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        actions_widget = CompactRowActions(row)
        actions_widget.setObjectName("asset_slot_actions")
        clear_btn = actions_widget.add_action(
            "clear",
            icon_name="x",
            tooltip="清除已选图片",
            variant="ghost-danger",
            callback=lambda *_args, slot_role=role: self._clear_asset_file(slot_role),
        )
        choose_action = path_action_presentation(PathAction.CHOOSE_IMAGE)
        choose_btn = actions_widget.add_action(
            "choose",
            icon_name=choose_action.icon_name,
            tooltip=f"为{label}选择图片",
            variant="secondary",
            callback=lambda *_args, slot_role=role: self._select_asset_file(slot_role),
        )
        choose_btn.setProperty("pathAction", PathAction.CHOOSE_IMAGE.value)
        reveal_action = path_action_presentation(PathAction.REVEAL_IN_FOLDER)
        open_btn = actions_widget.add_action(
            "reveal",
            icon_name=reveal_action.icon_name,
            tooltip=f"打开{label}所在文件夹",
            variant="secondary",
            callback=lambda *_args, slot_role=role: self._open_asset_slot_path(
                slot_role
            ),
        )
        open_btn.setProperty("pathAction", PathAction.REVEAL_IN_FOLDER.value)
        open_btn.setEnabled(False)
        add_btn = actions_widget.add_action(
            "add",
            icon_name="plus",
            tooltip=f"新增一项{label}",
            variant="outlined-primary",
            callback=lambda *_args, slot_role=role: defer_qt_method(
                self,
                "_add_asset_slot_series",
                slot_role,
            ),
        )
        remove_btn = actions_widget.add_action(
            "remove",
            icon_name="trash-2",
            tooltip=f"删除{target}",
            variant="outlined-danger",
            callback=lambda *_args, slot_role=role: defer_qt_method(
                self,
                "_remove_asset_slot",
                slot_role,
            ),
        )

        actions_cell = QWidget(row)
        actions_cell_layout = QHBoxLayout(actions_cell)
        actions_cell_layout.setContentsMargins(0, 0, 0, 0)
        actions_cell_layout.setSpacing(0)
        actions_cell_layout.addStretch(1)
        actions_cell_layout.addWidget(actions_widget)

        alt_text_input = None
        if _asset_slot_supports_alt_text(role):
            alt_text_input = ElidedValueEdit(parent=row)
            alt_text_input.setPlaceholderText("图片说明")
            alt_text_input.textChanged.connect(
                lambda *_args: self._schedule_summary_refresh()
            )

        top_layout.addWidget(index_label, 0, Qt.AlignVCenter)
        top_layout.addWidget(thumbnail, 0, Qt.AlignTop)
        top_layout.addWidget(target_edit, 0, Qt.AlignVCenter)
        top_layout.addWidget(name_edit, 0, Qt.AlignVCenter)
        top_layout.addWidget(path_widget, 1, Qt.AlignVCenter)
        top_layout.addWidget(actions_cell, 0, Qt.AlignVCenter)
        layout.addLayout(top_layout)
        if alt_text_input is not None:
            layout.addWidget(alt_text_input)

        self._asset_slot_rows[role] = row
        if not hasattr(self, "_asset_slot_index_labels"):
            self._asset_slot_index_labels = {}
        if not hasattr(self, "_asset_slot_path_edits"):
            self._asset_slot_path_edits = {}
        if not hasattr(self, "_asset_slot_target_edits"):
            self._asset_slot_target_edits = {}
        if not hasattr(self, "_asset_slot_name_edits"):
            self._asset_slot_name_edits = {}
        if not hasattr(self, "_asset_slot_path_widgets"):
            self._asset_slot_path_widgets = {}
        if not hasattr(self, "_asset_slot_action_cells"):
            self._asset_slot_action_cells = {}
        if not hasattr(self, "_asset_slot_column_layouts"):
            self._asset_slot_column_layouts = {}
        if not hasattr(self, "_asset_slot_add_buttons"):
            self._asset_slot_add_buttons = {}
        if not hasattr(self, "_asset_slot_remove_buttons"):
            self._asset_slot_remove_buttons = {}
        if not hasattr(self, "_asset_slot_action_strips"):
            self._asset_slot_action_strips = {}
        self._asset_slot_index_labels[role] = index_label
        self._asset_slot_target_edits[role] = target_edit
        self._asset_slot_name_edits[role] = name_edit
        self._asset_slot_path_edits[role] = path_edit
        self._asset_slot_path_widgets[role] = path_widget
        self._asset_slot_action_cells[role] = actions_cell
        self._asset_slot_column_layouts[role] = top_layout
        self._asset_slot_choose_buttons[role] = choose_btn
        self._asset_slot_open_buttons[role] = open_btn
        self._asset_slot_thumbnail_labels[role] = thumbnail
        self._asset_slot_status_labels[role] = status
        if alt_text_input is not None:
            self._asset_slot_alt_text_inputs[role] = alt_text_input
        self._asset_slot_clear_buttons[role] = clear_btn
        self._asset_slot_add_buttons[role] = add_btn
        self._asset_slot_remove_buttons[role] = remove_btn
        self._asset_slot_action_strips[role] = actions_widget
        if not hasattr(self, "_asset_slot_drop_controllers"):
            self._asset_slot_drop_controllers = {}
        drop_controller = attach_path_drop(
            parent=row,
            surface=row,
            policy=_image_path_policy(),
            on_paths=lambda paths, slot_role=role: self._apply_asset_slot_path(
                slot_role,
                paths[0],
            ),
        )
        self._asset_slot_drop_controllers[role] = drop_controller

        thumbnail.setProperty("asset_role", role)
        thumbnail.installEventFilter(self)
        return row

    def _update_asset_slot_row(self, row: QWidget, spec, index: int) -> None:
        row.setVisible(True)
        index_label = getattr(self, "_asset_slot_index_labels", {}).get(spec.role)
        if index_label is not None:
            index_label.setText(str(index + 1))
        target_edit = getattr(self, "_asset_slot_target_edits", {}).get(spec.role)
        if target_edit is not None and not target_edit.hasFocus() and target_edit.text() != spec.target:
            blocked = target_edit.blockSignals(True)
            target_edit.setText(spec.target)
            target_edit.blockSignals(blocked)
        name_edit = getattr(self, "_asset_slot_name_edits", {}).get(spec.role)
        if name_edit is not None and not name_edit.hasFocus() and name_edit.text() != spec.label:
            blocked = name_edit.blockSignals(True)
            name_edit.setText(spec.label)
            name_edit.blockSignals(blocked)
        choose_btn = self._asset_slot_choose_buttons.get(spec.role)
        if choose_btn is not None:
            choose_btn.setToolTip(f"为{spec.label}选择图片")
        open_btn = self._asset_slot_open_buttons.get(spec.role)
        if open_btn is not None:
            open_btn.setToolTip(f"打开{spec.label}所在文件夹")
        add_btn = getattr(self, "_asset_slot_add_buttons", {}).get(spec.role)
        if add_btn is not None:
            add_btn.setToolTip(f"新增一项{spec.label}")
        remove_btn = getattr(self, "_asset_slot_remove_buttons", {}).get(spec.role)
        if remove_btn is not None:
            remove_btn.setToolTip(f"删除{spec.target}")
        apply_token_row_style(
            row,
            object_name="asset_slot_row",
            is_last=index == len(self._asset_slot_specs) - 1,
        )

    def _apply_asset_slot_column_metrics(self, metrics: AssetColumnMetrics) -> None:
        if not isinstance(metrics, AssetColumnMetrics):
            return
        for spec in tuple(getattr(self, "_asset_slot_specs", ())):
            role = spec.role
            layout = getattr(self, "_asset_slot_column_layouts", {}).get(role)
            index = getattr(self, "_asset_slot_index_labels", {}).get(role)
            token = getattr(self, "_asset_slot_target_edits", {}).get(role)
            name = getattr(self, "_asset_slot_name_edits", {}).get(role)
            path_widget = getattr(self, "_asset_slot_path_widgets", {}).get(role)
            actions_cell = getattr(self, "_asset_slot_action_cells", {}).get(role)
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

    def _asset_role_has_source_conflict(self, role: str) -> bool:
        normalized = str(role or "").strip()
        return any(
            str(getattr(item, "code", "") or "") == "asset_source_conflict"
            and str(getattr(item, "role", "") or "").strip() == normalized
            for item in tuple(getattr(self, "_asset_resolution_diagnostics", ()) or ())
        )

    def _build_attachment_role_row(self, spec, *, parent: QWidget) -> QWidget:
        self._ensure_attachment_row_registries()
        row = QFrame(parent)
        row.setObjectName("attachment_role_row")
        row.setProperty("attachment_role", spec.role)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        row.setMinimumHeight(get_theme().token_row_min_height)
        chooses_directory = spec.source_kind == "directory_package"
        layout = QVBoxLayout(row)
        layout.setContentsMargins(
            4,
            get_theme().token_row_padding_y,
            4,
            get_theme().token_row_padding_y,
        )
        layout.setSpacing(get_theme().compact_action_gap)

        top = QWidget(row)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(get_theme().token_row_column_gap)

        index_label = QLabel("1", top)
        index_label.setObjectName("asset_row_index")
        index_label.setFixedWidth(34)
        index_label.setAlignment(Qt.AlignCenter)

        preview = QLabel("未选", top)
        preview.setObjectName("attachment_role_preview")
        preview.setFixedSize(52, 52)
        preview.setAlignment(Qt.AlignCenter)

        token_edit = MaterialTokenEdit(
            spec.anchor_token,
            top,
            editable=spec.deletable,
            namespace=MaterialTokenNamespace.ATTACHMENT,
        )
        token_edit.setObjectName("attachment_role_token")
        if spec.deletable:
            token_edit.editingFinished.connect(
                lambda role=spec.role, widget=token_edit: self._commit_attachment_role_token(
                    role,
                    widget.text(),
                )
            )
        token_edit.copied.connect(lambda _text: Toast.show_success("复制成功"))

        name_edit = MaterialNameEdit(self._attachment_role_display_name(spec), top)
        name_edit.setObjectName("attachment_role_name")
        name_edit.setPlaceholderText("附件名称")
        name_edit.editingFinished.connect(
            lambda role=spec.role, widget=name_edit: self._commit_attachment_role_label(
                role,
                widget.text(),
            )
        )
        name_edit.copied.connect(lambda _text: Toast.show_success("复制成功"))

        source_widget = QWidget(top)
        source_layout = QVBoxLayout(source_widget)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.setSpacing(2)
        path_edit = ElidedPathEdit(parent=source_widget)
        path_edit.setObjectName("attachment_role_path")
        path_edit.setPlaceholderText("尚未选择附件")
        status = ElidedTextLabel("", source_widget, mode=TextElideMode.MIDDLE)
        status.setObjectName("attachment_role_status")
        status.setVisible(False)
        source_layout.addWidget(path_edit)
        source_layout.addWidget(status)

        actions = CompactRowActions(top)
        actions.setObjectName("attachment_role_actions")
        clear_btn = actions.add_action(
            "clear",
            icon_name="x",
            tooltip=f"清除{spec.label}",
            variant="ghost-danger",
            callback=lambda *_args, role=spec.role: self._clear_attachment_file(role),
        )
        choose_action = path_action_presentation(
            PathAction.CHOOSE_DIRECTORY
            if chooses_directory
            else PathAction.CHOOSE_FILE
        )
        choose_btn = actions.add_action(
            "choose",
            icon_name=choose_action.icon_name,
            tooltip=f"选择{spec.label}{'文件夹' if chooses_directory else '文件'}",
            callback=lambda *_args, role=spec.role: self._select_attachment_file(role),
        )
        choose_btn.setProperty(
            "pathAction",
            (
                PathAction.CHOOSE_DIRECTORY.value
                if chooses_directory
                else PathAction.CHOOSE_FILE.value
            ),
        )
        refresh_btn = None
        if chooses_directory:
            refresh_btn = actions.add_action(
                "refresh",
                icon_name="refresh-ccw",
                tooltip=f"重新扫描{spec.label}",
                callback=lambda *_args, role=spec.role: self._refresh_attachment_folder(
                    role
                ),
            )
        reveal_action = path_action_presentation(PathAction.REVEAL_IN_FOLDER)
        open_btn = actions.add_action(
            "reveal",
            icon_name=reveal_action.icon_name,
            tooltip=f"打开{spec.label}所在文件夹",
            callback=lambda *_args, role=spec.role: self._open_attachment_path(role),
        )
        add_btn = actions.add_action(
            "add",
            icon_name="plus",
            tooltip=f"新增一项{spec.label}",
            variant="outlined-primary",
            callback=lambda *_args, role=spec.role: defer_qt_method(
                self,
                "_add_attachment_role_series",
                role,
            ),
        )
        remove_btn = actions.add_action(
            "remove",
            icon_name="trash-2",
            tooltip=f"删除{spec.label}",
            variant="outlined-danger",
            callback=lambda *_args, role=spec.role: self._remove_attachment_role(role),
        )
        remove_btn.setEnabled(spec.deletable)
        if not spec.deletable:
            remove_btn.setToolTip("场景固定附件不可删除")
        open_btn.setProperty("pathAction", PathAction.REVEAL_IN_FOLDER.value)
        open_btn.setEnabled(False)
        clear_btn.setEnabled(False)
        if refresh_btn is not None:
            refresh_btn.setEnabled(False)

        actions_cell = QWidget(row)
        actions_layout = QHBoxLayout(actions_cell)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.addStretch(1)
        actions_layout.addWidget(actions)

        top_layout.addWidget(index_label, 0, Qt.AlignVCenter)
        top_layout.addWidget(preview, 0, Qt.AlignTop)
        top_layout.addWidget(token_edit, 0, Qt.AlignVCenter)
        top_layout.addWidget(name_edit, 0, Qt.AlignVCenter)
        top_layout.addWidget(source_widget, 1, Qt.AlignVCenter)
        top_layout.addWidget(actions_cell, 0, Qt.AlignVCenter)
        layout.addWidget(top)

        preparation_summary = AttachmentPreparationSummary(row)
        preparation_summary.setProperty("attachmentRole", spec.role)
        preparation_summary.prepare_requested.connect(
            lambda role=spec.role: self._open_attachment_preparation(role)
        )
        layout.addWidget(preparation_summary)

        self._attachment_role_rows[spec.role] = row
        self._attachment_role_index_labels[spec.role] = index_label
        self._attachment_role_preview_labels[spec.role] = preview
        self._attachment_role_token_edits[spec.role] = token_edit
        self._attachment_role_name_edits[spec.role] = name_edit
        self._attachment_role_path_edits[spec.role] = path_edit
        self._attachment_role_source_widgets[spec.role] = source_widget
        self._attachment_role_action_cells[spec.role] = actions_cell
        self._attachment_role_column_layouts[spec.role] = top_layout
        self._attachment_role_status_labels[spec.role] = status
        self._attachment_role_choose_buttons[spec.role] = choose_btn
        self._attachment_role_open_buttons[spec.role] = open_btn
        self._attachment_role_clear_buttons[spec.role] = clear_btn
        self._attachment_role_add_buttons[spec.role] = add_btn
        self._attachment_role_remove_buttons[spec.role] = remove_btn
        self._attachment_role_action_strips[spec.role] = actions
        if refresh_btn is not None:
            self._attachment_role_refresh_buttons[spec.role] = refresh_btn
        self._attachment_preparation_summaries[spec.role] = preparation_summary
        if not hasattr(self, "_attachment_drop_controllers"):
            self._attachment_drop_controllers = {}
        drop_controller = attach_path_drop(
            parent=row,
            surface=row,
            policy=_attachment_path_policy(spec),
            on_paths=lambda paths, role=spec.role: self._apply_attachment_paths(
                role,
                paths,
            ),
        )
        self._attachment_drop_controllers[spec.role] = drop_controller
        return row

    def _ensure_attachment_row_registries(self) -> None:
        """Own the attachment-row registry shape at the row-builder boundary."""

        for name in (
            "_attachment_role_rows",
            "_attachment_role_index_labels",
            "_attachment_role_preview_labels",
            "_attachment_role_token_edits",
            "_attachment_role_name_edits",
            "_attachment_role_path_edits",
            "_attachment_role_source_widgets",
            "_attachment_role_action_cells",
            "_attachment_role_column_layouts",
            "_attachment_role_status_labels",
            "_attachment_role_choose_buttons",
            "_attachment_role_open_buttons",
            "_attachment_role_clear_buttons",
            "_attachment_role_add_buttons",
            "_attachment_role_remove_buttons",
            "_attachment_role_refresh_buttons",
            "_attachment_role_action_strips",
            "_attachment_preparation_summaries",
            "_attachment_drop_controllers",
        ):
            if not hasattr(self, name):
                setattr(self, name, {})

    def _apply_attachment_column_metrics(
        self,
        metrics: AssetColumnMetrics,
        *,
        scope: str | None = None,
    ) -> None:
        if not isinstance(metrics, AssetColumnMetrics):
            return
        for role in self._attachment_role_rows:
            spec = next(
                (
                    item
                    for item in tuple(getattr(self, "_attachment_role_specs", ()))
                    if item.role == role
                ),
                None,
            )
            is_independent = bool(
                spec is not None and spec.source_kind == "single_file"
            )
            if scope == "independent" and not is_independent:
                continue
            if scope == "folder" and is_independent:
                continue
            layout = self._attachment_role_column_layouts.get(role)
            index = self._attachment_role_index_labels.get(role)
            preview = self._attachment_role_preview_labels.get(role)
            token = self._attachment_role_token_edits.get(role)
            name = self._attachment_role_name_edits.get(role)
            source = self._attachment_role_source_widgets.get(role)
            actions = self._attachment_role_action_cells.get(role)
            if any(
                item is None
                for item in (layout, index, preview, token, name, source, actions)
            ):
                continue
            layout.setSpacing(metrics.column_gap)
            index.setFixedWidth(metrics.index_width)
            preview.setFixedWidth(metrics.preview_width)
            token.setFixedWidth(metrics.token_width)
            name.setFixedWidth(metrics.name_width)
            source.setVisible(metrics.source_visible)
            actions.setFixedWidth(metrics.actions_width)

    def _configure_asset_icon_button(self, button: QPushButton, icon_name: str, tooltip: str) -> None:
        button.setProperty("asset_icon_name", icon_name)
        button.setProperty("asset_text_action", False)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setCursor(Qt.PointingHandCursor)
        apply_icon_button_style(
            button,
            variant="ghost-danger" if icon_name in {"trash-2", "x"} else "secondary",
            size=34,
            icon_size=16,
        )

    def _configure_asset_text_button(
        self,
        button: QPushButton,
        icon_name: str,
        text: str,
        *,
        tooltip: str = "",
        variant: str = "secondary",
    ) -> None:
        """Configure a discoverable text action while retaining a leading icon."""

        theme = get_theme()
        accessible = tooltip or text
        button.setText(text)
        button.setProperty("asset_icon_name", icon_name)
        button.setProperty("asset_text_action", True)
        button.setProperty("asset_action_text", text)
        button.setProperty("variant", variant)
        button.setToolTip(accessible)
        button.setAccessibleName(accessible)
        button.setCursor(Qt.PointingHandCursor)
        button.setIcon(
            get_icon(
                icon_name,
                16,
                theme.text_on_primary if variant == "primary" else theme.icon_primary,
            )
        )
        apply_button_variant(button, variant)
        button.setStyleSheet(build_button_stylesheet(theme))


__all__ = ["AssetRowsPresenterMixin"]
