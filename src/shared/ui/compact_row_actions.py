"""Shared compact action buttons for repeatable token rows."""

from __future__ import annotations

from collections.abc import Callable

from src.qt_api import QEvent, QHBoxLayout, QPushButton, QSizePolicy, QWidget
from src.shared.ui.deferred_call import defer_qt_method
from src.shared.ui.icon_button import apply_icon_button_style
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.icons.catalog import get_icon


_GHOST_VARIANTS = {"ghost", "ghost-primary", "ghost-danger"}


def compact_row_actions_width(count: int, *, theme=None) -> int:
    """Return the exact logical width used by a visible action strip."""

    resolved_theme = theme or get_theme()
    normalized_count = max(0, int(count))
    return (
        normalized_count * resolved_theme.compact_action_size
        + max(0, normalized_count - 1) * resolved_theme.compact_action_gap
    )


def apply_compact_row_action(
    button: QPushButton,
    *,
    icon_name: str,
    tooltip: str,
    variant: str = "secondary",
) -> QPushButton:
    """Apply the one compact action geometry and visual contract."""

    button.setProperty("compactRowAction", True)
    button.setProperty("compactActionIcon", str(icon_name or ""))
    button.setProperty("compactActionVariant", str(variant or "secondary"))
    button.setToolTip(str(tooltip or ""))
    button.setAccessibleName(str(tooltip or ""))

    def refresh() -> None:
        theme = get_theme()
        resolved_variant = str(button.property("compactActionVariant") or "secondary")
        color = (
            theme.error
            if resolved_variant in {"ghost-danger", "outlined-danger"}
            else theme.primary
            if resolved_variant in {"ghost-primary", "outlined-primary"}
            else theme.icon_primary
        )
        button.setIcon(
            get_icon(
                str(button.property("compactActionIcon") or ""),
                theme.compact_action_icon_size,
                color,
            )
        )
        apply_icon_button_style(
            button,
            variant=(
                resolved_variant
                if resolved_variant in _GHOST_VARIANTS
                else "secondary"
            ),
            size=theme.compact_action_size,
            icon_size=theme.compact_action_icon_size,
        )

    refresh()
    bind_theme(button, refresh)
    return button


class CompactRowActions(QWidget):
    """A size-stable horizontal strip of compact icon-only actions."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(get_theme().compact_action_gap)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        bind_theme(self, self._apply_metrics)

    def add_action(
        self,
        key: str,
        *,
        icon_name: str,
        tooltip: str,
        variant: str = "secondary",
        callback: Callable[..., object] | None = None,
    ) -> QPushButton:
        if key in self._buttons:
            raise ValueError(f"duplicate compact action key: {key}")
        button = QPushButton("", self)
        apply_compact_row_action(
            button,
            icon_name=icon_name,
            tooltip=tooltip,
            variant=variant,
        )
        if callback is not None:
            button.clicked.connect(callback)
        button.installEventFilter(self)
        self._layout.addWidget(button)
        self._buttons[key] = button
        self._apply_metrics()
        return button

    def button(self, key: str) -> QPushButton | None:
        return self._buttons.get(key)

    def buttons(self) -> tuple[QPushButton, ...]:
        return tuple(self._buttons.values())

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API
        if watched in self._buttons.values() and event.type() in {
            QEvent.Show,
            QEvent.Hide,
        }:
            defer_qt_method(self, "sync_visibility")
        return super().eventFilter(watched, event)

    def sync_visibility(self) -> None:
        """Reclaim the slots of explicitly hidden row actions."""

        self._apply_metrics()
        self._layout.invalidate()
        self.updateGeometry()

    def _apply_metrics(self) -> None:
        theme = get_theme()
        self._layout.setSpacing(theme.compact_action_gap)
        count = sum(not button.isHidden() for button in self._buttons.values())
        width = compact_row_actions_width(count, theme=theme)
        self.setFixedWidth(width)


__all__ = [
    "CompactRowActions",
    "apply_compact_row_action",
    "compact_row_actions_width",
]
