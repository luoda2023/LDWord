"""Shared UI foundation for scene detail panes."""

from __future__ import annotations

from src.qt_api import QLabel, QSizePolicy, QVBoxLayout, QWidget, Signal
from src.shared.ui.card import Card
from src.shared.ui.navigation_highlight import NavigationHighlighter
from src.shared.ui.summary_grid import SummaryGrid, SummaryGridItem
from src.shared.ui.template_form_layout import TemplateFormStack
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.adapters.field_display_names import field_display_context, field_display_name

_SCENE_DETAIL_SUMMARY_COPY: dict[str, dict[str, str]] = {
    "风险检查": {
        "main_value": "执行前检查",
        "main_detail": "配置 Markdown 修复、对象预检、报告粒度和高风险处理。",
        "risk_value": "高风险先提醒",
        "risk_detail": "宏、嵌入对象、修订等会按策略提醒、跳过或阻断。",
    },
    "模板 Token 校验": {
        "main_value": "Token 存在性校验",
        "main_detail": "逐项核对模板 Token 是否存在于当前资料包，并查看填写内容。",
        "risk_value": "不一致会影响生成",
        "risk_detail": "模板有而资料包缺少、或资料包要求但模板缺少时会集中提示。",
    },
    "生成结果": {
        "main_value": "交付版本",
        "main_detail": "配置最终稿、对比稿、报告、资料清单和命名规则。",
        "risk_value": "输出路径需确认",
        "risk_detail": "路径冲突、目录不可写或命名过长会在执行前提示。",
    },
}


def _scene_detail_summary_items(
    title: str,
    description: str,
) -> tuple[SummaryGridItem, ...]:
    copy = _SCENE_DETAIL_SUMMARY_COPY.get(title, {})
    return (
        SummaryGridItem(
            key="main_controls",
            label="主要控件",
            value=copy.get("main_value", "下方编辑"),
            detail=copy.get("main_detail", description),
            variant="info",
        ),
        SummaryGridItem(
            key="risk_note",
            label="风险说明",
            value=copy.get("risk_value", "有风险会提醒"),
            detail=copy.get(
                "risk_detail",
                "阻断、跳过或人工确认会在风险检查和执行报告里说明。",
            ),
            variant="warning",
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
#  Detail panes
# ═══════════════════════════════════════════════════════════════════════


class _SimpleFormDetail(QWidget):
    """Generic form-based detail pane for feature-specific config cards."""

    scene_edited = Signal()

    def __init__(self, title: str, icon_name: str, description: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._icon_name = icon_name
        self._is_syncing = False
        self._navigation_highlighter = NavigationHighlighter()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._card = Card(parent=self)
        self._card.set_header(title, icon_name=icon_name)

        self._desc_label = QLabel(description)
        self._desc_label.setObjectName("scn_form_desc")
        self._desc_label.setWordWrap(True)
        self._card.add_widget(self._desc_label)

        self._detail_summary = SummaryGrid(columns=2, parent=self._card)
        self._detail_summary.set_items(_scene_detail_summary_items(title, description))
        self._card.add_widget(self._detail_summary)

        layout.addWidget(self._card)
        layout.addStretch(1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        t = get_theme()
        if self.layout() is not None:
            self.layout().setSpacing(t.template_detail_section_gap)
        self._desc_label.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
        )

    def _add_form_stack(self, rows: list[QWidget]) -> None:
        self._card.add_widget(TemplateFormStack(rows, parent=self._card))

    def _highlight_navigation_widget(self, widget: QWidget, label: str) -> None:
        self._navigation_highlighter.highlight(
            widget,
            label,
            display_label=(
                field_display_context(label).label_with_group()
                or field_display_name(label)
            ),
        )
