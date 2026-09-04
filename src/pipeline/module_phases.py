"""Map pipeline modules to the explicit phase graph.

Every registered module must have an explicit phase assignment. An unknown
module is not scheduled by guessing from its category or name. Declared hard dependencies and soft
ordering hints are projected into :class:`~src.pipeline.phases.PhaseGraph`
dependencies, while the phase graph supplies stable registration-order
tie-breaking and the top-level phase barriers.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

from src.pipeline.phases import Phase, PhaseGraph, PhaseStepMetadata


# This mapping is intentionally exhaustive rather than derived from
# ModuleMeta.category.  Category is a UI grouping and is not an execution
# contract (for example, md_cleanup belongs to Fill and validation is the sole
# FinalValidation step).
MODULE_PHASES: Mapping[str, Phase] = MappingProxyType(
    {
        # Fill
        "entity_fill": Phase.FILL,
        "source_fill": Phase.FILL,
        "placeholder_replace": Phase.FILL,
        "formula_convert": Phase.FILL,
        "md_cleanup": Phase.FILL,
        # Semantics
        "heading_recognition": Phase.SEMANTICS,
        "whitespace_normalize": Phase.SEMANTICS,
        "heading_numbering": Phase.SEMANTICS,
        "caption": Phase.SEMANTICS,
        "reference_format": Phase.SEMANTICS,
        "citation_link": Phase.SEMANTICS,
        # Format
        "page_setup": Phase.FORMAT,
        "section_format": Phase.FORMAT,
        "paragraph_style": Phase.FORMAT,
        "table_format": Phase.FORMAT,
        "figure_table_center": Phase.FORMAT,
        "chem_typography": Phase.FORMAT,
        "equation_table_format": Phase.FORMAT,
        "header_footer": Phase.FORMAT,
        "toc": Phase.FORMAT,
        "watermark": Phase.FORMAT,
        # Artifact staging and validation
        "image_insertion": Phase.STAGE_ARTIFACT,
        "validation": Phase.FINAL_VALIDATION,
    }
)


class ModuleScopeBehavior(str, Enum):
    """How one module relates to the reviewed logical-region boundary."""

    STRUCTURE_DISCOVERY = "structure_discovery"
    REGION_FILTERED = "region_filtered"
    DOCUMENT_LEVEL = "document_level"


# This mapping is intentionally exhaustive.  Content assembly and explicit
# artifact insertion remain document-level: choosing a formatting region must
# not leave template/material placeholders unresolved outside that region.
# Automatic semantic/format writers are region-filtered.
MODULE_SCOPE_BEHAVIORS: Mapping[str, ModuleScopeBehavior] = MappingProxyType(
    {
        "entity_fill": ModuleScopeBehavior.DOCUMENT_LEVEL,
        "source_fill": ModuleScopeBehavior.DOCUMENT_LEVEL,
        "placeholder_replace": ModuleScopeBehavior.DOCUMENT_LEVEL,
        "formula_convert": ModuleScopeBehavior.REGION_FILTERED,
        "md_cleanup": ModuleScopeBehavior.DOCUMENT_LEVEL,
        "heading_recognition": ModuleScopeBehavior.STRUCTURE_DISCOVERY,
        "whitespace_normalize": ModuleScopeBehavior.REGION_FILTERED,
        "heading_numbering": ModuleScopeBehavior.REGION_FILTERED,
        "caption": ModuleScopeBehavior.REGION_FILTERED,
        "reference_format": ModuleScopeBehavior.REGION_FILTERED,
        "citation_link": ModuleScopeBehavior.REGION_FILTERED,
        "page_setup": ModuleScopeBehavior.DOCUMENT_LEVEL,
        "section_format": ModuleScopeBehavior.DOCUMENT_LEVEL,
        "paragraph_style": ModuleScopeBehavior.REGION_FILTERED,
        "table_format": ModuleScopeBehavior.REGION_FILTERED,
        "figure_table_center": ModuleScopeBehavior.REGION_FILTERED,
        "chem_typography": ModuleScopeBehavior.REGION_FILTERED,
        "equation_table_format": ModuleScopeBehavior.REGION_FILTERED,
        "header_footer": ModuleScopeBehavior.DOCUMENT_LEVEL,
        "toc": ModuleScopeBehavior.REGION_FILTERED,
        "watermark": ModuleScopeBehavior.DOCUMENT_LEVEL,
        "image_insertion": ModuleScopeBehavior.DOCUMENT_LEVEL,
        "validation": ModuleScopeBehavior.DOCUMENT_LEVEL,
    }
)


@dataclass(frozen=True, slots=True)
class ModuleMutationContract:
    """Module mutation facts not represented directly by ModuleMeta.

    ``invalidates_document_index`` refers to the shared body paragraph/index
    view (``doc_tree`` and ``heading_map``).  Header/footer story edits and
    run-only XML rewrites therefore do not invalidate that index.
    """

    changes_document_structure: bool = False
    invalidates_document_index: bool = False
    changes_pagination: bool = False


_NO_MUTATION = ModuleMutationContract()


# These facts were audited from the apply implementations, not inferred from
# category names.  In particular, CaptionModule and TocModule can add/remove
# body paragraphs even though their current ModuleMeta.modifies_structure is
# false.  SectionFormatModule mutates section topology; until the future index
# protocol can invalidate only section-derived views, it conservatively
# invalidates the shared document index as one atomic contract.
MODULE_MUTATION_OVERRIDES: Mapping[str, ModuleMutationContract] = MappingProxyType(
    {
        "entity_fill": ModuleMutationContract(changes_pagination=True),
        "source_fill": ModuleMutationContract(changes_pagination=True),
        "placeholder_replace": ModuleMutationContract(changes_pagination=True),
        "formula_convert": ModuleMutationContract(
            changes_document_structure=True,
            invalidates_document_index=True,
            changes_pagination=True,
        ),
        "md_cleanup": ModuleMutationContract(changes_pagination=True),
        "whitespace_normalize": ModuleMutationContract(changes_pagination=True),
        "heading_numbering": ModuleMutationContract(changes_pagination=True),
        "caption": ModuleMutationContract(
            changes_document_structure=True,
            invalidates_document_index=True,
            changes_pagination=True,
        ),
        "reference_format": ModuleMutationContract(changes_pagination=True),
        "page_setup": ModuleMutationContract(changes_pagination=True),
        "section_format": ModuleMutationContract(
            changes_document_structure=True,
            invalidates_document_index=True,
            changes_pagination=True,
        ),
        "paragraph_style": ModuleMutationContract(changes_pagination=True),
        "table_format": ModuleMutationContract(changes_pagination=True),
        "chem_typography": ModuleMutationContract(changes_pagination=True),
        "equation_table_format": ModuleMutationContract(
            changes_document_structure=True,
            invalidates_document_index=True,
            changes_pagination=True,
        ),
        "toc": ModuleMutationContract(
            changes_document_structure=True,
            invalidates_document_index=True,
            changes_pagination=True,
        ),
        "image_insertion": ModuleMutationContract(
            changes_document_structure=True,
            invalidates_document_index=True,
            changes_pagination=True,
        ),
    }
)


class ModulePhaseContractError(ValueError):
    """Raised when a module cannot be placed without guessing."""


def build_module_phase_graph(
    modules: Iterable[Any] | None = None,
) -> PhaseGraph:
    """Return a validated phase graph for module classes or instances.

    Registration order of ``modules`` is retained and becomes the tie-breaker
    for otherwise independent steps.  A missing hard dependency remains an
    error.  A ``soft_after`` target is included only when that target is in the
    selected set, matching the optional soft-ordering contract.
    """

    registered = _registered_modules() if modules is None else tuple(modules)
    metadata = tuple(_module_meta(module) for module in registered)
    names = tuple(str(meta.name) for meta in metadata)

    present_names = set(names)
    steps: list[PhaseStepMetadata] = []
    for meta in metadata:
        name = str(meta.name)
        phase = _resolved_module_phase(meta)
        _resolved_module_scope_behavior(meta)
        mutation = MODULE_MUTATION_OVERRIDES.get(name, _NO_MUTATION)
        if bool(getattr(meta, "modifies_structure", False)) and not (
            mutation.changes_document_structure
            and mutation.invalidates_document_index
        ):
            raise ModulePhaseContractError(
                f"Module {name!r} declares modifies_structure=True but has no "
                "explicit structure/index invalidation override."
            )

        hard_dependencies = tuple(getattr(meta, "depends_on", ()) or ())
        present_soft_dependencies = tuple(
            dependency
            for dependency in (getattr(meta, "soft_after", ()) or ())
            if dependency in present_names
        )
        dependencies = _ordered_unique(
            (*hard_dependencies, *present_soft_dependencies)
        )
        steps.append(
            PhaseStepMetadata(
                name=name,
                phase=phase,
                depends_on=dependencies,
                changes_document_structure=mutation.changes_document_structure,
                invalidates_document_index=mutation.invalidates_document_index,
                changes_pagination=mutation.changes_pagination,
            )
        )

    graph = PhaseGraph(steps)
    # Fail at the adaptation boundary.  Returning a graph with a missing hard
    # dependency, phase inversion, duplicate, or cycle would merely defer an
    # already-known data-flow conflict to runtime.
    graph.validate()
    return graph


def order_modules_by_phase(
    modules: Iterable[Any] | None = None,
) -> tuple[Any, ...]:
    """Return the supplied modules in validated explicit-phase order."""

    registered = _registered_modules() if modules is None else tuple(modules)
    graph = build_module_phase_graph(registered)
    by_name = {str(_module_meta(module).name): module for module in registered}
    return tuple(by_name[step.name] for step in graph.topological_order())


def _resolved_module_phase(meta: Any) -> Phase:
    """Resolve one explicit/compatibility phase without inference."""

    name = str(meta.name)
    raw_explicit = getattr(meta, "execution_phase", "")
    if raw_explicit is None:
        raw_explicit = ""
    if not isinstance(raw_explicit, str):
        raise ModulePhaseContractError(
            f"Module {name!r} execution_phase must be a serialized Phase string."
        )
    explicit_text = raw_explicit.strip()
    if explicit_text != raw_explicit:
        raise ModulePhaseContractError(
            f"Module {name!r} execution_phase cannot contain surrounding whitespace."
        )
    explicit_phase: Phase | None = None
    if explicit_text:
        try:
            explicit_phase = Phase(explicit_text)
        except ValueError as exc:
            raise ModulePhaseContractError(
                f"Module {name!r} has invalid execution_phase {explicit_text!r}."
            ) from exc

    compatibility_phase = MODULE_PHASES.get(name)
    if compatibility_phase is not None:
        if explicit_phase is not None and explicit_phase is not compatibility_phase:
            raise ModulePhaseContractError(
                f"Module {name!r} execution_phase {explicit_phase.value!r} conflicts "
                f"with compatibility phase {compatibility_phase.value!r}."
            )
        return explicit_phase or compatibility_phase
    if explicit_phase is None:
        raise ModulePhaseContractError(
            "Modules have no explicit phase assignment: "
            f"{name!r}. Set ModuleMeta.execution_phase before scheduling."
        )
    return explicit_phase


def module_scope_behavior(module_or_name: Any) -> ModuleScopeBehavior:
    """Return one validated scope behavior for a module, metadata, or name."""

    if isinstance(module_or_name, str):
        behavior = MODULE_SCOPE_BEHAVIORS.get(module_or_name)
        if behavior is None:
            raise ModulePhaseContractError(
                f"Module {module_or_name!r} has no explicit scope_behavior."
            )
        return behavior
    meta = getattr(module_or_name, "meta", module_or_name)
    return _resolved_module_scope_behavior(meta)


def _resolved_module_scope_behavior(meta: Any) -> ModuleScopeBehavior:
    name = str(meta.name)
    raw_explicit = getattr(meta, "scope_behavior", "")
    if raw_explicit is None:
        raw_explicit = ""
    if not isinstance(raw_explicit, str):
        raise ModulePhaseContractError(
            f"Module {name!r} scope_behavior must be a serialized string."
        )
    explicit_text = raw_explicit.strip()
    if explicit_text != raw_explicit:
        raise ModulePhaseContractError(
            f"Module {name!r} scope_behavior cannot contain surrounding whitespace."
        )
    explicit_behavior: ModuleScopeBehavior | None = None
    if explicit_text:
        try:
            explicit_behavior = ModuleScopeBehavior(explicit_text)
        except ValueError as exc:
            raise ModulePhaseContractError(
                f"Module {name!r} has invalid scope_behavior {explicit_text!r}."
            ) from exc

    registered_behavior = MODULE_SCOPE_BEHAVIORS.get(name)
    if registered_behavior is not None:
        if (
            explicit_behavior is not None
            and explicit_behavior is not registered_behavior
        ):
            raise ModulePhaseContractError(
                f"Module {name!r} scope_behavior {explicit_behavior.value!r} "
                f"conflicts with registered behavior {registered_behavior.value!r}."
            )
        return explicit_behavior or registered_behavior
    if explicit_behavior is None:
        raise ModulePhaseContractError(
            f"Module {name!r} has no explicit scope_behavior."
        )
    return explicit_behavior


def _registered_modules() -> tuple[Any, ...]:
    # Keep the registry import lazy so importing the phase contract itself does
    # not eagerly import every python-docx mutation module.
    from src.modules.registry import ALL_MODULES

    return tuple(ALL_MODULES)


def _module_meta(module: Any) -> Any:
    meta = getattr(module, "meta", None)
    name = getattr(meta, "name", None)
    if meta is None or not isinstance(name, str) or not name.strip():
        raise ModulePhaseContractError(
            f"Object {module!r} does not expose a non-empty ModuleMeta.name."
        )
    return meta


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)
