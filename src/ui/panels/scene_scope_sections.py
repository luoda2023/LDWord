"""Scene processing-scope section widgets."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from src.qt_api import QVBoxLayout, QSizePolicy, QWidget, Signal
from src.shared.ui.card import Card
from src.shared.ui.scope_zone_checklist import ScopeZoneChecklist, ScopeZoneOption
from src.shared.ui.segmented_control import SegmentedControl
from src.shared.ui.summary_grid import SummaryGrid, SummaryGridItem


SCENE_SCOPE_ZONE_SECTION_TITLE = "处理范围"
SCENE_SCOPE_ZONE_SECTION_DESCRIPTION = ""
SCENE_APPLICATION_BOUNDARY_MODE_OPTIONS = (
    ("follow_template", "按模板默认"),
    ("body_only", "只处理正文"),
    ("full_document", "处理全文"),
    ("confirm_before_apply", "每次执行前选择"),
)


class SceneScopeZoneSection(QWidget):
    """Card-level section for scene application boundary."""

    zone_changed = Signal(str, bool)
    boundary_mode_changed = Signal(str)

    def __init__(
        self,
        parent=None,
        *,
        title: str = SCENE_SCOPE_ZONE_SECTION_TITLE,
        description: str = SCENE_SCOPE_ZONE_SECTION_DESCRIPTION,
        summary_items: Sequence[SummaryGridItem] = (),
        zone_labels: Mapping[str, str] | None = None,
        zone_options: Sequence[ScopeZoneOption] = (),
        object_name_prefix: str = "scn_scope_zone_checklist",
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._card = Card(parent=self)
        self._card.set_header(title, icon_name="crosshair")
        self._description_label = (
            self._card.set_description(description) if description else None
        )

        self._summary = SummaryGrid(columns=2, parent=self._card)
        self._summary.set_items(tuple(summary_items))
        self._summary.setVisible(False)

        self._boundary_mode_control = SegmentedControl(parent=self._card)
        self._boundary_mode_control.setObjectName(
            f"{object_name_prefix}_boundary_mode"
        )
        self._boundary_modes = tuple(SCENE_APPLICATION_BOUNDARY_MODE_OPTIONS)
        for mode, label in self._boundary_modes:
            self._boundary_mode_control.add_segment(label, mode)
        self._boundary_mode_control.current_changed.connect(
            self._on_boundary_mode_changed
        )
        self._card.add_widget(self._boundary_mode_control)

        self._checklist = ScopeZoneChecklist(
            self._card,
            object_name_prefix=object_name_prefix,
        )
        options = tuple(zone_options) or tuple(
            ScopeZoneOption(zone_id, label)
            for zone_id, label in (zone_labels or {}).items()
        )
        self._checklist.set_options(options)
        self._checklist.checked_changed.connect(self._on_zone_checked)
        self._card.add_widget(self._checklist)
        self._checklist.setVisible(False)

        layout.addWidget(self._card)

    @property
    def card(self) -> Card:
        return self._card

    @property
    def summary(self) -> SummaryGrid:
        return self._summary

    @property
    def checklist(self) -> ScopeZoneChecklist:
        return self._checklist

    @property
    def boundary_mode_control(self) -> SegmentedControl:
        return self._boundary_mode_control

    @property
    def checks(self):
        return self._checklist.checks

    def set_summary_items(self, items: Sequence[SummaryGridItem]) -> None:
        self._summary.set_items(tuple(items))

    def set_zone_checked(self, zone_id: str, checked: bool) -> None:
        self._checklist.set_checked(zone_id, checked)

    def checked_states(self) -> dict[str, bool]:
        return {
            zone_id: checkbox.isChecked()
            for zone_id, checkbox in self._checklist.checks.items()
        }

    def set_boundary_mode(self, mode: str) -> None:
        normalized = str(mode or "").strip() or "follow_template"
        for index, (candidate, _label) in enumerate(self._boundary_modes):
            if candidate == normalized:
                self._boundary_mode_control.set_current_index(index)
                return
        self._boundary_mode_control.set_current_index(0)

    def boundary_mode(self) -> str:
        value = self._boundary_mode_control.current_data()
        return str(value or "follow_template")

    def apply_theme(self) -> None:
        self._checklist.apply_theme()

    def _on_zone_checked(self, zone_id: str, checked: bool) -> None:
        self.zone_changed.emit(zone_id, bool(checked))

    def _on_boundary_mode_changed(self, *_args) -> None:
        self.boundary_mode_changed.emit(self.boundary_mode())


__all__ = [
    "SCENE_APPLICATION_BOUNDARY_MODE_OPTIONS",
    "SCENE_SCOPE_ZONE_SECTION_DESCRIPTION",
    "SCENE_SCOPE_ZONE_SECTION_TITLE",
    "SceneScopeZoneSection",
]
