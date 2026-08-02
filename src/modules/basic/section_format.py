"""section_format — planned, auditable Word section management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.modules.base import BaseModule, Issue, ModuleMeta
from src.shared.engine.page_number_planner import (
    collect_page_number_diagnostics,
    format_page_number_diagnostic_text,
)
from src.shared.engine.section_layout_planner import (
    build_section_execution_plan,
    collect_section_inventory,
    ensure_section_break_before_paragraph,
    execute_section_execution_plan,
    validate_section_policy,
)

if TYPE_CHECKING:
    from docx import Document

    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


class SectionFormatModule(BaseModule):
    """Inventory, plan, execute, and verify section topology changes."""

    meta = ModuleMeta(
        name="section_format",
        description="分节管理",
        category="basic",
        requires_config=("section",),
        soft_after=("heading_recognition",),
        soft_consumes=("doc_tree", "heading_map"),
        provides=("section_inventory", "section_execution_plan", "section_execution_receipt"),
        modifies_structure=True,
    )

    def validate(
        self,
        doc: Document,
        config: ResolvedConfig,
        context: PipelineContext,
    ) -> list[Issue]:
        issues = [
            Issue(
                level="error",
                module_name=self.meta.name,
                message=message,
                location=location,
            )
            for location, message in validate_section_policy(config.section)
        ]

        inventory = collect_section_inventory(doc)
        context.section_inventory = inventory
        if issues or not hasattr(config, "header_footer"):
            return issues

        plan = build_section_execution_plan(doc, config, context, inventory=inventory)
        context.section_execution_plan = plan
        for operation in plan.blocked_operations:
            issues.append(
                Issue(
                    level="error",
                    module_name=self.meta.name,
                    message=(
                        f"分节操作被阻止：{operation.reason}；"
                        f"{operation.blocked_reason}"
                    ),
                    location=f"段落 #{operation.paragraph_index}",
                )
            )

        issues.extend(
            Issue(
                level=item.level,
                module_name=self.meta.name,
                message=format_page_number_diagnostic_text(item),
                location=item.location,
            )
            for item in collect_page_number_diagnostics(
                doc,
                context,
                config.header_footer,
            )
            if item.level == "error"
        )
        return issues

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        inventory = collect_section_inventory(doc)
        plan = getattr(context, "section_execution_plan", None)
        if plan is None or plan.source_digest != inventory.digest:
            plan = build_section_execution_plan(doc, config, context, inventory=inventory)
            context.section_inventory = inventory
            context.section_execution_plan = plan

        receipt = execute_section_execution_plan(
            doc,
            plan,
            header_footer_link_mode=str(
                getattr(config.section, "header_footer_link_mode", "preserve_source")
                or "preserve_source"
            ),
        )
        context.section_execution_receipt = receipt
        if receipt.blocked_operations:
            self._record_blocked_operations(receipt, tracker)
            return
        if receipt.validation_errors:
            raise RuntimeError("; ".join(receipt.validation_errors))

        for operation in receipt.applied_operations:
            tracker.record(
                rule_name=self.meta.name,
                target=(
                    f"body[{operation.body_index}]"
                    if operation.body_index >= 0
                    else f"paragraph[{operation.paragraph_index}]"
                ),
                section="global",
                change_type=operation.action,
                before=f"sections={receipt.source_section_count}",
                after=(
                    f"{operation.target_break_type or operation.reason}; "
                    f"sections={receipt.final_section_count}"
                ),
            )

        if not receipt.applied_operations:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{receipt.final_section_count} sections",
                section="global",
                change_type="inventory",
                before=plan.boundary_mode,
                after="source topology preserved; no section mutation required",
                paragraph_index=-1,
                success=True,
            )

    def _record_blocked_operations(self, receipt, tracker: ChangeTracker) -> None:
        for operation in receipt.blocked_operations:
            tracker.record(
                rule_name=self.meta.name,
                target=f"paragraph[{operation.paragraph_index}]",
                section="global",
                change_type="blocked",
                before=operation.reason,
                after=operation.blocked_reason,
                paragraph_index=operation.paragraph_index,
                success=False,
                failure_reason=operation.blocked_reason,
            )


def _ensure_section_break_before_paragraph(
    doc: Document,
    para_index: int,
    break_type: str,
) -> bool:
    """Compatibility wrapper retained for header/footer semantic tests."""

    return ensure_section_break_before_paragraph(
        doc,
        para_index,
        break_type,
        header_footer_link_mode="semantic_rebuild",
    )


__all__ = ["SectionFormatModule", "_ensure_section_break_before_paragraph"]
