"""Compact scene-module controls for template detail headers.

Execution participation is projected directly from ``ModuleSelectionPlan``.
It deliberately does not depend on template-preview models; preview is a
downstream representation, not the owner of execution state.
"""

from __future__ import annotations

from src.pipeline.module_selection import ModuleDisposition, ModuleSelectionPlan
from src.qt_api import QHBoxLayout, QWidget, Signal, Qt
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch
from src.ui.panels.template_feature_specs import TemplateFeatureSpec


class CompactModuleControls(QWidget):
    """Compact feature controls projected from one or more backend modules."""

    participation_changed = Signal(str, bool)

    def __init__(self, feature: TemplateFeatureSpec, parent=None) -> None:
        super().__init__(parent)
        self.feature_id = feature.feature_id
        self._syncing = False
        self._controls = feature.module_controls
        self._toggles: dict[str, ToggleSwitch] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for control in feature.module_controls:
            toggle = ToggleSwitch(self, checked=False)
            toggle.setObjectName(f"template_module_{control.module_name}")
            toggle.setAccessibleName(control.label)
            toggle.toggled_signal.connect(
                lambda checked, name=control.module_name: self._on_toggled(name, checked)
            )
            layout.addWidget(toggle, 0, Qt.AlignVCenter)
            self._toggles[control.module_name] = toggle

        self.hide()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    @property
    def toggles(self) -> dict[str, ToggleSwitch]:
        return self._toggles

    def apply_selection(
        self,
        selection: ModuleSelectionPlan | None,
        *,
        has_scene: bool,
    ) -> None:
        self.setVisible(bool(has_scene and self._toggles))
        self._syncing = True
        try:
            for control in self._controls:
                toggle = self._toggles[control.module_name]
                if not has_scene or selection is None:
                    toggle.set_checked(False, animate=False)
                    toggle.setEnabled(False)
                    tooltip = f"{control.label}：当前未绑定方案"
                else:
                    decisions = tuple(
                        selection.decision_for(module_name)
                        for module_name in control.module_names
                    )
                    requested = any(
                        decision.requested_enabled for decision in decisions
                    )
                    effective = tuple(
                        decision
                        for decision in decisions
                        if decision.effectively_enabled
                    )
                    pruned = tuple(
                        decision
                        for decision in decisions
                        if decision.disposition is ModuleDisposition.AUTO_PRUNED
                    )
                    toggle.set_checked(requested, animate=False)
                    toggle.setEnabled(True)
                    if pruned:
                        unmet = "、".join(
                            dict.fromkeys(
                                dependency
                                for decision in pruned
                                for dependency in decision.unmet_dependencies
                            )
                        )
                        if effective:
                            tooltip = f"{control.label}：本次部分执行"
                        else:
                            tooltip = f"{control.label}：已请求，但依赖未满足"
                        if unmet:
                            tooltip += f"（{unmet}）"
                    elif len(effective) == len(decisions):
                        tooltip = f"{control.label}：本次执行"
                    elif effective:
                        tooltip = f"{control.label}：本次部分执行"
                    else:
                        tooltip = f"{control.label}：本次跳过"
                toggle.setToolTip(tooltip)
                toggle.setAccessibleDescription(tooltip)
        finally:
            self._syncing = False

    def _on_toggled(self, module_name: str, checked: bool) -> None:
        if not self._syncing:
            self.participation_changed.emit(module_name, bool(checked))

    def _apply_theme(self) -> None:
        theme = get_theme()
        layout = self.layout()
        if layout is not None:
            layout.setSpacing(0)
        for toggle in self._toggles.values():
            toggle.set_checked_track_color(theme.primary)


__all__ = ["CompactModuleControls"]
