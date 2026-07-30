import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication  # noqa: E402
from src.shared.ui.file_drop_zone import FileDropZone  # noqa: E402
from src.shared.ui.path_drop import PathAcceptancePolicy  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def test_file_drop_zone_set_file_round_trips_explicit_path():
    _app()
    zone = FileDropZone()

    explicit_path = "C:/docs/input-file.docx"
    zone.set_file(explicit_path)

    assert zone.file_path() == explicit_path


def test_file_drop_zone_can_reset_explicit_path_to_empty():
    _app()
    zone = FileDropZone()
    zone.set_file("C:/docs/input-file.docx")

    zone.set_file("")

    assert zone.file_path() == ""


def test_file_drop_zone_set_file_emits_file_selected_signal():
    _app()
    zone = FileDropZone()
    events = []
    zone.file_selected.connect(events.append)

    selected_path = "C:/demo.docx"
    zone.set_file(selected_path)

    assert events == [selected_path]


def test_file_drop_zone_browse_uses_configured_dialog_arguments_and_emits(
    monkeypatch,
    tmp_path,
):
    _app()
    calls = {}
    picked_path = tmp_path / "report.docx"
    picked_path.write_bytes(b"docx")

    def _fake_get_open_file_name(parent, title, start_dir, file_filter):
        calls["title"] = title
        calls["start_dir"] = start_dir
        calls["file_filter"] = file_filter
        return (str(picked_path), "Docx")

    monkeypatch.setattr(
        "src.shared.ui.file_drop_zone.QFileDialog.getOpenFileName",
        staticmethod(_fake_get_open_file_name),
    )

    zone = FileDropZone(
        dialog_title="Pick Input",
        start_dir="C:/start/here",
        policy=PathAcceptancePolicy(
            suffixes=(".docx",),
            dialog_label="Docx Files",
        ),
    )
    events = []
    zone.file_selected.connect(events.append)

    zone._browse_button.click()

    assert calls == {
        "title": "Pick Input",
        "start_dir": "C:/start/here",
        "file_filter": "Docx Files (*.docx);;所有文件 (*)",
    }
    assert zone.file_path() == str(picked_path)
    assert events == [str(picked_path)]


def test_file_drop_zone_recent_files_selection_emits_file_selected(tmp_path):
    _app()
    one = tmp_path / "one.docx"
    two = tmp_path / "two.docx"
    one.write_bytes(b"one")
    two.write_bytes(b"two")
    zone = FileDropZone(
        policy=PathAcceptancePolicy(suffixes=(".docx",))
    )
    events = []
    zone.file_selected.connect(events.append)
    zone.set_recent_files([str(one), str(two)])

    zone._recent_combo.setCurrentIndex(1)

    assert zone.file_path() == str(two)
    assert events == [str(two)]


def test_file_drop_zone_uses_shared_path_drop_controller(tmp_path):
    _app()
    source = tmp_path / "input.docx"
    source.write_bytes(b"docx")
    zone = FileDropZone(
        policy=PathAcceptancePolicy(suffixes=(".docx",))
    )
    events = []
    zone.file_selected.connect(events.append)

    zone._drop_controller.paths_dropped.emit((str(source),))

    assert zone.file_path() == str(source)
    assert events == [str(source)]
