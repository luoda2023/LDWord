"""
Shared combo-box foundation with themed popup shell styling.
"""

from __future__ import annotations

from src.qt_api import QComboBox, QFrame, QListView, QSizeGrip, QStyledItemDelegate, QColor, QPainter, QPen, QTimer, Qt

from src.shared.ui.theme import bind_theme, get_theme

# PySide6 popup shells can briefly report `maximumHeight() == 0` after
# `super().showPopup()`. If we lock width before releasing that cap, the popup
# can collapse to 0px high even though Qt already created the menu items.
_QT_WIDGETSIZE_MAX = 16777215


class StyledComboBox(QComboBox):
    _id_counter = 0

    def __init__(self, parent=None):
        super().__init__(parent)

        StyledComboBox._id_counter += 1
        combo_id = StyledComboBox._id_counter

        self.setObjectName(f"styled_combo_{combo_id}")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._popup_shell_name = f"combo_popup_shell_{combo_id}"
        self._popup_shell_qss = ""

        view = QListView(self)
        view.setObjectName(f"combo_popup_{combo_id}")
        view.setItemDelegate(QStyledItemDelegate(view))
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        view.setFrameShape(QFrame.NoFrame)
        self.setView(view)

        popup = view.window()
        popup.setObjectName(self._popup_shell_name)
        popup.setContentsMargins(0, 0, 0, 0)
        if hasattr(popup, "setFrameShape"):
            popup.setFrameShape(QFrame.NoFrame)
        popup.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        popup.setAttribute(Qt.WA_StyledBackground, True)
        popup.setAttribute(Qt.WA_TranslucentBackground, False)
        popup.setAutoFillBackground(False)

        self.setSizeAdjustPolicy(QComboBox.AdjustToContents)

        bind_theme(self, self._refresh_style)
        self._refresh_style()

    @staticmethod
    def build_popup_container_qss(popup_id: str, theme) -> str:
        return f"""
            #{popup_id} {{
                background: {theme.bg_card};
                border: 1px solid {theme.border};
                border-radius: {theme.combo_popup_radius}px;
            }}
        """

    @staticmethod
    def build_popup_view_qss(view_id: str, theme) -> str:
        return f"""
            #{view_id} {{
                background: {theme.bg_card};
                border: none;
                padding: {theme.combo_popup_padding}px;
                outline: none;
            }}
            #{view_id}::item {{
                padding: {theme.combo_popup_item_padding_y}px {theme.combo_popup_item_padding_x}px;
                border-radius: {theme.radius_sm}px;
                color: {theme.text_primary};
            }}
            #{view_id}::item:hover {{
                background: {theme.bg_hover};
            }}
            #{view_id}::item:selected {{
                background: {theme.bg_selected};
                color: {theme.text_primary};
            }}
        """

    @staticmethod
    def build_combo_stylesheet(object_name: str, theme) -> str:
        return f"""
            #{object_name} {{
                background: {theme.bg_input};
                color: {theme.text_primary};
                border: 1px solid {theme.border};
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
                border-color: {theme.border_focus};
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
        """

    @staticmethod
    def build_editor_stylesheet(theme) -> str:
        return f"""
            QLineEdit {{
                border: none;
                background: transparent;
                color: {theme.text_primary};
                selection-background-color: {theme.primary};
                selection-color: {theme.text_on_primary};
                padding: 0;
                font-size: {theme.font_size_md}px;
            }}
        """

    def showPopup(self):
        super().showPopup()

        popup = self.view().window()
        popup.setStyleSheet(self._popup_shell_qss)

        for grip in popup.findChildren(QSizeGrip):
            grip.hide()

        QTimer.singleShot(0, self._sync_popup_geometry)

    def _sync_popup_geometry(self) -> None:
        popup = self.view().window()
        self._release_popup_height_constraint(popup)
        popup.setFixedWidth(self.width())
        popup.setFixedHeight(self._popup_content_height())
        self._position_popup_below_combo(popup)

    def _release_popup_height_constraint(self, popup) -> None:
        if popup.maximumHeight() == 0:
            popup.setMinimumHeight(0)
            popup.setMaximumHeight(_QT_WIDGETSIZE_MAX)

    def _popup_content_height(self) -> int:
        view = self.view()
        model = view.model()
        if model is None:
            return self.height()

        view.doItemsLayout()

        visible_rows = min(self.maxVisibleItems(), model.rowCount())
        if visible_rows <= 0:
            return self.height()

        minimum_row_height = self.fontMetrics().height() + (get_theme().combo_popup_item_padding_y * 2)
        rows_height = sum(max(view.sizeHintForRow(row), minimum_row_height) for row in range(visible_rows))
        chrome_height = view.contentsMargins().top() + view.contentsMargins().bottom()
        return rows_height + chrome_height

    def _position_popup_below_combo(self, popup) -> None:
        pos = self.mapToGlobal(self.rect().bottomLeft())
        popup.move(pos.x(), pos.y() + get_theme().combo_popup_offset_y)

    def _refresh_style(self) -> None:
        theme = get_theme()
        popup = self.view().window()

        self._popup_shell_qss = self.build_popup_container_qss(self._popup_shell_name, theme)
        self.setStyleSheet(self.build_combo_stylesheet(self.objectName(), theme))
        self.view().setStyleSheet(self.build_popup_view_qss(self.view().objectName(), theme))
        popup.setStyleSheet(self._popup_shell_qss)
        if self.isEditable() and self.lineEdit() is not None:
            self.lineEdit().setStyleSheet(self.build_editor_stylesheet(theme))

    def paintEvent(self, event):
        super().paintEvent(event)

        theme = get_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(
            QPen(
                QColor(theme.border_focus if self.hasFocus() else theme.text_hint),
                1.5,
            )
        )

        zone_center_x = self.width() - (theme.combo_arrow_zone_width // 2)
        zone_center_y = self.height() // 2
        half = max(2, theme.combo_arrow_size // 2)
        painter.drawLine(zone_center_x - half, zone_center_y - 1, zone_center_x, zone_center_y + half - 1)
        painter.drawLine(zone_center_x, zone_center_y + half - 1, zone_center_x + half, zone_center_y - 1)
        painter.end()
