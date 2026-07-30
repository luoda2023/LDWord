"""Encoding-safe console output for Windows and redirected CLI streams."""

from __future__ import annotations

import locale
import sys
from typing import TextIO


def configure_console_output() -> None:
    """Make Python-owned stdout/stderr replace unencodable characters.

    Windows shells and redirected files may expose GBK/CP936 streams.  Keeping
    that encoding is important to the caller, but strict error handling must
    not turn a status message or user path into a process crash.
    """

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(errors="replace")
        except Exception:
            # Test doubles and embedded hosts may expose only part of the
            # TextIOWrapper API.  ``write_console`` remains safe for them.
            continue


def write_console(
    message: object,
    *,
    stream: TextIO | None = None,
    end: str = "",
    flush: bool = False,
) -> None:
    """Write one complete, encoding-safe console record."""

    target = stream if stream is not None else sys.stdout
    if target is None:
        # PyInstaller's ``--windowed`` mode intentionally exposes no console
        # streams. CLI help and validation errors must still terminate cleanly.
        return
    payload = f"{message}{end}"
    safe_payload = _safe_text_for_stream(payload, target)
    try:
        target.write(safe_payload)
    except UnicodeEncodeError:
        # Some embedded streams do not accurately expose their encoding.  An
        # ASCII backslash representation is the final universally encodable
        # fallback and preserves enough text for diagnostics.
        target.write(payload.encode("ascii", errors="backslashreplace").decode("ascii"))
    if flush:
        target.flush()


def console_print(
    *values: object,
    sep: str = " ",
    end: str = "\n",
    file: TextIO | None = None,
    flush: bool = False,
) -> None:
    """``print`` equivalent which cannot fail on GBK/CP936 characters."""

    write_console(
        sep.join(str(value) for value in values),
        stream=file,
        end=end,
        flush=flush,
    )


def _safe_text_for_stream(payload: str, stream: TextIO) -> str:
    encoding = str(getattr(stream, "encoding", "") or "").strip()
    if not encoding:
        encoding = locale.getpreferredencoding(False) or "utf-8"
    try:
        return payload.encode(encoding, errors="replace").decode(
            encoding,
            errors="replace",
        )
    except LookupError:
        return payload.encode("cp936", errors="replace").decode("cp936")


__all__ = ["configure_console_output", "console_print", "write_console"]
