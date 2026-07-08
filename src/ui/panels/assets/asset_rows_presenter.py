"""Presenter mixin for asset slot and attachment row construction."""

from __future__ import annotations

from src.qt_api import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSize,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
)
from src.ui.panels.assets.roles import _asset_slot_supports_alt_text


class AssetRowsPresenterMixin:
    """Build retained local asset and attachment rows."""

    def _build_asset_slot_row(self, role: str, label: str, target: str, *, parent: QWidget) -> QWidget:
        row = QFrame(parent)
        row.setObjectName("asset_slot_row")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        thumbnail = QLabel("未选", row)
        thumbnail.setObjectName("asset_slot_thumbnail")
        thumbnail.setFixedSize(56, 56)
        thumbnail.setAlignment(Qt.AlignCenter)

        title = QLabel(label, row)
        target_label = QLabel(f"用于：{target}", row)
        status = QLabel("未选择", row)
        title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        target_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        target_label.setWordWrap(True)
        status.setWordWrap(True)

        choose_btn = QPushButton(row)
        view_btn = QPushButton(row)
        open_btn = QPushButton(row)
        clear_btn = QPushButton(row)
        self._configure_asset_icon_button(choose_btn, "folder-open", "选择图片")
        self._configure_asset_icon_button(view_btn, "eye", "查看图片")
        self._configure_asset_icon_button(open_btn, "square-arrow-out-up-right", "打开原图")
        self._configure_asset_icon_button(clear_btn, "trash-2", "清除图片")
        choose_btn.clicked.connect(lambda *_args, slot_role=role: self._select_asset_file(slot_role))
        view_btn.clicked.connect(lambda *_args, slot_role=role: self._show_asset_slot_path(slot_role))
        open_btn.clicked.connect(lambda *_args, slot_role=role: self._open_asset_slot_path(slot_role))
        clear_btn.clicked.connect(lambda *_args, slot_role=role: self._clear_asset_file(slot_role))

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)
        text_layout.addWidget(title)
        text_layout.addWidget(target_label)
        text_layout.addWidget(status)

        alt_text_input = None
        if _asset_slot_supports_alt_text(role):
            alt_text_input = QLineEdit(row)
            alt_text_input.setPlaceholderText("图片说明")
            alt_text_input.textChanged.connect(lambda *_args: self._refresh_summary())
            text_layout.addWidget(alt_text_input)

        top_layout.addWidget(thumbnail, 0, Qt.AlignTop)
        top_layout.addLayout(text_layout, 1)

        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        actions_layout.addStretch(1)
        actions_layout.addWidget(choose_btn)
        actions_layout.addWidget(view_btn)
        actions_layout.addWidget(open_btn)
        actions_layout.addWidget(clear_btn)

        layout.addLayout(top_layout)
        layout.addLayout(actions_layout)

        self._asset_slot_rows[role] = row
        self._asset_slot_choose_buttons[role] = choose_btn
        self._asset_slot_thumbnail_labels[role] = thumbnail
        self._asset_slot_status_labels[role] = status
        if alt_text_input is not None:
            self._asset_slot_alt_text_inputs[role] = alt_text_input
        self._asset_slot_view_buttons[role] = view_btn
        self._asset_slot_open_buttons[role] = open_btn
        self._asset_slot_clear_buttons[role] = clear_btn
        for drop_target in (row, thumbnail, title, target_label, status):
            drop_target.setAcceptDrops(True)
            drop_target.setProperty("asset_role", role)
            drop_target.installEventFilter(self)
        return row

    def _build_attachment_role_row(self, spec, *, parent: QWidget) -> QWidget:
        row = QFrame(parent)
        row.setObjectName("attachment_role_row")
        row.setProperty("attachment_role", spec.role)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        text_widget = QWidget(row)
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)
        title = QLabel(spec.label, text_widget)
        title.setObjectName("attachment_role_title")
        accepted = " / ".join(spec.accepted_types)
        status = QLabel(
            f"必需，支持 {accepted}" if spec.required else f"可选，支持 {accepted}",
            text_widget,
        )
        status.setObjectName("attachment_role_status")
        status.setWordWrap(True)
        text_layout.addWidget(title)
        text_layout.addWidget(status)

        choose_btn = QPushButton("选择", row)
        open_btn = QPushButton("打开", row)
        clear_btn = QPushButton("清除", row)
        self._configure_asset_icon_button(choose_btn, "folder-open", f"选择{spec.label}")
        self._configure_asset_icon_button(open_btn, "external-link", f"打开{spec.label}")
        self._configure_asset_icon_button(clear_btn, "x", f"清除{spec.label}")
        choose_btn.clicked.connect(lambda *_args, role=spec.role: self._select_attachment_file(role))
        open_btn.clicked.connect(lambda *_args, role=spec.role: self._open_attachment_path(role))
        clear_btn.clicked.connect(lambda *_args, role=spec.role: self._clear_attachment_file(role))
        open_btn.setEnabled(False)
        clear_btn.setEnabled(False)

        layout.addWidget(text_widget, 1)
        layout.addWidget(choose_btn)
        layout.addWidget(open_btn)
        layout.addWidget(clear_btn)

        self._attachment_role_rows[spec.role] = row
        self._attachment_role_status_labels[spec.role] = status
        self._attachment_role_choose_buttons[spec.role] = choose_btn
        self._attachment_role_open_buttons[spec.role] = open_btn
        self._attachment_role_clear_buttons[spec.role] = clear_btn
        return row

    def _configure_asset_icon_button(self, button: QPushButton, icon_name: str, tooltip: str) -> None:
        button.setProperty("asset_icon_name", icon_name)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setFixedSize(34, 34)
        button.setIconSize(QSize(16, 16))


__all__ = ["AssetRowsPresenterMixin"]
