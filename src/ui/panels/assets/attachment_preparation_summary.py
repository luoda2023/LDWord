"""Compact, read-only entry summary for attachment preparation."""

from __future__ import annotations

from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    Qt,
    QWidget,
    Signal,
)
from src.services.material_attachments import AttachmentPreparationReport
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.theme import bind_theme, get_theme


class AttachmentPreparationSummary(QWidget):
    """Show one derived package state; all editing stays in the workbench."""

    prepare_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("attachment_preparation_summary")
        self._report: AttachmentPreparationReport | None = None
        self._status_text = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 12, 8)
        layout.setSpacing(12)
        self._summary_label = QLabel(self)
        self._summary_label.setObjectName("attachment_preparation_summary_text")
        layout.addWidget(self._summary_label, 1, Qt.AlignVCenter)

        self.prepare_button = QPushButton("去准备", self)
        self.prepare_button.setObjectName("attachment_preparation_open")
        self.prepare_button.setCursor(Qt.PointingHandCursor)
        self.prepare_button.clicked.connect(self.prepare_requested)
        apply_size_class(self.prepare_button, "sm")
        apply_button_variant(self.prepare_button, "secondary")
        layout.addWidget(self.prepare_button, 0, Qt.AlignVCenter)

        self.setVisible(False)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_report(self, report: AttachmentPreparationReport | None) -> None:
        self._report = report
        if report is None:
            self.setVisible(False)
            return
        if report.unreadable_paths:
            summary = f"{len(report.unreadable_paths)} 个文件无法读取"
            button_text = "查看问题"
        elif not report.profile_count:
            summary = "请先选择本次要生成的数据"
            button_text = "去准备"
        elif report.is_ready:
            summary = f"{report.source_file_count} 个文件 · 已准备完成"
            button_text = "查看资料"
        else:
            summary = (
                f"{report.source_file_count} 个文件 · "
                f"{len(report.pending_requirements)} 项待补充"
            )
            button_text = "去准备"
        self._status_text = summary
        self._summary_label.setText(summary)
        self.prepare_button.setText(button_text)
        self.setAccessibleDescription(
            f"{report.source_file_count} 个文件；{report.token_count} 项内容；"
            f"共 {report.occurrence_count} 处"
        )
        self.setVisible(bool(report.requirements or report.unreadable_paths))

    def report(self) -> AttachmentPreparationReport | None:
        return self._report

    def summary_text(self) -> str:
        return self._summary_label.text()

    def status_text(self) -> str:
        return self._status_text

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QWidget#attachment_preparation_summary {{
                background: transparent;
                border-top: 1px solid {theme.divider};
            }}
            QLabel#attachment_preparation_summary_text {{
                color: {theme.text_primary};
                font-size: {theme.font_size_md}px;
                font-weight: {theme.font_weight_emphasis};
                background: transparent;
                border: none;
            }}
            {build_button_stylesheet(theme, '#attachment_preparation_open')}
            """
        )


__all__ = ["AttachmentPreparationSummary"]
