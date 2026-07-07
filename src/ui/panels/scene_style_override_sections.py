"""Scene style-override section widgets."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from src.qt_api import QVBoxLayout, QSizePolicy, QWidget, Signal
from src.shared.ui.style_management_block import StyleManagementBlock
from src.shared.ui.style_owner_toolbar import StyleOwnerOption
from src.shared.ui.style_rule_control_deck import StyleRuleControlDeck
from src.shared.ui.style_policy_toggle_list import (
    StylePolicyToggleList,
    StylePolicyToggleOption,
)
from src.shared.ui.summary_grid import SummaryGrid, SummaryGridItem


SCENE_STYLE_OVERRIDE_SECTION_TITLE = "分区样式"


class StyleVariantLike(Protocol):
    key: str
    label: str


class SceneStyleOverrideSection(QWidget):
    """Card-level section for scene-specific paragraph style overrides."""

    policy_toggled = Signal(str, bool)
    override_toggled = Signal(str, bool)
    current_variant_changed = Signal(str)
    restore_requested = Signal()
    restore_all_requested = Signal()
    undo_restore_all_requested = Signal()
    style_changed = Signal()

    def __init__(
        self,
        parent=None,
        *,
        title: str = SCENE_STYLE_OVERRIDE_SECTION_TITLE,
        summary_items: Sequence[SummaryGridItem] = (),
        style_variants: Sequence[StyleVariantLike] = (),
        object_name_prefix: str = "scn_section_style",
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._rule_control_deck = StyleRuleControlDeck(
            self,
            toggle_options=tuple(
                StylePolicyToggleOption(
                    variant.key,
                    variant.label,
                    f"为「{variant.label}」添加格式例外",
                )
                for variant in style_variants
            ),
            object_name_prefix=object_name_prefix,
            toggle_title="分区",
        )
        self._rule_control_deck.policy_toggled.connect(self.policy_toggled.emit)
        self._rule_control_deck.override_toggled.connect(self.override_toggled.emit)
        self._rule_control_deck.restore_all_requested.connect(
            self.restore_all_requested.emit
        )
        self._rule_control_deck.undo_restore_all_requested.connect(
            self.undo_restore_all_requested.emit
        )

        self._style_management_block = StyleManagementBlock(
            self,
            title=title,
            icon_name="type-outline",
            object_name_prefix=object_name_prefix,
            mode="scene_section_rules",
            summary_items=tuple(summary_items),
            rule_control=self._rule_control_deck,
            difference_slot=self._rule_control_deck.difference_slot,
            owner_options=tuple(
                StyleOwnerOption(variant.key, variant.label)
                for variant in style_variants
            ),
            show_summary=False,
            show_owner_status=True,
            owner_title="当前分区",
            selector_label="分区",
            preview_object_name="scn_section_style_preview",
            compact_header=True,
        )
        self._style_management_block.add_action(
            self._rule_control_deck.restore_all_button
        )
        self._style_management_block.add_action(
            self._rule_control_deck.undo_restore_all_button
        )

        self._card = self._style_management_block.card
        self._summary = self._style_management_block.summary
        self._editing_section = self._style_management_block.editing_section
        if self._editing_section.owner_status is not None:
            self._editing_section.owner_status.setVisible(False)
            self._editing_section.owner_status.setMinimumHeight(0)
            self._editing_section.owner_status.setMaximumHeight(0)
            self._editing_section.owner_status.updateGeometry()
        self._editing_section.current_key_changed.connect(
            self._on_current_variant_changed
        )
        self._editing_section.action_requested.connect(self.restore_requested.emit)
        self._editing_section.style_changed.connect(self.style_changed.emit)
        assert self._editing_section.action_button is not None
        self._editing_section.action_button.setObjectName(
            "scn_section_style_restore_template"
        )
        self._editing_section.action_button.setToolTip(
            "关闭当前分区的独立样式，重新跟随模板"
        )
        layout.addWidget(self._style_management_block)
        self._sync_current_policy_key(self.current_variant_key())

    @property
    def card(self):
        return self._card

    @property
    def summary(self) -> SummaryGrid:
        return self._summary

    @property
    def management_block(self) -> StyleManagementBlock:
        return self._style_management_block

    @property
    def rule_control_deck(self) -> StyleRuleControlDeck:
        return self._rule_control_deck

    @property
    def toggle_list(self) -> StylePolicyToggleList:
        return self._rule_control_deck.toggle_list

    @property
    def toggles(self):
        return self._rule_control_deck.toggles

    @property
    def rows(self):
        return self._rule_control_deck.rows

    @property
    def toggle_labels(self):
        return self._rule_control_deck.toggle_labels

    @property
    def comparison_strip(self):
        return self._rule_control_deck.comparison_strip

    @property
    def difference_slot(self):
        return self._rule_control_deck.difference_slot

    @property
    def editing_section(self):
        return self._editing_section

    @property
    def owner_toolbar(self):
        return self._editing_section.owner_toolbar

    @property
    def owner_status(self):
        return self._editing_section.owner_status

    @property
    def selector(self):
        return self._editing_section.selector

    @property
    def restore_button(self):
        return self._editing_section.action_button

    @property
    def restore_all_button(self):
        return self._rule_control_deck.restore_all_button

    @property
    def undo_restore_all_button(self):
        return self._rule_control_deck.undo_restore_all_button

    @property
    def hint_label(self):
        return self._editing_section.hint_label

    @property
    def preview(self):
        return self._editing_section.preview

    @property
    def style_surface(self):
        return self._editing_section.style_surface

    @property
    def editor(self):
        return self._editing_section.editor

    @property
    def unit_labels(self):
        return self._editing_section.unit_labels

    def set_summary_items(self, items: Sequence[SummaryGridItem]) -> None:
        self._style_management_block.set_summary_items(tuple(items))

    def set_style_variants(self, style_variants: Sequence[StyleVariantLike]) -> None:
        self._editing_section.set_owner_options(
            tuple(
                StyleOwnerOption(variant.key, variant.label)
                for variant in style_variants
            )
        )

    def set_policy_row_visible(self, policy_key: str, visible: bool) -> None:
        self._rule_control_deck.set_policy_row_visible(policy_key, visible)

    def set_override_row_visible(self, variant_key: str, visible: bool) -> None:
        self.set_policy_row_visible(variant_key, visible)

    def set_policy_checked(self, policy_key: str, checked: bool) -> bool:
        return self._rule_control_deck.set_policy_checked(policy_key, checked)

    def has_policy_key(self, policy_key: str) -> bool:
        return self._rule_control_deck.has_policy_key(policy_key)

    def policy_toggle_for_key(self, policy_key: str) -> QWidget | None:
        return self._rule_control_deck.policy_toggle_for_key(policy_key)

    def set_current_variant(self, variant_key: str) -> bool:
        changed = self._editing_section.set_current_key(variant_key)
        if changed:
            self._sync_current_policy_key(variant_key)
        return changed

    def current_variant_key(self) -> str:
        return self._editing_section.current_key()

    def set_current_policy_key(self, policy_key: str) -> bool:
        changed = self._rule_control_deck.set_current_policy_key(policy_key)
        if changed and str(policy_key or "").strip():
            self._editing_section.set_current_key(policy_key)
        return changed

    def current_policy_key(self) -> str:
        return self._rule_control_deck.current_policy_key()

    def apply_preview_projection(self, projection) -> None:
        self._editing_section.apply_preview_projection(
            projection,
            empty_text="选择分区后预览样式",
        )

    def apply_comparison_projection(self, projection) -> None:
        self._rule_control_deck.apply_comparison_projection(projection)

    def set_restore_all_enabled(
        self,
        enabled: bool,
        labels: Sequence[str] = (),
    ) -> None:
        self._rule_control_deck.set_restore_all_enabled(enabled, labels)

    def set_undo_restore_all_enabled(
        self,
        enabled: bool,
        labels: Sequence[str] = (),
    ) -> None:
        self._rule_control_deck.set_undo_restore_all_enabled(enabled, labels)

    def apply_owner_state(self, owner_state) -> None:
        self._style_management_block.apply_owner_state(owner_state)

    def apply_style_object_projection(self, projection) -> None:
        self._style_management_block.apply_style_object_projection(projection)

    def apply_theme(self) -> None:
        self._rule_control_deck.apply_theme()
        self._style_management_block.apply_theme()

    def _on_current_variant_changed(self, variant_key: str) -> None:
        target = str(variant_key or "").strip()
        self._sync_current_policy_key(target)
        self.current_variant_changed.emit(target)

    def _sync_current_policy_key(self, variant_key: str) -> bool:
        return self._rule_control_deck.set_current_policy_key(variant_key)


__all__ = [
    "SCENE_STYLE_OVERRIDE_SECTION_TITLE",
    "SceneStyleOverrideSection",
]
