from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from shutil import copy2

from docx import Document

from src.config.entity import EntityProfile
from src.config.material_context import MaterialExecutionContext
from src.config.scene import DeliveryPreset, SceneWorkspace
from src.pipeline.context import PipelineContext
from src.pipeline.result import PipelineResult
from src.report_writer import write_json_report, write_markdown_report
from src.reporting.material_assembly import (
    extract_attachment_bundles,
    extract_material_assembly,
)
from src.services.material_attachments import (
    AttachmentBundleProcessingError,
    AttachmentProcessingDiagnostic,
)
from src.services.material_execution import (
    AssemblyDiagnostic,
    AssemblyFailureCode,
    AssemblyStage,
    MaterialAssemblyError,
    MaterialAssemblyRequest,
    MaterialAssemblyService,
    MaterialPipelineOutcome,
    MaterialVariantRequest,
    PipelineVisibilityEvidence,
    VisibilityEvidenceKind,
)
from src.shared.engine.office_image_layout import OfficeImageProvider
from src.services.production_runtime import delivery_reporting
from src.services.production_runtime.material_artifacts import _material_manifest_payload


class _CopyPipeline:
    def __call__(self, request, *, cancel_check=None):
        _ = cancel_check
        evidence = []
        for target in request.targets:
            copy2(request.prepared_input.path, target.owned_stage_output_path)
            evidence.append(
                PipelineVisibilityEvidence(
                    variant_id=target.variant_id,
                    kind=VisibilityEvidenceKind.NOT_APPLICABLE,
                    not_applicable_reason="no visibility rules configured",
                )
            )
        return MaterialPipelineOutcome(tuple(evidence))


def _successful_receipt(tmp_path: Path):
    source = tmp_path / "source.docx"
    final = tmp_path / "final.docx"
    document = Document()
    document.add_paragraph("source")
    document.save(source)
    request = MaterialAssemblyRequest(
        source_docx_path=str(source),
        profile=EntityProfile(profile_id="profile-a", profile_name="Profile A"),
        frozen_field_values={"project": "Alpha"},
        material_schema_id="schema-a",
        material_schema_version="1",
        variants=(
            MaterialVariantRequest(
                variant_id="final",
                variant_version="1",
                final_output_path=str(final),
                rule_versions={"delivery": "1"},
            ),
        ),
        office_provider=OfficeImageProvider.WORD,
            rule_versions={"content": "1", "image": "1"},
            work_root=str(tmp_path / "work"),
            image_cache_dir=str(tmp_path / "image-cache"),
        )
    return MaterialAssemblyService(_CopyPipeline()).execute(request)


def _manifest_payload(
    tmp_path: Path,
    *,
    result: PipelineResult | None,
) -> dict[str, object]:
    return _material_manifest_payload(
        input_path=tmp_path / "source.docx",
        config=SceneWorkspace(),
        material_context=MaterialExecutionContext(
            profile_id="profile-a",
            profile_name="Profile A",
            entity_data={"project": "Alpha"},
        ),
        material_diagnostics=[],
        output_paths={},
        compare_paths={},
        report_paths=[],
        intermediate_paths={},
        result=result,
    )


def test_reports_use_exact_receipt_and_render_variant_stage_evidence(tmp_path: Path):
    receipt = _successful_receipt(tmp_path)
    result = PipelineResult(success=True, material_assembly_receipt=receipt)
    report_json = tmp_path / "report.json"
    report_md = tmp_path / "report.md"

    write_json_report(
        result,
        input_path=tmp_path / "source.docx",
        output_path=tmp_path / "final.docx",
        report_path=report_json,
        elapsed=0.5,
        modules_enabled=0,
        modules_total=0,
    )
    write_markdown_report(
        result,
        input_path=tmp_path / "source.docx",
        output_path=tmp_path / "final.docx",
        report_path=report_md,
        elapsed=0.5,
        modules_enabled=0,
        modules_total=0,
    )

    assembly = json.loads(report_json.read_text(encoding="utf-8"))["material_assembly"]
    variant = assembly["variants"][0]
    assert assembly["status"] == "applied"
    assert assembly["receipt"] == receipt.to_dict()
    assert assembly["snapshot"]["snapshot_id"] == receipt.intake_snapshot.snapshot_id
    assert assembly["dependencies"]["index_id"] == receipt.dependency_index.index_id
    assert assembly["dependencies"]["source_revision_count"] == 1
    assert assembly["compose"]["receipt_id"] == receipt.content_compose_receipt.receipt_id
    assert assembly["pipeline"]["variant_count"] == 1
    assert assembly["pipeline"]["output_count"] == 1
    assert variant["configured"]["final_output_path"] == str(tmp_path / "final.docx")
    assert variant["planned"]["plan_id"] == receipt.variants[0].delivery_plan.plan_id
    assert variant["applied"]["publish"]["sha256"] == sha256(
        (tmp_path / "final.docx").read_bytes()
    ).hexdigest()
    assert variant["not_applicable"]["stages"] == [
        "content_visibility",
        "office_layout",
    ]
    assert variant["failed"] == []
    markdown = report_md.read_text(encoding="utf-8")
    assert "## 资料装配执行" in markdown
    assert "configured=yes" in markdown
    assert "not_applicable=content_visibility,office_layout" in markdown
    assert "publish=" in markdown


def test_manifest_separates_configured_applied_and_failure(tmp_path: Path):
    receipt = _successful_receipt(tmp_path)
    success_result = PipelineResult(success=True, material_assembly_receipt=receipt)
    configured_only = _manifest_payload(tmp_path, result=PipelineResult(success=True))
    applied = _manifest_payload(tmp_path, result=success_result)

    assert configured_only["execution"]["status"] == "configured_only"
    assert configured_only["execution"]["applied"] is None
    assert configured_only["execution"]["failure"] is None
    assert configured_only["execution"]["configured"]["fields"][0]["key"] == "project"
    assert applied["execution"]["status"] == "applied"
    assert applied["execution"]["configured"] == configured_only["execution"]["configured"]
    assert applied["execution"]["applied"]["receipt"] == receipt.to_dict()
    assert applied["material_dependencies"] == applied["execution"]["applied"][
        "dependencies"
    ]

    error = MaterialAssemblyError(
        (
            AssemblyDiagnostic(
                code=AssemblyFailureCode.OFFICE_LAYOUT_FAILED,
                stage=AssemblyStage.OFFICE_LAYOUT,
                message="layout failed",
                variant_id="final",
            ),
        )
    )
    failed_result = PipelineResult(
        success=False,
        material_assembly_error=error,
    )
    failed = _manifest_payload(tmp_path, result=failed_result)
    assert failed["execution"]["status"] == "failed"
    assert failed["execution"]["applied"] is None
    assert failed["execution"]["failure"] == error.to_dict()
    failure_projection = extract_material_assembly(failed_result)
    assert failure_projection["variants"][0]["failed"][0]["stage"] == "office_layout"


def test_attachment_cancellation_has_distinct_report_status():
    result = PipelineResult(success=False, status="cancelled", cancelled=True)
    result.attachment_bundle_errors = {
        "evidence": AttachmentBundleProcessingError(
            (
                AttachmentProcessingDiagnostic(
                    code="attachment_processing_cancelled",
                    message="cancelled by user",
                ),
            )
        )
    }

    projection = extract_attachment_bundles(result)

    assert projection["status"] == "cancelled"
    assert projection["cancelled_binding_count"] == 1
    assert projection["cancelled_roles"] == ["evidence"]


def test_structured_intermediate_carries_receipt_in_result_and_context_atomically(
    tmp_path: Path,
    monkeypatch,
):
    receipt = _successful_receipt(tmp_path)
    context = PipelineContext(
        source_doc_path=str(tmp_path / "source.docx"),
        source_doc_dir=str(tmp_path),
    )
    result = PipelineResult(
        success=True,
        context=context,
        material_assembly_receipt=receipt,
    )
    preset = DeliveryPreset(
        preset_id="review",
        output_dir_template="review",
        include_structured_intermediate=True,
    )
    config = SceneWorkspace(
        default_delivery_preset_id="review",
        delivery_presets=[preset],
    )
    writes: list[Path] = []
    real_atomic_write = delivery_reporting.atomic_write_text

    def _tracked_atomic_write(path, text, *, encoding="utf-8"):
        writes.append(Path(path))
        return real_atomic_write(path, text, encoding=encoding)

    monkeypatch.setattr(delivery_reporting, "atomic_write_text", _tracked_atomic_write)
    paths = delivery_reporting.write_structured_intermediates(
        result,
        input_path=tmp_path / "source.docx",
        output_dir=tmp_path / "output",
        output_paths={"review": str(tmp_path / "final.docx")},
        fallback_output_path=str(tmp_path / "final.docx"),
        config=config,
        elapsed=0.5,
        modules_enabled=0,
        modules_total=0,
    )

    assert len(writes) == 1
    payload = json.loads(Path(paths["review"]).read_text(encoding="utf-8"))
    assert payload["result"]["material_assembly_receipt"] == receipt.to_dict()
    assert payload["context"]["material_assembly_receipt"] == receipt.to_dict()
    assert payload["material_assembly"]["status"] == "applied"
    assert payload["material_assembly"]["receipt_id"] == receipt.receipt_id
