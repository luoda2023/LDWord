"""Immutable effective-module selection shared by every runtime and preview."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.modules.base import BaseModule


class ModuleDisposition(str, Enum):
    """Why a registered module will or will not run."""

    ENABLED = "enabled"
    DISABLED_BY_PLAN = "disabled_by_plan"
    AUTO_PRUNED = "auto_pruned"


@dataclass(frozen=True, slots=True)
class ModuleDecision:
    module_name: str
    requested_enabled: bool
    disposition: ModuleDisposition
    unmet_dependencies: tuple[str, ...] = ()

    @property
    def effectively_enabled(self) -> bool:
        return self.disposition is ModuleDisposition.ENABLED


@dataclass(frozen=True, slots=True)
class ModuleSelectionPlan:
    """Dependency-closed module decisions in registry order."""

    decisions: tuple[ModuleDecision, ...]
    ordered_enabled_names: tuple[str, ...]

    def decision_for(self, module_name: str) -> ModuleDecision:
        target = str(module_name or "")
        for decision in self.decisions:
            if decision.module_name == target:
                return decision
        raise KeyError(f"Unknown module: {target}")

    def is_effectively_enabled(self, module_name: str) -> bool:
        try:
            return self.decision_for(module_name).effectively_enabled
        except KeyError:
            return False

    @property
    def auto_pruned(self) -> tuple[ModuleDecision, ...]:
        return tuple(
            decision
            for decision in self.decisions
            if decision.disposition is ModuleDisposition.AUTO_PRUNED
        )

    @property
    def disabled_by_plan(self) -> tuple[ModuleDecision, ...]:
        return tuple(
            decision
            for decision in self.decisions
            if decision.disposition is ModuleDisposition.DISABLED_BY_PLAN
        )

    def select_modules(
        self,
        modules: Sequence[BaseModule],
    ) -> tuple[BaseModule, ...]:
        enabled = frozenset(self.ordered_enabled_names)
        selected = tuple(
            module for module in modules if module.meta.name in enabled
        )
        selected_names = tuple(module.meta.name for module in selected)
        if selected_names != self.ordered_enabled_names:
            raise ValueError(
                "Module registry does not match the selection plan: "
                f"expected {self.ordered_enabled_names}, got {selected_names}"
            )
        return selected


def build_module_selection_plan(
    modules: Sequence[BaseModule],
    is_requested: Callable[[str], bool],
) -> ModuleSelectionPlan:
    """Respect requested switches and prune unmet hard dependencies to closure."""

    ordered_modules = tuple(modules)
    names = tuple(module.meta.name for module in ordered_modules)
    if len(set(names)) != len(names):
        duplicates = sorted({name for name in names if names.count(name) > 1})
        raise ValueError(
            "Duplicate module names in registry: " + ", ".join(duplicates)
        )

    requested = {
        module.meta.name: bool(is_requested(module.meta.name))
        for module in ordered_modules
    }
    selected = {
        module.meta.name: module
        for module in ordered_modules
        if requested[module.meta.name]
    }
    unmet_by_name: dict[str, tuple[str, ...]] = {}

    changed = True
    while changed:
        changed = False
        for name, module in tuple(selected.items()):
            unmet = tuple(
                sorted(
                    dependency
                    for dependency in module.meta.depends_on
                    if dependency not in selected
                )
            )
            if not unmet:
                continue
            unmet_by_name[name] = unmet
            selected.pop(name)
            changed = True

    decisions: list[ModuleDecision] = []
    for name in names:
        if name in selected:
            disposition = ModuleDisposition.ENABLED
        elif requested[name]:
            disposition = ModuleDisposition.AUTO_PRUNED
        else:
            disposition = ModuleDisposition.DISABLED_BY_PLAN
        decisions.append(
            ModuleDecision(
                module_name=name,
                requested_enabled=requested[name],
                disposition=disposition,
                unmet_dependencies=unmet_by_name.get(name, ()),
            )
        )

    return ModuleSelectionPlan(
        decisions=tuple(decisions),
        ordered_enabled_names=tuple(name for name in names if name in selected),
    )


__all__ = [
    "ModuleDecision",
    "ModuleDisposition",
    "ModuleSelectionPlan",
    "build_module_selection_plan",
]
