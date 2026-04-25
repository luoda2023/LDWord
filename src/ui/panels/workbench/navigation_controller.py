from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.shared.ui import NavigationCard

if TYPE_CHECKING:
    from src.shared.ui import DynamicNavigationRail
    from .config_management_detail import ConfigManagementDetail
    from .quick_execution_detail import QuickExecutionDetail
    from .state import StrategySummaryState


class WorkbenchNavigationController:
    """Encapsulate workbench navigation-card creation and snapshot refresh."""

    DYNAMIC_SECTION_TITLE = "高级功能"

    def __init__(
        self,
        nav_rail: "DynamicNavigationRail",
        quick_execution_detail: "QuickExecutionDetail",
        config_management_detail: "ConfigManagementDetail",
        *,
        card_definitions: dict[str, tuple[str, str]],
        feature_card_order: tuple[str, ...],
    ) -> None:
        self._nav_rail = nav_rail
        self._quick_execution_detail = quick_execution_detail
        self._config_management_detail = config_management_detail
        self._card_definitions = dict(card_definitions)
        self._feature_card_order = tuple(feature_card_order)
        self.navigation_cards: dict[str, NavigationCard] = {}
        self.dynamic_cards: set[str] = set()
        self.dynamic_section_header = None

    def add_fixed_cards(self) -> None:
        self.add_navigation_card("quick_execute")
        self.add_navigation_card("config_management")

    def add_navigation_card(self, card_id: str) -> NavigationCard:
        title, icon_name = self._card_definitions.get(card_id, (card_id, ""))
        card = NavigationCard(card_id, title, icon_name=icon_name, parent=self._nav_rail)
        self.navigation_cards[card_id] = card
        self._nav_rail.add_card(card_id, card)
        return card

    def update_navigation_card(self, card_id: str, snapshot: dict[str, str]) -> None:
        card = self.navigation_cards.get(card_id)
        if card is None:
            return
        card.set_subtitle(snapshot.get("subtitle", ""))
        card.set_badge(snapshot.get("badge_text", ""), snapshot.get("badge_variant", "neutral"))

    def build_quick_execute_snapshot(
        self,
        *,
        cached_document_path: str,
        strategy_state: "StrategySummaryState",
        execution_worker,
    ) -> dict[str, str]:
        fallback = self._quick_execution_detail.navigation_snapshot()
        document_label = Path(cached_document_path).name if cached_document_path else "未选择文档"
        strategy_name = strategy_state.name if strategy_state.source_type == "scene" else strategy_state.template_label
        strategy_name = str(strategy_name or "").strip() or fallback.get("subtitle", "")
        if execution_worker is not None:
            badge_text = "执行中"
            badge_variant = "info"
        else:
            badge_text = fallback.get("badge_text", "")
            badge_variant = fallback.get("badge_variant", "neutral")
        return {
            "subtitle": f"{document_label} · {strategy_name or '未绑定模板'}",
            "badge_text": badge_text,
            "badge_variant": badge_variant,
        }

    def build_config_management_snapshot(
        self,
        *,
        strategy_state: "StrategySummaryState",
        scene_dirty: bool,
        template_dirty: bool,
    ) -> dict[str, str]:
        fallback = self._config_management_detail.navigation_snapshot()
        if scene_dirty or template_dirty:
            return fallback
        if strategy_state.source_type == "scene":
            subtitle = f"{strategy_state.name} · {strategy_state.enabled_module_count} 个模块"
            badge_text = "场景"
            badge_variant = "success"
        elif strategy_state.source_type == "template":
            subtitle = strategy_state.template_label
            badge_text = "模板"
            badge_variant = "neutral"
        else:
            return fallback
        return {
            "subtitle": subtitle,
            "badge_text": badge_text,
            "badge_variant": badge_variant,
        }

    def refresh_quick_execute_card(self, *, cached_document_path: str, strategy_state: "StrategySummaryState", execution_worker) -> None:
        self.update_navigation_card(
            "quick_execute",
            self.build_quick_execute_snapshot(
                cached_document_path=cached_document_path,
                strategy_state=strategy_state,
                execution_worker=execution_worker,
            ),
        )

    def refresh_config_management_card(self, *, strategy_state: "StrategySummaryState", scene_dirty: bool, template_dirty: bool) -> None:
        self.update_navigation_card(
            "config_management",
            self.build_config_management_snapshot(
                strategy_state=strategy_state,
                scene_dirty=scene_dirty,
                template_dirty=template_dirty,
            ),
        )

    def refresh_fixed_cards(self, *, cached_document_path: str, strategy_state: "StrategySummaryState", execution_worker, scene_dirty: bool, template_dirty: bool) -> None:
        self.refresh_quick_execute_card(
            cached_document_path=cached_document_path,
            strategy_state=strategy_state,
            execution_worker=execution_worker,
        )
        self.refresh_config_management_card(
            strategy_state=strategy_state,
            scene_dirty=scene_dirty,
            template_dirty=template_dirty,
        )

    def sync_dynamic_cards(self) -> None:
        selected_card_id = self._nav_rail.selected_card_id()

        if self.dynamic_section_header is not None:
            self.dynamic_section_header.setParent(None)
            self.dynamic_section_header.deleteLater()
            self.dynamic_section_header = None
        for feature_id in list(self.dynamic_cards):
            self._nav_rail.remove_card(feature_id)
            self.navigation_cards.pop(feature_id, None)
        self.dynamic_cards.clear()

        enabled = self._quick_execution_detail.enabled_features()
        has_features = any(fid in enabled for fid in self._feature_card_order)

        if has_features:
            self.dynamic_section_header = self._nav_rail.add_section_header(self.DYNAMIC_SECTION_TITLE)

        for feature_id in self._feature_card_order:
            if feature_id not in enabled:
                continue
            card = self.add_navigation_card(feature_id)
            snapshot = self._quick_execution_detail.feature_navigation_snapshot(feature_id)
            card.set_subtitle(snapshot.get("subtitle", ""))
            card.set_badge(snapshot.get("badge_text", ""), snapshot.get("badge_variant", "neutral"))
            self.dynamic_cards.add(feature_id)

        if selected_card_id in self.navigation_cards:
            self._nav_rail.select_card(selected_card_id)

    def open_feature_card(self, feature_id: str) -> None:
        if feature_id in self.navigation_cards:
            self._nav_rail.select_card(feature_id)
