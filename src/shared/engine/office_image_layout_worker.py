"""Child-process Office COM worker for exact inline-image layout."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field, replace
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence

from lxml import etree

from src.config.image_materials import ImagePlacementMode
from src.shared.engine.office_image_layout_child_lifecycle import (
    ChildBlocked as _ChildBlocked,
    OfficeChildSession as _OfficeChildSession,
)
from src.shared.engine.office_image_layout_contracts import (
    PROVIDER_SPECS,
    LayoutFailure,
    LayoutFailureCode,
    LayoutStatus,
    LayoutWarning,
    LayoutWarningCode,
    OfficeImageJobReceipt,
    OfficeImageLayoutJob,
    OfficeImageLayoutReceipt,
    OfficeImageLayoutRequest,
    OfficeImageProvider,
    OfficeProviderSpec,
    StabilizationRoundReceipt,
    build_layout_receipt,
    job_owned_shape_id,
)
from src.shared.engine.office_image_layout_fileio import atomic_write_json
from src.shared.engine.office_image_layout_geometry import (
    DIMENSION_SEARCH_FALLBACK_OFFSETS_PT,
    DIMENSION_SEARCH_MAX_OFFSET_PT,
    MAX_ACTUAL_DIMENSION_DEVIATION_PT,
    MAX_IMAGE_PROPORTION_ERROR,
    POINTS_PER_CM,
    WORD_MIN_INLINE_DIMENSION_PT,
    ImageGeometryError,
    ImageGeometryInput,
    ImageGeometryDecision,
    compute_image_geometry,
)
from src.shared.engine.office_image_layout_inventory import (
    W_NAMESPACE,
    W_PARAGRAPH_TAG,
)

_PAGE_BREAK_RE = re.compile(
    r"<w:br\\b[^>]*\\bw:type=(?:\"|')page(?:\"|')[^>]*/?>|<w:pageBreakBefore\\b",
    re.IGNORECASE,
)

@dataclass(slots=True)
class _ChildJobState:
    request_job: OfficeImageLayoutJob
    shape: Any
    receipt: OfficeImageJobReceipt
    guard_xml_before: str
    guard_keep_before: str


@dataclass(slots=True)
class _ChildRunState:
    jobs: list[_ChildJobState] = field(default_factory=list)
    warnings: list[LayoutWarning] = field(default_factory=list)
    rounds: list[StabilizationRoundReceipt] = field(default_factory=list)
    repaginate_count: int = 0
    field_rounds: int = 0
    page_breaks_before: int = 0
    page_breaks_after: int = 0

class _BaseOfficeAdapter:
    provider: OfficeImageProvider
    adapter_name: str
    prog_id: str

    def create_application(self) -> Any:
        import win32com.client

        return win32com.client.DispatchEx(self.prog_id)

    def open_shadow(self, application: Any, path: Path) -> Any:
        return application.Documents.Open(
            str(path.resolve()),
            ReadOnly=False,
            AddToRecentFiles=False,
            Visible=False,
        )

class _WordOfficeAdapter(_BaseOfficeAdapter):
    provider = OfficeImageProvider.WORD
    adapter_name = "word_adapter_v1"
    prog_id = "Word.Application"

class _WpsOfficeAdapter(_BaseOfficeAdapter):
    provider = OfficeImageProvider.WPS
    adapter_name = "wps_adapter_v1"
    prog_id = "KWPS.Application"

_ADAPTERS: dict[OfficeImageProvider, type[_BaseOfficeAdapter]] = {
    OfficeImageProvider.WORD: _WordOfficeAdapter,
    OfficeImageProvider.WPS: _WpsOfficeAdapter,
}


def _child_execute(envelope: Mapping[str, object]) -> OfficeImageLayoutReceipt:
    request_payload = envelope.get("request")
    if not isinstance(request_payload, Mapping):
        raise ValueError("child request payload is missing")
    request = OfficeImageLayoutRequest.from_dict(request_payload)
    spec = PROVIDER_SPECS[request.provider]
    session = _OfficeChildSession(
        _ADAPTERS[request.provider](),
        Path(str(envelope["shadow_path"])),
        Path(str(envelope["pid_path"])),
        {int(value) for value in envelope.get("before_pids", ())},  # type: ignore[arg-type]
    )
    state = _ChildRunState()
    try:
        return _execute_child_layout(request, spec, session, state)
    except _ChildBlocked as exc:
        failures = (exc.failure,)
    except Exception as exc:
        failures = (
            LayoutFailure(
                LayoutFailureCode.OFFICE_ERROR,
                f"{type(exc).__name__}: {exc}",
            ),
        )
    finally:
        session.release()
    return _build_child_receipt(
        request,
        spec,
        session,
        state,
        LayoutStatus.BLOCKED,
        failures=failures,
    )


def _execute_child_layout(
    request: OfficeImageLayoutRequest,
    spec: OfficeProviderSpec,
    session: _OfficeChildSession,
    state: _ChildRunState,
) -> OfficeImageLayoutReceipt:
    document = session.open()
    state.page_breaks_before = _page_break_count(document)
    _update_fields_and_toc(document)
    state.field_rounds += 1
    document.Repaginate()
    state.repaginate_count += 1
    for request_job in request.jobs:
        job_state, job_warnings = _insert_one_job(document, request_job, request)
        state.jobs.append(job_state)
        state.warnings.extend(job_warnings)
    state.rounds, stabilized, repaginates, field_rounds = _stabilize(
        document,
        state.jobs,
        request,
    )
    state.repaginate_count += repaginates
    state.field_rounds += field_rounds
    _validate_stabilized_layout(request, state, stabilized)
    _append_readability_warnings(state)
    state.page_breaks_after = _page_break_count(document)
    if state.page_breaks_after != state.page_breaks_before:
        raise _ChildBlocked(
            LayoutFailureCode.PAGE_BREAK_MUTATED,
            "layout transaction changed the explicit page-break count",
        )
    _verify_guard_invariants(document, state.jobs)
    document.Save()
    session.close_success()
    return _build_child_receipt(
        request,
        spec,
        session,
        state,
        LayoutStatus.SUCCESS,
        save_count=1,
    )


def _validate_stabilized_layout(
    request: OfficeImageLayoutRequest,
    state: _ChildRunState,
    stabilized: bool,
) -> None:
    if stabilized:
        return
    final_receipts = {item.receipt.job_id: item.receipt for item in state.jobs}
    violated = state.rounds[-1].violation_job_ids if state.rounds else ()
    for job_id in violated:
        item = final_receipts[job_id]
        if item.co_location_claimed and not (
            item.final_guard_page == item.final_anchor_page == item.final_image_page
        ):
            raise _ChildBlocked(
                LayoutFailureCode.FINAL_COLOCATION_FAILED,
                "guard, anchor bookmark, and job-owned image did not remain on one page",
                job_id,
            )
        if not item.boundary_ok:
            raise _ChildBlocked(
                LayoutFailureCode.FINAL_BOUNDARY_FAILED,
                "job-owned image did not fit its final text container/flow boundary",
                job_id,
            )
    raise _ChildBlocked(
        LayoutFailureCode.STABILIZATION_FAILED,
        f"layout did not stabilize in {request.max_stabilization_rounds} rounds",
    )


def _append_readability_warnings(state: _ChildRunState) -> None:
    warned_jobs = {
        warning.job_id
        for warning in state.warnings
        if warning.code is LayoutWarningCode.READABILITY_RISK
    }
    for item in state.jobs:
        if item.receipt.readability_warning and item.receipt.job_id not in warned_jobs:
            state.warnings.append(
                LayoutWarning(
                    LayoutWarningCode.READABILITY_RISK,
                    "corrected image is below the configured readability dimension",
                    item.receipt.job_id,
                )
            )


def _build_child_receipt(
    request: OfficeImageLayoutRequest,
    spec: OfficeProviderSpec,
    session: _OfficeChildSession,
    state: _ChildRunState,
    status: LayoutStatus,
    *,
    save_count: int = 0,
    failures: tuple[LayoutFailure, ...] = (),
) -> OfficeImageLayoutReceipt:
    return build_layout_receipt(
        request,
        spec,
        status,
        application_pid=session.pid,
        open_count=session.open_count,
        save_count=save_count,
        repaginate_count=state.repaginate_count,
        field_rounds=state.field_rounds,
        page_breaks_before=state.page_breaks_before,
        page_breaks_after=state.page_breaks_after,
        jobs=tuple(item.receipt for item in state.jobs),
        rounds=tuple(state.rounds),
        warnings=tuple(state.warnings),
        failures=failures,
    )

@dataclass(frozen=True, slots=True)
class _ShapeDimensionDecision:
    initial_width_pt: float
    initial_height_pt: float
    initial_proportion_error: float
    actual_width_pt: float
    actual_height_pt: float
    proportion_error: float
    selected_width_offset_pt: float
    candidate_count: int
    corrected: bool


@dataclass(frozen=True, slots=True)
class _MeasuredShapeDimension:
    width_pt: float
    height_pt: float
    proportion_error: float
    score: float
    bounded: bool

    @property
    def acceptable(self) -> bool:
        return self.proportion_error <= MAX_IMAGE_PROPORTION_ERROR and self.bounded


@dataclass(slots=True)
class _InlineDimensionSearch:
    shape: Any
    target_width_pt: float
    target_height_pt: float
    aspect_ratio: float
    job_id: str
    max_width_pt: float | None
    max_height_pt: float | None
    candidate_count: int = 0
    last_offset: float | None = None

    def evaluate(self, requested_width: float) -> _MeasuredShapeDimension:
        width, height = _assign_inline_shape_dimensions(
            self.shape,
            requested_width,
            self.aspect_ratio,
            self.job_id,
        )
        self.candidate_count += 1
        error = abs(width / height - self.aspect_ratio) / self.aspect_ratio
        return _MeasuredShapeDimension(
            width,
            height,
            error,
            math.hypot(
                (width - self.target_width_pt) / self.target_width_pt,
                (height - self.target_height_pt) / self.target_height_pt,
            ),
            abs(width - self.target_width_pt) <= MAX_ACTUAL_DIMENSION_DEVIATION_PT
            and abs(height - self.target_height_pt) <= MAX_ACTUAL_DIMENSION_DEVIATION_PT
            and (self.max_width_pt is None or width <= self.max_width_pt + 0.75)
            and (self.max_height_pt is None or height <= self.max_height_pt + 0.75),
        )

    def inspect_offsets(
        self,
        offsets: Sequence[float],
        attempted: set[float],
    ) -> list[tuple[float, float, float, _MeasuredShapeDimension]]:
        viable: list[tuple[float, float, float, _MeasuredShapeDimension]] = []
        for raw_offset in offsets:
            offset = round(float(raw_offset), 2)
            if offset in attempted:
                continue
            attempted.add(offset)
            requested = self.target_width_pt + offset
            if requested <= WORD_MIN_INLINE_DIMENSION_PT:
                continue
            measured = self.evaluate(requested)
            self.last_offset = offset
            if measured.acceptable:
                viable.append((measured.score, abs(offset), offset, measured))
        return viable

def _assign_inline_shape_dimensions(
    shape: Any,
    requested_width_pt: float,
    aspect_ratio: float,
    job_id: str,
) -> tuple[float, float]:
    try:
        # WPS quantizes the auto-derived second dimension differently from an
        # explicitly assigned point value.  Assign both dimensions while
        # unlocked, then restore the aspect lock for subsequent Office layout.
        shape.LockAspectRatio = 0
        shape.Width = requested_width_pt
        actual_width = float(shape.Width)
        shape.Height = actual_width / aspect_ratio
        shape.LockAspectRatio = -1
        return float(shape.Width), float(shape.Height)
    except Exception as exc:
        raise _ChildBlocked(
            LayoutFailureCode.OFFICE_ERROR,
            f"cannot set job-owned image dimensions: {exc}",
            job_id,
        ) from exc

def _set_inline_shape_dimensions(
    shape: Any,
    target_width_pt: float,
    target_height_pt: float,
    aspect_ratio: float,
    job_id: str,
    *,
    max_width_pt: float | None = None,
    max_height_pt: float | None = None,
) -> _ShapeDimensionDecision:
    search = _InlineDimensionSearch(
        shape,
        target_width_pt,
        target_height_pt,
        aspect_ratio,
        job_id,
        max_width_pt,
        max_height_pt,
    )
    initial = search.evaluate(target_width_pt)
    if initial.acceptable:
        return _dimension_decision(initial, initial, 0.0, search.candidate_count, False)
    desired_height = initial.width_pt / aspect_ratio
    direction = 1.0 if desired_height >= initial.height_pt else -1.0
    attempted: set[float] = set()
    viable = search.inspect_offsets(
        (-direction * 0.25, direction * 0.75),
        attempted,
    )
    if not viable:
        viable = search.inspect_offsets(DIMENSION_SEARCH_FALLBACK_OFFSETS_PT, attempted)
    if viable:
        _score, _absolute_offset, offset, measured = min(viable, key=lambda item: item[:3])
        if offset == search.last_offset:
            return _dimension_decision(
                initial, measured, offset, search.candidate_count, True
            )
        final = search.evaluate(target_width_pt + offset)
        if final.acceptable:
            return _dimension_decision(initial, final, offset, search.candidate_count, True)
    # One bounded retry pass handles provider hysteresis if reapplying the
    # selected request moved to a different point bucket.
    for _score, _absolute_offset, offset, _measured in sorted(
        viable, key=lambda item: item[:3]
    ):
        final = search.evaluate(target_width_pt + offset)
        if final.acceptable:
            return _dimension_decision(initial, final, offset, search.candidate_count, True)
    raise _ChildBlocked(
        LayoutFailureCode.PROPORTION_CHANGED,
        "Office point quantization has no bounded image dimension solution; "
        f"target={target_width_pt:.4f}x{target_height_pt:.4f}pt, "
        f"initial={initial.width_pt:.4f}x{initial.height_pt:.4f}pt, "
        f"ratio_error={initial.proportion_error:.6f}, search=\u00b1"
        f"{DIMENSION_SEARCH_MAX_OFFSET_PT:g}pt bounded candidates",
        job_id,
    )


def _dimension_decision(
    initial: _MeasuredShapeDimension,
    final: _MeasuredShapeDimension,
    offset: float,
    candidate_count: int,
    corrected: bool,
) -> _ShapeDimensionDecision:
    return _ShapeDimensionDecision(
        initial.width_pt,
        initial.height_pt,
        initial.proportion_error,
        final.width_pt,
        final.height_pt,
        final.proportion_error,
        offset,
        candidate_count,
        corrected,
    )


@dataclass(frozen=True, slots=True)
class _JobAnchorMeasurement:
    anchor: Any
    anchor_start: int
    anchor_page: int
    anchor_y: float
    guard_page: int | None
    guard_xml: str
    guard_keep: str
    section: Any
    column_index: int
    column_count: int
    container_width: float
    flow_bottom: float
    paragraph_reserve: float


def _insert_one_job(
    document: Any,
    job: OfficeImageLayoutJob,
    request: OfficeImageLayoutRequest,
) -> tuple[_ChildJobState, list[LayoutWarning]]:
    plan = job.plan
    strict = plan.placement.mode is ImagePlacementMode.FIT_REMAINING_ANCHOR_PAGE
    measurement = _measure_job_anchor(document, job, strict)
    geometry = _compute_job_geometry(job, request, measurement)
    shape, shape_id, dimension = _insert_job_shape(
        document,
        job,
        measurement,
        geometry,
        strict,
    )
    receipt = _build_job_receipt(
        job,
        request,
        measurement,
        geometry,
        dimension,
        shape_id,
        strict,
    )
    state = _ChildJobState(
        job,
        shape,
        receipt,
        measurement.guard_xml,
        measurement.guard_keep,
    )
    return state, _job_layout_warnings(job, geometry)


def _measure_job_anchor(
    document: Any,
    job: OfficeImageLayoutJob,
    strict: bool,
) -> _JobAnchorMeasurement:
    plan = job.plan
    anchor = _bookmark_range(document, plan.anchor.stable_marker_id, plan.job_id)
    anchor_start = int(anchor.Start)
    if job.expected_anchor_start is not None and anchor_start != job.expected_anchor_start:
        raise _ChildBlocked(
            LayoutFailureCode.RANGE_START_MISMATCH,
            f"anchor Range.Start={anchor_start}, expected {job.expected_anchor_start}",
            plan.job_id,
        )
    _validate_range_surface(document, anchor, plan.job_id)
    _scroll(document, anchor)
    anchor_page = _range_info_int(anchor, 3)
    anchor_y = _range_info_float(anchor, 6)
    if anchor_page < 1 or anchor_y < 0:
        raise _ChildBlocked(
            LayoutFailureCode.INVALID_GEOMETRY,
            f"invalid anchor page/y: {anchor_page}/{anchor_y}",
            plan.job_id,
        )
    guard_page, guard_xml, guard_keep = (
        _measure_strict_guard(document, job, anchor_start, anchor_page)
        if strict
        else (None, "", "")
    )
    if strict and (int(document.Footnotes.Count) or int(document.Endnotes.Count)):
        raise _ChildBlocked(
            LayoutFailureCode.UNSUPPORTED_SURFACE,
            "footnote/endnote flow is not modeled",
            plan.job_id,
        )
    section, column_index, column_count, container_width = _column_geometry(anchor)
    setup = section.PageSetup
    flow_bottom = float(setup.PageHeight) - float(setup.BottomMargin)
    reserve = _paragraph_reserve(anchor.Paragraphs.Item(1))
    return _JobAnchorMeasurement(
        anchor,
        anchor_start,
        anchor_page,
        anchor_y,
        guard_page,
        guard_xml,
        guard_keep,
        section,
        column_index,
        column_count,
        container_width,
        flow_bottom,
        reserve,
    )


def _measure_strict_guard(
    document: Any,
    job: OfficeImageLayoutJob,
    anchor_start: int,
    anchor_page: int,
) -> tuple[int, str, str]:
    plan = job.plan
    guard = _bookmark_range(document, plan.anchor.guard_marker_id, plan.job_id)
    _validate_range_surface(document, guard, plan.job_id)
    _scroll(document, guard)
    guard_page = _range_info_int(guard, 3)
    if guard_page != anchor_page:
        raise _ChildBlocked(
            LayoutFailureCode.GUARD_PAGE_MISMATCH,
            f"measurement guard page {guard_page} != anchor page {anchor_page}",
            plan.job_id,
        )
    if int(guard.Start) >= anchor_start:
        raise _ChildBlocked(
            LayoutFailureCode.GUARD_ORDER_INVALID,
            "guard bookmark must precede the anchor Range.Start",
            plan.job_id,
        )
    paragraph = guard.Paragraphs.Item(1)
    if not str(paragraph.Range.Text or "").strip("\r\a \t"):
        raise _ChildBlocked(
            LayoutFailureCode.GUARD_ORDER_INVALID,
            "guard paragraph is empty",
            plan.job_id,
        )
    return guard_page, _guard_paragraph_xml_hash(paragraph), _paragraph_keep_hash(paragraph)


def _compute_job_geometry(
    job: OfficeImageLayoutJob,
    request: OfficeImageLayoutRequest,
    measurement: _JobAnchorMeasurement,
) -> ImageGeometryDecision:
    placement = job.plan.placement
    try:
        return compute_image_geometry(
            ImageGeometryInput(
                mode=placement.mode,
                source_width_px=job.prepared_image.width_px,
                source_height_px=job.prepared_image.height_px,
                container_width_pt=measurement.container_width,
                anchor_y_pt=measurement.anchor_y,
                flow_bottom_pt=measurement.flow_bottom,
                paragraph_reserve_pt=measurement.paragraph_reserve,
                safety_margin_pt=request.safety_margin_pt,
                fixed_width_pt=(
                    None
                    if placement.fixed_width_cm is None
                    else placement.fixed_width_cm * POINTS_PER_CM
                ),
                max_width_pt=(
                    None
                    if placement.max_width_cm is None
                    else placement.max_width_cm * POINTS_PER_CM
                ),
                readability_min_dimension_pt=request.readability_min_dimension_pt,
            )
        )
    except ImageGeometryError as exc:
        raise _ChildBlocked(exc.code, str(exc), job.job_id) from exc


def _insert_job_shape(
    document: Any,
    job: OfficeImageLayoutJob,
    measurement: _JobAnchorMeasurement,
    geometry: ImageGeometryDecision,
    strict: bool,
) -> tuple[Any, str, _ShapeDimensionDecision]:
    plan = job.plan
    shape_id = job_owned_shape_id(plan.job_id)
    insertion = document.Range(measurement.anchor_start, measurement.anchor_start)
    shape = document.InlineShapes.AddPicture(
        str(Path(job.prepared_image.output_path).resolve()),
        False,
        True,
        insertion,
    )
    try:
        # The insertion point can precede a hidden sentinel run.  Office copies
        # that character formatting onto the new drawing run unless the
        # job-owned shape range is explicitly made visible.  Restricting the
        # assignment to shape.Range lets Word split runs as needed and does not
        # reveal the sentinel text that follows it.
        shape.Range.Font.Hidden = False
        if int(shape.Range.Font.Hidden) != 0:
            raise ValueError("Office kept the image range hidden")
    except Exception as exc:
        raise _ChildBlocked(
            LayoutFailureCode.JOB_IMAGE_HIDDEN,
            f"cannot make job-owned image range visible: {exc}",
            plan.job_id,
        ) from exc
    dimension = _set_inline_shape_dimensions(
        shape,
        geometry.target_width_pt,
        geometry.target_height_pt,
        geometry.aspect_ratio,
        plan.job_id,
        max_width_pt=geometry.width_cap_pt,
        max_height_pt=geometry.available_height_pt,
    )
    shape.AlternativeText = shape_id
    shape.Title = plan.job_id
    if dimension.proportion_error > MAX_IMAGE_PROPORTION_ERROR:
        raise _ChildBlocked(
            LayoutFailureCode.PROPORTION_CHANGED,
            "Office changed image aspect ratio by "
            f"{dimension.proportion_error:.6f}; target={geometry.target_width_pt:.4f}x"
            f"{geometry.target_height_pt:.4f}pt, actual={dimension.actual_width_pt:.4f}x"
            f"{dimension.actual_height_pt:.4f}pt",
            plan.job_id,
        )
    bookmark_position = int(shape.Range.Start) if strict else int(shape.Range.End)
    _replace_bookmark(document, plan.anchor.stable_marker_id, bookmark_position)
    return shape, shape_id, dimension


def _job_layout_warnings(
    job: OfficeImageLayoutJob,
    geometry: ImageGeometryDecision,
) -> list[LayoutWarning]:
    placement = job.plan.placement
    warnings: list[LayoutWarning] = []
    if geometry.readability_warning:
        warnings.append(
            LayoutWarning(
                LayoutWarningCode.READABILITY_RISK,
                "contained image is below the configured readability dimension",
                job.job_id,
            )
        )
    if placement.mode in {
        ImagePlacementMode.FIXED_BOX_FLOW,
        ImagePlacementMode.FIT_CONTAINER_FLOW,
    }:
        warnings.append(
            LayoutWarning(
                LayoutWarningCode.FIXED_FLOW_NO_COLOCATION_CLAIM,
                f"{placement.mode.value} participates in normal flow and makes "
                "no group same-page claim",
                job.job_id,
            )
        )
    return warnings


def _build_job_receipt(
    job: OfficeImageLayoutJob,
    request: OfficeImageLayoutRequest,
    measurement: _JobAnchorMeasurement,
    geometry: ImageGeometryDecision,
    dimension: _ShapeDimensionDecision,
    shape_id: str,
    strict: bool,
) -> OfficeImageJobReceipt:
    plan = job.plan
    return OfficeImageJobReceipt(
        job_id=plan.job_id,
        mode=plan.placement.mode,
        sequence=plan.sequence,
        shape_id=shape_id,
        source_image_sha256=plan.image_ref.content_sha256,
        prepared_image_sha256=job.prepared_image.output_sha256,
        measurement_guard_page=measurement.guard_page,
        measurement_anchor_page=measurement.anchor_page,
        measurement_anchor_start=measurement.anchor_start,
        anchor_y_pt=measurement.anchor_y,
        section_index=int(measurement.section.Index),
        column_index=measurement.column_index,
        column_count=measurement.column_count,
        container_width_pt=measurement.container_width,
        flow_bottom_pt=measurement.flow_bottom,
        paragraph_reserve_pt=measurement.paragraph_reserve,
        safety_margin_pt=request.safety_margin_pt,
        available_height_pt=geometry.available_height_pt,
        width_cap_pt=geometry.width_cap_pt,
        initial_target_width_pt=geometry.target_width_pt,
        initial_target_height_pt=geometry.target_height_pt,
        initial_scale_ratio=geometry.scale_ratio_96dpi,
        readability_warning=geometry.readability_warning,
        co_location_claimed=strict,
        guard_xml_sha256_before=measurement.guard_xml,
        guard_keep_sha256_before=measurement.guard_keep,
        correction_count=1 if dimension.corrected else 0,
        initial_actual_width_pt=dimension.initial_width_pt,
        initial_actual_height_pt=dimension.initial_height_pt,
        initial_proportion_error=dimension.initial_proportion_error,
        dimension_candidate_count=dimension.candidate_count,
        selected_width_offset_pt=dimension.selected_width_offset_pt,
    )

def _stabilize(
    document: Any,
    jobs: list[_ChildJobState],
    request: OfficeImageLayoutRequest,
) -> tuple[list[StabilizationRoundReceipt], bool, int, int]:
    rounds: list[StabilizationRoundReceipt] = []
    previous_state = ""
    repaginates = 0
    field_rounds = 0
    for round_index in range(1, request.max_stabilization_rounds + 1):
        field_update_count = _update_fields_and_toc(document)
        field_rounds += 1
        document.Repaginate()
        repaginates += 1
        page_count = int(document.ComputeStatistics(2))
        violations: list[_ChildJobState] = []
        page_rows: list[tuple[str, int | None, int | None, int | None]] = []
        shapes_by_id = _index_inline_shapes(document)
        for state in jobs:
            final, violation = _verify_job(document, state, shapes_by_id)
            state.receipt = final
            page_rows.append(
                (
                    final.job_id,
                    final.final_guard_page,
                    final.final_anchor_page,
                    final.final_image_page,
                )
            )
            if violation:
                violations.append(state)
        state_payload = {
            "page_count": page_count,
            "pages": page_rows,
            "text_sha256": _sha_text(str(document.Content.Text or "")),
        }
        state_hash = _sha_text(
            json.dumps(state_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        )
        corrected: list[str] = []
        if violations and round_index < request.max_stabilization_rounds:
            for state in violations:
                if not state.receipt.co_location_claimed:
                    continue
                _shrink_violating_job(
                    state,
                    request.correction_shrink_factor,
                    request.readability_min_dimension_pt,
                )
                corrected.append(state.receipt.job_id)
        stable = not violations and bool(previous_state) and state_hash == previous_state
        earliest = ""
        if violations:
            indexes = [jobs.index(item) for item in violations]
            earliest = jobs[min(indexes)].receipt.job_id
        rounds.append(
            StabilizationRoundReceipt(
                round_index=round_index,
                page_count=page_count,
                field_update_count=field_update_count,
                job_pages=tuple(page_rows),
                violation_job_ids=tuple(item.receipt.job_id for item in violations),
                corrected_job_ids=tuple(corrected),
                revalidate_from_job_id=earliest,
                state_sha256=state_hash,
                stable=stable,
            )
        )
        if stable:
            return rounds, True, repaginates, field_rounds
        previous_state = "" if violations else state_hash
    return rounds, False, repaginates, field_rounds

def _verify_job(
    document: Any,
    state: _ChildJobState,
    shapes_by_id: Mapping[str, Sequence[Any]],
) -> tuple[OfficeImageJobReceipt, bool]:
    receipt = state.receipt
    owned = tuple(shapes_by_id.get(receipt.shape_id, ()))
    if len(owned) != 1:
        raise _ChildBlocked(
            LayoutFailureCode.SHAPE_OWNERSHIP_INVALID,
            f"expected one job-owned InlineShape, found {len(owned)}",
            receipt.job_id,
        )
    shape = owned[0]
    if str(shape.Title or "") != receipt.job_id:
        raise _ChildBlocked(
            LayoutFailureCode.SHAPE_OWNERSHIP_INVALID,
            "job-owned image title no longer matches its job",
            receipt.job_id,
        )
    anchor = _bookmark_range(
        document,
        state.request_job.plan.anchor.stable_marker_id,
        receipt.job_id,
    )
    _scroll(document, anchor)
    anchor_page = _range_info_int(anchor, 3)
    image_range = shape.Range
    _scroll(document, image_range)
    image_page = _range_info_int(image_range, 3)
    image_y = _range_info_float(image_range, 6)
    guard_page: int | None = None
    if receipt.co_location_claimed:
        guard = _bookmark_range(
            document,
            state.request_job.plan.anchor.guard_marker_id,
            receipt.job_id,
        )
        _scroll(document, guard)
        guard_page = _range_info_int(guard, 3)
    _section, _column, _count, container = _column_geometry(image_range)
    width = float(shape.Width)
    height = float(shape.Height)
    aspect = (
        float(state.request_job.prepared_image.width_px)
        / float(state.request_job.prepared_image.height_px)
    )
    proportion_error = abs(width / height - aspect) / aspect
    if proportion_error > MAX_IMAGE_PROPORTION_ERROR:
        raise _ChildBlocked(
            LayoutFailureCode.PROPORTION_CHANGED,
            "job-owned image aspect ratio changed by "
            f"{proportion_error:.6f}; actual={width:.4f}x{height:.4f}pt",
            receipt.job_id,
        )
    boundary_ok = width <= container + 0.75
    if receipt.co_location_claimed:
        boundary_ok = boundary_ok and image_y >= 0 and (
            image_y + height <= receipt.flow_bottom_pt + 0.75
        )
    colocation_ok = (
        not receipt.co_location_claimed
        or guard_page == anchor_page == image_page
    )
    violation = (
        not boundary_ok
        or not colocation_ok
        or proportion_error > MAX_IMAGE_PROPORTION_ERROR
    )
    return (
        replace(
            receipt,
            final_guard_page=guard_page,
            final_anchor_page=anchor_page,
            final_image_page=image_page,
            final_image_y_pt=image_y,
            final_width_pt=width,
            final_height_pt=height,
            proportion_error=proportion_error,
            boundary_ok=boundary_ok,
        ),
        violation,
    )

def _index_inline_shapes(document: Any) -> dict[str, tuple[Any, ...]]:
    indexed: dict[str, list[Any]] = {}
    collection = document.InlineShapes
    for index in range(1, int(collection.Count) + 1):
        shape = collection.Item(index)
        shape_id = str(shape.AlternativeText or "")
        indexed.setdefault(shape_id, []).append(shape)
    return {shape_id: tuple(shapes) for shape_id, shapes in indexed.items()}

def _shrink_violating_job(
    state: _ChildJobState,
    factor: float,
    readability_min_dimension_pt: float,
) -> None:
    shape = state.shape
    current_width = float(shape.Width)
    new_width = current_width * factor
    aspect = (
        float(state.request_job.prepared_image.width_px)
        / float(state.request_job.prepared_image.height_px)
    )
    new_height = new_width / aspect
    if min(new_width, new_height) < WORD_MIN_INLINE_DIMENSION_PT:
        raise _ChildBlocked(
            LayoutFailureCode.BELOW_WORD_MINIMUM,
            "correction would reduce image below Word's inline minimum",
            state.receipt.job_id,
        )
    _set_inline_shape_dimensions(
        shape,
        new_width,
        new_height,
        aspect,
        state.receipt.job_id,
        max_width_pt=state.receipt.container_width_pt,
    )
    state.receipt = replace(
        state.receipt,
        correction_count=state.receipt.correction_count + 1,
        readability_warning=(
            state.receipt.readability_warning
            or min(new_width, new_height) < readability_min_dimension_pt
        ),
    )

def _verify_guard_invariants(document: Any, jobs: Sequence[_ChildJobState]) -> None:
    for state in jobs:
        if not state.receipt.co_location_claimed:
            continue
        guard = _bookmark_range(
            document,
            state.request_job.plan.anchor.guard_marker_id,
            state.receipt.job_id,
        )
        paragraph = guard.Paragraphs.Item(1)
        xml_after = _guard_paragraph_xml_hash(paragraph)
        keep_after = _paragraph_keep_hash(paragraph)
        state.receipt = replace(
            state.receipt,
            guard_xml_sha256_after=xml_after,
            guard_keep_sha256_after=keep_after,
        )
        if xml_after != state.guard_xml_before or keep_after != state.guard_keep_before:
            raise _ChildBlocked(
                LayoutFailureCode.GUARD_MUTATED,
                "guard paragraph XML or keep properties changed",
                state.receipt.job_id,
            )

def _validate_range_surface(document: Any, target: Any, job_id: str) -> None:
    if int(target.StoryType) != 1 or bool(target.Information(12)):
        raise _ChildBlocked(
            LayoutFailureCode.UNSUPPORTED_SURFACE,
            "only ordinary main-story body paragraphs are supported",
            job_id,
        )
    if int(target.Paragraphs.Count) != 1 or int(target.Sections.Count) != 1:
        raise _ChildBlocked(
            LayoutFailureCode.UNSUPPORTED_SURFACE,
            "anchor must resolve to exactly one ordinary paragraph and section",
            job_id,
        )
    paragraph = target.Paragraphs.Item(1)
    start = int(paragraph.Range.Start)
    end = int(paragraph.Range.End)
    for index in range(1, int(document.Shapes.Count) + 1):
        shape = document.Shapes.Item(index)
        try:
            anchor_start = int(shape.Anchor.Start)
        except Exception:
            continue
        if start <= anchor_start < end:
            raise _ChildBlocked(
                LayoutFailureCode.UNSUPPORTED_SURFACE,
                "floating/wrapped shape is anchored to the target paragraph",
                job_id,
            )

def _bookmark_range(document: Any, name: str, job_id: str) -> Any:
    if not name or not bool(document.Bookmarks.Exists(name)):
        raise _ChildBlocked(
            LayoutFailureCode.BOOKMARK_MISSING,
            f"bookmark {name!r} is unavailable in Office",
            job_id,
        )
    return document.Bookmarks.Item(name).Range.Duplicate

def _replace_bookmark(document: Any, name: str, position: int) -> None:
    if bool(document.Bookmarks.Exists(name)):
        document.Bookmarks.Item(name).Delete()
    document.Bookmarks.Add(name, document.Range(position, position))

def _column_geometry(target: Any) -> tuple[Any, int, int, float]:
    x = _range_info_float(target, 5)
    if x < 0 or not math.isfinite(x):
        raise _ChildBlocked(LayoutFailureCode.INVALID_GEOMETRY, f"invalid anchor X {x}")
    section = target.Sections.Item(1)
    setup = section.PageSetup
    columns = setup.TextColumns
    count = int(columns.Count)
    left = float(setup.LeftMargin)
    starts: list[float] = []
    widths: list[float] = []
    cursor = left
    for index in range(1, count + 1):
        column = columns.Item(index)
        width = float(column.Width)
        if width <= 0 or not math.isfinite(width):
            raise _ChildBlocked(LayoutFailureCode.INVALID_GEOMETRY, "invalid column width")
        starts.append(cursor)
        widths.append(width)
        try:
            spacing = max(0.0, float(column.SpaceAfter))
        except Exception:
            spacing = 0.0
        cursor += width + spacing
    best = min(range(count), key=lambda index: abs(x - starts[index]))
    for index, (start, width) in enumerate(zip(starts, widths, strict=True)):
        if start - 1 <= x <= start + width + 1:
            best = index
            break
    return section, best + 1, count, widths[best]

def _paragraph_reserve(paragraph: Any) -> float:
    try:
        font_size = float(paragraph.Range.Font.Size)
    except Exception:
        font_size = 12.0
    if not 1 <= font_size <= 200:
        font_size = 12.0
    try:
        line_spacing = float(paragraph.Format.LineSpacing)
    except Exception:
        line_spacing = 0.0
    if not 1 <= line_spacing <= 300:
        line_spacing = 0.0
    try:
        space_after = float(paragraph.Format.SpaceAfter)
    except Exception:
        space_after = 0.0
    if not 0 <= space_after <= 300:
        space_after = 0.0
    return min(300.0, max(6.0, font_size * 1.2, line_spacing) + space_after)

def _paragraph_keep_hash(paragraph: Any) -> str:
    values = {
        "keep_with_next": int(paragraph.Format.KeepWithNext),
        "keep_together": int(paragraph.Format.KeepTogether),
        "page_break_before": int(paragraph.Format.PageBreakBefore),
        "widow_control": int(paragraph.Format.WidowControl),
    }
    return _sha_text(json.dumps(values, sort_keys=True, separators=(",", ":")))

def _guard_paragraph_xml_hash(paragraph: Any) -> str:
    raw = str(paragraph.Range.WordOpenXML)
    try:
        root = etree.fromstring(raw.encode("utf-8"))
        node = root if root.tag == W_PARAGRAPH_TAG else next(root.iter(W_PARAGRAPH_TAG))
        # Word rewrites revision-session ids when an unrelated range is edited.
        # They are not paragraph content or formatting and cannot be treated as
        # evidence that the guarded title moved/changed.
        for element in node.iter():
            for attribute in tuple(element.attrib):
                qname = etree.QName(attribute)
                if qname.namespace == W_NAMESPACE and qname.localname.startswith("rsid"):
                    del element.attrib[attribute]
        canonical = etree.tostring(node, method="c14n", with_comments=False)
        return sha256(canonical).hexdigest()
    except Exception:
        return _sha_text(raw)

def _update_fields_and_toc(document: Any) -> int:
    updated = int(document.Fields.Count)
    document.Fields.Update()
    for index in range(1, int(document.TablesOfContents.Count) + 1):
        toc = document.TablesOfContents.Item(index)
        toc.Update()
        toc.UpdatePageNumbers()
        updated += 1
    return updated

def _page_break_count(document: Any) -> int:
    return len(_PAGE_BREAK_RE.findall(str(document.Content.WordOpenXML)))

def _scroll(document: Any, target: Any) -> None:
    try:
        document.ActiveWindow.ScrollIntoView(target, True)
    except Exception:
        # WPS intermittently rejects a reverse scroll even though its live
        # Range.Information page/Y values remain available in Print Layout.
        # Geometry is still validated immediately after this best-effort call.
        pass

def _range_info_int(target: Any, constant: int) -> int:
    return int(target.Information(constant))

def _range_info_float(target: Any, constant: int) -> float:
    return float(target.Information(constant))

def _sha_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()

def _child_main(request_path: Path) -> int:
    envelope = json.loads(request_path.read_text(encoding="utf-8"))
    result_path = Path(str(envelope["result_path"]))
    try:
        receipt = _child_execute(envelope)
        atomic_write_json(result_path, receipt.to_dict())
        return 0
    except Exception as exc:
        request = OfficeImageLayoutRequest.from_dict(envelope["request"])
        spec = PROVIDER_SPECS[request.provider]
        receipt = build_layout_receipt(
            request,
            spec,
            LayoutStatus.CHILD_FAILED,
            failures=(
                LayoutFailure(
                    LayoutFailureCode.CHILD_PROTOCOL_ERROR,
                    f"{type(exc).__name__}: {exc}",
                ),
            ),
        )
        atomic_write_json(result_path, receipt.to_dict())
        return 1

def run_office_image_layout_child(request_path: str | Path) -> int:
    """Run the internal broker child before any GUI initialization."""

    return _child_main(Path(request_path))

def module_main(argv: Sequence[str]) -> int:
    if len(argv) == 2 and argv[0] == "--child-request":
        return _child_main(Path(argv[1]))
    raise SystemExit("office_image_layout is internal; use scripts/run_office_image_layout.py")

__all__ = ["module_main", "run_office_image_layout_child"]
