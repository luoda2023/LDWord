"""Compact scene-module controls for template detail headers.

Execution participation is projected directly from ``ModuleSelectionPlan``.
It deliberately does not depend on template-preview models; preview is a
downstream representation, not the owner of execution state.
"""

from __future__ import annotations

from src.pipeline.module_selection import ModuleDisposition, ModuleSelectionPlan
from src.qt_api import QHBoxLayout, QLabel, QWidget, Signal, Qt
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch
from src.ui.panels.template_feature_specs import TemplateFeatureSpec


class CompactModuleControls(QWidget):
    """One compact independent switch per module, placed in a detail header."""

    participation_changed = Signal(str, bool)

    def __init__(self, feature: TemplateFeatureSpec, parent=None) -> None:
        super().__init__(parent)
        self.feature_id = feature.feature_id
        self._syncing = False
        self._controls = feature.module_controls
        self._toggles: dict[str, ToggleSwitch] = {}
        self._labels: dict[str, QLabel] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().spacing_sm)

        for control in feature.module_controls:
            label = QLabel(control.label, self)
            label.setAlignment(Qt.AlignVCenter)
            layout.addWidget(label, 0, Qt.AlignVCenter)
            self._labels[control.module_name] = label
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
                    decision = selection.decision_for(control.module_name)
                    toggle.set_checked(decision.requested_enabled, animate=False)
                    toggle.setEnabled(True)
                    if decision.disposition is ModuleDisposition.AUTO_PRUNED:
                        unmet = "、".join(decision.unmet_dependencies)
                        tooltip = f"{control.label}：已请求，但依赖未满足"
                        if unmet:
                            tooltip += f"（{unmet}）"
                    elif decision.effectively_enabled:
                        tooltip = f"{control.label}：本次执行"
                    else:
                        tooltip = f"{control.label}：本次跳过"
                toggle.setToolTip(tooltip)
                toggle.setAccessibleDescription(tooltip)
                label = self._labels.get(control.module_name)
                if label is not None:
                    label.setToolTip(tooltip)
        finally:
            self._syncing = False

    def _on_toggled(self, module_name: str, checked: bool) -> None:
        if not self._syncing:
            self.participation_changed.emit(module_name, bool(checked))

    def _apply_theme(self) -> None:
        theme = get_theme()
        layout = self.layout()
        if layout is not None:
            layout.setSpacing(theme.spacing_sm)
        for label in self._labels.values():
            label.setStyleSheet(
                f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary}; "
                "background: transparent;"
            )
        for toggle in self._toggles.values():
            toggle.set_checked_track_color(theme.primary)


__all__ = ["CompactModuleControls"]
