"""Compact current-document scope status and on-demand review UI."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QThread

from src.config.document_scope import (
    coerce_document_scope_policy,
    document_scope_role_label,
    selectable_document_scope_roles,
)
from src.qt_api import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
    QObject,
    Signal,
)
from src.services.document_structure_evidence import (
    DocumentStructureEvidence,
    ParagraphAnchor,
    RegionDecision,
    build_document_structure_evidence,
    read_document_paragraph_anchors,
)
from src.shared.ui.base_dialog import BaseDialog
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme


class DocumentScopeStatusRow(QWidget):
    review_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._label = QLabel("文档范围", self)
        self._status = QLabel("", self)
        self._status.setObjectName("wb_document_scope_status")
        self._review = QPushButton("检查", self)
        apply_button_variant(self._review, "secondary")
        self._review.clicked.connect(self.review_requested.emit)
        layout.addWidget(self._label)
        layout.addWidget(self._status)
        layout.addStretch(1)
        layout.addWidget(self._review)
        self.set_state("idle")
        bind_theme(self, self._apply_theme)
        self._apply_theme()

    def set_state(self, state: str, *, count: int = 0) -> None:
        normalized = str(state or "").strip()
        if normalized == "scanning":
            text = "识别中"
        elif normalized == "ready":
            text = f"已识别 {max(0, int(count))} 个区域"
        elif normalized == "review":
            text = f"{max(0, int(count))} 项待确认"
        elif normalized == "failed":
            text = "无法确认"
        else:
            text = ""
        self._status.setText(text)
        self._review.setVisible(normalized in {"ready", "review", "failed"})
        self.setVisible(bool(text))

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._label.setStyleSheet(
            f"color:{theme.text_primary};font-weight:{theme.font_weight_emphasis};"
        )
        self._status.setStyleSheet(f"color:{theme.text_secondary};")


class DocumentStructureScanWorker(QObject):
    finished = Signal(str, object)

    def __init__(self, request_id: str, source_path: str) -> None:
        super().__init__()
        self._request_id = request_id
        self._source_path = source_path

    def run(self) -> None:
        self.finished.emit(
            self._request_id,
            build_document_structure_evidence(self._source_path),
        )


class DocumentStructureScanHandle(QObject):
    finished = Signal(str, object)

    def __init__(self, request_id: str, source_path: str, parent=None) -> None:
        super().__init__(parent)
        self._thread = QThread(self)
        self._worker = DocumentStructureScanWorker(request_id, source_path)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self.finished.emit)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self.deleteLater)

    def start(self) -> None:
        self._thread.start()

    def shutdown(self, timeout_ms: int = 1000) -> bool:
        thread = getattr(self, "_thread", None)
        if thread is None:
            return True
        try:
            if not thread.isRunning():
                return True
            thread.requestInterruption()
            thread.quit()
            thread.wait(max(0, int(timeout_ms)))
            return not thread.isRunning()
        except RuntimeError:
            return True


@dataclass(slots=True)
class _ReviewRow:
    role_id: str
    status: str
    original_anchor: ParagraphAnchor | None
    action: StyledComboBox
    start: StyledComboBox
    synthetic: bool = False


class DocumentScopeReviewDialog(BaseDialog):
    def __init__(
        self,
        evidence: DocumentStructureEvidence,
        *,
        source_path: str,
        policy,
        mode_id: str,
        existing_decisions: tuple[RegionDecision, ...] = (),
        parent=None,
    ) -> None:
        super().__init__(
            title="确认文档范围",
            icon_style="info",
            parent=parent,
        )
        self._evidence = evidence
        self._policy = coerce_document_scope_policy(policy)
        self._mode_id = str(mode_id or "").strip() or "custom"
        self._anchors = read_document_paragraph_anchors(source_path)
        self._existing = {
            decision.role_id: decision for decision in existing_decisions
        }
        self._rows: list[_ReviewRow] = []
        if evidence.issues:
            self.add_message(
                "无法读取当前文档的结构。请确认文件是完整、可打开的 .docx，"
                "然后重新选择文档。"
            )
            close = self.add_primary_button("关闭")
            close.clicked.connect(self.reject)
            return

        self._grid_widget = QWidget(self)
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(10)
        self._grid.setVerticalSpacing(8)
        for column, label in enumerate(("区域", "起点", "状态", "操作")):
            self._grid.addWidget(QLabel(label, self._grid_widget), 0, column)
        self.content_layout.addWidget(self._grid_widget)

        for region in evidence.regions:
            self._append_region_row(
                role_id=region.role_id,
                anchor=region.start_anchor,
                status=(
                    "待确认"
                    if region.detection_status == "review"
                    else "已识别"
                ),
            )

        self._build_add_row()
        cancel = self.add_secondary_button("取消")
        confirm = self.add_primary_button("确认范围")
        cancel.clicked.connect(self.reject)
        confirm.clicked.connect(self.accept)

    def decisions(self) -> tuple[RegionDecision, ...]:
        review_roles = {item.role_id for item in self._evidence.review_items}
        decisions: list[RegionDecision] = []
        for row in self._rows:
            action = str(row.action.currentData() or "accept")
            if action == "exclude":
                decisions.append(RegionDecision(row.role_id, "exclude"))
            elif action == "set_start" or row.synthetic:
                anchor = row.start.currentData()
                if isinstance(anchor, ParagraphAnchor):
                    decisions.append(
                        RegionDecision(row.role_id, "set_start", anchor)
                    )
            elif row.role_id in review_roles:
                decisions.append(RegionDecision(row.role_id, "accept"))
        return tuple(decisions)

    def _append_region_row(
        self,
        *,
        role_id: str,
        anchor: ParagraphAnchor | None,
        status: str,
        synthetic: bool = False,
    ) -> None:
        row_index = self._grid.rowCount()
        role_label = QLabel(document_scope_role_label(role_id), self._grid_widget)
        start = self._anchor_combo(anchor)
        status_label = QLabel(status, self._grid_widget)
        action = StyledComboBox(self._grid_widget)
        if not synthetic:
            action.addItem("接受", "accept")
        action.addItem("调整", "set_start")
        action.addItem("排除", "exclude")
        existing = self._existing.get(role_id)
        if existing is not None:
            index = action.findData(existing.action)
            if index >= 0:
                action.setCurrentIndex(index)
            if existing.start_anchor is not None:
                self._set_anchor_combo(start, existing.start_anchor)
        elif synthetic:
            action.setCurrentIndex(action.findData("set_start"))
        action.currentIndexChanged.connect(
            lambda _index, combo=action, anchor_combo=start: anchor_combo.setEnabled(
                str(combo.currentData() or "") == "set_start"
            )
        )
        start.setEnabled(str(action.currentData() or "") == "set_start")
        self._grid.addWidget(role_label, row_index, 0)
        self._grid.addWidget(start, row_index, 1)
        self._grid.addWidget(status_label, row_index, 2)
        self._grid.addWidget(action, row_index, 3)
        self._rows.append(
            _ReviewRow(
                role_id=role_id,
                status=status,
                original_anchor=anchor,
                action=action,
                start=start,
                synthetic=synthetic,
            )
        )

    def _build_add_row(self) -> None:
        existing = {region.role_id for region in self._evidence.regions}
        candidates = [
            role_id
            for role_id in selectable_document_scope_roles(self._mode_id)
            if role_id not in existing
        ]
        if not candidates or not self._anchors:
            return
        wrapper = QWidget(self)
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        role_combo = StyledComboBox(wrapper)
        for role_id in candidates:
            role_combo.addItem(document_scope_role_label(role_id), role_id)
        start_combo = self._anchor_combo(self._anchors[0])
        add_button = QPushButton("添加", wrapper)
        apply_button_variant(add_button, "secondary")

        def add_region() -> None:
            role_id = str(role_combo.currentData() or "")
            anchor = start_combo.currentData()
            if not role_id or not isinstance(anchor, ParagraphAnchor):
                return
            self._append_region_row(
                role_id=role_id,
                anchor=anchor,
                status="未识别",
                synthetic=True,
            )
            index = role_combo.currentIndex()
            role_combo.removeItem(index)
            if role_combo.count() == 0:
                wrapper.setVisible(False)

        add_button.clicked.connect(add_region)
        layout.addWidget(role_combo)
        layout.addWidget(start_combo, 1)
        layout.addWidget(add_button)
        self.content_layout.addWidget(wrapper)

    def _anchor_combo(
        self,
        selected: ParagraphAnchor | None,
    ) -> StyledComboBox:
        combo = StyledComboBox(self._grid_widget)
        for anchor in self._anchors:
            combo.addItem(anchor.preview_text, anchor)
        if selected is not None:
            self._set_anchor_combo(combo, selected)
        return combo

    @staticmethod
    def _set_anchor_combo(
        combo: StyledComboBox,
        selected: ParagraphAnchor,
    ) -> None:
        for index in range(combo.count()):
            candidate = combo.itemData(index)
            if (
                isinstance(candidate, ParagraphAnchor)
                and candidate.text_digest == selected.text_digest
                and candidate.occurrence == selected.occurrence
            ):
                combo.setCurrentIndex(index)
                return


__all__ = [
    "DocumentScopeReviewDialog",
    "DocumentScopeStatusRow",
    "DocumentStructureScanHandle",
]
