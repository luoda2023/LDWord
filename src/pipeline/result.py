"""PipelineResult ? return value of Pipeline.execute()."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


@dataclass
class PipelineResult:
    """Execution result.

    status values:
    - "success"
    - "partial_success"
    - "failed"
    - "cancelled"
    """

    success: bool
    status: str = "success"
    doc: Any | None = None
    original_doc: Any | None = None
    tracker: "ChangeTracker | None" = None
    context: "PipelineContext | None" = None
    material_assembly_receipt: Any | None = None
    material_assembly_error: Any | None = None
    output_paths: dict[str, str] = field(default_factory=dict)
    failed_items: list[dict] = field(default_factory=list)
    error: str | None = None
    cancelled: bool = False
    config: Any | None = None
    attachment_bundle_receipts: dict[str, Any] = field(default_factory=dict)
    attachment_bundle_errors: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.cancelled:
            self.status = "cancelled"
        elif not self.success and self.status == "success":
            self.status = "failed"
