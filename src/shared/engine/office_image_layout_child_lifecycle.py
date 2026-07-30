"""Owned COM-session lifecycle for the isolated Office layout child."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.shared.engine.office_image_layout_contracts import (
    LayoutFailure,
    LayoutFailureCode,
)
from src.shared.engine.office_image_layout_fileio import atomic_write_json
from src.shared.engine.office_layout_probe import _application_process_id


class ChildBlocked(RuntimeError):
    def __init__(self, code: LayoutFailureCode, message: str, job_id: str = ""):
        self.failure = LayoutFailure(code, message, job_id)
        super().__init__(message)


@dataclass(slots=True)
class OfficeChildSession:
    adapter: Any
    shadow: Path
    pid_path: Path
    before_pids: set[int]
    application: Any = None
    document: Any = None
    pythoncom: Any = None
    pid: int | None = None
    open_count: int = 0

    def open(self) -> Any:
        import pythoncom

        pythoncom.CoInitialize()
        self.pythoncom = pythoncom
        self.application = self.adapter.create_application()
        self.application.Visible = False
        self.application.DisplayAlerts = 0
        try:
            self.application.AutomationSecurity = 3
        except Exception:
            pass
        self.document = self.adapter.open_shadow(self.application, self.shadow)
        self.open_count = 1
        self.pid = _application_process_id(self.application, self.document)
        if self.pid is None or self.pid in self.before_pids:
            raise ChildBlocked(
                LayoutFailureCode.PROCESS_OWNERSHIP_UNPROVEN,
                "DispatchEx did not yield a provably new Office PID/window",
            )
        atomic_write_json(self.pid_path, {"pid": self.pid})
        self.document.ActiveWindow.View.Type = 3
        if int(self.document.ActiveWindow.View.Type) != 3 or bool(
            self.application.Visible
        ):
            raise ChildBlocked(
                LayoutFailureCode.OFFICE_ERROR,
                "hidden Print Layout could not be established",
            )
        return self.document

    def close_success(self) -> None:
        self.document.Close(False)
        self.document = None
        self.application.Quit()
        self.application = None

    def release(self) -> None:
        if self.document is not None:
            try:
                self.document.Close(False)
            except Exception:
                pass
            self.document = None
        if self.application is not None:
            try:
                self.application.Quit()
            except Exception:
                pass
            self.application = None
        if self.pythoncom is not None:
            try:
                self.pythoncom.CoUninitialize()
            except Exception:
                pass
            self.pythoncom = None


__all__ = ["ChildBlocked", "OfficeChildSession"]
