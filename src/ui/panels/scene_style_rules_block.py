"""Stable scene style-rules block boundary."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from src.qt_api import QSizePolicy, QVBoxLayout, QWidget, Signal
from src.shared.ui.summary_grid import SummaryGridItem
from src.ui.panels.scene_style_override_sections import SceneStyleOverrideSection


class StyleVariantLike(Protocol):
    key: str
    label: str


class SceneStyleRulesBlock(QWidget):
    """Object-level wrapper for scene section style rules."""

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
        summary_items: Sequence[SummaryGridItem] = (),
        style_variants: Sequence[StyleVariantLike] = (),
        object_name_prefix: str = "scn_section_style",
    ) -> None:
        super().__init__(parent)
        self.setObjectName(f"{object_name_prefix}_rules_block")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._section = SceneStyleOverrideSection(
            self,
            summary_items=tuple(summary_items),
            style_variants=tuple(style_variants),
            object_name_prefix=object_name_prefix,
        )
        self._section.policy_toggled.connect(self.policy_toggled.emit)
        self._section.override_toggled.connect(self.override_toggled.emit)
        self._section.current_variant_changed.connect(
            self.current_variant_changed.emit
        )
        self._section.restore_requested.connect(self.restore_requested.emit)
        self._section.restore_all_requested.connect(self.restore_all_requested.emit)
        self._section.undo_restore_all_requested.connect(
            self.undo_restore_all_requested.emit
        )
        self._section.style_changed.connect(self.style_changed.emit)
        layout.addWidget(self._section)

    @property
    def section(self) -> SceneStyleOverrideSection:
        return self._section

    @property
    def card(self):
        return self._section.card

    @property
    def summary(self):
        return self._section.summary

    @property
    def management_block(self):
        return self._section.management_block

    @property
    def rule_control_deck(self):
        return self._section.rule_control_deck

    @property
    def toggle_list(self):
        return self._section.toggle_list

    @property
    def toggles(self):
        return self._section.toggles

    @property
    def rows(self):
        return self._section.rows

    @property
    def comparison_strip(self):
        return self._section.comparison_strip

    @property
    def editing_section(self):
        return self._section.editing_section

    @property
    def owner_toolbar(self):
        return self._section.owner_toolbar

    @property
    def owner_status(self):
        return self._section.owner_status

    @property
    def selector(self):
        return self._section.selector

    @property
    def restore_button(self):
        return self._section.restore_button

    @property
    def restore_all_button(self):
        return self._section.restore_all_button

    @property
    def undo_restore_all_button(self):
        return self._section.undo_restore_all_button

    @property
    def hint_label(self):
        return self._section.hint_label

    @property
    def preview(self):
        return self._section.preview

    @property
    def style_surface(self):
        return self._section.style_surface

    @property
    def editor(self):
        return self._section.editor

    @property
    def unit_labels(self):
        return self._section.unit_labels

    def set_summary_items(self, items: Sequence[SummaryGridItem]) -> None:
        self._section.set_summary_items(tuple(items))

    def set_style_variants(self, style_variants: Sequence[StyleVariantLike]) -> None:
        self._section.set_style_variants(tuple(style_variants))

    def set_policy_row_visible(self, policy_key: str, visible: bool) -> None:
        self._section.set_policy_row_visible(policy_key, visible)

    def set_override_row_visible(self, variant_key: str, visible: bool) -> None:
        self.set_policy_row_visible(variant_key, visible)

    def set_policy_checked(self, policy_key: str, checked: bool) -> bool:
        return self._section.set_policy_checked(policy_key, checked)

    def set_override_checked(self, variant_key: str, checked: bool) -> bool:
        return self.set_policy_checked(variant_key, checked)

    def has_policy_key(self, policy_key: str) -> bool:
        return str(policy_key or "").strip() in self.toggles

    def has_variant(self, variant_key: str) -> bool:
        return self.has_policy_key(variant_key)

    def policy_toggle_for_key(self, policy_key: str) -> QWidget | None:
        return self.toggles.get(str(policy_key or "").strip())

    def override_toggle_for_variant(self, variant_key: str) -> QWidget | None:
        return self.policy_toggle_for_key(variant_key)

    def editor_widget_for_field(self, field_id: str) -> QWidget | None:
        target = str(field_id or "").strip()
        if not target:
            return None
        return self.editor.widget_for_field(target)

    def navigation_widget_for_field(
        self,
        field_id: str,
        *,
        variant_key: str = "",
        prefer_toggle: bool = False,
        prefer_toggle_when_unchecked: bool = False,
    ) -> QWidget | None:
        toggle = self.policy_toggle_for_key(variant_key)
        if toggle is not None:
            if prefer_toggle or (
                prefer_toggle_when_unchecked and not toggle.isChecked()
            ):
                return toggle
        widget = self.editor_widget_for_field(field_id)
        if widget is not None:
            return widget
        return toggle

    def set_editor_editable(self, enabled: bool) -> None:
        self.editor.set_editable(bool(enabled))

    def apply_editor_to_style(self, style) -> None:
        self.editor.apply_to_style(style)

    def set_editor_values(self, **values) -> None:
        self.editor.set_values(**values)

    def set_current_variant(self, variant_key: str) -> bool:
        return self._section.set_current_variant(variant_key)

    def current_variant_key(self) -> str:
        return self._section.current_variant_key()

    def set_current_policy_key(self, policy_key: str) -> bool:
        return self._section.set_current_policy_key(policy_key)

    def current_policy_key(self) -> str:
        return self._section.current_policy_key()

    def apply_preview_projection(self, projection) -> None:
        self._section.apply_preview_projection(projection)

    def apply_comparison_projection(self, projection) -> None:
        self._section.apply_comparison_projection(projection)

    def set_restore_all_enabled(
        self,
        enabled: bool,
        labels: Sequence[str] = (),
    ) -> None:
        self._section.set_restore_all_enabled(enabled, labels)

    def set_undo_restore_all_enabled(
        self,
        enabled: bool,
        labels: Sequence[str] = (),
    ) -> None:
        self._section.set_undo_restore_all_enabled(enabled, labels)

    def apply_owner_state(self, owner_state) -> None:
        self._section.apply_owner_state(owner_state)

    def apply_style_object_projection(self, projection) -> None:
        self._section.apply_style_object_projection(projection)

    def apply_theme(self) -> None:
        self._section.apply_theme()


__all__ = ["SceneStyleRulesBlock"]
