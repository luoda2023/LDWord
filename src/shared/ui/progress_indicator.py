"""
Progress indicator with shared button styling.
"""

from __future__ import annotations

from src.qt_api import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget, Signal, Qt

from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.theme import bind_theme, get_theme


DEFAULT_STEP_TEXT = "处理中..."
CANCEL_BUTTON_TEXT = "取消"
DONE_STEP_TEXT = "已完成"


class ProgressIndicator(QWidget):
    """Show current step, progress, and a cancel action."""

    cancel_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().spacing_xs)

        self._step_label = self._build_step_label()
        layout.addWidget(self._step_label)

        self._build_progress_row(layout)

        self._pct_label = self._build_percentage_label()
        layout.addWidget(self._pct_label)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    @staticmethod
    def _build_step_label() -> QLabel:
        return QLabel(DEFAULT_STEP_TEXT)

    def _build_progress_row(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setSpacing(get_theme().spacing_sm)

        self._bar = QProgressBar()
        row.addWidget(self._bar, 1)

        self._cancel = self._build_cancel_button()
        row.addWidget(self._cancel)
        layout.addLayout(row)
        self._bar.setRange(0, 100)
        self._bar.setValue(0)

    def _build_cancel_button(self) -> QPushButton:
        button = QPushButton(CANCEL_BUTTON_TEXT)
        button.setObjectName("progress_cancel")
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(self.cancel_clicked.emit)
        apply_button_variant(button, "ghost-danger")
        return button

    @staticmethod
    def _build_percentage_label() -> QLabel:
        label = QLabel("0%")
        label.setAlignment(Qt.AlignRight)
        return label

    def _apply_theme(self) -> None:
        t = get_theme()
        self.layout().setSpacing(t.spacing_xs)
        row_layout = self.layout().itemAt(1).layout()
        row_layout.setSpacing(t.spacing_sm)
        self._apply_progress_bar_theme(t)
        self._apply_cancel_button_theme(t)
        self._apply_progress_label_theme(t)
        self.setFixedHeight(t.progress_indicator_height)

    def _apply_progress_bar_theme(self, theme) -> None:
        self._bar.setFixedHeight(theme.progress_bar_height)
        self._bar.setStyleSheet(
            f"""
            QProgressBar {{
                border: none;
                background: {theme.progress_track};
                border-radius: {theme.radius_xs}px;
            }}
            QProgressBar::chunk {{
                background: {theme.progress_fill};
                border-radius: {theme.radius_xs}px;
            }}
            """
        )

    def _apply_cancel_button_theme(self, theme) -> None:
        self._cancel.setMinimumWidth(theme.progress_cancel_min_width)
        self._cancel.setFixedHeight(theme.control_height_sm)
        self.setStyleSheet(self._build_cancel_button_stylesheet(theme))

    @staticmethod
    def _build_cancel_button_stylesheet(theme) -> str:
        return f"""
            #progress_cancel {{
                margin: 0;
            }}
            QLabel {{
                color: {theme.text_primary};
            }}
            {build_button_stylesheet(
                theme,
                '#progress_cancel',
                min_height=theme.control_height_sm,
                padding_x=theme.spacing_sm,
                padding_y=0,
                font_size=theme.font_size_sm,
            )}
            """

    def _apply_progress_label_theme(self, theme) -> None:
        self._pct_label.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};")
        self._step_label.setStyleSheet(f"font-size: {theme.font_size_md}px; color: {theme.text_primary};")

    def set_progress(self, current: int, total: int, step_name: str = ""):
        pct = int(current / max(total, 1) * 100)
        self._bar.setMaximum(total)
        self._bar.setValue(current)
        self._pct_label.setText(f"{pct}%")
        if step_name:
            self._step_label.setText(step_name)

    def set_done(self):
        self._bar.setValue(self._bar.maximum())
        self._pct_label.setText("100%")
        self._step_label.setText(DONE_STEP_TEXT)
        self._cancel.hide()

    def reset_idle(self) -> None:
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._pct_label.setText("0%")
        self._step_label.setText(DEFAULT_STEP_TEXT)
        self._cancel.show()

    def set_incomplete(self, step_name: str = "") -> None:
        if step_name:
            self._step_label.setText(step_name)
        self._cancel.show()
