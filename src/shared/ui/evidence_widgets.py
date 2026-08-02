"""Reusable evidence list and action bar widgets."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from src.qt_api import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSize,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)

from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.keyed_widget_list import KeyedWidgetListController
from src.shared.ui.theme import bind_theme, get_theme


@dataclass(frozen=True, slots=True)
class EvidenceLineItem:
    """One human-readable evidence row with an optional action."""

    kind: str
    label: str
    text: str
    action_type: str = ""
    action_value: str = ""
    action_label: str = ""
    tone: str = "neutral"

    def has_action(self) -> bool:
        return bool(self.action_type and self.action_value)

    def display_text(self) -> str:
        if self.text:
            return f"{self.label}：{self.text}"
        return self.label


@dataclass(frozen=True, slots=True)
class _KeyedEvidenceLine:
    """Internal model carrying the stable identity of an evidence row."""

    key: tuple[object, ...]
    item: EvidenceLineItem


@dataclass(frozen=True, slots=True)
class _KeyedEvidenceAction:
    """Internal model carrying the stable identity of an action button."""

    key: tuple[object, ...]
    item: EvidenceLineItem


class EvidenceActionBar(QWidget):
    """Compact action row for evidence-related navigation and artifacts."""

    action_requested = Signal(str, str)

    def __init__(self, *, parent=None) -> None:
        super().__init__(parent)
        self._items: list[EvidenceLineItem] = []
        self._buttons: dict[str, QPushButton] = {}
        self._button_items: dict[QPushButton, EvidenceLineItem] = {}
        self.setObjectName("shared_evidence_action_bar")

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._layout.addStretch(1)
        self._button_controller = KeyedWidgetListController[
            _KeyedEvidenceAction,
            tuple[object, ...],
        ](
            layout=self._layout,
            create_widget=self._create_button,
            update_widget=self._update_button,
            dispose_widget=self._dispose_button,
            key=lambda entry: entry.key,
            start_index=0,
        )
        self.setVisible(False)

    def set_actions(self, items: Iterable[EvidenceLineItem]) -> None:
        actions = [item for item in items if item.has_action()]
        self._items = _dedupe_evidence_actions(actions)
        self._reconcile_buttons()
        self.setVisible(bool(self._items))

    def clear(self) -> None:
        self.set_actions(())

    def current_actions(self) -> list[tuple[str, str, str]]:
        return [
            (item.kind, item.action_type, item.action_value)
            for item in self._items
        ]

    def button_for_action_type(self, action_type: str) -> QPushButton | None:
        return self._buttons.get(str(action_type or "").strip())

    def _reconcile_buttons(self) -> None:
        self._buttons.clear()
        entries = _keyed_evidence_actions(self._items)
        self._button_controller.reconcile(entries)
        for entry, widget in zip(entries, self._button_controller.widgets()):
            if not isinstance(widget, QPushButton):
                raise TypeError("evidence action controller received an unexpected widget")
            self._buttons.setdefault(entry.item.action_type, widget)

    def _create_button(self, entry: _KeyedEvidenceAction) -> QWidget:
        button = QPushButton("", self)
        button.setCursor(Qt.PointingHandCursor)
        button.setIconSize(QSize(16, 16))
        button.clicked.connect(
            lambda _checked=False, target=button: self._emit_button_action(target)
        )
        apply_button_variant(button, "secondary")
        return button

    def _update_button(
        self,
        widget: QWidget,
        entry: _KeyedEvidenceAction,
        _index: int,
    ) -> None:
        if not isinstance(widget, QPushButton):
            raise TypeError("evidence action controller received an unexpected widget")
        line = entry.item
        self._button_items[widget] = line
        widget.setObjectName(f"shared_evidence_action_btn_{line.action_type}")
        widget.setText(line.action_label or _default_evidence_action_label(line))
        widget.setToolTip(f"{widget.text()}：{line.action_value}")
        widget.setStyleSheet(
            build_button_stylesheet(
                get_theme(),
                selector="QPushButton",
                min_height=28,
                padding_x=12,
                padding_y=3,
                font_size=get_theme().font_size_sm,
            )
        )

    def _dispose_button(self, widget: QWidget) -> None:
        if isinstance(widget, QPushButton):
            self._button_items.pop(widget, None)
        widget.hide()
        widget.setParent(None)
        widget.deleteLater()

    def _emit_button_action(self, button: QPushButton) -> None:
        line = self._button_items.get(button)
        if line is not None and line.has_action():
            self.action_requested.emit(line.action_type, line.action_value)


class EvidenceLineList(QWidget):
    """Structured evidence rows used by compact detail panes."""

    action_requested = Signal(str, str)

    def __init__(self, *, show_inline_actions: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._items: list[EvidenceLineItem] = []
        self._rows: list[QWidget] = []
        self._show_inline_actions = bool(show_inline_actions)
        self.setObjectName("shared_evidence_line_list")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._row_controller = KeyedWidgetListController[
            _KeyedEvidenceLine,
            tuple[object, ...],
        ](
            layout=self._layout,
            create_widget=self._create_row,
            update_widget=self._update_row,
            key=lambda entry: entry.key,
        )

        self._apply_theme()
        bind_theme(self, self._apply_theme)
        self.setVisible(False)

    def set_items(self, items: Iterable[EvidenceLineItem]) -> None:
        self._items = [item for item in items if item.label or item.text]
        self._row_controller.reconcile(_keyed_evidence_lines(self._items))
        self._rows = list(self._row_controller.widgets())
        self.setVisible(bool(self._items))

    def clear(self) -> None:
        self.set_items(())

    def current_items(self) -> list[EvidenceLineItem]:
        return list(self._items)

    def line_count(self) -> int:
        return len(self._items)

    def text_at(self, index: int) -> str:
        return self._items[index].display_text()

    def _create_row(self, entry: _KeyedEvidenceLine) -> QWidget:
        row = _EvidenceLineRow(
            entry.item,
            show_action=self._show_inline_actions,
            parent=self,
        )
        row.action_requested.connect(self.action_requested.emit)
        return row

    @staticmethod
    def _update_row(
        widget: QWidget,
        entry: _KeyedEvidenceLine,
        _index: int,
    ) -> None:
        if not isinstance(widget, _EvidenceLineRow):
            raise TypeError("evidence row controller received an unexpected widget")
        widget.set_item(entry.item)

    def _apply_theme(self) -> None:
        self.setStyleSheet("background: transparent;")


class _EvidenceLineRow(QFrame):
    action_requested = Signal(str, str)

    def __init__(
        self,
        item: EvidenceLineItem,
        *,
        show_action: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._item = item
        self._show_action = bool(show_action)
        self._action_btn: QPushButton | None = None
        self.setObjectName("shared_evidence_line_row")
        self.setFrameShape(QFrame.NoFrame)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)

        self._label = QLabel(item.label, self)
        self._label.setObjectName("shared_evidence_line_label")
        self._label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._label.setMinimumWidth(72)
        self._label.setWordWrap(False)
        layout.addWidget(self._label, 0)

        self._body = QLabel(item.text, self)
        self._body.setObjectName("shared_evidence_line_text")
        self._body.setWordWrap(True)
        self._body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._body, 1)

        if self._show_action:
            self._action_btn = QPushButton(
                "",
                self,
            )
            self._action_btn.setObjectName("shared_evidence_line_action")
            self._action_btn.setCursor(Qt.PointingHandCursor)
            self._action_btn.clicked.connect(self._emit_action_requested)
            apply_button_variant(self._action_btn, "ghost-primary")
            layout.addWidget(self._action_btn, 0)

        self.set_item(item)
        bind_theme(self, self._apply_theme)

    def set_item(self, item: EvidenceLineItem) -> None:
        """Update row content without replacing the row widget."""

        self._item = item
        self._label.setText(item.label)
        self._body.setText(item.text)
        if self._action_btn is not None:
            has_action = item.has_action()
            action_label = item.action_label or _default_evidence_action_label(item)
            self._action_btn.setText(action_label if has_action else "")
            self._action_btn.setToolTip(
                f"{action_label}：{item.action_value}" if has_action else ""
            )
            self._action_btn.setVisible(has_action)
        self._apply_theme()

    def _emit_action_requested(self, _checked: bool = False) -> None:
        if self._item.has_action():
            self.action_requested.emit(
                self._item.action_type,
                self._item.action_value,
            )

    def _apply_theme(self) -> None:
        t = get_theme()
        tone_color = {
            "primary": t.primary,
            "info": t.info,
            "success": t.success,
            "warning": t.warning,
            "error": t.error,
            "neutral": t.text_secondary,
        }.get(self._item.tone, t.text_secondary)
        self.setStyleSheet(
            f"""
            QFrame#shared_evidence_line_row {{
                background: {t.bg_input};
                border: 1px solid {t.border_light};
                border-radius: {t.radius_sm}px;
            }}
            QLabel#shared_evidence_line_label {{
                color: {t.text_hint};
                font-size: {t.font_size_sm}px;
                font-weight: {t.font_weight_emphasis};
                background: transparent;
            }}
            QLabel#shared_evidence_line_text {{
                color: {tone_color};
                font-size: {t.font_size_sm}px;
                background: transparent;
            }}
            """
        )


def _dedupe_evidence_actions(
    items: Iterable[EvidenceLineItem],
) -> list[EvidenceLineItem]:
    seen: set[tuple[str, str]] = set()
    result: list[EvidenceLineItem] = []
    for item in items:
        key = (item.action_type, item.action_value)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _keyed_evidence_actions(
    items: Iterable[EvidenceLineItem],
) -> list[_KeyedEvidenceAction]:
    """Attach stable logical-slot keys to action buttons.

    ``action_value`` is deliberately treated as mutable payload.  A navigation
    button can therefore keep its QWidget identity when the target changes and
    will emit the latest target on its next click.
    """

    occurrences: dict[tuple[object, ...], int] = {}
    keyed: list[_KeyedEvidenceAction] = []
    for item in items:
        base_key: tuple[object, ...] = (
            "action-button",
            item.kind,
            item.action_type,
        )
        occurrence = occurrences.get(base_key, 0)
        occurrences[base_key] = occurrence + 1
        keyed.append(
            _KeyedEvidenceAction(
                key=(*base_key, occurrence),
                item=item,
            )
        )
    return keyed


def _keyed_evidence_lines(
    items: Iterable[EvidenceLineItem],
) -> list[_KeyedEvidenceLine]:
    """Attach deterministic keys while allowing repeated evidence categories.

    Evidence actions use their target as semantic identity.  Plain display rows
    use kind and label, so changing only the displayed value updates the live
    row instead of replacing it.  The occurrence suffix keeps repeated rows
    valid and deterministic even when callers do not provide unique models.
    """

    occurrences: dict[tuple[object, ...], int] = {}
    keyed: list[_KeyedEvidenceLine] = []
    for item in items:
        if item.has_action():
            base_key: tuple[object, ...] = (
                "action",
                item.kind,
                item.action_type,
                item.action_value,
            )
        else:
            base_key = ("line", item.kind, item.label)
        occurrence = occurrences.get(base_key, 0)
        occurrences[base_key] = occurrence + 1
        keyed.append(
            _KeyedEvidenceLine(
                key=(*base_key, occurrence),
                item=item,
            )
        )
    return keyed


def _default_evidence_action_label(item: EvidenceLineItem) -> str:
    action_type = str(item.action_type or "").strip()
    if action_type == "navigate_parameter":
        return "定位参数"
    if action_type == "open_output":
        return "打开输出"
    if action_type == "open_replacement":
        return "打开来源"
    return "打开证据"


__all__ = ["EvidenceActionBar", "EvidenceLineItem", "EvidenceLineList"]
