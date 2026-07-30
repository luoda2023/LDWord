"""Presenter for delivery attachments, isolated from inline images."""

from __future__ import annotations

from src.qt_api import QFrame, QVBoxLayout, QWidget
from src.services.material_attachments import (
    build_attachment_binding,
    build_directory_attachment_binding,
)
from src.shared.ui.card import Card
from src.shared.ui.asset_column_guide import AssetColumnGuide
from src.shared.ui.token_section_header import TokenSectionHeader


class AttachmentInventorySetupPresenterMixin:
    """Build the attachment-only inventory page."""

    def _setup_attachment_inventory_card(self) -> None:
        attachment_card = Card(parent=self._section_contents["attachments"])
        self._attachment_card = attachment_card
        attachment_card.set_header("附件资料", icon_name="gallery-vertical-end")

        (
            self._independent_attachments_header,
            self._independent_attachments_body,
            self._independent_attachments_column_guide,
            self._independent_attachments_container,
            self._independent_attachments_layout,
        ) = self._build_attachment_inventory_section(
            attachment_card,
            title="独立附件",
            add_text="＋ 新增独立附件",
            object_name="independent_attachment_section_header",
            source_text="附件来源",
            action_count=5,
            scope="independent",
        )
        self._independent_attachments_title = (
            self._independent_attachments_header.title_label
        )
        self._independent_attachments_count = (
            self._independent_attachments_header.count_label
        )
        self._add_independent_attachment_btn = (
            self._independent_attachments_header.add_button
        )
        self._add_independent_attachment_btn.clicked.connect(
            self._request_independent_attachment
        )

        separator = QFrame(attachment_card)
        separator.setObjectName("asset_section_separator")
        separator.setFrameShape(QFrame.NoFrame)
        separator.setMinimumHeight(1)
        separator.setMaximumHeight(1)
        attachment_card.add_widget(separator)

        section_gap = QWidget(attachment_card)
        section_gap.setObjectName("attachment_folder_section_gap")
        section_gap.setMinimumHeight(10)
        section_gap.setMaximumHeight(10)
        attachment_card.add_widget(section_gap)

        (
            self._attachment_folders_header,
            self._attachment_folders_body,
            self._attachment_folders_column_guide,
            self._attachment_folders_container,
            self._attachment_folders_layout,
        ) = self._build_attachment_inventory_section(
            attachment_card,
            title="附件文件夹",
            add_text="＋ 新增附件文件夹",
            object_name="attachment_folder_section_header",
            source_text="文件夹来源",
            action_count=6,
            scope="folder",
        )
        self._attachment_folders_title = self._attachment_folders_header.title_label
        self._attachment_folders_count = self._attachment_folders_header.count_label
        self._add_attachment_folder_btn = self._attachment_folders_header.add_button
        self._add_attachment_folder_btn.clicked.connect(
            self._request_attachment_folder
        )

        self._sync_attachment_role_rows()
        self._section_layouts["attachments"].addWidget(attachment_card)

    def _build_attachment_inventory_section(
        self,
        card: Card,
        *,
        title: str,
        add_text: str,
        object_name: str,
        source_text: str,
        action_count: int,
        scope: str,
    ) -> tuple[TokenSectionHeader, QWidget, AssetColumnGuide, QWidget, QVBoxLayout]:
        """Build one attachment list using the same visual grammar as images."""

        header = TokenSectionHeader(
            title,
            add_text=add_text,
            object_name=object_name,
            parent=card,
        )
        header.title_label.setObjectName("asset_section_title")
        header.count_label.setObjectName("asset_section_count")
        card.add_widget(header)

        body = QWidget(card)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        guide = AssetColumnGuide(
            source_text=source_text,
            action_count=action_count,
            parent=body,
        )
        guide.metrics_changed.connect(
            lambda metrics, selected_scope=scope: self._apply_attachment_column_metrics(
                metrics,
                scope=selected_scope,
            )
        )
        body_layout.addWidget(guide)

        container = QWidget(body)
        rows_layout = QVBoxLayout(container)
        rows_layout.setContentsMargins(0, 6, 0, 0)
        rows_layout.setSpacing(0)
        body_layout.addWidget(container)
        card.add_widget(body)
        return header, body, guide, container, rows_layout

    def _migrate_legacy_attachment_paths(self) -> None:
        """Move old shared ``asset_paths`` facts into typed attachments once."""

        for spec in tuple(getattr(self, "_attachment_role_specs", ()) or ()):
            legacy_path = str(self._asset_paths.pop(spec.role, "") or "").strip()
            if not legacy_path or spec.role in self._attachment_bindings:
                continue
            try:
                common = {
                    "role": spec.role,
                    "accepted_types": spec.accepted_types,
                    "required": spec.required,
                    "min_items": spec.min_items,
                    "max_items": spec.max_items,
                    "label": self._attachment_role_display_name(spec),
                    "processing_mode": spec.processing_mode,
                }
                if spec.source_kind == "directory_package":
                    binding = build_directory_attachment_binding(
                        source_directory=legacy_path,
                        recursive=spec.recursive,
                        **common,
                    )
                else:
                    binding = build_attachment_binding(
                        source_paths=(legacy_path,),
                        source_kind=spec.source_kind,
                        cardinality=spec.cardinality,
                        **common,
                    )
                self._attachment_bindings[spec.role] = binding
            except Exception as exc:
                self._attachment_legacy_errors[spec.role] = str(exc)


__all__ = ["AttachmentInventorySetupPresenterMixin"]
