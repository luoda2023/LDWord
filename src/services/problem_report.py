"""Build a privacy-conscious local problem report for support requests."""

from __future__ import annotations

import os
import platform
import re
import sys
from datetime import datetime
from pathlib import Path

from src.app_meta import APP_DISPLAY_NAME, APP_LOG_FILE, APP_VERSION
from src.app_paths import log_data_root

SOURCE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_TAIL_BYTES = 64 * 1024


def _unique_paths(paths: list[Path]) -> tuple[Path, ...]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = os.path.normcase(str(path.resolve(strict=False)))
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return tuple(unique)


def application_roots() -> tuple[Path, ...]:
    """Return source and packaged roots that may own app support files."""

    roots = [SOURCE_ROOT]
    if getattr(sys, "frozen", False):
        roots.insert(0, Path(sys.executable).resolve().parent)
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        roots.append(Path(bundle_root))
    roots.append(Path.cwd())
    return _unique_paths(roots)


def resolve_application_file(filename: str) -> Path:
    """Resolve a bundled/readable application file without assuming cwd."""

    normalized = str(filename or "").strip()
    if not normalized or Path(normalized).name != normalized:
        raise ValueError("filename must be a simple file name")
    candidates = [root / normalized for root in application_roots()]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def resolve_log_path() -> Path:
    """Locate the writable GUI log outside source and install directories."""

    return log_data_root() / APP_LOG_FILE


def read_log_tail(
    log_path: Path | None,
    *,
    max_bytes: int = DEFAULT_LOG_TAIL_BYTES,
) -> str:
    """Read only the tail of a potentially large log file."""

    if log_path is None or not log_path.is_file():
        return ""
    limit = max(1024, int(max_bytes))
    with log_path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        start = max(0, size - limit)
        stream.seek(start)
        payload = stream.read()
    text = payload.decode("utf-8", errors="replace")
    if start > 0:
        _separator, found, remainder = text.partition("\n")
        if found:
            text = remainder
    return text


def sanitize_log_text(text: str, *, home: Path | None = None) -> str:
    """Hide user names and local paths before a report leaves the computer."""

    sanitized = str(text or "")
    user_home = Path.home() if home is None else Path(home)

    # Quoted traceback paths and ordinary Windows paths are the most common
    # sources of document names in logs. Keep the surrounding error message.
    sanitized = re.sub(
        r"(?i)(?<![\w])(?:[a-z]:[\\/])[^\"'\r\n<>|]*",
        "<本地路径>",
        sanitized,
    )
    sanitized = re.sub(
        r"(?<![\\])\\\\[^\"'\r\n<>|]+",
        "<网络路径>",
        sanitized,
    )
    sanitized = re.sub(
        r"(?i)file:///{0,1}[^\"'\r\n<>|]+",
        "<本地路径>",
        sanitized,
    )
    sanitized = re.sub(
        r"(?<!\w)/(?:Users|home)/[^/\s]+/[^\"'\r\n<>|]*",
        "<本地路径>",
        sanitized,
    )
    sensitive_tokens = {
        str(user_home),
        str(user_home).replace("\\", "/"),
        user_home.name,
    }
    for token in sorted((item for item in sensitive_tokens if item), key=len, reverse=True):
        sanitized = re.sub(re.escape(token), "<已隐藏>", sanitized, flags=re.IGNORECASE)
    return sanitized


def build_problem_report(
    *,
    log_path: Path | None = None,
    created_at: datetime | None = None,
) -> str:
    """Return a plain-text report that can be reviewed before sharing."""

    timestamp = created_at or datetime.now().astimezone()
    resolved_log = resolve_log_path() if log_path is None else Path(log_path)
    log_tail = sanitize_log_text(read_log_tail(resolved_log)).strip()
    if not log_tail:
        log_tail = "（当前没有可用的错误日志）"

    return "\n".join(
        (
            f"{APP_DISPLAY_NAME} 问题报告",
            "=" * 36,
            f"生成时间：{timestamp.strftime('%Y-%m-%d %H:%M:%S %z')}",
            f"软件版本：{APP_VERSION}",
            f"操作系统：{platform.system()} {platform.release()}",
            f"系统架构：{platform.machine() or '未知'}",
            "",
            "隐私说明：本报告不包含用户文档；用户名和本地路径已隐藏。",
            "报告只保存在你选择的位置，不会自动发送。",
            "",
            "最近的运行日志",
            "-" * 36,
            log_tail,
            "",
        )
    )


__all__ = [
    "DEFAULT_LOG_TAIL_BYTES",
    "application_roots",
    "build_problem_report",
    "read_log_tail",
    "resolve_application_file",
    "resolve_log_path",
    "sanitize_log_text",
]
