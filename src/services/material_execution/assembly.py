"""Top-level, non-UI orchestration for material DOCX assembly.

This service is intentionally a coordinator, not another formatting module.
It freezes mutable intake once, composes content before the injected pipeline,
plans/transforms/layouts every staged delivery variant independently, verifies
all candidates, and only then enters the multi-variant publication transaction.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
import os
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from docx import Document

from src.config.content_materials import ContentResourceKey
from src.config.image_materials import DeliveryVariantPlan
from src.config.material_snapshot import MaterialSnapshot
from src.services.material_execution.material_snapshot_builder import (
    MaterialSnapshotBuildRequest,
    MaterialSnapshotBuilder,
)
from src.services.material_assets.image_plan_builder import (
    ContentResourceImageSource,
    ImageInsertionPlanBuilder,
    ImagePlanBuildResult,
)
from src.services.material_assets.image_execution_verifier import (
    ImageExecutionVerificationError,
    verify_image_plan_result,
    verify_image_transform_result,
    verify_office_layout_receipt,
)
from src.services.material_assets.image_policy_freezer import ImagePolicyFreezer
from src.services.material_assets.image_transform_batch import (
    ImageTransformBatch,
    ImageTransformBatchError,
    ImageTransformBatchResult,
)
from src.services.material_content.composer import (
    ComposeReceipt,
    ContentComposeCancelledError,
    ContentComposeRequest,
    ContentMaterialComposer,
)
from src.services.material_content.docx_renderer import ContentImageJobDraft
from src.shared.engine.material_dependency_index import (
    DependencyDiagnosticSeverity,
    MaterialDependencyIndex,
)
from src.shared.engine.office_image_layout_contracts import (
    OfficeImageLayoutReceipt,
    OfficeImageLayoutRequest,
)
from src.shared.engine.office_image_layout_coordinator import (
    build_office_image_layout_request,
    run_office_image_layout,
)

from .contracts import (
    AssemblyDiagnostic,
    AssemblyFailureCode,
    AssemblyStage,
    CancelCheck,
    FileEvidence,
    MATERIAL_ASSEMBLY_CONTRACT_VERSION,
    MaterialAssemblyCancelled,
    MaterialAssemblyError,
    MaterialAssemblyReceipt,
    MaterialAssemblyRequest,
    MaterialPipelineCallback,
    MaterialPipelineOutcome,
    MaterialPipelineRequest,
    MaterialVariantRequest,
    PipelineRunReceipt,
    PipelineVariantTarget,
    PipelineVisibilityEvidence,
    VariantAssemblyReceipt,
)
from .dependency_indexer import (
    MaterialDependencyIndexer,
    MaterialDependencyIndexRequest,
)
from src.shared.io.artifact_transaction import (
    OwnedAssemblyTransaction,
    TransactionViolation,
    same_file_identity,
    stable_file_evidence,
)


class _TransformBatchFactory(Protocol):
    def __call__(self, plans, **kwargs) -> object: ...


@dataclass(frozen=True, slots=True)
class MaterialAssemblyDependencies:
    """Pure dependency seam used by tests and provider-specific integration."""

    image_policy_freezer: ImagePolicyFreezer = field(
        default_factory=ImagePolicyFreezer
    )
    snapshot_builder: MaterialSnapshotBuilder = field(
        default_factory=MaterialSnapshotBuilder
    )
    dependency_indexer: MaterialDependencyIndexer = field(
        default_factory=MaterialDependencyIndexer
    )
    content_composer: ContentMaterialComposer = field(
        default_factory=ContentMaterialComposer
    )
    image_plan_builder: ImageInsertionPlanBuilder = field(
        default_factory=ImageInsertionPlanBuilder
    )
    document_loader: Callable[[str], object] = Document
    transform_batch_factory: _TransformBatchFactory = ImageTransformBatch
    layout_request_builder: Callable[..., OfficeImageLayoutRequest] = (
        build_office_image_layout_request
    )
    layout_runner: Callable[[OfficeImageLayoutRequest], OfficeImageLayoutReceipt] = (
        run_office_image_layout
    )
    atomic_replace: Callable[[str | Path, str | Path], object] = os.replace

    def __post_init__(self) -> None:
        for name in (
            "document_loader",
            "transform_batch_factory",
            "layout_request_builder",
            "layout_runner",
            "atomic_replace",
        ):
            if not callable(getattr(self, name)):
                raise TypeError(f"{name} must be callable")


@dataclass(slots=True)
class _PendingVariant:
    variant: MaterialVariantRequest
    pipeline_output: FileEvidence
    visibility_evidence: PipelineVisibilityEvidence
    not_applicable_content_job_ids: tuple[str, ...]
    not_applicable_content_markers: tuple[str, ...]
    delivery_plan: DeliveryVariantPlan
    image_plan_result: ImagePlanBuildResult
    transform_result: ImageTransformBatchResult
    layout_receipt: OfficeImageLayoutReceipt | None
    candidate: FileEvidence


@dataclass(slots=True)
class _AssemblyRunState:
    request: MaterialAssemblyRequest
    cancel_check: CancelCheck | None
    execution_id: str = field(default_factory=lambda: uuid4().hex)
    stage: AssemblyStage = AssemblyStage.PREFLIGHT
    variant_id: str = ""
    transaction: OwnedAssemblyTransaction | None = None

    def begin(self, stage: AssemblyStage) -> None:
        self.stage = stage

    def select_variant(self, variant_id: str) -> None:
        self.variant_id = variant_id

    def begin_variant(self, stage: AssemblyStage, variant_id: str) -> None:
        self.stage = stage
        self.variant_id = variant_id

    def check_cancel(self, *, include_variant: bool = False) -> None:
        _check_cancel(
            self.cancel_check,
            self.stage,
            variant_id=self.variant_id if include_variant else "",
        )


@dataclass(frozen=True, slots=True)
class _PreflightPhase:
    source: Path
    final_by_variant: dict[str, Path]
    source_evidence: FileEvidence
    transaction: OwnedAssemblyTransaction


@dataclass(frozen=True, slots=True)
class _IntakePhase:
    freeze_request: MaterialSnapshotBuildRequest
    snapshot: MaterialSnapshot


@dataclass(frozen=True, slots=True)
class _ComposePhase:
    receipt: ComposeReceipt
    prepared_evidence: FileEvidence
    content_sources: Mapping[ContentResourceKey, ContentResourceImageSource]


@dataclass(frozen=True, slots=True)
class _PipelinePhase:
    targets: tuple[PipelineVariantTarget, ...]
    receipt: PipelineRunReceipt
    visibility_by_variant: dict[str, PipelineVisibilityEvidence]


class MaterialAssemblyService:
    """Execute one all-or-nothing material assembly transaction."""

    def __init__(
        self,
        pipeline_callback: MaterialPipelineCallback,
        *,
        dependencies: MaterialAssemblyDependencies | None = None,
    ) -> None:
        if not callable(pipeline_callback):
            raise TypeError("pipeline_callback must be callable")
        self._pipeline_callback = pipeline_callback
        self._deps = dependencies or MaterialAssemblyDependencies()

    def execute(
        self,
        request: MaterialAssemblyRequest,
        *,
        cancel_check: CancelCheck | None = None,
    ) -> MaterialAssemblyReceipt:
        if not isinstance(request, MaterialAssemblyRequest):
            raise TypeError("request must be a MaterialAssemblyRequest")

        state = _AssemblyRunState(request=request, cancel_check=cancel_check)
        try:
            preflight = self._run_preflight(state)
            intake = self._freeze_intake(state)
            dependency_index = self._index_dependencies(
                state,
                preflight,
                intake,
            )
            compose = self._compose_content(state, preflight, intake)
            pipeline = self._run_pipeline(
                state,
                preflight,
                intake,
                compose,
            )
            pending = self._prepare_variants(
                state,
                preflight,
                intake,
                compose,
                pipeline,
            )
            self._verify_publish_readiness(state, preflight, intake)
            return self._publish(
                state,
                preflight,
                intake,
                dependency_index,
                compose,
                pipeline,
                pending,
            )
        except MaterialAssemblyError as exc:
            raise _rollback_or_extend(state.transaction, exc) from exc
        except Exception as exc:
            wrapped = _map_exception(
                exc,
                state.stage,
                variant_id=state.variant_id,
            )
            raise _rollback_or_extend(state.transaction, wrapped) from exc

    def _run_preflight(self, state: _AssemblyRunState) -> _PreflightPhase:
        request = state.request
        source, final_by_variant = _preflight_paths(request)
        source_evidence = stable_file_evidence(source)
        transaction = OwnedAssemblyTransaction(
            execution_id=state.execution_id,
            final_paths=tuple(final_by_variant.values()),
            work_root=(
                Path(request.work_root) if request.work_root.strip() else None
            ),
            atomic_replace=self._deps.atomic_replace,
        )
        state.transaction = transaction
        state.check_cancel()
        return _PreflightPhase(
            source=source,
            final_by_variant=final_by_variant,
            source_evidence=source_evidence,
            transaction=transaction,
        )

    def _freeze_intake(self, state: _AssemblyRunState) -> _IntakePhase:
        request = state.request
        state.begin(AssemblyStage.INTAKE_FREEZE)
        frozen_policy = self._deps.image_policy_freezer.freeze(
            frozen_field_values=request.frozen_field_values,
            rules=request.image_rules,
            source_items=request.image_source_items,
            runtime_watermark_text=request.runtime_image_watermark_text,
            watermark_font_path=request.watermark_font_path or None,
            watermark_font_identity=request.watermark_font_identity,
        )
        freeze_request = MaterialSnapshotBuildRequest(
            profile=request.profile,
            frozen_field_values=request.frozen_field_values,
            material_schema_id=request.material_schema_id,
            material_schema_version=request.material_schema_version,
            rule_versions=request.rule_versions,
            frozen_image_rules=frozen_policy.rules,
            image_source_bindings=frozen_policy.source_bindings,
            source_root=request.source_root or None,
        )
        snapshot = _build_intake_snapshot(
            self._deps.snapshot_builder,
            freeze_request,
        )
        _check_intake_contract(snapshot)
        state.check_cancel()
        return _IntakePhase(freeze_request=freeze_request, snapshot=snapshot)

    def _index_dependencies(
        self,
        state: _AssemblyRunState,
        preflight: _PreflightPhase,
        intake: _IntakePhase,
    ) -> MaterialDependencyIndex:
        state.begin(AssemblyStage.DEPENDENCY_INDEX)
        dependency_index = self._deps.dependency_indexer.build(
            MaterialDependencyIndexRequest(
                snapshot=intake.snapshot,
                main_document_path=str(preflight.source),
            )
        )
        dependency_errors = tuple(
            item
            for item in dependency_index.diagnostics
            if item.severity is DependencyDiagnosticSeverity.ERROR
        )
        if dependency_errors:
            summary = "; ".join(
                f"{item.consumer.consumer_id}:{item.code}:{item.token}"
                for item in dependency_errors[:8]
            )
            raise _assembly_error(
                AssemblyFailureCode.DEPENDENCY_INDEX_INVALID,
                state.stage,
                "material dependency preflight failed: " + summary,
            )
        state.check_cancel()
        return dependency_index

    def _compose_content(
        self,
        state: _AssemblyRunState,
        preflight: _PreflightPhase,
        intake: _IntakePhase,
    ) -> _ComposePhase:
        state.begin(AssemblyStage.CONTENT_COMPOSE)
        prepared_path = preflight.transaction.own_work_file("prepared.docx")
        receipt = self._deps.content_composer.compose(
            ContentComposeRequest(
                source_docx_path=str(preflight.source),
                output_docx_path=str(prepared_path),
                snapshot=intake.snapshot,
            ),
            cancel_check=state.cancel_check,
        )
        prepared_evidence = _verify_compose_receipt(
            receipt,
            preflight.source_evidence,
            prepared_path,
            intake.snapshot.snapshot_id,
        )
        content_sources = _content_resource_handoff(
            receipt,
            state.request.content_resource_sources,
        )
        _verify_immutable_file(preflight.source_evidence, state.stage)
        _verify_final_baselines(preflight.transaction, state.stage)
        state.check_cancel()
        return _ComposePhase(
            receipt=receipt,
            prepared_evidence=prepared_evidence,
            content_sources=content_sources,
        )

    def _run_pipeline(
        self,
        state: _AssemblyRunState,
        preflight: _PreflightPhase,
        intake: _IntakePhase,
        compose: _ComposePhase,
    ) -> _PipelinePhase:
        state.begin(AssemblyStage.PIPELINE)
        targets = tuple(
            PipelineVariantTarget(
                variant_id=variant.variant_id,
                variant_version=variant.variant_version,
                final_output_path=str(
                    preflight.final_by_variant[variant.variant_id]
                ),
                owned_stage_output_path=str(
                    preflight.transaction.allocate_stage(
                        variant.variant_id,
                        preflight.final_by_variant[variant.variant_id],
                    )
                ),
            )
            for variant in state.request.variants
        )
        request = MaterialPipelineRequest(
            execution_id=state.execution_id,
            logical_source_path=str(preflight.source),
            prepared_input=compose.prepared_evidence,
            intake_snapshot_id=intake.snapshot.snapshot_id,
            targets=targets,
        )
        outcome = self._pipeline_callback(
            request,
            cancel_check=state.cancel_check,
        )
        if not isinstance(outcome, MaterialPipelineOutcome):
            raise _assembly_error(
                AssemblyFailureCode.PIPELINE_CONTRACT_VIOLATION,
                state.stage,
                "pipeline callback must return MaterialPipelineOutcome",
            )
        visibility_by_variant = _verify_visibility_outcome(
            outcome,
            request,
            compose.receipt,
        )
        receipt = _verify_pipeline_outputs(
            request,
            preflight.source_evidence,
            preflight.transaction,
            outcome,
        )
        state.check_cancel()
        return _PipelinePhase(
            targets=targets,
            receipt=receipt,
            visibility_by_variant=visibility_by_variant,
        )

    def _prepare_variants(
        self,
        state: _AssemblyRunState,
        preflight: _PreflightPhase,
        intake: _IntakePhase,
        compose: _ComposePhase,
        pipeline: _PipelinePhase,
    ) -> list[_PendingVariant]:
        pipeline_by_variant = dict(
            zip(
                pipeline.receipt.variant_ids,
                pipeline.receipt.outputs,
                strict=True,
            )
        )
        target_by_variant = {
            item.variant_id: item for item in pipeline.targets
        }
        pending: list[_PendingVariant] = []
        for variant in state.request.variants:
            state.select_variant(variant.variant_id)
            pending.append(
                self._prepare_variant(
                    state,
                    preflight,
                    intake,
                    compose,
                    pipeline.visibility_by_variant[variant.variant_id],
                    target_by_variant[variant.variant_id],
                    pipeline_by_variant[variant.variant_id],
                    variant,
                )
            )
        return pending

    def _prepare_variant(
        self,
        state: _AssemblyRunState,
        preflight: _PreflightPhase,
        intake: _IntakePhase,
        compose: _ComposePhase,
        visibility: PipelineVisibilityEvidence,
        target: PipelineVariantTarget,
        pipeline_output: FileEvidence,
        variant: MaterialVariantRequest,
    ) -> _PendingVariant:
        stage_path = Path(target.owned_stage_output_path).resolve()
        applicable_drafts, suppressed_drafts = _partition_variant_drafts(
            compose.receipt,
            visibility,
        )
        image_plan_result, delivery_plan = self._plan_variant_images(
            state,
            intake,
            compose,
            variant,
            stage_path,
            applicable_drafts,
        )
        transform_result = self._transform_variant_images(
            state,
            preflight.transaction,
            delivery_plan,
        )
        layout_receipt, candidate_path = self._layout_variant(
            state,
            preflight.transaction,
            stage_path,
            delivery_plan,
            transform_result,
        )
        candidate = self._verify_variant_candidate(
            state,
            preflight,
            delivery_plan,
            layout_receipt,
            candidate_path,
        )
        return _PendingVariant(
            variant=variant,
            pipeline_output=pipeline_output,
            visibility_evidence=visibility,
            not_applicable_content_job_ids=tuple(
                draft.job_id for draft in suppressed_drafts
            ),
            not_applicable_content_markers=tuple(
                draft.stable_marker_id for draft in suppressed_drafts
            ),
            delivery_plan=delivery_plan,
            image_plan_result=image_plan_result,
            transform_result=transform_result,
            layout_receipt=layout_receipt,
            candidate=candidate,
        )

    def _plan_variant_images(
        self,
        state: _AssemblyRunState,
        intake: _IntakePhase,
        compose: _ComposePhase,
        variant: MaterialVariantRequest,
        stage_path: Path,
        applicable_drafts: tuple[ContentImageJobDraft, ...],
    ) -> tuple[ImagePlanBuildResult, DeliveryVariantPlan]:
        state.begin_variant(AssemblyStage.IMAGE_PLAN, variant.variant_id)
        state.check_cancel(include_variant=True)
        document = self._deps.document_loader(str(stage_path))
        image_plan_result = self._deps.image_plan_builder.build(
            document,
            snapshot_id=intake.snapshot.snapshot_id,
            frozen_rules=intake.snapshot.frozen_image_rules,
            source_bindings=intake.snapshot.image_source_bindings,
            content_image_drafts=applicable_drafts,
            content_resource_sources=compose.content_sources,
        )
        _verify_image_plan_receipt(image_plan_result, intake.snapshot)
        document.save(str(stage_path))
        planned_stage = stable_file_evidence(stage_path)

        state.begin(AssemblyStage.DELIVERY_PLAN)
        delivery_plan = DeliveryVariantPlan(
            snapshot_id=intake.snapshot.snapshot_id,
            variant_id=variant.variant_id,
            variant_version=variant.variant_version,
            staged_docx_sha256=planned_stage.sha256,
            staged_docx_byte_size=planned_stage.byte_size,
            resolved_image_plans=image_plan_result.plans,
        )
        _verify_delivery_plan(
            delivery_plan,
            planned_stage,
            intake.snapshot,
        )
        return image_plan_result, delivery_plan

    def _transform_variant_images(
        self,
        state: _AssemblyRunState,
        transaction: OwnedAssemblyTransaction,
        delivery_plan: DeliveryVariantPlan,
    ) -> ImageTransformBatchResult:
        state.begin(AssemblyStage.IMAGE_TRANSFORM)
        image_cache = _image_cache_path(state.request, transaction)
        transform_batch = self._deps.transform_batch_factory(
            delivery_plan.resolved_image_plans,
            cache_dir=image_cache,
            font_path_resolver=(
                (lambda _plan: state.request.watermark_font_path)
                if state.request.watermark_font_path.strip()
                else None
            ),
            max_workers=state.request.max_image_transform_workers,
        )
        result = transform_batch.run(cancel_check=state.cancel_check)
        if not isinstance(result, ImageTransformBatchResult):
            raise _assembly_error(
                AssemblyFailureCode.IMAGE_TRANSFORM_RECEIPT_INVALID,
                state.stage,
                "image transform dependency returned an invalid result",
                variant_id=state.variant_id,
            )
        _verify_transform_result(result, delivery_plan)
        return result

    def _layout_variant(
        self,
        state: _AssemblyRunState,
        transaction: OwnedAssemblyTransaction,
        stage_path: Path,
        delivery_plan: DeliveryVariantPlan,
        transform_result: ImageTransformBatchResult,
    ) -> tuple[OfficeImageLayoutReceipt | None, Path]:
        if not delivery_plan.resolved_image_plans:
            return None, stage_path

        state.begin(AssemblyStage.OFFICE_LAYOUT)
        state.check_cancel(include_variant=True)
        request = self._deps.layout_request_builder(
            stage_path,
            delivery_plan.resolved_image_plans,
            transform_result.prepared_by_job,
            provider=state.request.office_provider,
            transaction_id=f"{state.execution_id}-{state.variant_id}",
            **dict(state.request.layout_options),
        )
        receipt = self._deps.layout_runner(request)
        _verify_layout_receipt(receipt, request, delivery_plan)
        try:
            candidate_path = transaction.accept_layout_shadow(
                stage_path,
                receipt.shadow_path,
            )
        except TransactionViolation as exc:
            raise _assembly_error(
                AssemblyFailureCode.FOREIGN_SHADOW,
                state.stage,
                str(exc),
                variant_id=state.variant_id,
                path=receipt.shadow_path,
            ) from exc
        return receipt, candidate_path

    def _verify_variant_candidate(
        self,
        state: _AssemblyRunState,
        preflight: _PreflightPhase,
        delivery_plan: DeliveryVariantPlan,
        layout_receipt: OfficeImageLayoutReceipt | None,
        candidate_path: Path,
    ) -> FileEvidence:
        state.begin(AssemblyStage.VERIFY)
        candidate = stable_file_evidence(candidate_path)
        if (
            layout_receipt is not None
            and candidate.sha256 != layout_receipt.shadow_sha256
        ):
            raise _assembly_error(
                AssemblyFailureCode.OFFICE_LAYOUT_RECEIPT_INVALID,
                state.stage,
                "layout shadow hash differs from the verified candidate",
                variant_id=state.variant_id,
                path=str(candidate_path),
            )
        _verify_immutable_file(
            preflight.source_evidence,
            state.stage,
            variant_id=state.variant_id,
        )
        _verify_delivery_sources(
            delivery_plan,
            variant_id=state.variant_id,
        )
        _verify_final_baselines(
            preflight.transaction,
            state.stage,
            variant_id=state.variant_id,
        )
        return candidate

    def _verify_publish_readiness(
        self,
        state: _AssemblyRunState,
        preflight: _PreflightPhase,
        intake: _IntakePhase,
    ) -> None:
        state.begin(AssemblyStage.VERIFY)
        state.check_cancel()
        try:
            repeated_snapshot = _build_intake_snapshot(
                self._deps.snapshot_builder,
                intake.freeze_request,
            )
        except MaterialAssemblyError as exc:
            raise _assembly_error(
                AssemblyFailureCode.SOURCE_DRIFT,
                state.stage,
                "content, attachment, or image intake could not be "
                f"revalidated after Freeze: {exc.primary.message}",
            ) from exc
        if repeated_snapshot.snapshot_id != intake.snapshot.snapshot_id:
            raise _assembly_error(
                AssemblyFailureCode.SOURCE_DRIFT,
                state.stage,
                "content, attachment, or image intake changed after Freeze",
            )
        _verify_immutable_file(preflight.source_evidence, state.stage)
        _verify_final_baselines(preflight.transaction, state.stage)

    def _publish(
        self,
        state: _AssemblyRunState,
        preflight: _PreflightPhase,
        intake: _IntakePhase,
        dependency_index: MaterialDependencyIndex,
        compose: _ComposePhase,
        pipeline: _PipelinePhase,
        pending: list[_PendingVariant],
    ) -> MaterialAssemblyReceipt:
        state.begin(AssemblyStage.PUBLISH)
        # Intake revalidation above performs filesystem I/O. Honour
        # cancellation again before the first publication replace.
        state.check_cancel()
        published = preflight.transaction.publish(
            {
                preflight.final_by_variant[item.variant.variant_id]: item.candidate
                for item in pending
            }
        )
        receipt = MaterialAssemblyReceipt(
            receipt_id="",
            contract_version=MATERIAL_ASSEMBLY_CONTRACT_VERSION,
            execution_id=state.execution_id,
            source=preflight.source_evidence,
            intake_snapshot=intake.snapshot,
            dependency_index=dependency_index,
            content_compose_receipt=compose.receipt,
            pipeline_receipt=pipeline.receipt,
            variants=_variant_receipts(
                pending,
                published,
                preflight.final_by_variant,
            ),
        )
        preflight.transaction.release_backups()
        preflight.transaction.cleanup_owned()
        return receipt


def _partition_variant_drafts(
    receipt: ComposeReceipt,
    visibility: PipelineVisibilityEvidence,
) -> tuple[tuple[ContentImageJobDraft, ...], tuple[ContentImageJobDraft, ...]]:
    removed_markers = set(visibility.removed_content_image_markers)
    applicable = tuple(
        draft
        for draft in receipt.deferred_image_drafts
        if draft.stable_marker_id not in removed_markers
    )
    draft_by_marker = {
        draft.stable_marker_id: draft
        for draft in receipt.deferred_image_drafts
    }
    suppressed = tuple(
        draft_by_marker[marker]
        for marker in visibility.removed_content_image_markers
    )
    return applicable, suppressed


def _image_cache_path(
    request: MaterialAssemblyRequest,
    transaction: OwnedAssemblyTransaction,
) -> Path:
    if request.image_cache_dir.strip():
        return Path(request.image_cache_dir).expanduser().resolve()
    if transaction.work_dir is None:  # pragma: no cover - constructor invariant
        raise TransactionViolation("transaction work directory is unavailable")
    return transaction.work_dir / "image-cache"


def _variant_receipts(
    pending: list[_PendingVariant],
    published: Mapping[Path, FileEvidence],
    final_by_variant: Mapping[str, Path],
) -> tuple[VariantAssemblyReceipt, ...]:
    return tuple(
        VariantAssemblyReceipt(
            variant=item.variant,
            delivery_plan=item.delivery_plan,
            pipeline_output=item.pipeline_output,
            visibility_evidence=item.visibility_evidence,
            not_applicable_content_image_job_ids=(
                item.not_applicable_content_job_ids
            ),
            not_applicable_content_image_markers=(
                item.not_applicable_content_markers
            ),
            image_plan_receipt=item.image_plan_result.receipt,
            image_transform_receipt=item.transform_result.receipt,
            office_layout_receipt=item.layout_receipt,
            publish_candidate=item.candidate,
            final_output=published[
                final_by_variant[item.variant.variant_id]
            ],
        )
        for item in pending
    )


def _preflight_paths(
    request: MaterialAssemblyRequest,
) -> tuple[Path, dict[str, Path]]:
    raw_source = Path(request.source_docx_path).expanduser()
    if raw_source.is_symlink():
        raise _assembly_error(
            AssemblyFailureCode.INVALID_REQUEST,
            AssemblyStage.PREFLIGHT,
            "source DOCX cannot be a symbolic link",
            path=str(raw_source),
        )
    source = raw_source.resolve()
    if not source.is_file():
        raise _assembly_error(
            AssemblyFailureCode.SOURCE_MISSING,
            AssemblyStage.PREFLIGHT,
            "source DOCX does not exist",
            path=str(source),
        )
    if source.suffix.casefold() != ".docx":
        raise _assembly_error(
            AssemblyFailureCode.INVALID_REQUEST,
            AssemblyStage.PREFLIGHT,
            "source must be a DOCX file",
            path=str(source),
        )
    final_by_variant: dict[str, Path] = {}
    for variant in request.variants:
        raw_final = Path(variant.final_output_path).expanduser()
        if raw_final.is_symlink():
            raise _assembly_error(
                AssemblyFailureCode.INVALID_REQUEST,
                AssemblyStage.PREFLIGHT,
                "final output cannot be a symbolic link",
                variant_id=variant.variant_id,
                path=str(raw_final),
            )
        final = raw_final.resolve()
        if final.suffix.casefold() != ".docx":
            raise _assembly_error(
                AssemblyFailureCode.INVALID_REQUEST,
                AssemblyStage.PREFLIGHT,
                "every final output must be a DOCX file",
                variant_id=variant.variant_id,
                path=str(final),
            )
        if final == source:
            raise _assembly_error(
                AssemblyFailureCode.INVALID_REQUEST,
                AssemblyStage.PREFLIGHT,
                "final output cannot overwrite the immutable source DOCX",
                variant_id=variant.variant_id,
                path=str(final),
            )
        final_by_variant[variant.variant_id] = final
    if len(set(final_by_variant.values())) != len(final_by_variant):
        raise _assembly_error(
            AssemblyFailureCode.INVALID_REQUEST,
            AssemblyStage.PREFLIGHT,
            "final output paths must be unique",
        )
    return source, final_by_variant


def _build_intake_snapshot(
    builder: MaterialSnapshotBuilder,
    request: MaterialSnapshotBuildRequest,
) -> MaterialSnapshot:
    try:
        result = builder.build(request)
    except MaterialAssemblyError:
        raise
    except Exception as exc:
        raise _assembly_error(
            AssemblyFailureCode.INTAKE_FREEZE_FAILED,
            AssemblyStage.INTAKE_FREEZE,
            str(exc),
        ) from exc
    if not result.ok:
        detail = "; ".join(
            f"{item.code}: {item.message}" for item in result.diagnostics
        )
        raise _assembly_error(
            AssemblyFailureCode.INTAKE_FREEZE_FAILED,
            AssemblyStage.INTAKE_FREEZE,
            detail or "intake Freeze failed without diagnostics",
        )
    return result.require_snapshot()


def _check_intake_contract(snapshot: MaterialSnapshot) -> None:
    if not isinstance(snapshot, MaterialSnapshot):
        raise _assembly_error(
            AssemblyFailureCode.INTAKE_FREEZE_INVALID,
            AssemblyStage.INTAKE_FREEZE,
            "snapshot builder returned an invalid type",
        )
    payload = snapshot.to_dict()
    forbidden = {"variant_id", "variant_version", "resolved_image_plans", "image_config"}
    retained = sorted(forbidden & set(payload))
    if retained:
        raise _assembly_error(
            AssemblyFailureCode.INTAKE_FREEZE_INVALID,
            AssemblyStage.INTAKE_FREEZE,
            "intake snapshot retained delivery-only facts: " + ", ".join(retained),
        )


def _verify_compose_receipt(
    receipt: ComposeReceipt,
    source: FileEvidence,
    prepared_path: Path,
    snapshot_id: str,
) -> FileEvidence:
    if not isinstance(receipt, ComposeReceipt):
        raise _assembly_error(
            AssemblyFailureCode.CONTENT_RECEIPT_INVALID,
            AssemblyStage.CONTENT_COMPOSE,
            "content composer returned an invalid receipt",
        )
    prepared = stable_file_evidence(prepared_path)
    if (
        receipt.snapshot_id != snapshot_id
        or Path(receipt.source_docx_path).resolve() != Path(source.path)
        or Path(receipt.output_docx_path).resolve() != prepared_path.resolve()
        or receipt.source_sha256 != source.sha256
        or receipt.output_sha256 != prepared.sha256
    ):
        raise _assembly_error(
            AssemblyFailureCode.CONTENT_RECEIPT_INVALID,
            AssemblyStage.CONTENT_COMPOSE,
            "content receipt does not match its source, snapshot, or output bytes",
            path=str(prepared_path),
        )
    return prepared


def _content_resource_handoff(
    receipt: ComposeReceipt,
    configured: Mapping[ContentResourceKey, ContentResourceImageSource],
) -> Mapping[ContentResourceKey, ContentResourceImageSource]:
    materialized = receipt.resource_materialization.by_key()
    unknown = sorted(set(configured) - set(materialized))
    if unknown:
        raise _assembly_error(
            AssemblyFailureCode.CONTENT_RESOURCE_HANDOFF_INVALID,
            AssemblyStage.CONTENT_COMPOSE,
            "configured content resources were not materialized: "
            + ", ".join(f"{key.content_id}/{key.resource_id}" for key in unknown),
        )
    result: dict[ContentResourceKey, ContentResourceImageSource] = {}
    for key, entry in materialized.items():
        policy = configured.get(key)
        if policy is None:
            result[key] = ContentResourceImageSource.from_materialized_resource(entry)
            continue
        if policy.resource != entry.resource:
            raise _assembly_error(
                AssemblyFailureCode.CONTENT_RESOURCE_HANDOFF_INVALID,
                AssemblyStage.CONTENT_COMPOSE,
                "configured content resource identity differs from composition evidence",
                path=policy.source_path,
            )
        result[key] = replace(
            policy,
            resource=entry.resource,
            source_path=entry.source_path,
        )
    return result


def _verify_visibility_outcome(
    outcome: MaterialPipelineOutcome,
    request: MaterialPipelineRequest,
    compose_receipt: ComposeReceipt,
) -> dict[str, PipelineVisibilityEvidence]:
    expected_variants = {item.variant_id for item in request.targets}
    evidence_by_variant = {
        item.variant_id: item for item in outcome.visibility_evidence
    }
    if set(evidence_by_variant) != expected_variants:
        raise _assembly_error(
            AssemblyFailureCode.PIPELINE_CONTRACT_VIOLATION,
            AssemblyStage.PIPELINE,
            "visibility evidence must cover every pipeline variant exactly once",
        )
    known_markers = {
        item.stable_marker_id for item in compose_receipt.deferred_image_drafts
    }
    if len(known_markers) != len(compose_receipt.deferred_image_drafts):
        raise _assembly_error(
            AssemblyFailureCode.CONTENT_RECEIPT_INVALID,
            AssemblyStage.PIPELINE,
            "content compose receipt contains duplicate deferred image markers",
        )
    for variant_id, evidence in evidence_by_variant.items():
        unknown = sorted(
            set(evidence.removed_content_image_markers) - known_markers
        )
        if unknown:
            raise _assembly_error(
                AssemblyFailureCode.PIPELINE_CONTRACT_VIOLATION,
                AssemblyStage.PIPELINE,
                "visibility evidence tried to suppress unknown content image markers: "
                + ", ".join(unknown),
                variant_id=variant_id,
            )
    return evidence_by_variant


def _verify_pipeline_outputs(
    request: MaterialPipelineRequest,
    source: FileEvidence,
    transaction: OwnedAssemblyTransaction,
    outcome: MaterialPipelineOutcome,
) -> PipelineRunReceipt:
    try:
        prepared_after = stable_file_evidence(request.prepared_input.path)
        if not same_file_identity(prepared_after, request.prepared_input):
            raise TransactionViolation("pipeline callback mutated the prepared input")
        outputs = tuple(
            stable_file_evidence(item.owned_stage_output_path)
            for item in request.targets
        )
        _verify_immutable_file(source, AssemblyStage.PIPELINE)
        _verify_final_baselines(transaction, AssemblyStage.PIPELINE)
    except MaterialAssemblyError:
        raise
    except Exception as exc:
        raise _assembly_error(
            AssemblyFailureCode.PIPELINE_OUTPUT_INVALID,
            AssemblyStage.PIPELINE,
            str(exc),
        ) from exc
    return PipelineRunReceipt(
        prepared_input_before=request.prepared_input,
        prepared_input_after=prepared_after,
        outputs=outputs,
        variant_ids=tuple(item.variant_id for item in request.targets),
        visibility_evidence=outcome.visibility_evidence,
    )


def _verify_image_plan_receipt(
    result: ImagePlanBuildResult,
    snapshot: MaterialSnapshot,
) -> None:
    try:
        verify_image_plan_result(result, snapshot.snapshot_id)
    except ImageExecutionVerificationError as exc:
        raise _assembly_error(
            AssemblyFailureCode.IMAGE_PLAN_RECEIPT_INVALID,
            AssemblyStage.IMAGE_PLAN,
            str(exc),
        ) from exc


def _verify_delivery_plan(
    plan: DeliveryVariantPlan,
    staged_docx: FileEvidence,
    snapshot: MaterialSnapshot,
) -> None:
    if (
        plan.snapshot_id != snapshot.snapshot_id
        or plan.staged_docx_sha256 != staged_docx.sha256
        or plan.staged_docx_byte_size != staged_docx.byte_size
    ):
        raise _assembly_error(
            AssemblyFailureCode.DELIVERY_PLAN_INVALID,
            AssemblyStage.DELIVERY_PLAN,
            "delivery plan does not match its intake snapshot or staged DOCX",
        )
    if DeliveryVariantPlan.from_dict(plan.to_dict()) != plan:
        raise _assembly_error(
            AssemblyFailureCode.DELIVERY_PLAN_INVALID,
            AssemblyStage.DELIVERY_PLAN,
            "delivery plan failed its serialization round trip",
        )


def _verify_transform_result(
    result: ImageTransformBatchResult,
    delivery_plan: DeliveryVariantPlan,
) -> None:
    try:
        verify_image_transform_result(
            result,
            delivery_plan.resolved_image_plans,
        )
    except ImageExecutionVerificationError as exc:
        raise _assembly_error(
            AssemblyFailureCode.IMAGE_TRANSFORM_RECEIPT_INVALID,
            AssemblyStage.IMAGE_TRANSFORM,
            str(exc),
        ) from exc


def _verify_layout_receipt(
    receipt: OfficeImageLayoutReceipt,
    request: OfficeImageLayoutRequest,
    delivery_plan: DeliveryVariantPlan,
) -> None:
    try:
        verify_office_layout_receipt(
            receipt,
            request,
            delivery_plan.resolved_image_plans,
        )
    except ImageExecutionVerificationError as exc:
        failure_code = (
            AssemblyFailureCode.OFFICE_LAYOUT_FAILED
            if exc.code == "office_layout_failed"
            else AssemblyFailureCode.OFFICE_LAYOUT_RECEIPT_INVALID
        )
        raise _assembly_error(
            failure_code,
            AssemblyStage.OFFICE_LAYOUT,
            str(exc),
        ) from exc



def _verify_delivery_sources(
    delivery_plan: DeliveryVariantPlan,
    *,
    variant_id: str,
) -> None:
    for plan in delivery_plan.resolved_image_plans:
        try:
            evidence = stable_file_evidence(plan.image_ref.source_path)
        except Exception as exc:
            raise _assembly_error(
                AssemblyFailureCode.SOURCE_DRIFT,
                AssemblyStage.VERIFY,
                f"image source is unavailable for job {plan.job_id}: {exc}",
                variant_id=variant_id,
                path=plan.image_ref.source_path,
            ) from exc
        if (
            evidence.sha256 != plan.image_ref.content_sha256
            or evidence.byte_size != plan.image_ref.byte_size
        ):
            raise _assembly_error(
                AssemblyFailureCode.SOURCE_DRIFT,
                AssemblyStage.VERIFY,
                f"image source drifted for job {plan.job_id}",
                variant_id=variant_id,
                path=plan.image_ref.source_path,
            )


def _verify_immutable_file(
    expected: FileEvidence,
    stage: AssemblyStage,
    *,
    variant_id: str = "",
) -> None:
    try:
        current = stable_file_evidence(expected.path)
    except Exception as exc:
        raise _assembly_error(
            AssemblyFailureCode.SOURCE_DRIFT,
            stage,
            str(exc),
            variant_id=variant_id,
            path=expected.path,
        ) from exc
    if not same_file_identity(current, expected):
        raise _assembly_error(
            AssemblyFailureCode.SOURCE_DRIFT,
            stage,
            "source DOCX changed during material assembly",
            variant_id=variant_id,
            path=expected.path,
        )


def _verify_final_baselines(
    transaction: OwnedAssemblyTransaction,
    stage: AssemblyStage,
    *,
    variant_id: str = "",
) -> None:
    try:
        transaction.verify_finals_unchanged()
    except TransactionViolation as exc:
        raise _assembly_error(
            AssemblyFailureCode.FINAL_DRIFT,
            stage,
            str(exc),
            variant_id=variant_id,
        ) from exc


def _check_cancel(
    cancel_check: CancelCheck | None,
    stage: AssemblyStage,
    *,
    variant_id: str = "",
) -> None:
    if cancel_check is not None and cancel_check():
        raise MaterialAssemblyCancelled(stage, variant_id=variant_id)


def _rollback_or_extend(
    transaction: OwnedAssemblyTransaction | None,
    error: MaterialAssemblyError,
) -> MaterialAssemblyError:
    if transaction is None:
        return error
    rollback_diagnostic: AssemblyDiagnostic | None = None
    try:
        transaction.restore_finals()
    except Exception as exc:
        rollback_diagnostic = AssemblyDiagnostic(
            AssemblyFailureCode.ROLLBACK_FAILED,
            AssemblyStage.ROLLBACK,
            str(exc),
        )
    finally:
        transaction.cleanup_owned()
    if rollback_diagnostic is None:
        return error
    return MaterialAssemblyError((*error.diagnostics, rollback_diagnostic))


def _map_exception(
    exc: Exception,
    stage: AssemblyStage,
    *,
    variant_id: str,
) -> MaterialAssemblyError:
    if isinstance(exc, ContentComposeCancelledError) or (
        isinstance(exc, ImageTransformBatchError)
        and exc.code == "cancelled"
    ):
        return MaterialAssemblyCancelled(stage, variant_id=variant_id)
    if stage is AssemblyStage.INTAKE_FREEZE:
        code = AssemblyFailureCode.INTAKE_FREEZE_FAILED
    elif stage is AssemblyStage.DEPENDENCY_INDEX:
        code = AssemblyFailureCode.DEPENDENCY_INDEX_FAILED
    elif stage is AssemblyStage.PIPELINE:
        code = AssemblyFailureCode.PIPELINE_CALLBACK_FAILED
    elif stage is AssemblyStage.CONTENT_COMPOSE:
        code = AssemblyFailureCode.CONTENT_COMPOSE_FAILED
    elif stage is AssemblyStage.IMAGE_PLAN:
        code = AssemblyFailureCode.IMAGE_PLAN_FAILED
    elif stage is AssemblyStage.IMAGE_TRANSFORM:
        code = AssemblyFailureCode.IMAGE_TRANSFORM_FAILED
    elif stage is AssemblyStage.OFFICE_LAYOUT:
        code = AssemblyFailureCode.OFFICE_LAYOUT_FAILED
    elif stage is AssemblyStage.VERIFY:
        code = AssemblyFailureCode.FINAL_VERIFY_FAILED
    elif stage is AssemblyStage.PUBLISH:
        code = AssemblyFailureCode.ATOMIC_PUBLISH_FAILED
    elif stage is AssemblyStage.PREFLIGHT:
        code = AssemblyFailureCode.INVALID_REQUEST
    else:
        code = AssemblyFailureCode.INTERNAL_ERROR
    return _assembly_error(
        code,
        stage,
        str(exc) or type(exc).__name__,
        variant_id=variant_id,
    )


def _assembly_error(
    code: AssemblyFailureCode,
    stage: AssemblyStage,
    message: str,
    *,
    variant_id: str = "",
    path: str = "",
) -> MaterialAssemblyError:
    return MaterialAssemblyError(
        (
            AssemblyDiagnostic(
                code=code,
                stage=stage,
                message=message,
                variant_id=variant_id,
                path=path,
            ),
        )
    )

__all__ = ["MaterialAssemblyDependencies", "MaterialAssemblyService"]
