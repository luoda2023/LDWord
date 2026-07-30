"""Prepare one immutable, authoritative Markdown exam execution input."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from src.services.execution_session import execution_value_revision
from src.services.exam_markdown_source import project_exam_markdown_source
from src.config.material_context import MaterialExecutionContext
from src.config.scene import SceneWorkspace
from src.config.scene_surface_registry import scene_uses_exam_paper_surface
from src.shared.engine.exam_question_schema import (
    EXAM_SCHEMA_ID,
    ExamMarkdownImportResult,
)

from .exam_question_assets import material_context_with_exam_question_assets


@dataclass(frozen=True, slots=True)
class PreparedExamMarkdownInput:
    """Frozen source identity plus the exact scene/material projection to execute."""

    source_path: str
    source_revision: str
    base_scene_revision: str
    base_material_revision: str
    projection_revision: str
    scene: SceneWorkspace
    material_context: MaterialExecutionContext
    import_result: ExamMarkdownImportResult

    def clone(self) -> "PreparedExamMarkdownInput":
        return PreparedExamMarkdownInput(
            source_path=self.source_path,
            source_revision=self.source_revision,
            base_scene_revision=self.base_scene_revision,
            base_material_revision=self.base_material_revision,
            projection_revision=self.projection_revision,
            scene=copy.deepcopy(self.scene),
            material_context=self.material_context.clone(),
            import_result=copy.deepcopy(self.import_result),
        )


def is_exam_markdown_input(
    scene: SceneWorkspace | None,
    source_path: str | Path,
) -> bool:
    return (
        Path(source_path).suffix.lower() in {".md", ".markdown"}
        and scene_uses_exam_paper_surface(scene)
    )


def prepare_exam_markdown_input(
    *,
    scene: SceneWorkspace,
    material_context: MaterialExecutionContext,
    source_path: str | Path,
    expected_source_revision: str = "",
) -> PreparedExamMarkdownInput:
    """Parse the selected frozen source once and bind its hash to the projection."""

    path = Path(source_path).resolve(strict=True)
    if not is_exam_markdown_input(scene, path):
        raise RuntimeError("exam_markdown_input_not_applicable")

    revision_before = _file_revision(path)
    expected_revision = str(expected_source_revision or "").strip()
    if expected_revision and revision_before != expected_revision:
        raise RuntimeError("execution_input_drift:exam_markdown:expected_revision")

    base_scene_revision = execution_value_revision(scene)
    base_material_revision = execution_value_revision(material_context)
    runtime_scene = _scene_with_exam_items_schema(scene)
    source_projection = project_exam_markdown_source(path, material_context)
    import_result = source_projection.import_result
    runtime_material = source_projection.material_context
    if not runtime_material.profile_name:
        runtime_material.profile_name = "Markdown 题源"
    runtime_material = material_context_with_exam_question_assets(
        runtime_scene,
        runtime_material,
    )

    revision_after = _file_revision(path)
    if revision_after != revision_before:
        raise RuntimeError("execution_input_drift:exam_markdown:during_prepare")

    projection_revision = _projection_revision(
        source_revision=revision_after,
        scene=runtime_scene,
        material_context=runtime_material,
        import_result=import_result,
    )

    return PreparedExamMarkdownInput(
        source_path=str(path),
        source_revision=revision_after,
        base_scene_revision=base_scene_revision,
        base_material_revision=base_material_revision,
        projection_revision=projection_revision,
        scene=runtime_scene,
        material_context=runtime_material,
        import_result=import_result,
    )


def validated_prepared_exam_markdown_input(
    prepared: PreparedExamMarkdownInput,
    *,
    source_path: str | Path,
    expected_source_revision: str = "",
    expected_scene_revision: str = "",
    expected_material_revision: str = "",
) -> PreparedExamMarkdownInput:
    """Re-prove source identity without reparsing the already prepared payload."""

    path = Path(source_path).resolve(strict=True)
    prepared_path = Path(prepared.source_path).resolve(strict=True)
    if path != prepared_path:
        raise RuntimeError("execution_input_drift:exam_markdown:source_path")
    actual_revision = _file_revision(path)
    expected_revision = str(expected_source_revision or "").strip()
    if expected_revision and actual_revision != expected_revision:
        raise RuntimeError("execution_input_drift:exam_markdown:expected_revision")
    if actual_revision != prepared.source_revision:
        raise RuntimeError("execution_input_drift:exam_markdown:prepared_revision")
    scene_revision = str(expected_scene_revision or "").strip()
    if scene_revision and prepared.base_scene_revision != scene_revision:
        raise RuntimeError("execution_input_drift:exam_markdown:scene_revision")
    material_revision = str(expected_material_revision or "").strip()
    if material_revision and prepared.base_material_revision != material_revision:
        raise RuntimeError("execution_input_drift:exam_markdown:material_revision")
    actual_projection_revision = _projection_revision(
        source_revision=prepared.source_revision,
        scene=prepared.scene,
        material_context=prepared.material_context,
        import_result=prepared.import_result,
    )
    if actual_projection_revision != prepared.projection_revision:
        raise RuntimeError("execution_input_drift:exam_markdown:projection_revision")
    if not is_exam_markdown_input(prepared.scene, path):
        raise RuntimeError("exam_markdown_input_not_applicable")
    return prepared.clone()


def _scene_with_exam_items_schema(scene: SceneWorkspace) -> SceneWorkspace:
    runtime_scene = copy.deepcopy(scene)
    profile = getattr(runtime_scene, "input_source_profile", None)
    if profile is None:
        return runtime_scene
    if not str(getattr(profile, "material_schema_id", "") or "").strip():
        profile.material_schema_id = EXAM_SCHEMA_ID
    schema_ids = [
        str(value or "").strip()
        for value in list(getattr(profile, "material_schema_ids", []) or [])
        if str(value or "").strip()
    ]
    if EXAM_SCHEMA_ID not in schema_ids:
        schema_ids.insert(0, EXAM_SCHEMA_ID)
    profile.material_schema_ids = schema_ids
    profile.require_material_package = False
    return runtime_scene


def _file_revision(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def _projection_revision(
    *,
    source_revision: str,
    scene: SceneWorkspace,
    material_context: MaterialExecutionContext,
    import_result: ExamMarkdownImportResult,
) -> str:
    return execution_value_revision(
        {
            "source_revision": source_revision,
            "scene_revision": execution_value_revision(scene),
            "material_revision": execution_value_revision(material_context),
            "import_result": import_result.to_dict(),
        }
    )


__all__ = [
    "PreparedExamMarkdownInput",
    "is_exam_markdown_input",
    "prepare_exam_markdown_input",
    "validated_prepared_exam_markdown_input",
]
