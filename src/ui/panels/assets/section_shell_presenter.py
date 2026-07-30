"""Presenter mixin for assets section shell construction and navigation."""

from __future__ import annotations

from src.qt_api import QSizePolicy, QTimer, QVBoxLayout, QWidget
from src.shared.ui.navigation_card import NavigationCard
from src.shared.ui.template_summary_card import TemplateSummaryCard
from src.shared.ui.theme import get_theme
from src.ui.panels.assets import ASSETS_SECTION_SPECS
from src.ui.panels.assets.specs import ASSETS_RUNTIME_SECTION_SPECS


class SectionShellPresenterMixin:
    """Build and coordinate the assets panel section shell."""

    def _build_section_navigation(self) -> None:
        specs_by_id = {spec.section_id: spec for spec in ASSETS_SECTION_SPECS}
        navigation_groups: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("", ("generate",)),
            (
                "资料准备",
                ("fields", "content", "timeline", "images", "attachments"),
            ),
        )
        for group_title, section_ids in navigation_groups:
            if group_title:
                self._section_nav.add_section_header(group_title)
            for section_id in section_ids:
                spec = specs_by_id[section_id]
                card = NavigationCard(
                    section_id,
                    spec.title,
                    icon_name=spec.icon_name,
                    parent=self._section_nav,
                )
                card.setObjectName(f"assets_section_card_{section_id}")
                self._section_nav_cards[section_id] = card
                self._section_nav.add_card(section_id, card)

    def _build_section_pages(self) -> None:
        for spec in ASSETS_RUNTIME_SECTION_SPECS:
            content = QWidget(self._detail_stack)
            content.setObjectName(f"assets_section_content_{spec.section_id}")
            content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

            layout = QVBoxLayout(content)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(get_theme().template_detail_section_gap)

            summary_card = TemplateSummaryCard(
                spec.title,
                spec.icon_name,
                compact_header=spec.section_id == "generate",
                parent=content,
            )
            summary_card.setObjectName(f"assets_section_summary_{spec.section_id}")
            if spec.section_id not in {
                "generate",
                "fields",
                "content",
                "timeline",
                "images",
                "attachments",
            }:
                layout.addWidget(summary_card)
            else:
                summary_card.hide()

            self._detail_stack.addWidget(content)
            self._section_scrolls[spec.section_id] = self._detail_scroll
            self._section_contents[spec.section_id] = content
            self._section_layouts[spec.section_id] = layout
            self._section_pages[spec.section_id] = content
            self._section_summary_cards[spec.section_id] = summary_card

        self._scroll_area = self._detail_scroll
        self._scroll_content = self._section_contents["generate"]
        self._detail_stack.setCurrentWidget(self._scroll_content)
        self._detail_geometry.set_active_widget(self._scroll_content)

    def _register_detail_cards(self) -> None:
        self._card_section_ids = {
            self._generate_card: "generate",
            self._archive_card: "generate",
            self._profile_card: "fields",
            self._content_card: "content",
            self._timeline_card: "timeline",
            self._image_rules_card: "images",
            self._image_card: "images",
            self._attachment_card: "attachments",
            self._preview_card: "preview",
            self._profile_list_card: "batch",
        }

    def _connect_signals(self) -> None:
        self.bridge.material_context_changed.connect(self._on_material_context_changed)
        self.bridge.document_loaded.connect(self._on_document_loaded)
        if hasattr(self.bridge, "execution_target_changed"):
            self.bridge.execution_target_changed.connect(
                self._on_execution_target_changed
            )
        self.bridge.scene_changed.connect(self._on_scene_changed)
        if hasattr(self.bridge, "work_mode_changed"):
            self.bridge.work_mode_changed.connect(
                self._on_material_package_work_mode_changed
            )
        watcher = getattr(self, "_material_package_library_watcher", None)
        if watcher is not None:
            watcher.directoryChanged.connect(
                self._on_material_package_library_path_changed
            )
            watcher.fileChanged.connect(
                self._on_material_package_library_path_changed
            )
        self.bridge.template_changed.connect(lambda *_: self._refresh_summary())
        self.bridge.material_repair_target_requested.connect(
            self._on_material_repair_target_requested
        )
        self.bridge.material_profile_repair_target_requested.connect(
            self._on_material_profile_repair_target_requested
        )
        self.bridge.material_profile_repair_candidate_requested.connect(
            self._on_material_profile_repair_candidate_requested
        )
        self._section_nav.card_selected.connect(self._on_section_selected)
        QTimer.singleShot(0, self._focus_pending_material_repair_target)

    def _on_section_selected(self, section_id: str) -> None:
        page = self._section_pages.get(section_id)
        if page is None:
            return
        self._detail_scroll.setUpdatesEnabled(False)
        self._detail_shell.setUpdatesEnabled(False)
        try:
            self._active_section_id = section_id
            self._detail_stack.setCurrentWidget(page)
            self._scroll_area = self._detail_scroll
            self._scroll_content = self._section_contents[section_id]
            self._detail_geometry.set_active_widget(page)
            self._sync_current_section_geometry()
            # Every section shares the same scroll area.  A section switch
            # must not inherit the previous page's offset, otherwise the new
            # page opens with its header and first controls clipped.
            self._detail_scroll.verticalScrollBar().setValue(0)
        finally:
            self._detail_shell.setUpdatesEnabled(True)
            self._detail_scroll.setUpdatesEnabled(True)

    def _sync_current_section_geometry(self) -> None:
        self._detail_geometry.sync_now(self._detail_stack.currentWidget())


__all__ = ["SectionShellPresenterMixin"]
