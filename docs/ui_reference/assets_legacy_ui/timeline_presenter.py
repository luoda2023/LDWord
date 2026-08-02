"""Persistent multi-segment timeline editor for material preparation."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from src.config.material_field_inventory import discard_material_field
from src.config.material_preview import scan_docx_placeholder_inventory
from src.shared.engine.material_token_contract import (
    MaterialTokenNamespace,
    material_token,
    parse_material_token,
)
from src.qt_api import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    Signal,
    Qt,
    QVBoxLayout,
    QWidget,
)
from src.shared.engine.material_timeline import (
    TimelineResolution,
    default_timeline_segment,
    infer_timeline_date_format,
    normalize_timeline_plans,
    resolve_timeline_plans,
    timeline_segment_nodes,
    timeline_output_field_keys,
)
from src.shared.ui.base_dialog import BaseDialog
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.compact_row_actions import apply_compact_row_action
from src.shared.ui.dialogs import confirm
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.keyed_widget_list import KeyedWidgetListController
from src.shared.ui.layout_sync import refresh_layout_chain
from src.shared.ui.material_token_edit import MaterialTokenEdit
from src.shared.ui.material_text_views import ElidedReadOnlyValue
from src.shared.ui.sizing import resolved_control_height
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.styled_spin_box import StyledSpinBox
from src.shared.ui.summary_grid import SummaryGridItem
from src.shared.ui.template_form_layout import template_form_row
from src.shared.ui.theme import get_theme
from src.shared.ui.toast import Toast
from src.shared.ui.timeline_node_column_guide import (
    TimelineNodeColumnGuide,
    TimelineNodeColumnMetrics,
)
from src.shared.ui.token_row_style import apply_token_row_style
from src.shared.ui.icons.catalog import get_icon


_WEEKEND_OPTIONS = (
    ("不调整周末", "none"),
    ("周末向后顺延", "forward"),
    ("周末向前调整", "backward"),
    ("调整到最近工作日", "nearest"),
)
_DATE_FORMAT_OPTIONS = (
    ("自动（跟随开始日期）", "auto"),
    ("2025-5-31", "yyyy-M-d"),
    ("2025-05-31", "yyyy-MM-dd"),
    ("2025年5月31日", "yyyy年M月d日"),
    ("2025年05月31日", "yyyy年MM月dd日"),
    ("5月31日", "M月d日"),
    ("05月31日", "MM月dd日"),
    ("2025.5.31", "yyyy.M.d"),
    ("2025/5/31", "yyyy/M/d"),
    ("2025/05/31", "yyyy/MM/dd"),
    ("31/5/2025", "d/M/yyyy"),
    ("31/05/2025", "dd/MM/yyyy"),
    ("5/31/2025", "M/d/yyyy"),
    ("05/31/2025", "MM/dd/yyyy"),
)
_INPUT_SCOPE_OPTIONS = (
    ("固定字段", "fixed"),
    ("自由字段", "floating"),
)
_SEGMENT_PRESET = {"id": "timeline_segment", "version": 2}
_TIMELINE_EDITOR_PRESET_IDS = frozenset({"", "generic_equal", "timeline_segment"})


def _is_timeline_editor_plan(plan: dict[str, object]) -> bool:
    preset = dict(plan.get("preset", {}) or {})
    return str(preset.get("id", "") or "") in _TIMELINE_EDITOR_PRESET_IDS


@dataclass(frozen=True, slots=True)
class TimelineReferenceEvidence:
    """Local evidence that a segment number may already be in use."""

    scan_status: str
    token_keys: tuple[str, ...] = ()
    occurrence_count: int = 0


class TimelineTokenEdit(MaterialTokenEdit):
    """Read-only exact token that copies itself on a normal click."""

    activated = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(
            "",
            parent,
            editable=False,
            namespace=MaterialTokenNamespace.TIME,
        )
        self.setObjectName("timeline_token_edit")
        self.setCompleted(True)
        self.copied.connect(self.activated.emit)


class TimelinePresenterMixin:
    """Coordinate always-visible time segments and their generated tokens."""

    def _setup_timeline_cards(self) -> None:
        self._timeline_syncing = False
        self._timeline_resolution = TimelineResolution(values={})

        self._timeline_segment_rows: dict[str, QFrame] = {}
        self._timeline_segment_titles: dict[str, QLabel] = {}
        self._timeline_segment_ranges: dict[str, QLabel] = {}
        self._timeline_segment_status_labels: dict[str, QLabel] = {}
        self._timeline_start_edits: dict[str, QLineEdit] = {}
        self._timeline_end_edits: dict[str, QLineEdit] = {}
        self._timeline_node_count_spins: dict[str, StyledSpinBox] = {}
        self._timeline_weekend_combos: dict[str, StyledComboBox] = {}
        self._timeline_date_format_combos: dict[str, StyledComboBox] = {}
        self._timeline_input_scope_combos: dict[str, StyledComboBox] = {}
        self._timeline_segment_bodies: dict[str, QWidget] = {}
        self._timeline_segment_collapse_buttons: dict[str, QPushButton] = {}
        self._timeline_collapsed_segments: set[str] = set()
        self._timeline_segment_copy_buttons: dict[str, QPushButton] = {}
        self._timeline_segment_remove_buttons: dict[str, QPushButton] = {}
        self._timeline_segment_reset_buttons: dict[str, QPushButton] = {}
        self._timeline_node_controllers: dict[
            str, KeyedWidgetListController[dict[str, object], str]
        ] = {}
        self._timeline_node_containers: dict[str, QWidget] = {}
        self._timeline_node_layouts: dict[str, QVBoxLayout] = {}
        self._timeline_node_rows: dict[tuple[str, str], QFrame] = {}
        self._timeline_node_index_labels: dict[tuple[str, str], QLabel] = {}
        self._timeline_node_token_edits: dict[
            tuple[str, str], TimelineTokenEdit
        ] = {}
        self._timeline_node_ratio_edits: dict[tuple[str, str], QLineEdit] = {}
        self._timeline_node_result_edits: dict[
            tuple[str, str], ElidedReadOnlyValue
        ] = {}
        self._timeline_node_column_guides: dict[str, TimelineNodeColumnGuide] = {}

        self._setup_timeline_editor_card()
        self._timeline_segments_controller = KeyedWidgetListController[
            tuple[str, dict[str, object]], str
        ](
            layout=self._timeline_segments_layout,
            create_widget=self._create_timeline_segment_row,
            update_widget=self._update_timeline_segment_row,
            dispose_widget=self._dispose_timeline_segment_row,
            key=lambda item: item[0],
        )
        self._refresh_timeline_ui()

    def _setup_timeline_editor_card(self) -> None:
        summary = self._section_summary_cards.get("timeline")
        if summary is not None:
            summary.hide()

        card = Card(parent=self._section_contents["timeline"])
        self._timeline_card = card
        card.setObjectName("assets_timeline_editor_card")
        card.set_header("时间计划", icon_name="chart-no-axes-gantt")

        self._timeline_add_segment_btn = QPushButton("＋ 新增时间段", card)
        self._timeline_add_segment_btn.setObjectName("timeline_add_segment")
        apply_button_variant(self._timeline_add_segment_btn, "secondary")
        self._timeline_add_segment_btn.clicked.connect(self._add_timeline_segment)
        card.add_header_action(self._timeline_add_segment_btn)

        self._timeline_segments_container = QWidget(card)
        self._timeline_segments_container.setObjectName("timeline_segments_container")
        self._timeline_segments_layout = QVBoxLayout(self._timeline_segments_container)
        self._timeline_segments_layout.setContentsMargins(0, 0, 0, 0)
        self._timeline_segments_layout.setSpacing(14)
        card.add_widget(self._timeline_segments_container)
        self._section_layouts["timeline"].addWidget(card)

    # ------------------------------------------------------------------
    # Segment widgets
    # ------------------------------------------------------------------

    def _create_timeline_segment_row(
        self,
        item: tuple[str, dict[str, object]],
    ) -> QFrame:
        plan_id, plan = item
        row = QFrame(self._timeline_segments_container)
        row.setObjectName("timeline_segment_row")
        row.setProperty("planId", plan_id)
        row.setAttribute(Qt.WA_StyledBackground)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        outer = QVBoxLayout(row)
        outer.setContentsMargins(0, 12, 0, 16)
        outer.setSpacing(14)

        header = QWidget(row)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        title = QLabel(row)
        title.setObjectName("timeline_segment_title")
        token_range = QLabel(row)
        token_range.setObjectName("timeline_segment_range")
        status = QLabel(row)
        status.setObjectName("timeline_segment_status")
        collapse_button = QPushButton("", row)
        apply_compact_row_action(
            collapse_button,
            icon_name="chevron-down",
            tooltip="折叠本段",
            variant="ghost",
        )
        copy_button = QPushButton("", row)
        apply_compact_row_action(
            copy_button,
            icon_name="plus",
            tooltip="复制整段",
            variant="ghost-primary",
        )
        remove_button = QPushButton("", row)
        apply_compact_row_action(
            remove_button,
            icon_name="trash-2",
            tooltip="删除整段",
            variant="ghost-danger",
        )
        header_layout.addWidget(title, 0)
        header_layout.addWidget(token_range, 1)
        header_layout.addWidget(collapse_button, 0)
        header_layout.addWidget(status, 0)
        header_layout.addWidget(copy_button, 0)
        header_layout.addWidget(remove_button, 0)
        outer.addWidget(header)

        body = QWidget(row)
        body.setObjectName("timeline_segment_body")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(14)

        start_edit = QLineEdit(row)
        start_edit.setPlaceholderText("例如：2025-10-27 或 2025年10月27日")
        end_edit = QLineEdit(row)
        end_edit.setPlaceholderText("例如：2026-01-27 或 2026年1月27日")
        node_count = StyledSpinBox(row)
        node_count.setDecimals(0)
        node_count.setSingleStep(1)
        node_count.setRange(2, 50)
        node_count.setSuffix(" 个")
        node_count.setToolTip("节点数量包含开始节点和结束节点")
        weekend = StyledComboBox(row)
        weekend.set_full_width_mode()
        for label, value in _WEEKEND_OPTIONS:
            weekend.addItem(label, value)
        date_format = StyledComboBox(row)
        date_format.set_full_width_mode()
        for label, value in _DATE_FORMAT_OPTIONS:
            date_format.addItem(label, value)
        input_scope = StyledComboBox(row)
        input_scope.set_full_width_mode()
        for label, value in _INPUT_SCOPE_OPTIONS:
            input_scope.addItem(label, value)

        form = InspectorForm(parent=body)
        form_grid = form.add_grid(
            [
                [
                    template_form_row("日期格式", date_format, parent=form),
                    template_form_row("填写方式", input_scope, parent=form),
                ],
                [
                    template_form_row("开始日期", start_edit, parent=form),
                    template_form_row("结束日期", end_edit, parent=form),
                ],
                [
                    template_form_row("节点数量（含起止）", node_count, parent=form),
                    template_form_row("周末策略", weekend, parent=form),
                ],
            ]
        )
        form_grid.layout().setSpacing(8)
        control_height = resolved_control_height(get_theme(), "md")
        for control in (start_edit, end_edit, node_count, weekend, date_format, input_scope):
            set_outer_height = getattr(control, "set_outer_height", None)
            if callable(set_outer_height):
                set_outer_height(control_height)
            else:
                control.setMinimumHeight(control_height)
                control.setMaximumHeight(control_height)
        body_layout.addWidget(form)

        nodes_header = QWidget(body)
        nodes_header_layout = QHBoxLayout(nodes_header)
        nodes_header_layout.setContentsMargins(0, 0, 0, 0)
        nodes_header_layout.setSpacing(8)
        nodes_title = QLabel("时间节点", nodes_header)
        nodes_title.setObjectName("timeline_nodes_title")
        reset_button = QPushButton("恢复平均分配", nodes_header)
        apply_button_variant(reset_button, "secondary")
        nodes_header_layout.addWidget(nodes_title, 0)
        nodes_header_layout.addStretch(1)
        nodes_header_layout.addWidget(reset_button, 0)
        body_layout.addWidget(nodes_header)

        nodes_list_body = QWidget(body)
        nodes_list_layout = QVBoxLayout(nodes_list_body)
        nodes_list_layout.setContentsMargins(0, 0, 0, 0)
        nodes_list_layout.setSpacing(0)
        node_column_guide = TimelineNodeColumnGuide(parent=nodes_list_body)
        self._timeline_node_column_guides[plan_id] = node_column_guide
        node_column_guide.metrics_changed.connect(
            lambda metrics, pid=plan_id: self._apply_timeline_node_column_metrics(
                pid,
                metrics,
            )
        )
        nodes_list_layout.addWidget(node_column_guide)

        nodes_container = QWidget(nodes_list_body)
        nodes_layout = QVBoxLayout(nodes_container)
        nodes_layout.setContentsMargins(0, 6, 0, 0)
        nodes_layout.setSpacing(0)
        nodes_list_layout.addWidget(nodes_container)
        body_layout.addWidget(nodes_list_body)
        outer.addWidget(body)

        self._timeline_segment_rows[plan_id] = row
        self._timeline_segment_titles[plan_id] = title
        self._timeline_segment_ranges[plan_id] = token_range
        self._timeline_segment_status_labels[plan_id] = status
        self._timeline_start_edits[plan_id] = start_edit
        self._timeline_end_edits[plan_id] = end_edit
        self._timeline_node_count_spins[plan_id] = node_count
        self._timeline_weekend_combos[plan_id] = weekend
        self._timeline_date_format_combos[plan_id] = date_format
        self._timeline_input_scope_combos[plan_id] = input_scope
        self._timeline_segment_bodies[plan_id] = body
        self._timeline_segment_collapse_buttons[plan_id] = collapse_button
        self._timeline_segment_copy_buttons[plan_id] = copy_button
        self._timeline_segment_remove_buttons[plan_id] = remove_button
        self._timeline_segment_reset_buttons[plan_id] = reset_button
        self._timeline_node_containers[plan_id] = nodes_container
        self._timeline_node_layouts[plan_id] = nodes_layout
        self._timeline_node_controllers[plan_id] = KeyedWidgetListController[
            dict[str, object], str
        ](
            layout=nodes_layout,
            create_widget=lambda node, pid=plan_id: self._create_timeline_node_row(
                pid, node
            ),
            update_widget=lambda widget, node, index, pid=plan_id: (
                self._update_timeline_node_row(pid, widget, node, index)
            ),
            dispose_widget=lambda widget, pid=plan_id: self._dispose_timeline_node_row(
                pid, widget
            ),
            key=lambda node: str(node.get("node_id", "")),
        )

        start_edit.textChanged.connect(
            lambda _text, pid=plan_id: self._on_timeline_segment_changed(pid)
        )
        end_edit.textChanged.connect(
            lambda _text, pid=plan_id: self._on_timeline_segment_changed(pid)
        )
        node_count.valueChanged.connect(
            lambda value, pid=plan_id: self._set_timeline_segment_node_count(
                pid, value
            )
        )
        weekend.currentIndexChanged.connect(
            lambda _index, pid=plan_id: self._on_timeline_segment_changed(pid)
        )
        date_format.currentIndexChanged.connect(
            lambda _index, pid=plan_id: self._on_timeline_segment_changed(pid)
        )
        input_scope.currentIndexChanged.connect(
            lambda _index, pid=plan_id: self._on_timeline_segment_changed(pid)
        )
        collapse_button.clicked.connect(
            lambda _checked=False, pid=plan_id: self._toggle_timeline_segment(pid)
        )
        copy_button.clicked.connect(
            lambda _checked=False, pid=plan_id: self._duplicate_timeline_segment(pid)
        )
        remove_button.clicked.connect(
            lambda _checked=False, pid=plan_id: self._remove_timeline_segment(pid)
        )
        reset_button.clicked.connect(
            lambda _checked=False, pid=plan_id: self._reset_timeline_segment_ratios(
                pid
            )
        )
        self._style_timeline_segment_row(row)
        return row

    def _update_timeline_segment_row(
        self,
        row: QWidget,
        item: tuple[str, dict[str, object]],
        _index: int,
    ) -> None:
        plan_id, plan = item
        segment_no = max(1, int(plan.get("segment_no", 1) or 1))
        nodes = self._active_segment_nodes(plan)
        self._timeline_syncing = True
        try:
            self._timeline_segment_titles[plan_id].setText(f"第 {segment_no} 段时间")
            if nodes:
                self._timeline_segment_ranges[plan_id].setText(f"{len(nodes)} 项")
            else:
                self._timeline_segment_ranges[plan_id].setText("")
            self._set_line_text(
                self._timeline_start_edits[plan_id],
                self._effective_segment_date(plan, "start"),
            )
            self._set_line_text(
                self._timeline_end_edits[plan_id],
                self._effective_segment_date(plan, "end"),
            )
            self._timeline_node_count_spins[plan_id].setValue(max(2, len(nodes)))
            weekend = str(
                dict(plan.get("calendar", {}) or {}).get("weekend_adjust", "none")
                or "none"
            )
            combo = self._timeline_weekend_combos[plan_id]
            combo.setCurrentIndex(max(0, combo.findData(weekend)))
            format_mode = str(plan.get("format_mode", "auto") or "auto")
            format_combo = self._timeline_date_format_combos[plan_id]
            format_index = format_combo.findData(format_mode)
            if format_index < 0:
                format_index = format_combo.findData(
                    str(plan.get("output_format", "yyyy-MM-dd") or "yyyy-MM-dd")
                )
            format_combo.setCurrentIndex(max(0, format_index))
            scope_combo = self._timeline_input_scope_combos[plan_id]
            input_scope = str(plan.get("input_scope", "fixed") or "fixed")
            scope_combo.setCurrentIndex(max(0, scope_combo.findData(input_scope)))
            self._sync_timeline_date_edit_state(plan_id, input_scope)
            self._timeline_node_controllers[plan_id].reconcile(nodes)
            guide = self._timeline_node_column_guides.get(plan_id)
            if guide is not None:
                self._apply_timeline_node_column_metrics(
                    plan_id,
                    guide.metrics(),
                )
            self._set_timeline_segment_collapsed(
                plan_id,
                plan_id in self._timeline_collapsed_segments,
            )
        finally:
            self._timeline_syncing = False
        self._style_timeline_segment_row(row)

    def _toggle_timeline_segment(self, plan_id: str) -> None:
        self._set_timeline_segment_collapsed(
            plan_id,
            plan_id not in self._timeline_collapsed_segments,
        )
        refresh_layout_chain(self._timeline_card, passes=2)

    def _sync_timeline_date_edit_state(self, plan_id: str, scope: str) -> None:
        floating = str(scope or "fixed") == "floating"
        for side, edit in (
            ("开始", self._timeline_start_edits.get(plan_id)),
            ("结束", self._timeline_end_edits.get(plan_id)),
        ):
            if edit is None:
                continue
            edit.setEnabled(not floating)
            edit.setPlaceholderText(
                f"请在工作台填写{side}日期"
                if floating
                else (
                    "例如：2025-10-27 或 2025年10月27日"
                    if side == "开始"
                    else "例如：2026-01-27 或 2026年1月27日"
                )
            )

    def _set_timeline_segment_collapsed(
        self,
        plan_id: str,
        collapsed: bool,
    ) -> None:
        body = self._timeline_segment_bodies.get(plan_id)
        button = self._timeline_segment_collapse_buttons.get(plan_id)
        if body is None or button is None:
            return
        if collapsed:
            self._timeline_collapsed_segments.add(plan_id)
        else:
            self._timeline_collapsed_segments.discard(plan_id)
        body.setVisible(not collapsed)
        button.setIcon(
            get_icon(
                "chevron-right" if collapsed else "chevron-down",
                15,
                get_theme().text_secondary,
            )
        )
        button.setToolTip("展开本段" if collapsed else "折叠本段")

    def _dispose_timeline_segment_row(self, row: QWidget) -> None:
        plan_id = str(row.property("planId") or "")
        for key in [key for key in self._timeline_node_rows if key[0] == plan_id]:
            self._timeline_node_rows.pop(key, None)
            self._timeline_node_index_labels.pop(key, None)
            self._timeline_node_token_edits.pop(key, None)
            self._timeline_node_ratio_edits.pop(key, None)
            self._timeline_node_result_edits.pop(key, None)
        for mapping in (
            self._timeline_segment_rows,
            self._timeline_segment_titles,
            self._timeline_segment_ranges,
            self._timeline_segment_status_labels,
            self._timeline_start_edits,
            self._timeline_end_edits,
            self._timeline_node_count_spins,
            self._timeline_weekend_combos,
            self._timeline_date_format_combos,
            self._timeline_input_scope_combos,
            self._timeline_segment_bodies,
            self._timeline_segment_collapse_buttons,
            self._timeline_segment_copy_buttons,
            self._timeline_segment_remove_buttons,
            self._timeline_segment_reset_buttons,
            self._timeline_node_controllers,
            self._timeline_node_containers,
            self._timeline_node_layouts,
            self._timeline_node_column_guides,
        ):
            mapping.pop(plan_id, None)
        self._timeline_collapsed_segments.discard(plan_id)
        row.setParent(None)
        row.deleteLater()

    # ------------------------------------------------------------------
    # Node widgets
    # ------------------------------------------------------------------

    def _create_timeline_node_row(
        self,
        plan_id: str,
        node: dict[str, object],
    ) -> QFrame:
        node_id = str(node.get("node_id", ""))
        key = (plan_id, node_id)
        row = QFrame(self._timeline_node_containers[plan_id])
        row.setObjectName("timeline_node_row")
        row.setProperty("nodeId", node_id)
        row.setAttribute(Qt.WA_StyledBackground)
        row.setMinimumHeight(get_theme().token_row_min_height)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(
            0,
            get_theme().token_row_padding_y,
            0,
            get_theme().token_row_padding_y,
        )
        layout.setSpacing(get_theme().token_row_column_gap)

        index_label = QLabel(row)
        index_label.setFixedWidth(38)
        index_label.setAlignment(Qt.AlignCenter)
        token_edit = TimelineTokenEdit(row)
        ratio_edit = QLineEdit(row)
        ratio_edit.setObjectName("timeline_ratio_edit")
        ratio_edit.setPlaceholderText("0–100")
        result_edit = ElidedReadOnlyValue(parent=row)
        result_edit.setObjectName("timeline_node_result")
        result_edit.setPlaceholderText("等待起止时间")
        control_height = resolved_control_height(get_theme(), "md")
        for edit in (token_edit, ratio_edit, result_edit):
            edit.setMinimumHeight(control_height)
            edit.setMaximumHeight(control_height)
        layout.addWidget(index_label, 0)
        layout.addWidget(token_edit, 3)
        layout.addWidget(ratio_edit, 1)
        layout.addWidget(result_edit, 2)

        self._timeline_node_rows[key] = row
        self._timeline_node_index_labels[key] = index_label
        self._timeline_node_token_edits[key] = token_edit
        self._timeline_node_ratio_edits[key] = ratio_edit
        self._timeline_node_result_edits[key] = result_edit

        token_edit.activated.connect(
            lambda token, pid=plan_id: self._copy_timeline_token(pid, token)
        )
        ratio_edit.textChanged.connect(
            lambda _text, pid=plan_id, nid=node_id: self._on_timeline_ratio_changed(
                pid, nid
            )
        )
        return row

    def _update_timeline_node_row(
        self,
        plan_id: str,
        row: QWidget,
        node: dict[str, object],
        index: int,
    ) -> None:
        node_id = str(node.get("node_id", ""))
        key = (plan_id, node_id)
        active_nodes = self._active_segment_nodes(
            self._timeline_plan(plan_id) or {}
        )
        self._timeline_syncing = True
        try:
            self._timeline_node_index_labels[key].setText(str(index + 1))
            token = self._node_token(node)
            self._set_line_text(
                self._timeline_node_token_edits[key],
                material_token(MaterialTokenNamespace.TIME, token),
            )
            ratio_edit = self._timeline_node_ratio_edits[key]
            self._set_line_text(ratio_edit, self._ratio_percent_text(node))
            is_endpoint = index == 0 or index == len(active_nodes) - 1
            ratio_edit.setReadOnly(is_endpoint)
            ratio_edit.setToolTip(
                "起止节点固定为 0% / 100%"
                if is_endpoint
                else f"微调 {{{{{token}}}}} 在本段中的累计位置"
            )
            apply_token_row_style(
                row,
                object_name="timeline_node_row",
                is_last=index == len(active_nodes) - 1,
            )
        finally:
            self._timeline_syncing = False

    def _apply_timeline_node_column_metrics(
        self,
        plan_id: str,
        metrics: TimelineNodeColumnMetrics,
    ) -> None:
        if not isinstance(metrics, TimelineNodeColumnMetrics):
            return
        theme = get_theme()
        for key, row in self._timeline_node_rows.items():
            if key[0] != plan_id:
                continue
            layout = row.layout()
            index = self._timeline_node_index_labels.get(key)
            token = self._timeline_node_token_edits.get(key)
            ratio = self._timeline_node_ratio_edits.get(key)
            result = self._timeline_node_result_edits.get(key)
            if any(item is None for item in (layout, index, token, ratio, result)):
                continue
            layout.setContentsMargins(
                metrics.row_margin_x,
                theme.token_row_padding_y,
                metrics.row_margin_x,
                theme.token_row_padding_y,
            )
            layout.setSpacing(metrics.column_gap)
            layout.setStretch(1, metrics.token_stretch)
            layout.setStretch(3, metrics.result_stretch)
            index.setFixedWidth(metrics.index_width)
            token.setMinimumWidth(metrics.token_min_width)
            token.setMaximumWidth(16777215)
            token.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            ratio.setFixedWidth(metrics.position_width)
            result.setMinimumWidth(metrics.result_min_width)
            result.setMaximumWidth(16777215)
            result.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def _dispose_timeline_node_row(self, plan_id: str, row: QWidget) -> None:
        key = (plan_id, str(row.property("nodeId") or ""))
        self._timeline_node_rows.pop(key, None)
        self._timeline_node_index_labels.pop(key, None)
        self._timeline_node_token_edits.pop(key, None)
        self._timeline_node_ratio_edits.pop(key, None)
        self._timeline_node_result_edits.pop(key, None)
        row.setParent(None)
        row.deleteLater()

    # ------------------------------------------------------------------
    # Model normalization and mutation
    # ------------------------------------------------------------------

    def _normalized_timeline_segments(self) -> dict[str, dict[str, object]]:
        profile = self._selected_profile()
        plans = normalize_timeline_plans(profile.timeline_plans)
        if not plans:
            return {}

        used_segment_numbers: set[int] = set()
        next_segment_no = 1
        normalized: dict[str, dict[str, object]] = {}
        persisted: dict[str, dict[str, object]] = {}
        for plan_id, source in plans.items():
            if not _is_timeline_editor_plan(source):
                persisted[plan_id] = copy.deepcopy(source)
                continue
            plan = copy.deepcopy(source)
            segment_no = int(plan.get("segment_no", 0) or 0)
            if segment_no <= 0 or segment_no in used_segment_numbers:
                while next_segment_no in used_segment_numbers:
                    next_segment_no += 1
                segment_no = next_segment_no
            used_segment_numbers.add(segment_no)
            next_segment_no = max(next_segment_no, segment_no + 1)

            if (
                not bool(plan.get("deleted", False))
                and str(plan.get("input_scope", "fixed") or "fixed") == "floating"
            ):
                self._migrate_timeline_anchor_fields(plan, segment_no)

            preset = dict(plan.get("preset", {}) or {})
            is_legacy = preset.get("id") != _SEGMENT_PRESET["id"]
            effective_start = self._effective_segment_date(plan, "start")
            effective_end = self._effective_segment_date(plan, "end")
            uses_legacy_date_anchor = bool(
                not str(plan.get("start_value", "") or "").strip()
                and self._clean_timeline_field_key(plan.get("start_field", ""))
            )
            date_format = (
                infer_timeline_date_format(effective_start or effective_end)
                if is_legacy or uses_legacy_date_anchor
                else str(plan.get("output_format", "") or "").strip()
                or infer_timeline_date_format(effective_start or effective_end)
            )

            raw_nodes = list(plan.get("nodes", []) or [])
            if not raw_nodes and not bool(plan.get("deleted", False)):
                raw_nodes = timeline_segment_nodes(
                    segment_no,
                    3,
                    date_format=date_format,
                )
            canonical_nodes: list[dict[str, object]] = []
            used_node_ids: set[str] = set()
            used_node_numbers: set[int] = set()
            for index, raw_node in enumerate(raw_nodes, start=1):
                node = copy.deepcopy(dict(raw_node))
                node_no = int(node.get("node_no", index) or index)
                if node_no <= 0 or node_no in used_node_numbers:
                    node_no = index
                    while node_no in used_node_numbers:
                        node_no += 1
                used_node_numbers.add(node_no)
                node_id = str(node.get("node_id", "") or f"node_{node_no}")
                if node_id in used_node_ids:
                    suffix = 2
                    candidate = f"{node_id}_{suffix}"
                    while candidate in used_node_ids:
                        suffix += 1
                        candidate = f"{node_id}_{suffix}"
                    node_id = candidate
                used_node_ids.add(node_id)
                token = f"时间节点{segment_no}-{node_no}"
                outputs = [
                    dict(output)
                    for output in list(node.get("outputs", []) or [])
                    if isinstance(output, dict)
                    and str(dict(output).get("field", "") or "").strip()
                ]
                canonical_output = {"field": token, "format": date_format}
                legacy_outputs = [
                    {
                        "field": self._clean_timeline_field_key(output.get("field", "")),
                        "format": str(output.get("format", date_format) or date_format),
                    }
                    for output in outputs
                    if self._clean_timeline_field_key(output.get("field", "")) != token
                ]
                node.update(
                    {
                        "node_id": node_id,
                        "node_no": node_no,
                        "active": bool(node.get("active", True)),
                        "label": token,
                        "outputs": [canonical_output, *legacy_outputs],
                    }
                )
                canonical_nodes.append(node)

            plan.update(
                {
                    "segment_no": segment_no,
                    "label": f"第 {segment_no} 段时间",
                    "output_format": date_format,
                    "nodes": sorted(
                        canonical_nodes,
                        key=lambda node: int(node.get("node_no", 0) or 0),
                    ),
                    "preset": copy.deepcopy(preset if is_legacy else _SEGMENT_PRESET),
                }
            )
            if is_legacy:
                plan["format_mode"] = "auto"
            plan["enabled"] = bool(
                effective_start
                and effective_end
                and not bool(plan.get("deleted", False))
            )
            normalized[plan_id] = normalize_timeline_plans({plan_id: plan})[plan_id]
            persisted[plan_id] = normalized[plan_id]

        if persisted != profile.timeline_plans:
            profile.timeline_plans = persisted
        return normalized

    def _timeline_plan(self, plan_id: str) -> dict[str, object] | None:
        plans = normalize_timeline_plans(self._selected_profile().timeline_plans)
        plan = plans.get(plan_id)
        return copy.deepcopy(plan) if plan is not None else None

    def _store_timeline_plan(self, plan_id: str, plan: dict[str, object]) -> None:
        profile = self._selected_profile()
        plans = normalize_timeline_plans(profile.timeline_plans)
        normalized = normalize_timeline_plans({plan_id: plan})
        plans[plan_id] = normalized[plan_id]
        profile.timeline_plans = plans

    def _active_timeline_segment_items(
        self,
    ) -> list[tuple[str, dict[str, object]]]:
        plans = self._normalized_timeline_segments()
        return sorted(
            [
                (plan_id, plan)
                for plan_id, plan in plans.items()
                if not bool(plan.get("deleted", False))
            ],
            key=lambda item: int(item[1].get("segment_no", 0) or 0),
        )

    @staticmethod
    def _active_segment_nodes(plan: dict[str, object]) -> list[dict[str, object]]:
        return sorted(
            [
                dict(node)
                for node in list(plan.get("nodes", []) or [])
                if bool(dict(node).get("active", True))
            ],
            key=lambda node: int(node.get("node_no", 0) or 0),
        )

    def _effective_segment_date(self, plan: dict[str, object], side: str) -> str:
        direct = str(plan.get(f"{side}_value", "") or "").strip()
        if direct:
            return direct
        field_key = self._clean_timeline_field_key(plan.get(f"{side}_field", ""))
        if not field_key:
            return ""
        task_values = dict(getattr(self, "_task_field_values", {}) or {})
        if (
            str(plan.get("input_scope", "fixed") or "fixed") == "floating"
            and field_key in task_values
        ):
            return str(task_values.get(field_key, "") or "").strip()
        profile = self._selected_profile()
        return str(
            getattr(self, "_template_field_values", {}).get(
                field_key,
                profile.fields.get(field_key, ""),
            )
            or ""
        ).strip()

    @staticmethod
    def _timeline_anchor_field_keys(segment_no: int) -> tuple[str, str]:
        number = max(1, int(segment_no))
        return (
            f"时间段{number}开始日期",
            f"时间段{number}结束日期",
        )

    def _migrate_timeline_anchor_fields(
        self,
        plan: dict[str, object],
        segment_no: int,
    ) -> None:
        profile = self._selected_profile()
        expected = self._timeline_anchor_field_keys(segment_no)
        legacy = (
            f"时间段开始日期{segment_no}",
            f"时间段结束日期{segment_no}",
        )
        for side, expected_key, legacy_key in zip(
            ("start", "end"),
            expected,
            legacy,
        ):
            current_key = self._clean_timeline_field_key(
                plan.get(f"{side}_field", "")
            )
            if current_key not in {"", legacy_key, expected_key}:
                continue
            source_key = current_key or legacy_key
            value = str(
                self._template_field_values.get(
                    source_key,
                    profile.fields.get(source_key, ""),
                )
                or ""
            ).strip()
            plan[f"{side}_field"] = expected_key
            profile.field_scopes[expected_key] = "floating"
            self._declared_field_keys.add(expected_key)
            if value:
                profile.fields[expected_key] = value
                self._template_field_values[expected_key] = value
            if source_key != expected_key:
                discard_material_field(profile, source_key)
                self._template_field_values.pop(source_key, None)
                self._declared_field_keys.discard(source_key)

    def _remove_timeline_anchor_fields(self, plan: dict[str, object]) -> bool:
        segment_no = max(1, int(plan.get("segment_no", 1) or 1))
        owned = set(self._timeline_anchor_field_keys(segment_no))
        candidates = {
            self._clean_timeline_field_key(plan.get("start_field", "")),
            self._clean_timeline_field_key(plan.get("end_field", "")),
        }
        removable = {key for key in candidates if key and key in owned}
        if not removable:
            return False
        profile = self._selected_profile()
        for key in removable:
            discard_material_field(profile, key)
            getattr(self, "_template_field_values", {}).pop(key, None)
            getattr(self, "_task_field_values", {}).pop(key, None)
            getattr(self, "_declared_field_keys", set()).discard(key)
            if key in getattr(self, "_manual_field_keys", []):
                self._manual_field_keys.remove(key)
        return True

    def _configure_timeline_input_scope(
        self,
        plan: dict[str, object],
        *,
        scope: str,
        start_value: str,
        end_value: str,
    ) -> bool:
        previous_scope = str(plan.get("input_scope", "fixed") or "fixed")
        segment_no = max(1, int(plan.get("segment_no", 1) or 1))
        profile = self._selected_profile()
        scope_changed = previous_scope != scope
        if scope == "floating":
            start_field, end_field = self._timeline_anchor_field_keys(segment_no)
            plan["start_value"] = ""
            plan["end_value"] = ""
            plan["start_field"] = start_field
            plan["end_field"] = end_field
            for key, value in (
                (start_field, start_value),
                (end_field, end_value),
            ):
                profile.field_scopes[key] = "floating"
                self._declared_field_keys.add(key)
                if previous_scope != "floating":
                    cleaned = str(value or "").strip()
                    if cleaned:
                        self._task_field_values[key] = cleaned
                    else:
                        self._task_field_values.pop(key, None)
                    profile.fields.pop(key, None)
                    self._template_field_values.pop(key, None)
        else:
            removed_fields = self._remove_timeline_anchor_fields(plan)
            plan["start_value"] = start_value
            plan["end_value"] = end_value
            plan["start_field"] = ""
            plan["end_field"] = ""
            scope_changed = scope_changed or removed_fields
        plan["input_scope"] = scope
        return scope_changed

    @staticmethod
    def _clean_timeline_field_key(value: object) -> str:
        text = str(value or "").strip()
        try:
            ref = parse_material_token(text)
        except (TypeError, ValueError):
            ref = None
        if ref is not None:
            if ref.namespace is not MaterialTokenNamespace.TIME:
                return ""
            text = ref.identifier
        return text

    @staticmethod
    def _node_token(node: dict[str, object]) -> str:
        outputs = list(node.get("outputs", []) or [])
        return (
            str(dict(outputs[0]).get("field", "") or "").strip()
            if outputs
            else str(node.get("label", "") or "").strip()
        )

    def _next_timeline_segment_number(self) -> int:
        return self._next_timeline_segment_slot()[0]

    def _next_timeline_segment_slot(self) -> tuple[int, str, list[str]]:
        """Return a reusable public number before allocating a new one."""

        plans = self._normalized_timeline_segments()
        reusable = sorted(
            (
                int(plan.get("segment_no", 0) or 0),
                plan_id,
                plan,
            )
            for plan_id, plan in plans.items()
            if bool(plan.get("deleted", False))
            and str(plan.get("number_state", "") or "") == "reusable"
            and int(plan.get("segment_no", 0) or 0) > 0
        )
        if reusable:
            segment_no, plan_id, plan = reusable[0]
            retired_outputs = list(
                timeline_output_field_keys(
                    {plan_id: plan},
                    include_inactive=True,
                )
            )
            return segment_no, plan_id, retired_outputs

        segment_no = max(
            [int(plan.get("segment_no", 0) or 0) for plan in plans.values()] or [0]
        ) + 1
        return segment_no, self._next_timeline_plan_id(segment_no), []

    def _next_timeline_plan_id(self, segment_no: int) -> str:
        plans = normalize_timeline_plans(self._selected_profile().timeline_plans)
        base = f"segment_{segment_no}"
        if base not in plans:
            return base
        suffix = 2
        while f"{base}_{suffix}" in plans:
            suffix += 1
        return f"{base}_{suffix}"

    def _add_timeline_segment(self) -> None:
        segment_no, plan_id, retired_outputs = self._next_timeline_segment_slot()
        profile = self._selected_profile()
        plans = normalize_timeline_plans(profile.timeline_plans)
        segment = default_timeline_segment(segment_no, node_count=3)
        segment["retired_outputs"] = retired_outputs
        plans[plan_id] = segment
        profile.timeline_plans = plans
        self._refresh_timeline_ui()
        self._refresh_timeline_dependent_views(immediate=True)
        row = self._timeline_segment_rows.get(plan_id)
        if row is not None:
            self._detail_scroll.ensureWidgetVisible(row, 0, 24)

    def _duplicate_timeline_segment(self, plan_id: str) -> None:
        source = self._timeline_plan(plan_id)
        if source is None:
            return
        segment_no, new_plan_id, retired_outputs = (
            self._next_timeline_segment_slot()
        )
        duplicate = default_timeline_segment(
            segment_no,
            node_count=max(2, len(self._active_segment_nodes(source))),
            start_value=self._effective_segment_date(source, "start"),
            end_value=self._effective_segment_date(source, "end"),
        )
        duplicate["calendar"] = copy.deepcopy(source.get("calendar", {}))
        duplicate["rounding"] = str(source.get("rounding", "half_up") or "half_up")
        duplicate["constraints"] = copy.deepcopy(source.get("constraints", {}))
        duplicate["output_format"] = str(
            source.get("output_format", "yyyy-MM-dd") or "yyyy-MM-dd"
        )
        duplicate["format_mode"] = str(
            source.get("format_mode", "auto") or "auto"
        )
        duplicate_input_scope = str(
            source.get("input_scope", "fixed") or "fixed"
        )
        duplicate_start = str(duplicate.get("start_value", "") or "").strip()
        duplicate_end = str(duplicate.get("end_value", "") or "").strip()
        self._configure_timeline_input_scope(
            duplicate,
            scope=duplicate_input_scope,
            start_value=duplicate_start,
            end_value=duplicate_end,
        )
        source_nodes = self._active_segment_nodes(source)
        duplicate_nodes = timeline_segment_nodes(
            segment_no,
            max(2, len(source_nodes)),
            date_format=str(duplicate["output_format"]),
        )
        for target, original in zip(duplicate_nodes, source_nodes):
            target["rule"] = copy.deepcopy(original.get("rule", {}))
        duplicate["nodes"] = duplicate_nodes
        duplicate["retired_outputs"] = retired_outputs
        duplicate["enabled"] = bool(duplicate_start and duplicate_end)
        plans = normalize_timeline_plans(self._selected_profile().timeline_plans)
        plans[new_plan_id] = duplicate
        self._selected_profile().timeline_plans = plans
        if str(duplicate.get("input_scope", "fixed")) == "floating":
            refresh_fields = getattr(self, "_refresh_official_field_editor", None)
            if callable(refresh_fields):
                refresh_fields()
        self._refresh_timeline_ui()
        self._refresh_timeline_dependent_views(immediate=True)
        row = self._timeline_segment_rows.get(new_plan_id)
        if row is not None:
            self._detail_scroll.ensureWidgetVisible(row, 0, 24)
        Toast.show_success(f"已复制为第 {segment_no} 段时间")

    def _remove_timeline_segment(self, plan_id: str) -> None:
        plan = self._timeline_plan(plan_id)
        if plan is None:
            return
        segment_no = int(plan.get("segment_no", 0) or 0)
        reference_evidence = self._timeline_segment_reference_evidence(plan)
        referenced_fields = set(reference_evidence.token_keys)
        token_copied = bool(plan.get("token_copied", False))
        scan_failed = reference_evidence.scan_status == "failed"
        if referenced_fields or token_copied or scan_failed:
            number_state = self._choose_timeline_deletion_number_state(
                segment_no=segment_no,
                referenced_fields=referenced_fields,
                token_copied=token_copied,
                reference_occurrences=reference_evidence.occurrence_count,
                scan_failed=scan_failed,
            )
            if not number_state:
                return
        else:
            if reference_evidence.scan_status == "ok":
                evidence_summary = (
                    "当前已保存模板未发现本段 Token，且本应用没有点击复制记录"
                )
            else:
                evidence_summary = (
                    "当前没有可扫描的模板，且本应用没有该段 Token 的点击复制记录"
                )
            if not confirm(
                "删除整段时间",
                f"{evidence_summary}；删除后编号 {segment_no} 将自动回收。",
                confirm_text="删除并回收编号",
                destructive=True,
                parent=self,
            ):
                return
            number_state = "reusable"
        removed_anchor_fields = self._remove_timeline_anchor_fields(plan)
        plan["deleted"] = True
        plan["enabled"] = False
        plan["number_state"] = number_state
        self._store_timeline_plan(plan_id, plan)
        if removed_anchor_fields:
            refresh_fields = getattr(self, "_refresh_official_field_editor", None)
            if callable(refresh_fields):
                refresh_fields()
        self._refresh_timeline_ui()
        self._refresh_timeline_dependent_views(immediate=True)
        Toast.show_success(
            f"已删除第 {segment_no} 段时间，"
            + ("编号可再次使用" if number_state == "reusable" else "编号已保留")
        )

    def _timeline_segment_reference_evidence(
        self,
        plan: dict[str, object],
    ) -> TimelineReferenceEvidence:
        """Inspect the current saved DOCX for tokens owned by one segment."""

        source_path = str(
            getattr(self, "_placeholder_source_path", lambda: "")() or ""
        ).strip()
        if not source_path:
            return TimelineReferenceEvidence(scan_status="no_source")

        path = Path(source_path)
        if path.suffix.lower() != ".docx" or not path.is_file():
            return TimelineReferenceEvidence(scan_status="failed")

        try:
            inventory = scan_docx_placeholder_inventory(path)
        except Exception:
            return TimelineReferenceEvidence(scan_status="failed")

        segment_no = int(plan.get("segment_no", 0) or 0)
        segment_token_pattern = re.compile(
            rf"^时间节点{re.escape(str(segment_no))}-[1-9]\d*$"
        )
        matches = [
            item
            for item in inventory
            if segment_token_pattern.fullmatch(
                self._clean_timeline_field_key(getattr(item, "key", ""))
            )
        ]
        return TimelineReferenceEvidence(
            scan_status="ok",
            token_keys=tuple(
                self._clean_timeline_field_key(getattr(item, "key", ""))
                for item in matches
            ),
            occurrence_count=sum(
                int(getattr(item, "occurrence_count", 0) or 0)
                for item in matches
            ),
        )

    def _choose_timeline_deletion_number_state(
        self,
        *,
        segment_no: int,
        referenced_fields: set[str],
        token_copied: bool,
        reference_occurrences: int = 0,
        scan_failed: bool = False,
    ) -> str:
        reasons: list[str] = []
        if referenced_fields:
            reasons.append(
                "当前模板仍引用 "
                f"{len(referenced_fields)} 个本段 Token"
                f"（共 {reference_occurrences} 处）"
            )
        if token_copied:
            reasons.append("本段 Token 曾被点击复制")
        if scan_failed:
            reasons.append("当前模板扫描失败，无法确认 Token 是否仍在使用")
        message = "；".join(reasons) + "。\n\n"
        message += (
            f"若释放编号 {segment_no}，以后新增的时间段可能使用相同 Token；"
            "旧模板中的 Token 将随之指向新时间段。"
        )

        dialog = BaseDialog(
            title=f"删除第 {segment_no} 段时间",
            icon_style="warning",
            parent=self,
        )
        dialog.add_message(message)
        selected = {"value": ""}

        cancel_button = dialog.add_secondary_button("取消")
        release_button = dialog.add_secondary_button("释放编号并删除")
        preserve_button = dialog.add_primary_button(
            "保留编号并删除",
            destructive=True,
        )
        apply_button_variant(release_button, "ghost-danger")

        cancel_button.clicked.connect(dialog.reject)

        def choose(value: str) -> None:
            selected["value"] = value
            dialog.accept()

        release_button.clicked.connect(lambda: choose("reusable"))
        preserve_button.clicked.connect(lambda: choose("reserved"))
        return selected["value"] if dialog.exec() == QDialog.Accepted else ""

    def _on_timeline_segment_changed(self, plan_id: str) -> None:
        if self._timeline_syncing:
            return
        plan = self._timeline_plan(plan_id)
        if plan is None:
            return
        previous_scope = str(plan.get("input_scope", "fixed") or "fixed")
        if previous_scope == "floating":
            start_value = self._effective_segment_date(plan, "start")
            end_value = self._effective_segment_date(plan, "end")
        else:
            start_value = self._timeline_start_edits[plan_id].text().strip()
            end_value = self._timeline_end_edits[plan_id].text().strip()
        format_mode = str(
            self._timeline_date_format_combos[plan_id].currentData() or "auto"
        )
        date_format = (
            infer_timeline_date_format(start_value or end_value)
            if format_mode == "auto"
            else format_mode
        )
        input_scope = str(
            self._timeline_input_scope_combos[plan_id].currentData() or "fixed"
        )
        scope_changed = self._configure_timeline_input_scope(
            plan,
            scope=input_scope,
            start_value=start_value,
            end_value=end_value,
        )
        plan["enabled"] = bool(start_value and end_value)
        plan["output_format"] = date_format
        plan["format_mode"] = format_mode
        plan["preset"] = copy.deepcopy(_SEGMENT_PRESET)
        calendar = dict(plan.get("calendar", {}) or {})
        calendar["basis"] = "calendar_day"
        calendar["weekend_adjust"] = str(
            self._timeline_weekend_combos[plan_id].currentData() or "none"
        )
        plan["calendar"] = calendar
        for node in list(plan.get("nodes", []) or []):
            outputs = list(dict(node).get("outputs", []) or [])
            for output in outputs:
                output["format"] = date_format
            node["outputs"] = outputs
        self._store_timeline_plan(plan_id, plan)
        self._sync_timeline_date_edit_state(plan_id, input_scope)
        if input_scope == "floating" and previous_scope != "floating":
            update_preview = getattr(self, "_update_preview_field_value", None)
            if callable(update_preview):
                update_preview(
                    str(plan.get("start_field", "") or ""),
                    start_value,
                )
                update_preview(
                    str(plan.get("end_field", "") or ""),
                    end_value,
                )
        if scope_changed:
            refresh_fields = getattr(self, "_refresh_official_field_editor", None)
            if callable(refresh_fields):
                refresh_fields()
            if input_scope != "floating":
                apply_profile = getattr(self, "_apply_current_profile", None)
                if callable(apply_profile):
                    apply_profile()
        self._refresh_timeline_dependent_views()

    def _set_timeline_segment_node_count(self, plan_id: str, count: int) -> None:
        if self._timeline_syncing:
            return
        plan = self._timeline_plan(plan_id)
        if plan is None:
            return
        target_count = max(2, int(count))
        segment_no = max(1, int(plan.get("segment_no", 1) or 1))
        date_format = str(
            plan.get("output_format", "")
            or infer_timeline_date_format(
                self._effective_segment_date(plan, "start")
                or self._effective_segment_date(plan, "end")
            )
        )
        existing = {
            int(dict(node).get("node_no", 0) or 0): copy.deepcopy(dict(node))
            for node in list(plan.get("nodes", []) or [])
        }
        maximum = max([target_count, *existing.keys()])
        fresh = {
            int(node.get("node_no", 0) or 0): node
            for node in timeline_segment_nodes(
                segment_no,
                maximum,
                date_format=date_format,
            )
        }
        nodes: list[dict[str, object]] = []
        for node_no in range(1, maximum + 1):
            node = existing.get(node_no, fresh[node_no])
            token = f"时间节点{segment_no}-{node_no}"
            node["node_no"] = node_no
            node["active"] = node_no <= target_count
            node["label"] = token
            existing_outputs = [
                dict(output)
                for output in list(node.get("outputs", []) or [])
                if isinstance(output, dict)
            ]
            legacy_outputs = [
                {
                    "field": self._clean_timeline_field_key(output.get("field", "")),
                    "format": str(output.get("format", date_format) or date_format),
                }
                for output in existing_outputs
                if self._clean_timeline_field_key(output.get("field", "")) != token
            ]
            node["outputs"] = [
                {"field": token, "format": date_format},
                *legacy_outputs,
            ]
            if node_no <= target_count:
                ratio = Decimal(node_no - 1) / Decimal(target_count - 1)
                node["rule"] = {
                    "operation": "ratio",
                    "value": _decimal_text(ratio),
                }
            nodes.append(node)
        plan["nodes"] = nodes
        plan["overrides"] = {}
        self._store_timeline_plan(plan_id, plan)
        self._refresh_timeline_ui()
        self._refresh_timeline_dependent_views(immediate=True)

    def _reset_timeline_segment_ratios(self, plan_id: str) -> None:
        plan = self._timeline_plan(plan_id)
        if plan is None:
            return
        active = self._active_segment_nodes(plan)
        if len(active) < 2:
            return
        active_ids = {str(node.get("node_id", "")) for node in active}
        positions = {
            str(node.get("node_id", "")): _decimal_text(
                Decimal(index) / Decimal(len(active) - 1)
            )
            for index, node in enumerate(active)
        }
        for node in list(plan.get("nodes", []) or []):
            node_id = str(dict(node).get("node_id", ""))
            if node_id in active_ids:
                node["rule"] = {
                    "operation": "ratio",
                    "value": positions[node_id],
                }
        plan["overrides"] = {}
        self._store_timeline_plan(plan_id, plan)
        self._refresh_timeline_ui()
        self._refresh_timeline_dependent_views(immediate=True)
        Toast.show_success("已恢复平均分配")

    def _on_timeline_ratio_changed(self, plan_id: str, node_id: str) -> None:
        if self._timeline_syncing:
            return
        key = (plan_id, node_id)
        edit = self._timeline_node_ratio_edits.get(key)
        plan = self._timeline_plan(plan_id)
        if edit is None or plan is None or edit.isReadOnly():
            return
        raw = edit.text().strip()
        try:
            value = _decimal_text(Decimal(raw or "0") / Decimal(100))
        except InvalidOperation:
            value = raw
        for node in list(plan.get("nodes", []) or []):
            if str(dict(node).get("node_id", "")) == node_id:
                node["rule"] = {"operation": "ratio", "value": value}
                break
        self._store_timeline_plan(plan_id, plan)
        self._refresh_timeline_dependent_views()

    def _copy_timeline_token(self, plan_id: str, token: str) -> None:
        exact = str(token or "").strip()
        if not exact:
            return
        plan = self._timeline_plan(plan_id)
        if plan is not None and not bool(plan.get("token_copied", False)):
            plan["token_copied"] = True
            self._store_timeline_plan(plan_id, plan)
        QApplication.clipboard().setText(exact)
        Toast.show_success(f"已复制 {exact}")

    # ------------------------------------------------------------------
    # Resolution, status, navigation, and theme
    # ------------------------------------------------------------------

    def _refresh_timeline_ui(self) -> None:
        if not hasattr(self, "_timeline_card"):
            return
        items = self._active_timeline_segment_items()
        self._timeline_segments_controller.reconcile(items)
        self._timeline_segments_container.setVisible(bool(items))
        self._recalculate_timeline_preview()
        self._sync_timeline_navigation()
        self._apply_timeline_theme()
        refresh_layout_chain(self._timeline_card, passes=2)

    def _recalculate_timeline_preview(self) -> None:
        profile = self._selected_profile()
        preview_fields = getattr(self, "_material_preview_fields", None)
        base_values = (
            preview_fields()
            if callable(preview_fields)
            else {
                **profile.fields,
                **getattr(self, "_template_field_values", {}),
            }
        )
        self._resolve_timeline_preview_fields(base_values)

    def _refresh_timeline_dependent_views(self, *, immediate: bool = False) -> None:
        self._recalculate_timeline_preview()
        refresh_fields = getattr(self, "_refresh_field_only_projection", None)
        cached_state = getattr(self, "_last_section_summary_state", None)
        if immediate and callable(refresh_fields) and cached_state is not None:
            refresh_fields()
            return
        schedule_refresh = getattr(self, "_schedule_summary_refresh", None)
        if callable(schedule_refresh) and cached_state is not None:
            schedule_refresh(150, scope="fields")

    def _resolve_timeline_preview_fields(self, fields: dict[str, str]) -> dict[str, str]:
        self._timeline_resolution = resolve_timeline_plans(
            fields,
            self._selected_profile().timeline_plans,
        )
        self._apply_timeline_resolution_to_ui()
        return dict(self._timeline_resolution.values)

    def _apply_timeline_resolution_to_ui(self) -> None:
        node_output_fields: dict[tuple[str, str], str] = {}
        for plan_id, plan in normalize_timeline_plans(
            self._selected_profile().timeline_plans
        ).items():
            for node in self._active_segment_nodes(plan):
                node_output_fields[(plan_id, str(node.get("node_id", "")))] = (
                    self._node_token(node)
                )
        resolved_nodes = {
            (node.plan_id, node.node_id): node
            for node in self._timeline_resolution.nodes
        }
        for key, edit in self._timeline_node_result_edits.items():
            node = resolved_nodes.get(key)
            output_field = node_output_fields.get(key, "")
            value = (
                str(self._timeline_resolution.values.get(output_field, ""))
                if node is not None and output_field
                else ""
            )
            self._set_line_text(edit, value)
        self._sync_timeline_status()

    def _sync_timeline_status(self) -> None:
        plans = self._normalized_timeline_segments()
        visible = {
            plan_id: plan
            for plan_id, plan in plans.items()
            if not bool(plan.get("deleted", False))
        }
        issues_by_plan: dict[str, list] = {plan_id: [] for plan_id in visible}
        for issue in self._timeline_resolution.issues:
            issues_by_plan.setdefault(issue.plan_id, []).append(issue)

        missing_total = 0
        error_total = 0
        warning_total = 0
        node_total = 0
        for plan_id, plan in visible.items():
            messages: list[tuple[str, str]] = []
            start_value = self._effective_segment_date(plan, "start")
            end_value = self._effective_segment_date(plan, "end")
            if not start_value:
                messages.append(("error", "请填写开始时间"))
                missing_total += 1
            if not end_value:
                messages.append(("error", "请填写结束时间"))
                missing_total += 1
            if (
                start_value
                and end_value
                and str(plan.get("format_mode", "auto") or "auto") == "auto"
                and infer_timeline_date_format(start_value)
                != infer_timeline_date_format(end_value)
            ):
                messages.append(
                    ("warning", "起止时间格式不同，节点按开始时间格式输出")
                )
                warning_total += 1
            for issue in issues_by_plan.get(plan_id, []):
                severity = "error" if issue.severity == "error" else "warning"
                messages.append((severity, issue.message or "时间节点计算异常"))
                if severity == "error":
                    error_total += 1
                else:
                    warning_total += 1
            nodes = self._active_segment_nodes(plan)
            node_total += len(nodes)
            status = self._timeline_segment_status_labels.get(plan_id)
            if status is not None:
                local_errors = sum(severity == "error" for severity, _message in messages)
                local_warnings = len(messages) - local_errors
                if local_errors:
                    status.setText(f"缺 {local_errors}")
                    variant = "error"
                elif local_warnings:
                    status.setText(f"{local_warnings} 项提醒")
                    variant = "warning"
                elif nodes:
                    input_scope = str(
                        plan.get("input_scope", "fixed") or "fixed"
                    )
                    status.setText(
                        "每次填写" if input_scope == "floating" else "长期复用"
                    )
                    variant = "neutral"
                else:
                    status.setText("无节点")
                    variant = "neutral"
                self._style_timeline_status_label(status, variant)

        nav = self._section_nav_cards.get("timeline")
        if nav is not None:
            segment_count = len(visible)
            blocking = missing_total + error_total
            if blocking:
                nav.set_subtitle(f"{segment_count} 段时间 · {blocking} 项待处理")
                nav.set_badge(f"缺 {blocking}", "error")
            elif warning_total:
                nav.set_subtitle(f"{segment_count} 段时间 · {warning_total} 项提醒")
                nav.set_badge(f"{segment_count} 段", "warning")
            elif segment_count:
                nav.set_subtitle(f"{segment_count} 段时间 · {node_total} 个节点")
                nav.set_badge(f"{segment_count} 段", "success")
            else:
                nav.set_subtitle("按需新增时间段")
                nav.set_badge("0 段", "neutral")

    def _sync_timeline_navigation(self) -> None:
        nav = self._section_nav_cards.get("timeline")
        if nav is None:
            return
        nav.setVisible(True)
        refresh_layout_chain(self._section_nav, passes=2)

    def _timeline_summary_items(self) -> list[SummaryGridItem]:
        return []

    def _timeline_output_field_keys(self) -> set[str]:
        fields: set[str] = set()
        for plan in normalize_timeline_plans(
            self._selected_profile().timeline_plans
        ).values():
            if bool(plan.get("deleted", False)):
                continue
            for node in self._active_segment_nodes(plan):
                for output in list(node.get("outputs", []) or []):
                    field = self._clean_timeline_field_key(
                        dict(output).get("field", "")
                    )
                    if field:
                        fields.add(field)
        return fields

    def _open_timeline_from_fields(self) -> None:
        """Compatibility route retained for older repair intents."""

        self._section_nav.select_card("timeline")

    def _open_timeline_for_field(self, field_key: str) -> None:
        if field_key not in self._timeline_output_field_keys():
            return
        self._section_nav.select_card("timeline")
        for plan_id, plan in self._active_timeline_segment_items():
            for node in self._active_segment_nodes(plan):
                output_fields = {
                    self._clean_timeline_field_key(dict(output).get("field", ""))
                    for output in list(node.get("outputs", []) or [])
                }
                if field_key not in output_fields:
                    continue
                row = self._timeline_node_rows.get(
                    (plan_id, str(node.get("node_id", "")))
                )
                if row is not None:
                    self._detail_scroll.ensureWidgetVisible(row, 0, 24)
                return

    @staticmethod
    def _set_line_text(edit: QLineEdit, value: object) -> None:
        text = str(value or "")
        if edit.text() == text:
            return
        blocked = edit.blockSignals(True)
        edit.setText(text)
        edit.blockSignals(blocked)

    @staticmethod
    def _ratio_percent_text(node: dict[str, object]) -> str:
        rule = dict(node.get("rule", {}) or {})
        if str(rule.get("operation", "ratio") or "ratio") != "ratio":
            return ""
        try:
            return _display_decimal_text(
                Decimal(str(rule.get("value", "0") or "0")) * 100
            )
        except InvalidOperation:
            return str(rule.get("value", "") or "")

    @staticmethod
    def _style_timeline_segment_row(row: QWidget) -> None:
        theme = get_theme()
        row.setStyleSheet(
            f"""
            QFrame#timeline_segment_row {{
                background: transparent;
                border: none;
                border-bottom: 1px solid {theme.divider};
            }}
            """
        )

    @staticmethod
    def _style_timeline_status_label(label: QLabel, variant: str) -> None:
        theme = get_theme()
        palette = {
            "error": (theme.error_bg, theme.error),
            "warning": (theme.warning_bg, theme.warning),
            "success": (theme.success_bg, theme.success),
            "neutral": (theme.bg_hover, theme.text_secondary),
        }
        background, color = palette.get(variant, palette["neutral"])
        label.setStyleSheet(
            f"background: {background}; color: {color}; border-radius: {theme.radius_sm}px; "
            f"padding: 2px 8px; font-size: {max(11, theme.font_size_sm - 1)}px; font-weight: {theme.font_weight_emphasis};"
        )

    def _apply_timeline_theme(self) -> None:
        if not hasattr(self, "_timeline_card"):
            return
        theme = get_theme()
        control_height = resolved_control_height(theme, "md")
        self._timeline_add_segment_btn.setStyleSheet(build_button_stylesheet(theme))
        for plan_id, row in self._timeline_segment_rows.items():
            self._style_timeline_segment_row(row)
            self._timeline_segment_titles[plan_id].setStyleSheet(
                f"font-size: {theme.font_size_lg}px; font-weight: 700; color: {theme.text_primary};"
            )
            self._timeline_segment_ranges[plan_id].setStyleSheet(
                f"font-size: {theme.font_size_lg}px; font-weight: 700; "
                f"color: {theme.text_primary};"
            )
            for edit in (
                self._timeline_start_edits[plan_id],
                self._timeline_end_edits[plan_id],
            ):
                edit.setStyleSheet(
                    build_text_input_stylesheet(theme, min_height=control_height)
                )
            for control in (
                self._timeline_node_count_spins[plan_id],
                self._timeline_weekend_combos[plan_id],
                self._timeline_date_format_combos[plan_id],
                self._timeline_input_scope_combos[plan_id],
            ):
                set_outer_height = getattr(control, "set_outer_height", None)
                if callable(set_outer_height):
                    set_outer_height(control_height)
            apply_compact_row_action(
                self._timeline_segment_collapse_buttons[plan_id],
                icon_name="chevron-down",
                tooltip="折叠本段",
                variant="ghost",
            )
            apply_compact_row_action(
                self._timeline_segment_copy_buttons[plan_id],
                icon_name="plus",
                tooltip="复制整段",
                variant="ghost-primary",
            )
            apply_compact_row_action(
                self._timeline_segment_remove_buttons[plan_id],
                icon_name="trash-2",
                tooltip="删除整段",
                variant="ghost-danger",
            )
            self._timeline_segment_reset_buttons[plan_id].setStyleSheet(
                build_button_stylesheet(theme)
            )
        for key, token_edit in self._timeline_node_token_edits.items():
            ratio = self._timeline_node_ratio_edits[key]
            ratio.setStyleSheet(
                build_text_input_stylesheet(theme, min_height=control_height)
            )
        for plan_id, plan in self._active_timeline_segment_items():
            guide = self._timeline_node_column_guides.get(plan_id)
            if guide is not None:
                self._apply_timeline_node_column_metrics(plan_id, guide.metrics())
            nodes = self._active_segment_nodes(plan)
            for index, node in enumerate(nodes):
                key = (plan_id, str(node.get("node_id", "")))
                row = self._timeline_node_rows.get(key)
                if row is not None:
                    apply_token_row_style(
                        row,
                        object_name="timeline_node_row",
                        is_last=index == len(nodes) - 1,
                    )
        self._sync_timeline_status()


def _decimal_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return "0" if text in {"", "-0"} else text


def _display_decimal_text(value: Decimal) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


__all__ = ["TimelinePresenterMixin", "TimelineTokenEdit"]
