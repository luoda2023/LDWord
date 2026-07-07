"""Reusable style-management block for template and scene style panes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.qt_api import QSizePolicy, QVBoxLayout, QWidget, Signal
from src.shared.ui.style_editing_section import StyleEditingSection
from src.shared.ui.style_object_projection import StyleObjectProjection
from src.shared.ui.style_owner_toolbar import StyleOwnerOption
from src.shared.ui.style_policy_control_deck import style_policy_control_protocol
from src.shared.ui.summary_grid import SummaryGridItem
from src.shared.ui.template_summary_card import DetailSummaryCard
from src.shared.ui.layout_sync import refresh_layout_chain, refresh_layout_chain_later
from src.shared.ui.theme import bind_theme, get_theme


@dataclass(frozen=True, slots=True)
class StyleManagementContract:
    """Named interaction contract for shared style-management panes."""

    mode: str = "custom"
    show_owner_toolbar: bool = True
    owner_title: str = "编辑样式"
    selector_label: str = "编辑对象"
    action_label: str = "恢复"
    show_owner_status: bool = True
    show_preview: bool = True
    collapse_surface_when_readonly: bool = False


@dataclass(frozen=True, slots=True)
class StyleManagementContentPlan:
    """Semantic content sections expected in a shared style-management pane."""

    mode: str = "custom"
    source: bool = True
    scope: bool = True
    rules: bool = False
    difference: bool = False
    editor: bool = True
    preview: bool = True
    receipt: bool = False

    def sections(self) -> tuple[str, ...]:
        return tuple(
            name
            for name, enabled in (
                ("source", self.source),
                ("scope", self.scope),
                ("rules", self.rules),
                ("difference", self.difference),
                ("editor", self.editor),
                ("preview", self.preview),
                ("receipt", self.receipt),
            )
            if enabled
        )

    def slots(self) -> tuple[str, ...]:
        """Return user-facing semantic slots, with policy as the public rule name."""

        return tuple("policy" if name == "rules" else name for name in self.sections())

    def encoded(self) -> str:
        return "|".join(self.sections())

    def encoded_slots(self) -> str:
        return "|".join(self.slots())

    @property
    def policy(self) -> bool:
        return self.rules

    def with_effective_slots(
        self,
        *,
        source: bool | None = None,
        scope: bool | None = None,
        rules: bool | None = None,
        difference: bool | None = None,
        preview: bool | None = None,
        receipt: bool | None = None,
    ) -> "StyleManagementContentPlan":
        return StyleManagementContentPlan(
            mode=self.mode,
            source=self.source if source is None else bool(source),
            scope=self.scope if scope is None else bool(scope),
            rules=self.rules if rules is None else bool(rules),
            difference=self.difference if difference is None else bool(difference),
            editor=self.editor,
            preview=self.preview if preview is None else bool(preview),
            receipt=self.receipt if receipt is None else bool(receipt),
        )


STYLE_MANAGEMENT_CONTRACTS: dict[str, StyleManagementContract] = {
    "custom": StyleManagementContract(mode="custom"),
    "template_baseline_edit": StyleManagementContract(
        mode="template_baseline_edit",
        show_owner_toolbar=False,
        owner_title="模板样式",
        selector_label="编辑对象",
        action_label="恢复",
        show_owner_status=False,
        show_preview=False,
        collapse_surface_when_readonly=False,
    ),
    "scene_section_rules": StyleManagementContract(
        mode="scene_section_rules",
        show_owner_toolbar=True,
        owner_title="编辑样式",
        selector_label="编辑分区",
        action_label="恢复模板",
        show_owner_status=True,
        show_preview=True,
        collapse_surface_when_readonly=True,
    ),
    "template_overview_preview": StyleManagementContract(
        mode="template_overview_preview",
        show_owner_toolbar=False,
        owner_title="样式预览",
        selector_label="",
        action_label="",
        show_owner_status=False,
        show_preview=False,
        collapse_surface_when_readonly=True,
    ),
    "execution_receipt_review": StyleManagementContract(
        mode="execution_receipt_review",
        show_owner_toolbar=False,
        owner_title="样式回执",
        selector_label="",
        action_label="",
        show_owner_status=False,
        show_preview=False,
        collapse_surface_when_readonly=True,
    ),
    "execution_prereview": StyleManagementContract(
        mode="execution_prereview",
        show_owner_toolbar=False,
        owner_title="执行前复核",
        selector_label="",
        action_label="",
        show_owner_status=False,
        show_preview=False,
        collapse_surface_when_readonly=True,
    ),
    "readonly_review": StyleManagementContract(
        mode="readonly_review",
        show_owner_toolbar=False,
        owner_title="样式复核",
        selector_label="复核对象",
        action_label="",
        show_owner_status=True,
        show_preview=True,
        collapse_surface_when_readonly=True,
    ),
}


STYLE_MANAGEMENT_CONTENT_PLANS: dict[str, StyleManagementContentPlan] = {
    "custom": StyleManagementContentPlan(mode="custom"),
    "template_baseline_edit": StyleManagementContentPlan(
        mode="template_baseline_edit",
        source=True,
        scope=True,
        rules=False,
        difference=False,
        editor=True,
        preview=False,
        receipt=False,
    ),
    "scene_section_rules": StyleManagementContentPlan(
        mode="scene_section_rules",
        source=True,
        scope=True,
        rules=True,
        difference=True,
        editor=True,
        preview=True,
        receipt=False,
    ),
    "template_overview_preview": StyleManagementContentPlan(
        mode="template_overview_preview",
        source=False,
        scope=False,
        rules=False,
        difference=False,
        editor=False,
        preview=True,
        receipt=False,
    ),
    "execution_receipt_review": StyleManagementContentPlan(
        mode="execution_receipt_review",
        source=False,
        scope=False,
        rules=False,
        difference=False,
        editor=False,
        preview=False,
        receipt=True,
    ),
    "execution_prereview": StyleManagementContentPlan(
        mode="execution_prereview",
        source=True,
        scope=True,
        rules=False,
        difference=True,
        editor=False,
        preview=False,
        receipt=False,
    ),
    "readonly_review": StyleManagementContentPlan(
        mode="readonly_review",
        source=True,
        scope=True,
        rules=False,
        difference=False,
        editor=False,
        preview=True,
        receipt=True,
    ),
}


def style_management_contract(mode: str) -> StyleManagementContract:
    """Return a stable contract for a style-management use case."""

    normalized = str(mode or "custom").strip()
    return STYLE_MANAGEMENT_CONTRACTS.get(
        normalized,
        STYLE_MANAGEMENT_CONTRACTS["custom"],
    )


def style_management_content_plan(mode: str) -> StyleManagementContentPlan:
    """Return the semantic content sections expected for a style-management mode."""

    normalized = str(mode or "custom").strip()
    return STYLE_MANAGEMENT_CONTENT_PLANS.get(
        normalized,
        STYLE_MANAGEMENT_CONTENT_PLANS["custom"],
    )


def style_preview_slot_protocol(widget: QWidget | None) -> str:
    """Return the preview protocol implemented by a preview slot widget."""

    if widget is None:
        return "none"
    if callable(getattr(widget, "apply_preview_projection", None)):
        return "preview_projection"
    if callable(getattr(widget, "apply_envelope", None)):
        return "envelope"
    return "unsupported"


class StyleManagementBlock(QWidget):
    """Shared page-level structure for summary, owner controls, preview, and fields."""

    current_key_changed = Signal(str)
    action_requested = Signal()
    style_changed = Signal()

    def __init__(
        self,
        parent=None,
        *,
        title: str,
        icon_name: str = "type-outline",
        object_name_prefix: str = "style_management",
        mode: str = "custom",
        contract: StyleManagementContract | None = None,
        content_plan: StyleManagementContentPlan | None = None,
        summary_items: Sequence[SummaryGridItem] = (),
        summary_columns: int = 12,
        source_slot: QWidget | None = None,
        scope_slot: QWidget | None = None,
        rule_control: QWidget | None = None,
        difference_slot: QWidget | None = None,
        preview_slot: QWidget | None = None,
        receipt_slot: QWidget | None = None,
        management_widgets: Sequence[QWidget] = (),
        owner_options: Sequence[StyleOwnerOption] = (),
        show_owner_toolbar: bool | None = None,
        owner_title: str | None = None,
        selector_label: str | None = None,
        action_label: str | None = None,
        show_owner_status: bool | None = None,
        show_preview: bool | None = None,
        preview_object_name: str | None = None,
        collapse_surface_when_readonly: bool | None = None,
        surface_object_name_prefix: str | None = None,
        compact_header: bool = False,
        show_summary: bool = True,
    ) -> None:
        super().__init__(parent)
        prefix = str(object_name_prefix or "style_management").strip()
        base_contract = contract or style_management_contract(mode)
        effective_show_owner_toolbar = (
            base_contract.show_owner_toolbar
            if show_owner_toolbar is None
            else bool(show_owner_toolbar)
        )
        effective_owner_title = (
            base_contract.owner_title
            if owner_title is None
            else str(owner_title or "")
        )
        effective_selector_label = (
            base_contract.selector_label
            if selector_label is None
            else str(selector_label or "")
        )
        effective_action_label = (
            base_contract.action_label
            if action_label is None
            else str(action_label or "")
        )
        effective_show_owner_status = (
            base_contract.show_owner_status
            if show_owner_status is None
            else bool(show_owner_status)
        )
        effective_show_preview = (
            base_contract.show_preview
            if show_preview is None
            else bool(show_preview)
        )
        effective_collapse_surface = (
            base_contract.collapse_surface_when_readonly
            if collapse_surface_when_readonly is None
            else bool(collapse_surface_when_readonly)
        )
        self._contract = StyleManagementContract(
            mode=base_contract.mode,
            show_owner_toolbar=effective_show_owner_toolbar,
            owner_title=effective_owner_title,
            selector_label=effective_selector_label,
            action_label=effective_action_label,
            show_owner_status=effective_show_owner_status,
            show_preview=effective_show_preview,
            collapse_surface_when_readonly=effective_collapse_surface,
        )
        base_content_plan = content_plan or style_management_content_plan(
            base_contract.mode
        )
        self._content_plan = base_content_plan.with_effective_slots(
            source=bool(base_content_plan.source or source_slot is not None),
            scope=bool(base_content_plan.scope or scope_slot is not None),
            rules=bool(base_content_plan.rules or rule_control is not None),
            difference=bool(base_content_plan.difference or difference_slot is not None),
            preview=bool(effective_show_preview or preview_slot is not None),
            receipt=bool(base_content_plan.receipt or receipt_slot is not None),
        )
        self._legacy_management_widgets = tuple(management_widgets)
        self._show_summary = bool(show_summary)
        self._collapse_surface_when_readonly = effective_collapse_surface
        self._editor_enabled = bool(self._content_plan.editor)
        self._rule_control_protocol = style_policy_control_protocol(rule_control)
        if rule_control is not None and self._rule_control_protocol == "unsupported":
            raise TypeError(
                "rule_control must implement apply_projection(...)."
            )
        self._preview_slot_protocol = style_preview_slot_protocol(preview_slot)
        if preview_slot is not None and self._preview_slot_protocol == "unsupported":
            raise TypeError(
                "preview_slot must implement apply_preview_projection(...) "
                "or apply_envelope(...)."
            )
        self.setObjectName(f"{prefix}_block")
        self.setProperty("style_management_mode", self._contract.mode)
        self._sync_content_plan_properties()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)

        self._card = DetailSummaryCard(
            title,
            icon_name,
            columns=summary_columns,
            compact_header=compact_header,
            parent=self,
        )
        self._card.setObjectName(f"{prefix}_summary_card")
        self._summary = self._card.summary_grid
        self._summary.setObjectName(f"{prefix}_summary")
        self._set_summary_items(tuple(summary_items))
        self._source_slot = source_slot
        self._scope_slot = scope_slot
        self._rule_control = rule_control
        self._difference_slot = difference_slot
        self._preview_slot = preview_slot
        self._receipt_slot = receipt_slot
        self._sync_content_plan_properties()

        self._add_slot_widget(source_slot)
        if scope_slot is not source_slot:
            self._add_slot_widget(scope_slot)

        if rule_control is not None:
            self._card.add_widget(rule_control)

        if (
            difference_slot is not None
            and difference_slot is not rule_control
            and not self._slot_is_descendant_of(difference_slot, rule_control)
        ):
            self._card.add_widget(difference_slot)

        if preview_slot is not None:
            self._card.add_widget(preview_slot)

        if receipt_slot is not None:
            self._card.add_widget(receipt_slot)

        for widget in self._legacy_management_widgets:
            self._card.add_widget(widget)

        self._editing_section = StyleEditingSection(
            self,
            object_name_prefix=prefix,
            owner_options=tuple(owner_options),
            show_owner_toolbar=effective_show_owner_toolbar,
            owner_title=effective_owner_title,
            selector_label=effective_selector_label,
            action_label=effective_action_label,
            show_owner_status=effective_show_owner_status,
            show_preview=effective_show_preview,
            preview_object_name=preview_object_name,
            chrome_parent=self._card,
            embed_chrome=False,
            surface_object_name_prefix=surface_object_name_prefix,
        )
        self._editing_section.current_key_changed.connect(
            self.current_key_changed.emit
        )
        self._editing_section.action_requested.connect(self.action_requested.emit)
        self._editing_section.style_changed.connect(self.style_changed.emit)
        self._set_editor_surface_visible(self._editor_enabled)
        self._sync_content_plan_properties()

        if (
            effective_show_owner_status
            or effective_show_owner_toolbar
            or effective_show_preview
        ):
            self._card.add_widget(self._editing_section.chrome_widget)

        layout.addWidget(self._card)
        if self._editor_enabled:
            layout.addWidget(self._editing_section)
        else:
            self._editing_section.setVisible(False)

        bind_theme(self, self.apply_theme)
        self.apply_theme()

    @property
    def card(self) -> DetailSummaryCard:
        return self._card

    @property
    def summary(self):
        return self._summary

    @property
    def source_slot(self) -> QWidget | None:
        return self._source_slot

    @property
    def scope_slot(self) -> QWidget | None:
        return self._scope_slot

    @property
    def rule_control(self) -> QWidget | None:
        return self._rule_control

    @property
    def difference_slot(self) -> QWidget | None:
        return self._difference_slot

    @property
    def preview_slot(self) -> QWidget | None:
        return self._preview_slot

    @property
    def effective_preview_slot(self) -> QWidget | None:
        preview_slot = getattr(self, "_preview_slot", None)
        if preview_slot is not None:
            return preview_slot
        editing_section = getattr(self, "_editing_section", None)
        if editing_section is None:
            return None
        return editing_section.preview_surface

    @property
    def receipt_slot(self) -> QWidget | None:
        return self._receipt_slot

    @property
    def legacy_management_widgets(self) -> tuple[QWidget, ...]:
        return self._legacy_management_widgets

    @property
    def contract(self) -> StyleManagementContract:
        return self._contract

    @property
    def content_plan(self) -> StyleManagementContentPlan:
        return self._content_plan

    @property
    def editing_section(self) -> StyleEditingSection:
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
    def action_button(self):
        return self._editing_section.action_button

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

    def add_action(self, widget: QWidget) -> None:
        self._card.add_action(widget)

    def add_control(self, widget: QWidget) -> None:
        self._card.add_control(widget)

    def set_summary_items(self, items: Sequence[SummaryGridItem]) -> None:
        self._set_summary_items(tuple(items))

    def _set_summary_items(self, items: Sequence[SummaryGridItem]) -> None:
        normalized_items = tuple(items)
        if self._show_summary:
            self._card.set_summary_items(normalized_items)
            return
        self._summary.set_items(normalized_items)
        self._summary.setVisible(False)

    def set_current_key(self, key: str) -> bool:
        return self._editing_section.set_current_key(key)

    def current_key(self) -> str:
        return self._editing_section.current_key()

    def apply_preview_projection(
        self,
        projection,
        *,
        empty_text: str = "",
        envelope=None,
    ) -> None:
        self._editing_section.apply_preview_projection(
            projection,
            empty_text=empty_text,
            envelope=envelope,
        )

    def apply_owner_state(self, owner_state) -> None:
        self._editing_section.apply_owner_state(owner_state)
        if self._collapse_surface_when_readonly:
            state = owner_state.surface_state
            editable = bool(state.editable and state.style is not None)
            self._set_editor_surface_visible(editable)
            refresh_layout_chain(self)
            refresh_layout_chain_later(self)

    def apply_style_object_projection(self, projection) -> None:
        """Apply a unified style-object projection to the shared block."""

        style_object = StyleObjectProjection.from_object(projection)
        self.setProperty("style_object_kind", style_object.kind)
        self.setProperty("style_object_label", style_object.object_label)
        self.setProperty("style_object_source_label", style_object.source_label)
        self.setProperty("style_object_scope_label", style_object.scope_label)
        self.setProperty("style_object_edit_state_label", style_object.edit_state_label)

        if style_object.summary_items:
            self.set_summary_items(style_object.summary_items)
        if style_object.owner_state is not None:
            self.apply_owner_state(style_object.owner_state)
        if style_object.source is not None:
            self._apply_slot_projection(self._source_slot, style_object.source)
        if self._difference_slot is not None:
            self._apply_slot_method(
                self._difference_slot,
                "apply_projection",
                style_object.difference,
            )
        if style_object.policy is not None:
            self._apply_rule_control_projection(style_object.policy)
        if (
            style_object.preview_projection is not None
            or not style_object.preview.is_empty()
            or style_object.empty_preview_text
        ):
            self._apply_preview_slot(
                style_object.preview_projection,
                envelope=style_object.preview,
                empty_text=style_object.empty_preview_text,
            )
            self.apply_preview_projection(
                style_object.preview_projection,
                empty_text=style_object.empty_preview_text,
                envelope=style_object.preview,
            )
        elif self.preview is not None:
            self.apply_preview_projection(
                None,
                empty_text=style_object.empty_preview_text,
            )
        if self._receipt_slot is not None:
            self._apply_slot_method(
                self._receipt_slot,
                "apply_envelope",
                style_object.receipt,
            )

    def apply_theme(self) -> None:
        layout = self.layout()
        if layout is not None:
            layout.setSpacing(get_theme().template_detail_section_gap)
        self._editing_section.apply_theme()

    def _add_slot_widget(self, widget: QWidget | None) -> None:
        if widget is not None:
            self._card.add_widget(widget)

    @staticmethod
    def _apply_slot_method(widget: QWidget | None, method_name: str, value) -> None:
        method = getattr(widget, method_name, None)
        if callable(method):
            method(value)

    @classmethod
    def _apply_slot_projection(cls, widget: QWidget | None, value) -> None:
        if widget is None:
            return
        method = getattr(widget, "apply_projection", None)
        if callable(method):
            method(value)
            return
        for child in widget.findChildren(QWidget):
            method = getattr(child, "apply_projection", None)
            if callable(method):
                method(value)
                return

    def _apply_preview_slot(self, projection, *, envelope=None, empty_text: str = "") -> None:
        if self._preview_slot is None:
            return
        self._preview_slot_protocol = style_preview_slot_protocol(self._preview_slot)
        self._sync_content_plan_properties()
        if self._preview_slot_protocol == "preview_projection":
            method = getattr(self._preview_slot, "apply_preview_projection")
            method(projection, envelope=envelope, empty_text=empty_text)
            return
        if self._preview_slot_protocol == "envelope":
            method = getattr(self._preview_slot, "apply_envelope")
            method(envelope)

    def _apply_rule_control_projection(self, projection) -> None:
        if self._rule_control is None:
            return
        self._rule_control_protocol = style_policy_control_protocol(self._rule_control)
        self._sync_content_plan_properties()
        if self._rule_control_protocol == "policy_projection":
            self._rule_control.apply_projection(projection)

    def _set_editor_surface_visible(self, visible: bool) -> None:
        editor_visible = bool(self._editor_enabled and visible)
        self._editing_section.style_surface.setVisible(editor_visible)
        self.setProperty("style_management_editor_available", self._editor_enabled)
        self.setProperty("style_management_editor_visible", editor_visible)
        self.setProperty(
            "style_management_editor_collapsed",
            bool(self._editor_enabled and not editor_visible),
        )
        self.setProperty(
            "style_management_editor_collapsed_by_readonly",
            bool(
                self._collapse_surface_when_readonly
                and self._editor_enabled
                and not editor_visible
            ),
        )

    @staticmethod
    def _slot_is_descendant_of(widget: QWidget | None, ancestor: QWidget | None) -> bool:
        if widget is None or ancestor is None:
            return False
        current = widget.parentWidget()
        while current is not None:
            if current is ancestor:
                return True
            current = current.parentWidget()
        return False

    def _sync_content_plan_properties(self) -> None:
        self.setProperty("style_management_content_plan", self._content_plan.encoded())
        self.setProperty(
            "style_management_slot_plan",
            self._content_plan.encoded_slots(),
        )
        self.setProperty(
            "style_management_has_legacy_widgets",
            bool(self._legacy_management_widgets),
        )
        self.setProperty(
            "style_management_rule_control_protocol",
            self._rule_control_protocol,
        )
        self.setProperty(
            "style_management_rule_control_ready",
            self._rule_control_protocol == "policy_projection",
        )
        self.setProperty(
            "style_management_policy_control_protocol",
            self._rule_control_protocol,
        )
        self.setProperty(
            "style_management_policy_control_ready",
            self._rule_control_protocol == "policy_projection",
        )
        self.setProperty(
            "style_management_preview_slot_protocol",
            self._preview_slot_protocol,
        )
        self.setProperty(
            "style_management_preview_slot_ready",
            self._preview_slot_protocol in {"preview_projection", "envelope"},
        )
        effective_preview_protocol = style_preview_slot_protocol(
            self.effective_preview_slot
        )
        self.setProperty(
            "style_management_effective_preview_protocol",
            effective_preview_protocol,
        )
        self.setProperty(
            "style_management_effective_preview_ready",
            effective_preview_protocol in {"preview_projection", "envelope"},
        )
        for slot_name in (
            "source",
            "scope",
            "policy",
            "difference",
            "preview",
            "receipt",
        ):
            slot_attr = "_rule_control" if slot_name == "policy" else f"_{slot_name}_slot"
            self.setProperty(
                f"style_management_has_{slot_name}_slot",
                getattr(self, slot_attr, None) is not None,
            )
        for section in (
            "source",
            "scope",
            "rules",
            "difference",
            "editor",
            "preview",
            "receipt",
        ):
            self.setProperty(
                f"style_management_has_{section}",
                section in self._content_plan.sections(),
            )
        self.setProperty(
            "style_management_has_policy",
            "policy" in self._content_plan.slots(),
        )


__all__ = [
    "STYLE_MANAGEMENT_CONTENT_PLANS",
    "STYLE_MANAGEMENT_CONTRACTS",
    "StyleManagementBlock",
    "StyleManagementContentPlan",
    "StyleManagementContract",
    "style_management_content_plan",
    "style_management_contract",
    "style_preview_slot_protocol",
]
