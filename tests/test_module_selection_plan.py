from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from src.pipeline.module_selection import (
    ModuleDisposition,
    build_module_selection_plan,
)


class _Module:
    def __init__(
        self,
        name: str,
        *,
        depends_on: tuple[str, ...] = (),
        soft_after: tuple[str, ...] = (),
        enabled_by_default: bool = True,
    ) -> None:
        self.meta = SimpleNamespace(
            name=name,
            depends_on=depends_on,
            soft_after=soft_after,
            enabled_by_default=enabled_by_default,
        )


def test_plan_distinguishes_requested_disabled_and_auto_pruned_modules():
    modules = (
        _Module("recognition"),
        _Module("numbering", depends_on=("recognition",)),
        _Module("toc", depends_on=("numbering",)),
        _Module("caption"),
    )
    requested = {
        "recognition": True,
        "numbering": False,
        "toc": True,
        "caption": False,
    }

    plan = build_module_selection_plan(modules, requested.__getitem__)

    assert plan.ordered_enabled_names == ("recognition",)
    assert plan.decision_for("numbering").disposition is ModuleDisposition.DISABLED_BY_PLAN
    toc = plan.decision_for("toc")
    assert toc.requested_enabled is True
    assert toc.disposition is ModuleDisposition.AUTO_PRUNED
    assert toc.unmet_dependencies == ("numbering",)
    assert plan.decision_for("caption").disposition is ModuleDisposition.DISABLED_BY_PLAN


def test_plan_prunes_hard_dependencies_until_dependency_closure():
    modules = (
        _Module("root"),
        _Module("middle", depends_on=("root",)),
        _Module("leaf", depends_on=("middle",)),
    )
    requested = {"root": False, "middle": True, "leaf": True}

    plan = build_module_selection_plan(modules, requested.__getitem__)

    assert plan.ordered_enabled_names == ()
    assert plan.decision_for("middle").unmet_dependencies == ("root",)
    assert plan.decision_for("leaf").unmet_dependencies == ("middle",)


def test_soft_ordering_dependency_does_not_prune_requested_module():
    modules = (
        _Module("optional_provider"),
        _Module("consumer", soft_after=("optional_provider",)),
    )
    requested = {"optional_provider": False, "consumer": True}

    plan = build_module_selection_plan(modules, requested.__getitem__)

    assert plan.ordered_enabled_names == ("consumer",)
    assert plan.decision_for("consumer").disposition is ModuleDisposition.ENABLED


def test_plan_selects_modules_in_registry_order_and_rejects_mismatch():
    modules = (_Module("one"), _Module("two"), _Module("three"))
    plan = build_module_selection_plan(
        modules,
        lambda name: name != "two",
    )

    assert plan.select_modules(modules) == (modules[0], modules[2])
    with pytest.raises(ValueError, match="does not match"):
        plan.select_modules(tuple(reversed(modules)))


def test_plan_rejects_duplicate_module_names():
    with pytest.raises(ValueError, match="Duplicate module names"):
        build_module_selection_plan(
            (_Module("duplicate"), _Module("duplicate")),
            lambda _name: True,
        )


def test_plan_and_decisions_are_immutable():
    plan = build_module_selection_plan((_Module("one"),), lambda _name: True)

    with pytest.raises(FrozenInstanceError):
        plan.ordered_enabled_names = ()
    with pytest.raises(FrozenInstanceError):
        plan.decisions[0].requested_enabled = False


def test_unknown_module_is_not_effectively_enabled():
    plan = build_module_selection_plan((_Module("one"),), lambda _name: True)

    assert plan.is_effectively_enabled("missing") is False
    with pytest.raises(KeyError, match="Unknown module"):
        plan.decision_for("missing")
