"""Card-shaped, read-only material-package preview for quick execution."""

from __future__ import annotations

from src.qt_api import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QWidget,
    Qt,
    Signal,
)
from src.shared.ui.adaptive_pair_row import AdaptivePairRow
from src.shared.ui.badge import Badge
from src.shared.ui.card import Card
from src.shared.ui.rounded_surface import RoundedSurfaceFrame
from src.shared.ui.theme import bind_theme, get_theme, theme_rgba
from src.shared.ui.icons.catalog import get_icon

from .quick_material_preview_presenter import QuickMaterialPreviewProjection


class _ReadOnlyPreviewField(RoundedSurfaceFrame):
    """A non-interactive display surface using the selector control grammar."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("wb_quick_material_readonly_field")
        self.setMinimumHeight(38)
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


class QuickMaterialPreview(Card):
    """Stable material preview card matching the plan/template card language."""

    expanded_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._projection = QuickMaterialPreviewProjection()
        self._expanded = False
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
        ) = self._build_control_group("资料包", "package")
        (
            self._content_group,
            self._content_icon,
            self._content_key_label,
            self._content_field,
        ) = self._build_control_group("填充内容", "list-check")
        self._package_label = self._package_field.value_label
        self._source_badge = self._package_field.badge
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
        self._package_field.set_state(
            projection.package_label,
            badge_text=projection.package_source_text,
            badge_tone=projection.package_source_tone,
        )
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
            key_label = QLabel(item.label, self._details)
            key_label.setObjectName("wb_quick_material_detail_key")
            value_label = QLabel(item.value, self._details)
            value_label.setObjectName("wb_quick_material_detail_value")
            value_label.setProperty("missing", item.missing)
            value_label.setWordWrap(True)
            value_label.setMinimumWidth(0)
            self._details_layout.addWidget(key_label, row, column)
            self._details_layout.addWidget(value_label, row, column + 1)
            self._details_layout.setColumnStretch(column + 1, 1)

        if self._projection.hidden_item_count:
            row = (len(self._projection.items) + 1) // 2
            hidden_label = QLabel(
                f"另有 {self._projection.hidden_item_count} 项已载入",
                self._details,
            )
            hidden_label.setObjectName("wb_quick_material_hidden_count")
            self._details_layout.addWidget(hidden_label, row, 0, 1, 4)

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
            icon.setPixmap(
                get_icon(icon_name, 17, theme.icon_secondary).pixmap(17, 17)
            )
            icon.setStyleSheet("background: transparent;")
        for label in (self._package_key_label, self._content_key_label):
            label.setStyleSheet(
                f"font-size: {theme.font_size_md}px; "
                f"font-weight: {theme.font_weight_emphasis}; "
                f"color: {theme.text_secondary}; background: transparent;"
            )
        self._package_field.apply_theme()
        self._content_field.apply_theme()
        self._details.setStyleSheet(
            f"QWidget#wb_quick_material_details {{ "
            f"border-top: 1px solid {theme_rgba(theme.border, 0.8)}; "
            "background: transparent; }}"
        )
        for label in self.findChildren(QLabel, "wb_quick_material_detail_key"):
            label.setStyleSheet(
                f"font-size: {theme.font_size_sm}px; "
                f"font-weight: {theme.font_weight_emphasis}; "
                f"color: {theme.text_secondary}; background: transparent;"
            )
        for label in self.findChildren(QLabel, "wb_quick_material_detail_value"):
            color = theme.error if bool(label.property("missing")) else theme.text_primary
            label.setStyleSheet(
                f"font-size: {theme.font_size_sm}px; color: {color}; "
                "background: transparent;"
            )
        for label in self.findChildren(QLabel, "wb_quick_material_hidden_count"):
            label.setStyleSheet(
                f"font-size: {theme.font_size_sm}px; color: {theme.text_hint}; "
                "background: transparent;"
            )


__all__ = ["QuickMaterialPreview"]
