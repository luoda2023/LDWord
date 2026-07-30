"""Shared summary grid for compact configuration overviews."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from src.qt_api import (
    QColor,
    QFont,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSize,
    QVBoxLayout,
    QWidget,
    Qt,
)

from src.shared.ui.layout_sync import refresh_layout_chain, updates_suspended
from src.shared.ui.theme import bind_theme, get_theme


_SINGLE_ROW_NARROW_BREAKPOINT = 720
_SINGLE_ROW_MEDIUM_BREAKPOINT = 1160


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


class _ElidedLabel(QLabel):
    """QLabel variant that keeps full text but paints a width-safe display string."""

    def __init__(self, text: str = "", parent=None):
        super().__init__("", parent)
        self._full_text = ""
        self.setWordWrap(False)
        self.setText(text)

    @property
    def full_text(self) -> str:
        return self._full_text

    def setText(self, text: str) -> None:  # noqa: N802 - Qt API contract
        self._full_text = str(text or "")
        self._refresh_elide()

    def refresh_elide(self) -> None:
        self._refresh_elide()

    def resizeEvent(self, event) -> None:
        self._refresh_elide()
        super().resizeEvent(event)

    def _refresh_elide(self) -> None:
        display_text = self._full_text
        available_width = self.contentsRect().width()
        if available_width > 0:
            metrics = self.fontMetrics()
            candidates = _elide_display_candidates(self._full_text)
            for candidate in candidates:
                if metrics.horizontalAdvance(candidate) <= available_width:
                    display_text = candidate
                    break
            else:
                display_text = metrics.elidedText(
                    candidates[-1],
                    Qt.ElideRight,
                    max(1, available_width),
                )
        if super().text() != display_text:
            super().setText(display_text)


def _elide_display_candidates(text: str) -> list[str]:
    candidates = [text]
    if "\n" in text or " / " not in text:
        return candidates

    left, right = text.rsplit(" / ", 1)
    right_words = right.split()
    if len(right_words) <= 1:
        return candidates

    first_word = right_words[0]
    candidates.extend(
        [
            f"{left} / {first_word}...",
            f"{left}/{first_word}...",
            f"{first_word}...",
        ]
    )
    return candidates


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
    tooltip: str = ""


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
        self._apply_tooltip()
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
        self._apply_tooltip()
        self._apply_theme()

    def _apply_tooltip(self) -> None:
        tooltip = self._item.tooltip or _item_tooltip(self._item)
        self.setToolTip(tooltip)
        self._label.setToolTip(tooltip)
        self._value.setToolTip(tooltip)
        self._detail.setToolTip(tooltip)

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
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)
        self.setMinimumHeight(self.TILE_MIN_HEIGHT)
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        self._layout = layout

        self._icon_container = QLabel(self)
        self._icon_container.setObjectName("module_summary_icon")
        self._icon_container.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._icon_container, 0, Qt.AlignVCenter)

        text_column = QWidget(self)
        text_column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        text_column.setMinimumWidth(0)
        self._text_layout = QVBoxLayout(text_column)
        self._text_layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(item.label, text_column)
        self._value = _ElidedLabel(item.value, text_column)
        self._detail = _ElidedLabel(item.detail, text_column)
        self._label.setWordWrap(False)
        for label in (self._label, self._value, self._detail):
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)

        self._label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._value.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._detail.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._text_layout.addWidget(self._label)
        self._text_layout.addWidget(self._value)
        self._text_layout.addWidget(self._detail)
        layout.addWidget(text_column, 1, Qt.AlignVCenter)

        self._apply_theme()
        self._apply_tooltip()
        bind_theme(self, self._apply_theme)

    @property
    def item(self) -> SummaryGridItem:
        return self._item

    def set_item(self, item: SummaryGridItem) -> None:
        self._item = item
        self._label.setText(item.label)
        self._value.setText(item.value)
        self._detail.setText(item.detail)
        self._detail.setVisible(True)
        self._apply_tooltip()
        self._apply_theme()

    def _apply_tooltip(self) -> None:
        tooltip = self._item.tooltip or _item_tooltip(self._item)
        self.setToolTip(tooltip)
        self._label.setToolTip(tooltip)
        self._value.setToolTip(tooltip)
        self._detail.setToolTip(tooltip)

    def _apply_theme(self) -> None:
        t = get_theme()
        item = self._item

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

        self.setFixedHeight(t.module_summary_tile_min_height)
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

        _apply_font(self._label, pixel_size=t.module_summary_title_font_size, weight=t.font_weight_emphasis)
        _apply_font(self._value, pixel_size=t.font_size_md, weight=t.font_weight_normal)
        _apply_font(self._detail, pixel_size=t.font_size_md, weight=t.font_weight_normal)

        line_height = t.module_summary_body_line_height
        title_line_height = t.module_summary_title_line_height
        self._label.setMinimumHeight(title_line_height)
        self._value.setMinimumHeight(line_height)
        self._detail.setMinimumHeight(line_height)
        self._label.setMaximumHeight(title_line_height)
        self._value.setMaximumHeight(line_height)
        self._detail.setMaximumHeight(line_height)
        self._label.setStyleSheet(
            f"color: {t.text_primary}; background: transparent; line-height: {title_line_height}px;"
        )
        self._value.setStyleSheet(
            f"color: {t.text_primary}; background: transparent; line-height: {line_height}px;"
        )
        self._detail.setStyleSheet(
            f"color: {t.text_secondary}; background: transparent; line-height: {line_height}px;"
        )
        self._value.refresh_elide()
        self._detail.refresh_elide()
        self._detail.setVisible(True)

        if item.icon_name:
            try:
                from src.shared.ui.icons.catalog import get_icon

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
        layout_policy: Literal["fixed", "single_row_preferred"] = "fixed",
    ):
        super().__init__(parent)
        self._columns = max(1, columns)
        self._tile_style = tile_style
        self._layout_policy = layout_policy
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._render_columns = self._effective_columns()
        self._items: list[SummaryGridItem] = []
        self._tiles: dict[str, _SummaryTile | _ModuleSummaryTile] = {}
        self._row_count = 0

        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(12)
        self._layout.setVerticalSpacing(12)
        for column in range(self._columns):
            self._layout.setColumnStretch(column, 1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_items(self, items: Sequence[SummaryGridItem]) -> None:
        next_items = list(items)
        self._validate_unique_keys(next_items)
        if (
            next_items == self._items
            and self._effective_columns() == self._render_columns
        ):
            return

        parent = self.parentWidget()
        with updates_suspended(parent, self):
            layout_changed = self._layout_signature(next_items) != self._layout_signature(
                self._items
            )
            self._items = next_items
            self._reconcile_tiles(
                relayout=layout_changed
                or self._effective_columns() != self._render_columns
            )
            self.updateGeometry()
            self._sync_parent_summary_height()
        # Hidden detail panes still need their local item/size-hint cache, but
        # propagating a layout refresh through hidden ancestors only causes
        # unrelated visible pages to remeasure.  Their showEvent will commit
        # the parent chain when they become visible.
        if self.isVisible():
            refresh_layout_chain(parent or self, passes=2)

    def items(self) -> list[SummaryGridItem]:
        return list(self._items)

    def value_for(self, key: str) -> str:
        tile = self._tiles.get(key)
        return tile.item.value if tile is not None else ""

    def detail_for(self, key: str) -> str:
        tile = self._tiles.get(key)
        return tile.item.detail if tile is not None else ""

    def tooltip_for(self, key: str) -> str:
        tile = self._tiles.get(key)
        if tile is None:
            return ""
        return tile.item.tooltip or _item_tooltip(tile.item)

    @staticmethod
    def _validate_unique_keys(items: Sequence[SummaryGridItem]) -> None:
        seen: set[str] = set()
        duplicate_keys: list[str] = []
        for item in items:
            if item.key in seen and item.key not in duplicate_keys:
                duplicate_keys.append(item.key)
            seen.add(item.key)
        if duplicate_keys:
            duplicates = ", ".join(repr(key) for key in duplicate_keys)
            raise ValueError(
                f"SummaryGrid item keys must be unique; duplicates: {duplicates}"
            )

    @staticmethod
    def _layout_signature(
        items: Sequence[SummaryGridItem],
    ) -> tuple[tuple[str, int], ...]:
        return tuple((item.key, item.column_span) for item in items)

    def _reconcile_tiles(self, *, relayout: bool) -> None:
        previous_tiles = self._tiles
        next_tiles: dict[str, _SummaryTile | _ModuleSummaryTile] = {}

        for item in self._items:
            tile = previous_tiles.get(item.key)
            if tile is None:
                tile = self._build_tile(item)
            elif tile.item != item:
                tile.set_item(item)
            next_tiles[item.key] = tile

        removed_tiles = [
            tile for key, tile in previous_tiles.items() if key not in next_tiles
        ]
        self._tiles = next_tiles

        if relayout:
            self._relayout_tiles()

        for tile in removed_tiles:
            self._layout.removeWidget(tile)
            tile.hide()
            tile.deleteLater()

    def _relayout_tiles(self) -> None:
        while self._layout.count():
            self._layout.takeAt(0)

        self._render_columns = self._effective_columns()
        for column in range(self._columns):
            self._layout.setColumnStretch(column, 1 if column < self._render_columns else 0)

        row = 0
        column = 0
        max_row = -1
        for item in self._items:
            span = self._item_span(item, len(self._items))
            if column + span > self._render_columns:
                row += 1
                column = 0

            tile = self._tiles[item.key]
            self._layout.addWidget(tile, row, column, 1, span)
            max_row = max(max_row, row)

            column += span
            if column >= self._render_columns:
                row += 1
                column = 0
        self._row_count = max_row + 1

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

    def content_height_hint(self, width: int | None = None) -> int:
        if self._tile_style != "module" or self._row_count <= 0:
            return max(0, super().sizeHint().height())
        t = get_theme()
        render_columns = self._effective_columns_for_width(self._layout_width_hint(width))
        row_count = self._row_count_for_columns(render_columns)
        return (
            row_count * t.module_summary_tile_min_height
            + max(0, row_count - 1) * t.module_summary_grid_gap
        )

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API contract
        hint = super().sizeHint()
        if self._tile_style != "module" or self._row_count <= 0:
            return hint
        return QSize(0, self.content_height_hint(self._layout_width_hint()))

    def _effective_columns(self) -> int:
        return self._effective_columns_for_width(self._layout_width_hint())

    def _layout_width_hint(self, width: int | None = None) -> int:
        resolved = int(width or self.width() or 0)
        if self._layout_policy != "single_row_preferred":
            return resolved

        # The template summary grid is often populated while its detail pane is
        # hidden.  In that phase Qt reports 0px or a stale narrow width, which
        # used to rebuild the grid as a one-column mobile layout and let the
        # parent card cache that height.  Prefer the nearest usable ancestor
        # content width, and fall back to the full column model until a real
        # resize event arrives.
        if resolved >= _SINGLE_ROW_NARROW_BREAKPOINT:
            return resolved

        widget = self.parentWidget()
        while widget is not None:
            candidate = int(widget.width() or 0)
            if candidate > resolved:
                layout = widget.layout()
                if layout is not None:
                    margins = layout.contentsMargins()
                    candidate = max(0, candidate - margins.left() - margins.right())
                resolved = max(resolved, candidate)
                if resolved >= _SINGLE_ROW_NARROW_BREAKPOINT:
                    return resolved
            widget = widget.parentWidget()
        return resolved

    def _effective_columns_for_width(self, width: int) -> int:
        if self._layout_policy == "single_row_preferred":
            if width <= 0:
                return self._columns
            if width < _SINGLE_ROW_NARROW_BREAKPOINT:
                return 1
            if width < _SINGLE_ROW_MEDIUM_BREAKPOINT:
                return max(1, min(self._columns, 6))
        return self._columns

    def _item_span(self, item: SummaryGridItem, item_count: int) -> int:
        return self._item_span_for_columns(item, item_count, self._render_columns)

    def _item_span_for_columns(
        self,
        item: SummaryGridItem,
        item_count: int,
        render_columns: int,
    ) -> int:
        if self._layout_policy != "single_row_preferred":
            return max(1, min(item.column_span, render_columns))

        if item.column_span > 1:
            return self._scaled_span_for_columns(item.column_span, render_columns)

        default_spans = {
            2: (6, 6),
            3: (4, 4, 4),
            4: (3, 3, 3, 3),
            5: (2, 2, 2, 3, 3),
        }
        spans = default_spans.get(item_count)
        if spans is None:
            return self._scaled_span_for_columns(item.column_span, render_columns)
        index = self._items.index(item)
        return self._scaled_span_for_columns(spans[index], render_columns)

    def _scaled_span(self, span: int) -> int:
        return self._scaled_span_for_columns(span, self._render_columns)

    def _scaled_span_for_columns(self, span: int, render_columns: int) -> int:
        base_span = max(1, min(int(span), self._columns))
        if render_columns >= self._columns:
            return max(1, min(base_span, render_columns))
        scaled = (base_span * render_columns + self._columns - 1) // self._columns
        return max(1, min(scaled, render_columns))

    def _row_count_for_columns(self, render_columns: int) -> int:
        row = 0
        column = 0
        max_row = -1
        for item in self._items:
            span = self._item_span_for_columns(item, len(self._items), render_columns)
            if column + span > render_columns:
                row += 1
                column = 0
            max_row = max(max_row, row)
            column += span
            if column >= render_columns:
                row += 1
                column = 0
        return max_row + 1

    def resizeEvent(self, event) -> None:
        next_columns = self._effective_columns()
        relaid_out = False
        if next_columns != self._render_columns:
            self._relayout_tiles()
            relaid_out = True
        super().resizeEvent(event)
        if relaid_out:
            self.updateGeometry()
            self._sync_parent_summary_height()

    def _sync_parent_summary_height(self) -> None:
        parent = self.parentWidget()
        sync_height = getattr(parent, "_sync_content_height_limit", None)
        if callable(sync_height):
            sync_height()


def _item_tooltip(item: SummaryGridItem) -> str:
    parts = [item.label, item.value, item.detail]
    return "\n".join(part for part in parts if part)


__all__ = ["SummaryGrid", "SummaryGridItem"]
