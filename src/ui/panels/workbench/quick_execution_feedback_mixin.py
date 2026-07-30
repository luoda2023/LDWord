"""Execution feedback and delivery-receipt presentation for quick execution."""

from __future__ import annotations

import html as _html
from pathlib import Path

from src.qt_api import QDesktopServices, QIcon, QUrl
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.icons.catalog import get_icon
from src.shared.ui.path_action_semantics import PathAction, path_action_presentation
from src.shared.ui.sizing import apply_size_class, resolved_control_height
from src.shared.ui.theme import get_theme
from src.ui.panels.workbench.quick_execution_result_presenter import (
    build_execution_result_presentation,
)
from src.ui.panels.workbench.state import ExecutionProgressState, ExecutionResultState


class QuickExecutionFeedbackMixin:
    """Own progress, cancellation, logs, terminal feedback, and result actions."""

    def _append_exec_log(self, level: str, message: str) -> None:
        """Append one log line while keeping technical details collapsed by default."""

        safe = _html.escape(str(message))
        theme = get_theme()
        colors = {
            "info": theme.text_secondary,
            "warning": theme.warning,
            "error": theme.error,
            "critical": theme.error_pressed,
            "success": theme.success,
        }
        color = colors.get(level.lower(), theme.text_primary)
        self._exec_log.append(f'<span style="color: {color};">{safe}</span>')
        self._log_toggle_btn.setVisible(True)
        self._set_log_expanded(self._log_expanded)
        if level.lower() in ("error", "critical"):
            self._exec_error_count += 1

    def _request_execution_cancel(self) -> None:
        """Request cancellation once for the active execution."""

        if not self._execution_running or self._execution_cancel_requested:
            return
        self._execution_cancel_requested = True
        self._execution_cancel_btn.setEnabled(False)
        self._execution_cancel_btn.setText("正在取消...")
        self._execution_cancel_btn.setIcon(QIcon())
        self._set_status("正在取消，请稍候…", "info")
        self._append_exec_log("info", "已请求取消本次生成。")
        self.cancel_requested.emit()

    def _reset_execution_cancel_button(self) -> None:
        self._execution_cancel_requested = False
        self._execution_cancel_btn.setVisible(False)
        self._execution_cancel_btn.setEnabled(True)
        self._execution_cancel_btn.setText("取消生成")
        self._execution_cancel_btn.setIcon(
            get_icon("circle-x", 16, get_theme().text_primary)
        )

    def set_execution_progress(self, state: ExecutionProgressState) -> None:
        if not self._execution_running:
            self._execution_cancel_requested = False
        self._execution_running = True
        self._last_result_status = "running"
        self._exec_bar.setVisible(True)
        self._clear_result_receipt()
        self._set_material_repair_visible(False)
        self._object_preflight_cancel_btn.setVisible(False)
        self._execution_cancel_btn.setVisible(True)
        self._execution_cancel_btn.setEnabled(not self._execution_cancel_requested)
        self._execution_cancel_btn.setText(
            "正在取消..." if self._execution_cancel_requested else "取消生成"
        )
        self._execute_btn.setEnabled(False)
        self._execute_btn.setText("生成中...")
        self._execute_btn.setIcon(QIcon())

        stage_text = str(state.stage_text or "执行中")
        current_step = int(state.current_step or 0)
        total_steps = int(state.total_steps or 0)
        percentage = int(current_step / max(total_steps, 1) * 100)
        self._exec_bar.setValue(percentage)
        if self._execution_cancel_requested:
            self._set_status("正在取消，请稍候…", "info")
        else:
            self._set_status(f"{stage_text} {percentage}%", "info")
        if stage_text not in self._known_execution_modules:
            self._known_execution_modules.append(stage_text)
            self._append_exec_log("info", f"执行阶段：{stage_text}")
        self.summary_changed.emit()

    def set_execution_result(self, state: ExecutionResultState) -> None:
        self._execution_running = False
        presentation = build_execution_result_presentation(state)
        self._last_terminal_payload = presentation.terminal_payload
        self._last_result_status = presentation.status
        self._last_result_issue_count = presentation.issue_count
        self._exec_bar.setVisible(False)
        self._set_material_repair_visible(False)
        self._object_preflight_cancel_btn.setVisible(False)
        self._reset_execution_cancel_button()
        self._set_status(presentation.status_text, presentation.status_tone)
        if presentation.expand_log:
            self._set_log_expanded(True)
        for entry in presentation.log_entries:
            self._append_exec_log(entry.level, entry.message)
        if presentation.success:
            self._show_result_receipt(state)
            self._log_collapsed_label = "查看全部产物与日志"
        else:
            self._clear_result_receipt()
            self._log_collapsed_label = "查看执行日志"
        self._set_log_expanded(self._log_expanded)
        self._execute_btn.setText(presentation.execute_button_text)
        self._execute_btn.setIcon(get_icon("play", 16, get_theme().text_on_primary))
        self._execute_btn.setEnabled(True)
        apply_button_variant(self._execute_btn, "primary")
        self.summary_changed.emit()

    def finish_execution(self) -> None:
        self._execution_running = False
        self._reset_execution_cancel_button()
        if self._last_result_status == "running":
            self._last_result_status = "idle"
            self._emit_summary_changed()
            return
        self.summary_changed.emit()

    def reset_execution_feedback(self) -> None:
        self._clear_execution_feedback_state()
        self._emit_summary_changed()

    def _invalidate_execution_feedback(self) -> None:
        if self._execution_running or not hasattr(self, "_exec_log"):
            return
        self._clear_execution_feedback_state()

    def _clear_execution_feedback_state(self) -> None:
        self._known_execution_modules.clear()
        self._exec_bar.setValue(0)
        self._exec_bar.setVisible(False)
        self._exec_status_label.setText("等待开始...")
        self._exec_log.clear()
        self._exec_error_count = 0
        self._last_result_status = "idle"
        self._last_terminal_payload = {}
        self._execution_running = False
        self._reset_execution_cancel_button()
        self._last_result_issue_count = 0
        self._log_collapsed_label = "查看执行日志"
        self._execute_btn.setText("生成文档")
        self._execute_btn.setIcon(get_icon("play", 16, get_theme().text_on_primary))
        apply_button_variant(self._execute_btn, "primary")
        self._object_preflight_cancel_btn.setVisible(False)
        self._set_log_expanded(False)
        self._log_toggle_btn.setVisible(False)
        self._clear_result_receipt()

    @staticmethod
    def _primary_result_path(state: ExecutionResultState) -> str:
        direct = str(state.output_path or "").strip()
        if direct:
            return direct
        output_paths = {
            str(key or "").strip(): str(value or "").strip()
            for key, value in dict(state.output_paths or {}).items()
            if str(value or "").strip()
        }
        for key in ("official_docx", "final", "primary", "review"):
            if output_paths.get(key):
                return output_paths[key]
        if output_paths:
            return next(iter(output_paths.values()))
        report_paths = [
            str(path or "").strip()
            for path in list(state.report_paths or [])
            if str(path or "").strip()
        ]
        return report_paths[0] if report_paths else ""

    def _show_result_receipt(self, state: ExecutionResultState) -> None:
        path_text = self._primary_result_path(state)
        if not path_text:
            self._clear_result_receipt()
            return
        self._result_primary_path = path_text
        path = Path(path_text)
        display_name = path.name or path_text
        self._result_receipt_label.setText(f"已生成：{display_name}")
        self._result_receipt_label.setToolTip(path_text)
        self._open_result_btn.setText(
            "打开文档" if path.suffix.lower() == ".docx" else "打开文件"
        )
        is_file = self._path_exists(path)
        self._open_result_btn.setEnabled(is_file)
        self._open_result_folder_btn.setEnabled(
            self._nearest_existing_parent(path) is not None
        )
        self._result_receipt.setVisible(True)

    def _clear_result_receipt(self) -> None:
        self._result_primary_path = ""
        if not hasattr(self, "_result_receipt"):
            return
        self._result_receipt_label.clear()
        self._result_receipt_label.setToolTip("")
        self._open_result_btn.setText("打开文档")
        self._open_result_btn.setEnabled(False)
        self._open_result_folder_btn.setEnabled(False)
        self._result_receipt.setVisible(False)

    def _open_primary_result(self) -> None:
        path_text = str(self._result_primary_path or "").strip()
        if not path_text:
            return
        path = Path(path_text)
        if self._path_exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_primary_result_folder(self) -> None:
        path_text = str(self._result_primary_path or "").strip()
        if not path_text:
            return
        parent = self._nearest_existing_parent(Path(path_text))
        if parent is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(parent)))

    @staticmethod
    def _path_exists(path: Path) -> bool:
        try:
            return path.exists()
        except OSError:
            return False

    @classmethod
    def _nearest_existing_parent(cls, path: Path) -> Path | None:
        candidate = path if cls._path_exists(path) and path.is_dir() else path.parent
        while candidate != candidate.parent:
            if cls._path_exists(candidate):
                return candidate
            candidate = candidate.parent
        return candidate if cls._path_exists(candidate) else None

    def _set_status(self, text: str, tone: str = "hint") -> None:
        self._exec_status_label.setText(str(text or "").strip())
        theme = get_theme()
        colors = {
            "success": theme.success,
            "warning": theme.warning,
            "error": theme.error,
            "info": theme.primary,
            "hint": theme.text_hint,
        }
        color = colors.get(str(tone or "").strip(), theme.text_hint)
        self._exec_status_label.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {color}; "
            "background: transparent;"
        )

    def _set_material_repair_visible(
        self,
        visible: bool,
        detail_lines: list[str] | None = None,
    ) -> None:
        if not hasattr(self, "_material_repair_btn"):
            return
        self._material_repair_btn.setVisible(bool(visible))
        lines = [
            line
            for line in (str(item or "").strip() for item in list(detail_lines or []))
            if line
        ]
        if visible and lines:
            self._material_repair_btn.setToolTip(
                "资料缺口明细\n" + "\n".join(lines) + "\n点击打开资料配置"
            )
        else:
            self._material_repair_btn.setToolTip("打开资料配置")

    def _toggle_log_visibility(self) -> None:
        self._set_log_expanded(not self._log_expanded)

    def _set_log_expanded(self, expanded: bool) -> None:
        self._log_expanded = bool(expanded)
        if hasattr(self, "_exec_log"):
            self._exec_log.setVisible(self._log_expanded)
        if hasattr(self, "_log_toggle_btn"):
            self._log_toggle_btn.setText(
                "收起执行日志" if self._log_expanded else self._log_collapsed_label
            )
            self._log_toggle_btn.setIcon(
                get_icon(
                    "chevron-up" if self._log_expanded else "chevron-down",
                    16,
                    get_theme().text_primary,
                )
            )

    def _apply_execution_action_theme(self, theme) -> None:
        if hasattr(self, "_execute_btn"):
            apply_button_variant(self._execute_btn, "primary")
            apply_size_class(self._execute_btn, "lg")
            if not self._execution_running:
                self._execute_btn.setIcon(
                    get_icon("play", 16, theme.text_on_primary)
                )
        if hasattr(self, "_material_repair_btn"):
            apply_size_class(self._material_repair_btn, "lg")
            self._material_repair_btn.setIcon(
                get_icon("pen-tool", 16, theme.text_primary)
            )
            apply_button_variant(self._material_repair_btn, "secondary")
        if hasattr(self, "_execution_cancel_btn"):
            apply_size_class(self._execution_cancel_btn, "lg")
            if not self._execution_cancel_requested:
                self._execution_cancel_btn.setIcon(
                    get_icon("circle-x", 16, theme.text_primary)
                )
            apply_button_variant(self._execution_cancel_btn, "secondary")
        if hasattr(self, "_object_preflight_cancel_btn"):
            apply_size_class(self._object_preflight_cancel_btn, "lg")
            self._object_preflight_cancel_btn.setIcon(
                get_icon("circle-x", 16, theme.text_primary)
            )
            apply_button_variant(self._object_preflight_cancel_btn, "secondary")
        if hasattr(self, "_log_toggle_btn"):
            apply_size_class(self._log_toggle_btn, "sm")
            apply_button_variant(self._log_toggle_btn, "ghost-primary")
        if hasattr(self, "_open_result_btn"):
            open_file = path_action_presentation(PathAction.OPEN_FILE)
            apply_size_class(self._open_result_btn, "sm")
            apply_button_variant(self._open_result_btn, "secondary")
            self._open_result_btn.setIcon(
                get_icon(open_file.icon_name, 16, theme.text_primary)
            )
        if hasattr(self, "_open_result_folder_btn"):
            reveal = path_action_presentation(PathAction.REVEAL_IN_FOLDER)
            apply_size_class(self._open_result_folder_btn, "sm")
            apply_button_variant(self._open_result_folder_btn, "ghost-primary")
            self._open_result_folder_btn.setIcon(
                get_icon(reveal.icon_name, 16, theme.text_primary)
            )

    def _apply_execution_feedback_theme(self, theme) -> None:
        exec_height = resolved_control_height(theme, "lg")
        if hasattr(self, "_exec_status_area"):
            self._exec_status_area.setMinimumHeight(exec_height)
            self._exec_status_area.setMaximumHeight(exec_height)
            self._exec_status_area.setStyleSheet(
                f"""QWidget#wb_v2_exec_status_area {{
                    background: transparent;
                    border-radius: {theme.radius_sm}px;
                }}"""
            )
        if hasattr(self, "_exec_status_label"):
            self._exec_status_label.setStyleSheet(
                f"font-size: {theme.font_size_sm}px; color: {theme.text_hint}; "
                "background: transparent;"
            )
        if hasattr(self, "_exec_bar"):
            self._exec_bar.setStyleSheet(
                f"""QProgressBar#wb_v2_exec_bar {{
                    border: none; background: {theme.border_light};
                    border-radius: 2px;
                }}
                QProgressBar#wb_v2_exec_bar::chunk {{
                    background: {theme.primary}; border-radius: 2px;
                }}"""
            )
        if hasattr(self, "_exec_log"):
            self._exec_log.setStyleSheet(
                f"""QTextEdit#wb_v2_log_terminal {{
                    background: {theme.bg_hover};
                    color: {theme.text_secondary};
                    font-size: {theme.font_size_sm}px;
                    border-radius: {theme.radius_sm}px;
                    padding: 10px;
                    border: 1px solid {theme.border_light};
                }}"""
            )
        if hasattr(self, "_result_receipt"):
            self._result_receipt.setStyleSheet(
                f"QWidget#wb_v2_result_receipt {{ "
                f"background: {theme.bg_hover}; border: 1px solid {theme.border_light}; "
                f"border-radius: {theme.radius_sm}px; }}"
            )
            self._result_receipt_icon.setPixmap(
                get_icon("circle-check", 16, theme.success).pixmap(16, 16)
            )
            self._result_receipt_label.setStyleSheet(
                f"font-size: {theme.font_size_sm}px; "
                f"font-weight: {theme.font_weight_emphasis}; "
                f"color: {theme.text_primary}; background: transparent;"
            )


__all__ = ["QuickExecutionFeedbackMixin"]
