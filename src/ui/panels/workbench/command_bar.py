from __future__ import annotations

from src.qt_api import QHBoxLayout, QLabel, QPushButton, Qt, QWidget
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.theme import bind_theme, get_theme

from .state import CurrentTaskState


class TaskCommandBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("wb_command_bar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        self._center_label = QLabel("任务中控")
        self._center_label.setObjectName("wb_command_center_label")
        self._doc_value = QLabel()
        self._strategy_value = QLabel()
        self._status_value = QLabel()
        self._status_value.setObjectName("wb_ready_badge")
        self._run_button = QPushButton("开始执行")
        self._run_button.setObjectName("task_command_bar_run")
        apply_button_variant(self._run_button, "primary")

        layout.addWidget(self._center_label)
        layout.addSpacing(8)
        layout.addWidget(self._doc_value)
        layout.addWidget(self._strategy_value)
        layout.addWidget(self._status_value)
        layout.addStretch(1)
        layout.addWidget(self._run_button)

        self.set_state(CurrentTaskState())
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_state(self, state: CurrentTaskState) -> None:
        self._doc_value.setText(state.document_label)
        self._strategy_value.setText(state.strategy_label)
        self._status_value.setText(state.status_text)
        self._run_button.setEnabled(state.ready)

    def set_center_title(self, text: str) -> None:
        self._center_label.setText(text)

    def _apply_theme(self) -> None:
        t = get_theme()
        button_qss = build_button_stylesheet(t, selector="QPushButton#task_command_bar_run")
        self.setStyleSheet(button_qss)
