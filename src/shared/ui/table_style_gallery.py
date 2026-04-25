"""Compact visual controls for color table presets."""

from __future__ import annotations

from src.config.table_style_presets import (
    COLOR_TABLE_PALETTES,
    COLOR_TABLE_VARIANTS,
    ColorTablePalette,
    ColorTableVariant,
    color_palette,
    color_variant,
)
from src.qt_api import (
    QAbstractButton,
    QButtonGroup,
    QColor,
    QHBoxLayout,
    QLabel,
    QPainter,
    QPen,
    QRectF,
    QSize,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from src.shared.ui.theme import bind_theme, get_theme


class ColorDotButton(QAbstractButton):
    def __init__(self, palette: ColorTablePalette, parent=None):
        super().__init__(parent)
        self.palette = palette
        self.setCheckable(True)
        self.setToolTip(palette.label)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(26, 26)
        bind_theme(self, self.update)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        theme = get_theme()
        rect = QRectF(4, 4, self.width() - 8, self.height() - 8)
        painter.setPen(QPen(QColor(theme.primary if self.isChecked() else theme.border), 2))
        painter.setBrush(QColor(f"#{self.palette.accent}"))
        painter.drawEllipse(rect)
        if self.isChecked():
            painter.setPen(QPen(QColor("#FFFFFF" if self.palette.header_text == "FFFFFF" else "#1F2933"), 2))
            painter.drawLine(10, 14, 13, 17)
            painter.drawLine(13, 17, 19, 10)


class TableStylePreviewButton(QAbstractButton):
    def __init__(self, variant: ColorTableVariant, parent=None):
        super().__init__(parent)
        self.variant = variant
        self._palette = color_palette("blue")
        self.setCheckable(True)
        self.setToolTip(variant.label)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumSize(self.minimumSizeHint())
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bind_theme(self, self.update)

    def set_palette(self, palette_key: str) -> None:
        self._palette = color_palette(palette_key)
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(220, 88)

    def minimumSizeHint(self) -> QSize:
        return QSize(168, 84)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        theme = get_theme()
        outer = QRectF(1.5, 1.5, self.width() - 3, self.height() - 3)
        painter.setPen(QPen(QColor(theme.border_light), 1))
        painter.setBrush(QColor(theme.bg_card))
        painter.drawRoundedRect(outer, 7, 7)
        if self.isChecked():
            painter.setPen(QPen(QColor(theme.primary), 2))
            painter.setBrush(QColor(theme.bg_selected))
            painter.drawRoundedRect(outer, 8, 8)

        table_rect = outer.adjusted(10, 10, -10, -10)
        rows = 5
        cols = 5
        row_h = table_rect.height() / rows
        col_w = table_rect.width() / cols
        accent = QColor(f"#{self._palette.accent}")
        light = QColor(f"#{self._palette.accent_light}")
        soft = QColor(f"#{self._palette.accent_soft}")
        text = QColor("#6B7280")
        paper = QColor("#FFFFFF")

        painter.setPen(Qt.NoPen)
        painter.setBrush(paper)
        painter.drawRect(table_rect)

        if self.variant.zebra:
            painter.setBrush(soft)
            for row in range(1, rows, 2):
                painter.drawRect(QRectF(table_rect.left(), table_rect.top() + row * row_h, table_rect.width(), row_h))

        if self.variant.header_fill:
            painter.setBrush(accent)
            painter.drawRect(QRectF(table_rect.left(), table_rect.top(), table_rect.width(), row_h))

        pen_accent = QPen(accent, 1.15)
        pen_light = QPen(light, 0.8)
        if self.variant.header_rule_only:
            painter.setPen(QPen(accent, 1.45))
            painter.drawLine(table_rect.left(), table_rect.top(), table_rect.right(), table_rect.top())
            painter.drawLine(table_rect.left(), table_rect.top() + row_h, table_rect.right(), table_rect.top() + row_h)
            painter.drawLine(table_rect.left(), table_rect.bottom(), table_rect.right(), table_rect.bottom())
        elif self.variant.show_horizontal:
            painter.setPen(pen_accent)
            painter.drawLine(table_rect.left(), table_rect.top(), table_rect.right(), table_rect.top())
            painter.drawLine(table_rect.left(), table_rect.bottom(), table_rect.right(), table_rect.bottom())
            painter.setPen(pen_light)
            for row in range(1, rows):
                y = table_rect.top() + row * row_h
                painter.drawLine(table_rect.left(), y, table_rect.right(), y)

        if self.variant.show_vertical:
            painter.setPen(pen_accent)
            painter.drawLine(table_rect.left(), table_rect.top(), table_rect.left(), table_rect.bottom())
            painter.drawLine(table_rect.right(), table_rect.top(), table_rect.right(), table_rect.bottom())
            painter.setPen(pen_light)
            for col in range(1, cols):
                x = table_rect.left() + col * col_w
                painter.drawLine(x, table_rect.top(), x, table_rect.bottom())

        painter.setPen(QPen(QColor("#FFFFFF") if self.variant.header_fill else accent, 1.35))
        for row in range(rows):
            for col in range(cols):
                x1 = table_rect.left() + col * col_w + col_w * 0.22
                x2 = table_rect.left() + col * col_w + col_w * 0.78
                y = table_rect.top() + row * row_h + row_h * 0.55
                if row > 0:
                    painter.setPen(QPen(text, 1.05))
                painter.drawLine(x1, y, x2, y)


class _PreviewGridHost(QWidget):
    def __init__(self, *, card_spacing: int, row_spacing: int, top_margin: int, parent=None):
        super().__init__(parent)
        self._card_spacing = card_spacing
        self._row_spacing = row_spacing
        self._top_margin = top_margin
        self._columns = 2
        self._buttons: dict[str, TableStylePreviewButton] = {}
        self._order: list[str] = []
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def add_button(self, key: str, button: TableStylePreviewButton) -> None:
        self._buttons[key] = button
        self._order.append(key)
        button.setParent(self)
        self._layout_buttons()

    def set_columns(self, columns: int) -> None:
        columns = 4 if columns >= 4 else 2 if columns >= 2 else 1
        if columns == self._columns:
            return
        self._columns = columns
        self._layout_buttons()

    def columns(self) -> int:
        return self._columns

    def sizeHint(self) -> QSize:
        return QSize(self._preferred_width_for_columns(self._columns), self._height_for_columns(self._columns))

    def minimumSizeHint(self) -> QSize:
        return QSize(self._minimum_width_for_columns(1), self._height_for_columns(self._columns))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._height_for_columns(self._columns)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_buttons()

    def _button_size(self) -> QSize:
        button = next(iter(self._buttons.values()), None)
        return button.sizeHint() if button is not None else QSize(220, 88)

    def _minimum_button_size(self) -> QSize:
        button = next(iter(self._buttons.values()), None)
        return button.minimumSizeHint() if button is not None else QSize(168, 84)

    def _preferred_width_for_columns(self, columns: int) -> int:
        size = self._button_size()
        return columns * size.width() + max(0, columns - 1) * self._card_spacing

    def _minimum_width_for_columns(self, columns: int) -> int:
        size = self._minimum_button_size()
        return columns * size.width() + max(0, columns - 1) * self._card_spacing

    def _height_for_columns(self, columns: int) -> int:
        if not self._order:
            return 0
        size = self._button_size()
        rows = (len(self._order) + max(1, columns) - 1) // max(1, columns)
        return self._top_margin + rows * size.height() + max(0, rows - 1) * self._row_spacing

    def _layout_buttons(self) -> None:
        columns = max(1, self._columns)
        preferred = self._button_size()
        minimum = self._minimum_button_size()
        available_width = max(self.width(), self._minimum_width_for_columns(columns))
        spacing = self._card_spacing
        total_spacing = max(0, columns - 1) * spacing
        card_width = max(minimum.width(), (available_width - total_spacing) // columns)
        spare_width = max(0, available_width - total_spacing - card_width * columns)
        card_height = preferred.height()
        x = 0
        for index, key in enumerate(self._order):
            button = self._buttons[key]
            row = index // columns
            col = index % columns
            width = card_width + (1 if col < spare_width else 0)
            button.setGeometry(
                x,
                self._top_margin + row * (card_height + self._row_spacing),
                width,
                card_height,
            )
            button.show()
            if col == columns - 1:
                x = 0
            else:
                x += width + spacing
        height = self._height_for_columns(columns)
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)
        self.updateGeometry()


class ColorTableGallery(QWidget):
    selection_changed = Signal(str, str)

    _ROW_SPACING = 4
    _DOT_SPACING = 8
    _CARD_SPACING = 12
    _GRID_MARGIN_TOP = 2

    def __init__(self, parent=None, *, label_width: int | None = None):
        super().__init__(parent)
        self._is_syncing = False
        self._current_columns = 0
        self._label_width_override = label_width
        self._resolved_label_width = label_width or get_theme().form_row_label_width
        self._palette_buttons: dict[str, ColorDotButton] = {}
        self._variant_buttons: dict[str, TableStylePreviewButton] = {}
        self._palette_group = QButtonGroup(self)
        self._variant_group = QButtonGroup(self)
        self._palette_group.setExclusive(True)
        self._variant_group.setExclusive(True)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        self._selector_row = QWidget(self)
        selector_layout = QHBoxLayout(self._selector_row)
        selector_layout.setContentsMargins(0, 2, 0, 2)
        selector_layout.setSpacing(self._ROW_SPACING)

        self._label = QLabel("颜色表格", self._selector_row)
        self._label.setObjectName("color_table_gallery_label")
        self._label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        selector_layout.addWidget(self._label)

        self._dots_host = QWidget(self._selector_row)
        dots_layout = QHBoxLayout(self._dots_host)
        dots_layout.setContentsMargins(0, 0, 0, 0)
        dots_layout.setSpacing(self._DOT_SPACING)
        for palette in COLOR_TABLE_PALETTES:
            button = ColorDotButton(palette, self._dots_host)
            button.clicked.connect(self._emit_selection)
            self._palette_group.addButton(button)
            self._palette_buttons[palette.key] = button
            dots_layout.addWidget(button)
        dots_layout.addStretch(1)
        selector_layout.addWidget(self._dots_host, 1)
        root.addWidget(self._selector_row)

        self._preview_row = QWidget(self)
        self._preview_row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        preview_layout = QHBoxLayout(self._preview_row)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(self._ROW_SPACING)

        self._preview_gutter = QWidget(self._preview_row)
        self._preview_gutter.setFixedWidth(self._resolved_label_width)
        preview_layout.addWidget(self._preview_gutter)

        self._grid_host = _PreviewGridHost(
            card_spacing=self._CARD_SPACING,
            row_spacing=10,
            top_margin=self._GRID_MARGIN_TOP,
            parent=self._preview_row,
        )
        preview_layout.addWidget(self._grid_host, 1)
        root.addWidget(self._preview_row)

        for index, variant in enumerate(COLOR_TABLE_VARIANTS):
            button = TableStylePreviewButton(variant, self._grid_host)
            button.clicked.connect(self._emit_selection)
            self._variant_group.addButton(button)
            self._variant_buttons[variant.key] = button
            self._grid_host.add_button(variant.key, button)

        self._relayout_variants(2)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

        self.set_selection("blue", "header_grid")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout_variants(self._columns_for_width(event.size().width()))

    def minimumSizeHint(self) -> QSize:
        return QSize(self._row_width_for_columns(1), self._natural_height_for_columns(self._current_columns or 1))

    def sizeHint(self) -> QSize:
        columns = self._current_columns or 4
        return QSize(self._row_width_for_columns(columns), self._natural_height_for_columns(columns))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._natural_height_for_columns(self._columns_for_width(width))

    def set_selection(self, palette_key: str, variant_key: str) -> None:
        self._is_syncing = True
        try:
            palette = color_palette(palette_key)
            variant = color_variant(variant_key)
            self._palette_buttons[palette.key].setChecked(True)
            self._variant_buttons[variant.key].setChecked(True)
            for button in self._variant_buttons.values():
                button.set_palette(palette.key)
        finally:
            self._is_syncing = False

    def selected_palette(self) -> str:
        for key, button in self._palette_buttons.items():
            if button.isChecked():
                return key
        return "blue"

    def selected_variant(self) -> str:
        for key, button in self._variant_buttons.items():
            if button.isChecked():
                return key
        return "header_grid"

    def _emit_selection(self) -> None:
        palette_key = self.selected_palette()
        for button in self._variant_buttons.values():
            button.set_palette(palette_key)
        if not self._is_syncing:
            self.selection_changed.emit(palette_key, self.selected_variant())

    def _relayout_variants(self, columns: int) -> None:
        columns = 4 if columns >= 4 else 2 if columns >= 2 else 1
        if columns == self._current_columns:
            self._sync_natural_height()
            return
        self._current_columns = columns
        self._grid_host.set_columns(columns)
        self._sync_natural_height()
        self.updateGeometry()

    def _columns_for_width(self, width: int) -> int:
        content_width = max(0, width - self._resolved_label_width - self._ROW_SPACING)
        if content_width >= self._grid_minimum_width_for_columns(4):
            return 4
        if content_width >= self._grid_minimum_width_for_columns(2):
            return 2
        return 1

    def _grid_preferred_width_for_columns(self, columns: int) -> int:
        sample = next(iter(self._variant_buttons.values()), None)
        if sample is None:
            return 0
        return columns * sample.sizeHint().width() + max(0, columns - 1) * self._CARD_SPACING

    def _grid_minimum_width_for_columns(self, columns: int) -> int:
        sample = next(iter(self._variant_buttons.values()), None)
        if sample is None:
            return 0
        return columns * sample.minimumSizeHint().width() + max(0, columns - 1) * self._CARD_SPACING

    def _row_width_for_columns(self, columns: int) -> int:
        return self._resolved_label_width + self._ROW_SPACING + self._grid_minimum_width_for_columns(columns)

    def _natural_height_for_columns(self, columns: int) -> int:
        root_spacing = self.layout().spacing() if self.layout() is not None else 4
        selector_height = self._selector_row.sizeHint().height()
        return selector_height + root_spacing + self._grid_host._height_for_columns(max(1, columns))

    def _sync_natural_height(self) -> None:
        height = self._natural_height_for_columns(self._current_columns or 1)
        preview_height = self._grid_host.sizeHint().height()
        self._preview_row.setMinimumHeight(preview_height)
        self._preview_row.setMaximumHeight(preview_height)
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._resolved_label_width = self._label_width_override or theme.form_row_label_width
        self._label.setFixedWidth(self._resolved_label_width)
        self._preview_gutter.setFixedWidth(self._resolved_label_width)
        self._label.setStyleSheet(f"font-size: {theme.font_size_md}px; color: {theme.text_primary};")
        self._relayout_variants(self._columns_for_width(self.width()))
        self._sync_natural_height()
        self.update()


__all__ = ["ColorDotButton", "ColorTableGallery", "TableStylePreviewButton"]
