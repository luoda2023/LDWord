# -*- coding: utf-8 -*-
"""Legacy Word format import service (.doc / .wps -> .docx).

The production engine is OOXML-only (python-docx reads .docx).  Legacy
binary Word documents (.doc) and WPS Writer documents (.wps) must be
converted to .docx before they can enter the pipeline.  This service
performs that conversion through the locally registered WPS Writer or
Microsoft Word COM automation, caching the result under the per-user
data root so repeated imports of the same source file are cheap.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from src.app_paths import app_data_root

LEGACY_WORD_SUFFIXES = frozenset({".doc", ".wps"})
_ED_DOCX_SUFFIXES = frozenset({".docx"})

# WPS Writer opens .doc/.wps/.docx; Microsoft Word opens .doc/.docx but not .wps.
_WPS_PROG_IDS = ("KWPS.Application", "KWPS.Application.1", "WPS.Application")
_WORD_PROG_IDS = ("Word.Application", "Word.Application.16", "Word.Application.8")


@dataclass(frozen=True)
class LegacyConversionResult:
    """Outcome of preparing an editable .docx for a source document."""

    docx_path: Path
    converted: bool  # True when the source was legacy and got converted.
    renderer: str = ""  # "wps" / "word" / "" when no conversion was needed.
    message: str = ""


def _converted_root() -> Path:
    return app_data_root() / "converted_legacy"


class LegacyWordImportError(RuntimeError):
    """Raised when a legacy document cannot be converted to .docx."""


def ensure_editable_docx(source: str | Path) -> LegacyConversionResult:
    """Return an editable .docx for *source*.

    - ``.docx`` sources pass through untouched.
    - ``.doc`` / ``.wps`` sources are converted through the local office
      COM automation into the per-user converted cache and returned.
    """
    path = Path(str(source or "")).expanduser()
    if not path.is_file():
        raise FileNotFoundError(path)
    suffix = path.suffix.casefold()
    if suffix in _ED_DOCX_SUFFIXES:
        return LegacyConversionResult(docx_path=path, converted=False)
    if suffix not in LEGACY_WORD_SUFFIXES:
        raise ValueError(f"unsupported_document_suffix:{suffix}")
    return _convert_legacy(path)


def _convert_legacy(source: Path) -> LegacyConversionResult:
    root = _converted_root()
    root.mkdir(parents=True, exist_ok=True)
    digest = _file_sha256(source)
    target = root / f"{source.stem}-{digest[:12]}.docx"
    if target.is_file() and target.stat().st_size > 0:
        return LegacyConversionResult(
            docx_path=target, converted=True, renderer="cache", message="cached"
        )
    # Keep concurrent imports of the same source from colliding.
    lock_path = root / f"{source.stem}-{digest[:12]}.lock"
    lock = _FileLock(lock_path)
    if not lock.acquire(timeout=45):
        # Another process is converting; wait for the file then fall through.
        deadline = 0
        # fall through to convert under the same lock owner semantics.
        _wait_for_file(target, timeout=60)
        if target.is_file() and target.stat().st_size > 0:
            return LegacyConversionResult(
                docx_path=target, converted=True, renderer="cache", message="cached"
            )
    try:
        if target.is_file() and target.stat().st_size > 0:
            return LegacyConversionResult(
                docx_path=target, converted=True, renderer="cache", message="cached"
            )
        renderer, converted = _convert_via_com(source, target)
        return LegacyConversionResult(
            docx_path=target, converted=True, renderer=renderer, message="converted"
        )
    finally:
        lock.release()


def _convert_via_com(source: Path, target: Path) -> tuple[str, Path]:
    """Convert *source* into *target* using WPS then Word COM automation."""
    try:
        import pythoncom  # noqa: F401
        import win32com.client  # noqa: F401
    except Exception as exc:  # pragma: no cover - environment dependent
        raise LegacyWordImportError(
            f"pywin32 不可用，无法转换 .{source.suffix} 文档：{exc}"
        ) from exc

    issues: list[str] = []
    for renderer, prog_ids in (("wps", _WPS_PROG_IDS), ("word", _WORD_PROG_IDS)):
        try:
            _convert_single_com(prog_ids, source, target)
            if target.is_file() and target.stat().st_size > 0:
                return renderer, target
            issues.append(f"{renderer}: 转换未生成文件")
        except Exception as exc:  # noqa: BLE001 - COM boundary
            target.unlink(missing_ok=True)
            issues.append(f"{renderer}: {exc}")
    message = "; ".join(issues) or "没有可用的 Office COM 转换器"
    raise LegacyWordImportError(
        f"无法将 .{source.suffix} 文档转换为 .docx（{message}）"
    )


def _convert_single_com(prog_ids, source: Path, target: Path) -> None:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    application = None
    document = None
    try:
        application = _dispatch_any(prog_ids)
        if application is None:
            raise RuntimeError("COM 程序未注册")
        application.Visible = False
        application.DisplayAlerts = 0
        document = application.Documents.Open(
            str(source.resolve()), ReadOnly=True, AddToRecentFiles=False
        )
        # wdFormatXMLDocument = 12 (.docx).  WPS honours the same numeric id.
        document.SaveAs2(str(target.resolve()), 12)
    finally:
        if document is not None:
            try:
                document.Close(False)
            except Exception:
                pass
        if application is not None:
            try:
                application.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def _dispatch_any(prog_ids):
    import win32com.client

    last_error: Exception | None = None
    for prog_id in prog_ids:
        try:
            return win32com.client.DispatchEx(prog_id)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    return None


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wait_for_file(path: Path, *, timeout: float) -> None:
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file() and path.stat().st_size > 0:
            return
        time.sleep(0.3)


class _FileLock:
    """A tiny cross-process advisory lock built on an exclusive file open."""

    def __init__(self, path: Path):
        self._path = path
        self._handle = None

    def acquire(self, *, timeout: float) -> bool:
        import time

        deadline = time.monotonic() + timeout
        while True:
            try:
                handle = os.open(
                    str(self._path), os.O_CREAT | os.O_EXCL | os.O_WRONLY
                )
                os.write(handle, str(os.getpid()).encode("ascii"))
                self._handle = handle
                return True
            except FileExistsError:
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.3)
            except OSError:
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.3)

    def release(self) -> None:
        if self._handle is not None:
            try:
                os.close(self._handle)
            except OSError:
                pass
            self._handle = None
        try:
            self._path.unlink(missing_ok=True)
        except OSError:
            pass


__all__ = [
    "LEGACY_WORD_SUFFIXES",
    "LegacyConversionResult",
    "LegacyWordImportError",
    "ensure_editable_docx",
]
