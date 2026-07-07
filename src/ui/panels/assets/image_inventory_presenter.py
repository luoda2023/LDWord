"""Presenter mixin for building the local image inventory card."""

from __future__ import annotations

from src.qt_api import QLabel, QHBoxLayout, QPushButton, Qt, QVBoxLayout, QWidget
from src.shared.ui.card import Card
from src.shared.ui.folder_picker import FolderPicker
from src.shared.ui.inspector_form import InspectorForm


class ImageInventorySetupPresenterMixin:
    """Build the retained local image inventory and preview card."""

    def _setup_image_inventory_card(self) -> None:
        image_card = Card(parent=self._section_contents["images"])
        self._image_card = image_card
        image_card.set_header("鍥剧墖鏉愭枡", icon_name="image")
        self._assets_picker = FolderPicker(placeholder="鏈€夋嫨鍥剧墖鐩綍", parent=image_card)
        self._assets_picker.folder_changed.connect(lambda *_: self._refresh_summary())
        self._image_assets_status_label = QLabel(image_card)
        self._image_assets_status_label.setWordWrap(True)
        image_form = InspectorForm(parent=image_card)
        image_form.add_field("鍥剧墖鐩綍", self._assets_picker)
        image_card.add_widget(image_form)
        self._asset_slots_container = QWidget(image_card)
        self._asset_slots_layout = QVBoxLayout(self._asset_slots_container)
        self._asset_slots_layout.setContentsMargins(0, 0, 0, 0)
        self._asset_slots_layout.setSpacing(8)
        image_card.add_widget(self._asset_slots_container)
        self._sync_asset_slot_rows()
        self._setup_question_figure_items_table(image_card)
        self._setup_question_figure_library_card(image_card)
        self._setup_question_figure_library_issue_table(image_card)
        self._setup_question_figure_library_version_history_table(image_card)
        self._setup_question_figure_library_master_version_table(image_card)
        self._attachment_inventory_label = QLabel("闄勪欢娓呭崟", image_card)
        self._attachment_inventory_label.setObjectName("attachment_inventory_label")
        image_card.add_widget(self._attachment_inventory_label)
        self._attachment_roles_container = QWidget(image_card)
        self._attachment_roles_layout = QVBoxLayout(self._attachment_roles_container)
        self._attachment_roles_layout.setContentsMargins(0, 0, 0, 0)
        self._attachment_roles_layout.setSpacing(8)
        image_card.add_widget(self._attachment_roles_container)
        self._sync_attachment_role_rows()
        self._image_preview_label = QLabel("閫夋嫨鍥剧墖鍚庡彲鏌ョ湅棰勮", image_card)
        self._image_preview_label.setObjectName("asset_preview_label")
        self._image_preview_label.setAlignment(Qt.AlignCenter)
        self._image_preview_label.setMinimumHeight(160)
        self._image_preview_label.setWordWrap(True)
        image_card.add_widget(self._image_preview_label)
        preview_actions_row = QWidget(image_card)
        preview_actions_layout = QHBoxLayout(preview_actions_row)
        preview_actions_layout.setContentsMargins(0, 0, 0, 0)
        preview_actions_layout.setSpacing(8)
        self._full_image_preview_btn = QPushButton(preview_actions_row)
        self._full_image_preview_btn.setObjectName("asset_full_image_preview_button")
        self._configure_asset_icon_button(
            self._full_image_preview_btn,
            "square-arrow-out-up-right",
            "鎵撳紑澶у浘棰勮",
        )
        self._full_image_preview_btn.setEnabled(False)
        self._full_image_preview_btn.clicked.connect(self._open_current_image_preview_dialog)
        preview_actions_layout.addStretch(1)
        preview_actions_layout.addWidget(self._full_image_preview_btn)
        image_card.add_widget(preview_actions_row)
        image_card.add_widget(self._image_assets_status_label)
        self._section_layouts["images"].addWidget(image_card)


__all__ = ["ImageInventorySetupPresenterMixin"]
