"""Terminal path for contracts that intentionally publish no primary DOCX."""

from __future__ import annotations

from pathlib import Path

from src.application.materials import ExecutionMaterialSnapshot
from src.services.production_runtime.material_artifacts import (
    material_artifact_payload,
)


def run_material_only_delivery(
    *,
    config,
    input_path: Path,
    output_dir: Path,
    material_snapshot: ExecutionMaterialSnapshot | None,
    modules_total: int,
    progress_cb,
    cancel_check,
) -> dict[str, object] | None:
    """Publish material artifacts directly, or return ``None`` when inapplicable."""

    if not _is_material_only_delivery(config):
        return None
    if cancel_check():
        return {
            "status": "cancelled",
            "output_path": "",
            "output_paths": {},
            "report_paths": [],
            "failed_count": 0,
            "artifact_failure_count": 0,
            "error_text": "execution_cancelled",
        }
    progress_cb(0, 1, "生成材料清单和归档包")
    payload: dict[str, object] = {
        "status": "success",
        "summary": "材料清单和归档包已生成",
        "output_path": "",
        "output_paths": {},
        "report_paths": [],
        "failed_count": 0,
        "artifact_failure_count": 0,
        "error_text": "",
        "elapsed_seconds": 0.0,
        "modules_enabled": 0,
        "modules_total": modules_total,
        "execution_material_snapshot_id": (
            material_snapshot.snapshot_id if material_snapshot is not None else ""
        ),
        "material_only_delivery": True,
    }
    payload.update(
        material_artifact_payload(
            input_path=input_path,
            output_dir=output_dir,
            config=config,
            material_snapshot=material_snapshot,
            output_paths={},
        )
    )
    if not payload.get("material_manifest_paths"):
        payload.update(
            status="failed",
            failed_count=1,
            error_text="material_only_delivery_artifacts_missing",
        )
    receipt = payload.get("material_package_receipt")
    if isinstance(receipt, dict) and receipt.get("status") == "partial_success":
        payload["status"] = "partial_success"
        payload["error_text"] = "material_package_has_missing_references"
    progress_cb(1, 1, "Completed")
    return payload


def _is_material_only_delivery(config) -> bool:
    output = getattr(config, "output", None)
    presets = tuple(getattr(config, "delivery_presets", ()) or ())
    has_material_artifact = bool(
        getattr(output, "material_manifest", False)
        or getattr(output, "material_package", False)
        or any(
            getattr(getattr(preset, "artifacts", None), "material_manifest", False)
            or getattr(getattr(preset, "artifacts", None), "material_package", False)
            for preset in presets
        )
    )
    has_primary_document = bool(
        getattr(output, "final_docx", False)
        or any(
            getattr(getattr(preset, "artifacts", None), "final_docx", False)
            for preset in presets
        )
    )
    return has_material_artifact and not has_primary_document


__all__ = ["run_material_only_delivery"]
