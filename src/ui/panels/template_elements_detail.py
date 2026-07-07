"""Header/footer and TOC detail pane for template management."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from src.config.template import TemplateConfig
from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSize,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.summary_grid import SummaryGridItem
from src.shared.ui.template_summary_card import (
    TemplateSummaryCard,
    apply_template_summary_action_button,
)
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.panels.template_summary_projection import (
    build_template_detail_summary,
    build_template_detail_summary_items,
    summary_grid_items,
)
from src.ui.panels.template_elements_header_footer import (
    HeaderFooterDetailSection,
    ensure_default_page_number_phases,
)
from src.ui.panels.template_elements_toc import (
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
        self._desc_labels: list[QLabel] = []
        self._is_syncing = False
        self._save_enabled = False
        self._toc_style_controls: dict[str, dict[str, object]] = {}
        self._page_phase_rows = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)
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
        return "chart-no-axes-gantt" if self._scope == "toc" else "panel-top"

    def _build_summary_card(self) -> None:
        self._summary_card = TemplateSummaryCard(
            self._title_text(),
            self._icon_name(),
            parent=self,
        )
        header = self._summary_card.header

        self._restore_entry_btn = QPushButton("恢复", header)
        self._restore_entry_btn.setIconSize(QSize(16, 16))
        self._restore_entry_btn.clicked.connect(self._on_restore_entry)
        self._summary_card.add_action(self._restore_entry_btn)

        self._save_btn = QPushButton("保存", header)
        self._save_btn.setIconSize(QSize(16, 16))
        self._save_btn.clicked.connect(self.save_requested.emit)
        self._summary_card.add_action(self._save_btn)

        self._summary_grid = self._summary_card.summary_grid

    def _build_form(self) -> None:
        self._editor_column = QWidget(self)
        self._editor_column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._editor_layout = QVBoxLayout(self._editor_column)
        self._editor_layout.setContentsMargins(0, 0, 0, 0)
        self._editor_layout.setSpacing(get_theme().template_detail_section_gap)

        self._header_footer_detail = (
            HeaderFooterDetailSection(self) if self._scope in {"all", "header_footer"} else None
        )
        self._toc_detail = TocDetailSection(self) if self._scope in {"all", "toc"} else None
        self._editor_layout.addStretch(1)

    def _add_card_header(self, card: Card, icon_name: str, title: str, description: str | None = None) -> None:
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

        if description:
            desc_label = QLabel(description, card)
            desc_label.setWordWrap(True)
            self._desc_labels.append(desc_label)
            card.add_widget(desc_label)

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
            self._summary_card.set_summary_items(
                [
                    SummaryGridItem(
                        key="empty",
                        label="当前状态",
                        value="未选择模板。",
                        column_span=12,
                        icon_name="info",
                    )
                ]
            )
            return

        if self._scope == "header_footer":
            self._summary_card.set_summary_items(
                build_template_detail_summary_items(template, "tpl_header_footer")
            )
            return
        if self._scope == "toc":
            self._summary_card.set_summary_items(build_template_detail_summary_items(template, "tpl_toc"))
            return

        header_spec = build_template_detail_summary(template, "tpl_header_footer")
        toc_spec = build_template_detail_summary(template, "tpl_toc")
        self._summary_card.set_summary_items(
            summary_grid_items(header_spec.tiles + toc_spec.tiles, span_override=3)
        )

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

    def set_reformat_enabled(self, enabled: bool | None) -> None:
        if self._scope == "header_footer":
            if self._editor_column.isHidden():
                self._editor_column.setVisible(True)
            self._refresh_summary()

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
        gap = theme.template_detail_section_gap
        self.layout().setSpacing(gap)
        self._editor_layout.setSpacing(gap)

        title_ss = (
            f"font-size: {theme.font_size_lg}px; "
            f"font-weight: {theme.font_weight_emphasis}; color: {theme.primary}; background: transparent;"
        )
        note_ss = f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};"
        unit_ss = f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};"
        desc_ss = f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};"

        for widget in self.findChildren(QLabel, "tpl_card_title"):
            widget.setStyleSheet(title_ss)
        for label in self._desc_labels:
            label.setStyleSheet(desc_ss)
        if hasattr(self, "_page_plan_note"):
            self._page_plan_note.setStyleSheet(note_ss)
        for widget in self.findChildren(QLabel, "tpl_style_unit"):
            widget.setStyleSheet(unit_ss)

        if self._header_footer_detail is not None:
            self._header_footer_detail.apply_theme()
        if self._toc_detail is not None:
            self._toc_detail.apply_theme()

        apply_template_summary_action_button(self._restore_entry_btn, "ghost-primary")
        apply_template_summary_action_button(self._save_btn, "primary")
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
