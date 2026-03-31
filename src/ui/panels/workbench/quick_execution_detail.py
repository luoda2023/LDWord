from __future__ import annotations

from pathlib import Path

from src.qt_api import QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget, Signal
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.card import Card
from src.shared.ui.collapsible_section import CollapsibleSection
from src.shared.ui.execution_progress_widget import ExecutionProgressWidget
from src.shared.ui.feature_toggle_row import FeatureToggleRow
from src.shared.ui.file_drop_zone import FileDropZone
from src.shared.ui.form_row import FormRow
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch
from src.ui.panels.workbench.state import ExecutionProgressState, ExecutionResultState


class QuickExecutionDetail(QWidget):
    """Workbench V2 quick-execution detail pane."""

    feature_toggled = Signal(str, bool)
    feature_config_requested = Signal(str)
    summary_changed = Signal()
    execute_requested = Signal()
    cancel_requested = Signal()
    document_selected = Signal(str)

    FEATURE_DEFINITIONS = (
        ("heading_numbering", "\u6807\u9898\u7f16\u53f7", "\u65b9\u6848 1.1.1 / 4 \u7ea7", "\u5df2\u542f\u7528", "success"),
        ("quick_fill", "\u5185\u5bb9\u586b\u5145", "Excel / 5 \u4e2a\u6620\u5c04\u5b57\u6bb5", "\u6570\u636e\u5c31\u7eea", "neutral"),
        ("module_control", "\u6a21\u5757\u63a7\u5236", "\u5f53\u524d\u542f\u7528 8 / 12 \u4e2a\u6a21\u5757", "\u53ef\u8c03\u6574", "neutral"),
        ("output_settings", "\u8f93\u51fa\u8bbe\u7f6e", "output / {template}_{date}", "\u5df2\u8bbe\u7f6e", "neutral"),
        ("execution_history", "\u6267\u884c\u5386\u53f2", "\u6700\u8fd1\u4e00\u6b21 14:30 \u6210\u529f\u5b8c\u6210", "\u53ef\u67e5\u770b", "neutral"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._feature_rows: dict[str, FeatureToggleRow] = {}
        self._template_name_override = ""
        self._scene_name_override = ""
        self._strict_mode_override: bool | None = None
        self._execution_running = False
        self._last_result_status = "idle"
        self._known_execution_modules: list[str] = []

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(16)

        self._intro = QLabel(
            "\u4ece\u8f93\u5165\u6587\u6863\u5230\u6267\u884c\u53cd\u9988\u5168\u90e8\u5728\u540c\u4e00\u9875\u9762\u5b8c\u6210\u3002"
        )
        self._intro.setWordWrap(True)
        self._intro.setObjectName("wb_v2_intro")
        self._layout.addWidget(self._intro)

        self._build_input_card()
        self._build_template_card()
        self._build_advanced_card()
        self._build_output_card()
        self._build_execution_card()

        self._layout.addStretch(1)
        self._wire_signals()
        self._emit_summary_changed()

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _build_input_card(self) -> None:
        self._input_card = Card("\u8f93\u5165\u6587\u6863", parent=self)
        self._file_zone = FileDropZone(
            dialog_title="\u9009\u62e9\u6587\u6863",
            file_filter="Word Documents (*.docx);;All Files (*)",
            parent=self._input_card,
        )
        self._file_zone.set_recent_files(
            [
                "D:\\Projects\\Lark\\\u5468\u62a5-\u670d\u52a1\u5668\u8fc1\u79fb.docx",
                "D:\\Projects\\Lark\\\u6280\u672f\u89c4\u8303-\u5185\u7f51\u7248.docx",
                "D:\\Projects\\Lark\\\u4ea7\u54c1\u8bf4\u660e-\u5ba2\u6237\u7ec8\u7a3f.docx",
            ]
        )
        self._input_hint = QLabel(
            "\u652f\u6301\u9009\u62e9\u672c\u5730 Word \u6587\u6863\uff0c\u5e76\u53ef\u4ece\u6700\u8fd1\u6587\u4ef6\u4e2d\u5feb\u901f\u56de\u586b\u3002",
            self._input_card,
        )
        self._input_hint.setWordWrap(True)
        self._input_card.add_widget(self._file_zone)
        self._input_card.add_widget(self._input_hint)
        self._layout.addWidget(self._input_card)

    def _build_template_card(self) -> None:
        self._template_card = Card("\u6a21\u677f\u4e0e\u7ea6\u675f", parent=self)
        self._template_combo = StyledComboBox(self._template_card)
        self._template_combo.addItems(
            [
                "\u9ed8\u8ba4\u6d41\u7a0b",
                "\u6280\u672f\u6587\u6863",
                "\u6c47\u62a5\u6f14\u793a",
                "\u5408\u540c\u6a21\u677f",
            ]
        )
        self._strict_toggle = ToggleSwitch(self._template_card, checked=True)
        self._strict_row = FormRow("\u4e25\u683c\u6a21\u5f0f", self._strict_toggle, parent=self._template_card)
        self._template_card.add_widget(self._template_combo)
        self._template_card.add_widget(self._strict_row)
        self._layout.addWidget(self._template_card)

    def _build_advanced_card(self) -> None:
        self._advanced_card = Card("\u9ad8\u7ea7\u529f\u80fd", parent=self)
        self._advanced_section = CollapsibleSection(
            "\u6309\u9700\u542f\u7528\u5b50\u80fd\u529b",
            expanded=False,
            parent=self._advanced_card,
        )

        for feature_id, label, _subtitle, _badge_text, _badge_variant in self.FEATURE_DEFINITIONS:
            row = FeatureToggleRow(label, parent=self._advanced_section)
            row.config_button().setText("\u67e5\u770b" if feature_id == "execution_history" else "\u914d\u7f6e")
            row.toggled.connect(lambda checked, fid=feature_id: self._on_feature_toggled(fid, checked))
            row.config_clicked.connect(lambda fid=feature_id: self.feature_config_requested.emit(fid))
            self._feature_rows[feature_id] = row
            self._advanced_section.add_widget(row)

        self._advanced_card.add_widget(self._advanced_section)
        self._layout.addWidget(self._advanced_card)

    def _build_output_card(self) -> None:
        self._output_card = Card("\u8f93\u51fa\u76ee\u5f55", parent=self)
        self._output_path = QLineEdit(self._output_card)
        self._output_path.setPlaceholderText(
            "\u9ed8\u8ba4\u8f93\u51fa\u5230\u8f93\u5165\u6587\u6863\u540c\u7ea7 output \u76ee\u5f55"
        )
        self._output_card.add_widget(self._output_path)
        self._layout.addWidget(self._output_card)

    def _build_execution_card(self) -> None:
        self._execution_card = Card("\u6267\u884c\u4e0e\u53cd\u9988", parent=self)
        self._execute_btn = QPushButton("\u5f00\u59cb\u6267\u884c", self._execution_card)
        apply_button_variant(self._execute_btn, "primary")
        self._execute_btn.clicked.connect(self.execute_requested.emit)

        self._status_label = QLabel(self._execution_card)
        self._status_label.setObjectName("wb_v2_status")
        self._progress_widget = ExecutionProgressWidget(self._execution_card)
        self._progress_widget.setVisible(False)
        self._progress_widget.cancel_clicked.connect(self.cancel_requested.emit)

        self._execution_card.add_widget(self._execute_btn)
        self._execution_card.add_widget(self._status_label)
        self._execution_card.add_widget(self._progress_widget)
        self._layout.addWidget(self._execution_card)

    def _wire_signals(self) -> None:
        self._file_zone.file_selected.connect(self._on_file_selected)
        self._template_combo.currentIndexChanged.connect(lambda *_: self._emit_summary_changed())
        self._strict_toggle.clicked.connect(lambda *_: self._emit_summary_changed())
        self._output_path.textChanged.connect(lambda *_: self._emit_summary_changed())

    def _on_file_selected(self, file_path: str) -> None:
        file_name = Path(file_path).name if file_path else "\u672a\u9009\u62e9\u6587\u6863"
        self._status_label.setText(f"\u5df2\u9009\u62e9\u6587\u6863\uff1a{file_name}")
        if file_path:
            self.document_selected.emit(file_path)
        self._emit_summary_changed()

    def _on_feature_toggled(self, feature_id: str, enabled: bool) -> None:
        self.feature_toggled.emit(feature_id, enabled)
        self._emit_summary_changed()

    def _set_status_text(self, text: str) -> None:
        self._status_label.setText(str(text or "").strip())

    def _ensure_combo_value(self, text: str) -> None:
        target = str(text or "").strip()
        if not target:
            return
        for index in range(self._template_combo.count()):
            if self._template_combo.itemText(index).strip() == target:
                self._template_combo.setCurrentIndex(index)
                return
        self._template_combo.addItem(target)
        self._template_combo.setCurrentIndex(self._template_combo.count() - 1)

    def _active_template_label(self) -> str:
        return self._template_name_override or self._template_combo.currentText().strip() or "\u9ed8\u8ba4\u6d41\u7a0b"

    def _active_strategy_label(self) -> str:
        return self._scene_name_override or self._active_template_label()

    def _active_strict_mode(self) -> bool:
        if self._strict_mode_override is not None:
            return bool(self._strict_mode_override)
        return self._strict_toggle.isChecked()

    def _emit_summary_changed(self) -> None:
        if self._execution_running:
            self.summary_changed.emit()
            return

        if not self.document_path():
            self._set_status_text("\u8bf7\u5148\u9009\u62e9\u8f93\u5165\u6587\u6863\u3002")
        else:
            strict_text = "\u4e25\u683c\u6a21\u5f0f" if self._active_strict_mode() else "\u6807\u51c6\u6a21\u5f0f"
            self._set_status_text(f"\u5f53\u524d\u5c31\u7eea\uff1a{self._active_strategy_label()} · {strict_text}")
        self.summary_changed.emit()

    def document_path(self) -> str:
        return self._file_zone.file_path()

    def set_document_path(self, file_path: str) -> None:
        cleaned = str(file_path or "").strip()
        previous = self._file_zone.file_path()
        if cleaned == previous:
            return
        was_blocked = self._file_zone.blockSignals(True)
        try:
            self._file_zone.set_file(cleaned)
        finally:
            self._file_zone.blockSignals(was_blocked)
        self._emit_summary_changed()

    def set_strategy_context(
        self,
        *,
        template_name: str | None = None,
        scene_name: str | None = None,
        strict_mode: bool | None = None,
    ) -> None:
        self._template_name_override = str(template_name or "").strip()
        self._scene_name_override = str(scene_name or "").strip()
        self._strict_mode_override = strict_mode
        if self._template_name_override:
            self._ensure_combo_value(self._template_name_override)
        if strict_mode is not None and self._strict_toggle.isChecked() != bool(strict_mode):
            self._strict_toggle.setChecked(bool(strict_mode))
        self._emit_summary_changed()

    def set_execute_enabled(self, enabled: bool) -> None:
        self._execute_btn.setEnabled(bool(enabled))

    def set_execution_progress(self, state: ExecutionProgressState) -> None:
        self._execution_running = True
        self._last_result_status = "running"
        self._progress_widget.setVisible(True)
        self._execute_btn.setEnabled(False)
        self._execute_btn.setText("\u6267\u884c\u4e2d...")

        stage_text = str(state.stage_text or "\u6267\u884c\u4e2d")
        current_step = int(state.current_step or 0)
        total_steps = int(state.total_steps or 0)
        self._progress_widget.set_progress(current_step, total_steps, stage_text)
        if stage_text not in self._known_execution_modules:
            if self._known_execution_modules:
                previous = self._known_execution_modules[-1]
                self._progress_widget.update_module_status(previous, "completed", 100)
            self._known_execution_modules.append(stage_text)
        self._progress_widget.update_module_status(stage_text, "running", int(state.percent or 0))
        self._progress_widget.append_log("info", f"\u6267\u884c\u9636\u6bb5\uff1a{stage_text}")
        self._set_status_text(f"\u6b63\u5728\u6267\u884c\uff1a{stage_text}")
        self.summary_changed.emit()

    def set_execution_result(self, state: ExecutionResultState) -> None:
        self._execution_running = False
        self._last_result_status = state.status
        success = state.status in {"success", "partial_success"}
        success_count = 1 if success else 0
        self._progress_widget.setVisible(True)
        self._progress_widget.set_completed(success, {"success_count": success_count})
        if self._known_execution_modules:
            final_module = self._known_execution_modules[-1]
            final_status = "completed" if success else ("failed" if state.status == "failed" else "cancelled")
            final_progress = 100 if success else 0
            self._progress_widget.update_module_status(final_module, final_status, final_progress)
        self._progress_widget.append_log("info", state.summary)
        if state.output_path:
            self._progress_widget.append_log("info", f"\u8f93\u51fa\u6587\u4ef6\uff1a{state.output_path}")
        if state.report_paths:
            self._progress_widget.append_log("info", f"\u62a5\u544a\u6587\u4ef6\uff1a{', '.join(state.report_paths)}")
        if state.error_text:
            self._progress_widget.append_log("error", state.error_text)
        self._set_status_text(state.summary if not state.error_text else f"{state.summary} · {state.error_text}")
        self._execute_btn.setText("\u518d\u6b21\u6267\u884c")
        self.summary_changed.emit()

    def finish_execution(self) -> None:
        self._execution_running = False
        if self._last_result_status == "running":
            self._last_result_status = "idle"
        self._emit_summary_changed()

    def reset_execution_feedback(self) -> None:
        self._known_execution_modules.clear()
        self._progress_widget.reset()
        self._progress_widget.setVisible(False)
        self._last_result_status = "idle"
        self._execution_running = False
        self._execute_btn.setText("\u5f00\u59cb\u6267\u884c")
        self._emit_summary_changed()

    def enabled_features(self) -> list[str]:
        return [
            feature_id
            for feature_id, row in self._feature_rows.items()
            if row.is_checked()
        ]

    def navigation_snapshot(self) -> dict[str, str]:
        file_name = Path(self.document_path()).name if self.document_path() else "\u672a\u9009\u62e9\u6587\u6863"
        strategy_name = self._active_strategy_label()
        enabled_count = len(self.enabled_features())
        if self._execution_running:
            badge_text = "\u6267\u884c\u4e2d"
            badge_variant = "info"
        elif self._last_result_status in {"success", "partial_success"}:
            badge_text = "\u6700\u8fd1\u5b8c\u6210"
            badge_variant = "success"
        elif self._last_result_status in {"failed", "cancelled"}:
            badge_text = "\u6700\u8fd1\u5f02\u5e38"
            badge_variant = "warning"
        else:
            badge_text = f"{enabled_count} \u9879\u589e\u5f3a" if enabled_count else ("\u5c31\u7eea" if self.document_path() else "\u5f85\u8865\u5145")
            badge_variant = "success" if self.document_path() else "warning"
        return {
            "subtitle": f"{file_name} · {strategy_name}",
            "badge_text": badge_text,
            "badge_variant": badge_variant,
        }

    def feature_navigation_snapshot(self, feature_id: str) -> dict[str, str]:
        for current_id, _label, subtitle, badge_text, badge_variant in self.FEATURE_DEFINITIONS:
            if current_id == feature_id:
                return {
                    "subtitle": subtitle,
                    "badge_text": badge_text,
                    "badge_variant": badge_variant,
                }
        return {"subtitle": "", "badge_text": "", "badge_variant": "neutral"}

    def _apply_theme(self) -> None:
        t = get_theme()
        self._intro.setStyleSheet(
            f"font-size: {t.font_size_md}px; color: {t.text_secondary};"
        )
        self._input_hint.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_hint};"
        )
        self._status_label.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.success};"
        )
