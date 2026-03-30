"""
font_resolver — 字体名解析+系统检测+fallback

解析用户指定的字体名→系统实际可用的字体名。
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path


# ── 系统字体扫描 ─────────────────────────────────

@lru_cache(maxsize=1)
def list_system_fonts() -> set[str]:
    """扫描系统已安装的字体名称。"""
    font_dirs = _get_font_dirs()
    names: set[str] = set()
    for d in font_dirs:
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if f.suffix.lower() in (".ttf", ".otf", ".ttc"):
                names.add(f.stem)
    return names


def _get_font_dirs() -> list[Path]:
    if sys.platform == "win32":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        return [
            Path(windir) / "Fonts",
            Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts",
        ]
    elif sys.platform == "darwin":
        return [
            Path("/System/Library/Fonts"),
            Path("/Library/Fonts"),
            Path.home() / "Library" / "Fonts",
        ]
    else:
        return [
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            Path.home() / ".fonts",
            Path.home() / ".local" / "share" / "fonts",
        ]


# ── 字体名解析 ───────────────────────────────────

# 常见中文字体别名 → 标准名
_CN_ALIASES: dict[str, list[str]] = {
    "宋体": ["SimSun", "NSimSun", "宋体"],
    "黑体": ["SimHei", "黑体"],
    "微软雅黑": ["Microsoft YaHei", "微软雅黑"],
    "楷体": ["KaiTi", "楷体", "楷体_GB2312"],
    "仿宋": ["FangSong", "仿宋", "仿宋_GB2312"],
    "华文行楷": ["STXingkai", "华文行楷"],
    "华文仿宋": ["STFangsong", "华文仿宋"],
    "方正小标宋": ["FZXiaoBiaoSong-B05", "方正小标宋简体", "方正小标宋_GBK"],
}

# Fallback 链
_FALLBACK_CN = ["宋体", "SimSun", "Microsoft YaHei"]
_FALLBACK_EN = ["Times New Roman", "Arial", "Calibri"]

# 常见英文字体别名 → 文件名 stem
_EN_ALIASES: dict[str, list[str]] = {
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


def resolve_font(
    font_name: str,
    *,
    lang: str = "auto",
    fallback: bool = True,
) -> str:
    """解析字体名为系统可用的字体名。

    Args:
        font_name: 用户指定的字体名
        lang: "cn" / "en" / "auto" — 决定 fallback 链
        fallback: 未找到时是否使用 fallback

    Returns:
        系统可用的字体名。找不到且不 fallback 则返回原名。
    """
    # 直接匹配
    if _is_available(font_name):
        return font_name

    # 别名查找
    for canonical, aliases in _CN_ALIASES.items():
        if font_name in (canonical, *aliases):
            for alias in aliases:
                if _is_available(alias):
                    return alias

    if not fallback:
        return font_name

    # Fallback
    chain = _FALLBACK_CN if _is_cn(font_name, lang) else _FALLBACK_EN
    for fb in chain:
        if _is_available(fb):
            return fb

    return font_name


def _is_available(name: str) -> bool:
    """检查字体是否在系统中（启发式）。

    由于 list_system_fonts() 仅返回文件名 stem（如 times, simsun），
    无法精确匹配 "Times New Roman" 等含空格的名称。
    因此采用启发式：先查别名表 → 再比较去空格小写 stem。
    """
    fonts = list_system_fonts()
    fonts_lower = {n.lower() for n in fonts}

    # 直接 stem 匹配
    if name in fonts or name.lower() in fonts_lower:
        return True

    # 中文别名表
    for canonical, aliases in _CN_ALIASES.items():
        if name in (canonical, *aliases):
            for alias in aliases:
                if alias.lower() in fonts_lower:
                    return True

    # 英文别名表
    for canonical, stems in _EN_ALIASES.items():
        if name == canonical:
            for stem in stems:
                if stem.lower() in fonts_lower:
                    return True

    return False


def _is_cn(name: str, lang: str) -> bool:
    if lang == "cn":
        return True
    if lang == "en":
        return False
    # auto: 包含 CJK 字符则视为中文字体
    return any("\u4e00" <= c <= "\u9fff" for c in name)
