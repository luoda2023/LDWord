"""CLI resource resolution and production-execution entry point."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from src.config.library import (
    default_scene_entry,
    get_template_entry,
    load_scene_from_library,
    load_template_from_library,
    scene_source_type_for_path,
    template_source_type_for_path,
    validate_scene_resource_ids,
)
from src.config.loader import load_scene, load_template
from src.config.material_context import MaterialExecutionContext
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig
from src.config.work_mode import (
    default_work_mode,
    get_work_mode,
)
from src.services.console_output import console_print
from src.services.execution_session import (
    official_document_type_applicability_issue,
)
from src.services.production_execution import (
    ProductionExecutionRequest,
    execute_production_request,
)


CLI_EXIT_SUCCESS = 0
CLI_EXIT_FAILED = 1
CLI_EXIT_PARTIAL = 2
CLI_EXIT_CANCELLED = 130


@dataclass(frozen=True, slots=True)
class CliExecutionResources:
    mode_id: str
    scene: SceneWorkspace
    template: TemplateConfig
    plan_id: str
    plan_path: str
    plan_source_type: str
    template_id: str
    template_path: str
    template_source_type: str


def run(
    input_path: Path,
    *,
    template_path: str | None = None,
    scene_path: str | None = None,
    output_dir: Path | None = None,
    document_type_id: str | None = None,
) -> int:
    """Execute one CLI request through the same frozen production path as GUI."""

    input_path = Path(input_path).expanduser()
    input_error = _input_path_error(input_path)
    if input_error:
        console_print(f"[ERROR] {input_error}")
        return CLI_EXIT_FAILED

    output_root = (
        Path(output_dir).expanduser()
        if output_dir is not None
        else input_path.parent / "output"
    )
    try:
        resources = _resolve_cli_resources(
            template_path=template_path,
            scene_path=scene_path,
        )
    except Exception as exc:
        console_print(f"[ERROR] 配置解析失败: {str(exc) or type(exc).__name__}")
        return CLI_EXIT_FAILED

    explicit_document_type_id = str(document_type_id or "").strip()
    applicability_issue = official_document_type_applicability_issue(
        resources.mode_id,
        explicit_document_type_id,
    )
    if applicability_issue:
        console_print(f"[ERROR] {applicability_issue}")
        return CLI_EXIT_FAILED
    if resources.mode_id == "official" and not explicit_document_type_id:
        console_print("[ERROR] official_document_type_missing")
        return CLI_EXIT_FAILED

    console_print(
        "[INFO] 执行绑定: "
        f"mode={resources.mode_id}, "
        f"plan={resources.plan_id}, "
        f"template={resources.template_id}"
    )
    console_print(f"[INFO] 输入: {input_path}")
    console_print(f"[INFO] 输出根目录: {output_root}")

    request = ProductionExecutionRequest(
        input_path=input_path,
        output_root=output_root,
        mode_id=resources.mode_id,
        scene=resources.scene,
        template=resources.template,
        plan_id=resources.plan_id,
        plan_path=resources.plan_path,
        plan_source_type=resources.plan_source_type,
        template_id=resources.template_id,
        template_path=resources.template_path,
        template_source_type=resources.template_source_type,
        document_type_id=explicit_document_type_id,
        material_context=MaterialExecutionContext(),
    )
    payload = execute_production_request(
        request,
        progress_callback=_print_progress,
    )
    return _emit_execution_summary(payload)


def _resolve_cli_resources(
    *,
    template_path: str | None,
    scene_path: str | None,
) -> CliExecutionResources:
    if scene_path:
        resolved_scene_path = Path(scene_path).expanduser().resolve()
        scene = load_scene(resolved_scene_path)
        plan_id = str(scene.scene_id or "").strip()
        if not plan_id:
            raise ValueError("plan_identity_missing: field=scene_id")
        mode_id = str(scene.mode_id or "").strip()
        if not mode_id:
            raise ValueError(
                f"plan_mode_missing: plan_id={plan_id}; field=mode_id"
            )
        mode = get_work_mode(mode_id)
        if mode is None:
            raise ValueError(f"unknown_work_mode:{mode_id or '<empty>'}")
        mode_id = mode.mode_id
        scene = validate_scene_resource_ids(scene, mode_id=mode_id)
        plan_path = str(resolved_scene_path)
        plan_source_type = scene_source_type_for_path(resolved_scene_path)
    else:
        mode = default_work_mode()
        mode_id = mode.mode_id
        plan_id = mode.default_scene_id
        entry = default_scene_entry(mode_id=mode_id)
        if entry is None:
            raise FileNotFoundError(
                f"plan_ref_unresolved: mode={mode_id}; plan_id={plan_id}"
            )
        scene = load_scene_from_library(plan_id, mode_id=mode_id)
        plan_path = str(entry.path)
        plan_source_type = str(entry.source_type or "builtin")

    if template_path:
        resolved_template_path = Path(template_path).expanduser().resolve()
        template = load_template(resolved_template_path)
        template_id = resolved_template_path.stem
        template_path_text = str(resolved_template_path)
        template_source_type = template_source_type_for_path(resolved_template_path)
        _validate_explicit_template_selection(
            scene,
            mode_id=mode_id,
            template_id=template_id,
        )
    else:
        template_id = _scene_template_id(scene)
        if not template_id:
            raise ValueError(
                f"plan_template_missing: plan_id={plan_id}; field=template_id"
            )
        entry = get_template_entry(template_id, mode_id=mode_id)
        if entry is None:
            raise FileNotFoundError(
                "template_ref_unresolved: "
                f"mode={mode_id}; template_id={template_id or '<empty>'}"
            )
        template = load_template_from_library(template_id, mode_id=mode_id)
        template_path_text = str(entry.path)
        template_source_type = str(entry.source_type or "builtin")

    return CliExecutionResources(
        mode_id=mode_id,
        scene=scene,
        template=template,
        plan_id=plan_id,
        plan_path=plan_path,
        plan_source_type=plan_source_type,
        template_id=template_id,
        template_path=template_path_text,
        template_source_type=template_source_type,
    )


def _scene_template_id(scene: SceneWorkspace) -> str:
    return str(getattr(scene, "template_id", "") or "").strip()


def _validate_explicit_template_selection(
    scene: SceneWorkspace,
    *,
    mode_id: str,
    template_id: str,
) -> None:
    compatible = {
        str(item or "").strip()
        for item in list(scene.compatible_template_ids or [])
        if str(item or "").strip()
    }
    if template_id not in compatible:
        raise ValueError(
            "runtime_template_not_compatible:"
            f" mode={mode_id}; template_id={template_id};"
            f" plan_id={str(scene.scene_id or '').strip() or '<empty>'}"
        )


def _input_path_error(input_path: Path) -> str:
    if not input_path.is_file():
        return f"输入文件不存在: {input_path}"
    if input_path.suffix.casefold() != ".docx":
        return f"不支持的文件格式: {input_path.suffix} (仅支持 .docx)"
    return ""


def _print_progress(current: int, total: int, message: str) -> None:
    label = str(message or "").strip()
    if not label:
        return
    console_print(f"[PROGRESS {int(current)}/{int(total)}] {label}")


def _emit_execution_summary(payload: Mapping[str, object]) -> int:
    status = _effective_terminal_status(payload)
    for kind, path in _artifact_paths(payload):
        console_print(f"[ARTIFACT {kind}] {path}")

    error_text = str(payload.get("error_text") or "").strip()
    failed_count = _safe_int(payload.get("failed_count"))
    artifact_failure_count = _safe_int(payload.get("artifact_failure_count"))
    if status == "success":
        console_print("[OK] 执行完成: status=success")
        return CLI_EXIT_SUCCESS
    if status == "partial_success":
        console_print(
            "[PARTIAL] 执行部分完成: "
            f"failed_items={failed_count}, "
            f"artifact_failures={artifact_failure_count}"
        )
        if error_text:
            console_print(f"[PARTIAL] {error_text}")
        return CLI_EXIT_PARTIAL
    if status == "cancelled":
        console_print(f"[CANCELLED] {error_text or '执行已取消'}")
        return CLI_EXIT_CANCELLED

    console_print(f"[ERROR] 执行失败: {error_text or 'unknown execution failure'}")
    return CLI_EXIT_FAILED


def _effective_terminal_status(payload: Mapping[str, object]) -> str:
    status = str(payload.get("status") or "failed").strip()
    if status == "success" and (
        _safe_int(payload.get("failed_count")) > 0
        or _safe_int(payload.get("artifact_failure_count")) > 0
    ):
        return "partial_success"
    if status in {"success", "partial_success", "failed", "cancelled"}:
        return status
    return "failed"


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _artifact_paths(payload: Mapping[str, object]):
    seen: set[str] = set()
    mapping_fields = (
        ("output", "output_paths"),
        ("compare", "compare_paths"),
        ("intermediate", "intermediate_paths"),
        ("material_manifest", "material_manifest_paths"),
        ("material_package", "material_package_paths"),
    )
    for label, field_name in mapping_fields:
        values = payload.get(field_name)
        if not isinstance(values, Mapping):
            continue
        for artifact_id, raw_path in values.items():
            path = str(raw_path or "").strip()
            if path and path not in seen:
                seen.add(path)
                yield f"{label}:{artifact_id}", path

    primary = str(payload.get("output_path") or "").strip()
    if primary and primary not in seen:
        seen.add(primary)
        yield "output:primary", primary
    for raw_path in list(payload.get("report_paths") or []):
        path = str(raw_path or "").strip()
        if path and path not in seen:
            seen.add(path)
            yield "report", path


__all__ = [
    "CLI_EXIT_CANCELLED",
    "CLI_EXIT_FAILED",
    "CLI_EXIT_PARTIAL",
    "CLI_EXIT_SUCCESS",
    "CliExecutionResources",
    "run",
]
