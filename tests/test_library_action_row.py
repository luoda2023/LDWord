import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui.library_action_row import LibraryActionRow


def _app():
    return QApplication.instance() or QApplication([])


def test_library_action_row_keeps_internal_containers_transparent():
    _app()
    row = LibraryActionRow(object_name="test_library_actions")

    try:
        row.add_action("new", "新建", icon_name="plus")
        row.add_action(
            "delete",
            "删除",
            icon_name="trash-2",
            variant="ghost-danger",
            side="right",
        )
        qss = row.styleSheet()

        assert "QWidget#test_library_actions" in qss
        assert "QWidget#test_library_actions_left" in qss
        assert "QWidget#test_library_actions_right" in qss
        assert "background: transparent;" in qss
    finally:
        row.close()
