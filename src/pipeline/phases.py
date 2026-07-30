"""Explicit execution phases and validation for the document pipeline.

This module deliberately has no dependency on ``BaseModule`` or the current
runner.  It defines the orchestration contract that those layers can adopt
incrementally without making phase order an accidental consequence of module
names.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from heapq import heappop, heappush
from types import MappingProxyType


class Phase(str, Enum):
    """Frozen top-level phases of one document delivery transaction."""

    FREEZE = "freeze"
    INTAKE = "intake"
    COMPOSE = "compose"
    FILL = "fill"
    SEMANTICS = "semantics"
    FORMAT = "format"
    VARIANT = "variant"
    PREPARE_IMAGES = "prepare_images"
    STAGE_ARTIFACT = "stage_artifact"
    OFFICE_LAYOUT = "office_layout"
    FINAL_VALIDATION = "final_validation"
    PUBLISH = "publish"


# This tuple is the architectural contract.  Do not derive it from Enum
# declaration order: changing it must be a deliberate, reviewable edit.
PHASE_ORDER: tuple[Phase, ...] = (
    Phase.FREEZE,
    Phase.INTAKE,
    Phase.COMPOSE,
    Phase.FILL,
    Phase.SEMANTICS,
    Phase.FORMAT,
    Phase.VARIANT,
    Phase.PREPARE_IMAGES,
    Phase.STAGE_ARTIFACT,
    Phase.OFFICE_LAYOUT,
    Phase.FINAL_VALIDATION,
    Phase.PUBLISH,
)


@dataclass(frozen=True, slots=True)
class PhaseMetadata:
    """Human- and machine-readable metadata for a frozen phase."""

    phase: Phase
    ordinal: int
    display_name: str
    purpose: str
    allows_pagination_change: bool


_PHASE_PURPOSES: Mapping[Phase, tuple[str, str]] = MappingProxyType(
    {
        Phase.FREEZE: ("Freeze", "Freeze the material snapshot and resolved inputs."),
        Phase.INTAKE: ("Intake", "Preflight sources, targets, and token routing."),
        Phase.COMPOSE: ("Compose", "Import and compose semantic content blocks."),
        Phase.FILL: ("Fill", "Fill fields and source-backed values."),
        Phase.SEMANTICS: ("Semantics", "Resolve headings, numbering, captions, and references."),
        Phase.FORMAT: ("Format", "Apply page, section, paragraph, table, header, and footer formatting."),
        Phase.VARIANT: ("Variant", "Fork delivery variants and apply visibility contracts."),
        Phase.PREPARE_IMAGES: ("PrepareImages", "Normalize images and burn resolved watermarks."),
        Phase.STAGE_ARTIFACT: ("StageArtifact", "Persist the shadow DOCX and stable layout anchors."),
        Phase.OFFICE_LAYOUT: ("OfficeLayout", "Paginate, measure, insert, and verify in Office."),
        Phase.FINAL_VALIDATION: ("FinalValidation", "Validate structural and layout invariants."),
        Phase.PUBLISH: ("Publish", "Atomically publish artifacts, reports, and manifests."),
    }
)


PHASE_METADATA: Mapping[Phase, PhaseMetadata] = MappingProxyType(
    {
        phase: PhaseMetadata(
            phase=phase,
            ordinal=ordinal,
            display_name=_PHASE_PURPOSES[phase][0],
            purpose=_PHASE_PURPOSES[phase][1],
            # OfficeLayout is the last phase allowed to alter pagination.
            allows_pagination_change=ordinal
            <= PHASE_ORDER.index(Phase.OFFICE_LAYOUT),
        )
        for ordinal, phase in enumerate(PHASE_ORDER)
    }
)

_PHASE_RANK: Mapping[Phase, int] = MappingProxyType(
    {phase: ordinal for ordinal, phase in enumerate(PHASE_ORDER)}
)


@dataclass(frozen=True, slots=True)
class PhaseStepMetadata:
    """Scheduling and mutation contract for one named execution step.

    ``depends_on`` contains step names, not phase names.  A dependency may be
    in the same phase or an earlier phase.  Fixed phase order already provides
    the broad phase barrier; explicit dependencies document data-flow and
    determine stable ordering inside a phase.
    """

    name: str
    phase: Phase
    depends_on: tuple[str, ...] = ()
    changes_document_structure: bool = False
    invalidates_document_index: bool = False
    changes_pagination: bool = False

    def __post_init__(self) -> None:
        # Accept serialized phase values and list-like dependencies at the
        # boundary while storing one immutable representation internally.
        object.__setattr__(self, "phase", Phase(self.phase))
        object.__setattr__(self, "depends_on", tuple(self.depends_on))


class PhaseGraphValidationError(ValueError):
    """Raised when a phase graph violates one or more frozen contracts."""

    def __init__(self, errors: Iterable[str]):
        self.errors = tuple(errors)
        detail = "\n".join(f"- {error}" for error in self.errors)
        super().__init__(f"Invalid phase graph:\n{detail}")


class PhaseGraph:
    """Immutable phase-step graph with deterministic topological ordering."""

    def __init__(self, steps: Iterable[PhaseStepMetadata] = ()) -> None:
        self._steps = tuple(steps)

    @property
    def steps(self) -> tuple[PhaseStepMetadata, ...]:
        """Return steps in registration order."""
        return self._steps

    def steps_for(self, phase: Phase | str) -> tuple[PhaseStepMetadata, ...]:
        """Return registered steps for one phase without reordering them."""
        selected_phase = Phase(phase)
        return tuple(step for step in self._steps if step.phase is selected_phase)

    def validation_errors(self) -> tuple[str, ...]:
        """Return all deterministic validation errors without raising."""
        errors: list[str] = []
        names: dict[str, PhaseStepMetadata] = {}
        duplicate_names: set[str] = set()

        for step in self._steps:
            if not step.name or step.name != step.name.strip():
                errors.append(
                    f"Step name {step.name!r} must be non-empty and have no surrounding whitespace."
                )
            if step.name in names:
                duplicate_names.add(step.name)
            else:
                names[step.name] = step

            duplicate_dependencies = _duplicates(step.depends_on)
            if duplicate_dependencies:
                errors.append(
                    f"Step '{step.name}' declares duplicate dependencies: "
                    f"{', '.join(duplicate_dependencies)}."
                )

            if (
                step.changes_document_structure
                and not step.invalidates_document_index
            ):
                errors.append(
                    f"Step '{step.name}' changes document structure but does not "
                    "declare invalidates_document_index=True."
                )

            phase_meta = PHASE_METADATA[step.phase]
            if step.changes_pagination and not phase_meta.allows_pagination_change:
                errors.append(
                    f"Step '{step.name}' in phase '{phase_meta.display_name}' changes "
                    "pagination after OfficeLayout."
                )

        for name in _in_registration_order(duplicate_names, self._steps):
            errors.append(f"Duplicate step name '{name}'.")

        if duplicate_names:
            # Dependency targets would be ambiguous, so further graph analysis
            # would produce misleading secondary diagnostics.
            return tuple(errors)

        for step in self._steps:
            for dependency_name in step.depends_on:
                dependency = names.get(dependency_name)
                if dependency is None:
                    errors.append(
                        f"Step '{step.name}' has missing dependency '{dependency_name}'."
                    )
                    continue
                if _PHASE_RANK[dependency.phase] > _PHASE_RANK[step.phase]:
                    errors.append(
                        f"Step '{step.name}' in phase "
                        f"'{PHASE_METADATA[step.phase].display_name}' cannot depend on "
                        f"later-phase step '{dependency.name}' in phase "
                        f"'{PHASE_METADATA[dependency.phase].display_name}'."
                    )

        errors.extend(self._cycle_errors(names))
        return tuple(errors)

    def validate(self) -> None:
        """Raise one aggregate error if any phase contract is invalid."""
        errors = self.validation_errors()
        if errors:
            raise PhaseGraphValidationError(errors)

    def topological_order(self) -> tuple[PhaseStepMetadata, ...]:
        """Return fixed phase order plus stable topology within each phase.

        Registration order is the tie-breaker for independent ready steps.
        This makes ordering deterministic without falling back to alphabetical
        module names.
        """
        self.validate()
        registration_index = {
            step.name: index for index, step in enumerate(self._steps)
        }
        ordered: list[PhaseStepMetadata] = []

        for phase in PHASE_ORDER:
            phase_steps = self.steps_for(phase)
            if not phase_steps:
                continue

            phase_names = {step.name for step in phase_steps}
            in_degree = {step.name: 0 for step in phase_steps}
            dependents: dict[str, list[str]] = defaultdict(list)

            for step in phase_steps:
                for dependency_name in step.depends_on:
                    if dependency_name not in phase_names:
                        # Valid earlier-phase dependencies are already satisfied
                        # by the fixed phase barrier.
                        continue
                    in_degree[step.name] += 1
                    dependents[dependency_name].append(step.name)

            ready: list[tuple[int, str]] = []
            for step in phase_steps:
                if in_degree[step.name] == 0:
                    heappush(ready, (registration_index[step.name], step.name))

            while ready:
                _, name = heappop(ready)
                ordered.append(self._step_by_name(name))
                for dependent_name in dependents[name]:
                    in_degree[dependent_name] -= 1
                    if in_degree[dependent_name] == 0:
                        heappush(
                            ready,
                            (registration_index[dependent_name], dependent_name),
                        )

        return tuple(ordered)

    def _cycle_errors(
        self,
        names: Mapping[str, PhaseStepMetadata],
    ) -> tuple[str, ...]:
        errors: list[str] = []
        registration_index = {
            step.name: index for index, step in enumerate(self._steps)
        }

        for phase in PHASE_ORDER:
            phase_steps = self.steps_for(phase)
            if not phase_steps:
                continue
            phase_names = {step.name for step in phase_steps}
            in_degree = {step.name: 0 for step in phase_steps}
            dependents: dict[str, list[str]] = defaultdict(list)

            for step in phase_steps:
                for dependency_name in step.depends_on:
                    dependency = names.get(dependency_name)
                    if dependency is None or dependency_name not in phase_names:
                        continue
                    in_degree[step.name] += 1
                    dependents[dependency_name].append(step.name)

            ready: list[tuple[int, str]] = []
            for step in phase_steps:
                if in_degree[step.name] == 0:
                    heappush(ready, (registration_index[step.name], step.name))

            visited = 0
            while ready:
                _, name = heappop(ready)
                visited += 1
                for dependent_name in dependents[name]:
                    in_degree[dependent_name] -= 1
                    if in_degree[dependent_name] == 0:
                        heappush(
                            ready,
                            (registration_index[dependent_name], dependent_name),
                        )

            if visited != len(phase_steps):
                cyclic_names = [
                    step.name
                    for step in phase_steps
                    if in_degree[step.name] > 0
                ]
                errors.append(
                    f"Cycle detected in phase '{PHASE_METADATA[phase].display_name}': "
                    f"{', '.join(cyclic_names)}."
                )

        return tuple(errors)

    def _step_by_name(self, name: str) -> PhaseStepMetadata:
        for step in self._steps:
            if step.name == name:
                return step
        raise KeyError(name)  # pragma: no cover - guarded by validation


def _duplicates(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return tuple(duplicates)


def _in_registration_order(
    names: set[str],
    steps: tuple[PhaseStepMetadata, ...],
) -> tuple[str, ...]:
    ordered: list[str] = []
    for step in steps:
        if step.name in names and step.name not in ordered:
            ordered.append(step.name)
    return tuple(ordered)
