"""Retained token-row visual grammar backed by Material Package V1."""

from __future__ import annotations

from pathlib import Path

from src.qt_api import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPixmap,
    QSize,
    QSizePolicy,
    Qt,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.engine.material_token_contract import (
    MaterialTokenNamespace,
    parse_material_token,
)
from src.shared.ui.compact_row_actions import CompactRowActions
from src.shared.ui.material_name_edit import MaterialNameEdit
from src.shared.ui.material_text_views import ElidedPathEdit
from src.shared.ui.material_token_edit import MaterialTokenEdit
from src.shared.ui.theme import bind_theme, get_theme


class _AssetPreviewLabel(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            self.clicked.emit()


class LegacyFieldTokenRow(QFrame):
    """Old field-token row with a V1 key/value callback contract."""

    value_committed = Signal(str, str)
    token_renamed = Signal(str, str)
    clear_requested = Signal(str)
    remove_requested = Signal(str)

    def __init__(
        self,
        *,
        index: int,
        key: str,
        value: str,
        custom: bool,
        writable: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._key = key
        self._custom = custom
        self.setObjectName("material_v1_field_token_row")
        self.setProperty("tokenRow", True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.setMinimumHeight(get_theme().token_row_min_height)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            4,
            get_theme().token_row_padding_y,
            4,
            get_theme().token_row_padding_y,
        )
        layout.setSpacing(get_theme().token_row_column_gap)

        self.index_label = QLabel(str(index), self)
        self.index_label.setObjectName("asset_row_index")
        self.index_label.setAlignment(Qt.AlignCenter)

        self.token_edit = MaterialTokenEdit(
            f"{{{{@text:{key}}}}}",
            self,
            editable=custom and writable,
            namespace=MaterialTokenNamespace.TEXT,
        )
        self.token_edit.setObjectName("material_v1_field_token")
        self.token_edit.setCompleted(bool(str(value).strip()))
        self.token_edit.editingFinished.connect(self._commit_token)

        self.value_edit = QLineEdit(str(value), self)
        self.value_edit.setObjectName("material_v1_field_value")
        self.value_edit.setPlaceholderText("填写字段内容")
        self.value_edit.setReadOnly(not writable)
        self.value_edit.editingFinished.connect(self._commit_value)

        self.actions = CompactRowActions(self)
        self.clear_button = self.actions.add_action(
            "clear",
            icon_name="x",
            tooltip="清空当前层字段内容",
            variant="ghost-danger",
            callback=lambda *_: self.clear_requested.emit(self._key),
        )
        self.remove_button = self.actions.add_action(
            "remove",
            icon_name="trash-2",
            tooltip="删除自定义字段",
            variant="outlined-danger",
            callback=lambda *_: self.remove_requested.emit(self._key),
        )
        self.clear_button.setEnabled(writable and bool(str(value).strip()))
        self.remove_button.setVisible(custom)
        self.remove_button.setEnabled(custom and writable)
        self.actions.sync_visibility()

        layout.addWidget(self.index_label, 0, Qt.AlignVCenter)
        layout.addWidget(self.token_edit, 0, Qt.AlignVCenter)
        layout.addWidget(self.value_edit, 1, Qt.AlignVCenter)
        layout.addWidget(self.actions, 0, Qt.AlignVCenter)
        bind_theme(self, self._apply_theme)
        self._apply_theme()

    @property
    def key(self) -> str:
        return self._key

    def apply_metrics(self, metrics) -> None:
        self.layout().setContentsMargins(
            metrics.row_margin_x,
            get_theme().token_row_padding_y,
            metrics.row_margin_x,
            get_theme().token_row_padding_y,
        )
        self.layout().setSpacing(metrics.column_gap)
        self.index_label.setFixedWidth(metrics.index_width)
        self.token_edit.setFixedWidth(metrics.token_width)
        self.actions.setFixedWidth(metrics.actions_width)

    def _commit_token(self) -> None:
        try:
            key = parse_material_token(self.token_edit.text()).identifier
        except (TypeError, ValueError):
            self.token_edit.setText(f"{{{{@text:{self._key}}}}}")
            return
        if key and key != self._key:
            self.token_renamed.emit(self._key, key)

    def _commit_value(self) -> None:
        self.value_committed.emit(self._key, self.value_edit.text())

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.layout().setContentsMargins(
            4,
            theme.token_row_padding_y,
            4,
            theme.token_row_padding_y,
        )
        self.layout().setSpacing(theme.token_row_column_gap)
        self.index_label.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; "
            f"font-weight: {theme.font_weight_emphasis}; color: {theme.primary}; "
            "background: transparent; border: none;"
        )


class LegacyContentTokenRow(QFrame):
    """Old file-material row: number, type, token, source and actions."""

    token_renamed = Signal(str, str)
    choose_requested = Signal(str)
    open_requested = Signal(str)
    clear_requested = Signal(str)
    add_requested = Signal(str)
    remove_requested = Signal(str)

    def __init__(
        self,
        *,
        index: int,
        role: str,
        namespace: MaterialTokenNamespace,
        display_name: str,
        source_text: str,
        custom: bool,
        writable: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._role = role
        self.setObjectName("material_v1_content_token_row")
        self.setProperty("tokenRow", True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.setMinimumHeight(get_theme().token_row_min_height)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            4,
            get_theme().token_row_padding_y,
            4,
            get_theme().token_row_padding_y,
        )
        layout.setSpacing(get_theme().token_row_column_gap)

        self.index_label = QLabel(str(index), self)
        self.index_label.setObjectName("asset_row_index")
        self.index_label.setAlignment(Qt.AlignCenter)
        suffix = Path(display_name).suffix.lstrip(".").upper()
        self.preview_label = QLabel(suffix or "未选", self)
        self.preview_label.setObjectName("content_material_thumbnail")
        self.preview_label.setAlignment(Qt.AlignCenter)

        token = f"{{{{@{namespace.value}:{role}}}}}"
        self.token_edit = MaterialTokenEdit(
            token,
            self,
            editable=custom and writable,
            namespace=namespace,
        )
        self.token_edit.setObjectName("material_v1_content_token")
        self.token_edit.setCompleted(bool(display_name))
        self.token_edit.editingFinished.connect(self._commit_token)

        self.path_edit = ElidedPathEdit(source_text or display_name, self)
        self.path_edit.setObjectName("material_v1_content_path")
        self.path_edit.setPlaceholderText("尚未选择文件")
        self.path_edit.setAccessibleName(source_text or display_name)

        self.actions = CompactRowActions(self)
        self.clear_button = self.actions.add_action(
            "clear",
            icon_name="x",
            tooltip="清除当前层文件",
            variant="ghost-danger",
            callback=lambda *_: self.clear_requested.emit(self._role),
        )
        self.choose_button = self.actions.add_action(
            "choose",
            icon_name="file-input",
            tooltip="选择文件",
            callback=lambda *_: self.choose_requested.emit(self._role),
        )
        self.open_button = self.actions.add_action(
            "open",
            icon_name="square-arrow-out-up-right",
            tooltip="打开文件",
            callback=lambda *_: self.open_requested.emit(self._role),
        )
        self.add_button = self.actions.add_action(
            "add",
            icon_name="plus",
            tooltip="在当前项后新增同类资料",
            variant="outlined-primary",
            callback=lambda *_: self.add_requested.emit(self._role),
        )
        self.remove_button = self.actions.add_action(
            "remove",
            icon_name="trash-2",
            tooltip="删除自定义资料",
            variant="outlined-danger",
            callback=lambda *_: self.remove_requested.emit(self._role),
        )
        self.clear_button.setEnabled(writable and bool(display_name))
        self.choose_button.setEnabled(writable)
        self.open_button.setEnabled(bool(display_name))
        self.add_button.setEnabled(writable)
        self.remove_button.setVisible(custom)
        self.remove_button.setEnabled(custom and writable)
        self.actions.sync_visibility()

        layout.addWidget(self.index_label, 0, Qt.AlignVCenter)
        layout.addWidget(self.preview_label, 0, Qt.AlignVCenter)
        layout.addWidget(self.token_edit, 0, Qt.AlignVCenter)
        layout.addWidget(self.path_edit, 1, Qt.AlignVCenter)
        layout.addWidget(self.actions, 0, Qt.AlignVCenter)
        bind_theme(self, self._apply_theme)
        self._apply_theme()

    @property
    def role(self) -> str:
        return self._role

    def _commit_token(self) -> None:
        try:
            role = parse_material_token(self.token_edit.text()).identifier
        except (TypeError, ValueError):
            return
        if role and role != self._role:
            self.token_renamed.emit(self._role, role)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.index_label.setFixedWidth(34)
        self.preview_label.setFixedSize(52, 52)
        self.token_edit.setMinimumWidth(240)
        self.layout().setContentsMargins(
            4,
            theme.token_row_padding_y,
            4,
            theme.token_row_padding_y,
        )
        self.layout().setSpacing(theme.token_row_column_gap)
        self.index_label.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; "
            f"font-weight: {theme.font_weight_emphasis}; color: {theme.primary}; "
            "background: transparent; border: none;"
        )
        self.preview_label.setStyleSheet(
            f"background: {theme.bg_card}; border: 1px solid {theme.border}; "
            f"border-radius: {theme.radius_sm}px; color: {theme.text_hint}; "
            f"font-size: {theme.font_size_xs}px;"
        )


class LegacyAssetTokenRow(QFrame):
    """Image/attachment row aligned to the retained AssetColumnGuide."""

    token_renamed = Signal(str, str)
    label_committed = Signal(str, str)
    choose_requested = Signal(str)
    refresh_requested = Signal(str)
    open_requested = Signal(str)
    clear_requested = Signal(str)
    add_requested = Signal(str)
    remove_requested = Signal(str)
    preview_requested = Signal(str)

    def __init__(
        self,
        *,
        index: int,
        role: str,
        namespace: MaterialTokenNamespace,
        label: str,
        display_name: str,
        source_text: str,
        custom: bool,
        writable: bool,
        folder: bool = False,
        folder_items: tuple[str, ...] = (),
        preview_path: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._role = role
        self._folder = folder
        self.setObjectName("asset_group_row" if folder else "asset_slot_row")
        self.setProperty("tokenRow", True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.setMinimumHeight(get_theme().token_row_min_height)
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        top = QWidget(self)
        self._top_layout = QHBoxLayout(top)
        self._top_layout.setContentsMargins(0, 0, 0, 0)

        self.index_label = QLabel(str(index), top)
        self.index_label.setObjectName("asset_row_index")
        self.index_label.setAlignment(Qt.AlignCenter)
        suffix = Path(display_name).suffix.lstrip(".").upper()
        preview_text = f"{len(folder_items)} 项" if folder_items else suffix or "未选"
        self.preview_label = _AssetPreviewLabel(preview_text, top)
        self.preview_label.setObjectName(
            "asset_group_thumbnail" if folder else "asset_slot_thumbnail"
        )
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setCursor(Qt.PointingHandCursor)
        self.preview_label.clicked.connect(
            lambda: self.preview_requested.emit(self._role)
        )
        self._set_preview(preview_path, fallback_text=preview_text)
        self.token_edit = MaterialTokenEdit(
            f"{{{{@{namespace.value}:{role}}}}}",
            top,
            editable=custom and writable,
            namespace=namespace,
        )
        self.token_edit.setObjectName(
            "asset_group_token" if folder else "asset_slot_target"
        )
        self.token_edit.setCompleted(bool(display_name))
        self.token_edit.editingFinished.connect(self._commit_token)
        self.name_edit = MaterialNameEdit(label, top)
        self.name_edit.setObjectName(
            "asset_group_name" if folder else "asset_slot_name"
        )
        self.name_edit.setReadOnly(not (custom and writable))
        self.name_edit.editingFinished.connect(
            lambda: self.label_committed.emit(self._role, self.name_edit.text())
        )
        self.source_widget = QWidget(top)
        source_layout = QVBoxLayout(self.source_widget)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.setSpacing(2)
        self.path_edit = ElidedPathEdit(
            source_text or display_name,
            self.source_widget,
        )
        self.path_edit.setObjectName(
            "asset_group_path" if folder else "asset_slot_path"
        )
        self.path_edit.setPlaceholderText("尚未选择来源")
        self.status_label = QLabel("", self.source_widget)
        self.status_label.setObjectName(
            "asset_group_status" if folder else "asset_slot_status"
        )
        self.status_label.setVisible(False)
        source_layout.addWidget(self.path_edit)
        source_layout.addWidget(self.status_label)

        self.actions = CompactRowActions(top)
        self.actions.setObjectName(
            "asset_group_actions" if folder else "asset_slot_actions"
        )
        self.clear_button = self.actions.add_action(
            "clear",
            icon_name="x",
            tooltip="清除当前层来源",
            variant="ghost-danger",
            callback=lambda *_: self.clear_requested.emit(self._role),
        )
        self.choose_button = self.actions.add_action(
            "choose",
            icon_name="file-input",
            tooltip="选择来源",
            callback=lambda *_: self.choose_requested.emit(self._role),
        )
        self.refresh_button = None
        if folder:
            self.refresh_button = self.actions.add_action(
                "refresh",
                icon_name="refresh-ccw",
                tooltip="重新扫描文件夹",
                callback=lambda *_: self.refresh_requested.emit(self._role),
            )
        self.open_button = self.actions.add_action(
            "open",
            icon_name="square-arrow-out-up-right",
            tooltip="打开来源",
            callback=lambda *_: self.open_requested.emit(self._role),
        )
        self.add_button = self.actions.add_action(
            "add",
            icon_name="plus",
            tooltip="新增同类资料",
            variant="outlined-primary",
            callback=lambda *_: self.add_requested.emit(self._role),
        )
        self.remove_button = self.actions.add_action(
            "remove",
            icon_name="trash-2",
            tooltip="删除自定义资料",
            variant="outlined-danger",
            callback=lambda *_: self.remove_requested.emit(self._role),
        )
        self.clear_button.setEnabled(writable and bool(display_name))
        self.choose_button.setEnabled(writable)
        if self.refresh_button is not None:
            self.refresh_button.setVisible(bool(display_name))
            self.refresh_button.setEnabled(writable and bool(display_name))
        self.open_button.setEnabled(bool(display_name))
        if folder:
            self.open_button.setVisible(bool(display_name))
        self.add_button.setEnabled(writable)
        self.remove_button.setVisible(custom)
        self.remove_button.setEnabled(custom and writable)
        self.actions.sync_visibility()

        self.actions_cell = QWidget(top)
        actions_cell_layout = QHBoxLayout(self.actions_cell)
        actions_cell_layout.setContentsMargins(0, 0, 0, 0)
        actions_cell_layout.setSpacing(0)
        actions_cell_layout.addStretch(1)
        actions_cell_layout.addWidget(self.actions)

        self._top_layout.addWidget(self.index_label, 0, Qt.AlignVCenter)
        self._top_layout.addWidget(self.preview_label, 0, Qt.AlignVCenter)
        self._top_layout.addWidget(self.token_edit, 0, Qt.AlignVCenter)
        self._top_layout.addWidget(self.name_edit, 0, Qt.AlignVCenter)
        self._top_layout.addWidget(self.source_widget, 1, Qt.AlignVCenter)
        self._top_layout.addWidget(self.actions_cell, 0, Qt.AlignVCenter)
        layout.addWidget(top)

        self.items_table = QTableWidget(self)
        self.items_table.setObjectName("asset_group_items_table")
        self.items_table.setColumnCount(4)
        self.items_table.setHorizontalHeaderLabels(
            ("序号", "包内名称", "原文件名", "状态")
        )
        self.items_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.items_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.setAlternatingRowColors(True)
        self.items_table.setShowGrid(False)
        header = self.items_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        for row_index, item_name in enumerate(folder_items):
            self.items_table.insertRow(row_index)
            values = (str(row_index + 1), item_name, item_name, "可用")
            for column, value in enumerate(values):
                self.items_table.setItem(
                    row_index,
                    column,
                    QTableWidgetItem(value),
                )
            self.items_table.setRowHeight(row_index, 34)
        if folder_items:
            header_height = max(
                28,
                self.items_table.horizontalHeader().sizeHint().height(),
            )
            content_height = sum(
                self.items_table.rowHeight(row_index)
                for row_index in range(self.items_table.rowCount())
            )
            resolved_height = min(220, header_height + content_height + 6)
            self.items_table.setMinimumHeight(resolved_height)
            self.items_table.setMaximumHeight(resolved_height)
        self.items_table.setVisible(folder and bool(folder_items))
        self.setMaximumHeight(360 if folder_items else 108)
        layout.addWidget(self.items_table)
        bind_theme(self, self._apply_theme)
        self._apply_theme()

    @property
    def role(self) -> str:
        return self._role

    def apply_metrics(self, metrics) -> None:
        self.layout().setContentsMargins(
            metrics.row_margin_x,
            get_theme().token_row_padding_y,
            metrics.row_margin_x,
            get_theme().token_row_padding_y,
        )
        self._top_layout.setSpacing(metrics.column_gap)
        self.index_label.setFixedWidth(metrics.index_width)
        self.preview_label.setFixedWidth(metrics.preview_width)
        self.token_edit.setFixedWidth(metrics.token_width)
        self.name_edit.setFixedWidth(metrics.name_width)
        self.source_widget.setVisible(metrics.source_visible)
        self.actions_cell.setFixedWidth(metrics.actions_width)

    def _commit_token(self) -> None:
        try:
            role = parse_material_token(self.token_edit.text()).identifier
        except (TypeError, ValueError):
            return
        if role and role != self._role:
            self.token_renamed.emit(self._role, role)

    def _set_preview(self, path: str, *, fallback_text: str) -> None:
        pixmap = QPixmap(str(path or ""))
        if pixmap.isNull():
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText(fallback_text)
            return
        self.preview_label.setText("")
        self.preview_label.setPixmap(
            pixmap.scaled(
                QSize(52, 52),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.layout().setContentsMargins(
            4,
            theme.token_row_padding_y,
            4,
            theme.token_row_padding_y,
        )
        self._top_layout.setSpacing(theme.token_row_column_gap)
        self.preview_label.setFixedSize(52, 52)
        self.index_label.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; "
            f"font-weight: {theme.font_weight_emphasis}; color: {theme.primary}; "
            "background: transparent; border: none;"
        )
        self.preview_label.setStyleSheet(
            f"background: {theme.bg_card}; border: 1px solid {theme.border}; "
            f"border-radius: {theme.radius_sm}px; color: {theme.text_hint}; "
            f"font-size: {theme.font_size_xs}px;"
        )


class LegacySingleImageTokenRow(LegacyAssetTokenRow):
    """V1-backed restoration of the original single-image row."""

    def __init__(self, **kwargs) -> None:
        super().__init__(folder=False, **kwargs)


class LegacyImageGroupTokenRow(LegacyAssetTokenRow):
    """V1-backed restoration of the original multi-image folder row."""

    def __init__(self, **kwargs) -> None:
        super().__init__(folder=True, **kwargs)


__all__ = [
    "LegacyAssetTokenRow",
    "LegacyContentTokenRow",
    "LegacyFieldTokenRow",
    "LegacyImageGroupTokenRow",
    "LegacySingleImageTokenRow",
]
