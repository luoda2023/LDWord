import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.workbench.document_path_controller import WorkbenchDocumentPathController
from src.ui.panels.workbench.panel_v2 import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


def test_workbench_panel_uses_document_path_controller_for_path_sync():
    panel_source = inspect.getsource(WorkbenchPanel)
    module_source = (ROOT / "src/ui/panels/workbench/panel_v2.py").read_text(encoding="utf-8")

    assert "from .document_path_controller import WorkbenchDocumentPathController" in module_source
    assert "self._document_paths = WorkbenchDocumentPathController(" in panel_source
    assert "self._document_paths.accept_detail_selection(" in panel_source
    assert "self._document_paths.apply_loaded_document(" in panel_source
    assert "self._document_paths.resolve_execution_document()" in panel_source


def test_document_path_controller_owns_normalization_and_picker_fallback():
    controller_source = inspect.getsource(WorkbenchDocumentPathController)

    assert "def accept_detail_selection" in controller_source
    assert "def apply_loaded_document" in controller_source
    assert "def selected_existing_document" in controller_source
    assert "def resolve_execution_document" in controller_source
    assert "def has_selected_document" in controller_source
    assert "def _normalize_any_path" in controller_source
    assert "def _normalize_existing_path" in controller_source


def test_workbench_panel_breaks_setup_ui_into_focused_build_steps():
    panel_source = inspect.getsource(WorkbenchPanel)

    assert "def _initialize_panel_state" in panel_source
    assert "def _build_shell_widgets" in panel_source
    assert "def _build_detail_panes" in panel_source
    assert "def _build_controllers" in panel_source
    assert "self._initialize_panel_state()" in panel_source
    assert "self._build_shell_widgets()" in panel_source
    assert "self._build_detail_panes()" in panel_source
    assert "self._build_controllers()" in panel_source


def test_workbench_panel_syncs_existing_bridge_document_into_quick_execute_detail(tmp_path):
    app = _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        document_path = tmp_path / "draft.docx"
        document_path.write_bytes(b"")

        bridge.document_loaded.emit(str(document_path))
        app.processEvents()

        resolved = str(document_path.resolve())
        assert panel._document_paths.cached_document_path == resolved
        assert panel._quick_execution_detail.document_path() == resolved
    finally:
        panel.close()
        app.processEvents()


def test_workbench_panel_resolve_execution_document_prefers_existing_detail_path(tmp_path):
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        document_path = tmp_path / "selected.docx"
        document_path.write_bytes(b"")
        panel._quick_execution_detail.set_document_path(str(document_path))

        resolved = panel._resolve_document_path_for_execution()

        assert resolved == str(document_path.resolve())
        assert panel._document_paths.cached_document_path == resolved
        assert panel._quick_execution_detail.document_path() == resolved
    finally:
        panel.close()


def test_workbench_panel_resolve_execution_document_falls_back_to_cached_path(tmp_path):
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        document_path = tmp_path / "cached.docx"
        document_path.write_bytes(b"")
        cached = str(document_path.resolve())
        panel._document_paths.accept_detail_selection(cached)
        panel._quick_execution_detail.set_document_path("")

        resolved = panel._resolve_document_path_for_execution()

        assert resolved == cached
        assert panel._quick_execution_detail.document_path() == cached
    finally:
        panel.close()
