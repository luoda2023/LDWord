"""Page setup detail pane for template management."""

from __future__ import annotations

from dataclasses import dataclass

from src.config.template import TemplateConfig
from src.qt_api import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSize,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    Qt,
    Signal,
)
from src.shared.ui.button_style import build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.inline_alert import InlineAlert
from src.shared.ui.navigation_highlight import NavigationHighlighter
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.summary_grid import SummaryGridItem
from src.shared.ui.template_form_layout import template_form_row
from src.shared.ui.template_summary_card import (
    TemplateSummaryCard,
    apply_template_summary_action_button,
)
from src.shared.ui.themed_radio_button import ThemedRadioButton
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.adapters.field_display_names import field_display_name
from src.ui.panels.template_summary_projection import build_template_detail_summary_items


_PAPER_OPTIONS: tuple[tuple[str, str], ...] = (
    ("A4", "A4"),
    ("A3", "A3"),
    ("B5", "B5"),
    ("LETTER", "Letter"),
    ("LEGAL", "Legal"),
    ("16K", "16K"),
)

_SECTION_BREAK_OPTIONS: tuple[tuple[str, str], ...] = (
    ("", "不设置"),
    ("nextPage", "下一页分节"),
    ("continuous", "连续分节"),
)

_PAPER_DIMENSIONS_CM: dict[str, tuple[float, float]] = {
    "A4": (21.0, 29.7),
    "A3": (29.7, 42.0),
    "B5": (17.6, 25.0),
    "LETTER": (21.59, 27.94),
    "LEGAL": (21.59, 35.56),
    "16K": (18.4, 26.0),
}


@dataclass(eq=True)
class _PageSetupSnapshot:
    """Immutable snapshot of page-geometry values for restore operations."""

    paper_size: str
    orientation: str
    top_cm: float
    bottom_cm: float
    left_cm: float
    right_cm: float
    gutter_cm: float
    header_distance_cm: float
    footer_distance_cm: float
    section_break_type: str | None

    @classmethod
    def from_template(cls, template: TemplateConfig) -> _PageSetupSnapshot:
        page = template.page_setup
        return cls(
            paper_size=page.paper_size,
            orientation=getattr(page, "orientation", "portrait"),
            top_cm=page.margin.top_cm,
            bottom_cm=page.margin.bottom_cm,
            left_cm=page.margin.left_cm,
            right_cm=page.margin.right_cm,
            gutter_cm=page.gutter_cm,
            header_distance_cm=page.header_distance_cm,
            footer_distance_cm=page.footer_distance_cm,
            section_break_type=template.section.section_break_type,
        )

    @classmethod
    def defaults(cls) -> _PageSetupSnapshot:
        default_template = TemplateConfig()
        return cls.from_template(default_template)

    def apply_to(self, template: TemplateConfig) -> None:
        page = template.page_setup
        page.paper_size = self.paper_size
        page.orientation = self.orientation
        page.margin.top_cm = self.top_cm
        page.margin.bottom_cm = self.bottom_cm
        page.margin.left_cm = self.left_cm
        page.margin.right_cm = self.right_cm
        page.gutter_cm = self.gutter_cm
        page.header_distance_cm = self.header_distance_cm
        page.footer_distance_cm = self.footer_distance_cm
        template.section.section_break_type = self.section_break_type or None


def _set_combo_by_data(combo: StyledComboBox, target) -> None:
    normalized_target = "" if target in (None, "") else str(target)
    for index in range(combo.count()):
        current = combo.itemData(index)
        normalized_current = "" if current in (None, "") else str(current)
        if normalized_current == normalized_target:
            combo.setCurrentIndex(index)
            return


def _paper_dimensions_cm(paper_size: str, orientation: str) -> tuple[float, float]:
    width_cm, height_cm = _PAPER_DIMENSIONS_CM.get(
        str(paper_size or "").upper(),
        _PAPER_DIMENSIONS_CM["A4"],
    )
    if orientation == "landscape":
        return height_cm, width_cm
    return width_cm, height_cm


def _orientation_label(orientation: str) -> str:
    return "横向" if orientation == "landscape" else "纵向"


def _section_break_label(value: str | None) -> str:
    mapping = {
        "nextPage": "下一页分节",
        "continuous": "连续分节",
        "": "不设置",
        None: "不设置",
    }
    return mapping.get(value, str(value))


def _cm_text(value: float) -> str:
    return f"{value:g} cm"


class PageSetupDetail(QWidget):
    """Page geometry editor with live summary and grouped controls."""

    template_edited = Signal(object)
    save_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_template: TemplateConfig | None = None
        self._snapshot: _PageSetupSnapshot | None = None
        self._page_inputs: dict[str, SpacingInput] = {}
        self._header_icons: list[tuple[str, QLabel]] = []
        self._header_titles: list[QLabel] = []
        self._desc_labels: list[QLabel] = []
        self._unit_labels: list[QLabel] = []
        self._navigation_highlighter = NavigationHighlighter()
        self._is_syncing = False
        self._save_enabled = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._build_summary_card()
        layout.addWidget(self._summary_card)

        self._build_editor_column(self)
        layout.addWidget(self._editor_column)
        layout.addStretch(1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    # ------------------------------------------------------------------
    # UI builders
    # ------------------------------------------------------------------

    def _build_summary_card(self) -> None:
        self._summary_card = TemplateSummaryCard("页面设置", "ruler", parent=self)
        header = self._summary_card.header

        self._restore_entry_btn = QPushButton("恢复", header)
        self._restore_entry_btn.setCursor(Qt.PointingHandCursor)
        self._restore_entry_btn.setIconSize(QSize(16, 16))
        self._restore_entry_btn.clicked.connect(self._on_restore_entry)
        self._summary_card.add_action(self._restore_entry_btn)

        self._save_btn = QPushButton("保存", header)
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.setIconSize(QSize(16, 16))
        self._save_btn.clicked.connect(self.save_requested.emit)
        self._summary_card.add_action(self._save_btn)

        self._summary_grid = self._summary_card.summary_grid

    def _build_editor_column(self, parent: QWidget) -> None:
        self._editor_column = QWidget(parent)
        self._editor_column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout = QVBoxLayout(self._editor_column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)

        self._validation_alert = InlineAlert("", variant="warning", parent=self._editor_column)
        self._validation_alert.hide()
        layout.addWidget(self._validation_alert)

        self._paper_card = Card(parent=self._editor_column)
        self._add_card_header(
            self._paper_card,
            "layout",
            "纸张与方向",
        )
        self._build_paper_controls()
        layout.addWidget(self._paper_card)

        self._margin_card = Card(parent=self._editor_column)
        self._add_card_header(
            self._margin_card,
            "scan",
            "页边距与装订线",
        )
        self._build_margin_controls()
        layout.addWidget(self._margin_card)

        self._header_footer_card = Card(parent=self._editor_column)
        self._add_card_header(
            self._header_footer_card,
            "panel-top",
            "页眉与页脚",
        )
        self._build_header_footer_controls()
        layout.addWidget(self._header_footer_card)

        layout.addStretch(1)

    def _build_paper_controls(self) -> None:
        self._paper_combo = StyledComboBox(self)
        self._configure_expanding_combo(self._paper_combo)
        for value, label in _PAPER_OPTIONS:
            self._paper_combo.addItem(label, value)
        self._paper_combo.currentIndexChanged.connect(self._on_form_edited)

        self._orientation_group = QButtonGroup(self)
        self._orientation_group.setExclusive(True)
        self._orient_portrait_btn = ThemedRadioButton("纵向", self._paper_card)
        self._orient_landscape_btn = ThemedRadioButton("横向", self._paper_card)
        for button_id, button in enumerate((self._orient_portrait_btn, self._orient_landscape_btn)):
            button.setCursor(Qt.PointingHandCursor)
            self._orientation_group.addButton(button, button_id)
            button.clicked.connect(self._on_form_edited)

        self._section_break_combo = StyledComboBox(self)
        self._configure_expanding_combo(self._section_break_combo)
        for value, label in _SECTION_BREAK_OPTIONS:
            self._section_break_combo.addItem(label, value)
        self._section_break_combo.currentIndexChanged.connect(self._on_form_edited)
        self._paper_form = InspectorForm(parent=self._paper_card)
        self._paper_form.add_grid(
            [
                [
                    self._build_form_row("纸张", self._paper_combo, parent=self._paper_form),
                    self._build_form_row("分节方式", self._section_break_combo, parent=self._paper_form),
                ],
            ],
        )
        self._paper_form.add_field(
            "方向",
            self._build_direction_selector(parent=self._paper_form),
        )
        self._paper_card.add_widget(self._paper_form)

    def _build_margin_controls(self) -> None:
        self._margin_form = InspectorForm(parent=self._margin_card)
        self._margin_form.add_grid(
            [
                [
                    self._build_spacing_form_row("上边距", "top_cm", parent=self._margin_form),
                    self._build_spacing_form_row("下边距", "bottom_cm", parent=self._margin_form),
                ],
                [
                    self._build_spacing_form_row("左边距", "left_cm", parent=self._margin_form),
                    self._build_spacing_form_row("右边距", "right_cm", parent=self._margin_form),
                ],
                [
                    self._build_spacing_form_row("装订线", "gutter_cm", parent=self._margin_form),
                    self._margin_form.placeholder_cell(),
                ],
            ]
        )
        self._margin_card.add_widget(self._margin_form)

    def _build_header_footer_controls(self) -> None:
        self._header_footer_form = InspectorForm(parent=self._header_footer_card)
        self._header_footer_form.add_grid(
            [
                [
                    self._build_spacing_form_row(
                        "页眉距离",
                        "header_distance_cm",
                        parent=self._header_footer_form,
                    ),
                    self._build_spacing_form_row(
                        "页脚距离",
                        "footer_distance_cm",
                        parent=self._header_footer_form,
                    ),
                ],
            ],
        )
        self._header_footer_card.add_widget(self._header_footer_form)

    def _add_card_header(
        self,
        card: Card,
        icon_name: str,
        title: str,
        description: str | None = None,
    ) -> None:
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

    def _build_spacing_input(self, field_name: str) -> SpacingInput:
        spacing = SpacingInput(
            unit="cm",
            min_val=0.0,
            max_val=20.0,
            step=0.1,
            decimals=1,
            units=("cm",),
            show_unit=False,
            parent=self,
        )
        spacing.value_changed.connect(self._on_form_edited)
        self._page_inputs[field_name] = spacing
        return spacing

    def _configure_expanding_combo(self, combo: StyledComboBox) -> None:
        combo.setSizeAdjustPolicy(combo.SizeAdjustPolicy.AdjustToContentsOnFirstShow)

    def _build_form_row(
        self,
        label: str,
        widget: QWidget,
        *,
        parent,
        label_width: int | None = None,
    ) -> QWidget:
        return template_form_row(label, widget, label_width=label_width, parent=parent)

    def _build_direction_selector(self, *, parent) -> QWidget:
        row = QWidget(parent)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)
        layout.addWidget(self._orient_portrait_btn, 0)
        layout.addWidget(self._orient_landscape_btn, 0)
        layout.addStretch(1)
        return row

    def _build_spacing_form_row(self, label: str, field_name: str, *, parent) -> QWidget:
        spacing = self._build_spacing_input(field_name)
        suffix = QLabel("cm", parent)
        suffix.setObjectName("tpl_page_unit")
        self._unit_labels.append(suffix)
        return template_form_row(label, spacing, suffix_widget=suffix, parent=parent)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_template(self, template: TemplateConfig | None) -> None:
        preserve_snapshot = template is self._current_template and self._snapshot is not None
        self._current_template = template
        if template is None:
            self._snapshot = None
        elif not preserve_snapshot:
            self._snapshot = _PageSetupSnapshot.from_template(template)
        self._sync_from_template()
        self._refresh_view_state()

    def capture_entry_snapshot(self) -> None:
        if self._current_template is None:
            self._snapshot = None
        else:
            self._snapshot = _PageSetupSnapshot.from_template(self._current_template)
        self._refresh_action_state()

    def set_save_enabled(self, enabled: bool) -> None:
        self._save_enabled = bool(enabled)
        self._refresh_action_state()

    def focus_navigation_field(self, field_id: str) -> bool:
        target = str(field_id or "").strip()
        field_name = self._page_focus_field_id(target)
        widget = self._page_focus_widget(field_name)
        if widget is None:
            return False
        self._navigation_highlighter.highlight(
            widget,
            target,
            display_label=field_display_name(target),
        )
        return True

    # ------------------------------------------------------------------
    # Internal sync
    # ------------------------------------------------------------------

    def _sync_from_template(self) -> None:
        template = self._current_template
        if template is None:
            return

        self._is_syncing = True
        try:
            paper = (template.page_setup.paper_size or "A4").upper()
            _set_combo_by_data(self._paper_combo, paper)

            self._orient_landscape_btn.setChecked(template.page_setup.orientation == "landscape")
            self._orient_portrait_btn.setChecked(template.page_setup.orientation != "landscape")
            _set_combo_by_data(self._section_break_combo, template.section.section_break_type or "")

            values = {
                "top_cm": template.page_setup.margin.top_cm,
                "bottom_cm": template.page_setup.margin.bottom_cm,
                "left_cm": template.page_setup.margin.left_cm,
                "right_cm": template.page_setup.margin.right_cm,
                "gutter_cm": template.page_setup.gutter_cm,
                "header_distance_cm": template.page_setup.header_distance_cm,
                "footer_distance_cm": template.page_setup.footer_distance_cm,
            }
            for field_name, value in values.items():
                self._page_inputs[field_name].set_value(float(value), "cm")
        finally:
            self._is_syncing = False

    def _on_form_edited(self, *_args) -> None:
        if self._is_syncing or self._current_template is None:
            return

        self._write_form_to_template()
        self._refresh_view_state()
        self.template_edited.emit(self._current_template)

    def _write_form_to_template(self) -> None:
        template = self._current_template
        if template is None:
            return

        page_setup = template.page_setup
        page_setup.paper_size = str(self._paper_combo.currentData() or "A4").upper()
        page_setup.orientation = "landscape" if self._orient_landscape_btn.isChecked() else "portrait"
        page_setup.margin.top_cm = self._page_inputs["top_cm"].value()
        page_setup.margin.bottom_cm = self._page_inputs["bottom_cm"].value()
        page_setup.margin.left_cm = self._page_inputs["left_cm"].value()
        page_setup.margin.right_cm = self._page_inputs["right_cm"].value()
        page_setup.gutter_cm = self._page_inputs["gutter_cm"].value()
        page_setup.header_distance_cm = self._page_inputs["header_distance_cm"].value()
        page_setup.footer_distance_cm = self._page_inputs["footer_distance_cm"].value()
        template.section.section_break_type = str(self._section_break_combo.currentData() or "").strip() or None

    def _on_restore_entry(self) -> None:
        if self._current_template is None or self._snapshot is None:
            return
        self._snapshot.apply_to(self._current_template)
        self._sync_from_template()
        self._refresh_view_state()
        self.template_edited.emit(self._current_template)

    # ------------------------------------------------------------------
    # Derived UI state
    # ------------------------------------------------------------------

    def _refresh_view_state(self) -> None:
        self._refresh_summary()
        self._refresh_validation_alert()
        self._refresh_action_state()

    def _refresh_summary(self) -> None:
        template = self._current_template
        if template is None:
            self._summary_card.set_summary_items([
                SummaryGridItem(
                    key="empty",
                    label="当前状态",
                    value="未选择模板。",
                    detail="选择模板后，这里会汇总纸张、边距、页眉页脚和装订线信息。",
                    column_span=12,
                    icon_name="info",
                ),
            ])
            return

        self._summary_card.set_summary_items(build_template_detail_summary_items(template, "tpl_page"))

    def _refresh_validation_alert(self) -> None:
        variant, message = self._build_validation_message()
        self._validation_alert.setVisible(bool(message))
        if message:
            self._validation_alert.set_variant(variant)
            self._validation_alert.set_message(message)

    def _build_validation_message(self) -> tuple[str, str]:
        template = self._current_template
        if template is None:
            return ("info", "")

        page = template.page_setup
        paper_width_cm, paper_height_cm = _paper_dimensions_cm(page.paper_size, page.orientation)
        content_width_cm = paper_width_cm - page.margin.left_cm - page.margin.right_cm - page.gutter_cm
        content_height_cm = paper_height_cm - page.margin.top_cm - page.margin.bottom_cm

        if content_width_cm <= 0 or content_height_cm <= 0:
            return (
                "error",
                "当前纸张与边距组合会导致版心尺寸无效，请先减少边距或更换纸张。",
            )
        if page.header_distance_cm >= page.margin.top_cm or page.footer_distance_cm >= page.margin.bottom_cm:
            return (
                "warning",
                "页眉或页脚距离已经逼近正文区域，建议保持它们小于对应边距。",
            )
        if content_width_cm < 8.0 or content_height_cm < 12.0:
            return (
                "warning",
                "当前版心已经偏窄或偏矮，正文会显得拥挤，建议重新检查左右或上下边距。",
            )
        return ("info", "")

    def _refresh_action_state(self) -> None:
        template = self._current_template
        if template is None:
            self._restore_entry_btn.setEnabled(False)
            self._save_btn.setEnabled(False)
            self._refresh_action_icons()
            return

        current = _PageSetupSnapshot.from_template(template)
        self._restore_entry_btn.setEnabled(self._snapshot is not None and current != self._snapshot)
        self._save_btn.setEnabled(self._save_enabled)
        self._refresh_action_icons()

    def _refresh_action_icons(self) -> None:
        try:
            from src.shared.ui.icons.catalog import get_icon
        except Exception:
            return

        theme = get_theme()
        restore_color = theme.primary if self._restore_entry_btn.isEnabled() else theme.text_disabled
        save_color = theme.text_on_primary if self._save_btn.isEnabled() else theme.text_disabled
        self._restore_entry_btn.setIcon(get_icon("refresh-ccw", 16, restore_color))
        self._save_btn.setIcon(get_icon("save", 16, save_color))

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(build_button_stylesheet(theme))
        gap = theme.template_detail_section_gap
        self.layout().setSpacing(gap)
        self._editor_column.layout().setSpacing(gap)

        title_ss = (
            f"font-size: {theme.font_size_lg}px; "
            f"font-weight: {theme.font_weight_emphasis}; "
            f"color: {theme.primary}; background: transparent;"
        )
        desc_ss = f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};"
        unit_ss = f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};"

        for label in self._header_titles:
            label.setStyleSheet(title_ss)
        for label in self._desc_labels:
            label.setStyleSheet(desc_ss)
        for label in self._unit_labels:
            label.setStyleSheet(unit_ss)

        apply_template_summary_action_button(self._restore_entry_btn, "ghost-primary")
        apply_template_summary_action_button(self._save_btn, "primary")

        try:
            from src.shared.ui.icons.catalog import get_icon

            for icon_name, label in self._header_icons:
                label.setPixmap(get_icon(icon_name, 18, theme.primary).pixmap(18, 18))
        except Exception:
            pass

        self._refresh_view_state()

    def _page_focus_field_id(self, field_id: str) -> str:
        target = str(field_id or "").strip()
        if target.startswith("template."):
            target = target[len("template.") :]
        aliases = {
            "paper": "paper_size",
            "paper_size": "paper_size",
            "page.paper_size": "paper_size",
            "page_setup.paper_size": "paper_size",
            "orientation": "orientation",
            "page.orientation": "orientation",
            "page_setup.orientation": "orientation",
            "section_break_type": "section_break_type",
            "section.section_break_type": "section_break_type",
            "page_setup.section_break_type": "section_break_type",
            "top_cm": "top_cm",
            "top_margin_cm": "top_cm",
            "margin.top_cm": "top_cm",
            "page.margin.top_cm": "top_cm",
            "page_setup.margin.top_cm": "top_cm",
            "bottom_cm": "bottom_cm",
            "bottom_margin_cm": "bottom_cm",
            "margin.bottom_cm": "bottom_cm",
            "page.margin.bottom_cm": "bottom_cm",
            "page_setup.margin.bottom_cm": "bottom_cm",
            "left_cm": "left_cm",
            "left_margin_cm": "left_cm",
            "margin.left_cm": "left_cm",
            "page.margin.left_cm": "left_cm",
            "page_setup.margin.left_cm": "left_cm",
            "right_cm": "right_cm",
            "right_margin_cm": "right_cm",
            "margin.right_cm": "right_cm",
            "page.margin.right_cm": "right_cm",
            "page_setup.margin.right_cm": "right_cm",
            "gutter_cm": "gutter_cm",
            "page.gutter_cm": "gutter_cm",
            "page_setup.gutter_cm": "gutter_cm",
            "header_distance_cm": "header_distance_cm",
            "page.header_distance_cm": "header_distance_cm",
            "page_setup.header_distance_cm": "header_distance_cm",
            "footer_distance_cm": "footer_distance_cm",
            "page.footer_distance_cm": "footer_distance_cm",
            "page_setup.footer_distance_cm": "footer_distance_cm",
        }
        return aliases.get(target, "")

    def _page_focus_widget(self, field_name: str) -> QWidget | None:
        if field_name == "paper_size":
            return self._paper_combo
        if field_name == "orientation":
            if self._orient_landscape_btn.isChecked():
                return self._orient_landscape_btn
            return self._orient_portrait_btn
        if field_name == "section_break_type":
            return self._section_break_combo
        return self._page_inputs.get(field_name)


__all__ = ["PageSetupDetail"]
