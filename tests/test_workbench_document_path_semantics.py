import logging
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ui.panels.workbench.document_path_controller import WorkbenchDocumentPathController


class _QuickExecutionDetailStub:
    def __init__(self, path: str = "") -> None:
        self._path = path
        self.synced_paths: list[str] = []

    def document_path(self) -> str:
        return self._path

    def set_document_path(self, file_path: str) -> None:
        self._path = file_path
        self.synced_paths.append(file_path)


def test_document_path_controller_logs_expanduser_failure_and_keeps_cleaned_path(monkeypatch, caplog):
    import src.ui.panels.workbench.document_path_controller as controller_module

    def _raise_expanduser(self):
        raise RuntimeError("expanduser boom")

    monkeypatch.setattr(controller_module.Path, "expanduser", _raise_expanduser)

    with caplog.at_level(logging.WARNING):
        normalized = WorkbenchDocumentPathController._normalize_any_path("  broken.docx  ")

    assert normalized == "broken.docx"
    assert any("expanduser" in record.getMessage() for record in caplog.records)


def test_document_path_controller_accepts_detail_selection_when_exists_probe_fails(
    monkeypatch,
    caplog,
    tmp_path,
):
    import src.ui.panels.workbench.document_path_controller as controller_module

    original_exists = controller_module.Path.exists
    selected_path = str((tmp_path / "selected.docx").resolve())
    detail = _QuickExecutionDetailStub()
    controller = WorkbenchDocumentPathController(detail, pick_document_path=lambda: None)

    def _exists_with_failure(self):
        if str(self) == selected_path:
            raise OSError("exists boom")
        return original_exists(self)

    monkeypatch.setattr(controller_module.Path, "exists", _exists_with_failure)

    with caplog.at_level(logging.WARNING):
        normalized = controller.accept_detail_selection(selected_path)

    assert normalized == selected_path
    assert controller.cached_document_path == selected_path
    assert detail.document_path() == selected_path
    assert detail.synced_paths == [selected_path]
    assert any("exists probe" in record.getMessage() for record in caplog.records)


def test_document_path_controller_resolve_execution_document_skips_cached_path_when_check_fails(
    monkeypatch,
    caplog,
    tmp_path,
):
    import src.ui.panels.workbench.document_path_controller as controller_module

    original_exists = controller_module.Path.exists
    failing_path = str(tmp_path / "stale.docx")
    picked_path = tmp_path / "picked.docx"
    picked_path.write_bytes(b"")
    expected = str(picked_path.resolve())

    detail = _QuickExecutionDetailStub()
    controller = WorkbenchDocumentPathController(
        detail,
        pick_document_path=lambda: str(picked_path),
    )
    controller._cached_document_path = failing_path

    def _exists_with_failure(self):
        if str(self) == failing_path:
            raise OSError("cached exists boom")
        return original_exists(self)

    monkeypatch.setattr(controller_module.Path, "exists", _exists_with_failure)

    with caplog.at_level(logging.WARNING):
        resolved = controller.resolve_execution_document()

    assert resolved == expected
    assert controller.cached_document_path == expected
    assert detail.document_path() == expected
    assert any("existing-path check" in record.getMessage() for record in caplog.records)


def test_document_path_controller_selected_existing_document_does_not_call_picker(tmp_path):
    cached_path = tmp_path / "cached.docx"
    cached_path.write_bytes(b"")
    expected = str(cached_path.resolve())
    picker_calls: list[bool] = []

    detail = _QuickExecutionDetailStub()
    controller = WorkbenchDocumentPathController(
        detail,
        pick_document_path=lambda: picker_calls.append(True) or str(tmp_path / "picked.docx"),
    )
    controller._cached_document_path = expected

    resolved = controller.selected_existing_document()

    assert resolved == expected
    assert controller.cached_document_path == expected
    assert detail.document_path() == expected
    assert picker_calls == []
