"""Resolve configured font names to fonts available on the current machine."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

CN_ALIASES: dict[str, list[str]] = {
    "宋体": ["SimSun", "NSimSun", "宋体"],
    "黑体": ["SimHei", "黑体"],
    "微软雅黑": ["Microsoft YaHei", "微软雅黑"],
    "楷体": ["KaiTi", "楷体", "楷体_GB2312"],
    "仿宋": ["FangSong", "仿宋", "仿宋_GB2312"],
    "华文行楷": ["STXingkai", "华文行楷"],
    "华文仿宋": ["STFangsong", "华文仿宋"],
    "方正小标宋": ["FZXiaoBiaoSong-B05", "方正小标宋简体", "方正小标宋_GBK"],
}

FALLBACK_CN = ["宋体", "SimSun", "Microsoft YaHei"]
FALLBACK_EN = ["Times New Roman", "Arial", "Calibri"]

EN_ALIASES: dict[str, list[str]] = {
    "Times New Roman": ["times", "timesbd", "timesbi", "timesi"],
    "Arial": ["arial", "arialbd", "arialbi", "ariali"],
    "Calibri": ["calibri", "calibrib", "calibrii", "calibriz"],
    "Cambria": ["cambria", "cambriab", "cambriai", "cambriaz"],
    "Courier New": ["cour", "courbd", "courbi", "couri"],
    "Verdana": ["verdana", "verdanab", "verdanai", "verdanaz"],
    "Georgia": ["georgia", "georgiab", "georgiai", "georgiaz"],
    "Tahoma": ["tahoma", "tahomabd"],
    "Segoe UI": ["segoeui", "segoeuib", "segoeuii", "segoeuiz"],
    "Consolas": ["consola", "consolab", "consolai", "consolaz"],
}


def canonicalize_font_name(font_name: str) -> str:
    normalized = str(font_name or "").strip()
    if not normalized:
        return normalized

    repaired = _repair_utf8_gbk_mojibake(normalized)
    if repaired:
        normalized = repaired

    for canonical, aliases in CN_ALIASES.items():
        if normalized == canonical or normalized in aliases:
            return canonical

    for canonical in EN_ALIASES:
        if normalized.casefold() == canonical.casefold():
            return canonical

    return normalized


@lru_cache(maxsize=1)
def list_system_fonts() -> set[str]:
    font_dirs = _get_font_dirs()
    names: set[str] = set()
    for directory in font_dirs:
        if not directory.is_dir():
            continue
        for font_file in directory.iterdir():
            if font_file.suffix.lower() in (".ttf", ".otf", ".ttc"):
                names.add(font_file.stem)
    return names


@lru_cache(maxsize=1)
def qt_font_families() -> tuple[str, ...]:
    try:
        from PySide6.QtWidgets import QApplication
        if QApplication.instance() is None:
            return ()
        from PySide6.QtGui import QFontDatabase
    except Exception:
        return ()

    try:
        names = sorted(
            {str(name).strip() for name in QFontDatabase.families() if str(name).strip()},
            key=lambda item: item.casefold(),
        )
    except Exception:
        return ()
    return tuple(names)


def _get_font_dirs() -> list[Path]:
    if sys.platform == "win32":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        return [
            Path(windir) / "Fonts",
            Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts",
        ]
    if sys.platform == "darwin":
        return [
            Path("/System/Library/Fonts"),
            Path("/Library/Fonts"),
            Path.home() / "Library" / "Fonts",
        ]
    return [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path.home() / ".fonts",
        Path.home() / ".local" / "share" / "fonts",
    ]


def resolve_font(
    font_name: str,
    *,
    lang: str = "auto",
    fallback: bool = True,
) -> str:
    normalized = canonicalize_font_name(font_name)
    if not normalized:
        return font_name

    matched = _match_available_font(normalized)
    if matched is not None:
        return matched

    for canonical, aliases in CN_ALIASES.items():
        if normalized in (canonical, *aliases):
            for alias in aliases:
                matched = _match_available_font(alias)
                if matched is not None:
                    return matched

    if not fallback:
        return normalized

    chain = FALLBACK_CN if _is_cn(normalized, lang) else FALLBACK_EN
    for fallback_name in chain:
        matched = _match_available_font(fallback_name)
        if matched is not None:
            return matched

    return normalized


def _match_available_font(name: str) -> str | None:
    normalized_target = _normalize_font_name(name)
    if not normalized_target:
        return None

    for family in qt_font_families():
        if _normalize_font_name(family) == normalized_target:
            return family

    fonts = list_system_fonts()
    fonts_lower = {font.lower(): font for font in fonts}
    if name in fonts:
        return name
    if name.lower() in fonts_lower:
        return fonts_lower[name.lower()]

    for canonical, aliases in CN_ALIASES.items():
        if name in (canonical, *aliases):
            for alias in aliases:
                matched = _match_stem(alias, fonts)
                if matched is not None:
                    return matched

    for canonical, stems in EN_ALIASES.items():
        if name == canonical:
            for stem in stems:
                matched = _match_stem(stem, fonts)
                if matched is not None:
                    return canonical

    return None


def _match_stem(name: str, fonts: set[str]) -> str | None:
    normalized = name.lower()
    for font in fonts:
        if font.lower() == normalized:
            return font
    return None


def _normalize_font_name(name: str) -> str:
    return "".join(
        ch for ch in str(name or "").strip().casefold()
        if not ch.isspace() and ch not in "-_.,()[]{}"
    )


def _repair_utf8_gbk_mojibake(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return raw
    try:
        repaired = raw.encode("gbk").decode("utf-8")
    except UnicodeError:
        return raw
    return repaired if repaired else raw


def _is_cn(name: str, lang: str) -> bool:
    if lang == "cn":
        return True
    if lang == "en":
        return False
    return any("\u4e00" <= char <= "\u9fff" for char in name)
