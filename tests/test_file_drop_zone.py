import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui.file_drop_zone import FileDropZone


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


def test_file_drop_zone_browse_uses_configured_dialog_arguments_and_emits(monkeypatch):
    _app()
    calls = {}
    picked_path = "C:/picked/report.docx"

    def _fake_get_open_file_name(parent, title, start_dir, file_filter):
        calls["title"] = title
        calls["start_dir"] = start_dir
        calls["file_filter"] = file_filter
        return (picked_path, "Docx")

    monkeypatch.setattr(
        "src.shared.ui.file_drop_zone.QFileDialog.getOpenFileName",
        staticmethod(_fake_get_open_file_name),
    )

    zone = FileDropZone(
        dialog_title="Pick Input",
        file_filter="Docx Files (*.docx)",
        start_dir="C:/start/here",
    )
    events = []
    zone.file_selected.connect(events.append)

    zone._browse_button.click()

    assert calls == {
        "title": "Pick Input",
        "start_dir": "C:/start/here",
        "file_filter": "Docx Files (*.docx)",
    }
    assert zone.file_path() == picked_path
    assert events == [picked_path]


def test_file_drop_zone_recent_files_selection_emits_file_selected():
    _app()
    zone = FileDropZone()
    events = []
    zone.file_selected.connect(events.append)
    zone.set_recent_files(["C:/recent/one.docx", "C:/recent/two.docx"])

    zone._recent_combo.setCurrentIndex(1)

    assert zone.file_path() == "C:/recent/two.docx"
    assert events == ["C:/recent/two.docx"]
