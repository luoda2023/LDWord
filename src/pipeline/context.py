"""
PipelineContext ? typed execution context shared by modules.

The context schema is explicit and slotted: modules may only read / write
declared fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.config.scene import FormatScopeConfig


@dataclass(slots=True)
class PipelineContext:
    """Per-execution pipeline context."""

    source_doc_path: str = ""
    source_doc_dir: str = ""
    format_scope: FormatScopeConfig = field(default_factory=FormatScopeConfig)

    doc_tree: Any | None = None
    heading_map: dict[int, int] | None = None
    caption_counters: dict[str, int] | None = None
    entity_values: dict[str, str] | None = None
    source_values: dict[str, str] | None = None
    inserted_images: list[dict[str, Any]] | None = None
