from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main


def test_parse_args_accepts_explicit_official_document_type():
    args = main.parse_args(["example.docx", "--document-type", "letter"])

    assert args.document_type == "letter"


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
