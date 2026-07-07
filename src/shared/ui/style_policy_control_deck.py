"""Shared policy-control deck for style-management rules."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.qt_api import QPushButton, QSizePolicy, QVBoxLayout, QWidget, Signal
from src.shared.ui.layout_sync import refresh_layout_chain, updates_suspended
from src.shared.ui.style_comparison_strip import StyleComparisonStrip
from src.shared.ui.style_difference_summary_slot import StyleDifferenceSummarySlot
from src.shared.ui.style_policy_toggle_list import (
    StylePolicyToggleList,
    StylePolicyToggleOption,
)
from src.shared.ui.template_summary_card import apply_detail_summary_action_button


def style_policy_control_protocol(widget: QWidget | None) -> str:
    """Return the policy-control protocol implemented by a rule-control widget."""

    if widget is None:
        return "none"
    if callable(getattr(widget, "apply_projection", None)):
        return "policy_projection"
    return "unsupported"


@dataclass(frozen=True, slots=True)
class StylePolicyToggleProjection:
    key: str = ""
    label: str = ""
    checked: bool = False
    visible: bool = True
    tooltip: str = ""

    @classmethod
    def from_object(cls, value) -> "StylePolicyToggleProjection":
        if isinstance(value, cls):
            return value
        return cls(
            key=_clean(getattr(value, "key", "")),
            label=_clean(getattr(value, "label", "")),
            checked=bool(getattr(value, "checked", False)),
            visible=bool(getattr(value, "visible", True)),
            tooltip=_clean(getattr(value, "tooltip", "")),
        )


@dataclass(frozen=True, slots=True)
class StylePolicyActionProjection:
    label: str = ""
    enabled: bool = False
    labels: tuple[str, ...] = ()
    tooltip: str = ""

    @classmethod
    def from_object(cls, value) -> "StylePolicyActionProjection":
        if isinstance(value, cls):
            return value
        if value is None:
            return cls()
        return cls(
            label=_clean(getattr(value, "label", "")),
            enabled=bool(getattr(value, "enabled", False)),
            labels=_clean_names(getattr(value, "labels", ()) or ()),
            tooltip=_clean(getattr(value, "tooltip", "")),
        )


@dataclass(frozen=True, slots=True)
class StylePolicyProjection:
    kind: str = ""
    title: str = ""
    toggles: tuple[StylePolicyToggleProjection, ...] = ()
    difference: object | None = None
    restore_all: StylePolicyActionProjection = StylePolicyActionProjection()
    undo_restore_all: StylePolicyActionProjection = StylePolicyActionProjection()

    @classmethod
    def from_object(cls, value) -> "StylePolicyProjection":
        if isinstance(value, cls):
            return value
        if value is None:
            return cls()
        toggles = tuple(
            StylePolicyToggleProjection.from_object(item)
            for item in (getattr(value, "toggles", ()) or ())
        )
        return cls(
            kind=_clean(getattr(value, "kind", "")),
            title=_clean(getattr(value, "title", "")),
            toggles=toggles,
            difference=getattr(value, "difference", None),
            restore_all=StylePolicyActionProjection.from_object(
                getattr(value, "restore_all", None)
            ),
            undo_restore_all=StylePolicyActionProjection.from_object(
                getattr(value, "undo_restore_all", None)
            ),
        )


class StylePolicyControlDeck(QWidget):
    """Bundle style policy toggles, difference summary, and batch actions."""

    policy_toggled = Signal(str, bool)
    policy_selected = Signal(str)
    override_toggled = Signal(str, bool)
    restore_all_requested = Signal()
    undo_restore_all_requested = Signal()

    def __init__(
        self,
        parent=None,
        *,
        toggle_options: Sequence[StylePolicyToggleOption] = (),
        object_name_prefix: str = "style_policy_control",
        object_name_suffix: str = "policy_control_deck",
        toggle_title: str = "策略",
        restore_all_label: str = "全部恢复",
        restore_all_disabled_tooltip: str = "暂无可恢复项",
        restore_all_enabled_tooltip: str = "恢复全部策略",
        restore_all_enabled_labels_prefix: str = "将恢复：",
        undo_restore_all_label: str = "撤销恢复",
        undo_restore_all_disabled_tooltip: str = "暂无可撤销的恢复",
        undo_restore_all_enabled_tooltip: str = "恢复上次策略",
        undo_restore_all_enabled_labels_prefix: str = "恢复：",
        show_difference: bool = True,
        read_only: bool = False,
        read_only_tooltip: str = "只读复核：请到对应设置页调整。",
    ) -> None:
        super().__init__(parent)
        prefix = str(object_name_prefix or "style_policy_control").strip()
        suffix = str(object_name_suffix or "policy_control_deck").strip()
        self._show_difference = bool(show_difference)
        self._read_only = bool(read_only)
        self._read_only_tooltip = str(read_only_tooltip or "")
        self._restore_all_disabled_tooltip = str(restore_all_disabled_tooltip or "")
        self._restore_all_enabled_tooltip = str(restore_all_enabled_tooltip or "")
        self._restore_all_enabled_labels_prefix = str(
            restore_all_enabled_labels_prefix or ""
        )
        self._undo_restore_all_disabled_tooltip = str(
            undo_restore_all_disabled_tooltip or ""
        )
        self._undo_restore_all_enabled_tooltip = str(
            undo_restore_all_enabled_tooltip or ""
        )
        self._undo_restore_all_enabled_labels_prefix = str(
            undo_restore_all_enabled_labels_prefix or ""
        )
        self.setObjectName(f"{prefix}_{suffix}")
        self.setProperty("style_policy_control_deck", True)
        self.setProperty("style_policy_show_difference", self._show_difference)
        self.setProperty("style_policy_control_read_only", self._read_only)
        self.setProperty("style_policy_current_key", "")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._toggle_list = StylePolicyToggleList(
            self,
            title=toggle_title,
            object_name_prefix=f"{prefix}_policy_list",
        )
        self._toggle_list.set_options(tuple(toggle_options))
        self._toggle_list.toggled.connect(self.policy_toggled.emit)
        self._toggle_list.toggled.connect(self.override_toggled.emit)
        self._toggle_list.activated.connect(self.policy_selected.emit)
        layout.addWidget(self._toggle_list)

        self._difference_slot = StyleDifferenceSummarySlot(
            self,
            object_name_prefix=prefix,
        )
        self._comparison_strip = self._difference_slot.comparison_strip
        self._difference_slot.setVisible(self._show_difference)
        layout.addWidget(self._difference_slot)

        self._restore_all_button = QPushButton(restore_all_label, self)
        self._restore_all_button.setObjectName(f"{prefix}_restore_all_template")
        self._restore_all_button.setEnabled(False)
        self._restore_all_button.setToolTip(self._restore_all_disabled_tooltip)
        self._restore_all_button.clicked.connect(self.restore_all_requested.emit)

        self._undo_restore_all_button = QPushButton(undo_restore_all_label, self)
        self._undo_restore_all_button.setObjectName(
            f"{prefix}_undo_restore_all_template"
        )
        self._undo_restore_all_button.setEnabled(False)
        self._undo_restore_all_button.setToolTip(
            self._undo_restore_all_disabled_tooltip
        )
        self._undo_restore_all_button.clicked.connect(
            self.undo_restore_all_requested.emit
        )

        self.apply_theme()
        self._sync_read_only_controls()

    @property
    def toggle_list(self) -> StylePolicyToggleList:
        return self._toggle_list

    @property
    def toggles(self):
        return self._toggle_list.toggles

    @property
    def rows(self):
        return self._toggle_list.rows

    @property
    def toggle_labels(self):
        return self._toggle_list.labels

    @property
    def comparison_strip(self) -> StyleComparisonStrip:
        return self._comparison_strip

    @property
    def difference_slot(self) -> StyleDifferenceSummarySlot:
        return self._difference_slot

    @property
    def restore_all_button(self) -> QPushButton:
        return self._restore_all_button

    @property
    def undo_restore_all_button(self) -> QPushButton:
        return self._undo_restore_all_button

    @property
    def show_difference(self) -> bool:
        return self._show_difference

    @property
    def read_only(self) -> bool:
        return self._read_only

    def is_read_only(self) -> bool:
        return self._read_only

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = bool(read_only)
        self.setProperty("style_policy_control_read_only", self._read_only)
        self._sync_read_only_controls()

    def has_policy_key(self, policy_key: str) -> bool:
        return _clean(policy_key) in self._toggle_list.toggles

    def policy_toggle_for_key(self, policy_key: str) -> QWidget | None:
        return self._toggle_list.toggles.get(_clean(policy_key))

    def activate_policy(self, policy_key: str) -> bool:
        return self._toggle_list.activate_policy(policy_key)

    def current_policy_key(self) -> str:
        return self._toggle_list.current_policy_key()

    def set_current_policy_key(self, policy_key: str) -> bool:
        changed = self._toggle_list.set_current_policy_key(policy_key)
        if changed:
            self.setProperty(
                "style_policy_current_key",
                self._toggle_list.current_policy_key(),
            )
        return changed

    def set_policy_row_visible(self, policy_key: str, visible: bool) -> None:
        row = self._toggle_list.rows.get(_clean(policy_key))
        if row is None:
            return
        with updates_suspended(row, self):
            self._toggle_list.set_row_visible(policy_key, visible)
            refresh_layout_chain(row)

    def set_override_row_visible(self, variant_key: str, visible: bool) -> None:
        self.set_policy_row_visible(variant_key, visible)

    def set_policy_checked(self, policy_key: str, checked: bool) -> bool:
        return self._set_toggle_checked(policy_key, checked)

    def apply_comparison_projection(self, projection) -> None:
        self._difference_slot.apply_projection(projection)

    def apply_projection(self, projection) -> None:
        policy = StylePolicyProjection.from_object(projection)
        self.setProperty("style_policy_kind", policy.kind)
        self.setProperty("style_policy_title", policy.title)
        self.setProperty("style_policy_toggle_count", len(policy.toggles))
        self.setProperty(
            "style_policy_checked_count",
            sum(1 for item in policy.toggles if item.checked),
        )
        if policy.title:
            self._toggle_list.title_label.setText(policy.title)
        self._ensure_toggle_options(policy.toggles)
        with updates_suspended(self):
            for item in policy.toggles:
                self._apply_toggle_projection(item)
            self.apply_comparison_projection(policy.difference)
            self._apply_action_projection(
                self._restore_all_button,
                policy.restore_all,
                self.set_restore_all_enabled,
            )
            self._apply_action_projection(
                self._undo_restore_all_button,
                policy.undo_restore_all,
                self.set_undo_restore_all_enabled,
            )
            self._sync_read_only_controls()
        refresh_layout_chain(self)

    def set_restore_all_enabled(
        self,
        enabled: bool,
        labels: Sequence[str] = (),
    ) -> None:
        names = _clean_names(labels)
        self._restore_all_button.setEnabled(bool(enabled) and not self._read_only)
        self._restore_all_button.setToolTip(
            self._read_only_tooltip
            if self._read_only
            else (
                self._restore_all_enabled_labels_prefix + "、".join(names)
                if enabled and names
                else (
                    self._restore_all_enabled_tooltip
                    if enabled
                    else self._restore_all_disabled_tooltip
                )
            )
        )

    def set_undo_restore_all_enabled(
        self,
        enabled: bool,
        labels: Sequence[str] = (),
    ) -> None:
        names = _clean_names(labels)
        self._undo_restore_all_button.setEnabled(bool(enabled) and not self._read_only)
        self._undo_restore_all_button.setToolTip(
            self._read_only_tooltip
            if self._read_only
            else (
                self._undo_restore_all_enabled_labels_prefix + "、".join(names)
                if enabled and names
                else (
                    self._undo_restore_all_enabled_tooltip
                    if enabled
                    else self._undo_restore_all_disabled_tooltip
                )
            )
        )

    def apply_theme(self) -> None:
        self._toggle_list.apply_theme()
        self._difference_slot.apply_theme()
        apply_detail_summary_action_button(
            self._restore_all_button,
            "ghost-primary",
        )
        apply_detail_summary_action_button(
            self._undo_restore_all_button,
            "ghost-primary",
        )

    def _ensure_toggle_options(
        self,
        toggles: tuple[StylePolicyToggleProjection, ...],
    ) -> None:
        if not toggles or self._toggle_list.rows:
            return
        self._toggle_list.set_options(
            tuple(
                StylePolicyToggleOption(item.key, item.label, item.tooltip)
                for item in toggles
                if item.key and item.label
            )
        )
        self._sync_read_only_controls()

    def _apply_toggle_projection(self, item: StylePolicyToggleProjection) -> None:
        key = _clean(item.key)
        if not key or key not in self._toggle_list.toggles:
            return
        self.set_policy_row_visible(key, item.visible)
        self.set_policy_checked(key, item.checked)

    def _set_toggle_checked(self, key: str, checked: bool) -> bool:
        normalized_key = _clean(key)
        toggle = self._toggle_list.toggles.get(normalized_key)
        if toggle is None:
            return False
        self._toggle_list.set_checked(normalized_key, bool(checked))
        return True

    @staticmethod
    def _apply_action_projection(button, action, setter) -> None:
        if action.label:
            button.setText(action.label)
        setter(action.enabled, action.labels)
        if action.tooltip:
            button.setToolTip(action.tooltip)

    def _sync_read_only_controls(self) -> None:
        for toggle in self._toggle_list.toggles.values():
            toggle.setEnabled(not self._read_only)
        if self._read_only:
            self._restore_all_button.setEnabled(False)
            self._undo_restore_all_button.setEnabled(False)
            if self._read_only_tooltip:
                self._restore_all_button.setToolTip(self._read_only_tooltip)
                self._undo_restore_all_button.setToolTip(self._read_only_tooltip)


def _clean(value) -> str:
    return " ".join(str(value or "").split())


def _clean_names(labels: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        str(label or "").strip() for label in labels if str(label or "").strip()
    )


__all__ = [
    "StylePolicyActionProjection",
    "StylePolicyControlDeck",
    "StylePolicyProjection",
    "StylePolicyToggleProjection",
    "style_policy_control_protocol",
]
