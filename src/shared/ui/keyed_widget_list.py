"""Incremental QWidget list management keyed by stable model identity.

The controller owns one contiguous region of a :class:`QBoxLayout`.  A
reconciliation creates widgets only for new keys, disposes widgets only for
removed keys, and moves existing widgets when the visual order changes.

This is intentionally a small, layout-level primitive.  It does not own the
models and it does not schedule deferred layout or scroll corrections.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from typing import Generic, TypeVar

from src.qt_api import QBoxLayout, QWidget


ItemT = TypeVar("ItemT")
KeyT = TypeVar("KeyT", bound=Hashable)

KeySelector = Callable[[ItemT], KeyT]
WidgetFactory = Callable[[ItemT], QWidget]
WidgetUpdater = Callable[[QWidget, ItemT, int], None]
WidgetDisposer = Callable[[QWidget], None]


@dataclass(frozen=True, slots=True)
class KeyedWidgetListChange(Generic[KeyT]):
    """Ordered keys affected by one list mutation.

    ``moved`` contains retained keys whose numeric visual index changed.  A
    key can therefore be present in both ``retained`` and ``moved``.  Index
    shifts caused by an insertion or removal are reported as moves as well.
    """

    added: tuple[KeyT, ...] = ()
    removed: tuple[KeyT, ...] = ()
    moved: tuple[KeyT, ...] = ()
    retained: tuple[KeyT, ...] = ()

    @property
    def changed(self) -> bool:
        """Return whether the mutation changed keys or their order."""

        return bool(self.added or self.removed or self.moved)


@dataclass(slots=True)
class _Entry(Generic[ItemT]):
    item: ItemT
    widget: QWidget


class KeyedWidgetListController(Generic[ItemT, KeyT]):
    """Keep a stable-keyed QWidget sequence synchronized with model items.

    Args:
        layout: Box layout containing the managed widget sequence.
        create_widget: Creates one widget for a newly observed item.
        update_widget: Optional callback invoked as ``(widget, item, index)``
            for every item after each successful mutation.  It can refresh
            values, row numbers, and first/last-row styling without rebuilding
            widgets.
        dispose_widget: Optional callback invoked after a removed widget has
            left the layout.  The default detaches it and calls ``deleteLater``.
        key: Optional default item-key selector.  It can instead be supplied to
            the first ``reconcile`` or ``insert`` call.
        start_index: Layout index at which the managed contiguous region begins.
            Existing header items before this index and trailing stretches or
            widgets after the region are preserved.

    External code must not insert layout items inside the managed region.  It
    may safely mutate items before ``start_index`` or after the managed region.
    """

    def __init__(
        self,
        *,
        layout: QBoxLayout,
        create_widget: WidgetFactory[ItemT],
        update_widget: WidgetUpdater[ItemT] | None = None,
        dispose_widget: WidgetDisposer | None = None,
        key: KeySelector[ItemT, KeyT] | None = None,
        start_index: int = 0,
    ) -> None:
        if not isinstance(layout, QBoxLayout):
            raise TypeError("layout must be a QBoxLayout")
        if start_index < 0:
            raise ValueError("start_index must be non-negative")
        if start_index > layout.count():
            raise ValueError("start_index cannot exceed the current layout item count")

        self._layout = layout
        self._create_widget = create_widget
        self._update_widget = update_widget
        self._dispose_widget = dispose_widget or self._default_dispose_widget
        self._key_selector = key
        self._start_index = int(start_index)
        self._keys: list[KeyT] = []
        self._entries: dict[KeyT, _Entry[ItemT]] = {}

    def reconcile(
        self,
        items: Iterable[ItemT],
        *,
        key: KeySelector[ItemT, KeyT] | None = None,
    ) -> KeyedWidgetListChange[KeyT]:
        """Synchronize widgets to ``items`` while preserving retained identity.

        All desired keys are validated before the current layout is mutated.
        Duplicate or unhashable keys therefore leave the existing sequence
        untouched.
        """

        selector = self._resolve_key_selector(key)
        desired = [(self._validated_key(selector(item)), item) for item in items]
        self._validate_unique_keys(desired)
        change = self._apply(desired)
        if key is not None:
            self._key_selector = key
        return change

    def insert(
        self,
        index: int,
        item: ItemT,
        *,
        key: KeySelector[ItemT, KeyT] | None = None,
    ) -> KeyedWidgetListChange[KeyT]:
        """Insert one new item at ``index`` without rebuilding retained rows."""

        if index < 0 or index > len(self._keys):
            raise IndexError("insert index out of range")
        selector = self._resolve_key_selector(key)
        item_key = self._validated_key(selector(item))
        if item_key in self._entries:
            raise ValueError(f"duplicate key: {item_key!r}")

        desired = self._ordered_pairs()
        desired.insert(index, (item_key, item))
        change = self._apply(desired)
        if key is not None:
            self._key_selector = key
        return change

    def remove(self, key: KeyT) -> KeyedWidgetListChange[KeyT]:
        """Remove ``key``; a missing key is an idempotent no-op."""

        if key not in self._entries:
            return self._unchanged_result()
        desired = [(item_key, item) for item_key, item in self._ordered_pairs() if item_key != key]
        return self._apply(desired)

    def move(self, key: KeyT, target_index: int) -> KeyedWidgetListChange[KeyT]:
        """Move an existing item to an exact visual index without recreating it."""

        if key not in self._entries:
            raise KeyError(key)
        if target_index < 0 or target_index >= len(self._keys):
            raise IndexError("target index out of range")

        desired = self._ordered_pairs()
        current_index = self._keys.index(key)
        if current_index == target_index:
            self._update_all()
            return self._unchanged_result()
        pair = desired.pop(current_index)
        desired.insert(target_index, pair)
        return self._apply(desired)

    def widget_for(self, key: KeyT) -> QWidget | None:
        """Return the live widget for ``key``, or ``None`` when absent."""

        entry = self._entries.get(key)
        return None if entry is None else entry.widget

    def item_for(self, key: KeyT) -> ItemT | None:
        """Return the latest model item for ``key``, or ``None`` when absent."""

        entry = self._entries.get(key)
        return None if entry is None else entry.item

    def keys(self) -> tuple[KeyT, ...]:
        """Return keys in current visual order."""

        return tuple(self._keys)

    def items(self) -> tuple[ItemT, ...]:
        """Return the latest model items in current visual order."""

        return tuple(self._entries[item_key].item for item_key in self._keys)

    def widgets(self) -> tuple[QWidget, ...]:
        """Return managed widgets in current visual order."""

        return tuple(self._entries[item_key].widget for item_key in self._keys)

    def __len__(self) -> int:
        return len(self._keys)

    def _apply(
        self,
        desired: list[tuple[KeyT, ItemT]],
    ) -> KeyedWidgetListChange[KeyT]:
        old_keys = tuple(self._keys)
        old_indexes = {item_key: index for index, item_key in enumerate(old_keys)}
        desired_keys = tuple(item_key for item_key, _item in desired)
        desired_key_set = set(desired_keys)

        added = tuple(item_key for item_key in desired_keys if item_key not in self._entries)
        removed = tuple(item_key for item_key in old_keys if item_key not in desired_key_set)
        retained = tuple(item_key for item_key in desired_keys if item_key in self._entries)
        moved = tuple(
            item_key
            for index, item_key in enumerate(desired_keys)
            if item_key in old_indexes and old_indexes[item_key] != index
        )

        created: dict[KeyT, _Entry[ItemT]] = {}
        try:
            existing_widgets = {entry.widget for entry in self._entries.values()}
            added_set = set(added)
            for item_key, item in desired:
                if item_key not in added_set:
                    continue
                widget = self._create_widget(item)
                if not isinstance(widget, QWidget):
                    raise TypeError("create_widget must return a QWidget")
                if widget in existing_widgets or any(
                    entry.widget is widget for entry in created.values()
                ):
                    raise ValueError("create_widget returned the same QWidget for multiple keys")
                created[item_key] = _Entry(item=item, widget=widget)
        except Exception:
            for entry in created.values():
                self._dispose_widget(entry.widget)
            raise

        for item_key in removed:
            entry = self._entries.pop(item_key)
            self._layout.removeWidget(entry.widget)
            self._dispose_widget(entry.widget)

        self._entries.update(created)
        for item_key, item in desired:
            self._entries[item_key].item = item

        self._keys = list(desired_keys)
        for index, item_key in enumerate(self._keys):
            widget = self._entries[item_key].widget
            target_layout_index = self._start_index + index
            if self._layout.indexOf(widget) == target_layout_index:
                continue
            self._layout.removeWidget(widget)
            self._layout.insertWidget(target_layout_index, widget)

        self._update_all()
        return KeyedWidgetListChange(
            added=added,
            removed=removed,
            moved=moved,
            retained=retained,
        )

    def _update_all(self) -> None:
        if self._update_widget is None:
            return
        for index, item_key in enumerate(self._keys):
            entry = self._entries[item_key]
            self._update_widget(entry.widget, entry.item, index)

    def _ordered_pairs(self) -> list[tuple[KeyT, ItemT]]:
        return [(item_key, self._entries[item_key].item) for item_key in self._keys]

    def _resolve_key_selector(
        self,
        selector: KeySelector[ItemT, KeyT] | None,
    ) -> KeySelector[ItemT, KeyT]:
        if selector is not None:
            return selector
        if self._key_selector is None:
            raise ValueError("an item key selector is required")
        return self._key_selector

    @staticmethod
    def _validated_key(key: KeyT) -> KeyT:
        try:
            hash(key)
        except TypeError as exc:
            raise TypeError("item keys must be hashable") from exc
        return key

    @staticmethod
    def _validate_unique_keys(desired: list[tuple[KeyT, ItemT]]) -> None:
        seen: set[KeyT] = set()
        for item_key, _item in desired:
            if item_key in seen:
                raise ValueError(f"duplicate key: {item_key!r}")
            seen.add(item_key)

    def _unchanged_result(self) -> KeyedWidgetListChange[KeyT]:
        return KeyedWidgetListChange(retained=tuple(self._keys))

    @staticmethod
    def _default_dispose_widget(widget: QWidget) -> None:
        widget.hide()
        widget.setParent(None)
        widget.deleteLater()


__all__ = ["KeyedWidgetListChange", "KeyedWidgetListController"]
