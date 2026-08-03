from __future__ import annotations

from pathlib import Path

import pytest

from scripts import verify_windows_installer as verifier


class _FakeProcess:
    def __init__(self, *, return_code: int | None = None) -> None:
        self.return_code = return_code
        self.terminated = False

    def poll(self):
        return self.return_code

    def terminate(self) -> None:
        self.terminated = True
        self.return_code = -15

    def wait(self, timeout=None):
        del timeout
        return self.return_code

    def kill(self) -> None:
        self.return_code = -9


def _fast_clock(monkeypatch):
    current = {"value": 0.0}

    def monotonic() -> float:
        current["value"] += 0.5
        return current["value"]

    monkeypatch.setattr(verifier.time, "monotonic", monotonic)
    monkeypatch.setattr(verifier.time, "sleep", lambda _seconds: None)


def test_startup_verification_requires_main_window_readiness(tmp_path, monkeypatch):
    process = _FakeProcess()
    _fast_clock(monkeypatch)
    monkeypatch.setattr(verifier.subprocess, "Popen", lambda *_args, **_kwargs: process)

    with pytest.raises(
        verifier.InstallerVerificationError,
        match="did not report startup readiness",
    ):
        verifier._verify_startup(Path("Alavette-Form.exe"), tmp_path)

    assert process.terminated is True


def test_startup_verification_accepts_valid_marker_and_settles(
    tmp_path,
    monkeypatch,
):
    process = _FakeProcess()
    _fast_clock(monkeypatch)

    def launch(*_args, **kwargs):
        ready_file = Path(kwargs["env"]["ALAVETTE_STARTUP_READY_FILE"])
        ready_file.write_text("ready\n", encoding="utf-8")
        return process

    monkeypatch.setattr(verifier.subprocess, "Popen", launch)

    verifier._verify_startup(Path("Alavette-Form.exe"), tmp_path)

    assert process.terminated is True


def test_startup_verification_rejects_early_process_exit(tmp_path, monkeypatch):
    process = _FakeProcess(return_code=1)
    monkeypatch.setattr(verifier.subprocess, "Popen", lambda *_args, **_kwargs: process)

    with pytest.raises(
        verifier.InstallerVerificationError,
        match="exited before startup readiness with code 1",
    ):
        verifier._verify_startup(Path("Alavette-Form.exe"), tmp_path)
