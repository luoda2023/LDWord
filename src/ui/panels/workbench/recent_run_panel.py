# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

from src.qt_api import (
    QDesktopServices,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QUrl,
    QVBoxLayout,
    QWidget,
)
from src.shared.ui.style_management_block import StyleManagementBlock
from src.shared.ui.style_receipt_slot_frame import StyleReceiptSlotFrame
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.panels.style_object_projection_builders import (
    build_execution_style_projection,
)
from src.shared.ui.icons.catalog import get_icon

from .state import ArtifactItemState, RecentRunState


class RecentRunPanel(QWidget):
    _STATUS_LABELS = {
        "idle": "未执行",
        "success": "已完成",
        "partial_success": "部分完成",
        "failed": "执行失败",
        "cancelled": "已取消",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("wb_recent_run")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(8)

        self._title_label = QLabel("最近结果")
        self._title_label.setObjectName("wb_recent_run_title")
        self._status_label = QLabel(self._STATUS_LABELS["idle"])
        self._status_label.setObjectName("wb_recent_run_status")
        self._summary = QLabel("暂无最近结果")
        self._summary.setWordWrap(True)
        self._style_receipt_slot = StyleReceiptSlotFrame(
            self,
            object_name_prefix="wb_recent_style_receipt",
        )
        self._style_receipt_row = self._style_receipt_slot.receipt_row
        self._style_review_block = StyleManagementBlock(
            self,
            title="样式回执",
            icon_name="type-outline",
            object_name_prefix="wb_recent_style_review",
            mode="execution_receipt_review",
            receipt_slot=self._style_receipt_slot,
        )
        self._style_review_block.setVisible(False)
        self._meta_label = QLabel("")
        self._meta_label.setObjectName("wb_recent_run_meta")
        self._meta_label.setWordWrap(True)
        self._artifact_header = QLabel("产物清单")
        self._artifact_header.setObjectName("wb_recent_artifact_header")
        self._artifact_list = QWidget(self)
        self._artifact_layout = QVBoxLayout(self._artifact_list)
        self._artifact_layout.setContentsMargins(0, 0, 0, 0)
        self._artifact_layout.setSpacing(4)
        self._artifact_group_headers: list[QLabel] = []
        self._artifact_rows: list[QWidget] = []

        self._layout.addWidget(self._title_label)
        self._layout.addWidget(self._status_label)
        self._layout.addWidget(self._summary)
        self._layout.addWidget(self._style_review_block)
        self._layout.addWidget(self._meta_label)
        self._layout.addWidget(self._artifact_header)
        self._layout.addWidget(self._artifact_list)
        self._artifact_header.setVisible(False)
        self._artifact_list.setVisible(False)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_summary(self, text: str) -> None:
        self._summary.setText(text)

    def set_state(self, state: RecentRunState) -> None:
        self._status_label.setText(
            self._STATUS_LABELS.get(state.status, self._STATUS_LABELS["idle"])
        )
        summary_text = state.summary
        style_projection = build_execution_style_projection(
            style_source_envelope=state.style_source_envelope,
            style_source_summary=state.style_source_summary,
        )
        self._style_review_block.apply_style_object_projection(style_projection)
        self._sync_style_review_block_visible()
        if state.object_preflight_summary:
            summary_text = f"{summary_text}\n{state.object_preflight_summary}"
            if state.object_preflight_details:
                summary_text = (
                    f"{summary_text}\n"
                    + "\n".join(f"- {line}" for line in state.object_preflight_details)
                )
        if state.material_field_consistency_summary:
            summary_text = f"{summary_text}\n{state.material_field_consistency_summary}"
        if state.batch_isolation_summary:
            summary_text = f"{summary_text}\n{state.batch_isolation_summary}"
            if state.batch_isolation_details:
                summary_text = (
                    f"{summary_text}\n"
                    + "\n".join(f"- {line}" for line in state.batch_isolation_details)
                )
        if state.diagnostics_summary:
            summary_text = f"{summary_text}\n{state.diagnostics_summary}"
        self.set_summary(summary_text)
        meta_parts = []
        if state.output_label:
            meta_parts.append(f"输出: {state.output_label}")
        if state.compare_label:
            meta_parts.append(f"对比: {state.compare_label}")
        if state.report_label:
            meta_parts.append(f"报告: {state.report_label}")
        if state.intermediate_label:
            meta_parts.append(f"中间产物: {state.intermediate_label}")
        if state.material_manifest_label:
            meta_parts.append(f"资料清单: {state.material_manifest_label}")
        if state.material_package_label:
            meta_parts.append(f"资料包: {state.material_package_label}")
        if state.scene_sample_manifest_label:
            meta_parts.append(f"样本库: {state.scene_sample_manifest_label}")
        if state.artifact_label:
            meta_parts.append(f"产物清单: {state.artifact_label}")
        if state.error_summary:
            meta_parts.append(f"错误: {state.error_summary}")
        self._meta_label.setText(" | ".join(meta_parts))
        self._set_artifact_items(list(state.artifact_items or []))

    def _sync_style_review_block_visible(self) -> None:
        self._style_review_block.setVisible(
            self._style_receipt_slot.has_receipt()
        )
        self._style_review_block.updateGeometry()

    def _set_artifact_items(self, items: list[ArtifactItemState]) -> None:
        self._clear_artifact_rows()
        expanded_items = _expand_scene_sample_manifest_items(items)
        has_items = bool(expanded_items)
        self._artifact_header.setVisible(has_items)
        self._artifact_list.setVisible(has_items)
        for group_label, group_items in _group_artifact_items(expanded_items):
            group_header = QLabel(group_label, self._artifact_list)
            group_header.setObjectName("wb_recent_artifact_group")
            self._artifact_group_headers.append(group_header)
            self._artifact_layout.addWidget(group_header)
            for item in group_items:
                row = self._build_artifact_row(item)
                self._artifact_rows.append(row)
                self._artifact_layout.addWidget(row)

    def _clear_artifact_rows(self) -> None:
        while self._artifact_layout.count():
            layout_item = self._artifact_layout.takeAt(0)
            widget = layout_item.widget()
            if widget is not None:
                widget.deleteLater()
        self._artifact_group_headers.clear()
        self._artifact_rows.clear()

    def _build_artifact_row(self, item: ArtifactItemState) -> QWidget:
        row = QWidget(self._artifact_list)
        row.setObjectName("wb_recent_artifact_row")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        kind_label = QLabel(_artifact_kind_label(item.kind), row)
        kind_label.setObjectName("wb_recent_artifact_kind")
        kind_label.setFixedWidth(56)
        layout.addWidget(kind_label)

        status_label = QLabel(_artifact_status_label(item.status), row)
        status_label.setObjectName("wb_recent_artifact_status")
        status_label.setFixedWidth(42)
        layout.addWidget(status_label)

        path_label = QLabel(_artifact_path_text(item), row)
        path_label.setObjectName("wb_recent_artifact_path")
        path_label.setToolTip(item.detail or item.path)
        path_label.setWordWrap(True)
        path_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(path_label, 1)

        open_btn = _artifact_tool_button(
            row,
            icon_name="file-text",
            tooltip="打开文件",
        )
        open_btn.setEnabled(bool(item.path and Path(item.path).exists()))
        open_btn.clicked.connect(
            lambda *_args, path=item.path, fragment=item.fragment: _open_artifact_file(
                path,
                fragment=fragment,
            )
        )
        layout.addWidget(open_btn)

        folder_btn = _artifact_tool_button(
            row,
            icon_name="folder-open",
            tooltip="打开所在目录",
        )
        folder_btn.setEnabled(_nearest_existing_artifact_parent(item.path) is not None)
        folder_btn.clicked.connect(
            lambda *_args, path=item.path: _open_artifact_parent(path)
        )
        layout.addWidget(folder_btn)

        row._artifact_item = item
        row._kind_label = kind_label
        row._status_label = status_label
        row._path_label = path_label
        row._open_btn = open_btn
        row._folder_btn = folder_btn
        self._style_artifact_row(row)
        return row

    def _apply_theme(self) -> None:
        if not hasattr(self, "_status_label"):
            return
        t = get_theme()
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(8)
        self.setStyleSheet(
            f"QWidget#wb_recent_run {{ background: {t.bg_sidebar}; "
            f"border: 1px solid {t.border_light}; "
            f"border-radius: {t.radius_md}px; }}"
        )
        self._title_label.setStyleSheet(
            f"font-size: {t.font_size_lg}px; font-weight: {t.font_weight_bold}; "
            f"color: {t.text_primary}; background: transparent;"
        )
        self._status_label.setStyleSheet(
            f"font-size: {t.font_size_md}px; font-weight: {t.font_weight_emphasis}; color: {t.primary};"
        )
        self._summary.setStyleSheet(
            f"font-size: {t.font_size_md}px; color: {t.text_primary}; background: transparent;"
        )
        self._meta_label.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_secondary}; background: transparent;"
        )
        self._artifact_header.setStyleSheet(
            f"font-size: {t.font_size_sm}px; font-weight: {t.font_weight_emphasis}; color: {t.text_secondary};"
        )
        for group_header in list(self._artifact_group_headers):
            group_header.setStyleSheet(
                f"font-size: {t.font_size_sm}px; font-weight: {t.font_weight_emphasis}; color: {t.text_secondary};"
            )
        for row in list(self._artifact_rows):
            self._style_artifact_row(row)

    def _style_artifact_row(self, row: QWidget) -> None:
        t = get_theme()
        row.setStyleSheet(
            f"QWidget#wb_recent_artifact_row {{ background: {t.bg_hover}; border-radius: {t.radius_sm}px; }}"
            f"QLabel#wb_recent_artifact_kind {{ color: {t.text_secondary}; font-size: {t.font_size_sm}px; }}"
            f"QLabel#wb_recent_artifact_status {{ color: {t.text_hint}; font-size: {t.font_size_sm}px; }}"
            f"QLabel#wb_recent_artifact_path {{ color: {t.text_primary}; font-size: {t.font_size_sm}px; }}"
            f"QToolButton {{ border: none; padding: 2px; border-radius: {t.radius_xs}px; }}"
            f"QToolButton:hover {{ background: {t.bg_selected}; }}"
            f"QToolButton:disabled {{ color: {t.text_disabled}; }}"
        )
        for button, icon_name in (
            (getattr(row, "_open_btn", None), "file-text"),
            (getattr(row, "_folder_btn", None), "folder-open"),
        ):
            if button is not None:
                button.setIcon(get_icon(icon_name, 14, t.icon_primary))


def _artifact_tool_button(parent: QWidget, *, icon_name: str, tooltip: str) -> QToolButton:
    button = QToolButton(parent)
    button.setAutoRaise(True)
    button.setFixedSize(24, 24)
    button.setToolTip(tooltip)
    button.setIcon(get_icon(icon_name, 14, get_theme().icon_primary))
    return button


def _group_artifact_items(
    items: list[ArtifactItemState],
) -> list[tuple[str, list[ArtifactItemState]]]:
    groups: list[tuple[str, list[ArtifactItemState]]] = []
    index_by_id: dict[str, int] = {}
    for item in items:
        group_id = str(item.group_id or item.label or item.kind or "artifacts")
        group_label = str(item.group_label or group_id or "产物")
        if group_id not in index_by_id:
            index_by_id[group_id] = len(groups)
            groups.append((_artifact_group_title(group_id, group_label), []))
        groups[index_by_id[group_id]][1].append(item)
    return groups


def _expand_scene_sample_manifest_items(
    items: list[ArtifactItemState],
) -> list[ArtifactItemState]:
    expanded: list[ArtifactItemState] = []
    for item in items:
        expanded.append(item)
        if item.kind == "scene_sample_manifest":
            expanded.extend(_scene_sample_manifest_child_items(item))
    return expanded


def _scene_sample_manifest_child_items(item: ArtifactItemState) -> list[ArtifactItemState]:
    manifest_path = Path(str(item.path or ""))
    if not manifest_path.exists() or not manifest_path.is_file():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(manifest, dict):
        return []

    group_id = item.group_id or "scene_samples"
    group_label = item.group_label or "样本库"
    artifact_items, fixture_path_by_id = _scene_sample_fixture_artifact_items(
        manifest,
        manifest_path=manifest_path,
        group_id=group_id,
        group_label=group_label,
    )
    request_items = _scene_request_cell_artifact_items(
        manifest,
        fixture_path_by_id=fixture_path_by_id,
        group_id=group_id,
        group_label=group_label,
    )
    return [*artifact_items, *request_items]


def _scene_sample_fixture_artifact_items(
    manifest: dict[str, object],
    *,
    manifest_path: Path,
    group_id: str,
    group_label: str,
) -> tuple[list[ArtifactItemState], dict[str, str]]:
    items: list[ArtifactItemState] = []
    fixture_path_by_id: dict[str, str] = {}
    output_dir = Path(str(manifest.get("output_dir") or manifest_path.parent))
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return items, fixture_path_by_id
    for raw_artifact in artifacts:
        if not isinstance(raw_artifact, dict):
            continue
        fixture_id = str(raw_artifact.get("fixture_id") or "").strip()
        if not fixture_id:
            continue
        path_text = str(raw_artifact.get("path") or "").strip()
        if not path_text:
            path_text = str(output_dir / f"{fixture_id}.docx")
        fixture_path_by_id[fixture_id] = path_text
        path = Path(path_text)
        items.append(
            ArtifactItemState(
                kind="scene_sample_fixture",
                label=fixture_id,
                group_id=group_id,
                group_label=group_label,
                path=path_text,
                status="available" if path.exists() else "missing",
                detail=_scene_sample_fixture_detail(raw_artifact),
            )
        )
    return items, fixture_path_by_id


def _scene_request_cell_artifact_items(
    manifest: dict[str, object],
    *,
    fixture_path_by_id: dict[str, str],
    group_id: str,
    group_label: str,
) -> list[ArtifactItemState]:
    items: list[ArtifactItemState] = []
    request_cells = manifest.get("request_cells")
    if not isinstance(request_cells, list):
        return items
    default_report_path = str(manifest.get("request_cell_report_path") or "").strip()
    for raw_cell in request_cells:
        if not isinstance(raw_cell, dict):
            continue
        sample_id = str(raw_cell.get("sample_id") or "").strip()
        if not sample_id:
            continue
        fixture_ids = [
            str(fixture_id or "").strip()
            for fixture_id in list(raw_cell.get("fixture_ids") or [])
            if str(fixture_id or "").strip()
        ]
        path_text = ""
        for fixture_id in fixture_ids:
            path_text = fixture_path_by_id.get(fixture_id, "")
            if path_text:
                break
        fixture_path_text = path_text
        report_path_text = str(raw_cell.get("report_path") or "").strip()
        report_anchor = str(raw_cell.get("report_anchor") or "").strip()
        if not report_path_text:
            report_path_text = default_report_path
        fragment = report_anchor if report_path_text else ""
        if report_path_text:
            path_text = report_path_text
            status = "available" if Path(path_text).exists() else "missing"
        elif fixture_path_text:
            path_text = fixture_path_text
            status = "available" if Path(path_text).exists() else "missing"
        else:
            status = "boundary"
        items.append(
            ArtifactItemState(
                kind="scene_request_cell",
                label=sample_id,
                group_id=group_id,
                group_label=group_label,
                path=path_text,
                fragment=fragment,
                status=status,
                detail=_scene_request_cell_detail(
                    raw_cell,
                    fixture_path=fixture_path_text,
                    report_path=report_path_text,
                ),
            )
        )
    return items


def _scene_sample_fixture_detail(artifact: dict[str, object]) -> str:
    parts = [
        f"pack={_clean_text(artifact.get('pack_id'))}",
        "OOXML=" + _join_values(artifact.get("docx_surfaces")),
        "findings=" + _join_values(artifact.get("expected_preflight_findings")),
    ]
    manual_gate = _clean_text(artifact.get("manual_gate_id"))
    if manual_gate:
        parts.append(f"manual_gate={manual_gate}")
    return " | ".join(part for part in parts if part and not part.endswith("=-"))


def _scene_request_cell_detail(
    cell: dict[str, object],
    *,
    fixture_path: str = "",
    report_path: str = "",
) -> str:
    parts = [
        f"request={_clean_text(cell.get('request_text'))}",
        f"coverage={_clean_text(cell.get('coverage_level'))}",
        "fixture=" + _join_values(cell.get("fixture_ids")),
        f"fixture_path={_clean_text(fixture_path) or '-'}",
        f"report={_clean_text(report_path) or '-'}",
        f"anchor={_clean_text(cell.get('report_anchor')) or '-'}",
        "manual_gate=" + _join_values(cell.get("manual_gate_ids")),
        "boundary=" + _join_values(cell.get("boundary_notes")),
    ]
    return " | ".join(part for part in parts if part and not part.endswith("=-"))


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _join_values(values: object) -> str:
    if isinstance(values, (list, tuple)):
        normalized = [
            str(value or "").strip()
            for value in values
            if str(value or "").strip()
        ]
        return " / ".join(normalized) if normalized else "-"
    text = str(values or "").strip()
    return text or "-"


def _artifact_path_text(item: ArtifactItemState) -> str:
    label = str(item.label or "").strip()
    path = str(item.path or "").strip()
    fragment = str(item.fragment or "").strip()
    if path and fragment:
        path = f"{path}#{fragment}"
    if label and path:
        return f"{label}: {path}"
    return path or label or "-"


def _artifact_kind_label(kind: str) -> str:
    return {
        "output": "输出",
        "planned_output": "计划",
        "compare": "对比",
        "report": "报告",
        "intermediate": "中间",
        "material_manifest": "清单",
        "material_package": "资料包",
        "scene_sample_manifest": "样本",
        "material_package_report": "资料包报告",
        "question_figure_repair_queue": "题图修复候选",
        "question_figure_batch_apply_transaction_manifest": "题图事务台账",
        "question_figure_batch_apply_transaction_report": "题图事务报告",
        "question_figure_batch_apply_transaction_task_summary": "题图事务任务",
        "scene_sample_fixture": "DOCX",
        "scene_request_cell": "请求",
    }.get(str(kind or ""), "产物")


def _artifact_group_title(group_id: str, group_label: str) -> str:
    normalized = str(group_id or "").strip()
    label = str(group_label or normalized or "产物").strip()
    if normalized == "scene_samples":
        return label or "样本库"
    return f"交付 {label}"


def _artifact_status_label(status: str) -> str:
    return {
        "available": "就绪",
        "planned": "计划",
        "warning": "预警",
        "missing": "缺失",
        "boundary": "边界",
    }.get(str(status or ""), "就绪")


def _open_artifact_file(path_text: str, *, fragment: str = "") -> bool:
    path = Path(str(path_text or ""))
    if not path.exists():
        return False
    url = QUrl.fromLocalFile(str(path))
    normalized_fragment = str(fragment or "").strip()
    if normalized_fragment:
        url.setFragment(normalized_fragment)
    return bool(QDesktopServices.openUrl(url))


def _open_artifact_parent(path_text: str) -> bool:
    parent = _nearest_existing_artifact_parent(path_text)
    if parent is None:
        return False
    return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(parent))))


def _nearest_existing_artifact_parent(path_text: str) -> Path | None:
    text = str(path_text or "").strip()
    if not text:
        return None
    path = Path(text)
    current = path if path.is_dir() else path.parent
    while True:
        if current.exists():
            return current
        if current.parent == current:
            return None
        current = current.parent
