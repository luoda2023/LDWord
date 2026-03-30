"""
file_ops — 文件操作工具

安全读写、路径规范、临时文件管理。
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


def safe_copy(src: str | Path, dst: str | Path) -> Path:
    """安全拷贝文件（目标目录不存在则创建）。"""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    return Path(shutil.copy2(str(src), str(dst)))


def ensure_dir(path: str | Path) -> Path:
    """确保目录存在。"""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def temp_docx_path(prefix: str = "lf_", suffix: str = ".docx") -> str:
    """获取临时 docx 文件路径。"""
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    os.close(fd)
    return path


def normalize_path(path: str | Path) -> str:
    """路径规范化：统一为正斜杠, 解析 ~ 和 ..。"""
    return str(Path(path).expanduser().resolve())


def read_text_safe(path: str | Path, encoding: str = "utf-8") -> str | None:
    """安全读取文本文件, 失败返回 None。"""
    try:
        return Path(path).read_text(encoding=encoding)
    except (OSError, UnicodeDecodeError):
        return None


def write_text_safe(
    path: str | Path,
    content: str,
    encoding: str = "utf-8",
    mkdir: bool = True,
) -> bool:
    """安全写入文本文件。"""
    try:
        p = Path(path)
        if mkdir:
            p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        return True
    except OSError:
        return False


def scan_files(
    folder: str | Path,
    extensions: set[str] | None = None,
    recursive: bool = False,
) -> list[Path]:
    """扫描文件夹中指定扩展名的文件。

    Args:
        folder: 目标文件夹
        extensions: 扩展名集合 (含点号, e.g. {".png", ".jpg"})
        recursive: 是否递归子目录

    Returns:
        排序后的文件 Path 列表
    """
    folder = Path(folder)
    if not folder.is_dir():
        return []

    pattern = "**/*" if recursive else "*"
    files = []
    for p in folder.glob(pattern):
        if not p.is_file():
            continue
        if extensions and p.suffix.lower() not in extensions:
            continue
        files.append(p)

    return sorted(files)


def file_size_human(size_bytes: int) -> str:
    """字节数→可读大小 (e.g. 1.2 MB)。"""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore
    return f"{size_bytes:.1f} TB"
