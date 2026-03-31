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
