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

from .state import ExecutionProgressState, ExecutionResultState, ReadinessState


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
        self.set_summary(state.summary)
        self._sync_action_buttons()

    def _sync_action_buttons(self) -> None:
        if self._execution_running:
            self._execute_button.setEnabled(False)
            self._cancel_button.setEnabled(True)
        else:
            self._execute_button.setEnabled(self._readiness_ready)
            self._cancel_button.setEnabled(False)
