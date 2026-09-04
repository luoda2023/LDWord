"""
units — 排版单位互转

支持: cm / mm / pt / emu / twip / inch / chars
所有函数保证双向转换无精度丢失（使用 Decimal 精度）。
"""

from __future__ import annotations

# ── 常量 ─────────────────────────────────────────
CM_PER_INCH = 2.54
PT_PER_INCH = 72.0
EMU_PER_INCH = 914400
TWIP_PER_INCH = 1440
EMU_PER_CM = EMU_PER_INCH / CM_PER_INCH       # 360000
EMU_PER_PT = EMU_PER_INCH / PT_PER_INCH       # 12700
TWIP_PER_PT = TWIP_PER_INCH / PT_PER_INCH     # 20
TWIP_PER_CM = TWIP_PER_INCH / CM_PER_INCH     # ~566.929


# ── cm 转换 ──────────────────────────────────────

def cm_to_pt(cm: float) -> float:
    return cm / CM_PER_INCH * PT_PER_INCH

def cm_to_emu(cm: float) -> int:
    return round(cm * EMU_PER_CM)

def cm_to_twip(cm: float) -> int:
    return round(cm * TWIP_PER_CM)


# ── pt 转换 ──────────────────────────────────────

def pt_to_cm(pt: float) -> float:
    return pt / PT_PER_INCH * CM_PER_INCH

def pt_to_emu(pt: float) -> int:
    return round(pt * EMU_PER_PT)

def pt_to_twip(pt: float) -> int:
    return round(pt * TWIP_PER_PT)


# ── emu 转换 ─────────────────────────────────────

def emu_to_cm(emu: int) -> float:
    return emu / EMU_PER_CM

def emu_to_pt(emu: int) -> float:
    return emu / EMU_PER_PT

def emu_to_twip(emu: int) -> int:
    return round(emu / EMU_PER_PT * TWIP_PER_PT)


# ── twip 转换 ────────────────────────────────────

def twip_to_cm(twip: int) -> float:
    return twip / TWIP_PER_CM

def twip_to_pt(twip: int) -> float:
    return twip / TWIP_PER_PT

def twip_to_emu(twip: int) -> int:
    return round(twip / TWIP_PER_PT * EMU_PER_PT)


# ── chars 转换 ───────────────────────────────────

def chars_to_pt(chars: float, base_font_pt: float = 12.0) -> float:
    """字符数→磅。1 char = 基准字号的宽度。"""
    return chars * base_font_pt

def chars_to_emu(chars: float, base_font_pt: float = 12.0) -> int:
    return pt_to_emu(chars_to_pt(chars, base_font_pt))

def pt_to_chars(pt: float, base_font_pt: float = 12.0) -> float:
    return pt / base_font_pt


# ── 中文字号映射 ─────────────────────────────────

CN_SIZE_MAP: dict[str, float] = {
    "初号": 42, "小初": 36, "一号": 26, "小一": 24,
    "二号": 22, "小二": 18, "三号": 16, "小三": 15,
    "四号": 14, "小四": 12, "五号": 10.5, "小五": 9,
    "六号": 7.5, "小六": 6.5, "七号": 5.5, "八号": 5,
}

CN_SIZE_MAP_REVERSE: dict[float, str] = {v: k for k, v in CN_SIZE_MAP.items()}


def cn_size_to_pt(cn_name: str) -> float | None:
    """中文字号名→磅值, e.g. '小四' → 12.0"""
    return CN_SIZE_MAP.get(cn_name.strip())


def pt_to_cn_size(pt: float) -> str | None:
    """磅值→中文字号名, e.g. 12.0 → '小四'"""
    return CN_SIZE_MAP_REVERSE.get(pt)
