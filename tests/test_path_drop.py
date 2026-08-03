from __future__ import annotations

from PySide6.QtCore import QMimeData, QPoint, QPointF, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from src.qt_api import QApplication, QLineEdit, QObject, Qt, QWidget
from src.shared.ui.path_drop import (
    PathAcceptancePolicy,
    PathDropController,
    PathRejectionCode,
    accepted_drop_paths,
    evaluate_drop_mime,
    local_paths_from_mime,
)


def _mime_for(*paths) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
    return mime


def test_path_drop_acceptance_is_local_shape_suffix_and_cardinality_aware(tmp_path):
    docx = tmp_path / "input.docx"
    docx.write_bytes(b"docx")
    markdown = tmp_path / "input.md"
    markdown.write_text("body", encoding="utf-8")
    folder = tmp_path / "images"
    folder.mkdir()

    assert local_paths_from_mime(_mime_for(docx)) == (str(docx.resolve()),)
    assert accepted_drop_paths(
        _mime_for(docx),
        PathAcceptancePolicy(suffixes=(".docx",)),
    ) == (str(docx.resolve()),)
    assert not accepted_drop_paths(
        _mime_for(markdown),
        PathAcceptancePolicy(suffixes=(".docx",)),
    )
    assert not accepted_drop_paths(
        _mime_for(docx, markdown),
        PathAcceptancePolicy(cardinality="single"),
    )
    assert accepted_drop_paths(
        _mime_for(docx, markdown),
        PathAcceptancePolicy(
            cardinality="multiple",
            suffixes=(".docx", ".md"),
        ),
    ) == (str(docx.resolve()), str(markdown.resolve()))
    assert accepted_drop_paths(
        _mime_for(folder),
        PathAcceptancePolicy(path_kind="directory"),
    ) == (str(folder.resolve()),)
    assert not accepted_drop_paths(
        _mime_for(folder),
        PathAcceptancePolicy(path_kind="file"),
    )

    wrong_suffix = evaluate_drop_mime(
        _mime_for(markdown),
        PathAcceptancePolicy(suffixes=(".docx",)),
    )
    assert not wrong_suffix.accepted
    assert wrong_suffix.rejection_code is PathRejectionCode.SUFFIX_NOT_ALLOWED
    assert wrong_suffix.detail == ".md"

    duplicate = evaluate_drop_mime(
        _mime_for(docx, docx),
        PathAcceptancePolicy(cardinality="multiple"),
    )
    assert duplicate.rejection_code is PathRejectionCode.DUPLICATE_PATH


def test_path_drop_controller_handles_present_and_future_surface_children(
    tmp_path,
    qapp,
):
    source = tmp_path / "source.docx"
    source.write_bytes(b"docx")
    rejected_source = tmp_path / "source.md"
    rejected_source.write_text("body", encoding="utf-8")
    host = QWidget()
    child = QLineEdit(host)
    received: list[tuple[str, ...]] = []
    rejected = []
    controller = PathDropController(
        PathAcceptancePolicy(suffixes=(".docx",)),
        parent=host,
    )
    controller.paths_dropped.connect(received.append)
    controller.proposal_rejected.connect(rejected.append)
    controller.install_on_surface(host)
    helper = QObject(host)
    assert helper not in controller._targets
    mime = _mime_for(source)

    drag = QDragEnterEvent(
        QPoint(2, 2),
        Qt.CopyAction,
        mime,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(child, drag)
    assert drag.isAccepted()

    drop = QDropEvent(
        QPointF(2, 2),
        Qt.CopyAction,
        mime,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(child, drop)

    assert drop.isAccepted()
    assert received == [(str(source.resolve()),)]

    dynamic_container = QWidget(host)
    dynamic_child = QLineEdit(dynamic_container)
    assert dynamic_child.acceptDrops()
    dynamic_drag = QDragEnterEvent(
        QPoint(2, 2),
        Qt.CopyAction,
        mime,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(dynamic_child, dynamic_drag)
    dynamic_drop = QDropEvent(
        QPointF(2, 2),
        Qt.CopyAction,
        mime,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(dynamic_child, dynamic_drop)

    assert dynamic_drag.isAccepted()
    assert dynamic_drop.isAccepted()
    assert received == [
        (str(source.resolve()),),
        (str(source.resolve()),),
    ]

    plain_mime = QMimeData()
    plain_mime.setText("internal-control-drag")
    plain_drag = QDragEnterEvent(
        QPoint(2, 2),
        Qt.CopyAction,
        plain_mime,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    assert controller.eventFilter(dynamic_child, plain_drag) is False
    assert rejected == []

    rejected_mime = _mime_for(rejected_source)
    rejected_drag = QDragEnterEvent(
        QPoint(2, 2),
        Qt.CopyAction,
        rejected_mime,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(child, rejected_drag)

    assert not rejected_drag.isAccepted()
    assert rejected[-1].rejection_code is PathRejectionCode.SUFFIX_NOT_ALLOWED
    host.close()
