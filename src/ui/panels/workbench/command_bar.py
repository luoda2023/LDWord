from __future__ import annotations

from src.qt_api import QHBoxLayout, QLabel, QPushButton, Qt, QVBoxLayout, QWidget
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.theme import bind_theme, get_theme

from .state import CurrentTaskState


class TaskCommandBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("wb_command_bar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        self._center_label = QLabel("\u4efb\u52a1\u4e2d\u63a7")
        self._center_label.setObjectName("wb_command_center_label")
        self._center_subtitle = QLabel("\u5feb\u901f\u6267\u884c \u00b7 \u914d\u7f6e\u7ba1\u7406")
        self._center_subtitle.setObjectName("wb_command_center_subtitle")
        self._doc_value = QLabel()
        self._strategy_value = QLabel()
        self._status_value = QLabel()
        self._status_value.setObjectName("wb_ready_badge")
        self._run_button = QPushButton("\u5f00\u59cb\u6267\u884c")
        self._run_button.setObjectName("task_command_bar_run")
        apply_button_variant(self._run_button, "primary")

        center_layout = QVBoxLayout()
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(2)
        center_layout.addWidget(self._center_label)
        center_layout.addWidget(self._center_subtitle)

        layout.addLayout(center_layout)
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

    def set_center_subtitle(self, text: str) -> None:
        self._center_subtitle.setText(text)

    def _apply_theme(self) -> None:
        t = get_theme()
        button_qss = build_button_stylesheet(t, selector="QPushButton#task_command_bar_run")
        self.setStyleSheet(button_qss)
