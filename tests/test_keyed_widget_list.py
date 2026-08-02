from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.qt_api import QLabel, QVBoxLayout, QWidget
from src.shared.ui.keyed_widget_list import KeyedWidgetListController


@dataclass(frozen=True)
class _Row:
    key: str
    label: str


def _layout_widgets(layout: QVBoxLayout) -> tuple[QWidget, ...]:
    widgets: list[QWidget] = []
    for index in range(layout.count()):
        widget = layout.itemAt(index).widget()
        if widget is not None:
            widgets.append(widget)
    return tuple(widgets)


def test_reconcile_preserves_retained_widget_identity_and_reports_diff(qapp) -> None:
    container = QWidget()
    layout = QVBoxLayout(container)
    header = QLabel("header", container)
    layout.addWidget(header)
    layout.addStretch(1)

    created: list[str] = []
    disposed: list[QWidget] = []

    def create_widget(item: _Row) -> QWidget:
        created.append(item.key)
        return QLabel(parent=container)

    def update_widget(widget: QWidget, item: _Row, index: int) -> None:
        assert isinstance(widget, QLabel)
        widget.setText(f"{index + 1}:{item.label}")

    controller = KeyedWidgetListController[_Row, str](
        layout=layout,
        create_widget=create_widget,
        update_widget=update_widget,
        dispose_widget=disposed.append,
        start_index=1,
    )

    initial = controller.reconcile(
        [_Row("a", "Alpha"), _Row("b", "Beta"), _Row("c", "Gamma")],
        key=lambda item: item.key,
    )
    assert initial.added == ("a", "b", "c")
    assert initial.removed == ()
    assert initial.moved == ()
    assert initial.retained == ()
    assert initial.changed is True
    assert controller.keys() == ("a", "b", "c")
    assert tuple(item.label for item in controller.items()) == ("Alpha", "Beta", "Gamma")
    assert created == ["a", "b", "c"]

    original_a = controller.widget_for("a")
    original_b = controller.widget_for("b")
    original_c = controller.widget_for("c")
    assert original_a is not None
    assert original_b is not None
    assert original_c is not None
    assert _layout_widgets(layout) == (header, original_a, original_b, original_c)

    change = controller.reconcile(
        [_Row("c", "Gamma 2"), _Row("b", "Beta 2"), _Row("d", "Delta")]
    )

    assert change.added == ("d",)
    assert change.removed == ("a",)
    assert change.moved == ("c",)
    assert change.retained == ("c", "b")
    assert created == ["a", "b", "c", "d"]
    assert disposed == [original_a]
    assert layout.indexOf(original_a) == -1
    assert controller.widget_for("c") is original_c
    assert controller.widget_for("b") is original_b
    assert controller.keys() == ("c", "b", "d")
    assert tuple(widget.text() for widget in controller.widgets()) == (
        "1:Gamma 2",
        "2:Beta 2",
        "3:Delta",
    )
    assert _layout_widgets(layout) == (header, *controller.widgets())
    assert layout.itemAt(layout.count() - 1).spacerItem() is not None


def test_insert_move_and_remove_are_incremental_and_update_indexes(qapp) -> None:
    container = QWidget()
    layout = QVBoxLayout(container)
    created: list[str] = []
    disposed: list[QWidget] = []

    def create_widget(item: _Row) -> QWidget:
        created.append(item.key)
        return QLabel(parent=container)

    controller = KeyedWidgetListController[_Row, str](
        layout=layout,
        create_widget=create_widget,
        update_widget=lambda widget, item, index: widget.setObjectName(
            f"{index}:{item.key}:{item.label}"
        ),
        dispose_widget=disposed.append,
        key=lambda item: item.key,
    )
    controller.reconcile([_Row("a", "A"), _Row("c", "C")])
    widget_a = controller.widget_for("a")
    widget_c = controller.widget_for("c")

    inserted = controller.insert(1, _Row("b", "B"))
    widget_b = controller.widget_for("b")
    assert inserted.added == ("b",)
    assert inserted.moved == ("c",)
    assert inserted.retained == ("a", "c")
    assert created == ["a", "c", "b"]
    assert controller.keys() == ("a", "b", "c")
    assert controller.widget_for("a") is widget_a
    assert controller.widget_for("c") is widget_c
    assert tuple(widget.objectName() for widget in controller.widgets()) == (
        "0:a:A",
        "1:b:B",
        "2:c:C",
    )

    moved = controller.move("c", 0)
    assert moved.moved == ("c", "a", "b")
    assert controller.keys() == ("c", "a", "b")
    assert controller.widget_for("a") is widget_a
    assert controller.widget_for("b") is widget_b
    assert controller.widget_for("c") is widget_c
    assert tuple(widget.objectName() for widget in controller.widgets()) == (
        "0:c:C",
        "1:a:A",
        "2:b:B",
    )

    removed = controller.remove("a")
    assert removed.removed == ("a",)
    assert removed.moved == ("b",)
    assert disposed == [widget_a]
    assert controller.keys() == ("c", "b")
    assert controller.widget_for("a") is None
    assert controller.widget_for("c") is widget_c
    assert controller.widget_for("b") is widget_b

    missing = controller.remove("missing")
    assert missing.changed is False
    assert missing.retained == ("c", "b")


def test_default_disposal_hides_widget_before_native_detach(qapp) -> None:
    container = QWidget()
    layout = QVBoxLayout(container)
    controller = KeyedWidgetListController[_Row, str](
        layout=layout,
        create_widget=lambda item: QLabel(item.label, container),
        key=lambda item: item.key,
    )
    controller.reconcile([_Row("a", "A")])
    removed_widget = controller.widget_for("a")
    assert removed_widget is not None
    container.show()
    qapp.processEvents()
    assert removed_widget.isVisible()

    controller.remove("a")

    assert removed_widget.isHidden()
    assert removed_widget.parent() is None


def test_reconcile_validates_all_keys_before_mutating_current_widgets(qapp) -> None:
    container = QWidget()
    layout = QVBoxLayout(container)
    created: list[str] = []

    def create_widget(item: _Row) -> QWidget:
        created.append(item.key)
        return QLabel(item.label, container)

    controller = KeyedWidgetListController[_Row, str](
        layout=layout,
        create_widget=create_widget,
    )
    controller.reconcile([_Row("a", "A")], key=lambda item: item.key)
    original = controller.widget_for("a")

    with pytest.raises(ValueError, match="duplicate key"):
        controller.reconcile([_Row("b", "B1"), _Row("b", "B2")])

    assert created == ["a"]
    assert controller.keys() == ("a",)
    assert controller.widget_for("a") is original
    assert layout.indexOf(original) == 0

    unhashable_container = QWidget()
    unhashable_controller = KeyedWidgetListController[list[str], str](
        layout=QVBoxLayout(unhashable_container),
        create_widget=lambda _item: QLabel(),
    )
    with pytest.raises(TypeError, match="hashable"):
        unhashable_controller.reconcile([["not-hashable"]], key=lambda item: item)  # type: ignore[arg-type,return-value]
    assert len(unhashable_controller) == 0


def test_factory_failure_disposes_only_provisional_widgets_and_keeps_old_state(qapp) -> None:
    container = QWidget()
    layout = QVBoxLayout(container)
    disposed: list[QWidget] = []

    def create_widget(item: _Row) -> QWidget:
        if item.key == "c":
            raise RuntimeError("factory failed")
        return QLabel(item.label, container)

    controller = KeyedWidgetListController[_Row, str](
        layout=layout,
        create_widget=create_widget,
        dispose_widget=disposed.append,
        key=lambda item: item.key,
    )
    controller.reconcile([_Row("a", "A")])
    original = controller.widget_for("a")

    with pytest.raises(RuntimeError, match="factory failed"):
        controller.reconcile([_Row("a", "A2"), _Row("b", "B"), _Row("c", "C")])

    assert len(disposed) == 1
    assert isinstance(disposed[0], QLabel)
    assert disposed[0].text() == "B"
    assert controller.keys() == ("a",)
    assert controller.widget_for("a") is original
    assert controller.item_for("a") == _Row("a", "A")
    assert layout.indexOf(original) == 0


def test_mutation_argument_errors_do_not_change_the_sequence(qapp) -> None:
    container = QWidget()
    controller = KeyedWidgetListController[_Row, str](
        layout=QVBoxLayout(container),
        create_widget=lambda item: QLabel(item.label, container),
        key=lambda item: item.key,
    )
    controller.reconcile([_Row("a", "A"), _Row("b", "B")])
    original_widgets = controller.widgets()

    with pytest.raises(ValueError, match="duplicate key"):
        controller.insert(1, _Row("a", "duplicate"))
    with pytest.raises(IndexError, match="insert index"):
        controller.insert(3, _Row("c", "C"))
    with pytest.raises(KeyError):
        controller.move("missing", 0)
    with pytest.raises(IndexError, match="target index"):
        controller.move("a", 2)

    assert controller.keys() == ("a", "b")
    assert controller.widgets() == original_widgets


def test_key_selector_is_required_before_item_based_mutations(qapp) -> None:
    container = QWidget()
    controller = KeyedWidgetListController[_Row, str](
        layout=QVBoxLayout(container),
        create_widget=lambda item: QLabel(item.label, container),
    )

    with pytest.raises(ValueError, match="key selector"):
        controller.reconcile([_Row("a", "A")])
    with pytest.raises(ValueError, match="key selector"):
        controller.insert(0, _Row("a", "A"))

    assert len(controller) == 0
