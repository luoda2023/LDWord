from __future__ import annotations

from pathlib import Path

from src.qt_api import (
    QDesktopServices,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    Qt,
    QUrl,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.card import Card
from src.shared.ui.icons.catalog import get_icon
from src.shared.ui.sizing import apply_size_class, resolved_control_height
from src.shared.ui.theme import bind_theme, get_theme

from .document_execution_state import (
    DocumentExecutionReadiness,
    DocumentExecutionTopology,
    inspect_document_execution_readiness,
    present_document_execution,
)
from .quick_execution_result_presenter import (
    QuickExecutionResultPresentation,
    build_execution_result_presentation,
)
from .state import ExecutionProgressState, ExecutionResultState


class WorkbenchExecutionFooter(Card):
    """Stable, inline execution status and action surface.

    The footer deliberately does not expose raw execution logs. User-facing
    state, progress, result and recovery actions stay in one fixed row; full
    diagnostics remain part of the terminal payload and application logging.
    """

    execute_requested = Signal()
    retry_requested = Signal()
    cancel_requested = Signal()
    confirmation_cancel_requested = Signal()
    repair_requested = Signal(str, str)
    summary_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent=parent)
        self.setObjectName("wb_execution_footer")
        self._execution_running = False
        self._cancel_requested = False
        self._actions_enabled = True
        self._context_bound = False
        self._last_result_status = "idle"
        self._retry_record_ids: tuple[str, ...] = ()
        self._last_batch_run_id = ""
        self._last_batch_attempt_number = 1
        self._preflight_blocked = False
        self._confirmation_required = False
        self._external_status_text = ""
        self._external_status_tone = "warning"
        self._result_path = ""
        self._result_is_directory = False
        self._topology = DocumentExecutionTopology(
            kind="single",
            document_count=0,
            record_count=0,
            expected_output_count=0,
            summary="",
        )
        self._readiness = inspect_document_execution_readiness(self._topology)

        action_row = QWidget(self)
        action_row.setObjectName("wb_execution_footer_row")
        row = QHBoxLayout(action_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(get_theme().spacing_sm)

        self._status_host = QWidget(action_row)
        self._status_host.setObjectName("wb_execution_footer_status_host")
        status_host_layout = QHBoxLayout(self._status_host)
        status_host_layout.setContentsMargins(0, 0, 0, 0)
        status_host_layout.setSpacing(6)

        self._status_icon = QLabel(self._status_host)
        self._status_icon.setFixedSize(18, 18)
        self._status_icon.setAlignment(Qt.AlignCenter)
        status_host_layout.addWidget(self._status_icon)

        self._status_area = QWidget(self._status_host)
        self._status_area.setObjectName("wb_execution_footer_status_area")
        status_layout = QVBoxLayout(self._status_area)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(2)

        self._status_label = QLabel("", self._status_area)
        self._status_label.setMinimumWidth(0)
        self._status_label.setWordWrap(False)
        self._status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._status_label.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred,
        )
        status_layout.addWidget(self._status_label, 1)

        self._progress = QProgressBar(self._status_area)
        self._progress.setRange(0, 100)
        self._progress.setTextVisible(False)
        self._progress.setMinimumHeight(4)
        self._progress.setMaximumHeight(4)
        self._progress.setVisible(False)
        status_layout.addWidget(self._progress)
        status_host_layout.addWidget(self._status_area, 1)
        row.addWidget(self._status_host, 1)

        self._repair_target_type = ""
        self._repair_target_key = ""
        self._repair_button = QPushButton("补充资料", action_row)
        self._repair_button.clicked.connect(self._request_repair)
        self._repair_button.setVisible(False)
        row.addWidget(self._repair_button)

        self._retry_button = QPushButton("重试失败项", action_row)
        self._retry_button.clicked.connect(self.retry_requested.emit)
        self._retry_button.setVisible(False)
        row.addWidget(self._retry_button)

        self._open_button = QPushButton("打开文档", action_row)
        self._open_button.clicked.connect(self._open_result)
        self._open_button.setVisible(False)
        row.addWidget(self._open_button)

        self._confirmation_cancel_button = QPushButton("取消", action_row)
        self._confirmation_cancel_button.clicked.connect(
            self.confirmation_cancel_requested.emit
        )
        self._confirmation_cancel_button.setVisible(False)
        row.addWidget(self._confirmation_cancel_button)

        self._cancel_button = QPushButton("取消", action_row)
        self._cancel_button.clicked.connect(self._request_cancel)
        self._cancel_button.setVisible(False)
        row.addWidget(self._cancel_button)

        self._execute_button = QPushButton("生成文档", action_row)
        self._execute_button.setObjectName("wb_execution_footer_execute")
        self._execute_button.clicked.connect(self.execute_requested.emit)
        row.addWidget(self._execute_button)
        self.add_widget(action_row)

        bind_theme(self, self._apply_footer_theme)
        self._apply_footer_theme()
        self._refresh_idle_projection()

    def set_context(
        self,
        topology: DocumentExecutionTopology,
        readiness: DocumentExecutionReadiness,
    ) -> None:
        self._context_bound = True
        self._topology = topology
        self._readiness = readiness
        self._external_status_text = ""
        if not self._execution_running and self._last_result_status == "idle":
            self._refresh_idle_projection()

    def set_execute_enabled(self, enabled: bool) -> None:
        self._actions_enabled = bool(enabled)
        if (
            not self._execution_running
            and self._last_result_status == "idle"
            and not self._confirmation_required
            and not self._preflight_blocked
        ):
            self._refresh_idle_projection()
        else:
            self._refresh_actions()

    def set_blocking_message(self, message: str) -> None:
        """Project an external inline blocker without entering confirmation."""

        self._external_status_text = _compact_text(message)
        self._external_status_tone = "warning"
        self._confirmation_required = False
        self._preflight_blocked = False
        if self._external_status_text:
            self._set_status(self._external_status_text, "warning")
        elif not self._execution_running and self._last_result_status == "idle":
            self._refresh_idle_projection()
        self._refresh_actions()

    def reset_execution_feedback(self) -> None:
        self._execution_running = False
        self._cancel_requested = False
        self._last_result_status = "idle"
        self._retry_record_ids = ()
        self._last_batch_run_id = ""
        self._last_batch_attempt_number = 1
        self._preflight_blocked = False
        self._confirmation_required = False
        self._external_status_text = ""
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setVisible(False)
        self._retry_button.setVisible(False)
        self._repair_button.setVisible(False)
        self._cancel_button.setText("取消")
        self._cancel_button.setVisible(False)
        self._confirmation_cancel_button.setVisible(False)
        self._open_button.setVisible(False)
        self._result_path = ""
        self._result_is_directory = False
        self._refresh_idle_projection()
        self.summary_changed.emit()

    def set_execution_progress(self, state: ExecutionProgressState) -> None:
        self._preflight_blocked = False
        self._confirmation_required = False
        self._external_status_text = ""
        self._execution_running = True
        self._last_result_status = "running"
        self._open_button.setVisible(False)
        self._retry_button.setVisible(False)
        self._repair_button.setVisible(False)
        self._cancel_button.setText("取消")
        self._result_path = ""
        self._result_is_directory = False

        current = max(0, int(state.current_step or 0))
        total = max(0, int(state.total_steps or 0))
        running_text = self._running_status_text()
        if total <= 0:
            self._progress.setRange(0, 0)
            status_text = running_text
        else:
            percent = int(state.percent or (current / max(total, 1) * 100))
            percent = max(0, min(100, percent))
            self._progress.setRange(0, 100)
            self._progress.setValue(percent)
            status_text = f"{running_text} · {percent}%"
        self._progress.setVisible(True)
        self._set_status(status_text, "info")
        self._refresh_actions()
        self.summary_changed.emit()

    def set_execution_result(self, state: ExecutionResultState) -> None:
        presentation = build_execution_result_presentation(state)
        self._execution_running = False
        self._preflight_blocked = False
        self._confirmation_required = False
        self._external_status_text = ""
        self._cancel_requested = False
        self._last_result_status = presentation.status
        self._retry_record_ids = presentation.retry_record_ids
        self._last_batch_run_id = presentation.batch_run_id
        self._last_batch_attempt_number = presentation.batch_attempt_number
        self._progress.setRange(0, 100)
        self._progress.setVisible(False)
        self._cancel_button.setText("取消")
        self._cancel_button.setVisible(False)
        self._repair_button.setVisible(False)
        self._confirmation_cancel_button.setVisible(False)

        result_name = self._capture_result_target(
            state,
            success=presentation.success,
        )
        status_text, status_tone = _result_status_text(
            presentation,
            result_name=result_name,
        )
        self._set_status(status_text, status_tone)
        self._refresh_actions()
        self.summary_changed.emit()

    def finish_execution(self) -> None:
        if self._execution_running:
            self._execution_running = False
            self._cancel_requested = False
            self._last_result_status = "failed"
            self._progress.setRange(0, 100)
            self._progress.setVisible(False)
            self._set_status("执行结束，未生成结果", "error")
        self._refresh_actions()
        self.summary_changed.emit()

    def set_preflight_confirmation(
        self,
        state: ExecutionResultState,
        *,
        blocked: bool,
    ) -> None:
        self._execution_running = False
        self._preflight_blocked = bool(blocked)
        self._confirmation_required = not blocked
        self._external_status_text = ""
        self._last_result_status = "failed" if blocked else "idle"
        summary = _compact_text(state.object_preflight_summary)
        self._set_status(
            (
                f"预检未通过 · {summary or '请先处理文档中的阻断内容'}"
                if blocked
                else f"发现需要确认的内容 · {summary or '确认后继续生成'}"
            ),
            "error" if blocked else "warning",
        )
        self._progress.setVisible(False)
        self._open_button.setVisible(False)
        self._refresh_actions()
        self.summary_changed.emit()

    def set_confirmation_message(self, message: str) -> None:
        text = _compact_text(message)
        self._preflight_blocked = False
        self._confirmation_required = bool(text)
        self._external_status_text = ""
        self._last_result_status = "idle"
        if text:
            self._set_status(text, "warning")
        else:
            self._refresh_idle_projection()
        self._refresh_actions()
        self.summary_changed.emit()

    def set_repair_action(
        self,
        *,
        label: str = "",
        target_type: str = "",
        target_key: str = "",
        tooltip: str = "",
    ) -> None:
        self._repair_target_type = str(target_type or "").strip()
        self._repair_target_key = str(target_key or "").strip()
        visible = bool(str(label or "").strip() and self._repair_target_type)
        self._repair_button.setText(str(label or "补充资料").strip())
        self._repair_button.setToolTip(str(tooltip or "").strip())
        self._repair_button.setVisible(
            visible
            and not self._execution_running
            and self._last_result_status == "idle"
        )

    def retry_record_ids(self) -> tuple[str, ...]:
        return self._retry_record_ids

    def last_batch_run_id(self) -> str:
        return self._last_batch_run_id

    def next_batch_attempt_number(self) -> int:
        return max(1, self._last_batch_attempt_number + 1)

    def navigation_snapshot(self) -> dict[str, str]:
        status = self._last_result_status
        if self._execution_running:
            badge, variant = "执行中", "info"
        elif status == "success":
            badge, variant = "已完成", "success"
        elif status == "partial_success":
            badge, variant = "部分完成", "warning"
        elif status == "failed":
            badge, variant = "需处理", "warning"
        elif status == "cancelled":
            badge, variant = "已取消", "neutral"
        elif self._can_execute():
            badge, variant = "可执行", "success"
        else:
            badge, variant = "待补充", "neutral"
        return {
            "subtitle": self._topology.summary,
            "badge_text": badge,
            "badge_variant": variant,
        }

    def _refresh_idle_projection(self) -> None:
        presentation = present_document_execution(
            self._topology,
            self._readiness,
        )
        self._execute_button.setText(presentation.action_text)
        if self._external_status_text:
            self._set_status(
                self._external_status_text,
                self._external_status_tone,
            )
        elif self._context_bound and self._readiness.state == "empty":
            self._set_status("请先在上方选择文档", "hint")
        elif self._context_bound and not self._readiness.can_execute:
            self._set_status(
                presentation.issue_text or "请先完成上方必需项",
                "warning",
            )
        elif self._can_execute():
            self._set_status("已准备完成", "success")
        else:
            self._set_status("请先完成上方必需项", "hint")
        self._progress.setVisible(False)
        self._open_button.setVisible(False)
        self._refresh_actions()

    def _can_execute(self) -> bool:
        readiness_allows = (
            self._readiness.can_execute if self._context_bound else True
        )
        return (
            self._actions_enabled
            and readiness_allows
            and not self._preflight_blocked
            and not self._external_status_text
        )

    def _running_status_text(self) -> str:
        count = self._topology.expected_output_count
        if self._topology.kind == "files" and count > 1:
            return f"正在处理 {count} 份文档"
        if self._topology.kind == "records" and count > 1:
            return f"正在生成 {count} 份文档"
        return "正在生成文档"

    def _refresh_actions(self) -> None:
        retry_visible = bool(self._retry_record_ids) and (
            self._last_result_status in {"partial_success", "failed"}
        )
        self._retry_button.setVisible(retry_visible)
        if retry_visible:
            self._retry_button.setText(
                f"重试失败项 {len(self._retry_record_ids)} 份"
            )

        self._cancel_button.setVisible(self._execution_running)
        self._cancel_button.setEnabled(not self._cancel_requested)
        self._confirmation_cancel_button.setVisible(
            self._confirmation_required and not self._execution_running
        )

        show_execute = not self._execution_running and not retry_visible
        self._execute_button.setVisible(show_execute)
        self._execute_button.setEnabled(
            show_execute
            and self._can_execute()
            and not self._preflight_blocked
        )

        if self._confirmation_required:
            self._execute_button.setText("确认并继续")
        elif self._preflight_blocked:
            self._execute_button.setText("生成文档")
        elif self._last_result_status in {"success", "partial_success"}:
            self._execute_button.setText("再次生成")
        elif self._last_result_status in {"failed", "cancelled"}:
            self._execute_button.setText("重试")
        elif self._last_result_status == "idle":
            self._execute_button.setText(
                present_document_execution(
                    self._topology,
                    self._readiness,
                ).action_text
            )
        self._refresh_action_styles()

    def _refresh_action_styles(self) -> None:
        if self._last_result_status == "success" and self._open_button.isVisible():
            apply_button_variant(self._open_button, "primary")
            apply_button_variant(self._execute_button, "secondary")
        elif self._retry_button.isVisible():
            apply_button_variant(self._retry_button, "primary")
            apply_button_variant(self._open_button, "secondary")
        else:
            apply_button_variant(self._execute_button, "primary")
            apply_button_variant(self._open_button, "secondary")

    def _request_cancel(self) -> None:
        if not self._execution_running or self._cancel_requested:
            return
        self._cancel_requested = True
        self._cancel_button.setEnabled(False)
        self._cancel_button.setText("正在取消…")
        self._progress.setRange(0, 0)
        self._progress.setVisible(True)
        self._set_status("正在取消…", "info")
        self.cancel_requested.emit()

    def _request_repair(self) -> None:
        if self._repair_target_type:
            self.repair_requested.emit(
                self._repair_target_type,
                self._repair_target_key,
            )

    def _set_status(self, text: str, tone: str) -> None:
        compact = _compact_text(text)
        self._status_label.setText(compact)
        theme = get_theme()
        colors = {
            "success": theme.success,
            "warning": theme.warning,
            "error": theme.error,
            "info": theme.primary,
            "hint": theme.text_hint,
        }
        icons = {
            "success": "circle-check",
            "warning": "alert-triangle",
            "error": "circle-x",
            "info": "file-output" if self._execution_running else "info",
            "hint": "info",
        }
        color = colors.get(tone, theme.text_hint)
        self._status_icon.setPixmap(
            get_icon(icons.get(tone, "info"), 18, color).pixmap(18, 18)
        )
        self._status_label.setStyleSheet(
            f"font-size: {theme.font_size_lg}px; "
            f"font-weight: {theme.font_weight_emphasis}; "
            f"color: {color}; background: transparent;"
        )

    def _capture_result_target(
        self,
        state: ExecutionResultState,
        *,
        success: bool,
    ) -> str:
        path = str(state.output_path or "").strip()
        if not path:
            for key in ("official_docx", "final", "primary", "review"):
                path = str(dict(state.output_paths or {}).get(key) or "").strip()
                if path:
                    break
        self._result_path = path
        candidate = Path(path) if path else None
        multiple_outputs = len(dict(state.output_paths or {})) > 1
        self._result_is_directory = bool(
            candidate
            and (
                candidate.is_dir()
                or self._topology.kind in {"files", "records"}
                or multiple_outputs
            )
        )
        self._open_button.setText(
            "打开目录" if self._result_is_directory else "打开文档"
        )
        self._open_button.setVisible(bool(success and path))
        self._open_button.setEnabled(bool(candidate and candidate.exists()))
        if not candidate:
            return ""
        if self._result_is_directory:
            return candidate.name or str(candidate)
        return candidate.name or str(candidate)

    def _open_result(self) -> None:
        if not self._result_path:
            return
        path = Path(self._result_path)
        if not path.exists():
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _apply_footer_theme(self) -> None:
        theme = get_theme()
        for button, variant, size in (
            (self._execute_button, "primary", "lg"),
            (self._repair_button, "secondary", "lg"),
            (self._retry_button, "primary", "lg"),
            (self._cancel_button, "secondary", "lg"),
            (self._confirmation_cancel_button, "secondary", "lg"),
            (self._open_button, "secondary", "lg"),
        ):
            apply_button_variant(button, variant)
            apply_size_class(button, size)
        height = resolved_control_height(theme, "lg")
        self._status_host.setMinimumHeight(height)
        self._status_host.setMaximumHeight(height)
        self._progress.setStyleSheet(
            f"QProgressBar {{ border: none; background: {theme.border_light}; "
            f"border-radius: {theme.radius_xs}px; }}"
            f"QProgressBar::chunk {{ background: {theme.primary}; "
            f"border-radius: {theme.radius_xs}px; }}"
        )
        self._refresh_action_styles()


def _compact_text(value: object, *, limit: int = 88) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: max(1, limit - 1)].rstrip()}…"


def _result_status_text(
    presentation: QuickExecutionResultPresentation,
    *,
    result_name: str,
) -> tuple[str, str]:
    if presentation.status == "success":
        text = "生成完成"
        if result_name:
            text += f" · {result_name}"
        if presentation.issue_count:
            text += f" · {presentation.issue_count} 项提醒"
        return text, "success"
    if presentation.status == "partial_success":
        summary = _compact_text(presentation.summary)
        return (
            f"部分完成 · {summary}" if summary else "部分完成，请重试失败项",
            "warning",
        )
    if presentation.status == "cancelled":
        return "已取消，未生成文件", "hint"
    return f"生成失败 · {_user_error_text(presentation)}", "error"


def _user_error_text(presentation: QuickExecutionResultPresentation) -> str:
    raw = _compact_text(presentation.error_text or presentation.summary, limit=72)
    lowered = raw.casefold()
    if not raw or raw in {"执行失败", "生成失败"}:
        return "生成过程中出现错误，请重试"
    if (
        "output_path_exists" in lowered
        or "document_batch_output_exists" in lowered
        or "target_collision" in lowered
    ):
        return "输出目标已存在，旧文件已保留；请重试生成"
    if "material.bind.template_resources_unsupported" in lowered:
        roles = raw.partition(":")[2].strip().replace(",", "、")
        return (
            f"资料包图片缺少对应文档占位符：{roles}"
            if roles
            else "资料包图片缺少对应文档占位符"
        )
    if "material.bind.template_resource_required_missing" in lowered:
        role = raw.rpartition(":")[2].strip()
        return (
            f"文档图片占位符尚未绑定资料：{role}"
            if role
            else "文档图片占位符尚未绑定资料"
        )
    if "material.bind.template_fields_required_missing" in lowered:
        fields = raw.partition(":")[2].strip().replace(",", "、")
        return (
            f"文档字段占位符缺少资料：{fields}"
            if fields
            else "文档字段占位符缺少资料"
        )
    if (
        "material.bind.template_resource_role_unknown" in lowered
        or "material.bind.template_resource_domain_mismatch" in lowered
    ):
        return "资料包资源角色与文档占位符不兼容"
    if "permissionerror" in lowered or "拒绝访问" in raw or "权限" in raw:
        return "文件正在使用或输出目录没有写入权限"
    if "filenotfounderror" in lowered or "没有找到" in raw or "不存在" in raw:
        return "没有找到输入文件，请重新选择"
    if "invalid terminal payload" in lowered or "contract" in lowered:
        return "执行结果异常，请重试"
    if any("\u4e00" <= char <= "\u9fff" for char in raw):
        return raw
    return "生成过程中出现错误，请重试"


__all__ = ["WorkbenchExecutionFooter"]
