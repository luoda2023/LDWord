# -*- coding: utf-8 -*-
"""左侧「工程范本库」一级面板。

从 LDWord 工程范本参考清单（用户级 manifest，指向 H:\\AI-model 等工程
范本语料）按六大工程阶段浏览范本，双击任一范本即“像打开 Word 文件一样”
在「MarkText 文档」面板中打开 Markdown 范本并继续编辑。

面板自身只负责“浏览与选择”：真正的打开交给 MarkTextPanel，通过
bridge.navigate_to_intent 携带 open_path 跨面板跳转。
"""
from __future__ import annotations

from pathlib import Path

from src.config.engineering_reference import (
    EngineeringReferenceSample,
    engineering_stage_label,
    list_engineering_reference_samples,
)
from src.qt_api import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.typography_policy import TextRole, apply_text_role
from src.ui.base_panel import BasePanel

_STAGES = (
    "decision",
    "design",
    "transaction",
    "implementation",
    "completion",
    "throughout",
)
_STAGE_HINTS = {
    "decision": "决策 · 立项 · 可研",
    "design": "设计 · 报批 · 方案",
    "transaction": "招投标 · 合同 · 造价",
    "implementation": "施工 · 组织设计 · 专项方案",
    "completion": "竣工 · 结算 · 审计",
    "throughout": "贯穿 · 定额 · 价格 · 概算",
}


class _StageButton(QPushButton):
    clicked_stage = Signal(str)

    def __init__(self, stage_id: str, title: str, hint: str, parent=None) -> None:
        super().__init__(parent)
        self.stage_id = stage_id
        self.setObjectName("engineering_stage_button")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._title = title
        self._hint = hint
        self.setText(f"{title}\n{hint}")
        self.clicked.connect(lambda: self.clicked_stage.emit(self.stage_id))

    def apply_theme(self, active: bool) -> None:
        theme = get_theme()
        background = theme.bg_selected if active else theme.bg_card
        border = theme.border_focus if active else theme.border_light
        color = theme.text_primary if active else theme.text_secondary
        self.setStyleSheet(
            f"""
            QPushButton#engineering_stage_button {{
                background: {background};
                border: 1px solid {border};
                border-radius: {theme.radius_md}px;
                padding: 10px 8px;
                text-align: left;
            }}
            QPushButton#engineering_stage_button:hover {{
                background: {theme.bg_hover};
            }}
            """
        )


class _SampleRow(QWidget):
    """一个范本卡片：标题 + 阶段/类型/提示 + 文件大小。"""

    selected = Signal(object)

    def __init__(self, sample: EngineeringReferenceSample, parent=None) -> None:
        super().__init__(parent)
        self.sample = sample
        self.setObjectName("engineering_sample_row")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 12, 10)
        layout.setSpacing(4)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        title = QLabel(sample.name or Path(sample.path).stem, self)
        title.setObjectName("engineering_sample_title")
        title.setWordWrap(True)
        apply_text_role(title, TextRole.NAVIGATION_TITLE_ACTIVE)
        top.addWidget(title, 1)
        kind = QLabel(sample.kind or "文档", self)
        kind.setObjectName("engineering_sample_kind")
        apply_text_role(kind, TextRole.MICRO)
        top.addWidget(kind, 0, Qt.AlignTop)
        layout.addLayout(top)
        if sample.note:
            note = QLabel(sample.note, self)
            note.setObjectName("engineering_sample_note")
            note.setWordWrap(True)
            note.setTextInteractionFlags(Qt.TextSelectableByMouse)
            apply_text_role(note, TextRole.CAPTION)
            layout.addWidget(note)
        meta = QLabel(_sample_meta(sample), self)
        meta.setObjectName("engineering_sample_meta")
        meta.setWordWrap(True)
        apply_text_role(meta, TextRole.MICRO)
        layout.addWidget(meta)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.selected.emit(self.sample)
        super().mouseReleaseEvent(event)


def _sample_meta(sample: EngineeringReferenceSample) -> str:
    path = Path(sample.path or "")
    parts = [engineering_stage_label(sample.stage)]
    if sample.available:
        try:
            size = path.stat().st_size
            parts.append(f"{size / 1024 / 1024:.1f} MB" if size > 1024 * 1024 else f"{size // 1024} KB")
        except OSError:
            pass
    else:
        parts.append("文件缺失")
    suffix = path.suffix.lstrip(".").upper()
    if suffix:
        parts.append(suffix)
    return " · ".join(parts)


class EngineeringLibraryPanel(BasePanel):
    """一级面板：工程范本库（按阶段浏览，双击打开到文档办公）。"""

    panel_title = "工程范本库"
    panel_icon = "book-open"

    def __init__(self, bridge, parent=None) -> None:
        self._samples: list[EngineeringReferenceSample] = []
        self._active_stage = ""
        super().__init__(bridge, parent)

    # ---- UI ----------------------------------------------------------------
    def _setup_ui(self) -> None:
        self.setObjectName("EngineeringLibraryPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame(self)
        header.setObjectName("engineering_header")
        header.setFixedHeight(54)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 8, 14, 8)
        title = QLabel("工程范本库", header)
        title.setObjectName("engineering_header_title")
        apply_text_role(title, TextRole.NAVIGATION_TITLE_ACTIVE)
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        self._count_label = QLabel("", header)
        self._count_label.setObjectName("engineering_count")
        apply_text_role(self._count_label, TextRole.CAPTION)
        header_layout.addWidget(self._count_label)
        root.addWidget(header)

        # 阶段选择区
        stage_title = QLabel("按工程阶段浏览范本", self)
        stage_title.setObjectName("engineering_section_label")
        stage_title.setContentsMargins(16, 6, 0, 2)
        apply_text_role(stage_title, TextRole.NAVIGATION_TITLE_ACTIVE)
        root.addWidget(stage_title)

        stage_host = QWidget(self)
        stage_layout = QHBoxLayout(stage_host)
        stage_layout.setContentsMargins(14, 0, 14, 8)
        stage_layout.setSpacing(8)
        self._stage_buttons: dict[str, _StageButton] = {}
        self._stage_group = QButtonGroup(self)
        self._stage_group.setExclusive(True)
        for stage_id in _STAGES:
            button = _StageButton(
                stage_id,
                engineering_stage_label(stage_id).split(" ", 1)[-1]
                if " " in engineering_stage_label(stage_id)
                else engineering_stage_label(stage_id),
                _STAGE_HINTS.get(stage_id, ""),
                stage_host,
            )
            button.clicked_stage.connect(self._on_stage_clicked)
            self._stage_group.addButton(button)
            self._stage_buttons[stage_id] = button
            stage_layout.addWidget(button)
        root.addWidget(stage_host)

        # 结果列表
        self._list_host = QScrollArea(self)
        self._list_host.setObjectName("engineering_list_scroll")
        self._list_host.setFrameShape(QFrame.NoFrame)
        self._list_host.setWidgetResizable(True)
        self._list_host.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list = QWidget(self._list_host)
        self._list_layout = QVBoxLayout(self._list)
        self._list_layout.setContentsMargins(14, 6, 14, 12)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch(1)
        self._list_host.setWidget(self._list)
        root.addWidget(self._list_host, 1)

        self._refresh_samples()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _connect_signals(self) -> None:
        return None

    # ---- data --------------------------------------------------------------
    def _refresh_samples(self) -> None:
        try:
            self._samples = list(list_engineering_reference_samples())
        except Exception:  # noqa: BLE001
            self._samples = []
        total = len(self._samples)
        self._count_label.setText(f"共 {total} 份范本")
        if not total:
            self._render_samples([])
            return
        first_stage = _STAGES[0]
        if self._active_stage not in _STAGES:
            self._active_stage = first_stage
        button = self._stage_buttons.get(self._active_stage)
        if button is not None:
            button.setChecked(True)
        self._render_samples(
            [s for s in self._samples if s.stage == self._active_stage]
        )

    def _on_stage_clicked(self, stage_id: str) -> None:
        self._active_stage = stage_id
        for sid, button in self._stage_buttons.items():
            button.apply_theme(sid == stage_id)
        self._render_samples(
            [s for s in self._samples if s.stage == stage_id]
        )

    def _render_samples(self, samples: list[EngineeringReferenceSample]) -> None:
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not samples:
            empty = QLabel(
                "该阶段暂无可用的工程范本。\n可先在 AI 文档助手的“工程参考”中补充范本清单。",
                self._list,
            )
            empty.setObjectName("engineering_empty")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignCenter)
            apply_text_role(empty, TextRole.BODY)
            self._list_layout.insertWidget(0, empty)
            return
        for sample in samples:
            row = _SampleRow(sample, self._list)
            row.selected.connect(self._open_sample)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
        self._list_layout.insertStretch(0, 0)

    # ---- open --------------------------------------------------------------
    def _open_sample(self, sample: EngineeringReferenceSample) -> None:
        if not sample.available:
            from src.shared.ui.dialogs import warning as show_warning

            show_warning(
                "范本文件缺失",
                f"该范本文件不存在：\n{sample.path}\n\n请确认文件仍位于原路径。",
                parent=self,
            )
            return
        # 跨面板跳转到 MarkText 文档工作区并携带路径打开。
        self.bridge.navigate_to_intent.emit(
            {
                "panel_id": "marktext",
                "payload": {
                    "open_path": str(Path(sample.path).expanduser().resolve()),
                    "library_sample_name": sample.name or "",
                },
            }
        )

    # ---- intent ------------------------------------------------------------
    def handle_navigation_intent(self, intent) -> None:
        from src.ui.bridge import navigation_intent_value

        payload = navigation_intent_value(intent, "payload", {})
        if isinstance(payload, dict):
            open_path = str(payload.get("open_path") or "")
            if open_path:
                self._open_path_from_library(open_path)

    def _open_path_from_library(self, path_text: str) -> None:
        """Ask the MarkText panel to open the file."""
        # EngineeringLibraryPanel only browses; MarkTextPanel owns editing.
        # Direct path intents are forwarded so the file opens there.
        self.bridge.navigate_to_intent.emit(
            {
                "panel_id": "marktext",
                "payload": {"open_path": path_text},
            }
        )

    # ---- theme -------------------------------------------------------------
    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QFrame#engineering_header {{
                background: {theme.bg_card};
                border-bottom: 1px solid {theme.divider};
            }}
            QLabel#engineering_header_title {{ color: {theme.text_primary}; background: transparent; }}
            QLabel#engineering_count {{ color: {theme.text_hint}; background: transparent; }}
            QLabel#engineering_section_label {{ color: {theme.text_primary}; background: transparent; }}
            QFrame#engineering_sample_row {{
                background: {theme.bg_card};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_md}px;
            }}
            QFrame#engineering_sample_row:hover {{
                border-color: {theme.border_focus};
                background: {theme.bg_hover};
            }}
            QLabel#engineering_sample_title {{ color: {theme.text_primary}; background: transparent; }}
            QLabel#engineering_sample_kind {{
                color: {theme.text_on_primary};
                background: {theme.primary};
                border-radius: {theme.radius_xs}px;
                padding: 2px 8px;
            }}
            QLabel#engineering_sample_note {{ color: {theme.text_secondary}; background: transparent; }}
            QLabel#engineering_sample_meta {{ color: {theme.text_hint}; background: transparent; }}
            QLabel#engineering_empty {{ color: {theme.text_hint}; background: transparent; }}
            QScrollArea#engineering_list_scroll {{ background: transparent; border: none; }}
            """
        )
        for stage_id, button in self._stage_buttons.items():
            button.apply_theme(stage_id == self._active_stage)


__all__ = ["EngineeringLibraryPanel"]
