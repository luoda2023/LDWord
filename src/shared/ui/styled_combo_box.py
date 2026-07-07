"""
Shared combo-box foundation with an anchored in-window popup panel.
"""

from __future__ import annotations

from src.qt_api import QComboBox, QListView, QPoint, QRect, QColor, QEvent, QPainter, QPen, QSizePolicy, Signal, Qt

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
from src.shared.ui.sizing import apply_size_class, resolved_control_height
from src.shared.ui.theme import bind_theme, get_theme


class StyledComboBox(QComboBox):
    popup_about_to_show = Signal()

    _id_counter = 0

    def __init__(self, parent=None):
        super().__init__(parent)

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

        self.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self._inline = False
        self._editor_widget = None
        self._syncing_editor_geometry = False
        self._display_text_override: str | None = None
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
    def build_combo_stylesheet(object_name: str, theme) -> str:
        # QSS owns size hints and popup chrome; visible text geometry is
        # normalized in input_metrics so editable and static combos match.
        height_sm = resolved_control_height(theme, "sm")
        height_md = resolved_control_height(theme, "md")
        height_lg = resolved_control_height(theme, "lg")
        return f"""
            #{object_name} {{
                background: {theme.bg_input};
                color: {theme.text_primary};
                border: none;
                border-radius: {theme.input_radius}px;
                padding: {theme.input_padding_y}px {theme.input_padding_x}px;
                padding-right: {theme.combo_arrow_zone_width}px;
                font-size: {theme.font_size_md}px;
                font-family: {theme.font_family};
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
                font-size: {theme.font_size_md}px;
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
        if 0 <= row < self.count():
            self.setCurrentIndex(row)
        self.hidePopup()

    def _refresh_style(self) -> None:
        theme = get_theme()

        self.setStyleSheet(self.build_combo_stylesheet(self.objectName(), theme))
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

    def set_inline(self, inline: bool = True) -> None:
        """Enable borderless inline mode — WPS-style unit selector."""
        self._inline = inline
        self.setProperty("inline", "true" if inline else "false")
        style = self.style()
        if style:
            style.unpolish(self)
            style.polish(self)
        self._refresh_style()

    def paintEvent(self, event):
        if self._inline:
            self._paint_inline_combo()
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
        elided = painter.fontMetrics().elidedText(text, Qt.ElideRight, rect.width())
        painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, elided)

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
        painter.setPen(QPen(arrow_color, 1.5))
        zone_x = self.width() - 10
        cy = self.height() // 2
        half = 3
        painter.drawLine(zone_x - half, cy - 1, zone_x, cy + half - 1)
        painter.drawLine(zone_x, cy + half - 1, zone_x + half, cy - 1)
        painter.end()
