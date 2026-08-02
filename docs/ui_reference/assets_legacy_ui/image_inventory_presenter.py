"""Presenter mixin for building the local image inventory card."""

from __future__ import annotations

from src.qt_api import QFrame, QLabel, QVBoxLayout, QWidget
from src.shared.ui.asset_column_guide import AssetColumnGuide
from src.shared.ui.card import Card
from src.shared.ui.folder_picker import FolderPicker
from src.shared.ui.token_section_header import TokenSectionHeader


class ImageInventorySetupPresenterMixin:
    """Build the retained local image inventory and preview card."""

    def _setup_image_inventory_card(self) -> None:
        image_card = Card(parent=self._section_contents["images"])
        self._image_card = image_card
        image_card.set_header("图片资料", icon_name="image")
        # ``assets_dir`` is an explicit package source, not a fallback for the
        # role-specific sources edited below. It stays hidden because this UI
        # only authors sources with an explicit role owner.
        self._assets_picker = FolderPicker(placeholder="图片目录", parent=image_card)
        self._assets_picker.setVisible(False)
        self._assets_picker.folder_changed.connect(lambda *_: self._refresh_summary())
        self._image_assets_status_label = QLabel(image_card)
        self._image_assets_status_label.setWordWrap(True)
        # Role-specific rows surface source state and conflicts, so this global
        # status line remains a non-visual accessibility/status projection.
        self._image_assets_status_label.setVisible(False)

        single_header = TokenSectionHeader(
            "单图",
            add_text="＋ 新增单图",
            object_name="single_asset_section_header",
            parent=image_card,
        )
        self._single_assets_title = single_header.title_label
        self._single_assets_title.setObjectName("asset_section_title")
        self._single_assets_count = single_header.count_label
        self._single_assets_count.setObjectName("asset_section_count")
        self._add_single_asset_btn = single_header.add_button
        self._add_single_asset_btn.clicked.connect(self._request_asset_slot)
        image_card.add_widget(single_header)

        self._asset_slots_body = QWidget(image_card)
        single_body_layout = QVBoxLayout(self._asset_slots_body)
        single_body_layout.setContentsMargins(0, 0, 0, 0)
        single_body_layout.setSpacing(0)
        self._asset_slots_column_guide = AssetColumnGuide(
            source_text="图片来源",
            action_count=5,
            parent=self._asset_slots_body,
        )
        self._asset_slots_column_guide.setProperty("assetScope", "single")
        self._asset_slots_column_guide.metrics_changed.connect(
            self._apply_asset_slot_column_metrics
        )
        single_body_layout.addWidget(self._asset_slots_column_guide)

        self._asset_slots_container = QWidget(self._asset_slots_body)
        self._asset_slots_layout = QVBoxLayout(self._asset_slots_container)
        self._asset_slots_layout.setContentsMargins(0, 6, 0, 0)
        self._asset_slots_layout.setSpacing(0)
        single_body_layout.addWidget(self._asset_slots_container)
        image_card.add_widget(self._asset_slots_body)
        self._sync_asset_slot_rows()

        separator = QFrame(image_card)
        separator.setObjectName("asset_section_separator")
        separator.setFrameShape(QFrame.NoFrame)
        separator.setMinimumHeight(1)
        separator.setMaximumHeight(1)
        image_card.add_widget(separator)

        self._asset_group_section_gap = QWidget(image_card)
        self._asset_group_section_gap.setObjectName("asset_group_section_gap")
        # This is a non-interactive layout spacer.  Keep its geometry explicit
        # without bypassing the panel-wide ban on business-layer
        # ``setFixedHeight`` calls used by themed controls.
        self._asset_group_section_gap.setMinimumHeight(10)
        self._asset_group_section_gap.setMaximumHeight(10)
        image_card.add_widget(self._asset_group_section_gap)

        self._asset_groups_header = TokenSectionHeader(
            "多图文件夹",
            add_text="＋ 新增多图文件夹",
            object_name="asset_group_section_header",
            parent=image_card,
        )
        self._asset_groups_title = self._asset_groups_header.title_label
        self._asset_groups_title.setObjectName("asset_section_title")
        self._asset_groups_count = self._asset_groups_header.count_label
        self._asset_groups_count.setObjectName("asset_section_count")
        self._add_asset_group_btn = self._asset_groups_header.add_button
        self._add_asset_group_btn.clicked.connect(self._request_asset_group)
        image_card.add_widget(self._asset_groups_header)

        self._asset_groups_body = QWidget(image_card)
        group_body_layout = QVBoxLayout(self._asset_groups_body)
        group_body_layout.setContentsMargins(0, 0, 0, 0)
        group_body_layout.setSpacing(0)
        self._asset_groups_column_guide = AssetColumnGuide(
            source_text="文件夹来源",
            action_count=6,
            parent=self._asset_groups_body,
        )
        self._asset_groups_column_guide.setProperty("assetScope", "multiple")
        self._asset_groups_column_guide.metrics_changed.connect(
            self._apply_asset_group_column_metrics
        )
        group_body_layout.addWidget(self._asset_groups_column_guide)

        self._asset_groups_container = QWidget(self._asset_groups_body)
        self._asset_groups_layout = QVBoxLayout(self._asset_groups_container)
        self._asset_groups_layout.setContentsMargins(0, 6, 0, 0)
        self._asset_groups_layout.setSpacing(0)
        group_body_layout.addWidget(self._asset_groups_container)
        image_card.add_widget(self._asset_groups_body)
        self._sync_asset_group_rows()

        self._setup_question_figure_items_table(image_card)
        self._setup_question_figure_library_card(image_card)
        self._setup_question_figure_library_issue_table(image_card)
        self._setup_question_figure_library_version_history_table(image_card)
        self._setup_question_figure_library_master_version_table(image_card)
        self._section_layouts["images"].addWidget(image_card)


__all__ = ["ImageInventorySetupPresenterMixin"]
