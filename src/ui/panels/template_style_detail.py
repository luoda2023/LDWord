"""Body-style detail pane for template management."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from src.config.style_semantics import (
    format_spacing_value,
    line_spacing_display_label,
    normalize_line_spacing_type,
    resolve_line_spacing_value,
    resolve_style_special_indent,
)
from src.config.template import StyleConfig, TemplateConfig
from src.qt_api import (
    QLabel,
    QPushButton,
    QSize,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from src.shared.ui.button_style import build_button_stylesheet
from src.shared.ui.navigation_highlight import NavigationHighlighter
from src.shared.ui.paragraph_style_editor import (
    ALIGNMENT_OPTIONS,
)
from src.shared.ui.style_management_block import StyleManagementBlock
from src.shared.ui.template_summary_card import (
    apply_template_summary_action_button,
)
from src.shared.ui.template_summary_header import TemplateSummaryHeader
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.adapters.field_display_names import field_display_context, field_display_name
from src.ui.panels.style_object_projection_builders import (
    build_template_body_style_projection,
)

ALIGNMENT_LABELS = {value: label for value, label in ALIGNMENT_OPTIONS}

INDENT_UNIT_LABELS = {
    "chars": "字",
    "pt": "磅",
    "cm": "cm",
}


@dataclass(eq=True)
class _StyleSnapshot:
    """Immutable snapshot of editable body-style values for restore operations."""

    body_style: StyleConfig

    @classmethod
    def from_template(cls, template: TemplateConfig) -> _StyleSnapshot:
        body = template.styles.get("body")
        if body is None:
            normal = template.styles.get("normal")
            body = deepcopy(normal) if normal is not None else StyleConfig()
        return cls(body_style=deepcopy(body))

    def apply_to(self, template: TemplateConfig) -> None:
        template.styles["body"] = deepcopy(self.body_style)


def _size_text(style: StyleConfig) -> str:
    if style.size_display:
        return style.size_display
    if style.size_pt:
        return f"{style.size_pt:g}磅"
    return "未设置字号"


def _emphasis_text(style: StyleConfig) -> str:
    states: list[str] = []
    if style.bold:
        states.append("加粗")
    if style.italic:
        states.append("斜体")
    return " / ".join(states) if states else "常规"


def _indent_value_text(value: float, unit: str) -> str:
    return f"{float(value):g}{INDENT_UNIT_LABELS.get(str(unit), str(unit))}"


def _special_indent_text(style: StyleConfig) -> str:
    special = resolve_style_special_indent(style)
    if special["mode"] == "first_line" and float(special["value"]) > 0:
        return f"首行 {_indent_value_text(float(special['value']), str(special['unit']))}"
    if special["mode"] == "hanging" and float(special["value"]) > 0:
        return f"悬挂 {_indent_value_text(float(special['value']), str(special['unit']))}"
    return "无特殊缩进"


def _line_spacing_text(style: StyleConfig) -> str:
    line_kind = normalize_line_spacing_type(style.line_spacing_type)
    value = resolve_line_spacing_value(line_kind, style.line_spacing_pt)
    label = line_spacing_display_label(line_kind)
    if line_kind == "exact":
        return f"{label} {value:g} 磅"
    if line_kind == "multiple":
        return f"{label} {value:g} 倍"
    return label


class StyleDetail(QWidget):
    """Editable body-style pane backed by ``TemplateConfig.styles['body']``."""

    template_edited = Signal(object)
    save_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_template: TemplateConfig | None = None
        self._current_scene = None
        self._snapshot: _StyleSnapshot | None = None
        self._header_icons: list[tuple[str, QLabel]] = []
        self._header_titles: list[QLabel] = []
        self._section_header_titles: list[QLabel] = []
        self._desc_labels: list[QLabel] = []
        self._unit_labels: list[QLabel] = []
        self._is_syncing = False
        self._save_enabled = False
        self._navigation_highlighter = NavigationHighlighter()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._build_style_management_block()
        layout.addWidget(self._style_management_block)
        layout.addStretch(1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    # ------------------------------------------------------------------
    # UI builders
    # ------------------------------------------------------------------

    def _build_style_management_block(self) -> None:
        self._style_management_block = StyleManagementBlock(
            self,
            title="正文排版",
            icon_name="type-outline",
            object_name_prefix="tpl_style_body",
            mode="template_baseline_edit",
        )
        self._summary_card = self._style_management_block.card
        header = self._summary_card.header

        self._restore_entry_btn = QPushButton("恢复", header)
        self._restore_entry_btn.setCursor(Qt.PointingHandCursor)
        self._restore_entry_btn.setIconSize(QSize(16, 16))
        self._restore_entry_btn.clicked.connect(self._on_restore_entry)
        self._style_management_block.add_action(self._restore_entry_btn)

        self._save_btn = QPushButton("保存", header)
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.setIconSize(QSize(16, 16))
        self._save_btn.clicked.connect(self.save_requested.emit)
        self._style_management_block.add_action(self._save_btn)

        self._summary_grid = self._style_management_block.summary
        self._editor_column = self._style_management_block
        self._style_editing_section = self._style_management_block.editing_section
        self._style_editing_section.style_changed.connect(self._on_form_edited)
        self._style_owner_status = self._style_management_block.owner_status
        self._style_surface = self._style_editing_section.style_surface
        self._paragraph_style_editor = self._style_surface.editor
        self._bind_paragraph_style_controls()
        self._text_card = self._style_surface.text_card
        self._alignment_indent_card = self._style_surface.alignment_indent_card
        self._spacing_card = self._style_surface.spacing_card
        self._text_form = self._style_surface.text_form
        self._alignment_indent_form = self._style_surface.alignment_indent_form
        self._spacing_form = self._style_surface.spacing_form

    def _bind_paragraph_style_controls(self) -> None:
        editor = self._paragraph_style_editor
        self._font_cn = editor.font_cn
        self._font_en = editor.font_en
        self._size_combo = editor.size_combo
        self._bold_switch = editor.bold_switch
        self._italic_switch = editor.italic_switch
        self._emphasis_widget = editor.emphasis_widget
        self._alignment_combo = editor.alignment_combo
        self._special_indent = editor.special_indent
        self._left_indent = editor.left_indent
        self._right_indent = editor.right_indent
        self._line_type_combo = editor.line_type_combo
        self._line_value = editor.line_value
        self._line_value_suffix = editor.line_value_suffix
        self._line_value_suffix.setObjectName("tpl_style_unit")
        self._space_before = editor.space_before
        self._space_after = editor.space_after
        self._unit_labels.append(self._line_value_suffix)
        self._alignment_combo.setToolTip("正文对齐方式。论文正文通常使用两端对齐。")
        self._line_type_combo.setToolTip("支持固定值、单倍、1.5 倍、双倍和多倍行距。")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_template(self, template: TemplateConfig | None) -> None:
        preserve_snapshot = template is self._current_template and self._snapshot is not None
        self._current_template = template
        if template is None:
            self._snapshot = None
        elif not preserve_snapshot:
            self._snapshot = _StyleSnapshot.from_template(template)
        self._sync_from_template()
        self._refresh_view_state()

    def set_scene(self, scene) -> None:
        self._current_scene = scene
        self._refresh_summary()

    def capture_entry_snapshot(self) -> None:
        if self._current_template is None:
            self._snapshot = None
        else:
            self._snapshot = _StyleSnapshot.from_template(self._current_template)
        self._refresh_action_state()

    def set_save_enabled(self, enabled: bool) -> None:
        self._save_enabled = bool(enabled)
        self._refresh_action_state()

    def apply_theme(self) -> None:
        self._apply_theme()

    def focus_navigation_field(self, field_id: str) -> bool:
        target = str(field_id or "").strip()
        widget = self._paragraph_style_editor.widget_for_field(target)
        if widget is None:
            return False
        self._navigation_highlighter.highlight(
            widget,
            target,
            display_label=(
                field_display_context(target).label_with_group()
                or field_display_name(target)
            ),
        )
        return True

    # ------------------------------------------------------------------
    # Internal sync
    # ------------------------------------------------------------------

    def _editable_style(self) -> StyleConfig | None:
        if self._current_template is None:
            return None
        styles = self._current_template.styles
        body = styles.get("body")
        if body is not None:
            return body
        normal = styles.get("normal")
        if normal is not None:
            styles["body"] = deepcopy(normal)
        else:
            styles["body"] = StyleConfig()
        return styles["body"]

    def _sync_from_template(self) -> None:
        self._is_syncing = True
        try:
            self._style_management_block.apply_style_object_projection(
                build_template_body_style_projection(
                    self._current_template,
                    self._editable_style(),
                    scene=self._current_scene,
                )
            )
        finally:
            self._is_syncing = False

    def _on_form_edited(self, *_args) -> None:
        if self._is_syncing:
            return

        style = self._editable_style()
        if style is None:
            return

        self._paragraph_style_editor.apply_to_style(style)

        self._refresh_view_state()
        self.template_edited.emit(self._current_template)

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
        self._refresh_action_state()

    def _refresh_summary(self) -> None:
        self._style_management_block.apply_style_object_projection(
            build_template_body_style_projection(
                self._current_template,
                self._editable_style(),
                scene=self._current_scene,
            )
        )

    def _refresh_action_state(self) -> None:
        template = self._current_template
        if template is None:
            self._restore_entry_btn.setEnabled(False)
            self._save_btn.setEnabled(False)
            self._refresh_action_icons()
            return

        current = _StyleSnapshot.from_template(template)
        self._restore_entry_btn.setEnabled(self._snapshot is not None and current != self._snapshot)
        self._save_btn.setEnabled(self._save_enabled)
        self._refresh_action_icons()

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

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(build_button_stylesheet(theme))
        gap = theme.template_detail_section_gap
        self.layout().setSpacing(gap)
        self._editor_column.layout().setSpacing(gap)
        if hasattr(self, "_style_editing_section"):
            self._style_editing_section.apply_theme()

        section_title_ss = (
            f"font-size: {theme.font_size_lg}px; "
            f"font-weight: {theme.font_weight_emphasis}; "
            f"color: {theme.primary}; background: transparent;"
        )
        desc_ss = f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};"
        unit_ss = f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};"

        for label in self._header_titles:
            label.setStyleSheet(
                f"font-size: {TemplateSummaryHeader.TITLE_FONT_SIZE}px; "
                f"font-weight: {theme.font_weight_emphasis}; "
                f"color: {theme.primary}; background: transparent;"
            )
        for label in self._section_header_titles:
            label.setStyleSheet(section_title_ss)
        for label in self._desc_labels:
            label.setStyleSheet(desc_ss)
        for label in self._unit_labels:
            label.setStyleSheet(unit_ss)

        apply_template_summary_action_button(self._restore_entry_btn, "ghost-primary")
        apply_template_summary_action_button(self._save_btn, "primary")

        try:
            from src.ui.icons.catalog import get_icon

            for icon_name, label in self._header_icons:
                label.setPixmap(get_icon(icon_name, 18, theme.primary).pixmap(18, 18))
        except Exception:
            pass

        self._refresh_view_state()


__all__ = ["StyleDetail"]
