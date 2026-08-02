"""Prepare material-bound DOCX inputs and verify observable format changes."""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.application.materials import (
    ExecutionMaterialRecord,
    ExecutionMaterialSnapshot,
)
from src.config.resolved import ResolvedConfig
from src.document_batch.material_resources import materialize_record_resources
from src.services.docx_format_change import compare_docx_formatting


@dataclass(frozen=True, slots=True)
class PreparedFormattingInput:
    path: Path
    work_dir: Path | None = None
    materialized_resource_count: int = 0

    def cleanup(self) -> None:
        if self.work_dir is not None:
            shutil.rmtree(self.work_dir, ignore_errors=True)


def is_production_module_requested(
    config: ResolvedConfig,
    module_name: str,
    record: ExecutionMaterialRecord | None,
) -> bool:
    """Force exact field filling when a material record carries field data."""

    return bool(config.is_module_enabled(module_name)) or bool(
        module_name == "entity_fill" and record is not None and record.field_values
    )


def production_module_selector(
    config: ResolvedConfig,
    record: ExecutionMaterialRecord | None,
) -> Callable[[str], bool]:
    return lambda name: is_production_module_requested(config, name, record)


def prepare_formatting_input(
    source_path: Path,
    *,
    snapshot: ExecutionMaterialSnapshot | None,
    record: ExecutionMaterialRecord | None,
    output_dir: Path,
) -> PreparedFormattingInput:
    if snapshot is None or record is None or source_path.suffix.casefold() != ".docx":
        return PreparedFormattingInput(path=source_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = Path(
        tempfile.mkdtemp(prefix=".alavette-material-format-", dir=output_dir)
    )
    materialized = work_dir / source_path.name
    try:
        materialize_record_resources(
            source_path,
            materialized,
            record=record,
            resource_domains=snapshot.resource_domains,
            image_policy=snapshot.image_policy,
            work_dir=work_dir,
        )
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
    return PreparedFormattingInput(
        path=materialized,
        work_dir=work_dir,
        materialized_resource_count=sum(
            len(resources) for resources in record.resources.values()
        ),
    )


def collect_format_change_evidence(
    before_path: Path,
    after_path: str | Path,
) -> dict[str, object]:
    target = Path(after_path) if str(after_path or "").strip() else None
    if target is None or not target.is_file() or target.suffix.casefold() != ".docx":
        return _unavailable("primary_docx_output_missing")
    try:
        return compare_docx_formatting(before_path, target)
    except (OSError, TypeError, ValueError, zipfile.BadZipFile) as exc:
        return _unavailable(f"{type(exc).__name__}:{exc}")


def apply_required_format_change_policy(
    payload: dict[str, object],
    evidence: dict[str, object],
    *,
    required: bool,
) -> None:
    if not (
        required
        and evidence.get("status") == "compared"
        and not bool(evidence.get("format_changed"))
    ):
        return
    payload["status"] = "partial_success"
    payload["warnings"] = [
        "formatting_noop:文档格式与处理前一致，请检查模板规则是否启用或源文档是否已符合要求。"
    ]
    payload["summary"] = (
        str(payload.get("summary") or "") + "；未检测到可观察的格式变化"
    )


def _unavailable(reason: str) -> dict[str, object]:
    return {
        "schema_version": "docx-format-change-v1",
        "status": "unavailable",
        "reason": reason,
    }


__all__ = [
    "PreparedFormattingInput",
    "apply_required_format_change_policy",
    "collect_format_change_evidence",
    "is_production_module_requested",
    "prepare_formatting_input",
    "production_module_selector",
]


def document_scope_pipeline_kwargs(context) -> dict[str, object]:
    evidence, decisions = context
    return {
        "document_structure_evidence": evidence,
        "document_scope_decisions": tuple(decisions or ()),
    }
