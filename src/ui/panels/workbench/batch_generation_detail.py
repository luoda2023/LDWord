"""Record-batch detail backed only by MaterialPackage V1 selections."""

from __future__ import annotations

from pathlib import Path

from src.application.materials import MaterialPreviewSnapshot
from src.config.scene import SceneWorkspace
from src.domain.materials import MaterialIssue, MaterialRunSelection
from src.qt_api import (
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.adapters.workbench_execution_gate import ExecutionGateDecision

from .batch_generation_source_area import BatchGenerationSourceArea
from .material_state import material_execution_gate
from .quick_execution_result_presenter import build_execution_result_presentation
from .state import ExecutionProgressState, ExecutionResultState


class BatchGenerationDetail(QWidget):
    execute_requested = Signal()
    retry_requested = Signal()
    cancel_requested = Signal()
    source_document_selected = Signal(str)
    summary_changed = Signal()

    def __init__(
        self,
        parent=None,
        *,
        defer_context_build: bool = False,
    ) -> None:
        super().__init__(parent)
        self._context_built = False
        self._context_initialized = False
        self._scene = SceneWorkspace(scene_id="default")
        self._work_mode_id = "custom"
        self._selection: MaterialRunSelection | None = None
        self._preview: MaterialPreviewSnapshot | None = None
        self._issues: tuple[MaterialIssue, ...] = ()
        self._source_document_path = ""
        self._custom_output_dir = ""
        self._runtime_template_overrides: dict[str, object] = {}
        self._actions_enabled = True
        self._execution_running = False
        self._last_result_status = "idle"
        self._last_retry_record_ids: tuple[str, ...] = ()

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(get_theme().template_detail_section_gap)
        self.setMinimumWidth(320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        if not defer_context_build:
            self.ensure_context_built()
        bind_theme(self, self._apply_theme)
        self._context_initialized = True

    def ensure_context_built(self) -> None:
        if self._context_built:
            return
        self._source_area = BatchGenerationSourceArea(self)
        self._source_area.source_document_selected.connect(
            self._on_source_document_selected
        )
        self._layout.addWidget(self._source_area)
        self._layout.addStretch(1)
        self._context_built = True
        self._refresh_projection()
        self._apply_theme()

    def set_material_selection(
        self,
        selection: MaterialRunSelection | None,
        *,
        preview: MaterialPreviewSnapshot | None = None,
        issues: tuple[MaterialIssue, ...] = (),
    ) -> None:
        self._selection = (
            selection if isinstance(selection, MaterialRunSelection) else None
        )
        self._preview = (
            preview if isinstance(preview, MaterialPreviewSnapshot) else None
        )
        self._issues = tuple(issues)
        self.reset_execution_feedback()

    def set_scene_context(self, scene: SceneWorkspace | None) -> None:
        self._scene = (
            scene
            if isinstance(scene, SceneWorkspace)
            else SceneWorkspace(scene_id="default")
        )
        self._refresh_projection()

    def set_work_mode(self, mode_id: str) -> None:
        self._work_mode_id = str(mode_id or "").strip() or "custom"
        self._refresh_projection()

    def set_source_document(self, path: str) -> None:
        cleaned = str(path or "").strip()
        if cleaned == self._source_document_path:
            return
        self._source_document_path = cleaned
        self._refresh_projection()

    def _on_source_document_selected(self, path: str) -> None:
        self._source_document_path = str(path or "").strip()
        self._refresh_projection()
        self.source_document_selected.emit(self._source_document_path)

    def set_runtime_template_overrides(
        self,
        overrides: dict[str, object] | None,
    ) -> None:
        self._runtime_template_overrides = dict(overrides or {})

    def runtime_template_overrides(self) -> dict[str, object]:
        return dict(self._runtime_template_overrides)

    def output_dir(self) -> str:
        return self._custom_output_dir

    def current_batch_execution_gate_decision(self) -> ExecutionGateDecision:
        return material_execution_gate(self._selection, self._issues)

    def can_start_execution(self) -> bool:
        return not self.execution_blocking_reasons()

    def execution_blocking_reasons(self) -> list[str]:
        decision = self.current_batch_execution_gate_decision()
        reasons = list(decision.blocking_reasons)
        if self._selection is None:
            reasons.append("尚未选择资料包")
        elif not self._selection.selected_record_ids:
            reasons.append("尚未选择资料记录")
        if not self._selected_source_document_exists():
            reasons.append("请选择本批次共用的 DOCX 源文档")
        return list(dict.fromkeys(reasons))

    def _selected_source_document_exists(self) -> bool:
        path = Path(self._source_document_path)
        return path.is_file() and path.suffix.casefold() == ".docx"

    def _selected_record_ids(self) -> tuple[str, ...]:
        return (
            self._selection.selected_record_ids
            if self._selection is not None
            else ()
        )

    def failed_batch_record_ids(self) -> list[str]:
        selected = set(self._selected_record_ids())
        return [
            record_id
            for record_id in self._last_retry_record_ids
            if record_id in selected
        ]

    def set_execute_enabled(self, enabled: bool) -> None:
        self._actions_enabled = bool(enabled)
        self._refresh_actions()

    def reset_execution_feedback(self) -> None:
        self._execution_running = False
        self._last_result_status = "idle"
        self._last_retry_record_ids = ()
        if self._context_built:
            self._refresh_projection()

    def set_execution_progress(self, state: ExecutionProgressState) -> None:
        self._execution_running = True
        self._last_result_status = "running"
        self.summary_changed.emit()

    def set_execution_result(self, state: ExecutionResultState) -> None:
        self._execution_running = False
        presentation = build_execution_result_presentation(state)
        self._last_result_status = presentation.status
        self._last_retry_record_ids = tuple(presentation.retry_record_ids)
        self._refresh_actions()
        self.summary_changed.emit()

    def finish_execution(self) -> None:
        self._execution_running = False
        self._refresh_projection()

    def has_local_execution_surface(self) -> bool:
        return False

    def navigation_snapshot(self) -> dict[str, str]:
        count = len(self._selected_record_ids())
        if self._execution_running:
            badge_text, badge_variant = "执行中", "info"
        elif self._last_result_status == "success":
            badge_text, badge_variant = "已完成", "success"
        elif self._last_result_status == "partial_success":
            badge_text, badge_variant = "部分完成", "warning"
        elif self.can_start_execution():
            badge_text, badge_variant = "可执行", "success"
        else:
            badge_text, badge_variant = "待补充", "neutral"
        return {
            "subtitle": (
                f"{count} 条资料记录"
                if count
                else "尚未准备批次资料"
            ),
            "badge_text": badge_text,
            "badge_variant": badge_variant,
        }

    def _refresh_projection(self) -> None:
        if not self._context_built:
            self.summary_changed.emit()
            return
        count = len(self._selected_record_ids())
        package_name = (
            self._preview.package_name
            if self._preview is not None
            else (
                self._selection.package_ref.package_id
                if self._selection is not None
                else ""
            )
        )
        self._source_area.set_batch_state(
            count=count,
            source_label=package_name or "未选择资料包",
            profile_summary=(
                self._preview.current_record_name
                if self._preview is not None
                else ""
            ),
            source_document_required=True,
            source_document_path=self._source_document_path,
        )
        self._refresh_actions()
        self.summary_changed.emit()

    def _refresh_actions(self) -> None:
        return

    def _apply_theme(self) -> None:
        return


__all__ = ["BatchGenerationDetail"]
