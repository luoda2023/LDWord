"""
numbering — 编号格式化

生成合规编号文本: 阿拉伯/中文小写/中文大写/罗马/带圈/字母。
"""

from __future__ import annotations


# ── 中文数字映射 ─────────────────────────────────

_CN_LOWER_DIGITS = ("零", "一", "二", "三", "四", "五", "六", "七", "八", "九")
_CN_UPPER_DIGITS = ("零", "壹", "贰", "叁", "肆", "伍", "陆", "柒", "捌", "玖")
_CN_UNITS = ("", "十", "百", "千", "万")
_CN_UPPER_UNITS = ("", "拾", "佰", "仟", "万")
_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
_CIRCLED_PAREN = "⑴⑵⑶⑷⑸⑹⑺⑻⑼⑽⑾⑿⒀⒁⒂⒃⒄⒅⒆⒇"
_ROMAN_VALS = (
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
    (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
    (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
)


def format_number(n: int, style: str) -> str:
    """将整数格式化为指定编号样式。

    支持的 style:
    - "arabic"          1, 2, 3
    - "arabic_pad2"     01, 02, 03
    - "cn_lower"        一, 二, 三 ... 十一, 十二
    - "cn_upper"        壹, 贰, 叁 ... 拾壹, 拾贰
    - "roman_upper"     I, II, III
    - "roman_lower"     i, ii, iii
    - "alpha_upper"     A, B, C
    - "alpha_lower"     a, b, c
    - "circled"         ①, ②, ③
    - "circled_paren"   ⑴, ⑵, ⑶
    """
    if n < 1:
        return str(n)

    if style == "arabic":
        return str(n)
    if style == "arabic_pad2":
        return f"{n:02d}"
    if style == "cn_lower":
        return _to_cn(n, _CN_LOWER_DIGITS, _CN_UNITS)
    if style == "cn_upper":
        return _to_cn(n, _CN_UPPER_DIGITS, _CN_UPPER_UNITS)
    if style == "roman_upper":
        return _to_roman(n)
    if style == "roman_lower":
        return _to_roman(n).lower()
    if style == "alpha_upper":
        return _to_alpha(n, uppercase=True)
    if style == "alpha_lower":
        return _to_alpha(n, uppercase=False)
    if style == "circled":
        return _CIRCLED[n - 1] if 1 <= n <= 20 else f"({n})"
    if style == "circled_paren":
        return _CIRCLED_PAREN[n - 1] if 1 <= n <= 20 else f"({n})"

    return str(n)


def _to_cn(n: int, digits: tuple, units: tuple) -> str:
    """整数→中文（支持 1~9999）。"""
    if n <= 0 or n >= 10000:
        return str(n)
    if n <= 10:
        if n == 10:
            return units[1]  # "十"
        return digits[n]

    result = []
    s = str(n)
    length = len(s)
    for i, ch in enumerate(s):
        d = int(ch)
        pos = length - 1 - i
        if d == 0:
            if result and result[-1] != digits[0]:
                result.append(digits[0])
        else:
            # 十几时省略"一十"的"一"
            if not (pos == 1 and d == 1 and i == 0):
                result.append(digits[d])
            result.append(units[pos])

    # 去尾零
    while result and result[-1] == digits[0]:
        result.pop()
    return "".join(result)


def _to_roman(n: int) -> str:
    if n <= 0 or n >= 4000:
        return str(n)
    result = []
    for val, numeral in _ROMAN_VALS:
        while n >= val:
            result.append(numeral)
            n -= val
    return "".join(result)


def _to_alpha(n: int, uppercase: bool = True) -> str:
    """整数→字母(A-Z, AA, AB...)。"""
    if n <= 0:
        return str(n)
    result = []
    while n > 0:
        n -= 1
        result.append(chr((n % 26) + (65 if uppercase else 97)))
        n //= 26
    return "".join(reversed(result))
