from __future__ import annotations

from src.qt_api import QLabel, QVBoxLayout, QWidget, Signal

from .execution_center import ExecutionCenter
from .recent_run_panel import RecentRunPanel


class QuickExecutePane(QWidget):
    execute_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("wb_quick_execute_pane")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self._title = QLabel("\u5feb\u901f\u6267\u884c")
        self._title.setObjectName("wb_quick_execute_title")
        self._description = QLabel("\u76f4\u63a5\u8fd0\u884c\u5f53\u524d\u6587\u6863\uff0c\u5e76\u5728\u540c\u4e00\u89c6\u56fe\u67e5\u770b\u8fdb\u5ea6\u4e0e\u6700\u8fd1\u7ed3\u679c\u3002")
        self._description.setWordWrap(True)
        self._description.setObjectName("wb_command_center_subtitle")
        self._execution_center = ExecutionCenter(self)
        self._recent_run_panel = RecentRunPanel(self)

        layout.addWidget(self._title)
        layout.addWidget(self._description)
        layout.addWidget(self._execution_center)
        layout.addWidget(self._recent_run_panel)

        self._execution_center.execute_requested.connect(self.execute_requested.emit)
        self._execution_center.cancel_requested.connect(self.cancel_requested.emit)

    @property
    def execution_center(self) -> ExecutionCenter:
        return self._execution_center

    @property
    def recent_run_panel(self) -> RecentRunPanel:
        return self._recent_run_panel
