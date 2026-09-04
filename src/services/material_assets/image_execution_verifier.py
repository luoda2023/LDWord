"""Shared evidence verification for material-image execution.

The main document and every substituted attachment DOCX use the same image
planning, transform, and Office-layout contracts.  Keeping the verification in
this module prevents either consumer from silently accepting weaker evidence.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Sequence

from src.config.image_materials import ResolvedImageInsertionPlan
from src.services.material_assets.image_plan_builder import ImagePlanBuildResult
from src.services.material_assets.image_transform_batch import (
    ImageTransformBatchResult,
)
from src.shared.engine.office_image_layout_contracts import (
    LAYOUT_SCHEMA_VERSION,
    OfficeImageLayoutReceipt,
    OfficeImageLayoutRequest,
)
from src.shared.engine.office_image_layout_geometry import (
    MAX_IMAGE_PROPORTION_ERROR,
)
from src.shared.engine.office_image_layout_inventory import (
    image_inventory_sha256,
    image_preservation_sha256,
    inventory_ooxml_images,
)


class ImageExecutionVerificationError(RuntimeError):
    """One stable failure code for an invalid image-execution boundary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = str(code)
        super().__init__(message)


def verify_image_plan_result(
    result: ImagePlanBuildResult,
    snapshot_id: str,
) -> None:
    if not isinstance(result, ImagePlanBuildResult):
        raise _invalid(
            "image_plan_receipt_invalid",
            "image plan builder returned an invalid result",
        )
    receipt = result.receipt
    if receipt.snapshot_id != snapshot_id:
        raise _invalid(
            "image_plan_receipt_invalid",
            "image plan receipt references a different intake snapshot",
        )
    by_job = {plan.job_id: plan for plan in result.plans}
    entries = {item.job_id: item for item in receipt.entries}
    if len(by_job) != len(result.plans) or set(by_job) != set(entries):
        raise _invalid(
            "image_plan_receipt_invalid",
            "image plan receipt jobs do not match resolved plans",
        )
    for job_id, plan in by_job.items():
        entry = entries[job_id]
        if (
            entry.source_sha256 != plan.image_ref.content_sha256
            or entry.occurrence_id != plan.occurrence_id
            or entry.stable_marker_id != plan.anchor.stable_marker_id
        ):
            raise _invalid(
                "image_plan_receipt_invalid",
                f"image plan receipt evidence is inconsistent for job {job_id}",
            )
    payload = {
        "snapshot_id": snapshot_id,
        "entries": [item.to_dict() for item in receipt.entries],
    }
    expected = "image-plan-" + sha256(
        _stable_json(payload).encode("utf-8")
    ).hexdigest()
    if receipt.receipt_id != expected:
        raise _invalid(
            "image_plan_receipt_invalid",
            "image plan receipt_id does not match its canonical evidence",
        )


def verify_image_transform_result(
    result: ImageTransformBatchResult,
    plans: Sequence[ResolvedImageInsertionPlan],
) -> None:
    if not isinstance(result, ImageTransformBatchResult):
        raise _invalid(
            "image_transform_receipt_invalid",
            "image transform dependency returned an invalid result",
        )
    frozen_plans = tuple(plans or ())
    plan_by_job = {item.job_id: item for item in frozen_plans}
    job_by_id = {item.job_id: item for item in result.jobs}
    receipt_by_id = {item.job_id: item for item in result.receipt.jobs}
    if (
        len(plan_by_job) != len(frozen_plans)
        or set(plan_by_job) != set(job_by_id)
        or set(plan_by_job) != set(receipt_by_id)
    ):
        raise _invalid(
            "image_transform_receipt_invalid",
            "image transform jobs do not match the resolved image plans",
        )
    for job_id, plan in plan_by_job.items():
        prepared = job_by_id[job_id].prepared_image
        try:
            evidence_sha256 = _stable_file_sha256(prepared.output_path)
        except (OSError, ValueError) as exc:
            raise _invalid(
                "image_transform_receipt_invalid",
                f"image transform output cannot be verified for job {job_id}: {exc}",
            ) from exc
        receipt = receipt_by_id[job_id]
        if (
            evidence_sha256 != prepared.output_sha256
            or receipt.output_sha256 != prepared.output_sha256
            or receipt.source_sha256 != plan.image_ref.content_sha256
            or prepared.source_sha256 != plan.image_ref.content_sha256
        ):
            raise _invalid(
                "image_transform_receipt_invalid",
                f"image transform evidence is inconsistent for job {job_id}",
            )
    expected = sha256(
        _stable_json(result.receipt.to_identity_dict()).encode("utf-8")
    ).hexdigest()
    if result.receipt.identity_sha256 != expected:
        raise _invalid(
            "image_transform_receipt_invalid",
            "image transform receipt identity is invalid",
        )


def verify_office_layout_receipt(
    receipt: OfficeImageLayoutReceipt,
    request: OfficeImageLayoutRequest,
    plans: Sequence[ResolvedImageInsertionPlan],
) -> None:
    if not isinstance(receipt, OfficeImageLayoutReceipt):
        raise _invalid(
            "office_layout_receipt_invalid",
            "layout dependency returned an invalid receipt",
        )
    if not receipt.succeeded:
        detail = "; ".join(
            f"{item.code.value}: {item.message}" for item in receipt.failures
        )
        raise _invalid(
            "office_layout_failed",
            detail or f"layout ended with status {receipt.status.value}",
        )
    frozen_plans = tuple(plans or ())
    expected_jobs = tuple(item.job_id for item in frozen_plans)
    receipt_jobs = tuple(item.job_id for item in receipt.jobs)
    if (
        receipt.schema_version != LAYOUT_SCHEMA_VERSION
        or receipt.transaction_id != request.transaction_id
        or receipt.provider != request.provider
        or Path(receipt.source_docx_path).resolve()
        != Path(request.source_docx_path).resolve()
        or receipt.source_docx_sha256_before != request.source_docx_sha256
        or receipt.source_docx_sha256_after != request.source_docx_sha256
        or not receipt.shadow_retained
        or not receipt.source_images_unchanged
        or not receipt.prepared_images_unchanged
        or receipt.document_open_count != 1
        or receipt.document_save_count != 1
        or receipt.pdf_export_count != 0
        or receipt_jobs != expected_jobs
    ):
        raise _invalid(
            "office_layout_receipt_invalid",
            "layout receipt violates the one-open/one-save immutable-input contract",
        )
    request_jobs = {item.plan.job_id: item for item in request.jobs}
    if set(request_jobs) != set(expected_jobs):
        raise _invalid(
            "office_layout_receipt_invalid",
            "layout request jobs do not match the resolved image plans",
        )
    for item in receipt.jobs:
        requested = request_jobs[item.job_id]
        if (
            item.source_image_sha256 != requested.plan.image_ref.content_sha256
            or item.prepared_image_sha256
            != requested.prepared_image.output_sha256
        ):
            raise _invalid(
                "office_layout_receipt_invalid",
                f"layout receipt image identity differs for job {item.job_id}",
            )

    _verify_layout_geometry_evidence(receipt, request)

    try:
        source_inventory = inventory_ooxml_images(request.source_docx_path)
        shadow_inventory = inventory_ooxml_images(receipt.shadow_path)
    except (OSError, ValueError) as exc:
        raise _invalid(
            "office_layout_receipt_invalid",
            f"layout receipt image inventory cannot be verified: {exc}",
        ) from exc

    inserted_inventory = tuple(receipt.inserted_image_inventory)
    remaining = Counter(shadow_inventory)
    for item in inserted_inventory:
        if remaining[item] <= 0:
            raise _invalid(
                "office_layout_receipt_invalid",
                "layout receipt inserted-image inventory is not present in the shadow",
            )
        remaining[item] -= 1
    shadow_preexisting = tuple(
        item for item, count in remaining.items() for _index in range(count)
    )
    expected_inserted = Counter(
        (item.shape_id, item.job_id, item.prepared_image_sha256)
        for item in receipt.jobs
    )
    actual_inserted = Counter(
        (item.alternative_text, item.title, item.media_sha256)
        for item in inserted_inventory
    )
    phase_k_valid = (
        receipt.preexisting_images_unchanged
        and receipt.inserted_images_job_owned
        and receipt.inserted_images_visible
        and receipt.sentinel_texts_hidden
        and tuple(receipt.source_image_inventory) == source_inventory
        and tuple(receipt.shadow_image_inventory) == shadow_inventory
        and receipt.source_image_inventory_sha256
        == image_inventory_sha256(source_inventory)
        and receipt.shadow_image_inventory_sha256
        == image_inventory_sha256(shadow_inventory)
        and receipt.preexisting_image_semantic_sha256_before
        == image_preservation_sha256(source_inventory)
        and receipt.preexisting_image_semantic_sha256_after
        == image_preservation_sha256(shadow_preexisting)
        and receipt.preexisting_image_semantic_sha256_before
        == receipt.preexisting_image_semantic_sha256_after
        and len(inserted_inventory) == len(request.jobs)
        and len(shadow_preexisting) == len(source_inventory)
        and expected_inserted == actual_inserted
        and all(
            item.drawing_kind == "inline"
            and item.run_visibility == "visible"
            and item.relationship_reference == "embed"
            and item.target_mode == "internal"
            and item.relationship_type.endswith("/image")
            for item in inserted_inventory
        )
    )
    if not phase_k_valid:
        raise _invalid(
            "office_layout_receipt_invalid",
            "layout receipt violates the preexisting-image preservation, "
            "visible job-owned insertion, or hidden-sentinel contract",
        )


def _verify_layout_geometry_evidence(
    receipt: OfficeImageLayoutReceipt,
    request: OfficeImageLayoutRequest,
) -> None:
    if not receipt.jobs:
        return
    rounds = tuple(receipt.stabilization_rounds)
    if not rounds or not rounds[-1].stable or bool(rounds[-1].violation_job_ids):
        raise _invalid(
            "office_layout_receipt_invalid",
            "layout receipt has no stable, violation-free final round",
        )
    final_rows = tuple(rounds[-1].job_pages)
    if tuple(row[0] for row in final_rows) != tuple(
        item.job_id for item in receipt.jobs
    ):
        raise _invalid(
            "office_layout_receipt_invalid",
            "layout final-round jobs do not match the receipt jobs",
        )

    request_jobs = {item.plan.job_id: item for item in request.jobs}
    final_row_by_job = {row[0]: row for row in final_rows}
    for item in receipt.jobs:
        requested = request_jobs[item.job_id]
        final_values = (
            item.final_image_y_pt,
            item.final_width_pt,
            item.final_height_pt,
            item.proportion_error,
            item.initial_actual_width_pt,
            item.initial_actual_height_pt,
            item.initial_proportion_error,
        )
        if any(
            value is None or not math.isfinite(float(value))
            for value in final_values
        ):
            raise _invalid(
                "office_layout_receipt_invalid",
                f"layout geometry evidence is incomplete for job {item.job_id}",
            )
        assert item.final_image_y_pt is not None
        assert item.final_width_pt is not None
        assert item.final_height_pt is not None
        assert item.proportion_error is not None
        assert item.initial_actual_width_pt is not None
        assert item.initial_actual_height_pt is not None
        assert item.initial_proportion_error is not None
        if (
            item.measurement_anchor_page < 1
            or item.measurement_anchor_start < 0
            or item.final_anchor_page is None
            or item.final_anchor_page < 1
            or item.final_image_page is None
            or item.final_image_page < 1
            or item.final_image_y_pt < 0
            or item.final_width_pt <= 0
            or item.final_height_pt <= 0
            or item.initial_actual_width_pt <= 0
            or item.initial_actual_height_pt <= 0
            or item.initial_proportion_error < 0
            or not item.boundary_ok
        ):
            raise _invalid(
                "office_layout_receipt_invalid",
                f"layout geometry bounds are invalid for job {item.job_id}",
            )

        aspect = (
            float(requested.prepared_image.width_px)
            / float(requested.prepared_image.height_px)
        )
        computed_error = abs(
            item.final_width_pt / item.final_height_pt - aspect
        ) / aspect
        if (
            computed_error > MAX_IMAGE_PROPORTION_ERROR
            or item.proportion_error > MAX_IMAGE_PROPORTION_ERROR
            or abs(computed_error - item.proportion_error) > 1e-9
        ):
            raise _invalid(
                "office_layout_receipt_invalid",
                f"layout aspect-ratio evidence is invalid for job {item.job_id}",
            )

        boundary_recomputed = item.final_width_pt <= item.container_width_pt + 0.75
        if item.co_location_claimed:
            boundary_recomputed = boundary_recomputed and (
                item.final_image_y_pt + item.final_height_pt
                <= item.flow_bottom_pt + 0.75
            )
            pages = (
                item.final_guard_page,
                item.final_anchor_page,
                item.final_image_page,
            )
            if (
                item.measurement_guard_page != item.measurement_anchor_page
                or pages[0] is None
                or len(set(pages)) != 1
                or not item.guard_xml_sha256_before
                or not item.guard_keep_sha256_before
            ):
                raise _invalid(
                    "office_layout_receipt_invalid",
                    f"layout same-page evidence is invalid for job {item.job_id}",
                )
        elif item.final_guard_page is not None:
            raise _invalid(
                "office_layout_receipt_invalid",
                f"non-strict layout unexpectedly claims a guard page for job {item.job_id}",
            )
        if (
            not boundary_recomputed
            or item.guard_xml_sha256_before != item.guard_xml_sha256_after
            or item.guard_keep_sha256_before != item.guard_keep_sha256_after
        ):
            raise _invalid(
                "office_layout_receipt_invalid",
                f"layout boundary or guard preservation evidence is invalid for job {item.job_id}",
            )
        if final_row_by_job[item.job_id] != (
            item.job_id,
            item.final_guard_page,
            item.final_anchor_page,
            item.final_image_page,
        ):
            raise _invalid(
                "office_layout_receipt_invalid",
                f"layout final-round page evidence differs for job {item.job_id}",
            )


def _stable_file_sha256(path: str | Path) -> str:
    raw = Path(path).expanduser()
    if raw.is_symlink():
        raise ValueError(f"symbolic links are not accepted: {raw}")
    candidate = raw.resolve()
    if not candidate.is_file():
        raise ValueError(f"not a regular file: {candidate}")
    before = candidate.stat()
    digest = sha256()
    with candidate.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    after = candidate.stat()
    if (
        before.st_size,
        before.st_mtime_ns,
        getattr(before, "st_ino", 0),
    ) != (
        after.st_size,
        after.st_mtime_ns,
        getattr(after, "st_ino", 0),
    ):
        raise ValueError(f"file changed while hashing: {candidate}")
    return digest.hexdigest()


def _stable_json(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _invalid(code: str, message: str) -> ImageExecutionVerificationError:
    return ImageExecutionVerificationError(code, message)


__all__ = [
    "ImageExecutionVerificationError",
    "verify_image_plan_result",
    "verify_image_transform_result",
    "verify_office_layout_receipt",
]
