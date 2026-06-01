"""Shared summary grid for compact configuration overviews."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from src.qt_api import (
    QColor,
    QFont,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Qt,
)

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
    icon_name: str | None = None


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


class _ModuleSummaryTile(QWidget):
    """Module-style summary tile with a leading semantic icon."""

    @property
    def ICON_CONTAINER_SIZE(self) -> int:
        return get_theme().module_summary_icon_container_size

    @property
    def ICON_SIZE(self) -> int:
        return get_theme().module_summary_icon_size

    @property
    def TILE_MIN_HEIGHT(self) -> int:
        return get_theme().module_summary_tile_min_height

    @property
    def TITLE_FONT_SIZE(self) -> int:
        return get_theme().module_summary_title_font_size

    def __init__(self, item: SummaryGridItem, *, parent=None):
        super().__init__(parent)
        self._item = item
        self.setObjectName("module_summary_tile")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setMinimumHeight(self.TILE_MIN_HEIGHT)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._shadow = QGraphicsDropShadowEffect(self)
        self.setGraphicsEffect(self._shadow)

        layout = QHBoxLayout(self)
        self._layout = layout

        self._icon_container = QLabel(self)
        self._icon_container.setObjectName("module_summary_icon")
        self._icon_container.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._icon_container, 0, Qt.AlignVCenter)

        text_column = QWidget(self)
        text_column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._text_layout = QVBoxLayout(text_column)
        self._text_layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(item.label, text_column)
        self._value = QLabel(item.value, text_column)
        self._detail = QLabel(item.detail, text_column)
        self._label.setWordWrap(True)
        self._value.setWordWrap(True)
        self._detail.setWordWrap(True)

        self._label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._value.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._detail.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._text_layout.addWidget(self._label)
        self._text_layout.addWidget(self._value)
        self._text_layout.addWidget(self._detail)
        layout.addWidget(text_column, 1, Qt.AlignVCenter)

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

        variant_value = {
            "neutral": t.text_primary,
            "info": t.primary,
            "success": t.success,
            "warning": t.warning,
            "error": t.error,
        }
        variant_icon = {
            "neutral": t.primary,
            "info": t.primary,
            "success": t.success,
            "warning": t.warning,
            "error": t.error,
        }
        icon_color = variant_icon.get(item.variant, t.primary)
        soft_border = _rgba(t.border_light, t.module_summary_border_alpha)
        icon_background = _rgba(t.primary, t.module_summary_icon_bg_alpha)
        icon_container_size = t.module_summary_icon_container_size
        icon_size = t.module_summary_icon_size

        self.setMinimumHeight(t.module_summary_tile_min_height)
        self._layout.setContentsMargins(
            t.module_summary_tile_padding_x,
            t.module_summary_tile_padding_y,
            t.module_summary_tile_padding_x,
            t.module_summary_tile_padding_y,
        )
        self._layout.setSpacing(t.module_summary_icon_text_gap)
        self._text_layout.setSpacing(t.module_summary_content_spacing)
        self._icon_container.setFixedSize(icon_container_size, icon_container_size)

        self.setStyleSheet(
            f"""
            #module_summary_tile {{
                background: {t.bg_card};
                border: 1px solid {soft_border};
                border-radius: {t.radius_md}px;
            }}
            #module_summary_icon {{
                background: {icon_background};
                border-radius: {icon_container_size // 2}px;
            }}
            """
        )
        self._shadow.setBlurRadius(t.shadow_blur_sm)
        self._shadow.setColor(QColor(0, 0, 0, t.module_summary_shadow_alpha))
        self._shadow.setOffset(0, t.module_summary_shadow_offset_y)

        _apply_font(self._label, pixel_size=t.module_summary_title_font_size, weight=t.font_weight_emphasis)
        _apply_font(self._value, pixel_size=t.font_size_md, weight=t.font_weight_normal)
        _apply_font(self._detail, pixel_size=t.font_size_md, weight=t.font_weight_normal)

        line_height = t.module_summary_body_line_height
        title_line_height = t.module_summary_title_line_height
        self._label.setMinimumHeight(title_line_height)
        self._value.setMinimumHeight(line_height)
        self._detail.setMinimumHeight(line_height)
        self._label.setStyleSheet(
            f"color: {t.text_primary}; background: transparent; line-height: {title_line_height}px;"
        )
        self._value.setStyleSheet(
            f"color: {t.text_primary}; background: transparent; line-height: {line_height}px;"
        )
        self._detail.setStyleSheet(
            f"color: {t.text_secondary}; background: transparent; line-height: {line_height}px;"
        )
        self._detail.setVisible(bool(item.detail))

        if item.icon_name:
            try:
                from src.ui.icons.catalog import get_icon

                self._icon_container.setPixmap(
                    get_icon(item.icon_name, icon_size, icon_color).pixmap(
                        icon_size, icon_size
                    )
                )
            except Exception:
                self._icon_container.clear()
        else:
            self._icon_container.clear()


class SummaryGrid(QWidget):
    """Multi-column summary grid for quick visual scanning."""

    def __init__(
        self,
        *,
        columns: int = 3,
        parent=None,
        tile_style: Literal["metric", "module"] = "metric",
    ):
        super().__init__(parent)
        self._columns = max(1, columns)
        self._tile_style = tile_style
        self._render_columns = self._effective_columns()
        self._items: list[SummaryGridItem] = []
        self._tiles: dict[str, _SummaryTile | _ModuleSummaryTile] = {}

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
        self._render_columns = self._effective_columns()
        for column in range(self._columns):
            self._layout.setColumnStretch(column, 1 if column < self._render_columns else 0)

        row = 0
        column = 0
        for item in self._items:
            span = max(1, min(item.column_span, self._render_columns))
            if column + span > self._render_columns:
                row += 1
                column = 0

            tile = self._build_tile(item)
            self._tiles[item.key] = tile
            self._layout.addWidget(tile, row, column, 1, span)

            column += span
            if column >= self._render_columns:
                row += 1
                column = 0

    def _apply_theme(self) -> None:
        t = get_theme()
        grid_gap = t.module_summary_grid_gap if self._tile_style == "module" else t.spacing_md
        self._layout.setHorizontalSpacing(grid_gap)
        self._layout.setVerticalSpacing(grid_gap)
        for tile in self._tiles.values():
            tile._apply_theme()

    def _build_tile(self, item: SummaryGridItem) -> _SummaryTile | _ModuleSummaryTile:
        if self._tile_style == "module":
            return _ModuleSummaryTile(item, parent=self)
        return _SummaryTile(item, parent=self)

    def _effective_columns(self) -> int:
        return self._columns

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)


__all__ = ["SummaryGrid", "SummaryGridItem"]
