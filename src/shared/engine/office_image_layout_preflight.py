"""Static parent-side validation for an Office image-layout request."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from src.config.image_materials import ImageCoLocationGuard, ImagePlacementMode
from src.shared.engine.office_image_layout_contracts import (
    LayoutFailure,
    LayoutFailureCode,
    OfficeImageLayoutJob,
    OfficeImageLayoutRequest,
)
from src.shared.engine.office_image_layout_fileio import (
    safe_file_sha256,
    safe_file_size,
)
from src.shared.engine.office_image_layout_inventory import (
    OFFICE_DOCX_PACKAGE_LIMITS,
    W_BOOKMARK_NAME_ATTRIBUTE,
    W_BOOKMARK_START_TAG,
    W_PARAGRAPH_TAG,
    W_TABLE_CELL_TAG,
    WP_ANCHOR_TAG,
    xml_ancestor,
)
from src.shared.io.safe_docx_package import DocxPackageError, SafeDocxPackage


@dataclass(frozen=True, slots=True)
class _BookmarkEvidence:
    name: str
    part: str
    path: str
    in_table: bool
    has_floating: bool
    paragraph_text: str
    order: int


def parent_preflight(
    request: OfficeImageLayoutRequest,
) -> tuple[list[LayoutFailure], list[tuple[str, str]]]:
    source = Path(request.source_docx_path)
    if not source.is_file():
        return [LayoutFailure(LayoutFailureCode.SOURCE_DOCX_MISSING, str(source))], []
    failures = _preflight_source_identity(request, source)
    job_failures, identities, fit_by_anchor, jobs_by_anchor = _preflight_jobs(
        request.jobs
    )
    failures.extend(job_failures)
    failures.extend(_preflight_anchor_groups(fit_by_anchor, jobs_by_anchor))
    if not failures:
        failures.extend(_preflight_bookmarks(source, request.jobs))
    return failures, identities


def _preflight_source_identity(
    request: OfficeImageLayoutRequest,
    source: Path,
) -> list[LayoutFailure]:
    source_hash = safe_file_sha256(source)
    if (
        safe_file_size(source) == request.source_docx_size
        and source_hash == request.source_docx_sha256
    ):
        return []
    return [
        LayoutFailure(
            LayoutFailureCode.SOURCE_DOCX_IDENTITY_MISMATCH,
            "source DOCX size/hash no longer matches the request",
        )
    ]


def _preflight_jobs(
    jobs: Sequence[OfficeImageLayoutJob],
) -> tuple[
    list[LayoutFailure],
    list[tuple[str, str]],
    dict[str, int],
    dict[str, list[OfficeImageLayoutJob]],
]:
    failures: list[LayoutFailure] = []
    identities: list[tuple[str, str]] = []
    seen_jobs: set[str] = set()
    fit_by_anchor: dict[str, int] = {}
    jobs_by_anchor: dict[str, list[OfficeImageLayoutJob]] = {}
    for job in jobs:
        if job.job_id in seen_jobs:
            failures.append(
                LayoutFailure(
                    LayoutFailureCode.DUPLICATE_JOB_ID,
                    "job ids must be unique",
                    job.job_id,
                )
            )
        seen_jobs.add(job.job_id)
        identity, identity_failures = _preflight_job_identity(job)
        identities.append(identity)
        failures.extend(identity_failures)
        failures.extend(_preflight_job_policy(job))
        anchor_name = job.plan.anchor.stable_marker_id
        jobs_by_anchor.setdefault(anchor_name, []).append(job)
        if job.plan.placement.mode is ImagePlacementMode.FIT_REMAINING_ANCHOR_PAGE:
            fit_by_anchor[anchor_name] = fit_by_anchor.get(anchor_name, 0) + 1
    return failures, identities, fit_by_anchor, jobs_by_anchor


def _preflight_job_identity(
    job: OfficeImageLayoutJob,
) -> tuple[tuple[str, str], list[LayoutFailure]]:
    plan = job.plan
    prepared = job.prepared_image
    source_image = Path(plan.image_ref.source_path)
    source_image_hash = safe_file_sha256(source_image)
    prepared_path = Path(prepared.output_path)
    prepared_hash = safe_file_sha256(prepared_path)
    failures: list[LayoutFailure] = []
    if (
        not source_image.is_file()
        or safe_file_size(source_image) != plan.image_ref.byte_size
        or source_image_hash != plan.image_ref.content_sha256
        or prepared.source_sha256 != plan.image_ref.content_sha256
    ):
        failures.append(
            LayoutFailure(
                LayoutFailureCode.SOURCE_IMAGE_IDENTITY_MISMATCH,
                "source image identity no longer matches the resolved plan",
                plan.job_id,
            )
        )
    if not prepared_path.is_file() or prepared_hash != prepared.output_sha256:
        failures.append(
            LayoutFailure(
                LayoutFailureCode.PREPARED_IMAGE_IDENTITY_MISMATCH,
                "prepared image identity no longer matches its receipt",
                plan.job_id,
            )
        )
    return (source_image_hash, prepared_hash), failures


def _preflight_job_policy(job: OfficeImageLayoutJob) -> list[LayoutFailure]:
    plan = job.plan
    failures: list[LayoutFailure] = []
    if (
        not plan.placement.contain
        or plan.placement.allow_crop
        or plan.placement.allow_move_preceding_text
        or plan.placement.allow_page_break
    ):
        failures.append(
            LayoutFailure(
                LayoutFailureCode.INVALID_REQUEST,
                "Office image layout requires contain=true and forbids crop, text moves, and page breaks",
                plan.job_id,
            )
        )
    if plan.placement.mode is ImagePlacementMode.FIT_REMAINING_ANCHOR_PAGE:
        if (
            plan.placement.co_location_guard
            is not ImageCoLocationGuard.PRECEDING_NONEMPTY_PARAGRAPH
            or not plan.anchor.guard_marker_id
        ):
            failures.append(
                LayoutFailure(
                    LayoutFailureCode.GUARD_REQUIRED,
                    "fit_remaining_anchor_page requires a preceding paragraph guard bookmark",
                    plan.job_id,
                )
            )
    return failures


def _preflight_anchor_groups(
    fit_by_anchor: Mapping[str, int],
    jobs_by_anchor: Mapping[str, Sequence[OfficeImageLayoutJob]],
) -> list[LayoutFailure]:
    failures: list[LayoutFailure] = []
    for anchor, count in fit_by_anchor.items():
        if count > 1 or len(jobs_by_anchor.get(anchor, ())) > 1:
            failures.append(
                LayoutFailure(
                    LayoutFailureCode.DUPLICATE_STRICT_ANCHOR,
                    "strict fit supports exactly one image for one anchor",
                    jobs_by_anchor[anchor][0].job_id,
                )
            )
    for anchor, jobs in jobs_by_anchor.items():
        if len(jobs) <= 1:
            continue
        flow_modes = {
            ImagePlacementMode.NATURAL_SIZE,
            ImagePlacementMode.FIT_CONTAINER_FLOW,
            ImagePlacementMode.FIXED_BOX_FLOW,
        }
        if any(job.plan.placement.mode not in flow_modes for job in jobs):
            failures.append(
                LayoutFailure(
                    LayoutFailureCode.DUPLICATE_STRICT_ANCHOR,
                    "only flow placement may share an anchor",
                    jobs[0].job_id,
                )
            )
            continue
        sequences = [job.plan.sequence for job in jobs]
        if (
            any(value is None for value in sequences)
            or len(set(sequences)) != len(sequences)
            or sequences != sorted(sequences)  # type: ignore[arg-type]
        ):
            failures.append(
                LayoutFailure(
                    LayoutFailureCode.INVALID_FLOW_SEQUENCE,
                    "shared flow jobs require unique ascending sequences",
                    jobs[0].job_id,
                )
            )
    return failures


def _preflight_bookmarks(
    source: Path,
    jobs: Sequence[OfficeImageLayoutJob],
) -> list[LayoutFailure]:
    requested = {
        name
        for job in jobs
        for name in (
            job.plan.anchor.stable_marker_id,
            job.plan.anchor.guard_marker_id,
        )
        if name
    }
    try:
        found, failures = _scan_bookmark_evidence(source, jobs, requested)
    except DocxPackageError as exc:
        return [
            LayoutFailure(
                LayoutFailureCode.INVALID_REQUEST,
                f"invalid DOCX package [{exc.code}]: {exc}",
            )
        ]
    failures.extend(_validate_bookmark_occurrences(found, jobs))
    failures.extend(_validate_strict_guard_order(found, jobs))
    return failures


def _scan_bookmark_evidence(
    source: Path,
    jobs: Sequence[OfficeImageLayoutJob],
    requested: set[str],
) -> tuple[dict[str, list[_BookmarkEvidence]], list[LayoutFailure]]:
    found: dict[str, list[_BookmarkEvidence]] = {name: [] for name in requested}
    failures: list[LayoutFailure] = []
    package = SafeDocxPackage.open_path(source, limits=OFFICE_DOCX_PACKAGE_LIMITS)
    part_names = set(package.part_names)
    strict = any(
        job.plan.placement.mode is ImagePlacementMode.FIT_REMAINING_ANCHOR_PAGE
        for job in jobs
    )
    if strict and ({"word/footnotes.xml", "word/endnotes.xml"} & part_names):
        failures.append(
            LayoutFailure(
                LayoutFailureCode.UNSUPPORTED_SURFACE,
                "footnote/endnote flow is not modeled for strict image layout",
            )
        )
    order = 0
    for part in sorted(
        name
        for name in part_names
        if name.startswith("word/") and name.endswith(".xml")
    ):
        try:
            root = package.parse_xml(part)
        except DocxPackageError as exc:
            failures.append(
                LayoutFailure(
                    LayoutFailureCode.INVALID_REQUEST,
                    f"malformed {part} [{exc.code}]: {exc}",
                )
            )
            continue
        for element in root.iter(W_BOOKMARK_START_TAG):
            bookmark_name = str(element.get(W_BOOKMARK_NAME_ATTRIBUTE, ""))
            if bookmark_name not in found:
                continue
            order += 1
            found[bookmark_name].append(
                _bookmark_evidence(element, bookmark_name, part, order)
            )
    return found, failures


def _bookmark_evidence(
    element,
    name: str,
    part: str,
    order: int,
) -> _BookmarkEvidence:
    paragraph = xml_ancestor(element, W_PARAGRAPH_TAG)
    return _BookmarkEvidence(
        name=name,
        part=part,
        path=element.getroottree().getpath(element),
        in_table=xml_ancestor(element, W_TABLE_CELL_TAG) is not None,
        has_floating=(
            paragraph is not None
            and any(descendant.tag == WP_ANCHOR_TAG for descendant in paragraph.iter())
        ),
        paragraph_text="" if paragraph is None else "".join(paragraph.itertext()),
        order=order,
    )


def _validate_bookmark_occurrences(
    found: Mapping[str, Sequence[_BookmarkEvidence]],
    jobs: Sequence[OfficeImageLayoutJob],
) -> list[LayoutFailure]:
    failures: list[LayoutFailure] = []
    for name, evidence in found.items():
        job_id = _bookmark_job_id(name, jobs)
        if not evidence:
            failures.append(
                LayoutFailure(
                    LayoutFailureCode.BOOKMARK_MISSING,
                    f"bookmark {name!r} is missing",
                    job_id,
                )
            )
        elif len(evidence) != 1:
            failures.append(
                LayoutFailure(
                    LayoutFailureCode.BOOKMARK_NOT_UNIQUE,
                    f"bookmark {name!r} occurs {len(evidence)} times",
                    job_id,
                )
            )
        elif (
            evidence[0].part != "word/document.xml"
            or evidence[0].in_table
            or evidence[0].has_floating
        ):
            failures.append(
                LayoutFailure(
                    LayoutFailureCode.UNSUPPORTED_SURFACE,
                    f"bookmark {name!r} is not on a normal main-body paragraph",
                    job_id,
                )
            )
    return failures


def _bookmark_job_id(name: str, jobs: Sequence[OfficeImageLayoutJob]) -> str:
    related = next(
        (
            job
            for job in jobs
            if name
            in {
                job.plan.anchor.stable_marker_id,
                job.plan.anchor.guard_marker_id,
            }
        ),
        None,
    )
    return related.job_id if related else ""


def _validate_strict_guard_order(
    found: Mapping[str, Sequence[_BookmarkEvidence]],
    jobs: Sequence[OfficeImageLayoutJob],
) -> list[LayoutFailure]:
    failures: list[LayoutFailure] = []
    for job in jobs:
        if job.plan.placement.mode is not ImagePlacementMode.FIT_REMAINING_ANCHOR_PAGE:
            continue
        anchor = found.get(job.plan.anchor.stable_marker_id, ())
        guard = found.get(job.plan.anchor.guard_marker_id, ())
        if len(anchor) == len(guard) == 1:
            if guard[0].order >= anchor[0].order or not guard[0].paragraph_text.strip():
                failures.append(
                    LayoutFailure(
                        LayoutFailureCode.GUARD_ORDER_INVALID,
                        "guard must be a preceding non-empty paragraph",
                        job.job_id,
                    )
                )
    return failures


__all__ = ["parent_preflight"]
