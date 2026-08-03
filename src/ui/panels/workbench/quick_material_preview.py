"""Material-package selector and compact content preview for quick execution."""

from __future__ import annotations

from collections.abc import Sequence

from src.config.execution_feature_state import (
    DISABLED_SELECTOR_LABEL,
    DISABLED_SELECTOR_VALUE,
)
from src.qt_api import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    Qt,
    QToolButton,
    QWidget,
    Signal,
)
from src.shared.ui.adaptive_pair_row import AdaptivePairRow
from src.shared.ui.badge import Badge
from src.shared.ui.card import Card
from src.shared.ui.icons.catalog import get_icon
from src.shared.ui.material_token_edit import MaterialTokenEdit
from src.shared.ui.rounded_surface import RoundedSurfaceFrame
from src.shared.ui.sizing import resolved_control_height
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme, theme_rgba
from src.ui.adapters.config_selector_models import SelectorOption

from .quick_material_preview_presenter import QuickMaterialPreviewProjection


class _ReadOnlyPreviewField(RoundedSurfaceFrame):
    """A non-interactive display surface using the selector control grammar."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("wb_quick_material_readonly_field")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        self.value_label = QLabel("", self)
        self.value_label.setObjectName("wb_quick_material_readonly_value")
        self.value_label.setMinimumWidth(0)
        self.value_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.value_label, 1)

        self.badge = Badge(parent=self)
        layout.addWidget(self.badge, 0, Qt.AlignVCenter)

    def set_state(
        self,
        value: str,
        *,
        badge_text: str = "",
        badge_tone: str = "neutral",
    ) -> None:
        self.value_label.setText(str(value or ""))
        self.badge.set_text(str(badge_text or ""))
        self.badge.set_variant(str(badge_tone or "neutral"))

    def apply_theme(self) -> None:
        theme = get_theme()
        control_height = resolved_control_height(theme, "md")
        self.setMinimumHeight(control_height)
        self.setMaximumHeight(control_height)
        self.configure_surface(
            background=theme.bg_card,
            radius=theme.radius_sm,
            border_color=theme.border,
            border_width=1.0,
        )
        self.value_label.setStyleSheet(
            f"font-size: {theme.font_size_md}px; color: {theme.text_primary}; "
            "background: transparent;"
        )


class _MaterialPackageComboBox(StyledComboBox):
    """Selector compatibility surface used by preview-focused tests and callers."""

    def text(self) -> str:
        return self.display_text()


class QuickMaterialPreview(Card):
    """Stable material preview card matching the plan/template card language."""

    expanded_changed = Signal(bool)
    package_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._projection = QuickMaterialPreviewProjection()
        self._expanded = False
        self._package_options: tuple[SelectorOption, ...] | None = None
        self._selected_package_identity = ""
        self.setObjectName("wb_quick_material_preview")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.set_header("资料包内容预览", icon_name="package")

        self._toggle_button = QToolButton(self)
        self._toggle_button.setObjectName("wb_quick_material_preview_toggle")
        self._toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._toggle_button.clicked.connect(self._toggle_expanded)
        self.add_header_action(self._toggle_button)

        (
            self._package_group,
            self._package_icon,
            self._package_key_label,
            self._package_field,
        ) = self._build_package_control_group("资料包", "package")
        (
            self._content_group,
            self._content_icon,
            self._content_key_label,
            self._content_field,
        ) = self._build_control_group("填充内容", "list-checks")
        self._package_label = self._package_field
        self._summary_label = self._content_field.value_label
        self._status_badge = self._content_field.badge

        self._control_row = AdaptivePairRow(
            self._package_group,
            self._content_group,
            parent=self,
            spacing=28,
            stacked_spacing=10,
            stretches=(1, 1),
            stack_slack=90,
        )
        self._control_row.setObjectName("wb_quick_material_control_row")
        self.add_widget(self._control_row)

        self._details = QWidget(self)
        self._details.setObjectName("wb_quick_material_details")
        self._details_layout = QGridLayout(self._details)
        self._details_layout.setContentsMargins(0, 4, 0, 0)
        self._details_layout.setHorizontalSpacing(18)
        self._details_layout.setVerticalSpacing(8)
        self.add_widget(self._details)

        self._apply_preview_theme()
        bind_theme(self, self._apply_preview_theme)
        self.set_projection(self._projection)

    def projection(self) -> QuickMaterialPreviewProjection:
        return self._projection

    def is_expanded(self) -> bool:
        return self._expanded

    def set_projection(self, projection: QuickMaterialPreviewProjection) -> None:
        if not isinstance(projection, QuickMaterialPreviewProjection):
            raise TypeError("projection must be a QuickMaterialPreviewProjection")
        self._projection = projection
        self.setVisible(projection.visible)
        if self._package_options is None:
            self._package_field.set_display_text_override(projection.package_label)
        self._content_field.set_state(
            projection.summary_text,
            badge_text=projection.status_text,
            badge_tone=projection.status_tone,
        )
        self._rebuild_details()
        if not projection.can_expand:
            self._expanded = False
        self._sync_expanded_state()
        self._apply_preview_theme()

    def set_package_options(
        self,
        options: Sequence[SelectorOption],
        *,
        selected_identity: str = "",
    ) -> None:
        self._package_options = tuple(options)
        self._selected_package_identity = str(selected_identity or "").strip()
        blocked = self._package_field.blockSignals(True)
        try:
            self._package_field.clear()
            self._package_field.set_display_text_override(None)
            selected_index = -1
            for option in self._package_options:
                if option.source_type == "builtin":
                    badge_text, badge_kind = "内置", "builtin"
                elif option.source_type == "unavailable":
                    badge_text, badge_kind = "失效", "neutral"
                else:
                    badge_text, badge_kind = "自定", "user"
                item_index = self._package_field.add_badged_item(
                    option.label,
                    option.value,
                    badge_text=badge_text,
                    badge_kind=badge_kind,
                )
                if option.tooltip:
                    self._package_field.setItemData(
                        item_index,
                        option.tooltip,
                        Qt.ToolTipRole,
                    )
                if option.disabled:
                    item_getter = getattr(self._package_field.model(), "item", None)
                    item = item_getter(item_index) if callable(item_getter) else None
                    if item is not None:
                        item.setEnabled(False)
                if option.value == self._selected_package_identity:
                    selected_index = item_index
            disabled_index = self._package_field.add_badged_item(
                DISABLED_SELECTOR_LABEL,
                DISABLED_SELECTOR_VALUE,
                badge_text="关闭",
                badge_kind="off",
            )
            if selected_index < 0:
                selected_index = disabled_index
            self._package_field.setCurrentIndex(selected_index)
        finally:
            self._package_field.blockSignals(blocked)

    def set_expanded(self, expanded: bool) -> None:
        next_state = bool(expanded) and self._projection.can_expand
        if next_state == self._expanded:
            self._sync_expanded_state()
            return
        self._expanded = next_state
        self._sync_expanded_state()
        self.expanded_changed.emit(self._expanded)

    def _build_control_group(
        self,
        label: str,
        icon_name: str,
    ) -> tuple[QWidget, QLabel, QLabel, _ReadOnlyPreviewField]:
        container = QWidget(self)
        container.setObjectName("wb_quick_material_control_group")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)

        icon = QLabel(container)
        icon.setObjectName("wb_quick_material_control_icon")
        icon.setFixedSize(18, 18)
        layout.addWidget(icon, 0, Qt.AlignVCenter)

        key_label = QLabel(label, container)
        key_label.setObjectName("wb_quick_material_control_key")
        layout.addWidget(key_label, 0, Qt.AlignVCenter)

        field = _ReadOnlyPreviewField(container)
        layout.addWidget(field, 1)
        icon.setProperty("iconName", icon_name)
        return container, icon, key_label, field

    def _build_package_control_group(
        self,
        label: str,
        icon_name: str,
    ) -> tuple[QWidget, QLabel, QLabel, _MaterialPackageComboBox]:
        container = QWidget(self)
        container.setObjectName("wb_quick_material_control_group")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)

        icon = QLabel(container)
        icon.setObjectName("wb_quick_material_control_icon")
        icon.setFixedSize(18, 18)
        layout.addWidget(icon, 0, Qt.AlignVCenter)

        key_label = QLabel(label, container)
        key_label.setObjectName("wb_quick_material_control_key")
        layout.addWidget(key_label, 0, Qt.AlignVCenter)

        field = _MaterialPackageComboBox(container)
        field.setObjectName("wb_quick_material_package_selector")
        field.set_full_width_mode(True)
        field.currentIndexChanged.connect(self._on_package_selection_changed)
        layout.addWidget(field, 1)
        icon.setProperty("iconName", icon_name)
        return container, icon, key_label, field

    def _on_package_selection_changed(self, index: int) -> None:
        if index < 0:
            return
        identity = str(self._package_field.itemData(index) or "").strip()
        self._selected_package_identity = identity
        self.package_selected.emit(identity)

    def _toggle_expanded(self) -> None:
        self.set_expanded(not self._expanded)

    def _sync_expanded_state(self) -> None:
        can_expand = self._projection.can_expand
        self._toggle_button.setVisible(can_expand)
        self._toggle_button.setText("收起" if self._expanded else "展开")
        self._toggle_button.setIcon(
            get_icon(
                "chevron-up" if self._expanded else "chevron-down",
                15,
                get_theme().text_secondary,
            )
        )
        self._details.setVisible(self._expanded and can_expand)
        self.updateGeometry()

    def _rebuild_details(self) -> None:
        while self._details_layout.count():
            layout_item = self._details_layout.takeAt(0)
            widget = layout_item.widget()
            if widget is not None:
                widget.deleteLater()

        for index, item in enumerate(self._projection.items):
            row = index // 2
            column = (index % 2) * 2
            token_edit = MaterialTokenEdit(
                item.token,
                self._details,
                editable=False,
            )
            token_edit.setObjectName("wb_quick_material_detail_token")
            token_edit.setToolTip("单击复制完整 Token")

            value_label = QLabel(item.value, self._details)
            value_label.setObjectName("wb_quick_material_detail_value")
            value_label.setProperty("missing", item.missing)
            value_label.setWordWrap(True)
            value_label.setMinimumWidth(0)
            self._details_layout.addWidget(token_edit, row, column)
            self._details_layout.addWidget(value_label, row, column + 1)
            self._details_layout.setColumnStretch(column, 1)
            self._details_layout.setColumnStretch(column + 1, 1)

    def _apply_preview_theme(self) -> None:
        theme = get_theme()
        self._toggle_button.setStyleSheet(
            "QToolButton {"
            f"color: {theme.text_secondary}; font-size: {theme.font_size_sm}px; "
            "border: none; background: transparent; padding: 0;"
            "}"
        )
        for icon in (self._package_icon, self._content_icon):
            icon_name = str(icon.property("iconName") or "package")
            icon.setPixmap(get_icon(icon_name, 17, theme.icon_secondary).pixmap(17, 17))
            icon.setStyleSheet("background: transparent;")
        for label in (self._package_key_label, self._content_key_label):
            label.setStyleSheet(
                f"font-size: {theme.font_size_md}px; "
                f"font-weight: {theme.font_weight_emphasis}; "
                f"color: {theme.text_secondary}; background: transparent;"
            )
        self._content_field.apply_theme()
        self._details.setStyleSheet(
            f"QWidget#wb_quick_material_details {{ "
            f"border-top: 1px solid {theme_rgba(theme.border, 0.8)}; "
            "background: transparent; }}"
        )
        for label in self.findChildren(QLabel, "wb_quick_material_detail_value"):
            color = (
                theme.error if bool(label.property("missing")) else theme.text_primary
            )
            label.setStyleSheet(
                f"font-size: {theme.font_size_sm}px; color: {color}; "
                "background: transparent;"
            )


__all__ = ["QuickMaterialPreview"]
