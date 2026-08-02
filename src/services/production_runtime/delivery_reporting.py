"""Publish delivery-preset reports, comparisons, and intermediate evidence.

The production pipeline owns the primary DOCX transaction.  This module owns
only auxiliary delivery artifacts and records each publication failure without
hiding a successfully published primary document.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from src.application.materials import ExecutionMaterialSnapshot
from src.config.atomic_io import atomic_write_text
from src.config.delivery_preset_display import delivery_preset_display_name
from src.execution_diagnostics import build_execution_diagnostics
from src.product_report_writer import write_json_report, write_markdown_report
from src.reporting.execution_payload import plain_data
from src.services.artifact_failure import capture_artifact_write
from src.services.production_runtime.material_artifacts import (
    MaterialArtifactOutcome,
    publish_material_artifacts,
)
from src.shared.engine.docx_compare import write_compare_docx


@dataclass(frozen=True, slots=True)
class ResultArtifactOutcome:
    compare_paths: dict[str, str] = field(default_factory=dict)
    report_paths: list[str] = field(default_factory=list)
    intermediate_paths: dict[str, str] = field(default_factory=dict)
    material_manifest_paths: dict[str, str] = field(default_factory=dict)
    material_package_paths: dict[str, str] = field(default_factory=dict)
    material_package_receipt: dict[str, object] = field(default_factory=dict)
    artifact_failures: list[dict[str, str]] = field(default_factory=list)

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "compare_paths": dict(self.compare_paths),
            "report_paths": list(self.report_paths),
            "intermediate_paths": dict(self.intermediate_paths),
        }
        if self.material_manifest_paths:
            payload["material_manifest_paths"] = dict(
                self.material_manifest_paths
            )
        if self.material_package_paths:
            payload["material_package_paths"] = dict(self.material_package_paths)
            payload["material_package_receipt"] = dict(
                self.material_package_receipt
            )
        return payload


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
    material_snapshot: ExecutionMaterialSnapshot | None,
) -> ResultArtifactOutcome:
    """Publish configured evidence for a non-cancelled terminal result."""

    failures: list[dict[str, str]] = []
    successful = bool(getattr(result, "success", False)) and str(
        getattr(result, "status", "") or ""
    ) != "cancelled"
    compare_paths = (
        capture_artifact_write(
            failures,
            "compare_docx",
            lambda: _write_compare_docx_artifacts(
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
        ),
        [],
    )
    intermediate_paths = capture_artifact_write(
        failures,
        "structured_intermediate",
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
    material_outcome = capture_artifact_write(
        failures,
        "material_artifacts",
        lambda: publish_material_artifacts(
            input_path=input_path,
            output_dir=output_dir,
            config=config,
            material_snapshot=material_snapshot,
            output_paths=output_paths,
            report_paths=report_paths,
            compare_paths=compare_paths,
            intermediate_paths=intermediate_paths,
        ),
        MaterialArtifactOutcome(),
    )
    return ResultArtifactOutcome(
        compare_paths=compare_paths,
        report_paths=report_paths,
        intermediate_paths=intermediate_paths,
        material_manifest_paths=material_outcome.material_manifest_paths,
        material_package_paths=material_outcome.material_package_paths,
        material_package_receipt=material_outcome.material_package_receipt,
        artifact_failures=failures,
    )


def should_force_delivery_presets(config) -> bool:
    """Return whether the scene describes business delivery variants."""

    presets = list(getattr(config, "delivery_presets", ()) or ())
    if len(presets) != 1:
        return bool(presets)
    preset = presets[0]
    preset_id = str(getattr(preset, "preset_id", "") or "").strip()
    default_id = str(
        getattr(config, "default_delivery_preset_id", "") or ""
    ).strip()
    output_dir_template = str(
        getattr(preset, "output_dir_template", "") or ""
    ).strip()
    filename_template = str(
        getattr(preset, "filename_template", "") or ""
    ).strip()
    return any(
        (
            preset_id not in {"", "final"},
            default_id not in {"", "final"},
            output_dir_template not in {"", "{document_dir}/output"},
            filename_template not in {"", "{stem}_{preset_id}"},
        )
    )


def primary_output_path(config, output_paths: dict[str, str]) -> str:
    default_id = str(
        getattr(config, "default_delivery_preset_id", "") or ""
    ).strip()
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
    """Plan auxiliary paths and reject cross-preset path collisions."""

    planned: dict[str, str] = {}
    identities: set[str] = set()
    for preset in list(getattr(config, "delivery_presets", ()) or ()):
        preset_id = str(getattr(preset, "preset_id", "") or "").strip()
        if not preset_id:
            continue
        artifacts = getattr(preset, "artifacts", None)
        directory = delivery_report_dir(output_dir, input_path, preset)
        stem = delivery_report_stem(input_path, preset)
        candidates: list[tuple[str, Path]] = []
        if bool(getattr(artifacts, "report_json", False)):
            candidates.append(("report_json", directory / f"{stem}_changes.json"))
        if bool(getattr(artifacts, "report_markdown", False)):
            candidates.append(
                ("report_markdown", directory / f"{stem}_changes.md")
            )
        if bool(getattr(artifacts, "compare_docx", False)) and output_paths.get(
            preset_id
        ):
            candidates.append(("compare_docx", directory / f"{stem}_compare.docx"))
        if bool(getattr(preset, "include_structured_intermediate", False)):
            candidates.append(
                ("structured_intermediate", directory / f"{stem}_intermediate.json")
            )
        for artifact_kind, path in candidates:
            identity = os.path.normcase(str(path.resolve(strict=False)))
            if identity in identities:
                raise ValueError(f"delivery_artifact_path_collision:{path}")
            identities.add(identity)
            planned[f"{preset_id}:{artifact_kind}"] = str(path)
    return planned


def _write_compare_docx_artifacts(
    *,
    input_path: Path,
    output_dir: Path,
    output_paths: dict[str, str],
    fallback_output_path: str,
    config,
) -> dict[str, str]:
    compare_paths: dict[str, str] = {}
    if input_path.suffix.casefold() != ".docx":
        return compare_paths
    plan_delivery_artifact_paths(
        input_path=input_path,
        output_dir=output_dir,
        config=config,
        output_paths=output_paths,
    )
    for preset in list(getattr(config, "delivery_presets", ()) or ()):
        preset_id = str(getattr(preset, "preset_id", "") or "").strip()
        artifacts = getattr(preset, "artifacts", None)
        if not preset_id or not bool(getattr(artifacts, "compare_docx", False)):
            continue
        revised_path = _preset_output_path(
            preset_id=preset_id,
            output_paths=output_paths,
            fallback_output_path=fallback_output_path,
            config=config,
        )
        revised = Path(revised_path) if revised_path else None
        if revised is None or not revised.is_file():
            continue
        target = delivery_report_dir(output_dir, input_path, preset) / (
            f"{delivery_report_stem(input_path, preset)}_compare.docx"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".alavette-compare-",
            dir=target.parent,
        ) as temporary_directory:
            stage = Path(temporary_directory) / target.name
            write_compare_docx(
                input_path,
                revised,
                stage,
                compare_text=bool(getattr(artifacts, "compare_text", True)),
                compare_formatting=bool(
                    getattr(artifacts, "compare_formatting", True)
                ),
            )
            os.replace(stage, target)
        compare_paths[preset_id] = str(target)
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
    paths: dict[str, str] = {}
    for preset in list(getattr(config, "delivery_presets", ()) or ()):
        if not bool(getattr(preset, "include_structured_intermediate", False)):
            continue
        preset_id = str(getattr(preset, "preset_id", "") or "").strip()
        if not preset_id:
            continue
        directory = delivery_report_dir(output_dir, input_path, preset)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{delivery_report_stem(input_path, preset)}_intermediate.json"
        payload = _structured_intermediate_payload(
            result,
            input_path=input_path,
            output_path=_preset_output_path(
                preset_id=preset_id,
                output_paths=output_paths,
                fallback_output_path=fallback_output_path,
                config=config,
            ),
            preset=preset,
            elapsed=elapsed,
            modules_enabled=modules_enabled,
            modules_total=modules_total,
        )
        atomic_write_text(
            path,
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        paths[preset_id] = str(path)
    return paths


def _structured_intermediate_payload(
    result,
    *,
    input_path: Path,
    output_path: str,
    preset,
    elapsed: float,
    modules_enabled: int,
    modules_total: int,
) -> dict[str, object]:
    diagnostics = build_execution_diagnostics(result)
    return {
        "kind": "delivery_structured_intermediate",
        "schema_version": 1,
        "visibility": "local_diagnostic",
        "input": str(input_path),
        "output": str(output_path or ""),
        "status": str(getattr(result, "status", "failed") or "failed"),
        "elapsed_seconds": round(elapsed, 2),
        "modules_enabled": modules_enabled,
        "modules_total": modules_total,
        "preset": delivery_preset_payload(preset),
        "diagnostics": diagnostics,
        "counts": _extract_count_result(result),
        "changes": _extract_change_records(result),
        "context": pipeline_context_payload(getattr(result, "context", None)),
        "failed_items": plain_data(list(getattr(result, "failed_items", ()) or ())),
    }


def delivery_preset_payload(preset) -> dict[str, object]:
    return {
        "preset_id": str(getattr(preset, "preset_id", "") or ""),
        "label": str(getattr(preset, "label", "") or ""),
        "display_label": delivery_preset_display_name(preset),
        "target_template_id": str(getattr(preset, "target_template_id", "") or ""),
        "output_dir_template": str(
            getattr(preset, "output_dir_template", "") or ""
        ),
        "filename_template": str(getattr(preset, "filename_template", "") or ""),
        "artifacts": plain_data(getattr(preset, "artifacts", None)),
        "content_visibility_rules": plain_data(
            list(getattr(preset, "content_visibility_rules", ()) or ())
        ),
        "include_structured_intermediate": bool(
            getattr(preset, "include_structured_intermediate", False)
        ),
        "report_level": str(getattr(preset, "report_level", "") or ""),
    }


def pipeline_context_payload(context) -> dict[str, object]:
    if context is None:
        return {}
    names = (
        "source_doc_path",
        "source_doc_dir",
        "working_doc_path",
        "working_doc_dir",
        "content_visibility_receipts",
        "entity_values",
        "source_values",
        "document_scope_receipt",
        "exam_question_schema",
        "journal_rule_source_governance",
        "journal_citations",
        "journal_submission_package",
        "official_document_assembly",
        "official_numbering_preservation",
        "technical_chapter_inventory",
        "application_section_word_limits",
        "inserted_images",
    )
    return {
        name: plain_data(getattr(context, name, None))
        for name in names
        if getattr(context, name, None) not in (None, "", [], {})
    }


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


def _extract_count_result(result) -> dict[str, object] | None:
    context = getattr(result, "context", None)
    count_result = getattr(context, "count_result", None) if context else None
    if count_result is None:
        return None
    to_dict = getattr(count_result, "to_dict", None)
    if callable(to_dict):
        return plain_data(to_dict())
    return plain_data(count_result) if isinstance(count_result, dict) else None


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
) -> list[str]:
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
        )
    output = getattr(config, "output", None)
    final_path = Path(fallback_output_path) if fallback_output_path else None
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    common = {
        "result": result,
        "input_path": input_path,
        "output_path": final_path,
        "elapsed": elapsed,
        "modules_enabled": modules_enabled,
        "modules_total": modules_total,
    }
    if bool(getattr(output, "report_json", True)):
        path = output_dir / f"{input_path.stem}_changes.json"
        write_json_report(report_path=path, **common)
        paths.append(str(path))
    if bool(getattr(output, "report_markdown", True)):
        path = output_dir / f"{input_path.stem}_changes.md"
        write_markdown_report(report_path=path, **common)
        paths.append(str(path))
    return paths


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
) -> list[str]:
    paths: list[str] = []
    for preset in list(getattr(config, "delivery_presets", ()) or ()):
        preset_id = str(getattr(preset, "preset_id", "") or "").strip()
        if not preset_id:
            continue
        artifacts = getattr(preset, "artifacts", None)
        directory = delivery_report_dir(output_dir, input_path, preset)
        directory.mkdir(parents=True, exist_ok=True)
        stem = delivery_report_stem(input_path, preset)
        common = {
            "result": result,
            "input_path": input_path,
            "output_path": (
                Path(output_paths[preset_id]) if output_paths.get(preset_id) else None
            ),
            "elapsed": elapsed,
            "modules_enabled": modules_enabled,
            "modules_total": modules_total,
            "delivery_preset": delivery_preset_payload(preset),
        }
        if bool(getattr(artifacts, "report_json", False)):
            path = directory / f"{stem}_changes.json"
            write_json_report(report_path=path, **common)
            paths.append(str(path))
        if bool(getattr(artifacts, "report_markdown", False)):
            path = directory / f"{stem}_changes.md"
            write_markdown_report(report_path=path, **common)
            paths.append(str(path))
    return paths


class _SafeReportFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def delivery_report_stem(input_path: Path, preset) -> str:
    template = str(getattr(preset, "filename_template", "") or "").strip()
    rendered = (template or "{stem}_{preset_id}").format_map(
        _report_format_values(input_path, Path(), preset)
    )
    return Path(rendered).stem or f"{input_path.stem}_final"


def delivery_report_dir(
    base_output_dir: Path,
    input_path: Path,
    preset,
) -> Path:
    template = str(getattr(preset, "output_dir_template", "") or "").strip()
    if template in {"", "{document_dir}/output"}:
        return base_output_dir
    rendered = template.format_map(
        _report_format_values(input_path, base_output_dir, preset)
    )
    path = Path(rendered)
    return path if path.is_absolute() else base_output_dir / path


def _report_format_values(
    input_path: Path,
    output_dir: Path,
    preset,
) -> _SafeReportFormatDict:
    return _SafeReportFormatDict(
        {
            "document_dir": str(input_path.parent),
            "output_dir": str(output_dir),
            "stem": input_path.stem,
            "suffix": input_path.suffix or ".docx",
            "preset_id": str(getattr(preset, "preset_id", "") or ""),
            "preset_label": delivery_preset_display_name(preset),
        }
    )


def _preset_output_path(
    *,
    preset_id: str,
    output_paths: dict[str, str],
    fallback_output_path: str,
    config,
) -> str:
    if output_paths.get(preset_id):
        return str(output_paths[preset_id])
    default_id = str(
        getattr(config, "default_delivery_preset_id", "") or ""
    ).strip()
    presets = list(getattr(config, "delivery_presets", ()) or ())
    if preset_id == default_id or len(presets) == 1:
        return str(fallback_output_path or "")
    return ""


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
