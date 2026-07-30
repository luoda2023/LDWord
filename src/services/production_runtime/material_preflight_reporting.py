"""Publish fail-closed material-preflight evidence and auxiliary artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from src.config.atomic_io import atomic_write_text
from src.config.material_context import MaterialExecutionContext
from src.config.resolver import resolve_config
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig
from src.reporting.exam_sections import format_exam_markdown_import_markdown
from src.reporting.execution_payload import plain_data
from src.shared.io.artifact_publication import StagedArtifact, publish_staged_artifacts

from src.services.artifact_failure import (
    apply_artifact_failures,
    capture_artifact_write,
)
from .material_artifacts import (
    material_artifact_path_map,
    material_package_path_map,
    material_package_receipt_payload,
    write_material_manifest,
    write_material_package_artifacts,
)


def attach_material_preflight_reports(
    payload: dict[str, object],
    *,
    input_path: Path,
    output_dir: Path,
    template: TemplateConfig,
    scene: SceneWorkspace,
    material_context: MaterialExecutionContext | None = None,
) -> None:
    """Attach preflight evidence without hiding the original business failure."""

    runtime_material = (
        material_context.clone()
        if isinstance(material_context, MaterialExecutionContext)
        else MaterialExecutionContext()
    )
    config = resolve_config(template, scene, **runtime_material.to_resolve_kwargs())
    output_cfg = getattr(config, "output", None)
    diagnostics = list(payload.get("material_diagnostics") or [])
    artifact_failures: list[dict[str, str]] = []
    report_payload = _material_preflight_report_payload(
        payload,
        input_path=input_path,
        diagnostics=diagnostics,
    )
    report_paths = capture_artifact_write(
        artifact_failures,
        "material_preflight_reports",
        lambda: _publish_material_preflight_reports(
            report_payload,
            input_path=input_path,
            output_dir=output_dir,
            include_json=bool(getattr(output_cfg, "report_json", True)),
            include_markdown=bool(getattr(output_cfg, "report_markdown", True)),
        ),
        [],
    )
    payload["report_paths"] = report_paths
    payload["material_manifest_paths"] = capture_artifact_write(
        artifact_failures,
        "material_manifest",
        lambda: write_material_manifest(
            input_path=input_path,
            output_dir=output_dir,
            config=config,
            material_context=runtime_material,
            material_diagnostics=diagnostics,
            output_paths={},
            compare_paths={},
            report_paths=report_paths,
            intermediate_paths={},
        ),
        {},
    )
    material_package_result = capture_artifact_write(
        artifact_failures,
        "material_package",
        lambda: write_material_package_artifacts(
            input_path=input_path,
            output_dir=output_dir,
            config=config,
            material_manifest_paths=material_artifact_path_map(
                payload.get("material_manifest_paths")
            ),
            material_context=runtime_material,
            output_paths={},
            compare_paths={},
            report_paths=report_paths,
            intermediate_paths={},
        ),
        None,
    )
    payload["material_package_paths"] = material_package_path_map(
        material_package_result
    )
    payload["material_package_receipt"] = material_package_receipt_payload(
        material_package_result
    )
    apply_artifact_failures(payload, artifact_failures)


def _material_preflight_report_payload(
    payload: Mapping[str, object],
    *,
    input_path: Path,
    diagnostics: list[object],
) -> dict[str, object]:
    report_payload: dict[str, object] = {
        "input": str(input_path),
        "output": "",
        "status": str(payload.get("status") or "failed"),
        "elapsed_seconds": 0,
        "modules_enabled": 0,
        "modules_total": 0,
        "changes": [],
        "diagnostics": {
            "count": len(diagnostics),
            "items": plain_data(diagnostics),
        },
        "material_diagnostics": plain_data(diagnostics),
        "counts": None,
        "failed_items": [],
        "error_text": str(payload.get("error_text") or ""),
    }
    for field_name in (
        "exam_markdown_import",
        "exam_question_schema",
        "exam_delivery_runtime",
        "style_source",
    ):
        if field_name in payload:
            report_payload[field_name] = plain_data(payload.get(field_name))
    return report_payload


def _publish_material_preflight_reports(
    report_payload: dict[str, object],
    *,
    input_path: Path,
    output_dir: Path,
    include_json: bool,
    include_markdown: bool,
) -> list[str]:
    if not include_json and not include_markdown:
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix=".material-preflight-report-",
        dir=str(output_dir),
    ) as temp_dir:
        staging_dir = Path(temp_dir)
        artifacts: list[StagedArtifact] = []
        if include_json:
            final_json = output_dir / f"{input_path.stem}_changes.json"
            staged_json = staging_dir / final_json.name
            atomic_write_text(
                staged_json,
                json.dumps(
                    report_payload,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )
            artifacts.append(
                StagedArtifact(
                    "material_preflight_report_json",
                    staged_json,
                    final_json,
                )
            )
        if include_markdown:
            final_markdown = output_dir / f"{input_path.stem}_changes.md"
            staged_markdown = staging_dir / final_markdown.name
            atomic_write_text(
                staged_markdown,
                _render_material_preflight_markdown(report_payload),
                encoding="utf-8",
            )
            artifacts.append(
                StagedArtifact(
                    "material_preflight_report_markdown",
                    staged_markdown,
                    final_markdown,
                )
            )
        published = publish_staged_artifacts(
            tuple(artifacts),
            execution_id=f"material-preflight-report-{uuid4().hex}",
            work_root=output_dir,
        )
    return [published[artifact.artifact_id] for artifact in artifacts]


def _render_material_preflight_markdown(
    report_payload: Mapping[str, object],
) -> str:
    input_path = Path(str(report_payload.get("input") or "input"))
    lines = [
        f"# 排版报告 - {input_path.name}",
        "",
        f"- 状态: **{report_payload.get('status', 'failed')}**",
        "- 耗时: 0.00s",
        "- 模块: 0/0 启用",
        "",
        f"- Error: {report_payload.get('error_text', '')}",
        "",
    ]
    diagnostics = [
        item
        for item in list(report_payload.get("material_diagnostics") or [])
        if isinstance(item, Mapping)
    ]
    if diagnostics:
        lines.extend([f"## 诊断提示 ({len(diagnostics)} 项)", ""])
        for item in diagnostics:
            reason = str(item.get("reason") or "").strip()
            target = str(item.get("target") or "").strip()
            rule_name = str(item.get("rule_name") or "material_schema").strip()
            lines.append(f"- [{rule_name}] {target}: {reason}")
        lines.append("")
    exam_import = report_payload.get("exam_markdown_import")
    if isinstance(exam_import, dict) and exam_import:
        lines.extend(format_exam_markdown_import_markdown(exam_import))
    return "\n".join(lines)


__all__ = ["attach_material_preflight_reports"]
