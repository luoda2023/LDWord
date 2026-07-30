"""Template overview surface driven only by an immutable projection."""

from __future__ import annotations

from src.qt_api import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSize,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from src.shared.ui import LibraryActionRow
from src.shared.ui.card import Card
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.preview_dialog import PreviewDialog, WidgetPreviewContent
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.template_summary_card import DetailSummaryCard
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.panels.template_feature_specs import TEMPLATE_FEATURE_SPECS
from src.ui.panels.template_overview_projection import TemplateOverviewProjection
from src.ui.panels.template_preview.model import TemplatePreviewMode
from src.ui.panels.template_preview.widget import TemplateStylePreview
from src.ui.template_library_controller import TemplateLibraryOption


class TemplateOverviewDetail(QWidget):
    """Template selector, baseline summaries, and whole-window style preview."""

    template_selected = Signal(int)
    edit_navigate = Signal(str)
    preview_mode_requested = Signal(str)
    new_template_requested = Signal()
    duplicate_template_requested = Signal()
    rename_template_requested = Signal()
    open_template_folder_requested = Signal()
    delete_template_requested = Signal()
    selector_open_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cached_title_labels: list[QLabel] = []
        self._header_icons: dict[str, QLabel] = {}
        self._cached_sep: QFrame | None = None
        self._preview_dialog: PreviewDialog | None = None
        self._preview_dialog_renderer: TemplateStylePreview | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._selector_card = Card(parent=self)
        self._build_selector()
        layout.addWidget(self._selector_card)

        self._overview_card = Card(parent=self)
        self._build_overview()
        layout.addWidget(self._overview_card)

        self._build_preview()
        layout.addWidget(self._preview_card)
        layout.addStretch(1)

        self.apply_theme()
        bind_theme(self, self.apply_theme)

    def _build_selector(self) -> None:
        self._selector_card.add_widget(self._make_card_header("file-text", "当前模板"))
        self._combo = StyledComboBox(self)
        self._combo.set_full_width_mode(True)
        self._combo.currentIndexChanged.connect(self.template_selected.emit)
        self._combo.popup_about_to_show.connect(self.selector_open_requested.emit)
        self._selector_card.add_widget(self._combo)

        self._status_chip = QLabel("内置模板", self._selector_card)
        self._status_chip.setObjectName("tpl_overview_status_chip")
        self._status_chip.setAlignment(Qt.AlignCenter)
        self._status_chip.hide()

        self._template_action_row = LibraryActionRow(
            self._selector_card,
            object_name="tpl_overview_template_action_row",
        )
        self._new_template_btn = self._template_action_row.add_action(
            "new", "新建模板", object_name="tpl_overview_new_template_btn",
            icon_name="plus", callback=self.new_template_requested.emit,
        )
        self._duplicate_template_btn = self._template_action_row.add_action(
            "duplicate", "创建副本", object_name="tpl_overview_duplicate_template_btn",
            icon_name="copy", callback=self.duplicate_template_requested.emit,
        )
        self._rename_template_btn = self._template_action_row.add_action(
            "rename", "重命名模板", object_name="tpl_overview_rename_template_btn",
            icon_name="pencil-line", callback=self.rename_template_requested.emit,
        )
        self._open_template_folder_btn = self._template_action_row.add_action(
            "open_folder", "打开模板文件夹",
            object_name="tpl_overview_open_template_folder_btn",
            icon_name="folder-open", callback=self.open_template_folder_requested.emit,
        )
        self._delete_template_btn = self._template_action_row.add_action(
            "delete", "删除模板", object_name="tpl_overview_delete_template_btn",
            icon_name="trash-2", variant="ghost-danger", side="right",
            callback=self.delete_template_requested.emit,
        )
        self._selector_card.add_widget(self._template_action_row)

    def _build_overview(self) -> None:
        self._overview_card.add_widget(self._make_card_header("square-sigma", "参数概览"))
        self._cached_sep = QFrame(self._overview_card)
        self._cached_sep.setFrameShape(QFrame.HLine)
        self._overview_card.add_widget(self._cached_sep)

        self._rows: dict[str, _SummaryRow] = {}
        for feature in TEMPLATE_FEATURE_SPECS:
            row = _SummaryRow(
                feature.icon_name,
                feature.nav_label,
                "等待投影",
                row_key=feature.feature_id,
                parent=self._overview_card,
            )
            row.edit_clicked.connect(
                lambda _feature_id, target=feature.card_id: self.edit_navigate.emit(target)
            )
            self._rows[feature.feature_id] = row
            self._overview_card.add_widget(row)

    def _build_preview(self) -> None:
        self._preview_card = DetailSummaryCard(
            "样式预览",
            "eye",
            compact_header=True,
            parent=self,
        )
        self._preview_card.setObjectName("tpl_overview_preview_card")
        self._preview_mode_chip = QPushButton("模板基线", self._preview_card)
        self._preview_mode_chip.setObjectName("tpl_overview_preview_mode")
        self._preview_mode_chip.setCursor(Qt.PointingHandCursor)
        self._preview_mode_chip.setAccessibleName("切换预览范围")
        self._preview_mode_chip.clicked.connect(self._on_preview_mode_clicked)
        self._preview_card.add_control(self._preview_mode_chip)
        self._preview_mode = TemplatePreviewMode.TEMPLATE_BASELINE
        self._preview_has_scene = False

        self._preview_status = QLabel("正在生成模板基线预览", self._preview_card)
        self._preview_status.setObjectName("tpl_overview_preview_status")
        self._preview_status.setWordWrap(True)
        self._preview_status.setAccessibleName("预览状态")
        self._preview_card.insert_body_widget(self._preview_status)

        self._preview = TemplateStylePreview(self._preview_card)
        self._preview.preview_requested.connect(
            self._open_template_preview_dialog
        )
        self._preview_card.insert_body_widget(self._preview, index=2)

    def _open_template_preview_dialog(self) -> bool:
        projection = self._preview.projection
        if projection is None:
            return False
        existing = self._preview_dialog
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return True

        renderer = TemplateStylePreview(presentation="dialog")
        renderer.set_projection(projection)
        natural_size = self._preview_dialog_natural_size(renderer)
        dialog = PreviewDialog(
            WidgetPreviewContent(renderer, natural_size),
            title="样式预览",
            subtitle=projection.status_text,
            initial_view="fit",
            preferred_size=QSize(1180, 860),
            parent=self.window(),
        )
        dialog.setObjectName("template_style_preview_dialog")
        dialog.finished.connect(
            lambda _result, current=dialog: self._clear_preview_dialog(current)
        )
        self._preview_dialog = dialog
        self._preview_dialog_renderer = renderer
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return True

    @staticmethod
    def _preview_dialog_natural_size(renderer: TemplateStylePreview) -> QSize:
        width = 936
        return QSize(width, renderer.heightForWidth(width))

    def _sync_open_preview_dialog(self) -> None:
        dialog = self._preview_dialog
        renderer = self._preview_dialog_renderer
        projection = self._preview.projection
        if dialog is None or renderer is None or projection is None:
            return
        renderer.set_projection(projection)
        content = WidgetPreviewContent(
            renderer,
            self._preview_dialog_natural_size(renderer),
        )
        dialog.set_title_text("样式预览", projection.status_text)
        dialog.viewport.replace_content(
            content,
            fit=dialog.viewport.mode == "fit",
        )

    def _clear_preview_dialog(self, dialog: PreviewDialog) -> None:
        if self._preview_dialog is not dialog:
            return
        self._preview_dialog = None
        self._preview_dialog_renderer = None

    def set_preview_mode_state(
        self,
        mode: TemplatePreviewMode,
        *,
        has_scene: bool,
    ) -> None:
        self._preview_mode = TemplatePreviewMode(mode)
        self._preview_has_scene = bool(has_scene)
        self._preview_mode_chip.setEnabled(bool(has_scene))
        self._preview_mode_chip.setText(
            "当前方案" if self._preview_mode is TemplatePreviewMode.CURRENT_PLAN else "模板基线"
        )
        self._preview_mode_chip.setToolTip(
            "点击切换到模板基线"
            if self._preview_mode is TemplatePreviewMode.CURRENT_PLAN
            else "点击查看当前方案的应用范围"
            if has_scene
            else "当前没有绑定方案，仅显示模板基线"
        )

    def _on_preview_mode_clicked(self) -> None:
        if not self._preview_has_scene:
            return
        target = (
            TemplatePreviewMode.TEMPLATE_BASELINE
            if self._preview_mode is TemplatePreviewMode.CURRENT_PLAN
            else TemplatePreviewMode.CURRENT_PLAN
        )
        self.preview_mode_requested.emit(target.value)

    def set_template_options(
        self,
        options: list[TemplateLibraryOption],
        *,
        current_template_id: str = "",
    ) -> None:
        self._combo.blockSignals(True)
        try:
            self._combo.clear()
            for option in options:
                is_builtin = str(option.source_type or "").strip() == "builtin"
                item_index = self._combo.add_badged_item(
                    option.name,
                    option.template_id,
                    badge_text="内置" if is_builtin else "自定",
                    badge_kind="builtin" if is_builtin else "user",
                )
                if option.tooltip:
                    self._combo.setItemData(item_index, option.tooltip, Qt.ToolTipRole)
                if option.disabled:
                    item_getter = getattr(self._combo.model(), "item", None)
                    item = item_getter(item_index) if callable(item_getter) else None
                    if item is not None:
                        item.setEnabled(False)
            target_id = str(current_template_id or "").strip()
            for index in range(self._combo.count()):
                if str(self._combo.itemData(index) or "").strip() == target_id:
                    self._combo.setCurrentIndex(index)
                    break
            else:
                if self._combo.count() > 0:
                    self._combo.setCurrentIndex(0)
        finally:
            self._combo.blockSignals(False)

    def apply_projection(self, projection: TemplateOverviewProjection) -> None:
        for feature in projection.features:
            row = self._rows.get(feature.feature_id)
            if row is not None:
                row.set_value(feature.summary)
        mode_text = (
            "当前方案"
            if projection.preview.mode is TemplatePreviewMode.CURRENT_PLAN
            else "模板基线"
        )
        self._preview_mode_chip.setText(mode_text)
        self._preview_status.setText(projection.preview.status_text)
        self._preview_status.setAccessibleDescription(
            projection.preview.accessible_description
        )
        self._preview.set_projection(projection.preview)
        self._sync_open_preview_dialog()
        self._preview_card.refresh_body_layout()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        dialog = self._preview_dialog
        self._preview_dialog = None
        self._preview_dialog_renderer = None
        if dialog is not None:
            dialog.close()
        super().closeEvent(event)

    def set_status_text(self, text: str) -> None:
        self._status_chip.setText(text)

    def set_template_action_state(
        self,
        *,
        can_rename: bool,
        can_delete: bool,
        rename_tooltip: str = "",
        delete_tooltip: str = "",
        folder_tooltip: str = "",
    ) -> None:
        self._rename_template_btn.setEnabled(can_rename)
        self._delete_template_btn.setEnabled(can_delete)
        self._rename_template_btn.setToolTip(rename_tooltip)
        self._delete_template_btn.setToolTip(delete_tooltip)
        self._open_template_folder_btn.setToolTip(folder_tooltip)

    def _make_card_header(self, icon_name: str, title: str) -> QWidget:
        header = QWidget(self)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(6)
        icon_label = QLabel(header)
        icon_label.setFixedSize(18, 18)
        layout.addWidget(icon_label)
        title_label = QLabel(title, header)
        self._cached_title_labels.append(title_label)
        layout.addWidget(title_label)
        layout.addStretch(1)
        self._header_icons[icon_name] = icon_label
        return header

    def apply_theme(self) -> None:
        theme = get_theme()
        if self.layout() is not None:
            self.layout().setSpacing(theme.template_detail_section_gap)
        title_style = (
            f"font-size: {theme.font_size_lg}px; "
            f"font-weight: {theme.font_weight_emphasis}; "
            f"color: {theme.primary}; background: transparent;"
        )
        for label in self._cached_title_labels:
            label.setStyleSheet(title_style)
        self._status_chip.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {theme.primary}; "
            f"background: {theme.bg_selected}; border: 1px solid {theme.border_light}; "
            f"border-radius: {theme.radius_sm}px; padding: 3px 8px;"
        )
        self._preview_mode_chip.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {theme.primary}; "
            f"background: {theme.bg_selected}; border: 1px solid {theme.border_light}; "
            f"border-radius: {theme.radius_sm}px; padding: 3px 8px;"
        )
        self._preview_status.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary}; "
            "background: transparent;"
        )
        self._template_action_row.apply_theme()
        if self._cached_sep is not None:
            self._cached_sep.setStyleSheet(
                f"background: {theme.border_light}; max-height: 1px;"
            )
        from src.shared.ui.icons.catalog import get_icon

        for icon_name, label in self._header_icons.items():
            label.setPixmap(
                get_icon(icon_name, 18, theme.primary).pixmap(18, 18)
            )
        self._preview.apply_theme()


class _SummaryRow(QWidget):
    edit_clicked = Signal(str)

    def __init__(
        self,
        icon_name: str,
        label: str,
        value: str,
        *,
        row_key: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self._label_text = label
        self._row_key = row_key
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(8)
        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(16, 16)
        layout.addWidget(self._icon_label)
        self._label = QLabel(label, self)
        self._label.setFixedWidth(72)
        layout.addWidget(self._label)
        self._value = QLabel(value, self)
        self._value.setWordWrap(True)
        self._value.setMinimumWidth(0)
        self._value.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout.addWidget(self._value, 1)
        self._edit_button = QPushButton("编辑", self)
        self._edit_button.setFlat(True)
        self._edit_button.setCursor(Qt.PointingHandCursor)
        self._edit_button.clicked.connect(
            lambda: self.edit_clicked.emit(self._row_key)
        )
        layout.addWidget(self._edit_button)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_value(self, text: str) -> None:
        self._value.setText(text)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._label.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; "
            f"font-weight: {theme.font_weight_emphasis}; "
            f"color: {theme.text_secondary};"
        )
        self._value.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {theme.text_primary};"
        )
        self._edit_button.setStyleSheet(
            f"QPushButton {{ font-size: {theme.font_size_sm}px; color: {theme.primary}; "
            "border: none; background: transparent; padding: 2px 6px; }"
            "QPushButton:hover { text-decoration: underline; }"
        )
        apply_size_class(self._edit_button, "sm")
        from src.shared.ui.icons.catalog import get_icon

        self._icon_label.setPixmap(
            get_icon(self._icon_name, 14, theme.text_hint).pixmap(14, 14)
        )


__all__ = ["TemplateOverviewDetail"]
