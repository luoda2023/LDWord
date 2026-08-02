"""Canonical material state helpers for Workbench presentation and execution."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.materials import (
    ExecutionMaterialSnapshot,
    MaterialPreviewSnapshot,
    bind_repository_material_run,
    get_package_material_contract,
    project_material_preview,
)
from src.config.material_package_library import (
    get_material_package_entry,
    load_material_package_entry,
    material_package_repository,
)
from src.domain.materials import (
    MaterialIssue,
    MaterialRunSelection,
)
from src.ui.adapters.workbench_execution_gate import (
    ExecutionGateAction,
    ExecutionGateDecision,
    decide_execution_gate,
)


@dataclass(frozen=True, slots=True)
class MaterialSelectionProjection:
    selection: MaterialRunSelection | None
    preview: MaterialPreviewSnapshot | None
    issues: tuple[MaterialIssue, ...] = ()

    @property
    def record_ids(self) -> tuple[str, ...]:
        if self.selection is None:
            return ()
        return self.selection.selected_record_ids

    @property
    def package_id(self) -> str:
        if self.selection is not None:
            return self.selection.package_ref.package_id
        if self.preview is not None:
            return self.preview.package_id
        return ""

    @property
    def package_name(self) -> str:
        if self.preview is not None and self.preview.package_name:
            return self.preview.package_name
        return self.package_id


def choose_material_package(
    package_id: str,
    *,
    work_mode_id: str,
) -> MaterialSelectionProjection:
    """Select all active records from one exact repository revision."""

    identity = str(package_id or "").strip()
    if not identity:
        return MaterialSelectionProjection(None, None)
    entry = get_material_package_entry(identity, mode_id=work_mode_id)
    if entry is None or not entry.is_available:
        return MaterialSelectionProjection(
            None,
            None,
            (
                MaterialIssue(
                    code="material.selection.package_unavailable",
                    path="package_id",
                    message="所选资料包不可用，请回到资料区检查。",
                ),
            ),
        )
    try:
        snapshot = load_material_package_entry(entry)
        package = snapshot.package
        selected_ids = tuple(
            record.record_id for record in package.active_records()
        )
        selection = MaterialRunSelection(
            package_ref=snapshot.ref,
            selected_record_ids=selected_ids,
        )
        contract = get_package_material_contract(package)
        preview = project_material_preview(
            package,
            revision=snapshot.ref.revision,
            source_type=snapshot.source_type,
            contract=contract,
            current_record_id=(selected_ids[0] if selected_ids else ""),
        )
    except Exception as exc:
        return MaterialSelectionProjection(
            None,
            None,
            (
                MaterialIssue(
                    code="material.selection.package_load_failed",
                    path="package_id",
                    message=f"{type(exc).__name__}: {exc}",
                ),
            ),
        )
    issues: tuple[MaterialIssue, ...] = ()
    if not selected_ids:
        issues = (
            MaterialIssue(
                code="material.selection.no_active_records",
                path="records",
                message="资料包中没有可执行记录，请先在资料区激活记录。",
                remediation="打开资料区，将本次要使用的记录状态设为“可执行”。",
            ),
        )
    return MaterialSelectionProjection(selection, preview, issues)


def material_execution_gate(
    selection: MaterialRunSelection | None,
    issues: tuple[MaterialIssue, ...] = (),
) -> ExecutionGateDecision:
    """Project canonical typed issues into the shared Workbench gate."""

    errors = [
        item.message or item.code
        for item in issues
        if item.severity == "error"
    ]
    warnings = [
        item.message or item.code
        for item in issues
        if item.severity == "warning"
    ]
    if selection is not None and not selection.selected_record_ids:
        errors.append("资料包中尚未选择可执行记录")
    return decide_execution_gate(
        blocking_reasons=errors,
        warning_reasons=warnings,
        primary_action=(
            ExecutionGateAction("打开资料区", "material_package")
            if errors or warnings
            else None
        ),
    )


def bind_workbench_material(
    selection: MaterialRunSelection,
    *,
    work_mode_id: str,
    recipe_id: str,
    scene_id: str = "",
    document_type: str = "",
) -> tuple[ExecutionMaterialSnapshot | None, tuple[MaterialIssue, ...]]:
    result = bind_repository_material_run(
        material_package_repository(),
        selection,
        work_mode_id=work_mode_id,
        recipe_id=recipe_id,
        scene_id=scene_id,
        document_type=document_type,
    )
    return result.snapshot, result.issues


def material_issue_lines(issues: tuple[MaterialIssue, ...]) -> tuple[str, ...]:
    return tuple(
        item.message or item.code
        for item in issues
        if item.message or item.code
    )


__all__ = [
    "MaterialSelectionProjection",
    "bind_workbench_material",
    "choose_material_package",
    "material_execution_gate",
    "material_issue_lines",
]
