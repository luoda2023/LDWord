from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main


def test_parse_args_accepts_explicit_official_document_type():
    args = main.parse_args(["example.docx", "--document-type", "letter"])

    assert args.document_type == "letter"


def test_startup_ready_probe_is_written_only_when_requested(tmp_path):
    ready_file = tmp_path / "startup" / "ready.txt"

    assert main._publish_startup_ready_probe({}) is None
    assert not ready_file.exists()

    result = main._publish_startup_ready_probe(
        {"ALAVETTE_STARTUP_READY_FILE": str(ready_file)}
    )

    assert result == ready_file
    assert ready_file.read_text(encoding="utf-8") == "ready\n"


def test_startup_ready_probe_is_published_only_after_main_window_is_shown():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    start_gui_source = source[source.index("def _start_gui"):source.index("def _run_cli")]
    before_show_callback, show_callback_and_after = start_gui_source.split(
        "    def _show_main_window() -> None:",
        maxsplit=1,
    )
    show_callback = show_callback_and_after.split(
        "    win.startup_status_changed.connect",
        maxsplit=1,
    )[0]

    assert "_publish_startup_ready_probe()" not in before_show_callback
    assert show_callback.index("win.show()") < show_callback.index(
        "_publish_startup_ready_probe()"
    )


def test_uninstall_cleanup_command_is_dispatched_before_argument_parsing(monkeypatch):
    monkeypatch.setattr(main, "_run_internal_maintenance_command", lambda argv: 73)
    monkeypatch.setattr(
        main,
        "parse_args",
        lambda _argv: pytest.fail("maintenance command should bypass public parsing"),
    )

    assert main.run_app(["--internal-uninstall-clean-user-data"]) == 73


def test_package_import_probe_checks_frozen_and_lazy_runtime_modules(monkeypatch):
    import importlib

    imported: list[str] = []
    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda module_name: imported.append(module_name),
    )

    assert main._run_package_import_probe() == 0
    assert imported == [
        "win32timezone",
        "src.ui.panels.preferences_panel",
        "src.assistant.ui.assistant_panel",
        "src.ui.panels.workbench.batch_generation_detail",
        "src.ui.panels.workbench.file_batch_execution_detail",
    ]


def test_package_import_probe_fails_closed_on_missing_module(monkeypatch):
    import importlib

    def missing_module(_module_name):
        raise ModuleNotFoundError("missing packaged dependency")

    monkeypatch.setattr(importlib, "import_module", missing_module)

    assert main._run_package_import_probe() == 1


def test_run_cli_passes_explicit_document_type_to_production_entry(
    tmp_path,
    monkeypatch,
):
    import src.cli_runner as cli_runner

    source = tmp_path / "example.docx"
    source.write_bytes(b"placeholder")
    captured = {}

    def fake_run(input_path, **kwargs):
        captured["input_path"] = input_path
        captured.update(kwargs)
        return 37

    monkeypatch.setattr(cli_runner, "run", fake_run)
    args = main.parse_args([str(source), "--document-type", "letter"])

    assert main._run_cli(args) == 37
    assert captured["input_path"] == source
    assert captured["document_type_id"] == "letter"


def test_run_app_defaults_to_gui_when_no_input(monkeypatch):
    def fake_start_gui(font_engine=None):
        assert font_engine is None
        return 123

    def fake_run_cli(_args):
        pytest.fail("CLI should not run when the app starts without an input path.")

    monkeypatch.setattr(main, "_start_gui", fake_start_gui)
    monkeypatch.setattr(main, "_run_cli", fake_run_cli)

    assert main.run_app([]) == 123


def test_run_app_uses_cli_when_input_is_provided(monkeypatch):
    def fake_start_gui(_font_engine=None):
        pytest.fail("GUI should not run when a CLI input path is provided.")

    def fake_run_cli(args):
        assert args.input == "example.docx"
        return 321

    monkeypatch.setattr(main, "_start_gui", fake_start_gui)
    monkeypatch.setattr(main, "_run_cli", fake_run_cli)

    assert main.run_app(["example.docx"]) == 321


def test_run_app_passes_explicit_font_engine_to_gui(monkeypatch):
    seen = []

    def fake_start_gui(font_engine=None):
        seen.append(font_engine)
        return 456

    monkeypatch.setattr(main, "_start_gui", fake_start_gui)

    assert main.run_app(["--gui", "--font-engine", "directwrite"]) == 456
    assert seen == ["directwrite"]


def test_start_gui_configures_font_engine_before_importing_qt_api():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    start_gui_source = source[source.index("def _start_gui"):source.index("def _run_cli")]

    assert start_gui_source.index("configure_application_windows_font_engine(font_engine)") < (
        start_gui_source.index("from src.qt_api import")
    )


def test_start_gui_uses_lazy_file_handler_for_exception_logging():
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "logging.basicConfig(" not in source
    assert "logging.FileHandler(" in source
    assert "delay=True" in source


def test_start_gui_guards_against_multiple_draft_owning_instances():
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "QLockFile" in source
    assert "instance_lock.tryLock(0)" in source
    assert "避免两个实例持有不同的草稿状态" in source
