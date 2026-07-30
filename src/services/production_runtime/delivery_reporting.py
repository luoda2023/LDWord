"""Delivery evidence planning and publication for production execution.

This module owns delivery-specific path semantics and auxiliary artifacts.  It
does not execute pipelines or depend on the workbench runner, so artifact
publication can be tested and failed independently of orchestration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.config.atomic_io import atomic_write_text
from src.config.delivery_preset_display import delivery_preset_display_name
from src.config.material_context import MaterialExecutionContext
from src.execution_diagnostics import build_execution_diagnostics
from src.product_report_writer import write_json_report, write_markdown_report
from src.reporting.execution_payload import plain_data
from src.reporting.material_assembly import (
    extract_attachment_bundles,
    extract_material_assembly,
    material_assembly_error_payload,
    material_assembly_receipt_payload,
)
from src.services.artifact_failure import capture_artifact_write
from src.shared.engine.docx_compare import write_compare_docx

from .material_artifacts import (
    material_package_path_map,
    material_package_receipt_payload,
    write_material_manifest,
    write_material_package_artifacts,
)


@dataclass(slots=True)
class ResultArtifactOutcome:
    compare_paths: dict[str, str]
    report_paths: list[str]
    intermediate_paths: dict[str, str]
    material_manifest_paths: dict[str, str]
    material_package_paths: dict[str, str]
    material_package_receipt: dict[str, object]
    artifact_failures: list[dict[str, str]]


def finalize_result_artifacts(
    result,
    *,
    input_path: Path,
    output_dir: Path,
    output_paths: dict[str, str],
    fallback_output_path: str,
    config,
    elapsed: float,
    modules_enabled: int,
    modules_total: int,
    material_diagnostics: list[dict],
    material_context: MaterialExecutionContext,
    style_source_summary: dict[str, object] | None,
    include_material_artifacts: bool,
) -> ResultArtifactOutcome:
    """Publish configured evidence consistently for every terminal branch."""

    failures: list[dict[str, str]] = []
    status = str(getattr(result, "status", "failed") or "failed")
    successful = bool(getattr(result, "success", False)) and status != "cancelled"

    compare_paths = (
        capture_artifact_write(
            failures,
            "compare_docx",
            lambda: _write_compare_docx_artifacts(
                result,
                input_path=input_path,
                output_dir=output_dir,
                output_paths=output_paths,
                fallback_output_path=fallback_output_path,
                config=config,
            ),
            {},
        )
        if successful
        else {}
    )
    report_paths = capture_artifact_write(
        failures,
        "reports",
        lambda: write_enabled_result_reports(
            result,
            input_path=input_path,
            output_dir=output_dir,
            output_paths=output_paths,
            fallback_output_path=fallback_output_path,
            config=config,
            elapsed=elapsed,
            modules_enabled=modules_enabled,
            modules_total=modules_total,
            material_diagnostics=material_diagnostics,
            material_context=material_context,
            style_source_summary=style_source_summary,
        ),
        [],
    )
    intermediate_paths = capture_artifact_write(
        failures,
        "intermediates",
        lambda: write_structured_intermediates(
            result,
            input_path=input_path,
            output_dir=output_dir,
            output_paths=output_paths,
            fallback_output_path=fallback_output_path,
            config=config,
            elapsed=elapsed,
            modules_enabled=modules_enabled,
            modules_total=modules_total,
        ),
        {},
    )

    material_manifest_paths: dict[str, str] = {}
    material_package_paths: dict[str, str] = {}
    material_package_receipt: dict[str, object] = {}
    if include_material_artifacts and status != "cancelled":
        material_manifest_paths = capture_artifact_write(
            failures,
            "material_manifest",
            lambda: write_material_manifest(
                input_path=input_path,
                output_dir=output_dir,
                config=config,
                material_context=material_context,
                material_diagnostics=material_diagnostics,
                output_paths=output_paths,
                compare_paths=compare_paths,
                report_paths=report_paths,
                intermediate_paths=intermediate_paths,
                result=result,
            ),
            {},
        )
        material_package_result = capture_artifact_write(
            failures,
            "material_package",
            lambda: write_material_package_artifacts(
                input_path=input_path,
                output_dir=output_dir,
                config=config,
                material_manifest_paths=material_manifest_paths,
                material_context=material_context,
                output_paths=output_paths,
                compare_paths=compare_paths,
                report_paths=report_paths,
                intermediate_paths=intermediate_paths,
                result=result,
            ),
            None,
        )
        material_package_paths = material_package_path_map(material_package_result)
        material_package_receipt = material_package_receipt_payload(
            material_package_result
        )

    return ResultArtifactOutcome(
        compare_paths=compare_paths,
        report_paths=report_paths,
        intermediate_paths=intermediate_paths,
        material_manifest_paths=material_manifest_paths,
        material_package_paths=material_package_paths,
        material_package_receipt=material_package_receipt,
        artifact_failures=failures,
    )


def should_force_delivery_presets(config) -> bool:
    presets = list(getattr(config, "delivery_presets", []) or [])
    if len(presets) > 1:
        return True
    if len(presets) != 1:
        return False

    preset = presets[0]
    preset_id = str(getattr(preset, "preset_id", "") or "").strip()
    default_id = str(getattr(config, "default_delivery_preset_id", "") or "").strip()
    if preset_id and preset_id != "final":
        return True
    if default_id and default_id != "final":
        return True

    output_dir_template = str(
        getattr(preset, "output_dir_template", "") or ""
    ).strip()
    if output_dir_template and output_dir_template != "{document_dir}/output":
        return True

    filename_template = str(getattr(preset, "filename_template", "") or "").strip()
    if filename_template and filename_template != "{stem}_{preset_id}":
        return True

    return False


def primary_output_path(config, output_paths: dict[str, str]) -> str:
    default_id = str(getattr(config, "default_delivery_preset_id", "") or "").strip()
    return primary_output_path_for_default(default_id, output_paths)


def primary_output_path_for_default(
    default_id: str,
    output_paths: dict[str, str],
) -> str:
    if default_id and output_paths.get(default_id):
        return output_paths[default_id]
    if output_paths.get("final"):
        return output_paths["final"]
    return next(iter(output_paths.values()), "")


def plan_delivery_artifact_paths(
    *,
    input_path: Path,
    output_dir: Path,
    config,
    output_paths: dict[str, str],
) -> dict[str, str]:
    """Plan every auxiliary delivery target before any group may execute."""

    planned: dict[str, str] = {}
    for preset in list(getattr(config, "delivery_presets", []) or []):
        preset_id = str(getattr(preset, "preset_id", "") or "").strip()
        if not preset_id:
            continue
        artifacts = getattr(preset, "artifacts", None)
        artifact_dir = delivery_report_dir(output_dir, input_path, preset)
        artifact_stem = delivery_report_stem(input_path, preset)

        candidates: list[tuple[str, Path]] = []
        if bool(getattr(artifacts, "report_json", False)):
            candidates.append(
                ("report_json", artifact_dir / f"{artifact_stem}_changes.json")
            )
        if bool(getattr(artifacts, "report_markdown", False)):
            candidates.append(
                ("report_markdown", artifact_dir / f"{artifact_stem}_changes.md")
            )
        revised_path = _preset_output_path(
            preset_id=preset_id,
            output_paths=output_paths,
            fallback_output_path="",
            config=config,
        )
        if (
            input_path.suffix.casefold() == ".docx"
            and revised_path
            and bool(getattr(artifacts, "compare_docx", False))
        ):
            candidates.append(
                ("compare_docx", artifact_dir / f"{artifact_stem}_compare.docx")
            )
        if bool(getattr(preset, "include_structured_intermediate", False)):
            candidates.append(
                (
                    "structured_intermediate",
                    artifact_dir / f"{artifact_stem}_intermediate.json",
                )
            )

        for artifact_kind, artifact_path in candidates:
            artifact_id = f"{preset_id}:{artifact_kind}"
            if artifact_id in planned:
                raise ValueError(f"duplicate planned artifact id: {artifact_id}")
            planned[artifact_id] = str(artifact_path)
    return planned


def _write_compare_docx_artifacts(
    result,
    *,
    input_path: Path,
    output_dir: Path,
    output_paths: dict[str, str],
    fallback_output_path: str,
    config,
) -> dict[str, str]:
    del result
    compare_paths: dict[str, str] = {}
    if input_path.suffix.lower() != ".docx":
        return compare_paths
    for preset in list(getattr(config, "delivery_presets", []) or []):
        preset_id = str(getattr(preset, "preset_id", "") or "").strip()
        if not preset_id:
            continue

        artifacts = getattr(preset, "artifacts", None)
        if not bool(getattr(artifacts, "compare_docx", False)):
            continue

        revised_path = _preset_output_path(
            preset_id=preset_id,
            output_paths=output_paths,
            fallback_output_path=fallback_output_path,
            config=config,
        )
        if not revised_path:
            continue
        revised = Path(revised_path)
        if not revised.exists():
            continue

        compare_dir = delivery_report_dir(output_dir, input_path, preset)
        compare_dir.mkdir(parents=True, exist_ok=True)
        compare_path = (
            compare_dir / f"{delivery_report_stem(input_path, preset)}_compare.docx"
        )
        write_compare_docx(
            input_path,
            revised,
            compare_path,
            compare_text=bool(getattr(artifacts, "compare_text", True)),
            compare_formatting=bool(getattr(artifacts, "compare_formatting", True)),
        )
        compare_paths[preset_id] = str(compare_path)
    return compare_paths


def write_structured_intermediates(
    result,
    *,
    input_path: Path,
    output_dir: Path,
    output_paths: dict[str, str],
    fallback_output_path: str,
    config,
    elapsed: float,
    modules_enabled: int,
    modules_total: int,
) -> dict[str, str]:
    intermediate_paths: dict[str, str] = {}
    for preset in list(getattr(config, "delivery_presets", []) or []):
        if not bool(getattr(preset, "include_structured_intermediate", False)):
            continue
        preset_id = str(getattr(preset, "preset_id", "") or "").strip()
        if not preset_id:
            continue

        artifact_dir = delivery_report_dir(output_dir, input_path, preset)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = (
            artifact_dir
            / f"{delivery_report_stem(input_path, preset)}_intermediate.json"
        )
        output_path = _preset_output_path(
            preset_id=preset_id,
            output_paths=output_paths,
            fallback_output_path=fallback_output_path,
            config=config,
        )
        payload = _structured_intermediate_payload(
            result,
            input_path=input_path,
            output_path=output_path,
            preset=preset,
            config=config,
            elapsed=elapsed,
            modules_enabled=modules_enabled,
            modules_total=modules_total,
        )
        atomic_write_text(
            artifact_path,
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        intermediate_paths[preset_id] = str(artifact_path)
    return intermediate_paths


def _preset_output_path(
    *,
    preset_id: str,
    output_paths: dict[str, str],
    fallback_output_path: str,
    config,
) -> str:
    direct = str(output_paths.get(preset_id) or "")
    if direct:
        return direct

    default_id = str(getattr(config, "default_delivery_preset_id", "") or "").strip()
    if preset_id == default_id:
        return str(fallback_output_path or "")

    presets = list(getattr(config, "delivery_presets", []) or [])
    if len(presets) == 1:
        return str(fallback_output_path or "")

    return ""


def _structured_intermediate_payload(
    result,
    *,
    input_path: Path,
    output_path: str,
    preset,
    config,
    elapsed: float,
    modules_enabled: int,
    modules_total: int,
) -> dict[str, object]:
    diagnostics = build_execution_diagnostics(result)
    assembly_receipt = material_assembly_receipt_payload(result)
    assembly_error = material_assembly_error_payload(result)
    material_assembly = extract_material_assembly(result)
    return {
        "kind": "delivery_structured_intermediate",
        "schema_version": 1,
        "input": str(input_path),
        "output": str(output_path or ""),
        "status": str(getattr(result, "status", "failed") or "failed"),
        "elapsed_seconds": round(elapsed, 2),
        "modules_enabled": modules_enabled,
        "modules_total": modules_total,
        "preset": delivery_preset_payload(preset),
        "diagnostics": {
            "count": diagnostics["count"],
            "items": diagnostics["items"],
        },
        "counts": _extract_count_result(result),
        "changes": _extract_change_records(result),
        "runtime_inputs": _runtime_inputs_payload(config),
        "context": pipeline_context_payload(
            getattr(result, "context", None),
            material_assembly_receipt=assembly_receipt,
            material_assembly_error=assembly_error,
        ),
        "result": {
            "material_assembly_receipt": assembly_receipt,
            "material_assembly_error": assembly_error,
        },
        "material_assembly": material_assembly,
        "attachment_bundles": extract_attachment_bundles(result),
        "material_dependency_usage": dict(
            material_assembly.get("dependency_usage") or {}
        ),
        "failed_items": list(getattr(result, "failed_items", []) or []),
    }


def delivery_preset_payload(preset) -> dict[str, object]:
    return {
        "preset_id": str(getattr(preset, "preset_id", "") or ""),
        "label": str(getattr(preset, "label", "") or ""),
        "display_label": delivery_preset_display_name(preset),
        "target_template_id": str(getattr(preset, "target_template_id", "") or ""),
        "output_dir_template": str(getattr(preset, "output_dir_template", "") or ""),
        "filename_template": str(getattr(preset, "filename_template", "") or ""),
        "artifacts": plain_data(getattr(preset, "artifacts", None)),
        "content_visibility_rules": plain_data(
            list(getattr(preset, "content_visibility_rules", []) or [])
        ),
        "include_structured_intermediate": bool(
            getattr(preset, "include_structured_intermediate", False)
        ),
        "report_level": str(getattr(preset, "report_level", "") or ""),
    }


def _runtime_inputs_payload(config) -> dict[str, object]:
    return {
        "entity_data": dict(getattr(config, "entity_data", {}) or {}),
        "entity_assets_dir": str(getattr(config, "entity_assets_dir", "") or ""),
        "images": plain_data(list(getattr(config, "images", []) or [])),
        "replacements": plain_data(list(getattr(config, "replacements", []) or [])),
    }


def pipeline_context_payload(
    context,
    *,
    material_assembly_receipt: dict[str, object] | None = None,
    material_assembly_error: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "material_assembly_receipt": material_assembly_receipt,
        "material_assembly_error": material_assembly_error,
    }
    if context is None:
        return payload
    payload.update(
        {
            "source_doc_path": str(getattr(context, "source_doc_path", "") or ""),
            "source_doc_dir": str(getattr(context, "source_doc_dir", "") or ""),
            "working_doc_path": str(getattr(context, "working_doc_path", "") or ""),
            "working_doc_dir": str(getattr(context, "working_doc_dir", "") or ""),
            "content_visibility_receipts": plain_data(
                getattr(context, "content_visibility_receipts", None) or {}
            ),
            "entity_values": dict(getattr(context, "entity_values", None) or {}),
            "source_values": dict(getattr(context, "source_values", None) or {}),
            "document_scope": plain_data(
                getattr(context, "document_scope_receipt", None) or {}
            ),
            "exam_question_schema": plain_data(
                getattr(context, "exam_question_schema", None)
            ),
            "journal_rule_source_governance": plain_data(
                getattr(context, "journal_rule_source_governance", None)
            ),
            "journal_citations": plain_data(
                getattr(context, "journal_citations", None)
            ),
            "journal_submission_package": plain_data(
                getattr(context, "journal_submission_package", None)
            ),
            "official_document_assembly": plain_data(
                getattr(context, "official_document_assembly", None)
            ),
            "official_numbering_preservation": plain_data(
                getattr(context, "official_numbering_preservation", None)
            ),
            "technical_chapter_inventory": plain_data(
                getattr(context, "technical_chapter_inventory", None)
            ),
            "application_section_word_limits": plain_data(
                getattr(context, "application_section_word_limits", None)
            ),
            "inserted_images": plain_data(
                getattr(context, "inserted_images", None) or []
            ),
        }
    )
    return payload


def _extract_change_records(result) -> list[dict[str, object]]:
    tracker = getattr(result, "tracker", None)
    if tracker is None:
        return []
    return [
        {
            "rule_name": getattr(record, "rule_name", ""),
            "target": getattr(record, "target", ""),
            "section": getattr(record, "section", ""),
            "change_type": getattr(record, "change_type", ""),
            "before": getattr(record, "before", ""),
            "after": getattr(record, "after", ""),
            "paragraph_index": getattr(record, "paragraph_index", -1),
            "success": bool(getattr(record, "success", True)),
            "failure_reason": getattr(record, "failure_reason", None),
        }
        for record in tracker.get_all()
    ]


def _extract_count_result(result) -> dict | None:
    context = getattr(result, "context", None)
    count_result = getattr(context, "count_result", None) if context is not None else None
    if count_result is None:
        return None
    to_dict = getattr(count_result, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    if isinstance(count_result, dict):
        return count_result
    return None


def write_enabled_result_reports(
    result,
    *,
    input_path: Path,
    output_dir: Path,
    output_paths: dict[str, str],
    fallback_output_path: str,
    config,
    elapsed: float,
    modules_enabled: int,
    modules_total: int,
    material_diagnostics: list[dict] | None = None,
    material_context: MaterialExecutionContext | None = None,
    style_source_summary: dict[str, object] | None = None,
) -> list[str]:
    """Write only configured reports for either success or failure evidence."""

    if should_force_delivery_presets(config):
        return write_delivery_reports(
            result,
            input_path=input_path,
            output_dir=output_dir,
            output_paths=output_paths,
            config=config,
            elapsed=elapsed,
            modules_enabled=modules_enabled,
            modules_total=modules_total,
            material_diagnostics=list(material_diagnostics or []),
            material_context=material_context,
            style_source_summary=style_source_summary,
        )

    output_cfg = getattr(config, "output", None)
    report_paths: list[str] = []
    final_output_path = (
        Path(fallback_output_path) if str(fallback_output_path or "") else None
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    if bool(getattr(output_cfg, "report_json", True)):
        report_json = output_dir / f"{input_path.stem}_changes.json"
        write_json_report(
            result,
            input_path=input_path,
            output_path=final_output_path,
            report_path=report_json,
            elapsed=elapsed,
            modules_enabled=modules_enabled,
            modules_total=modules_total,
            extra_diagnostics=list(material_diagnostics or []),
            style_source_summary=style_source_summary,
        )
        report_paths.append(str(report_json))
    if bool(getattr(output_cfg, "report_markdown", True)):
        report_markdown = output_dir / f"{input_path.stem}_changes.md"
        write_markdown_report(
            result,
            input_path=input_path,
            output_path=final_output_path,
            report_path=report_markdown,
            elapsed=elapsed,
            modules_enabled=modules_enabled,
            modules_total=modules_total,
            extra_diagnostics=list(material_diagnostics or []),
            style_source_summary=style_source_summary,
        )
        report_paths.append(str(report_markdown))
    return report_paths


def write_delivery_reports(
    result,
    *,
    input_path: Path,
    output_dir: Path,
    output_paths: dict[str, str],
    config,
    elapsed: float,
    modules_enabled: int,
    modules_total: int,
    material_diagnostics: list[dict] | None = None,
    material_context: MaterialExecutionContext | None = None,
    style_source_summary: dict[str, object] | None = None,
) -> list[str]:
    del material_context
    report_paths: list[str] = []
    for preset in list(getattr(config, "delivery_presets", []) or []):
        preset_id = str(getattr(preset, "preset_id", "") or "").strip()
        if not preset_id:
            continue
        artifacts = getattr(preset, "artifacts", None)
        output_path = output_paths.get(preset_id, "")
        output_report_path = Path(output_path) if output_path else None
        preset_payload = delivery_preset_payload(preset)
        report_stem = delivery_report_stem(input_path, preset)
        report_dir = delivery_report_dir(output_dir, input_path, preset)
        report_dir.mkdir(parents=True, exist_ok=True)

        if bool(getattr(artifacts, "report_json", False)):
            report_json = report_dir / f"{report_stem}_changes.json"
            write_json_report(
                result,
                input_path=input_path,
                output_path=output_report_path,
                report_path=report_json,
                elapsed=elapsed,
                modules_enabled=modules_enabled,
                modules_total=modules_total,
                extra_diagnostics=list(material_diagnostics or []),
                style_source_summary=style_source_summary,
                delivery_preset=preset_payload,
            )
            report_paths.append(str(report_json))

        if bool(getattr(artifacts, "report_markdown", False)):
            report_md = report_dir / f"{report_stem}_changes.md"
            write_markdown_report(
                result,
                input_path=input_path,
                output_path=output_report_path,
                report_path=report_md,
                elapsed=elapsed,
                modules_enabled=modules_enabled,
                modules_total=modules_total,
                extra_diagnostics=list(material_diagnostics or []),
                style_source_summary=style_source_summary,
                delivery_preset=preset_payload,
            )
            report_paths.append(str(report_md))
    return report_paths


class _SafeReportFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def delivery_report_stem(input_path: Path, preset) -> str:
    template = str(getattr(preset, "filename_template", "") or "").strip()
    if not template:
        template = "{stem}_{preset_id}"
    rendered = template.format_map(
        _SafeReportFormatDict(
            {
                "document_dir": str(input_path.parent),
                "output_dir": "",
                "stem": input_path.stem,
                "suffix": input_path.suffix or ".docx",
                "preset_id": str(getattr(preset, "preset_id", "") or ""),
                "preset_label": delivery_preset_display_name(preset),
            }
        )
    )
    return Path(rendered).stem or (
        f"{input_path.stem}_{getattr(preset, 'preset_id', 'final')}"
    )


def delivery_report_dir(base_output_dir: Path, input_path: Path, preset) -> Path:
    template = str(getattr(preset, "output_dir_template", "") or "").strip()
    if not template or template == "{document_dir}/output":
        return base_output_dir
    rendered = template.format_map(
        _SafeReportFormatDict(
            {
                "document_dir": str(input_path.parent),
                "output_dir": str(base_output_dir),
                "stem": input_path.stem,
                "suffix": input_path.suffix or ".docx",
                "preset_id": str(getattr(preset, "preset_id", "") or ""),
                "preset_label": delivery_preset_display_name(preset),
            }
        )
    )
    path = Path(rendered)
    return path if path.is_absolute() else base_output_dir / path


__all__ = [
    "ResultArtifactOutcome",
    "delivery_preset_payload",
    "delivery_report_dir",
    "delivery_report_stem",
    "finalize_result_artifacts",
    "pipeline_context_payload",
    "plan_delivery_artifact_paths",
    "primary_output_path",
    "primary_output_path_for_default",
    "should_force_delivery_presets",
    "write_delivery_reports",
    "write_enabled_result_reports",
    "write_structured_intermediates",
]
