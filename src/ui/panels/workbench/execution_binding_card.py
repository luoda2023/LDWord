from __future__ import annotations

from src.qt_api import QVBoxLayout, QWidget, Signal
from src.shared.ui.theme import get_theme


class ExecutionBindingCard(QWidget):
    """Stable host for the workbench's single plan/template selector.

    The existing quick-execution selector remains the compatibility adapter
    during the migration, but it is physically owned and rendered here.
    """

    binding_changed = Signal(object, str)

    def __init__(self, binding_owner, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("wb_execution_binding_card_host")
        self._binding_owner = binding_owner
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)

        card = binding_owner._scene_card
        owner_layout = getattr(binding_owner, "_layout", None)
        if owner_layout is not None:
            owner_layout.removeWidget(card)
        card.setParent(self)
        layout.addWidget(card)
        self._card = card

        binding_owner.binding_changed.connect(self.binding_changed.emit)

    def current_template_id(self) -> str:
        return str(self._binding_owner.current_template_id() or "").strip()

    def current_scene(self):
        return self._binding_owner.current_scene()

    def set_work_mode(self, mode_id: str) -> None:
        self._binding_owner.set_work_mode(mode_id)

    def set_scene_context(self, scene) -> None:
        self._binding_owner.set_scene_context(scene)

    def set_template_context(self, template) -> None:
        self._binding_owner.set_template_context(template)

    def set_strategy_context(self, **kwargs) -> None:
        self._binding_owner.set_strategy_context(**kwargs)


__all__ = ["ExecutionBindingCard"]
