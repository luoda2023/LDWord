from __future__ import annotations

from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    Signal,
)

from src.shared.ui.style_receipt_slot_frame import StyleReceiptSlotFrame
from src.shared.ui.style_management_block import StyleManagementBlock
from src.ui.panels.style_object_projection_builders import (
    build_execution_style_projection,
)

from .state import (
    ExecutionProgressState,
    ExecutionResultState,
    ReadinessState,
)


class ExecutionCenter(QWidget):
    execute_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("wb_execution_center")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._center_title = QLabel("执行中心")
        self._center_title.setObjectName("wb_execution_title")
        self._ready_label = QLabel("待执行")
        self._ready_label.setObjectName("wb_ready_badge")
        self._reason_label = QLabel("")
        self._reason_label.setWordWrap(True)
        self._progress_title = QLabel("执行进度")
        self._progress_title.setObjectName("wb_execution_section_title")
        self._summary_title = QLabel("执行摘要")
        self._summary_title.setObjectName("wb_execution_section_title")

        progress_state = ExecutionProgressState()
        self._progress_stage_label = QLabel(progress_state.stage_text)
        self._progress_label = QLabel(f"{progress_state.current_step} / {progress_state.total_steps}")
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(progress_state.percent)
        self._progress_bar.setTextVisible(False)

        self._execute_button = QPushButton("开始执行")
        self._cancel_button = QPushButton("取消")
        self._status_label = QLabel(self._friendly_status(ExecutionResultState().status))
        self._status_label.setObjectName("wb_execution_status")

        self._execution_running = False
        self._readiness_ready = False

        self._summary_box = QTextEdit()
        self._summary_box.setReadOnly(True)
        self._summary_box.setObjectName("wb_execution_summary")
        self._style_receipt_slot = StyleReceiptSlotFrame(
            self,
            object_name_prefix="wb_execution_style_receipt",
        )
        self._style_receipt_row = self._style_receipt_slot.receipt_row
        self._style_receipt_block = StyleManagementBlock(
            self,
            title="样式回执",
            icon_name="type-outline",
            object_name_prefix="wb_execution_style_receipt",
            mode="execution_receipt_review",
            receipt_slot=self._style_receipt_slot,
        )
        self._style_receipt_block.setVisible(False)

        layout.addWidget(self._center_title)
        layout.addWidget(self._ready_label)
        layout.addWidget(self._reason_label)
        layout.addWidget(self._progress_title)

        progress_header = QHBoxLayout()
        progress_header.addWidget(self._progress_stage_label)
        progress_header.addStretch(1)
        progress_header.addWidget(self._progress_label)
        layout.addLayout(progress_header)
        layout.addWidget(self._progress_bar)

        button_row = QHBoxLayout()
        button_row.addWidget(self._execute_button)
        button_row.addWidget(self._cancel_button)
        layout.addLayout(button_row)

        layout.addWidget(self._status_label)
        layout.addWidget(self._summary_title)
        layout.addWidget(self._style_receipt_block)
        layout.addWidget(self._summary_box)

        self._execute_button.clicked.connect(self.execute_requested.emit)
        self._cancel_button.clicked.connect(self.cancel_requested.emit)

        self.set_readiness(ReadinessState())

    @staticmethod
    def _friendly_status(status: str) -> str:
        return {
            "idle": "待执行",
            "running": "执行中",
            "success": "已完成",
            "partial_success": "部分完成",
            "failed": "执行失败",
            "cancelled": "已取消",
        }.get(status, status)

    def set_readiness(self, state: ReadinessState) -> None:
        self._ready_label.setText(state.label)
        if state.reasons:
            self._reason_label.setText("、".join(state.reasons))
        else:
            self._reason_label.clear()
        self._readiness_ready = state.ready
        self._sync_action_buttons()

    def set_summary(self, text: str) -> None:
        self._summary_box.setPlainText(text)

    def set_progress_state(self, state: ExecutionProgressState) -> None:
        self._progress_stage_label.setText(state.stage_text)
        self._progress_label.setText(f"{state.current_step} / {state.total_steps}")
        percent = max(0, min(100, state.percent))
        self._progress_bar.setValue(percent)
        self._execution_running = True
        self._status_label.setText(self._friendly_status("running"))
        self._sync_action_buttons()

    def set_result_state(self, state: ExecutionResultState) -> None:
        self._execution_running = False
        self._status_label.setText(self._friendly_status(state.status))
        summary_text = state.summary
        style_projection = build_execution_style_projection(
            style_source_envelope=state.style_source_envelope,
            style_source_summary=state.style_source_summary,
        )
        self._style_receipt_block.apply_style_object_projection(style_projection)
        self._sync_style_receipt_block_visible()
        if state.object_preflight_summary:
            object_preflight_text = state.object_preflight_summary
            if state.object_preflight_details:
                object_preflight_text = (
                    f"{object_preflight_text}\n"
                    + "\n".join(f"- {line}" for line in state.object_preflight_details)
                )
            summary_text = f"{summary_text}\n\n{object_preflight_text}"
        if state.material_field_consistency_summary:
            summary_text = f"{summary_text}\n\n{state.material_field_consistency_summary}"
        if state.attachment_bundle_summary:
            summary_text = f"{summary_text}\n\n{state.attachment_bundle_summary}"
        if state.material_dependency_summary:
            summary_text = f"{summary_text}\n\n{state.material_dependency_summary}"
        if state.batch_isolation_summary:
            batch_text = state.batch_isolation_summary
            if state.batch_isolation_details:
                batch_text = (
                    f"{batch_text}\n"
                    + "\n".join(f"- {line}" for line in state.batch_isolation_details)
                )
            summary_text = f"{summary_text}\n\n{batch_text}"
        if state.diagnostics_summary:
            summary_text = f"{summary_text}\n\n{state.diagnostics_summary}"
        self.set_summary(summary_text)
        self._sync_action_buttons()

    def _sync_style_receipt_block_visible(self) -> None:
        self._style_receipt_block.setVisible(
            self._style_receipt_slot.has_receipt()
        )
        self._style_receipt_block.updateGeometry()

    def _sync_action_buttons(self) -> None:
        if self._execution_running:
            self._execute_button.setEnabled(False)
            self._cancel_button.setEnabled(True)
        else:
            self._execute_button.setEnabled(self._readiness_ready)
            self._cancel_button.setEnabled(False)
