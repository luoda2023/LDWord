from dataclasses import FrozenInstanceError

import pytest

from src.pipeline.phases import (
    PHASE_METADATA,
    PHASE_ORDER,
    Phase,
    PhaseGraph,
    PhaseGraphValidationError,
    PhaseStepMetadata,
)


def _step(
    name: str,
    phase: Phase,
    *,
    depends_on: tuple[str, ...] = (),
    changes_document_structure: bool = False,
    invalidates_document_index: bool = False,
    changes_pagination: bool = False,
) -> PhaseStepMetadata:
    return PhaseStepMetadata(
        name=name,
        phase=phase,
        depends_on=depends_on,
        changes_document_structure=changes_document_structure,
        invalidates_document_index=invalidates_document_index,
        changes_pagination=changes_pagination,
    )


def test_phase_order_and_display_names_are_frozen_architecture_contract():
    assert PHASE_ORDER == (
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
    assert [PHASE_METADATA[phase].display_name for phase in PHASE_ORDER] == [
        "Freeze",
        "Intake",
        "Compose",
        "Fill",
        "Semantics",
        "Format",
        "Variant",
        "PrepareImages",
        "StageArtifact",
        "OfficeLayout",
        "FinalValidation",
        "Publish",
    ]
    assert [PHASE_METADATA[phase].ordinal for phase in PHASE_ORDER] == list(
        range(len(PHASE_ORDER))
    )


def test_phase_and_step_metadata_are_immutable():
    with pytest.raises(TypeError):
        PHASE_METADATA[Phase.FREEZE] = PHASE_METADATA[Phase.INTAKE]

    step = _step("freeze_snapshot", Phase.FREEZE)
    with pytest.raises(FrozenInstanceError):
        step.name = "changed"


def test_topology_uses_fixed_phase_order_and_registration_order_for_ties():
    graph = PhaseGraph(
        [
            _step("format_second", Phase.FORMAT),
            _step("freeze_first", Phase.FREEZE),
            _step("format_first", Phase.FORMAT),
            _step("publish_last", Phase.PUBLISH),
        ]
    )

    assert [step.name for step in graph.topological_order()] == [
        "freeze_first",
        "format_second",
        "format_first",
        "publish_last",
    ]


def test_same_phase_dependency_overrides_registration_order_stably():
    graph = PhaseGraph(
        [
            _step("consumer", Phase.SEMANTICS, depends_on=("provider",)),
            _step("independent", Phase.SEMANTICS),
            _step("provider", Phase.SEMANTICS),
            _step("tail", Phase.SEMANTICS),
        ]
    )

    assert [step.name for step in graph.topological_order()] == [
        "independent",
        "provider",
        "consumer",
        "tail",
    ]


def test_later_phase_may_depend_on_earlier_phase():
    graph = PhaseGraph(
        [
            _step("snapshot", Phase.FREEZE),
            _step("compose", Phase.COMPOSE, depends_on=("snapshot",)),
            _step("layout", Phase.OFFICE_LAYOUT, depends_on=("compose",)),
        ]
    )

    graph.validate()
    assert [step.name for step in graph.topological_order()] == [
        "snapshot",
        "compose",
        "layout",
    ]


def test_earlier_phase_cannot_depend_on_later_phase():
    graph = PhaseGraph(
        [
            _step("compose", Phase.COMPOSE, depends_on=("layout",)),
            _step("layout", Phase.OFFICE_LAYOUT),
        ]
    )

    with pytest.raises(PhaseGraphValidationError, match="cannot depend on later-phase"):
        graph.topological_order()


def test_missing_dependencies_and_duplicate_names_are_rejected():
    missing = PhaseGraph(
        [_step("compose", Phase.COMPOSE, depends_on=("not_registered",))]
    )
    with pytest.raises(PhaseGraphValidationError, match="missing dependency"):
        missing.validate()

    duplicate = PhaseGraph(
        [_step("same", Phase.FREEZE), _step("same", Phase.INTAKE)]
    )
    with pytest.raises(PhaseGraphValidationError, match="Duplicate step name 'same'"):
        duplicate.validate()


def test_same_phase_cycle_is_rejected_with_phase_diagnostic():
    graph = PhaseGraph(
        [
            _step("one", Phase.FILL, depends_on=("two",)),
            _step("two", Phase.FILL, depends_on=("one",)),
        ]
    )

    with pytest.raises(PhaseGraphValidationError, match="Cycle detected in phase 'Fill'"):
        graph.topological_order()


def test_structural_mutation_must_invalidate_document_index():
    invalid = PhaseGraph(
        [
            _step(
                "insert_content",
                Phase.COMPOSE,
                changes_document_structure=True,
            )
        ]
    )
    with pytest.raises(
        PhaseGraphValidationError,
        match="invalidates_document_index=True",
    ):
        invalid.validate()

    valid = PhaseGraph(
        [
            _step(
                "insert_content",
                Phase.COMPOSE,
                changes_document_structure=True,
                invalidates_document_index=True,
            )
        ]
    )
    valid.validate()


@pytest.mark.parametrize("phase", [Phase.FINAL_VALIDATION, Phase.PUBLISH])
def test_pagination_changing_mutation_is_forbidden_after_office_layout(phase):
    graph = PhaseGraph([_step("late_write", phase, changes_pagination=True)])

    with pytest.raises(
        PhaseGraphValidationError,
        match="changes pagination after OfficeLayout",
    ):
        graph.validate()


def test_office_layout_itself_is_last_phase_allowed_to_change_pagination():
    assert PHASE_METADATA[Phase.OFFICE_LAYOUT].allows_pagination_change is True
    assert PHASE_METADATA[Phase.FINAL_VALIDATION].allows_pagination_change is False

    PhaseGraph(
        [_step("insert_fitted_image", Phase.OFFICE_LAYOUT, changes_pagination=True)]
    ).validate()


def test_steps_for_preserves_registration_order_and_accepts_serialized_phase():
    graph = PhaseGraph(
        [
            PhaseStepMetadata(name="one", phase="fill"),
            _step("other", Phase.FORMAT),
            _step("two", Phase.FILL),
        ]
    )

    assert [step.name for step in graph.steps_for("fill")] == ["one", "two"]


def test_validation_reports_duplicate_dependency_declaration():
    graph = PhaseGraph(
        [
            _step("provider", Phase.INTAKE),
            _step(
                "consumer",
                Phase.COMPOSE,
                depends_on=("provider", "provider"),
            ),
        ]
    )

    with pytest.raises(PhaseGraphValidationError, match="duplicate dependencies"):
        graph.validate()
