"""Shared summary grid for compact configuration overviews."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.qt_api import QColor, QFont, QGridLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget, Qt

from src.shared.ui.theme import bind_theme, get_theme


def _rgba(color_value: str, alpha: int) -> str:
    color = QColor(color_value)
    color.setAlpha(max(0, min(alpha, 255)))
    red, green, blue, current_alpha = color.getRgb()
    return f"rgba({red}, {green}, {blue}, {current_alpha})"


def _apply_font(widget: QLabel, *, pixel_size: int, weight: int) -> None:
    font = QFont(widget.font())
    font.setPixelSize(pixel_size)
    font.setWeight(QFont.Weight(weight))
    font.setBold(weight >= 700)
    widget.setFont(font)


@dataclass(frozen=True)
class SummaryGridItem:
    """Declarative summary cell payload."""

    key: str
    label: str
    value: str
    detail: str = ""
    detail_emphasis: bool = False
    variant: str = "neutral"
    column_span: int = 1


class _SummaryTile(QWidget):
    """Single tile rendered inside SummaryGrid."""

    def __init__(self, item: SummaryGridItem, *, parent=None):
        super().__init__(parent)
        self._item = item
        self.setObjectName("summary_tile")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self._label = QLabel(item.label, self)
        self._value = QLabel(item.value, self)
        self._detail = QLabel(item.detail, self)

        self._value.setWordWrap(True)
        self._detail.setWordWrap(True)

        layout.addWidget(self._label)
        layout.addWidget(self._value)
        layout.addWidget(self._detail)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    @property
    def item(self) -> SummaryGridItem:
        return self._item

    def set_item(self, item: SummaryGridItem) -> None:
        self._item = item
        self._label.setText(item.label)
        self._value.setText(item.value)
        self._detail.setText(item.detail)
        self._detail.setVisible(bool(item.detail))
        self._apply_theme()

    def _apply_theme(self) -> None:
        t = get_theme()
        item = self._item

        variant_bg = {
            "neutral": t.bg_hover,
            "info": t.info_bg,
            "success": t.success_bg,
            "warning": t.warning_bg,
            "error": t.error_bg,
        }
        variant_border = {
            "neutral": t.border_light,
            "info": _rgba(t.primary, 72),
            "success": _rgba(t.success, 72),
            "warning": _rgba(t.warning, 72),
            "error": _rgba(t.error, 72),
        }
        variant_value = {
            "neutral": t.text_primary,
            "info": t.primary,
            "success": t.success,
            "warning": t.warning,
            "error": t.error,
        }

        self.setStyleSheet(
            f"""
            #summary_tile {{
                background: {variant_bg.get(item.variant, variant_bg["neutral"])};
                border: 1px solid {variant_border.get(item.variant, variant_border["neutral"])};
                border-radius: {t.radius_sm}px;
            }}
            """
        )
        _apply_font(self._label, pixel_size=t.font_size_sm, weight=t.font_weight_normal)
        _apply_font(self._value, pixel_size=t.font_size_md, weight=t.font_weight_emphasis)
        self._label.setStyleSheet(
            f"color: {t.text_secondary}; background: transparent;"
        )
        self._value.setStyleSheet(
            f"color: {variant_value.get(item.variant, t.text_primary)}; background: transparent;"
        )
        if item.detail_emphasis:
            _apply_font(self._detail, pixel_size=t.font_size_md, weight=t.font_weight_emphasis)
            self._detail.setStyleSheet(
                f"color: {variant_value.get(item.variant, t.text_primary)}; background: transparent;"
            )
        else:
            _apply_font(self._detail, pixel_size=t.font_size_sm, weight=t.font_weight_normal)
            self._detail.setStyleSheet(
                f"color: {t.text_hint}; background: transparent;"
            )
        self._detail.setVisible(bool(item.detail))


class SummaryGrid(QWidget):
    """Multi-column summary grid for quick visual scanning."""

    def __init__(self, *, columns: int = 3, parent=None):
        super().__init__(parent)
        self._columns = max(1, columns)
        self._items: list[SummaryGridItem] = []
        self._tiles: dict[str, _SummaryTile] = {}

        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(12)
        self._layout.setVerticalSpacing(12)
        for column in range(self._columns):
            self._layout.setColumnStretch(column, 1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_items(self, items: Sequence[SummaryGridItem]) -> None:
        self._items = list(items)
        self._rebuild()

    def items(self) -> list[SummaryGridItem]:
        return list(self._items)

    def value_for(self, key: str) -> str:
        tile = self._tiles.get(key)
        return tile.item.value if tile is not None else ""

    def detail_for(self, key: str) -> str:
        tile = self._tiles.get(key)
        return tile.item.detail if tile is not None else ""

    def _rebuild(self) -> None:
        while self._layout.count():
            child = self._layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

        self._tiles.clear()

        row = 0
        column = 0
        for item in self._items:
            span = max(1, min(item.column_span, self._columns))
            if column + span > self._columns:
                row += 1
                column = 0

            tile = _SummaryTile(item, parent=self)
            self._tiles[item.key] = tile
            self._layout.addWidget(tile, row, column, 1, span)

            column += span
            if column >= self._columns:
                row += 1
                column = 0

    def _apply_theme(self) -> None:
        t = get_theme()
        self._layout.setHorizontalSpacing(t.spacing_md)
        self._layout.setVerticalSpacing(t.spacing_md)
        for tile in self._tiles.values():
            tile._apply_theme()


__all__ = ["SummaryGrid", "SummaryGridItem"]
