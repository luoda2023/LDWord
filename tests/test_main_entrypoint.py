from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main


def test_run_app_defaults_to_gui_when_no_input(monkeypatch):
    def fake_start_gui():
        return 123

    def fake_run_cli(_args):
        pytest.fail("CLI should not run when the app starts without an input path.")

    monkeypatch.setattr(main, "_start_gui", fake_start_gui)
    monkeypatch.setattr(main, "_run_cli", fake_run_cli)

    assert main.run_app([]) == 123


def test_run_app_uses_cli_when_input_is_provided(monkeypatch):
    def fake_start_gui():
        pytest.fail("GUI should not run when a CLI input path is provided.")

    def fake_run_cli(args):
        assert args.input == "example.docx"
        return 321

    monkeypatch.setattr(main, "_start_gui", fake_start_gui)
    monkeypatch.setattr(main, "_run_cli", fake_run_cli)

    assert main.run_app(["example.docx"]) == 321


def test_start_gui_uses_lazy_file_handler_for_exception_logging():
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "logging.basicConfig(" not in source
    assert "logging.FileHandler(" in source
    assert "delay=True" in source
