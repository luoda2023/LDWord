"""Lazy detail creation and loading feedback for the template panel."""

from __future__ import annotations

from time import monotonic

from src.qt_api import (
    QApplication,
    QColor,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPainter,
    QSizePolicy,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
)
from src.shared.ui.theme import get_theme
from src.ui.panels.template_feature_specs import TEMPLATE_CARD_DEFINITIONS


FIRST_LOAD_LOADING_CARDS = frozenset(
    {
        "tpl_page",
        "tpl_style",
        "tpl_heading",
        "tpl_table",
        "tpl_header_footer",
        "tpl_toc",
        "tpl_caption",
    }
)
STARTUP_BACKGROUND_PRELOAD_CARDS = (
    "tpl_heading",
    "tpl_header_footer",
    "tpl_toc",
)
FIRST_LOAD_LOADING_DELAY_MS = 150
DETAIL_LOADING_MIN_VISIBLE_MS = 200
DETAIL_REFRESH_MIN_VISIBLE_MS = 140
DETAIL_LOADING_SKELETONS: dict[str, tuple[tuple[str, int], ...]] = {
    "tpl_page": (
        ("summary_3", 118),
        ("card_header_a", 24),
        ("editor_a", 186),
        ("card_header_b", 24),
        ("editor_b", 154),
    ),
    "tpl_style": (
        ("summary_3", 118),
        ("card_header_a", 24),
        ("editor_a", 148),
        ("card_header_b", 24),
        ("editor_b", 148),
        ("card_header_c", 24),
        ("editor_c", 148),
    ),
    "tpl_heading": (
        ("summary_3", 118),
        ("card_header_a", 24),
        ("editor_a", 168),
        ("card_header_b", 24),
        ("editor_b", 168),
        ("card_header_c", 24),
        ("editor_c", 168),
    ),
    "tpl_table": (
        ("summary_3", 118),
        ("card_header_a", 24),
        ("editor_a", 164),
        ("card_header_b", 24),
        ("editor_b", 148),
        ("card_header_c", 24),
        ("editor_c", 132),
    ),
    "tpl_header_footer": (
        ("summary_2", 118),
        ("card_header_a", 24),
        ("editor_a", 142),
        ("card_header_b", 24),
        ("editor_b", 210),
        ("card_header_c", 24),
        ("editor_c", 168),
    ),
    "tpl_toc": (
        ("summary_2", 118),
        ("card_header_a", 24),
        ("editor_a", 148),
        ("card_header_b", 24),
        ("editor_b", 188),
    ),
    "tpl_caption": (
        ("summary_2", 112),
        ("card_header_a", 24),
        ("editor_a", 168),
        ("card_header_b", 24),
        ("editor_b", 168),
    ),
}


class _LoadingDetail(QWidget):
    """In-place first-load skeleton overlay for heavier detail panes."""

    def __init__(
        self,
        title: str,
        icon_name: str,
        *,
        blocks: tuple[tuple[str, int], ...],
        parent=None,
    ):
        super().__init__(parent)
        self._title = title
        self._icon_name = icon_name
        self._block_specs = tuple(blocks)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(8)

        self._shell = QWidget(self)
        shell_layout = QVBoxLayout(self._shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(8)

        header = QWidget(self._shell)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        self._hdr_icon = QLabel(header)
        self._hdr_icon.setFixedSize(18, 18)
        header_layout.addWidget(self._hdr_icon)
        title_label = QLabel(title, header)
        title_label.setObjectName("tpl_card_title")
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        shell_layout.addWidget(header)

        self._desc = QLabel(f"正在加载“{title}”…", self._shell)
        self._desc.setObjectName("tpl_loading_desc")
        self._desc.setWordWrap(True)
        shell_layout.addWidget(self._desc)

        self._blocks: dict[str, QFrame] = {}
        for name, height in self._block_specs:
            block = QFrame(self._shell)
            block.setObjectName(f"tpl_loading_block_{name}")
            block.setMinimumHeight(height)
            block.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            if name.startswith("summary_"):
                inner = QHBoxLayout(block)
                inner.setContentsMargins(16, 14, 16, 14)
                inner.setSpacing(12)
                chip_count = 3 if name.endswith("_3") else 2
                for index in range(chip_count):
                    chip = QFrame(block)
                    chip.setObjectName(f"tpl_loading_chip_{name}_{index}")
                    chip.setMinimumHeight(52)
                    chip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    inner.addWidget(chip, 1)
            elif name.startswith("editor_"):
                inner = QVBoxLayout(block)
                inner.setContentsMargins(18, 16, 18, 16)
                inner.setSpacing(10)
                for row_index in range(2):
                    row = QFrame(block)
                    row.setObjectName(f"tpl_loading_row_{name}_{row_index}")
                    row.setMinimumHeight(28)
                    row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    inner.addWidget(row)
            shell_layout.addWidget(block)
            self._blocks[name] = block

        layout.addWidget(self._shell)
        layout.addStretch(1)

    def show_overlay(self) -> None:
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        tint = QColor(get_theme().bg_window)
        tint.setAlpha(210)
        painter.fillRect(self.rect(), tint)
        super().paintEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.updateGeometry()

    def apply_theme(self) -> None:
        theme = get_theme()
        for widget in self.findChildren(QLabel, "tpl_card_title"):
            widget.setStyleSheet(
                f"font-size: {theme.font_size_lg}px; "
                f"font-weight: {theme.font_weight_emphasis}; "
                f"color: {theme.primary}; background: transparent;"
            )
        self._desc.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};"
        )
        self._shell.setStyleSheet("background: transparent; border: none;")
        block_style = (
            f"background: {theme.bg_card}; "
            f"border: 1px solid {theme.border_light}; "
            f"border-radius: {theme.radius_md}px;"
        )
        header_block_style = (
            f"background: {theme.bg_hover}; "
            f"border: 1px solid {theme.border_light}; "
            f"border-radius: {theme.radius_sm}px;"
        )
        for name, block in self._blocks.items():
            block.setStyleSheet(
                header_block_style if name.startswith("card_header_") else block_style
            )
        placeholder_style = (
            f"background: {theme.bg_hover}; "
            f"border: 1px solid {theme.border_light}; "
            f"border-radius: {theme.radius_sm}px;"
        )
        for placeholder in self.findChildren(QFrame):
            object_name = placeholder.objectName()
            if object_name.startswith(
                ("tpl_loading_chip_", "tpl_loading_row_")
            ):
                placeholder.setStyleSheet(placeholder_style)
        try:
            from src.shared.ui.icons.catalog import get_icon

            self._hdr_icon.setPixmap(
                get_icon(self._icon_name, 18, theme.primary).pixmap(18, 18)
            )
        except Exception:
            pass
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.update()


class _RefreshOverlay(QWidget):
    """Lightweight refresh transition overlay for the visible detail pane."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.hide()

    def show_overlay(self) -> None:
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        tint = QColor(get_theme().bg_window)
        tint.setAlpha(150)
        painter.fillRect(self.rect(), tint)

    def apply_theme(self) -> None:
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.update()


class TemplateDetailLifecycleMixin:
    """Own template-detail creation, transitions, preloading, and feedback.

    The host panel supplies the domain hooks used after a detail is created:
    ``_attach_participation_section``, ``_wire_parameter_detail_signals``,
    ``_sync_detail_state``, and ``_has_pending_template_edits``.
    """

    def _initialize_detail_lifecycle_state(self) -> None:
        self._loading_detail: _LoadingDetail | None = None
        self._refresh_overlay: _RefreshOverlay | None = None
        self._loading_timer: QTimer | None = None
        self._loading_min_visible_timer: QTimer | None = None
        self._loading_visible_since: float | None = None
        self._pending_detail_card_id: str | None = None
        self._pending_real_detail_switch_card_id: str | None = None

    def _show_detail(self, card_id: str) -> None:
        is_first_detail_load = (
            card_id not in self._loaded_detail_ids
            and card_id in self._detail_factories
        )
        use_loading = (
            is_first_detail_load and card_id in FIRST_LOAD_LOADING_CARDS
        )
        if use_loading:
            self._pending_real_detail_switch_card_id = card_id
            self._schedule_loading_detail(card_id)
            QTimer.singleShot(
                0,
                lambda cid=card_id: self._complete_first_load_detail(cid),
            )
            return
        self._show_loaded_detail(card_id)

    def _complete_first_load_detail(self, card_id: str) -> None:
        if self._pending_real_detail_switch_card_id != card_id:
            return
        self._ensure_detail_loaded(card_id)
        self._finish_detail_transition(card_id)

    def _show_loaded_detail(self, card_id: str) -> None:
        self._ensure_detail_loaded(card_id)
        self._finish_detail_transition(card_id)

    def _finish_detail_transition(self, card_id: str) -> None:
        self._pending_real_detail_switch_card_id = None
        loading_visible_since = self._loading_visible_since
        if loading_visible_since is not None:
            elapsed_ms = int((monotonic() - loading_visible_since) * 1000)
            remaining_ms = max(
                0,
                DETAIL_LOADING_MIN_VISIBLE_MS - elapsed_ms,
            )
            if remaining_ms > 0:
                if self._loading_min_visible_timer is None:
                    self._loading_min_visible_timer = QTimer(self)
                    self._loading_min_visible_timer.setSingleShot(True)
                    self._loading_min_visible_timer.timeout.connect(
                        self._on_loading_min_visible_timeout
                    )
                self._pending_detail_card_id = card_id
                self._loading_min_visible_timer.start(remaining_ms)
                return
        self._show_resolved_detail(card_id)

    def _show_resolved_detail(self, card_id: str) -> None:
        self._hide_loading_detail()
        self._details.show_detail(card_id)
        self._current_detail = self._details.current_detail
        self._current_detail_card_id = card_id
        detail = self._detail_map.get(card_id)
        if (
            detail is not None
            and hasattr(detail, "capture_entry_snapshot")
            and not self._has_pending_template_edits()
        ):
            detail.capture_entry_snapshot()

    def _schedule_loading_detail(self, card_id: str) -> None:
        self._pending_detail_card_id = card_id
        if self._loading_timer is None:
            self._loading_timer = QTimer(self)
            self._loading_timer.setSingleShot(True)
            self._loading_timer.timeout.connect(
                self._on_loading_timer_timeout
            )
        self._loading_timer.start(FIRST_LOAD_LOADING_DELAY_MS)

    def _on_loading_timer_timeout(self) -> None:
        card_id = self._pending_detail_card_id
        if (
            not card_id
            or self._pending_real_detail_switch_card_id != card_id
        ):
            return
        self._show_loading_detail(card_id)

    def _on_loading_min_visible_timeout(self) -> None:
        card_id = self._pending_detail_card_id
        if not card_id:
            return
        self._show_resolved_detail(card_id)

    def _show_loading_detail(self, card_id: str) -> None:
        title, icon = TEMPLATE_CARD_DEFINITIONS.get(
            card_id,
            (card_id, ""),
        )
        if self._loading_timer is not None:
            self._loading_timer.stop()
        self._pending_detail_card_id = card_id
        self._loading_visible_since = monotonic()
        block_specs = DETAIL_LOADING_SKELETONS.get(
            card_id,
            (
                ("summary", 118),
                ("editor_a", 168),
                ("editor_b", 148),
            ),
        )
        self._loading_detail = _LoadingDetail(
            title,
            icon,
            blocks=block_specs,
            parent=self._detail_container,
        )
        self._loading_detail.apply_theme()
        self._loading_detail.show_overlay()

    def _hide_loading_detail(self) -> None:
        if self._loading_timer is not None:
            self._loading_timer.stop()
        if self._loading_min_visible_timer is not None:
            self._loading_min_visible_timer.stop()
        self._pending_detail_card_id = None
        self._loading_visible_since = None
        loading = self._loading_detail
        self._loading_detail = None
        if loading is None:
            return
        loading.hide()
        loading.deleteLater()

    def _ensure_detail_loaded(self, card_id: str) -> QWidget:
        if card_id in self._loaded_detail_ids:
            return self._detail_map[card_id]

        factory = self._detail_factories.get(card_id)
        if factory is None:
            return self._detail_map[card_id]

        detail = factory()
        old = self._detail_map[card_id]
        self._detail_map[card_id] = detail
        self._details.detail_map[card_id] = detail
        detail.hide()
        detail.setParent(self._detail_container)
        self._attach_participation_section(card_id, detail)
        old.hide()
        old.deleteLater()

        for attr_name, attr_card_id in self._detail_attr_names.items():
            if attr_card_id == card_id:
                setattr(self, attr_name, detail)
                break

        self._loaded_detail_ids.add(card_id)
        self._wire_parameter_detail_signals(card_id, detail)
        self._sync_detail_state(detail)
        return detail

    def preload_details_for_startup(self, status_callback=None) -> None:
        """Create heavier detail panes while the startup splash is visible."""
        while self.preload_one_detail_for_startup(status_callback):
            pass

    def preload_one_detail_for_startup(self, status_callback=None) -> bool:
        """Create one pending detail pane and return whether work was done."""
        for card_id in STARTUP_BACKGROUND_PRELOAD_CARDS:
            if card_id in self._loaded_detail_ids:
                continue
            if card_id not in self._detail_factories:
                continue
            title, _icon = TEMPLATE_CARD_DEFINITIONS.get(
                card_id,
                (card_id, ""),
            )
            if callable(status_callback):
                status_callback(f"后台预热{title}")
            QApplication.processEvents()
            self._ensure_detail_loaded(card_id)
            return True
        return False

    def _show_refresh_overlay(self) -> None:
        current = self._details.current_detail
        if current is None:
            return
        if self._refresh_overlay is not None:
            self._refresh_overlay.hide()
            self._refresh_overlay.deleteLater()
        self._refresh_overlay = _RefreshOverlay(
            parent=self._detail_container
        )
        self._refresh_overlay.apply_theme()
        self._refresh_overlay.show_overlay()

    def _hide_refresh_overlay(self) -> None:
        overlay = self._refresh_overlay
        self._refresh_overlay = None
        if overlay is None:
            return
        overlay.hide()
        overlay.deleteLater()

    def _prepare_detail_feedback_theme(self) -> bool:
        if self._loading_detail is not None:
            self._loading_detail.apply_theme()
        if self._refresh_overlay is not None:
            self._refresh_overlay.apply_theme()
        current_detail = self._details.current_detail
        show_refresh = (
            current_detail is not None
            and current_detail is not self._overview_detail
        )
        if show_refresh:
            self._show_refresh_overlay()
        return show_refresh

    def _finish_detail_feedback_theme(self, show_refresh: bool) -> None:
        if not show_refresh:
            return
        QTimer.singleShot(
            DETAIL_REFRESH_MIN_VISIBLE_MS,
            self._hide_refresh_overlay,
        )
