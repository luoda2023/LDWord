"""Pure preflight projections for one production execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.material_context import MaterialExecutionContext
from src.config.scene import SceneWorkspace

from .material_preflight import (
    image_anchor_diagnostics,
    material_requirement_diagnostics,
    missing_asset_rule_diagnostics,
    question_figure_file_diagnostics,
    undeclared_image_token_diagnostics,
)


@dataclass(slots=True)
class MaterialPreflightState:
    material_context: MaterialExecutionContext
    diagnostics: list[dict]
    blocking_diagnostics: list[dict]
    failure_diagnostics: list[dict]


def prepare_document_material_preflight(
    *,
    input_path: Path,
    scene: SceneWorkspace,
    material_context: MaterialExecutionContext,
) -> MaterialPreflightState:
    """Freeze field resolution and collect every document material gate."""

    field_resolution = material_context.resolve_material_fields()
    requirement_diagnostics = material_requirement_diagnostics(
        scene,
        material_context,
        field_resolution=field_resolution,
    )
    runtime_material = material_context.with_frozen_field_resolution(field_resolution)
    anchor_diagnostics = image_anchor_diagnostics(
        input_path,
        scene,
        runtime_material,
    )
    undeclared_image_diagnostics = undeclared_image_token_diagnostics(
        input_path,
        scene,
        runtime_material,
    )
    asset_file_diagnostics = question_figure_file_diagnostics(runtime_material)
    asset_rule_diagnostics = missing_asset_rule_diagnostics(
        runtime_material.missing_required_asset_roles()
    )
    diagnostics = [
        *requirement_diagnostics,
        *anchor_diagnostics,
        *undeclared_image_diagnostics,
        *asset_file_diagnostics,
    ]
    blocking_diagnostics = [
        *_error_level_diagnostics(requirement_diagnostics),
        *_error_level_diagnostics(anchor_diagnostics),
        *_error_level_diagnostics(undeclared_image_diagnostics),
        *asset_rule_diagnostics,
    ]
    return MaterialPreflightState(
        material_context=runtime_material,
        diagnostics=diagnostics,
        blocking_diagnostics=blocking_diagnostics,
        failure_diagnostics=[*diagnostics, *asset_rule_diagnostics],
    )


def document_scope_diagnostic(
    input_path: Path,
    reason: str,
) -> dict[str, object]:
    return {
        "rule_name": "document_scope_execution_gate",
        "target": str(input_path),
        "section": "execution_scope",
        "change_type": "document_scope_invalid",
        "before": "",
        "after": "",
        "paragraph_index": -1,
        "success": False,
        "level": "error",
        "diagnostic_code": "document_scope_invalid",
        "reason": reason,
        "repair_target_type": "scene_document_scope_field",
        "repair_target_key": "scene.document_scope.mode",
        "parameter_paths": ["scene.document_scope.mode"],
    }


def _error_level_diagnostics(diagnostics) -> list[dict]:
    return [
        diagnostic
        for diagnostic in diagnostics
        if isinstance(diagnostic, dict)
        and str(diagnostic.get("level") or "").strip().lower() == "error"
    ]


__all__ = [
    "MaterialPreflightState",
    "document_scope_diagnostic",
    "prepare_document_material_preflight",
]
