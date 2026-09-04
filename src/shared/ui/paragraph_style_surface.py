"""Reusable paragraph-style control surface for template and scene owners."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.config.style_field_descriptors import (
    style_field_group_descriptor,
    style_field_layout_rows,
)
from src.config.template import StyleConfig
from src.qt_api import QSizePolicy, QVBoxLayout, QWidget, Signal
from src.shared.ui.card import Card
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.paragraph_style_editor import ParagraphStyleEditor
from src.shared.ui.template_form_layout import compact_form_column_gap, template_form_row
from src.shared.ui.theme import bind_theme, get_theme


STYLE_CONTROL_SURFACE_GROUPS: tuple[str, ...] = (
    "text",
    "alignment_indent",
    "spacing",
)


@dataclass(frozen=True, slots=True)
class StyleControlSurfaceState:
    """Owner-facing state applied to a shared paragraph-style surface."""

    owner_kind: str = ""
    active_label: str = ""
    source_label: str = ""
    detail: str = ""
    editable: bool = True
    style: StyleConfig | None = None
    readonly_reason: str = ""


class StyleControlSurface(QWidget):
    """Shared paragraph-style sections used by template and scene panes."""

    style_changed = Signal()

    def __init__(
        self,
        parent=None,
        *,
        object_name_prefix: str = "paragraph_style",
        groups: Sequence[str] = STYLE_CONTROL_SURFACE_GROUPS,
    ) -> None:
        super().__init__(parent)
        self._groups = tuple(str(group or "").strip() for group in groups if str(group or "").strip())
        self._cards: dict[str, Card] = {}
        self._forms: dict[str, InspectorForm] = {}
        self._state = StyleControlSurfaceState()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._editor = ParagraphStyleEditor(
            self,
            object_name_prefix=object_name_prefix,
            build_layout=False,
        )
        self._editor.style_changed.connect(self.style_changed.emit)

        for group_id in self._groups:
            card = Card(parent=self)
            group = style_field_group_descriptor(group_id)
            title = group.label if group is not None else group_id
            icon_name = group.icon_name if group is not None else None
            title_label = card.set_header(title, icon_name=icon_name)
            title_label.setObjectName("style_surface_card_title")

            form = InspectorForm(parent=card)
            self._add_style_layout_grid(group_id, form)
            card.add_widget(form)

            self._cards[group_id] = card
            self._forms[group_id] = form
            layout.addWidget(card)

        bind_theme(self, self._apply_theme)
        self._apply_theme()

    @property
    def editor(self) -> ParagraphStyleEditor:
        return self._editor

    @property
    def text_card(self) -> Card | None:
        return self._cards.get("text")

    @property
    def alignment_indent_card(self) -> Card | None:
        return self._cards.get("alignment_indent")

    @property
    def spacing_card(self) -> Card | None:
        return self._cards.get("spacing")

    @property
    def text_form(self) -> InspectorForm | None:
        return self._forms.get("text")

    @property
    def alignment_indent_form(self) -> InspectorForm | None:
        return self._forms.get("alignment_indent")

    @property
    def spacing_form(self) -> InspectorForm | None:
        return self._forms.get("spacing")

    def card_for_group(self, group_id: str) -> Card | None:
        return self._cards.get(str(group_id or "").strip())

    def form_for_group(self, group_id: str) -> InspectorForm | None:
        return self._forms.get(str(group_id or "").strip())

    def state(self) -> StyleControlSurfaceState:
        return self._state

    def apply_state(self, state: StyleControlSurfaceState) -> None:
        self._state = state
        self.setProperty("style_surface_owner_kind", state.owner_kind)
        self.setProperty("style_surface_active_label", state.active_label)
        self.setProperty("style_surface_source_label", state.source_label)
        self.setProperty("style_surface_detail", state.detail)
        self.setProperty("style_surface_editable", bool(state.editable))
        self.setProperty(
            "style_surface_readonly_reason",
            "" if state.editable else state.readonly_reason,
        )
        self.set_style(state.style)
        self.set_editable(state.editable and state.style is not None)

    def set_style(self, style: StyleConfig | None) -> None:
        self._editor.set_style(style)

    def apply_to_style(self, style: StyleConfig) -> None:
        self._editor.apply_to_style(style)

    def set_editable(self, enabled: bool) -> None:
        self._editor.set_editable(enabled)

    def widget_for_field(self, field_id: str) -> QWidget | None:
        return self._editor.widget_for_field(field_id)

    def widget_for_layout_item(self, item_id: str) -> QWidget | None:
        return self._editor.widget_for_layout_item(item_id)

    def _add_style_layout_grid(self, group_id: str, form: InspectorForm) -> None:
        grid: list[list[QWidget]] = []
        for row_items in style_field_layout_rows(group_id):
            row: list[QWidget] = []
            for item in row_items:
                widget = self.widget_for_layout_item(item.item_id)
                if widget is None:
                    raise KeyError(f"Unknown paragraph style layout item: {item.item_id}")
                row.append(
                    template_form_row(
                        item.label,
                        widget,
                        suffix_widget=(
                            self._editor.line_value_suffix
                            if item.item_id == "line_spacing_pt"
                            else None
                        ),
                        parent=form,
                    )
                )
            if row:
                grid.append(row)

        form.add_grid(
            grid,
            column_gap=(
                compact_form_column_gap()
                if group_id in {"alignment_indent", "spacing"}
                else None
            ),
            align_trailing_labels=(
                True if group_id in {"alignment_indent", "spacing"} else None
            ),
            stack_slack=32 if group_id in {"alignment_indent", "spacing"} else 0,
        )

    def _apply_theme(self) -> None:
        layout = self.layout()
        if layout is not None:
            layout.setSpacing(get_theme().template_detail_section_gap)


__all__ = [
    "STYLE_CONTROL_SURFACE_GROUPS",
    "StyleControlSurface",
    "StyleControlSurfaceState",
]
