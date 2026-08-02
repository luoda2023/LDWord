"""Material-suite delivery surface backed by MaterialPackage V1."""

from __future__ import annotations

from pathlib import Path

from src.application.materials import MaterialPreviewSnapshot
from src.domain.materials import MaterialIssue, MaterialRunSelection
from src.qt_api import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.ui.card import Card
from src.shared.ui.theme import bind_theme, get_theme

from .material_state import material_execution_gate, material_issue_lines
from .workbench_execution_footer import WorkbenchExecutionFooter


class MaterialSuiteGenerationDetail(QWidget):
    execute_requested = Signal()
    retry_requested = Signal()
    cancel_requested = Signal()
    material_workspace_requested = Signal()
    summary_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._selection: MaterialRunSelection | None = None
        self._preview: MaterialPreviewSnapshot | None = None
        self._issues: tuple[MaterialIssue, ...] = ()
        self._suite_root = ""
        self._output_root = ""
        self._execution_running = False
        self._last_result_status = "idle"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)

        self._source_card = Card("资料包", parent=self)
        source_header = QHBoxLayout()
        self._source_summary = QLabel("未选择资料包", self._source_card)
        self._source_summary.setWordWrap(True)
        source_header.addWidget(self._source_summary, 1)
        self._open_material_button = QPushButton("打开资料区", self._source_card)
        self._open_material_button.clicked.connect(
            self.material_workspace_requested.emit
        )
        source_header.addWidget(self._open_material_button)
        self._source_card.add_layout(source_header)
        self._issue_summary = QLabel("", self._source_card)
        self._issue_summary.setWordWrap(True)
        self._source_card.add_widget(self._issue_summary)
        layout.addWidget(self._source_card)

        self._suite_card = Card("交付套件", parent=self)
        suite_row = QHBoxLayout()
        self._suite_path = QLineEdit(self._suite_card)
        self._suite_path.setReadOnly(True)
        suite_row.addWidget(self._suite_path, 1)
        choose_suite = QPushButton("选择模板套件", self._suite_card)
        choose_suite.clicked.connect(self._choose_suite_root)
        suite_row.addWidget(choose_suite)
        self._suite_card.add_layout(suite_row)
        layout.addWidget(self._suite_card)

        self._output_card = Card("输出目录", parent=self)
        output_row = QHBoxLayout()
        self._output_path = QLineEdit(self._output_card)
        self._output_path.setReadOnly(True)
        output_row.addWidget(self._output_path, 1)
        choose_output = QPushButton("选择输出目录", self._output_card)
        choose_output.clicked.connect(self._choose_output_root)
        output_row.addWidget(choose_output)
        self._output_card.add_layout(output_row)
        layout.addWidget(self._output_card)

        self._execution_footer = WorkbenchExecutionFooter(self)
        self._execution_footer.execute_requested.connect(
            self.execute_requested.emit
        )
        self._execution_footer.retry_requested.connect(
            self.retry_requested.emit
        )
        self._execution_footer.cancel_requested.connect(
            self.cancel_requested.emit
        )
        self._execution_card = self._execution_footer
        layout.addWidget(self._execution_footer)
        layout.addStretch(1)

        bind_theme(self, self._apply_theme)
        self._refresh_projection()
        self._apply_theme()

    def _choose_suite_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择模板套件目录")
        if path:
            self._suite_root = path
            self._suite_path.setText(path)
            self.reset_execution_feedback()

    def _choose_output_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self._output_root = path
            self._output_path.setText(path)
            self.reset_execution_feedback()

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

    def material_selection(self) -> MaterialRunSelection | None:
        return self._selection

    def suite_root(self) -> str:
        return self._suite_root

    def output_dir(self) -> str:
        return self._output_root

    def execution_blocking_reasons(self) -> tuple[str, ...]:
        decision = material_execution_gate(self._selection, self._issues)
        reasons = list(decision.blocking_reasons)
        if self._selection is None:
            reasons.append("请选择资料包")
        elif not self._selection.selected_record_ids:
            reasons.append("请选择至少一条可执行资料记录")
        if not Path(self._suite_root).is_dir():
            reasons.append("请选择有效的模板套件目录")
        if not self._output_root:
            reasons.append("请选择输出目录")
        return tuple(dict.fromkeys(reasons))

    def can_start_execution(self) -> bool:
        return not self.execution_blocking_reasons()

    def navigation_snapshot(self) -> dict[str, str]:
        count = (
            len(self._selection.selected_record_ids)
            if self._selection is not None
            else 0
        )
        if self._execution_running:
            badge_text, badge_variant = "执行中", "info"
        elif self._last_result_status in {"success", "partial_success"}:
            badge_text, badge_variant = "已完成", "success"
        elif self.can_start_execution():
            badge_text, badge_variant = "可执行", "success"
        else:
            badge_text, badge_variant = "待补充", "neutral"
        return {
            "subtitle": (
                f"{count} 条资料记录 · 成套交付"
                if count
                else "尚未准备成套交付"
            ),
            "badge_text": badge_text,
            "badge_variant": badge_variant,
        }

    def set_execute_enabled(self, enabled: bool) -> None:
        self._execution_footer.set_execute_enabled(
            bool(enabled) and self.can_start_execution()
        )

    def reset_execution_feedback(self) -> None:
        self._execution_running = False
        self._last_result_status = "idle"
        self._execution_footer.reset_execution_feedback()
        self._refresh_projection()

    def set_execution_progress(self, state) -> None:
        self._execution_running = True
        self._last_result_status = "running"
        self._execution_footer.set_execution_progress(state)
        self.summary_changed.emit()

    def set_execution_result(self, state) -> None:
        self._execution_running = False
        self._last_result_status = str(
            getattr(state, "status", "") or "failed"
        )
        self._execution_footer.set_execution_result(state)
        self._refresh_projection()

    def finish_execution(self) -> None:
        self._execution_running = False
        self._execution_footer.finish_execution()
        self._refresh_projection()

    def _refresh_projection(self) -> None:
        count = (
            len(self._selection.selected_record_ids)
            if self._selection is not None
            else 0
        )
        package_name = (
            self._preview.package_name
            if self._preview is not None
            else (
                self._selection.package_ref.package_id
                if self._selection is not None
                else ""
            )
        )
        self._source_summary.setText(
            f"{package_name} · 已选 {count} 条记录"
            if package_name
            else "未选择资料包"
        )
        issue_lines = material_issue_lines(self._issues)
        self._issue_summary.setText("；".join(issue_lines))
        self._issue_summary.setVisible(bool(issue_lines))
        blockers = self.execution_blocking_reasons()
        self._execution_footer.set_blocking_message(
            "；".join(blockers)
        )
        self._execution_footer.set_execute_enabled(
            not self._execution_running and not blockers
        )
        self.summary_changed.emit()

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._source_summary.setStyleSheet(
            f"color: {theme.text_primary}; font-size: {theme.font_size_md}px;"
        )
        self._issue_summary.setStyleSheet(
            f"color: {theme.warning}; font-size: {theme.font_size_sm}px;"
        )


__all__ = ["MaterialSuiteGenerationDetail"]
