"""
Shared combo-box foundation with an anchored in-window popup panel.
"""

from __future__ import annotations

from src.qt_api import (
    QColor,
    QComboBox,
    QEvent,
    QFont,
    QListView,
    QPainter,
    QPoint,
    QRect,
    QRectF,
    QSize,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    Signal,
    Qt,
)

from src.shared.ui.combo_popup_panel import ComboPopupPanel
from src.shared.ui.input_metrics import (
    build_input_editor_stylesheet,
    configure_input_line_edit,
    draw_combo_chevron,
    draw_input_surface,
    input_text_color,
    input_text_rect,
    sync_input_line_edit_geometry,
)
from src.shared.ui.paint_geometry import STROKE_ICON, stroke_pen
from src.shared.ui.sizing import apply_size_class, resolved_control_height
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.typography_policy import TextRole, apply_text_role


SOURCE_BADGE_TEXT_ROLE = int(Qt.UserRole) + 101
SOURCE_BADGE_KIND_ROLE = int(Qt.UserRole) + 102
SOURCE_BADGE_FONT_PX = 10
CURRENT_BADGE_RIGHT_INSET = 8


def _source_badge_colors(theme, badge_kind: str, *, enabled: bool) -> tuple[QColor, QColor]:
    if badge_kind == "user":
        fill = QColor(theme.primary)
        fill.setAlpha(42 if enabled else 18)
        text = QColor(theme.primary if enabled else theme.text_disabled)
        return fill, text

    fill = QColor(theme.text_secondary)
    fill.setAlpha(32 if enabled else 14)
    text = QColor(theme.text_secondary if enabled else theme.text_disabled)
    return fill, text


class _SourceBadgeItemDelegate(QStyledItemDelegate):
    """Paint source-aware options as one selectable card with a trailing badge."""

    _OUTER_X = 4
    _OUTER_Y = 2
    _CONTENT_X = 10
    _BADGE_GAP = 10
    _BADGE_PADDING_X = 7
    _BADGE_HEIGHT = 20

    def paint(self, painter, option, index) -> None:
        badge_text = str(index.data(SOURCE_BADGE_TEXT_ROLE) or "").strip()
        if not badge_text:
            super().paint(painter, option, index)
            return

        theme = get_theme()
        enabled = bool(index.flags() & Qt.ItemIsEnabled)
        hovered = bool(option.state & QStyle.State_MouseOver)
        selected = bool(option.state & QStyle.State_Selected)
        card_rect = option.rect.adjusted(
            self._OUTER_X,
            self._OUTER_Y,
            -self._OUTER_X,
            -self._OUTER_Y,
        )

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        if enabled and (hovered or selected):
            painter.setBrush(QColor(theme.bg_selected if selected else theme.bg_hover))
            painter.drawRoundedRect(card_rect, theme.radius_sm, theme.radius_sm)

        badge_font = QFont(option.font)
        badge_font.setPixelSize(SOURCE_BADGE_FONT_PX)
        badge_metrics = painter.fontMetrics() if badge_font == painter.font() else None
        painter.setFont(badge_font)
        if badge_metrics is None:
            badge_metrics = painter.fontMetrics()
        badge_width = badge_metrics.horizontalAdvance(badge_text) + (self._BADGE_PADDING_X * 2)
        badge_height = min(self._BADGE_HEIGHT, max(16, card_rect.height() - 8))
        badge_rect = QRect(
            max(card_rect.left() + self._CONTENT_X, card_rect.right() - badge_width - self._CONTENT_X + 1),
            card_rect.top() + ((card_rect.height() - badge_height) // 2),
            badge_width,
            badge_height,
        )

        badge_kind = str(index.data(SOURCE_BADGE_KIND_ROLE) or "neutral").strip()
        badge_fill, badge_color = _source_badge_colors(
            theme,
            badge_kind,
            enabled=enabled,
        )
        painter.setBrush(badge_fill)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(badge_rect, theme.radius_sm, theme.radius_sm)
        painter.setPen(badge_color)
        painter.drawText(badge_rect, Qt.AlignCenter, badge_text)

        text = str(index.data(Qt.DisplayRole) or "")
        text_rect = QRect(
            card_rect.left() + self._CONTENT_X,
            card_rect.top(),
            max(
                0,
                badge_rect.left()
                - self._BADGE_GAP
                - card_rect.left()
                - self._CONTENT_X,
            ),
            card_rect.height(),
        )
        painter.setFont(option.font)
        painter.setPen(QColor(theme.text_primary if enabled else theme.text_disabled))
        elided = painter.fontMetrics().elidedText(text, Qt.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, elided)
        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        badge_text = str(index.data(SOURCE_BADGE_TEXT_ROLE) or "").strip()
        if not badge_text:
            return super().sizeHint(option, index)

        base = super().sizeHint(option, index)
        badge_font = QFont(option.font)
        badge_font.setPixelSize(SOURCE_BADGE_FONT_PX)
        badge_width = option.fontMetrics.horizontalAdvance(badge_text) + (self._BADGE_PADDING_X * 2)
        text = str(index.data(Qt.DisplayRole) or "")
        text_width = option.fontMetrics.horizontalAdvance(text)
        width = (
            (self._OUTER_X * 2)
            + (self._CONTENT_X * 2)
            + text_width
            + self._BADGE_GAP
            + badge_width
        )
        return QSize(max(base.width(), width), max(base.height(), self._BADGE_HEIGHT + 8))


class StyledComboBox(QComboBox):
    popup_about_to_show = Signal()

    _id_counter = 0

    def __init__(self, parent=None, *, text_role: TextRole = TextRole.BODY):
        super().__init__(parent)

        self._text_role = TextRole(text_role)
        apply_text_role(self, self._text_role)
        self._style_initialized = False
        StyledComboBox._id_counter += 1
        combo_id = StyledComboBox._id_counter

        self.setObjectName(f"styled_combo_{combo_id}")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._popup_shell_name = f"combo_popup_shell_{combo_id}"
        self._popup_surface_name = f"combo_popup_surface_{combo_id}"

        view = QListView(self)
        view.setObjectName(f"combo_popup_{combo_id}")
        view.setAttribute(Qt.WA_StyledBackground, True)
        view.setFrameShape(QListView.NoFrame)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        view.setMouseTracking(True)
        view.setItemDelegate(_SourceBadgeItemDelegate(view))
        self.setView(view)

        self._popup_panel = ComboPopupPanel(
            self,
            view,
            object_name=self._popup_shell_name,
            surface_name=self._popup_surface_name,
        )
        self._popup_panel.item_activated.connect(self._on_popup_item_activated)
        self._popup_panel.dismissed.connect(self.update)
        self.destroyed.connect(self._popup_panel.deleteLater)
        # The popup view is reparented into an in-window surface, so relying on
        # QObject ancestry would make its font authority depend on popup chrome.
        # Its delegate receives this same font through QStyleOptionViewItem.
        view.setFont(self.font())

        self.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self._inline = False
        self._titlebar_mode = False
        self._editor_widget = None
        self._syncing_editor_geometry = False
        self._display_text_override: str | None = None
        self._outer_height_override: int | None = None
        apply_size_class(self, "md")

        self._style_initialized = True
        bind_theme(self, self._refresh_style)
        self._refresh_style()

    def setObjectName(self, name: str) -> None:  # noqa: N802 - Qt API contract
        previous_name = self.objectName()
        super().setObjectName(name)
        if getattr(self, "_style_initialized", False) and self.objectName() != previous_name:
            self._refresh_style()

    def set_full_width_mode(self, enabled: bool = True) -> None:
        """Use this combo as a stable full-row selector in a form layout."""
        if enabled:
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            self.setMinimumContentsLength(1)
        else:
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            self.setSizeAdjustPolicy(QComboBox.AdjustToContents)
            self.setMinimumContentsLength(0)
        self.setProperty("fullWidthMode", bool(enabled))
        self.updateGeometry()

    def set_outer_height(self, height: int) -> None:
        """Own an explicit final outer height for a component-specific rhythm."""

        resolved_height = max(1, int(height))
        self._outer_height_override = resolved_height
        self.setMinimumHeight(resolved_height)
        self.setMaximumHeight(resolved_height)
        self._refresh_style()

    def add_badged_item(
        self,
        text: str,
        user_data=None,
        *,
        badge_text: str,
        badge_kind: str = "neutral",
    ) -> int:
        """Add a real option whose source/category is rendered as a trailing badge."""

        self.addItem(text, user_data)
        index = self.count() - 1
        self.setItemData(index, str(badge_text or "").strip(), SOURCE_BADGE_TEXT_ROLE)
        self.setItemData(index, str(badge_kind or "neutral").strip(), SOURCE_BADGE_KIND_ROLE)
        return index

    @staticmethod
    def build_popup_container_qss(popup_id: str, theme) -> str:
        return f"""
            #{popup_id} {{
                background: transparent;
                border: none;
            }}
        """

    @staticmethod
    def build_popup_surface_qss(surface_id: str, theme) -> str:
        return f"""
            #{surface_id} {{
                background: {theme.bg_card};
                border: {theme.combo_popup_border_width}px solid {theme.border};
                border-radius: {theme.combo_popup_radius}px;
            }}
        """

    @staticmethod
    def build_popup_view_qss(view_id: str, theme) -> str:
        return f"""
            #{view_id} {{
                background: transparent;
                border: none;
                padding: {theme.combo_popup_padding}px;
                outline: none;
            }}
            #{view_id}::item {{
                padding: {theme.combo_popup_item_padding_y}px {theme.combo_popup_item_padding_x}px;
                color: {theme.text_primary};
            }}
            #{view_id}::item:hover {{
                background: {theme.bg_hover};
            }}
            #{view_id}::item:selected {{
                background: transparent;
                color: {theme.text_primary};
            }}
        """

    @staticmethod
    def build_combo_stylesheet(
        object_name: str,
        theme,
        *,
        outer_height: int | None = None,
    ) -> str:
        # QSS owns size hints and popup chrome; visible text geometry is
        # normalized in input_metrics so editable and static combos match.
        height_sm = int(outer_height or resolved_control_height(theme, "sm"))
        height_md = int(outer_height or resolved_control_height(theme, "md"))
        height_lg = int(outer_height or resolved_control_height(theme, "lg"))
        return f"""
            #{object_name} {{
                background: {theme.bg_input};
                color: {theme.text_primary};
                border: none;
                border-radius: {theme.input_radius}px;
                padding: {theme.input_padding_y}px {theme.input_padding_x}px;
                padding-right: {theme.combo_arrow_zone_width}px;
                selection-background-color: {theme.primary};
                selection-color: {theme.text_on_primary};
            }}
            #{object_name}:focus,
            #{object_name}:on {{
                background: {theme.bg_window};
            }}
            #{object_name}:disabled {{
                background: {theme.bg_hover};
                color: {theme.text_disabled};
            }}
            #{object_name}::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                border: none;
                width: {theme.combo_arrow_zone_width}px;
                border-top-right-radius: {theme.input_radius}px;
                border-bottom-right-radius: {theme.input_radius}px;
            }}
            #{object_name}::down-arrow {{
                width: {theme.combo_arrow_size}px;
                height: {theme.combo_arrow_size}px;
                image: none;
            }}
            #{object_name}[sizeClass="sm"] {{
                min-height: {height_sm}px;
                max-height: {height_sm}px;
                padding-top: 0px;
                padding-bottom: 0px;
            }}
            #{object_name}[sizeClass="md"] {{
                min-height: {height_md}px;
                max-height: {height_md}px;
                padding-top: 0px;
                padding-bottom: 0px;
            }}
            #{object_name}[sizeClass="lg"] {{
                min-height: {height_lg}px;
                max-height: {height_lg}px;
                padding-top: 0px;
                padding-bottom: 0px;
            }}
            #{object_name}[inline="true"] {{
                background: transparent;
                border: none;
                padding: 0 14px 0 2px;
                min-height: {theme.control_height_md}px;
                max-height: {theme.control_height_md}px;
                color: {theme.text_secondary};
            }}
            #{object_name}[inline="true"]:hover {{
                color: {theme.primary};
            }}
            #{object_name}[inline="true"]:focus,
            #{object_name}[inline="true"]:on {{
                background: transparent;
                color: {theme.primary};
            }}
            #{object_name}[inline="true"]:disabled {{
                background: transparent;
                color: {theme.text_disabled};
            }}
            #{object_name}[inline="true"]::drop-down {{
                width: 14px;
            }}
            #{object_name}[titlebarMode="true"] {{
                background: transparent;
                border: none;
                padding: 0px;
                padding-right: 0px;
                min-height: 28px;
                max-height: 28px;
            }}
            #{object_name}[titlebarMode="true"]::drop-down {{
                border: none;
                width: 26px;
            }}
        """

    @staticmethod
    def build_editor_stylesheet(theme) -> str:
        return build_input_editor_stylesheet(theme)

    def setEditable(self, editable: bool) -> None:
        super().setEditable(editable)
        if editable:
            self._configure_editor()
        else:
            self._release_editor_filter()

    def _configure_editor(self) -> None:
        line_edit = self.lineEdit()
        if line_edit is None:
            return

        configure_input_line_edit(
            line_edit,
            get_theme(),
            stylesheet=self.build_editor_stylesheet(get_theme()),
            text_role=self._text_role,
        )
        if self._editor_widget is not line_edit:
            self._release_editor_filter()
            self._editor_widget = line_edit
            line_edit.installEventFilter(self)
        self._sync_editor_geometry()

    def _release_editor_filter(self) -> None:
        if self._editor_widget is None:
            return
        try:
            self._editor_widget.removeEventFilter(self)
        except RuntimeError:
            pass
        self._editor_widget = None

    def _sync_editor_geometry(self) -> None:
        line_edit = self.lineEdit()
        if line_edit is None:
            return
        if self._syncing_editor_geometry:
            return

        self._syncing_editor_geometry = True
        try:
            sync_input_line_edit_geometry(
                self,
                line_edit,
                button_width=get_theme().combo_arrow_zone_width,
                theme=get_theme(),
            )
        finally:
            self._syncing_editor_geometry = False

    def _input_text_rect(self) -> QRect:
        return input_text_rect(
            self.width(),
            self.height(),
            button_width=get_theme().combo_arrow_zone_width,
            theme=get_theme(),
        )

    def set_display_text_override(self, text: str | None) -> None:
        normalized = str(text or "").strip()
        self._display_text_override = normalized or None
        self.update()

    def display_text(self) -> str:
        return self._display_text_override or self.currentText()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.isEditable():
            self._sync_editor_geometry()

    def eventFilter(self, watched, event) -> bool:
        if watched is self._editor_widget and event.type() in {QEvent.Move, QEvent.Resize, QEvent.Show}:
            self._sync_editor_geometry()
        return super().eventFilter(watched, event)

    def showPopup(self):
        if self._popup_panel.isVisible():
            self.hidePopup()
            return
        self.popup_about_to_show.emit()
        geometry = self._popup_geometry_in_window()
        if geometry.width() <= 0 or geometry.height() <= 0:
            return
        self._popup_panel.open_for_combo(geometry)
        self.update()

    def hidePopup(self):
        self._popup_panel.close_panel()
        self.update()

    def _popup_content_height(self) -> int:
        view = self.view()
        model = view.model()
        if model is None:
            return max(1, self.height())

        view.doItemsLayout()
        visible_rows = min(self.maxVisibleItems(), model.rowCount())
        if visible_rows <= 0:
            return max(1, self.height())

        minimum_row_height = self.fontMetrics().height() + (get_theme().combo_popup_item_padding_y * 2)
        rows_height = sum(max(view.sizeHintForRow(row), minimum_row_height) for row in range(visible_rows))
        chrome_height = view.contentsMargins().top() + view.contentsMargins().bottom()
        if visible_rows == 1:
            chrome_height -= view.contentsMargins().bottom()
        surface_border = get_theme().combo_popup_border_width * 2
        return max(1, rows_height + chrome_height + surface_border)

    def _popup_content_width(self) -> int:
        view = self.view()
        model = view.model()
        if model is None:
            return max(1, self.width())

        theme = get_theme()
        content_width = max(0, view.sizeHintForColumn(0))
        if content_width <= 0:
            font_metrics = view.fontMetrics()
            for row in range(model.rowCount()):
                index = model.index(row, self.modelColumn())
                text = str(index.data(Qt.DisplayRole) or "")
                content_width = max(
                    content_width,
                    font_metrics.horizontalAdvance(text) + (theme.combo_popup_item_padding_x * 2),
                )

        chrome_width = view.contentsMargins().left() + view.contentsMargins().right()
        chrome_width += theme.combo_popup_border_width * 2
        if 0 < self.maxVisibleItems() < model.rowCount():
            chrome_width += view.verticalScrollBar().sizeHint().width()
        return max(1, content_width + chrome_width)

    def _popup_geometry_in_window(self) -> QRect:
        root = self.window()
        if root is None:
            return QRect()
        root_rect = root.rect()
        if root_rect.width() <= 0 or root_rect.height() <= 0:
            return QRect()

        offset_y = get_theme().combo_popup_offset_y
        min_popup_height = max(1, min(24, root_rect.height()))
        width = max(1, min(max(self.width(), self._popup_content_width()), root_rect.width()))
        height = max(min_popup_height, min(self._popup_content_height(), root_rect.height()))

        below = self.mapTo(root, QPoint(0, self.height() + offset_y))
        x = max(0, min(below.x(), max(0, root_rect.width() - width)))
        below_y = max(0, below.y())
        space_below = max(0, root_rect.height() - below_y)

        above_anchor = self.mapTo(root, QPoint(0, -offset_y)).y()
        space_above = max(0, above_anchor)

        if space_below >= height or space_below >= space_above:
            y = max(0, min(below_y, max(0, root_rect.height() - min_popup_height)))
            height = min(height, max(min_popup_height, root_rect.height() - y))
        else:
            height = min(height, max(min_popup_height, space_above))
            y = max(0, above_anchor - height)

        return QRect(x, y, width, height)

    def _on_popup_item_activated(self, row: int) -> None:
        if not 0 <= row < self.count():
            return
        model_index = self.model().index(row, self.modelColumn())
        flags = model_index.flags()
        if not (flags & Qt.ItemIsEnabled and flags & Qt.ItemIsSelectable):
            return
        self.setCurrentIndex(row)
        self.hidePopup()

    def _refresh_style(self) -> None:
        theme = get_theme()

        font = apply_text_role(self, self._text_role)
        self.view().setFont(font)

        self.setStyleSheet(
            self.build_combo_stylesheet(
                self.objectName(),
                theme,
                outer_height=self._outer_height_override,
            )
        )
        self.view().setStyleSheet(self.build_popup_view_qss(self.view().objectName(), theme))
        self._popup_panel.setStyleSheet(self.build_popup_container_qss(self._popup_shell_name, theme))
        self._popup_panel.surface().setStyleSheet(
            self.build_popup_surface_qss(self._popup_surface_name, theme)
        )

        viewport = self.view().viewport()
        viewport.setAttribute(Qt.WA_StyledBackground, True)
        viewport.setAutoFillBackground(False)
        viewport.setStyleSheet("background: transparent; border: none;")

        if self.isEditable():
            self._configure_editor()

        if self._popup_panel.isVisible():
            self._popup_panel.reposition()
        self.updateGeometry()
        self.update()

    def set_text_role(self, role: TextRole) -> None:
        """Select a semantic font role for the control, editor, and popup."""

        resolved_role = TextRole(role)
        if resolved_role == self._text_role:
            return
        self._text_role = resolved_role
        self._refresh_style()

    def set_inline(self, inline: bool = True) -> None:
        """Enable borderless inline mode — WPS-style unit selector."""
        self._inline = inline
        self.setProperty("inline", "true" if inline else "false")
        style = self.style()
        if style:
            style.unpolish(self)
            style.polish(self)
        self._refresh_style()

    def set_titlebar_mode(self, enabled: bool = True) -> None:
        """Render as a compact chrome selector for the custom title bar."""
        self._titlebar_mode = bool(enabled)
        self.setProperty("titlebarMode", "true" if self._titlebar_mode else "false")
        if self._titlebar_mode:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()
        style = self.style()
        if style:
            style.unpolish(self)
            style.polish(self)
        self._refresh_style()

    def paintEvent(self, event):
        if self._inline:
            self._paint_inline_combo()
            return
        if self._titlebar_mode:
            self._paint_titlebar_combo()
            return

        theme = get_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        active = self.hasFocus() or self._popup_panel.isVisible()
        draw_input_surface(
            painter,
            self.width(),
            self.height(),
            theme=theme,
            enabled=self.isEnabled(),
            active=active,
            button_width=theme.combo_arrow_zone_width,
        )

        if not self.isEditable():
            self._paint_current_text(painter, self._input_text_rect(), theme=theme)
        draw_combo_chevron(
            painter,
            self.width(),
            self.height(),
            theme=theme,
            enabled=self.isEnabled(),
            active=active,
        )
        painter.end()

    def _paint_current_text(self, painter: QPainter, rect: QRect, *, theme) -> None:
        text = self.display_text()
        if not text:
            return
        painter.setFont(self.font())
        painter.setPen(input_text_color(theme, enabled=self.isEnabled()))
        badge_text = ""
        badge_kind = "neutral"
        if self.currentIndex() >= 0 and self._display_text_override is None:
            badge_text = str(self.currentData(SOURCE_BADGE_TEXT_ROLE) or "").strip()
            badge_kind = str(self.currentData(SOURCE_BADGE_KIND_ROLE) or "neutral").strip()

        text_rect = QRect(rect)
        if badge_text:
            badge_font = QFont(self.font())
            badge_font.setPixelSize(SOURCE_BADGE_FONT_PX)
            painter.setFont(badge_font)
            badge_width = painter.fontMetrics().horizontalAdvance(badge_text) + 14
            badge_height = min(20, max(16, rect.height() - 12))
            badge_rect = QRect(
                max(
                    rect.left(),
                    rect.right() - CURRENT_BADGE_RIGHT_INSET - badge_width + 1,
                ),
                rect.top() + ((rect.height() - badge_height) // 2),
                badge_width,
                badge_height,
            )
            badge_fill, badge_color = _source_badge_colors(
                theme,
                badge_kind,
                enabled=self.isEnabled(),
            )
            painter.setPen(Qt.NoPen)
            painter.setBrush(badge_fill)
            painter.drawRoundedRect(badge_rect, theme.radius_sm, theme.radius_sm)
            painter.setPen(badge_color)
            painter.drawText(badge_rect, Qt.AlignCenter, badge_text)
            text_rect.setRight(max(text_rect.left(), badge_rect.left() - 9))

        painter.setFont(self.font())
        painter.setPen(input_text_color(theme, enabled=self.isEnabled()))
        elided = painter.fontMetrics().elidedText(text, Qt.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, elided)

    def _paint_inline_combo(self) -> None:
        theme = get_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if not self.isEditable():
            text_rect = QRect(2, 0, max(0, self.width() - 16), max(0, self.height()))
            self._paint_current_text(painter, text_rect, theme=theme)

        active = self.hasFocus() or self._popup_panel.isVisible()
        arrow_color = QColor(theme.primary if active else theme.text_hint)
        if not self.isEnabled():
            arrow_color = QColor(theme.text_disabled)
        painter.setPen(stroke_pen(painter, arrow_color, STROKE_ICON))
        zone_x = self.width() - 10
        cy = self.height() // 2
        half = 3
        painter.drawLine(zone_x - half, cy - 1, zone_x, cy + half - 1)
        painter.drawLine(zone_x, cy + half - 1, zone_x + half, cy - 1)
        painter.end()

    def _paint_titlebar_combo(self) -> None:
        theme = get_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = max(0, self.width())
        height = max(0, self.height())
        expanded = self._popup_panel.isVisible()
        focused = self.hasFocus()
        hovered = self.underMouse()
        radius = min(8.0, max(4.0, height / 2.0))

        fill = QColor(theme.bg_card)
        fill.setAlpha(245 if expanded else 180 if hovered or focused else 125)
        if not self.isEnabled():
            fill = QColor(theme.bg_hover)
            fill.setAlpha(150)

        border = QColor(theme.primary if expanded else theme.border_light)
        border.setAlpha(180 if expanded else 150 if hovered or focused else 95)
        border_width = 1.2 if expanded else 1.0
        half_border = border_width / 2.0
        rect = QRectF(
            half_border,
            half_border,
            max(0.0, float(width) - border_width),
            max(0.0, float(height) - border_width),
        )

        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, radius, radius)
        painter.setPen(stroke_pen(painter, border, border_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)

        if not self.isEditable():
            text_rect = QRect(12, 0, max(0, width - 40), height)
            self._paint_current_text(painter, text_rect, theme=theme)

        arrow_color = QColor(theme.primary if expanded else theme.text_secondary)
        if not self.isEnabled():
            arrow_color = QColor(theme.text_disabled)
        painter.setPen(stroke_pen(painter, arrow_color, STROKE_ICON))
        zone_center_x = width - 18
        zone_center_y = height // 2
        half = 4
        painter.drawLine(zone_center_x - half, zone_center_y - 2, zone_center_x, zone_center_y + 2)
        painter.drawLine(zone_center_x, zone_center_y + 2, zone_center_x + half, zone_center_y - 2)
        painter.end()
