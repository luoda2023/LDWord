"""Helpers for TOC field detection and best-effort Word field refresh."""

from __future__ import annotations

import os
import shutil
import subprocess
from src.shared.win_process import run_hidden
import sys
import tempfile
import uuid
from pathlib import Path

from lxml import etree

from src.app_meta import APP_TEMP_DIR_NAME
from src.shared.engine.field_builder import iter_field_instructions
from src.shared.engine.ooxml_ops import qn

_DISABLE_WORD_COM_REFRESH_ENV = "LARK_DISABLE_WORD_COM_REFRESH"
_ENABLE_WORD_COM_IN_TESTS_ENV = "LARK_ENABLE_WORD_COM_IN_TESTS"
_FALSEY_ENV_VALUES = {"", "0", "false", "no", "off"}

_PS_REFRESH_SCRIPT = r"""
$ErrorActionPreference = 'Stop'

$docPath = $env:DOCX_REFRESH_PATH
if (-not $docPath) {
    throw "DOCX_REFRESH_PATH is empty."
}
if (-not (Test-Path -LiteralPath $docPath)) {
    throw "File not found: $docPath"
}

$word = $null
$doc = $null

try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0

    $doc = $word.Documents.Open($docPath, $false, $false)
    $doc.Repaginate() | Out-Null

    foreach ($toc in @($doc.TablesOfContents)) {
        $toc.Update() | Out-Null
        $toc.UpdatePageNumbers() | Out-Null
    }

    foreach ($para in @($doc.Paragraphs)) {
        foreach ($fld in @($para.Range.Fields)) {
            try {
                $code = ($fld.Code.Text + '').ToUpperInvariant()
                if ($code.Contains('PAGEREF') -or $code.Contains('TOC')) {
                    $fld.Update() | Out-Null
                }
            } catch {
            }
        }
    }

    $doc.Repaginate() | Out-Null
    foreach ($toc in @($doc.TablesOfContents)) {
        $toc.Update() | Out-Null
        $toc.UpdatePageNumbers() | Out-Null
    }

    $doc.Save()
}
finally {
    if ($doc -ne $null) {
        try { $doc.Close() } catch {}
        try { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc) } catch {}
    }
    if ($word -ne $null) {
        try { $word.Quit() } catch {}
        try { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) } catch {}
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
"""

_PYWIN32_REFRESH_CHILD = r"""
import os
from pathlib import Path

doc_path = (os.environ.get("DOCX_REFRESH_PATH") or "").strip()
if not doc_path:
    raise RuntimeError("DOCX_REFRESH_PATH is empty.")

import pythoncom
import win32com.client

word = None
doc = None
pythoncom.CoInitialize()
try:
    p = str(Path(doc_path).resolve())
    word = win32com.client.DispatchEx("Word.Application")
    try:
        word.Visible = False
    except Exception:
        pass
    try:
        word.DisplayAlerts = 0
    except Exception:
        pass

    doc = word.Documents.Open(
        p,
        False, False, False, "", "", False, "", "", 0, 0, False, True
    )
    doc.Repaginate()

    for toc in list(doc.TablesOfContents):
        try:
            toc.Update()
            toc.UpdatePageNumbers()
        except Exception:
            pass

    for para in list(doc.Paragraphs):
        try:
            fields = list(para.Range.Fields)
        except Exception:
            continue
        for fld in fields:
            try:
                code = (fld.Code.Text or "").upper()
            except Exception:
                code = ""
            if ("PAGEREF" in code) or ("TOC" in code):
                try:
                    fld.Update()
                except Exception:
                    pass

    doc.Repaginate()
    for toc in list(doc.TablesOfContents):
        try:
            toc.Update()
            toc.UpdatePageNumbers()
        except Exception:
            pass

    doc.Save()
    print("ok(pywin32)")
finally:
    if doc is not None:
        try:
            doc.Close(False)
        except Exception:
            pass
    if word is not None:
        try:
            word.Quit()
        except Exception:
            pass
    pythoncom.CoUninitialize()
"""


def _env_flag(name: str) -> bool:
    value = os.environ.get(name)
    if value is None:
        return False
    return value.strip().lower() not in _FALSEY_ENV_VALUES


def _is_toc_instruction(instr: str) -> bool:
    normalized = " ".join((instr or "").upper().split())
    return normalized.startswith("TOC ")


def document_has_toc(doc) -> bool:
    """Return True when the document body contains a TOC field."""
    body = doc.element.body
    return any(
        _is_toc_instruction(instr)
        for _kind, _elem, instr in iter_field_instructions(body)
    )


def ensure_update_fields_on_open(doc) -> None:
    """Set w:updateFields=true so Word refreshes fields when opening the file."""
    settings = doc.settings.element
    node = settings.find(qn("w:updateFields"))
    if node is None:
        node = etree.SubElement(settings, qn("w:updateFields"))
    node.set(qn("w:val"), "true")


def _atomic_copy_back(src_path: Path, target_path: Path) -> None:
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)

        shutil.copy2(src_path, temp_path)
        try:
            with open(temp_path, "rb") as handle:
                os.fsync(handle.fileno())
        except OSError:
            pass
        os.replace(temp_path, target)
    except Exception:
        if temp_path is not None:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
        raise


def _automation_word_process_ids() -> set[int] | None:
    """Return hidden Word COM automation PIDs, excluding normal user Word windows."""
    if os.name != "nt":
        return set()

    script = (
        "$ErrorActionPreference = 'SilentlyContinue'; "
        "Get-CimInstance Win32_Process -Filter \"Name='WINWORD.EXE'\" | "
        "Where-Object { (($_.CommandLine + '') -match '(/Automation|-Embedding)') } | "
        "ForEach-Object { $_.ProcessId }"
    )
    try:
        proc = run_hidden(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None

    pids: set[int] = set()
    for raw in (proc.stdout or "").split():
        try:
            pid = int(raw.strip())
        except ValueError:
            continue
        if pid > 0:
            pids.add(pid)
    return pids


def _terminate_process_ids(process_ids: set[int]) -> None:
    if os.name != "nt" or not process_ids:
        return

    ids = ",".join(str(pid) for pid in sorted(process_ids))
    script = (
        f"$ids = @({ids}); "
        "foreach ($id in $ids) { "
        "try { Stop-Process -Id $id -Force -ErrorAction Stop } catch {} "
        "}"
    )
    try:
        run_hidden(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        pass


def _cleanup_new_automation_word_processes(before_ids: set[int] | None) -> None:
    if before_ids is None:
        return
    current_ids = _automation_word_process_ids()
    if current_ids is None:
        return
    _terminate_process_ids(current_ids - before_ids)


def _refresh_via_pywin32(doc_path: Path, timeout_sec: int) -> tuple[bool, str]:
    if getattr(sys, "frozen", False):
        return False, "pywin32 refresh skipped in frozen executable."
    exe_name = Path(sys.executable).name.lower()
    if "python" not in exe_name:
        return False, "pywin32 skipped: current runtime is not a Python interpreter."

    env = os.environ.copy()
    env["DOCX_REFRESH_PATH"] = str(doc_path.resolve())
    cmd = [sys.executable, "-c", _PYWIN32_REFRESH_CHILD]
    before_word_ids = _automation_word_process_ids()
    try:
        proc = run_hidden(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"pywin32 refresh timed out after {timeout_sec}s."
    except Exception as exc:
        return False, f"pywin32 refresh failed to start: {exc}"
    finally:
        _cleanup_new_automation_word_processes(before_word_ids)

    if proc.returncode == 0:
        return True, (proc.stdout or "").strip() or "ok(pywin32)"

    detail = (proc.stderr or "").strip() or (proc.stdout or "").strip()
    return False, detail or f"pywin32 child exited with code {proc.returncode}"


def _refresh_via_powershell(doc_path: Path, timeout_sec: int) -> tuple[bool, str]:
    env = os.environ.copy()
    env["DOCX_REFRESH_PATH"] = str(doc_path.resolve())
    cmd = [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        _PS_REFRESH_SCRIPT,
    ]
    before_word_ids = _automation_word_process_ids()
    try:
        proc = run_hidden(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"Word field refresh timed out after {timeout_sec}s."
    except Exception as exc:
        return False, f"Word field refresh failed to start: {exc}"
    finally:
        _cleanup_new_automation_word_processes(before_word_ids)

    if proc.returncode == 0:
        return True, "ok(powershell)"

    detail = (proc.stderr or "").strip() or (proc.stdout or "").strip()
    return False, detail or f"powershell exited with code {proc.returncode}"


def refresh_doc_fields_with_word(doc_path: str, timeout_sec: int = 30) -> tuple[bool, str]:
    """Best-effort in-place field refresh using local Microsoft Word on Windows."""
    if _env_flag(_DISABLE_WORD_COM_REFRESH_ENV):
        return False, "Word COM refresh disabled by LARK_DISABLE_WORD_COM_REFRESH."
    if os.name != "nt":
        return False, "Word COM refresh requires Windows."
    if os.environ.get("PYTEST_CURRENT_TEST") and not _env_flag(
        _ENABLE_WORD_COM_IN_TESTS_ENV
    ):
        return False, "Word COM refresh skipped under pytest."

    target = Path(doc_path)
    if not target.exists():
        return False, f"Output file not found: {doc_path}"

    tmp_dir = Path(tempfile.gettempdir()) / APP_TEMP_DIR_NAME
    tmp_dir.mkdir(parents=True, exist_ok=True)
    shadow = tmp_dir / f"{uuid.uuid4().hex}.docx"
    try:
        shutil.copy2(target, shadow)
    except Exception as exc:
        return False, f"Failed to prepare refresh shadow copy: {exc}"

    try:
        ok, detail = _refresh_via_pywin32(shadow, timeout_sec)
        if ok:
            _atomic_copy_back(shadow, target)
            return True, detail

        ok_ps, detail_ps = _refresh_via_powershell(shadow, timeout_sec)
        if ok_ps:
            _atomic_copy_back(shadow, target)
            return True, detail_ps

        return False, f"{detail}; fallback failed: {detail_ps}"
    except Exception as exc:
        return False, str(exc)
    finally:
        try:
            shadow.unlink(missing_ok=True)
        except Exception:
            pass
