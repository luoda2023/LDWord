"""Release-governance item factories for scene matrix drilldown reports."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

from src.config.scene_matrix_drilldown_models import (
    SceneMatrixDrilldownItem,
    SceneMatrixDrilldownRow,
)
from src.config.scene_matrix_drilldown_projection_references import (
    _release_residual_receipt_action_ids,
)
from src.config.scene_release_governance_registry import (
    build_scene_release_governance_report,
)


@lru_cache(maxsize=None)
def _release_governance_report(report_id: str) -> object:
    return build_scene_release_governance_report(report_id)


def _boundary_guarded_completion_item() -> SceneMatrixDrilldownItem:
    report = _release_governance_report("scene_boundary_guarded_completion_audit")
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=f"{row.subject_type}:{row.subject_id}",
            label=row.subject_id,
            status=row.status,
            source_id="scene_boundary_guarded_completion_audit",
            detail=(
                f"{row.readiness_level} / {row.maturity_status} / "
                f"{len(row.remaining_gap_ids)} retained gaps / "
                f"{len(row.external_handoff_contract_ids)} contracts / "
                f"{len(row.excluded_core_claims)} excluded claims"
            ),
            pack_ids=(row.subject_id,) if row.subject_type == "pack" else (),
            family_ids=(row.subject_id,) if row.subject_type == "family" else (),
            fixture_ids=row.fixture_ids,
            action_behavior_ids=row.evidence_ids,
            capability_ids=(
                *row.remaining_gap_ids,
                *row.boundary_capability_ids,
                *row.external_handoff_contract_ids,
                *row.target_plugin_ids,
                *row.report_ids,
                *row.excluded_core_claims,
            ),
            maturity_gap_domain_ids=("boundary_gate",),
            plugin_gate_ids=row.plugin_gate_ids,
            risk_domain_ids=row.risk_domain_ids,
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="boundary_guarded_completion",
        label="Boundary guarded completion",
        source_id="scene_boundary_guarded_completion_audit",
        lens_ids=("boundary", "evidence_chain", "product_readiness"),
        route_hint="Blue/Boundary subject -> retained gap -> capability/gate/handoff -> excluded core claims",
        detail=(
            "Browse Blue/Boundary subjects that remain outside Green/L5 but "
            "are complete as guarded product boundaries."
        ),
        rows=rows,
        visible_rows=rows,
    )


def _residual_warning_governance_item() -> SceneMatrixDrilldownItem:
    report = _release_governance_report("scene_residual_warning_governance_audit")
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.row_id,
            label=f"{row.scope_id} / {row.warning_kind}",
            status=row.status,
            source_id="scene_residual_warning_governance_audit",
            detail=f"{row.governance_mode} / {row.reason}",
            pack_ids=row.linked_pack_ids,
            family_ids=row.linked_family_ids,
            count_profile_ids=row.linked_profile_ids,
            action_behavior_ids=(row.warning_kind, row.governance_mode),
            capability_ids=(
                *row.evidence_ids,
                *row.linked_boundary_subject_ids,
                *row.linked_profile_ids,
            ),
            plugin_gate_ids=row.linked_plugin_gate_ids,
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="residual_warning_governance",
        label="Residual warning governance",
        source_id="scene_residual_warning_governance_audit",
        lens_ids=("boundary", "evidence_chain", "product_readiness"),
        route_hint="warning source -> managed boundary/reference evidence -> dashboard/release projection",
        detail=(
            "Browse managed residual warnings so plugin/manual boundaries, "
            "reference profiles, and dashboard projections cannot drift silently."
        ),
        rows=rows,
        visible_rows=rows,
    )


def _boundary_readiness_reconciliation_item() -> SceneMatrixDrilldownItem:
    report = _release_governance_report(
        "scene_boundary_readiness_reconciliation_audit"
    )
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.row_id,
            label=f"{row.scope_id} / {row.metric_id}",
            status=row.status,
            source_id="scene_boundary_readiness_reconciliation_audit",
            detail=(
                f"{row.observed_status} -> {row.reconciliation_mode}; "
                f"{row.reason}"
            ),
            pack_ids=row.linked_pack_ids,
            family_ids=row.linked_family_ids,
            action_behavior_ids=(
                row.metric_id,
                row.observed_status,
                row.reconciliation_mode,
            ),
            capability_ids=(
                *row.evidence_ids,
                *row.linked_boundary_subject_ids,
            ),
            maturity_gap_domain_ids=(
                ("boundary_gate",)
                if row.linked_boundary_subject_ids
                else ()
            ),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="boundary_readiness_reconciliation",
        label="Boundary readiness reconciliation",
        source_id="scene_boundary_readiness_reconciliation_audit",
        lens_ids=("boundary", "evidence_chain", "product_readiness"),
        route_hint="non-full readiness counter -> observed status -> boundary/not-applicable reconciliation",
        detail=(
            "Browse non-full readiness counters that are intentionally retained "
            "as boundary, not-applicable, or static-closed-but-not-Green/L5."
        ),
        rows=rows,
        visible_rows=rows,
    )


def _terminal_release_exception_item() -> SceneMatrixDrilldownItem:
    report = _release_governance_report("scene_terminal_release_exception_audit")
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.exception_id,
            label=f"{row.exception_id} / {row.exception_kind}",
            status=row.status,
            source_id="scene_terminal_release_exception_audit",
            detail=(
                f"{row.governed_count}/{row.observed_count} governed; "
                f"{row.trace_count} traces; "
                f"{row.reason}"
            ),
            action_behavior_ids=(row.exception_kind, row.status),
            capability_ids=(
                *row.evidence_ids,
                *row.source_ids,
                *row.source_trace_ids,
            ),
            maturity_gap_domain_ids=(
                ("boundary_gate",)
                if row.exception_id
                in {
                    "boundary_guarded_maturity",
                    "static_closed_boundary",
                }
                else ()
            ),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="terminal_release_exception",
        label="Terminal release exceptions",
        source_id="scene_terminal_release_exception_audit",
        lens_ids=("boundary", "evidence_chain", "product_readiness"),
        route_hint="release residual counter -> governed exception ledger -> lower-level audit",
        detail=(
            "Browse terminal release exceptions that make nonzero warnings, "
            "non-full readiness, and L5-blocked boundary states releasable."
        ),
        rows=rows,
        visible_rows=rows,
    )


def _boundary_subject_release_dossier_item() -> SceneMatrixDrilldownItem:
    report = _release_governance_report(
        "scene_boundary_subject_release_dossier_audit"
    )
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.subject_key,
            label=f"{row.subject_key} / {row.status}",
            status=row.status,
            source_id="scene_boundary_subject_release_dossier_audit",
            detail=(
                f"{row.subject_trace_count} traces / "
                f"{len(row.readiness_reconciliation_row_ids)} readiness rows / "
                f"{len(row.external_handoff_contract_ids)} handoff contracts"
            ),
            pack_ids=((row.subject_id,) if row.subject_type == "pack" else ()),
            family_ids=((row.subject_id,) if row.subject_type == "family" else ()),
            action_behavior_ids=(
                row.status,
                row.readiness_level,
                row.maturity_status,
                *row.terminal_exception_ids,
            ),
            capability_ids=(
                *row.evidence_ids,
                *row.boundary_capability_ids,
                *row.external_handoff_contract_ids,
                *row.readiness_reconciliation_row_ids,
                *row.release_exception_trace_ids,
            ),
            plugin_gate_ids=row.plugin_gate_ids,
            maturity_gap_domain_ids=row.retained_gap_ids,
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="boundary_subject_release_dossier",
        label="Boundary subject release dossiers",
        source_id="scene_boundary_subject_release_dossier_audit",
        lens_ids=("boundary", "evidence_chain", "product_readiness"),
        route_hint="boundary subject -> release dossier -> exception/readiness traces",
        detail=(
            "Browse Blue/Boundary subjects as release dossiers with guarded "
            "completion, readiness reconciliation, handoff, and exception traces."
        ),
        rows=rows,
        visible_rows=rows,
    )


def _non_subject_release_trace_attribution_item() -> SceneMatrixDrilldownItem:
    report = _release_governance_report(
        "scene_non_subject_release_trace_attribution_audit"
    )
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.trace_id,
            label=f"{row.scope_type}:{row.scope_id} / {row.attribution_kind}",
            status=row.status,
            source_id="scene_non_subject_release_trace_attribution_audit",
            detail=f"{row.terminal_exception_id}; {row.reason}",
            pack_ids=row.linked_pack_ids,
            action_behavior_ids=(
                row.attribution_kind,
                row.terminal_exception_id,
                row.status,
            ),
            capability_ids=(
                *row.evidence_ids,
                row.source_trace_id,
                row.surface_source_id,
                *row.linked_profile_ids,
            ),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="non_subject_release_trace_attribution",
        label="Non-subject release trace attribution",
        source_id="scene_non_subject_release_trace_attribution_audit",
        lens_ids=("boundary", "evidence_chain", "product_readiness"),
        route_hint="terminal release trace -> non-subject attribution",
        detail=(
            "Browse release traces that intentionally stay outside boundary "
            "subject dossiers, including dashboard projections and generic "
            "not-applicable surfaces."
        ),
        rows=rows,
        visible_rows=rows,
    )


def _release_trace_partition_guard_item() -> SceneMatrixDrilldownItem:
    report = _release_governance_report("scene_release_trace_partition_guard_audit")
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.partition_id,
            label=f"{row.label} / {row.status}",
            status=row.status,
            source_id="scene_release_trace_partition_guard_audit",
            detail=(
                f"{row.trace_count}/{row.expected_trace_count} traces; "
                f"{len(row.issue_ids)} issues"
            ),
            action_behavior_ids=(row.status,),
            capability_ids=(
                *row.evidence_ids,
                *row.trace_ids,
            ),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="release_trace_partition_guard",
        label="Release trace partition guard",
        source_id="scene_release_trace_partition_guard_audit",
        lens_ids=("boundary", "evidence_chain", "product_readiness"),
        route_hint="terminal trace ledger -> subject/non-subject partition guard",
        detail=(
            "Browse the guard that proves terminal release traces are fully "
            "and exclusively partitioned by boundary subjects or non-subject "
            "attribution."
        ),
        rows=rows,
        visible_rows=rows,
    )


def _release_projection_surface_parity_item() -> SceneMatrixDrilldownItem:
    report = _release_governance_report(
        "scene_release_projection_surface_parity_audit"
    )
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.projection_id,
            label=f"{row.projection_id} / {row.status}",
            status=row.status,
            source_id="scene_release_projection_surface_parity_audit",
            detail=(
                f"{row.audit_source_id} -> {row.dashboard_card_id} -> "
                f"{row.drilldown_id}"
            ),
            action_behavior_ids=(
                row.release_gate_check_id,
                row.dashboard_card_id,
                row.drilldown_id,
                row.status,
            ),
            capability_ids=(
                *row.evidence_ids,
                row.audit_source_id,
                row.summary_marker,
                row.export_script_path,
                row.test_path,
                row.closure_doc_path,
                *row.supplemental_closure_doc_paths,
            ),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="release_projection_surface_parity",
        label="Release projection parity",
        source_id="scene_release_projection_surface_parity_audit",
        lens_ids=("boundary", "evidence_chain", "product_readiness"),
        route_hint="release audit -> gate/dashboard/drilldown/summary/CI parity",
        detail=(
            "Browse whether release-related audits are projected through all "
            "user-visible and release-gate surfaces."
        ),
        rows=rows,
        visible_rows=rows,
    )


def _boundary_subject_release_continuity_item() -> SceneMatrixDrilldownItem:
    report = _release_governance_report(
        "scene_boundary_subject_release_continuity_audit"
    )
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.subject_key,
            label=f"{row.subject_key} / {row.status}",
            status=row.status,
            source_id="scene_boundary_subject_release_continuity_audit",
            detail=(
                f"{len(row.readiness_row_ids)} readiness rows / "
                f"{len(row.terminal_trace_ids)} terminal traces / "
                f"{len(row.dossier_trace_ids)} dossier traces"
            ),
            pack_ids=((row.subject_id,) if row.subject_type == "pack" else ()),
            family_ids=((row.subject_id,) if row.subject_type == "family" else ()),
            action_behavior_ids=(
                row.status,
                "maturity" if row.in_maturity else "missing_maturity",
                "guarded_completion"
                if row.in_guarded_completion
                else "missing_guarded_completion",
                "readiness_reconciliation"
                if row.in_readiness_reconciliation
                else "missing_readiness_reconciliation",
                "terminal_release"
                if row.in_terminal_release_exception
                else "missing_terminal_release",
                "subject_dossier" if row.in_subject_dossier else "missing_dossier",
            ),
            capability_ids=(
                *row.evidence_ids,
                *row.readiness_row_ids,
                *row.terminal_trace_ids,
                *row.dossier_trace_ids,
            ),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="boundary_subject_release_continuity",
        label="Boundary subject release continuity",
        source_id="scene_boundary_subject_release_continuity_audit",
        lens_ids=("boundary", "evidence_chain", "product_readiness"),
        route_hint="boundary subject -> maturity/guarded/readiness/terminal/dossier continuity",
        detail=(
            "Browse whether each Blue/Boundary subject appears in every "
            "release-layer evidence surface."
        ),
        rows=rows,
        visible_rows=rows,
    )


def _release_closure_ledger_item() -> SceneMatrixDrilldownItem:
    report = _release_governance_report("scene_release_closure_ledger_audit")
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.stage_id,
            label=f"{row.order}. {row.stage_id} / {row.status}",
            status=row.status,
            source_id="scene_release_closure_ledger_audit",
            detail=(
                f"{row.n2_id} / upstream={len(row.upstream_stage_ids)} / "
                f"{row.release_gate_check_id} -> {row.dashboard_card_id}"
            ),
            action_behavior_ids=(
                row.status,
                row.release_gate_check_id,
                row.dashboard_card_id,
                row.drilldown_id,
                row.summary_marker,
            ),
            capability_ids=(
                *row.evidence_ids,
                *row.upstream_stage_ids,
                row.n2_id,
                row.source_id,
                row.export_script_path,
                row.test_path,
                row.closure_doc_path,
                *row.supplemental_closure_doc_paths,
            ),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="release_closure_ledger",
        label="Release closure ledger",
        source_id="scene_release_closure_ledger_audit",
        lens_ids=("boundary", "evidence_chain", "product_readiness"),
        route_hint="N2 release stage -> ordered gate/dashboard/drilldown evidence",
        detail=(
            "Browse the ordered release-closure stages so scattered release "
            "audits cannot drift away from the same gate and user-visible "
            "surfaces."
        ),
        rows=rows,
        visible_rows=rows,
    )


def _boundary_maturity_release_envelope_item() -> SceneMatrixDrilldownItem:
    report = _release_governance_report(
        "scene_boundary_maturity_release_envelope_audit"
    )
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.envelope_id,
            label=f"{row.subject_type}:{row.subject_id} / {row.status}",
            status=row.status,
            source_id="scene_boundary_maturity_release_envelope_audit",
            detail=(
                f"{row.gap_id} / {row.external_handoff_contract_id} / "
                f"{len(row.terminal_trace_ids)} terminal traces"
            ),
            pack_ids=((row.subject_id,) if row.subject_type == "pack" else ()),
            family_ids=((row.subject_id,) if row.subject_type == "family" else ()),
            action_behavior_ids=(
                row.status,
                row.external_handoff_contract_id,
                row.guarded_completion_status,
                row.release_dossier_status,
                row.subject_continuity_status,
            ),
            capability_ids=(
                *row.evidence_ids,
                row.gap_id,
                *row.readiness_row_ids,
                *row.terminal_trace_ids,
                *row.dossier_trace_ids,
            ),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="boundary_maturity_release_envelope",
        label="Boundary maturity release envelope",
        source_id="scene_boundary_maturity_release_envelope_audit",
        lens_ids=("boundary", "evidence_chain", "product_readiness"),
        route_hint="retained maturity gap -> handoff/guarded/readiness/terminal/dossier continuity",
        detail=(
            "Browse the release envelope that keeps each retained Blue/Boundary "
            "maturity blocker explainable without promoting it to Green/L5."
        ),
        rows=rows,
        visible_rows=rows,
    )


def _retained_gap_exit_criteria_item() -> SceneMatrixDrilldownItem:
    report = _release_governance_report("scene_retained_gap_exit_criteria_audit")
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.criteria_id,
            label=f"{row.subject_type}:{row.subject_id} / {row.status}",
            status=row.status,
            source_id="scene_retained_gap_exit_criteria_audit",
            detail=(
                f"{row.gap_id}; {len(row.exit_signal_ids)} exit signals; "
                f"{len(row.prohibited_core_claim_ids)} prohibited claims"
            ),
            pack_ids=((row.subject_id,) if row.subject_type == "pack" else ()),
            family_ids=((row.subject_id,) if row.subject_type == "family" else ()),
            action_behavior_ids=(
                row.status,
                row.release_envelope_id,
                row.external_handoff_contract_id,
                row.guarded_completion_status,
                *row.release_condition_ids,
            ),
            capability_ids=(
                row.gap_id,
                *row.exit_signal_ids,
                *row.prohibited_core_claim_ids,
            ),
            maturity_gap_domain_ids=("boundary_gate",),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="retained_gap_exit_criteria",
        label="Retained gap exit criteria",
        source_id="scene_retained_gap_exit_criteria_audit",
        lens_ids=("boundary", "evidence_chain", "product_readiness"),
        route_hint="retained maturity gap -> release conditions -> exit signals -> prohibited claims",
        detail=(
            "Browse the release allowance and exit criteria for retained "
            "Blue/Boundary gaps, including the claims core must not make "
            "before the boundary exits."
        ),
        rows=rows,
        visible_rows=rows,
    )


def _release_residual_ratio_ledger_item() -> SceneMatrixDrilldownItem:
    report = _release_governance_report("scene_release_residual_ratio_ledger_audit")
    guarded_by_envelope_id = _guarded_completion_rows_by_envelope_id()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.ratio_id,
            label=f"{row.ratio_id} / {row.observed_ratio}",
            status=row.status,
            source_id="scene_release_residual_ratio_ledger_audit",
            detail=(
                f"expected={row.expected_ratio}; {row.residual_mode}; "
                f"{row.reason}; "
                f"{_release_residual_receipt_detail(row)}; "
                f"{_release_residual_boundary_scope_detail(row, guarded_by_envelope_id)}"
            ),
            action_behavior_ids=(
                row.status,
                row.residual_mode,
                *row.terminal_exception_ids,
                *_release_residual_receipt_action_ids(row),
                *(
                    ("boundary_scope_guarded", "excluded_core_claims_declared")
                    if _release_residual_boundary_scope_capability_ids(
                        row,
                        guarded_by_envelope_id,
                    )
                    else ()
                ),
            ),
            capability_ids=_release_residual_capability_ids(
                row,
                guarded_by_envelope_id,
            ),
            maturity_gap_domain_ids=(
                ("boundary_gate",) if row.release_envelope_ids else ()
            ),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="release_residual_ratio_ledger",
        label="Release residual ratio ledger",
        source_id="scene_release_residual_ratio_ledger_audit",
        lens_ids=("boundary", "evidence_chain", "product_readiness"),
        route_hint="release summary ratio -> reconciliation/exception/envelope evidence",
        detail=(
            "Browse release-gate ratios that remain below 100% but are "
            "published as explained boundary or not-applicable residuals. "
            f"count_delivery_receipts={report.count_delivery_receipt_alignment_count}/"
            f"{report.count_delivery_receipt_alignment_link_count}; "
            f"maturity_l5_receipts={report.maturity_l5_blocker_receipt_alignment_count}/"
            f"{report.maturity_l5_blocker_receipt_alignment_link_count}."
        ),
        rows=rows,
        visible_rows=rows,
    )


def _guarded_completion_rows_by_envelope_id() -> dict[str, object]:
    report = _release_governance_report("scene_boundary_guarded_completion_audit")
    rows_by_envelope_id: dict[str, object] = {}
    for row in report.rows:
        subject_type = str(getattr(row, "subject_type", "") or "")
        subject_id = str(getattr(row, "subject_id", "") or "")
        for gap_id in getattr(row, "remaining_gap_ids", ()) or ():
            rows_by_envelope_id[f"{subject_type}:{subject_id}:{gap_id}"] = row
    return rows_by_envelope_id


def _release_residual_capability_ids(
    row: object,
    guarded_by_envelope_id: dict[str, object],
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            (
                *getattr(row, "evidence_ids", ()),
                *getattr(row, "readiness_reconciliation_row_ids", ()),
                *getattr(row, "release_envelope_ids", ()),
                *getattr(row, "retained_gap_exit_criteria_ids", ()),
                *getattr(row, "retained_gap_receipt_alignment_ids", ()),
                *_release_residual_boundary_scope_capability_ids(
                    row,
                    guarded_by_envelope_id,
                ),
            )
        )
    )


def _release_residual_receipt_detail(row: object) -> str:
    receipt_count = len(
        getattr(row, "retained_gap_receipt_alignment_ids", ()) or ()
    )
    exit_criteria_count = len(
        getattr(row, "retained_gap_exit_criteria_ids", ()) or ()
    )
    details = [f"receipt_alignments={receipt_count}/{exit_criteria_count}"]
    ratio_id = str(getattr(row, "ratio_id", "") or "")
    if ratio_id in ("count_profiles", "delivery_families"):
        details.append(f"count_delivery_receipts={receipt_count}/{exit_criteria_count}")
    elif ratio_id == "maturity_l5_blocked":
        details.append(f"maturity_l5_receipts={receipt_count}/{exit_criteria_count}")
    return "; ".join(details)


def _release_residual_boundary_scope_capability_ids(
    row: object,
    guarded_by_envelope_id: dict[str, object],
) -> tuple[str, ...]:
    capability_ids: list[str] = []
    for envelope_id in getattr(row, "release_envelope_ids", ()) or ():
        guarded_row = guarded_by_envelope_id.get(envelope_id)
        if guarded_row is None:
            continue
        capability_ids.extend(getattr(guarded_row, "boundary_capability_ids", ()))
    return tuple(dict.fromkeys(capability_ids))


def _join_values(values: tuple[object, ...]) -> str:
    return ", ".join(str(value) for value in values if str(value).strip())


def _release_residual_boundary_scope_detail(
    row: object,
    guarded_by_envelope_id: dict[str, object],
) -> str:
    capability_ids: list[str] = []
    excluded_claims: list[str] = []
    for envelope_id in getattr(row, "release_envelope_ids", ()) or ():
        guarded_row = guarded_by_envelope_id.get(envelope_id)
        if guarded_row is None:
            continue
        capability_ids.extend(getattr(guarded_row, "boundary_capability_ids", ()))
        excluded_claims.extend(getattr(guarded_row, "excluded_core_claims", ()))
    if not capability_ids and not excluded_claims:
        return "boundary_scopes=-; excluded_core_claims=-"
    return (
        "boundary_scopes="
        f"{_join_values(tuple(dict.fromkeys(capability_ids))) or '-'}; "
        "excluded_core_claims="
        f"{_join_values(tuple(dict.fromkeys(excluded_claims))) or '-'}"
    )


def _release_residual_explanation_item() -> SceneMatrixDrilldownItem:
    report = _release_governance_report("scene_release_residual_explanation_audit")
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.residual_id,
            label=f"{row.residual_id} / {row.governed_count}/{row.residual_count}",
            status=row.status,
            source_id="scene_release_residual_explanation_audit",
            detail=(
                f"marker={row.summary_marker}; "
                f"summary_marker_present={row.summary_marker_present}; "
                f"{row.reason}"
            ),
            action_behavior_ids=(
                row.status,
                row.summary_marker,
            ),
            capability_ids=(
                "release_residual_explanation",
                "release_gate_summary_marker",
                row.residual_id,
            ),
            maturity_gap_domain_ids=("boundary_gate",),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="release_residual_explanation",
        label="Release residual explanations",
        source_id="scene_release_residual_explanation_audit",
        lens_ids=("boundary", "evidence_chain", "product_readiness"),
        route_hint="release summary residual -> governed count -> summary marker",
        detail=(
            "Browse the residual release-gate readings that remain visible "
            "and the governing counts that explain why they are publishable."
        ),
        rows=rows,
        visible_rows=rows,
    )


def _release_acceptance_certificate_item() -> SceneMatrixDrilldownItem:
    report = _release_governance_report(
        "scene_release_acceptance_certificate_audit"
    )
    certificate_rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.certificate_id,
            label=f"{row.certificate_id} / {row.observed_ratio}",
            status=row.status,
            source_id="scene_release_acceptance_certificate_audit",
            detail=(
                f"expected={row.expected_ratio}; {row.summary}"
            ),
            action_behavior_ids=(
                row.status,
                *(
                    ("acceptance_receipt_trace",)
                    if row.certificate_id
                    in (
                        "release_residual_ratio_receipts",
                        "retained_gap_external_receipts",
                    )
                    else ()
                ),
            ),
            capability_ids=(
                row.certificate_id,
                *row.evidence_ids,
                *(
                    ("acceptance_receipt_trace",)
                    if row.certificate_id
                    in (
                        "release_residual_ratio_receipts",
                        "retained_gap_external_receipts",
                    )
                    else ()
                ),
                row.source_id,
            ),
            maturity_gap_domain_ids=("boundary_gate",),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    requirement_dimension_rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=f"requirement:{row.dimension_id}",
            label=f"{row.dimension_id} / {row.observed_ratio}",
            status=row.status,
            source_id="scene_release_acceptance_certificate_audit",
            detail=row.requirement,
            action_behavior_ids=(row.status, "requirement_dimension_trace"),
            capability_ids=(
                row.dimension_id,
                *row.evidence_ids,
                *row.source_ids,
            ),
            maturity_gap_domain_ids=("boundary_gate",),
            issue_ids=row.issue_ids,
        )
        for row in report.requirement_dimension_rows
    )
    rows = (*certificate_rows, *requirement_dimension_rows)
    return SceneMatrixDrilldownItem(
        drilldown_id="release_acceptance_certificate",
        label="Release acceptance certificate",
        source_id="scene_release_acceptance_certificate_audit",
        lens_ids=("boundary", "evidence_chain", "product_readiness"),
        route_hint="release component -> observed/expected certificate evidence",
        detail=(
            "Browse the final release certificate that binds projection parity, "
            "closure ledger, boundary envelopes, and residual ratios."
        ),
        rows=rows,
        visible_rows=rows,
    )


RELEASE_GOVERNANCE_ITEM_FACTORIES: dict[
    str,
    Callable[[], SceneMatrixDrilldownItem],
] = {
    "scene_boundary_guarded_completion_audit": _boundary_guarded_completion_item,
    "scene_residual_warning_governance_audit": _residual_warning_governance_item,
    "scene_boundary_readiness_reconciliation_audit": (
        _boundary_readiness_reconciliation_item
    ),
    "scene_terminal_release_exception_audit": _terminal_release_exception_item,
    "scene_boundary_subject_release_dossier_audit": (
        _boundary_subject_release_dossier_item
    ),
    "scene_non_subject_release_trace_attribution_audit": (
        _non_subject_release_trace_attribution_item
    ),
    "scene_release_trace_partition_guard_audit": _release_trace_partition_guard_item,
    "scene_release_projection_surface_parity_audit": (
        _release_projection_surface_parity_item
    ),
    "scene_boundary_subject_release_continuity_audit": (
        _boundary_subject_release_continuity_item
    ),
    "scene_release_closure_ledger_audit": _release_closure_ledger_item,
    "scene_boundary_maturity_release_envelope_audit": (
        _boundary_maturity_release_envelope_item
    ),
    "scene_retained_gap_exit_criteria_audit": _retained_gap_exit_criteria_item,
    "scene_release_residual_ratio_ledger_audit": (
        _release_residual_ratio_ledger_item
    ),
    "scene_release_residual_explanation_audit": (
        _release_residual_explanation_item
    ),
    "scene_release_acceptance_certificate_audit": (
        _release_acceptance_certificate_item
    ),
}


__all__ = [
    "RELEASE_GOVERNANCE_ITEM_FACTORIES",
    "_boundary_guarded_completion_item",
    "_boundary_maturity_release_envelope_item",
    "_boundary_readiness_reconciliation_item",
    "_boundary_subject_release_continuity_item",
    "_boundary_subject_release_dossier_item",
    "_non_subject_release_trace_attribution_item",
    "_release_acceptance_certificate_item",
    "_release_closure_ledger_item",
    "_release_projection_surface_parity_item",
    "_release_residual_explanation_item",
    "_release_residual_ratio_ledger_item",
    "_release_trace_partition_guard_item",
    "_residual_warning_governance_item",
    "_retained_gap_exit_criteria_item",
    "_terminal_release_exception_item",
]
