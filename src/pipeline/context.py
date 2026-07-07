"""
PipelineContext ? typed execution context shared by modules.

The context schema is explicit and slotted: modules may only read / write
declared fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.config.scene import FormatScopeConfig, SceneApplicationBoundaryConfig


@dataclass(slots=True)
class PipelineContext:
    """Per-execution pipeline context."""

    source_doc_path: str = ""
    source_doc_dir: str = ""
    application_boundary: SceneApplicationBoundaryConfig = field(
        default_factory=SceneApplicationBoundaryConfig
    )
    format_scope: FormatScopeConfig = field(default_factory=FormatScopeConfig)

    doc_tree: Any | None = None
    heading_map: dict[int, int] | None = None
    caption_counters: dict[str, int] | None = None
    validation_issues: list[Any] | None = None
    count_result: Any | None = None
    scene_journey_runtime: Any | None = None
    material_field_consistency: Any | None = None
    exam_question_schema: Any | None = None
    exam_delivery_runtime: Any | None = None
    journal_rule_source_governance: Any | None = None
    journal_citations: Any | None = None
    journal_submission_package: Any | None = None
    official_numbering_preservation: Any | None = None
    technical_chapter_inventory: Any | None = None
    application_section_word_limits: Any | None = None
    object_preflight: Any | None = None
    object_preflight_policy: dict[str, Any] | None = None
    object_preflight_module_skips: list[dict[str, Any]] | None = None
    output_target_preflight: Any | None = None
    coverage_boundaries: list[dict[str, Any]] | None = None
    parameter_runtime_consumption: list[dict[str, Any]] | None = None
    content_visibility_scan: Any | None = None
    content_visibility_preview: Any | None = None
    entity_values: dict[str, str] | None = None
    source_values: dict[str, str] | None = None
    inserted_images: list[dict[str, Any]] | None = None
