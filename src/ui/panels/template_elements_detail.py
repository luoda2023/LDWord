"""Header/footer and TOC detail pane for template management."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from src.config.template import PageNumberPhaseConfig, TemplateConfig
from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSize,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.summary_grid import SummaryGrid, SummaryGridItem
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.panels.template_elements_header_footer import (
    HeaderFooterDetailSection,
    default_page_number_phases,
    default_suppress_header_footer_selectors,
    ensure_default_page_number_phases,
    page_number_phase_brief,
)
from src.ui.panels.template_elements_toc import (
    TOC_INSERT_OPTIONS,
    TOC_MODE_OPTIONS,
    TOC_STYLE_KEYS,
    TocDetailSection,
)


@dataclass(eq=True)
class _ElementsSnapshot:
    header_footer_config: object
    toc_config: object
    toc_styles: dict[str, object]

    @classmethod
    def from_template(cls, template: TemplateConfig) -> "_ElementsSnapshot":
        return cls(
            header_footer_config=deepcopy(template.header_footer),
            toc_config=deepcopy(template.toc),
            toc_styles={
                key: deepcopy(template.styles[key])
                for key in TOC_STYLE_KEYS
                if key in template.styles
            },
        )

def _option_label(options: tuple[tuple[str, str], ...], value, fallback: str = "") -> str:
    return dict(options).get(value, fallback or str(value or ""))


def _size_text(size_pt: float | None) -> str:
    if size_pt in (None, ""):
        return "默认字号"
    return f"{float(size_pt):g} 磅"


class ElementsDetail(QWidget):
    """Editable header/footer + TOC pane backed by TemplateConfig."""

    template_edited = Signal(object)
    save_requested = Signal()

    def __init__(self, *, scope: str = "all", parent=None):
        super().__init__(parent)
        self._scope = scope if scope in {"all", "header_footer", "toc"} else "all"
        self._current_template: TemplateConfig | None = None
        self._snapshot: _ElementsSnapshot | None = None
        self._header_icons: list[tuple[str, QLabel]] = []
        self._header_titles: list[QLabel] = []
        self._is_syncing = False
        self._save_enabled = False
        self._toc_style_controls: dict[str, dict[str, object]] = {}
        self._page_phase_rows = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._build_summary_card()
        layout.addWidget(self._summary_card)
        self._build_form()
        layout.addWidget(self._editor_column)
        layout.addStretch(1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _title_text(self) -> str:
        if self._scope == "header_footer":
            return "页眉与页脚"
        if self._scope == "toc":
            return "目录"
        return "页眉与目录"

    def _icon_name(self) -> str:
        return "scroll-text" if self._scope == "toc" else "panel-top"

    def _build_summary_card(self) -> None:
        self._summary_card = Card(parent=self)
        header = QWidget(self._summary_card)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 6)
        header_layout.setSpacing(6)

        self._header_icon = QLabel(header)
        self._header_icon.setFixedSize(18, 18)
        self._header_icons.append((self._icon_name(), self._header_icon))
        header_layout.addWidget(self._header_icon)

        title = QLabel(self._title_text(), header)
        title.setObjectName("tpl_card_title")
        self._header_titles.append(title)
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        self._restore_entry_btn = QPushButton("恢复", header)
        self._restore_entry_btn.setIconSize(QSize(16, 16))
        self._restore_entry_btn.clicked.connect(self._on_restore_entry)
        header_layout.addWidget(self._restore_entry_btn)

        self._save_btn = QPushButton("保存", header)
        self._save_btn.setIconSize(QSize(16, 16))
        self._save_btn.clicked.connect(self.save_requested.emit)
        header_layout.addWidget(self._save_btn)

        self._summary_card.add_widget(header)

        self._summary_grid = SummaryGrid(columns=6, parent=self._summary_card)
        self._summary_card.add_widget(self._summary_grid)

    def _build_form(self) -> None:
        self._editor_column = QWidget(self)
        self._editor_column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._editor_layout = QVBoxLayout(self._editor_column)
        self._editor_layout.setContentsMargins(0, 0, 0, 0)
        self._editor_layout.setSpacing(8)

        self._header_footer_detail = (
            HeaderFooterDetailSection(self) if self._scope in {"all", "header_footer"} else None
        )
        self._toc_detail = TocDetailSection(self) if self._scope in {"all", "toc"} else None
        self._editor_layout.addStretch(1)

    def _add_card_header(self, card: Card, icon_name: str, title: str) -> None:
        header = QWidget(card)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(6)

        icon_label = QLabel(header)
        icon_label.setFixedSize(18, 18)
        self._header_icons.append((icon_name, icon_label))
        layout.addWidget(icon_label)

        title_label = QLabel(title, header)
        title_label.setObjectName("tpl_card_title")
        self._header_titles.append(title_label)
        layout.addWidget(title_label)
        layout.addStretch(1)
        card.add_widget(header)

    def _refresh_page_plan_validation_alert(self) -> None:
        if self._header_footer_detail is not None:
            self._header_footer_detail.refresh_validation_alert(self._current_template)

    def _sync_dependent_state(self) -> None:
        if self._header_footer_detail is not None:
            self._header_footer_detail.sync_dependent_state()
        if self._toc_detail is not None:
            self._toc_detail.sync_dependent_state()

    def _refresh_summary(self) -> None:
        template = self._current_template
        if template is None:
            self._summary_grid.set_items(
                [
                    SummaryGridItem(
                        key="empty",
                        label="当前状态",
                        value="未选择模板。",
                        column_span=6,
                    )
                ]
            )
            return

        header_footer = template.header_footer
        toc = template.toc
        phases = default_page_number_phases(header_footer)

        items: list[SummaryGridItem] = []
        if self._scope in {"all", "header_footer"}:
            items.extend(
                [
                    SummaryGridItem(
                        key="header",
                        label="页眉",
                        value=self._header_summary_value(header_footer),
                        detail=self._header_summary_detail(header_footer),
                        column_span=3,
                    ),
                    SummaryGridItem(
                        key="page_number",
                        label="页脚页码",
                        value="页码开启" if header_footer.page_number_enabled else "页码关闭",
                        detail=self._page_number_summary_detail(header_footer, phases),
                        column_span=3,
                    ),
                ]
            )

        if self._scope in {"all", "toc"} and self._toc_detail is not None:
            title_style = self._toc_detail.effective_style("toc_title")
            entry_style = self._toc_detail.effective_style("toc_level1")
            items.extend(
                [
                    SummaryGridItem(
                        key="toc",
                        label="目录结构",
                        value=self._toc_summary_value(toc),
                        detail=self._toc_summary_detail(toc),
                        column_span=3,
                    ),
                    SummaryGridItem(
                        key="toc_style",
                        label="目录样式",
                        value=(
                            f"标题 {_size_text(title_style.size_pt)} / 条目 {_size_text(entry_style.size_pt)}"
                            if toc.enabled
                            else "目录关闭"
                        ),
                        detail=(
                            f"{title_style.font_cn or '-'} / {entry_style.font_cn or '-'}"
                            if toc.enabled
                            else "样式暂不输出"
                        ),
                        column_span=3,
                    ),
                ]
            )

        self._summary_grid.set_items(items)

    def _header_summary_value(self, header_footer) -> str:
        mode = str(header_footer.header_mode or "styleref")
        if mode == "none":
            return "无页眉"
        if mode == "fixed":
            return "固定页眉"
        return f"跟随 {header_footer.styleref_level} 级标题"

    def _header_summary_detail(self, header_footer) -> str:
        mode = str(header_footer.header_mode or "styleref")
        if mode == "none":
            return "不输出页眉线"
        if mode == "fixed":
            text = str(header_footer.header_text or "").strip() or "未填写固定文字"
            return f"{text} / {'横线开启' if header_footer.header_border else '横线关闭'}"
        return f"{header_footer.font_cn or '-'} / {header_footer.font_en or '-'} / {_size_text(header_footer.size_pt)}"

    def _page_number_summary_detail(self, header_footer, phases: list[PageNumberPhaseConfig]) -> str:
        if not header_footer.page_number_enabled:
            return "不输出页脚页码"
        valid_phases = [
            phase
            for phase in phases
            if any(str(selector or "").strip() for selector in (getattr(phase, "selectors", []) or []))
        ]
        visible_phases = valid_phases[:2]
        detail = "；".join(page_number_phase_brief(phase) for phase in visible_phases)
        extra_count = max(0, len(valid_phases) - len(visible_phases))
        if detail and extra_count:
            detail = f"{detail}；另 {extra_count} 段"
        suppress_selectors = default_suppress_header_footer_selectors(header_footer)
        prefix = "起始前留空" if suppress_selectors else ""
        if detail:
            return f"{prefix}；{detail}" if prefix else detail
        return f"{prefix}；全文连续阿拉伯数字页码" if prefix else "全文连续阿拉伯数字页码"

    def _toc_summary_value(self, toc) -> str:
        if not toc.enabled:
            return "目录关闭"
        mode_label = _option_label(TOC_MODE_OPTIONS, toc.mode, "Word 自动目录")
        return f"{mode_label} / {int(toc.max_level or 3)} 级"

    def _toc_summary_detail(self, toc) -> str:
        if not toc.enabled:
            return "不插入或更新目录"
        insert_label = _option_label(TOC_INSERT_OPTIONS, str(toc.insert_position or "auto"), str(toc.insert_position or "auto"))
        return f"插入位置 {insert_label}"

    def set_template(self, template: TemplateConfig | None) -> None:
        preserve_snapshot = template is self._current_template and self._snapshot is not None
        self._current_template = template
        if template is None:
            self._snapshot = None
            if self._header_footer_detail is not None:
                self._header_footer_detail.clear()
            if self._toc_detail is not None:
                self._toc_detail.clear()
            self._refresh_summary()
            self._refresh_action_state()
            return
        ensure_default_page_number_phases(template.header_footer)
        if not preserve_snapshot:
            self._snapshot = _ElementsSnapshot.from_template(template)

        self._is_syncing = True
        try:
            if self._header_footer_detail is not None:
                self._header_footer_detail.set_header_footer(template.header_footer)
            if self._toc_detail is not None:
                self._toc_detail.set_template(template)
        finally:
            self._is_syncing = False
        self._sync_dependent_state()
        self._refresh_page_plan_validation_alert()
        self._refresh_summary()
        self._refresh_action_state()

    def capture_entry_snapshot(self) -> None:
        if self._current_template is None:
            self._snapshot = None
        else:
            self._snapshot = _ElementsSnapshot.from_template(self._current_template)
        self._refresh_action_state()

    def set_save_enabled(self, enabled: bool) -> None:
        self._save_enabled = bool(enabled)
        self._refresh_action_state()

    def _on_structure_edited(self, *_args) -> None:
        if self._is_syncing or self._current_template is None:
            return

        header_footer = self._current_template.header_footer
        toc = self._current_template.toc
        if self._header_footer_detail is not None:
            self._header_footer_detail.apply_to(header_footer)
        if self._toc_detail is not None:
            self._toc_detail.apply_to(toc)

        self._sync_dependent_state()
        self._refresh_page_plan_validation_alert()
        self._refresh_summary()
        self._refresh_action_state()
        self.template_edited.emit(self._current_template)

    def _on_restore_entry(self) -> None:
        if self._current_template is None or self._snapshot is None:
            return
        self._apply_snapshot_to_active_scope()
        self.set_template(self._current_template)
        self.template_edited.emit(self._current_template)

    def _refresh_action_state(self) -> None:
        if self._current_template is None:
            self._restore_entry_btn.setEnabled(False)
            self._save_btn.setEnabled(False)
            self._refresh_action_icons()
            return
        current = _ElementsSnapshot.from_template(self._current_template)
        self._restore_entry_btn.setEnabled(
            self._snapshot is not None
            and self._snapshot_state(current) != self._snapshot_state(self._snapshot)
        )
        self._save_btn.setEnabled(self._save_enabled)
        self._refresh_action_icons()

    def _snapshot_state(self, snapshot: _ElementsSnapshot):
        if self._scope == "header_footer":
            return snapshot.header_footer_config
        if self._scope == "toc":
            return (snapshot.toc_config, snapshot.toc_styles)
        return snapshot

    def _apply_snapshot_to_active_scope(self) -> None:
        if self._current_template is None or self._snapshot is None:
            return
        if self._scope in {"all", "header_footer"}:
            self._current_template.header_footer = deepcopy(self._snapshot.header_footer_config)
        if self._scope in {"all", "toc"}:
            self._current_template.toc = deepcopy(self._snapshot.toc_config)
            for key in TOC_STYLE_KEYS:
                if key in self._snapshot.toc_styles:
                    self._current_template.styles[key] = deepcopy(self._snapshot.toc_styles[key])
                else:
                    self._current_template.styles.pop(key, None)

    def _refresh_action_icons(self) -> None:
        try:
            from src.ui.icons.catalog import get_icon
        except Exception:
            return

        theme = get_theme()
        restore_color = theme.primary if self._restore_entry_btn.isEnabled() else theme.text_disabled
        save_color = theme.text_on_primary if self._save_btn.isEnabled() else theme.text_disabled
        self._restore_entry_btn.setIcon(get_icon("refresh-ccw", 16, restore_color))
        self._save_btn.setIcon(get_icon("save", 16, save_color))

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(build_button_stylesheet(theme))

        title_ss = (
            f"font-size: {theme.font_size_lg}px; "
            f"font-weight: {theme.font_weight_emphasis}; color: {theme.primary}; background: transparent;"
        )
        note_ss = f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};"
        unit_ss = f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};"

        for widget in self.findChildren(QLabel, "tpl_card_title"):
            widget.setStyleSheet(title_ss)
        if hasattr(self, "_page_plan_note"):
            self._page_plan_note.setStyleSheet(note_ss)
        for widget in self.findChildren(QLineEdit):
            widget.setStyleSheet(build_text_input_stylesheet(theme, selector="QLineEdit"))
        for widget in self.findChildren(QLabel, "tpl_style_unit"):
            widget.setStyleSheet(unit_ss)

        apply_button_variant(self._restore_entry_btn, "ghost-primary")
        apply_button_variant(self._save_btn, "primary")
        if hasattr(self, "_preset_continuous_btn"):
            apply_button_variant(self._preset_continuous_btn, "secondary")
            apply_button_variant(self._preset_split_restart_btn, "secondary")
            apply_button_variant(self._preset_split_continue_btn, "secondary")
            apply_button_variant(self._add_phase_btn, "ghost-primary")
        for row in self._page_phase_rows:
            apply_button_variant(row.remove_btn, "ghost-danger")

        try:
            from src.ui.icons.catalog import get_icon

            for icon_name, icon_label in self._header_icons:
                icon_label.setPixmap(get_icon(icon_name, 18, theme.primary).pixmap(18, 18))
        except Exception:
            for _, icon_label in self._header_icons:
                icon_label.setText("")

        self._refresh_action_state()


__all__ = ["ElementsDetail", "HeaderFooterDetailSection", "TocDetailSection"]
