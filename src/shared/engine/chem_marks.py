"""
chem_marks ? 1.0 chemistry superscript/subscript compatibility engine.

Ported and trimmed from the 0.2 LTS chemistry restore logic so 1.0 can
preserve compatibility for common chemical formula typography while keeping the
module layer thin.
"""

from __future__ import annotations

import re
import unicodedata
from copy import deepcopy

from docx.document import Document
from docx.oxml import OxmlElement
from lxml import etree

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
_M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

_RE_FIGURE_CAPTION = re.compile(r"^(图|表|Figure|Table|Fig\.?)\s*\d", re.IGNORECASE)
_HEADING_STYLE_PREFIXES = ("Heading", "heading", "标题")
_RE_TOC_STYLE = re.compile(r"^(toc|目录)\s*\d+", re.IGNORECASE)

# Body text subfigure references: "3.11　(a)" -> "3.11 (a)"
_RE_SUBFIG_REF_FULLWIDTH_SPACE = re.compile(
    r"(?P<num>\d+(?:\.\d+)+)\u3000(?P<label>[（(][A-Za-z][)）])"
)

_RE_REFERENCE_ENTRY_LINE = re.compile(r"^\s*([\[\uFF3B]\s*\d{1,4}\s*[\]\uFF3D])\s+\S")
_RE_TITLE_TAIL_MARKS = re.compile(r"[：:;；·•\-—_~\.。…]+$")
_RE_ABSTRACT_CN_TITLE = re.compile(r"^\u6458\u8981(?:[（(][^()（）]{0,8}[)）])?$")
_RE_ABSTRACT_EN_TITLE = re.compile(
    r"^abstract(?:[（(][^()（）]{0,16}[)）])?$",
    re.IGNORECASE,
)
_RE_TOC_TITLE_LINE = re.compile(
    r"^(?:\u76ee\u5f55|\u76ee\u9304|contents|tableofcontents)(?:[（(][^()（）]{0,8}[)）])?$",
    re.IGNORECASE,
)
_CHEM_TOKEN_RE = re.compile(
    r"[A-Za-z0-9Ａ-Ｚａ-ｚ０-９µμα-ωΑ-ΩΩω\(\)\[\]\{\}（）［］｛｝"
    r"\+\-−＋－‐‑‒–—―=\^\.·•∙⋅≡/%％／<>→←↔"
    r"⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₙ]+"
)
_CHARGE_SIGNS = "+-−＋－"
_DOT_SEPARATORS = ".·•"
_RADICAL_DOT_CHARS = {"·", "•"}
_BOND_CHARS = "-−－‐‑‒–—―=≡"
_SUPER_SUB_UNICODE_CHARS = set(
    "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ"
    "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₙ"
)
_SUPER_SUB_ASCII_MAP = {
    "⁰": "0",
    "¹": "1",
    "²": "2",
    "³": "3",
    "⁴": "4",
    "⁵": "5",
    "⁶": "6",
    "⁷": "7",
    "⁸": "8",
    "⁹": "9",
    "⁺": "+",
    "⁻": "-",
    "⁼": "=",
    "⁽": "(",
    "⁾": ")",
    "₀": "0",
    "₁": "1",
    "₂": "2",
    "₃": "3",
    "₄": "4",
    "₅": "5",
    "₆": "6",
    "₇": "7",
    "₈": "8",
    "₉": "9",
    "₊": "+",
    "₋": "-",
    "₌": "=",
    "₍": "(",
    "₎": ")",
}
_INTERNAL_CHEM_CONFUSABLE_CHAR_MAP = {
    # Small symbol variants seen in copied equations/units.
    "﹣": "-",
    "﹢": "+",
    # Common non-ASCII unit letters.
    "ɡ": "g",
    "ℊ": "g",
    "ℎ": "h",
    "ℓ": "l",
    "K": "K",
    # Greek/material-prefix display variants seen in OCR / copied equations.
    "ɑ": "α",
    "𝛂": "α",
    "𝛼": "α",
    "𝛃": "β",
    "𝛽": "β",
    "𝛄": "γ",
    "𝛾": "γ",
}
_BRACKET_OPEN_TO_CLOSE = {"(": ")", "[": "]", "{": "}"}
_RE_MASS_ADDUCT_CHARGE = re.compile(r"^\[[A-Za-z0-9+\-−＋－]+\](\d*[+\-−＋－])$")
_ELEMENT_SYMBOLS = set(
    (
        "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn "
        "Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce "
        "Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn "
        "Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl "
        "Mc Lv Ts Og"
    ).split()
)
# Common isotope symbols in chemistry writing.
_ELEMENT_SYMBOLS.update({"D", "T"})

# Internal hardening dictionaries for extreme/ambiguous cases.
# These are intentionally conservative and not exposed in UI.
_INTERNAL_CHEM_IGNORE_TOKENS = {
    "H1N1",
    "H5N1",
    "H3N2",
}
_INTERNAL_CHEM_ALLOW_TOKENS: set[str] = {
    # Common isotope labels in thesis / paper writing.
    "13C",
    "14C",
    "15N",
    "18O",
    "19F",
    "29Si",
    "31P",
    "35S",
    "57Fe",
    "60Co",
    "99Tc",
    "99mTc",
    # Labeled water / heavy-water forms.
    "D2O",
    "T2O",
}
_INTERNAL_CHEM_IGNORE_PATTERNS = [
    re.compile(r"^H\d{1,2}N\d{1,2}$"),  # Influenza subtype naming.
    # Compact measurement-like tokens common in thesis methods/results sections.
    re.compile(r"^\d{2,4}(?:W|V|K|N)$"),
    re.compile(
        r"^\d{2,4}(?:mV|kV|MV|GV|mA|kA|MA|mW|kW|MW|GW|Hz|kHz|MHz|GHz|Pa|kPa|MPa|GPa)$"
    ),
    # Instrument/model codes.
    re.compile(r"^CHI\d{2,}[A-Z]*$"),
    re.compile(r"^LCMS\d{2,}[A-Z]*$"),
]
_INTERNAL_CHEM_ALLOW_PATTERNS: list[re.Pattern[str]] = []
_INTERNAL_CHEM_MANUAL_OVERRIDES = {
    # Common light-element isotope shorthands.
    "1H": "^.",
    "2H": "^.",
    "3H": "^.",
    "3He": "^..",
    "4He": "^..",
    "2H2O": "^._.",
    "3H2O": "^._.",
    # Compact NMR shorthand frequently used in papers.
    "1HNMR": "^....",
    "13CNMR": "^^....",
    "15NNMR": "^^....",
    "19FNMR": "^^....",
    "29SiNMR": "^^.....",
    "31PNMR": "^^....",
    "1H-NMR": "^.....",
    "13C-NMR": "^^.....",
    "15N-NMR": "^^.....",
    "19F-NMR": "^^.....",
    "29Si-NMR": "^^......",
    "31P-NMR": "^^.....",
    # Singlet oxygen: leading isotope/singlet marker + oxygen count.
    "1O2": "^._",
    # Radical forms often represented with a raised dot and sign.
    "O2·-": "._.^",
    "O2•-": "._.^",
    # Sulfate radical anion; keep leading dot baseline.
    "·SO42-": "..._^^",
    "•SO42-": "..._^^",
    "SO42-": ".._^^",
    "SO42+": ".._^^",
    "SO4^2-": ".._.^^",
    "SO4^2+": ".._.^^",
    "SO4-2": ".._^^",
    "SO4+2": ".._^^",
}
_INSTRUMENT_MODEL_PREFIXES = {
    "CHI",
    "LCMS",
    "HPLC",
    "UPLC",
    "GCMS",
    "ICP",
    "XRD",
    "XPS",
    "FTIR",
    "NMR",
    "SEM",
    "TEM",
}
_RE_BOND_TOKEN = re.compile(
    r"^(?:[A-Z][a-z]?)(?:[\-−－‐‑‒–—―=≡](?:[A-Z][a-z]?))+$"
)
_RE_ROMAN_OX_STATE = re.compile(
    r"^(?P<elem>[A-Z][a-z]?)\((?P<roman>I|II|III|IV|V|VI|VII)\)$"
)
_RE_ROMAN_OXO_TOKEN = re.compile(
    r"^(?P<lemma>[A-Z][a-z]?\((?:I|II|III|IV|V|VI|VII)\))(?:[=≡](?:[A-Z][a-z]?\d*))+$"
)
_RE_UNIT_RATIO_TOKEN = re.compile(
    r"^(?:[A-Za-zµμΩω%]{1,10}(?:\([A-Za-zµμΩω%·\.]+\))?)(?:/(?:[A-Za-zµμΩω%]{1,10}(?:\([A-Za-zµμΩω%·\.]+\))?))+?$"
)
_RE_ISOTOPE_LABEL_TOKEN = re.compile(
    r"^\[(?P<mass>\d{1,3})(?P<elem>[A-Z][a-z]?)\]\d*(?:-[A-Za-z0-9]+)*$"
)
_RE_REACTION_ARROW_TOKEN = re.compile(
    r"^(?P<left>.+?)(?:<->|->|<-|→|←|↔)(?P<right>.+)$"
)
_RE_SPACED_FORMULA_SPAN = re.compile(
    r"[A-Za-z0-9Ａ-Ｚａ-ｚ０-９µμα-ωΑ-ΩΩω\(\)\[\]\{\}（）［］｛｝"
    r"\+\-−＋－‐‑‒–—―=\^\.·•∙⋅≡/%％／<>→←↔"
    r"⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₙ\s]{4,}"
)
_RE_PHASE_PREFIX_TOKEN = re.compile(
    r"^(?P<prefix>g|p|n|α|β|γ)(?P<sep>[\-−－‐‑‒–—―])(?P<rest>.+)$"
)
_RE_GREEK_PREFIX_TOKEN = re.compile(r"^(?P<prefix>[α-ωΑ-Ω])(?P<sep>[\-−－‐‑‒–—―])(?P<rest>.+)$")
_RE_PLAIN_FORMULA_CHAIN = re.compile(r"^(?:\d{0,3})?(?:[A-Z][a-z]?\d*){2,}$")
_RE_SINGLE_ELEMENT_TOKEN = re.compile(r"^[A-Z][a-z]?$")
_RE_HYBRIDIZATION_TOKEN = re.compile(
    r"^(?:sp\d(?:d\d{0,2})?|dsp\d|d\d{1,2}sp\d(?:d\d{0,2})?)$",
    re.IGNORECASE,
)
_RE_BRACKET_COMPLEX_WITH_CHARGE = re.compile(
    r"^\[[A-Za-z0-9\(\)\+\-−＋－·•]+\]\d*[+\-−＋－]$"
)
_RE_SIMPLE_UNIT_CONNECT_TOKEN = re.compile(
    r"^[A-Za-zµμΩω%]{1,10}(?:[·•∙⋅/][A-Za-zµμΩω%]{1,10})+$"
)
_RE_PERCENT_SHORT_UNIT = re.compile(r"^(?:wt|vol|at)%$", re.IGNORECASE)
_RE_PERCENT_BRACKET_UNIT = re.compile(r"^%\((?:w|v)/(?:w|v)\)$", re.IGNORECASE)
_PLAIN_UNIT_WORDS = {"ppm", "ppb", "ppt", "ppmv", "ppbv", "pptr"}
_KNOWN_UNIT_SEGMENTS = {
    "m", "cm", "mm", "km", "nm", "pm",
    "μm", "um",
    "g", "kg", "mg", "ng", "pg",
    "μg", "ug",
    "l", "ml", "nl", "pl",
    "μl", "ul",
    "mol", "mmol", "nmol", "pmol",
    "μmol", "umol",
    "moll",  # tolerate rare OCR-like collapse before cleanup
    "s", "ms", "ns", "ps", "min", "h", "d",
    "hz", "khz", "mhz", "ghz",
    "pa", "kpa", "mpa", "gpa", "bar", "mbar",
    "ev", "kev", "mev", "gev",
    "ma", "mv", "kw", "kj",
    "ma", "ms", "mpa", "mm", "ml",
    "°c", "℃",
    "ω", "kω", "mω", "μs", "us",
    "wt%", "vol%", "at%", "%",
}
_ALLOWED_NEUTRAL_COMPACT_TAILS = {"O", "N", "S", "H", "F", "I"}
_COMMON_SINGLE_LETTER_FORMULA_TOKENS = {"H2", "N2", "O2", "O3"}
_RE_APPENDIX_LABEL_TOKEN = re.compile(r"^[A-Z]-\d{1,3}$")
_RE_PREFIXED_APPENDIX_LABEL_TOKEN = re.compile(r"^(?:Fig\.?|Table|Appendix|图|表)[A-Z]-\d{1,3}$", re.IGNORECASE)
_RE_DOMAIN_LIKE_TOKEN = re.compile(r"^(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,24}$")
_RE_COMPACT_SINGLE_LETTER_ISOTOPE_TOKEN = re.compile(r"^\d{1,3}[A-Z]$")
_RE_SHORT_IDENTIFIER_TOKEN = re.compile(r"^[A-Z]\d{1,3}$")
_RE_HISTONE_MARK_TOKEN = re.compile(r"^H[1-4](?:K|R|Q|N|S|T)\d{1,3}$", re.IGNORECASE)
_SINGLE_LETTER_ELEMENT_ATOMIC_NUMBERS = {
    "H": 1,
    "B": 5,
    "C": 6,
    "N": 7,
    "O": 8,
    "F": 9,
    "P": 15,
    "S": 16,
    "K": 19,
    "V": 23,
    "Y": 39,
    "I": 53,
    "W": 74,
    "U": 92,
}
# For spaced compacted spans like "40 K" / "220 V", prefer the common unit
# interpretation over isotope recovery. Compact no-space forms like "14C" are
# still handled by the normal token recognizer.
_COMMON_SPACED_SINGLE_LETTER_UNIT_SYMBOLS = {"K", "V", "W"}

ChemRuntime = tuple[
    set[str],  # ignore_tokens
    list[re.Pattern[str]],  # ignore_patterns
    dict[str, str],  # manual_overrides
    set[str],  # allow_tokens
    list[re.Pattern[str]],  # allow_patterns
]

def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in (text or ""))

def _run_vert_align(run) -> str | None:
    """Return run vertical alignment value if present."""
    if run.font.superscript:
        return "superscript"
    if run.font.subscript:
        return "subscript"
    rpr = run._element.find(f"{{{_W_NS}}}rPr")
    if rpr is None:
        return None
    va = rpr.find(f"{{{_W_NS}}}vertAlign")
    if va is None:
        return None
    val = (va.get(f"{{{_W_NS}}}val") or "").strip()
    if val in {"superscript", "subscript"}:
        return val
    return None


def _para_has_existing_vert_align(para) -> bool:
    """Skip paragraphs that already contain explicit superscript/subscript."""
    for run in para.runs:
        if _run_vert_align(run) in {"superscript", "subscript"}:
            return True
    return False


def _mark_style(marks: list[str | None], start: int, end: int, style: str) -> None:
    for i in range(max(0, start), min(len(marks), end)):
        marks[i] = style


def _is_ascii_upper(ch: str) -> bool:
    return "A" <= ch <= "Z"


def _is_ascii_lower(ch: str) -> bool:
    return "a" <= ch <= "z"


def _is_cjk(ch: str) -> bool:
    return "\u4e00" <= ch <= "\u9fff"


def _is_word_or_cjk(ch: str) -> bool:
    return ch.isalnum() or _is_cjk(ch)


def _normalize_math_alnum_char(ch: str) -> str:
    """Map mathematical alphanumeric symbols to plain ASCII when possible."""
    if not ch:
        return ""
    name = unicodedata.name(ch, "")
    if not name.startswith("MATHEMATICAL "):
        return ""

    m_alpha = re.search(r"(CAPITAL|SMALL) ([A-Z])$", name)
    if m_alpha:
        letter = m_alpha.group(2)
        return letter if m_alpha.group(1) == "CAPITAL" else letter.lower()

    m_digit = re.search(r"DIGIT ([0-9])$", name)
    if m_digit:
        return m_digit.group(1)

    if name.endswith("SMALL DOTLESS I"):
        return "i"
    if name.endswith("SMALL DOTLESS J"):
        return "j"
    return ""


def _normalize_formula_scan_char(ch: str) -> str:
    """Normalize single char for candidate scanning while keeping length 1:1."""
    if not ch:
        return ""
    # Fullwidth ASCII to halfwidth ASCII.
    if "\uff01" <= ch <= "\uff5e":
        ch = chr(ord(ch) - 0xFEE0)

    if ch in _INTERNAL_CHEM_CONFUSABLE_CHAR_MAP:
        return _INTERNAL_CHEM_CONFUSABLE_CHAR_MAP[ch]

    mapped = _normalize_math_alnum_char(ch)
    if mapped:
        return mapped
    return ch


def _normalize_formula_scan_text(text: str) -> str:
    if not text:
        return ""
    return "".join(_normalize_formula_scan_char(ch) for ch in str(text))


def _first_non_space_char(text: str) -> str:
    for ch in text or "":
        if not ch.isspace():
            return ch
    return ""


def _normalize_formula_token_chars(token: str) -> str:
    if not token:
        return ""
    out = []
    for ch in str(token):
        ch = _normalize_formula_scan_char(ch)

        if ch in {"µ"}:
            out.append("μ")
        elif ch in {"•"}:
            out.append("·")
        elif ch in {"∙", "⋅"}:
            out.append("·")
        elif ch in {"＋"}:
            out.append("+")
        elif ch in {"−", "－", "‐", "‑", "‒", "–", "—", "―"}:
            out.append("-")
        elif ch in {"（"}:
            out.append("(")
        elif ch in {"）"}:
            out.append(")")
        elif ch in {"［"}:
            out.append("[")
        elif ch in {"］"}:
            out.append("]")
        elif ch in {"｛"}:
            out.append("{")
        elif ch in {"｝"}:
            out.append("}")
        elif ch in {"／"}:
            out.append("/")
        elif ch in {"％"}:
            out.append("%")
        elif ch in _SUPER_SUB_ASCII_MAP:
            out.append(_SUPER_SUB_ASCII_MAP[ch])
        else:
            out.append(ch)
    return "".join(out)


def _normalize_unit_placeholder_token(token: str) -> str:
    """Normalize ad-hoc placeholders that may appear in imported corpora."""
    t = str(token or "")
    t = t.replace("{DOT}", "·").replace("{dot}", "·")
    return t


def _looks_like_roman_oxidation_token(token: str) -> bool:
    t = _normalize_formula_token_chars(token or "")
    m = _RE_ROMAN_OX_STATE.fullmatch(t)
    if not m:
        return False
    return m.group("elem") in _ELEMENT_SYMBOLS


def _looks_like_unit_ratio_token(token: str) -> bool:
    t = _normalize_unit_placeholder_token(_normalize_formula_token_chars(token or ""))
    if not t:
        return False
    if _RE_UNIT_RATIO_TOKEN.fullmatch(t):
        return True
    # Relaxed fallback: unit fragments connected by '/', no spaces.
    if "/" in t and " " not in t:
        parts = [p for p in t.split("/") if p]
        if len(parts) >= 2 and all(
            re.fullmatch(r"[A-Za-zµμΩω%\(\)·\.\-]+", p or "") for p in parts
        ):
            return True
    return False


def _looks_like_isotope_label_token(token: str) -> bool:
    t = _normalize_formula_token_chars(token or "")
    if not t:
        return False
    m = _RE_ISOTOPE_LABEL_TOKEN.fullmatch(t)
    if m and m.group("elem") in _ELEMENT_SYMBOLS:
        return True
    # Common isotope shorthand.
    if t in {"D2O", "T2O"}:
        return True
    return False


def _looks_like_plain_unit_token(token: str) -> bool:
    t = _normalize_unit_placeholder_token(_normalize_formula_token_chars(token or ""))
    if not t:
        return False
    if t.lower() in _PLAIN_UNIT_WORDS:
        return True
    if _RE_PERCENT_SHORT_UNIT.fullmatch(t):
        return True
    if _RE_PERCENT_BRACKET_UNIT.fullmatch(t):
        return True
    if _RE_SIMPLE_UNIT_CONNECT_TOKEN.fullmatch(t):
        return True
    if any(ch in _SUPER_SUB_UNICODE_CHARS for ch in token or "") and re.search(r"[A-Za-zµμΩω]", t):
        return True
    return False


def _is_formula_like_token_without_arrow(
    token: str,
    right_char: str = "",
    right_non_space_char: str = "",
) -> bool:
    t = _normalize_formula_token_chars(token or "")
    if not t:
        return False
    if _is_ambiguous_neutral_compact_token(t):
        return False
    if _is_radical_token_candidate(t):
        return True
    if _is_bond_like_chem_token(t):
        return True
    if _looks_like_roman_oxidation_token(t):
        return True
    if _RE_ROMAN_OXO_TOKEN.fullmatch(t):
        return True
    if _looks_like_unit_ratio_token(t):
        return True
    if _looks_like_plain_unit_token(token):
        return True
    if _looks_like_isotope_label_token(t):
        return True
    if _RE_BRACKET_COMPLEX_WITH_CHARGE.fullmatch(t):
        return True

    greek_m = _RE_GREEK_PREFIX_TOKEN.fullmatch(t)
    if greek_m and _is_formula_like_token_without_arrow(
        greek_m.group("rest"),
        right_char=right_char,
        right_non_space_char=right_non_space_char,
    ):
        return True

    if _RE_PLAIN_FORMULA_CHAIN.fullmatch(t):
        symbols = re.findall(r"[A-Z][a-z]?", t)
        if len(symbols) >= 2 and all(sym in _ELEMENT_SYMBOLS for sym in symbols):
            return True

    return any(
        _build_token_formula_marks(
            t,
            right_char=right_char,
            right_non_space_char=right_non_space_char,
        )
    )


def _is_formula_side_token(side: str) -> bool:
    t = _normalize_formula_token_chars((side or "").strip())
    if not t:
        return False
    if _RE_SINGLE_ELEMENT_TOKEN.fullmatch(t):
        return t in _ELEMENT_SYMBOLS
    return _is_formula_like_token_without_arrow(t)


def _looks_like_reaction_arrow_token(token: str) -> bool:
    t = _normalize_formula_token_chars(token or "")
    if not t:
        return False
    m = _RE_REACTION_ARROW_TOKEN.fullmatch(t)
    if not m:
        return False
    left = m.group("left").strip()
    right = m.group("right").strip()
    if not left or not right:
        return False
    return _is_formula_side_token(left) and _is_formula_side_token(right)


def _normalize_chem_token_key(token: str) -> str:
    raw = re.sub(r"\s+", "", str(token or "")).strip()
    if not raw:
        return ""
    return _normalize_unit_placeholder_token(_normalize_formula_token_chars(raw))


def _token_matches_patterns(
    patterns: list[re.Pattern[str]],
    token: str,
    normalized_token: str,
) -> bool:
    for pat in patterns:
        if pat.search(token):
            return True
        if normalized_token != token and pat.search(normalized_token):
            return True
    return False


def _resolve_chem_token_policy(
    token: str,
    normalized_token: str,
    chem_runtime: ChemRuntime,
) -> tuple[bool, str]:
    ignore_tokens, ignore_patterns, manual_overrides, allow_tokens, allow_patterns = chem_runtime
    if not normalized_token:
        return False, ""

    manual_mask = manual_overrides.get(normalized_token)
    if manual_mask:
        return True, manual_mask

    is_allowed = (
        normalized_token in allow_tokens
        or _token_matches_patterns(allow_patterns, token, normalized_token)
    )
    if not is_allowed:
        if _looks_like_ambiguous_identifier_token(token):
            return False, ""
        if normalized_token in ignore_tokens:
            return False, ""
        if _token_matches_patterns(ignore_patterns, token, normalized_token):
            return False, ""
        if _looks_like_instrument_model_token(token):
            return False, ""
    return True, ""


def _build_chem_dictionary_runtime(chem_cfg) -> ChemRuntime:
    ignore_tokens: set[str] = {
        _normalize_chem_token_key(v)
        for v in _INTERNAL_CHEM_IGNORE_TOKENS
        if _normalize_chem_token_key(v)
    }
    ignore_patterns: list[re.Pattern[str]] = list(_INTERNAL_CHEM_IGNORE_PATTERNS)
    manual_overrides: dict[str, str] = {
        _normalize_chem_token_key(k): str(v)
        for k, v in _INTERNAL_CHEM_MANUAL_OVERRIDES.items()
        if _normalize_chem_token_key(k) and str(v)
    }
    allow_tokens: set[str] = {
        _normalize_chem_token_key(v)
        for v in _INTERNAL_CHEM_ALLOW_TOKENS
        if _normalize_chem_token_key(v)
    }
    allow_patterns: list[re.Pattern[str]] = list(_INTERNAL_CHEM_ALLOW_PATTERNS)
    if chem_cfg is None:
        return ignore_tokens, ignore_patterns, manual_overrides, allow_tokens, allow_patterns

    raw_allow_tokens = getattr(chem_cfg, "allow_tokens", []) or []
    for raw in raw_allow_tokens:
        token = _normalize_chem_token_key(str(raw))
        if token:
            allow_tokens.add(token)

    raw_allow_patterns = getattr(chem_cfg, "allow_patterns", []) or []
    for raw in raw_allow_patterns:
        pat = str(raw).strip()
        if not pat:
            continue
        try:
            allow_patterns.append(re.compile(pat))
        except re.error:
            continue

    raw_tokens = getattr(chem_cfg, "ignore_tokens", []) or []
    for raw in raw_tokens:
        token = _normalize_chem_token_key(str(raw))
        if token:
            ignore_tokens.add(token)

    raw_patterns = getattr(chem_cfg, "ignore_patterns", []) or []
    for raw in raw_patterns:
        pat = str(raw).strip()
        if not pat:
            continue
        try:
            ignore_patterns.append(re.compile(pat))
        except re.error:
            continue

    raw_overrides = getattr(chem_cfg, "manual_overrides", {}) or {}
    if isinstance(raw_overrides, dict):
        for raw_token, raw_mask in raw_overrides.items():
            token = _normalize_chem_token_key(str(raw_token))
            mask = str(raw_mask or "")
            if token and mask:
                manual_overrides[token] = mask

    return ignore_tokens, ignore_patterns, manual_overrides, allow_tokens, allow_patterns


def _iter_chem_token_candidates(
    text: str,
    *,
    chem_cfg=None,
    chem_runtime: ChemRuntime | None = None,
):
    if not text:
        return
    trim_right_punct = ",.;:，。；："
    if chem_runtime is None:
        chem_runtime = _build_chem_dictionary_runtime(chem_cfg)
    scan_text = _normalize_formula_scan_text(text)
    for m in _CHEM_TOKEN_RE.finditer(scan_text):
        raw_token = text[m.start():m.end()]
        if not raw_token:
            continue

        token_start = 0
        token_end = len(raw_token)
        while token_end > token_start and raw_token[token_end - 1] in trim_right_punct:
            token_end -= 1
        token = raw_token[token_start:token_end]
        if not token:
            continue

        abs_start = m.start() + token_start
        abs_end = abs_start + len(token)
        normalized_token = _normalize_chem_token_key(token)
        if not normalized_token:
            continue
        if _is_weak_single_unit_exponent_token_in_context(
            text,
            abs_start,
            abs_end,
            token,
        ):
            continue
        right_char = text[abs_end] if abs_end < len(text) else ""
        right_non_space_char = _first_non_space_char(text[abs_end:])

        use_token, manual_mask = _resolve_chem_token_policy(token, normalized_token, chem_runtime)
        if not use_token:
            continue
        yield abs_start, abs_end, token, normalized_token, right_char, right_non_space_char, manual_mask


def _iter_compacted_formula_spans(text: str):
    """Yield spaced spans and compacted tokens for secondary matching.

    This recovers cases such as:
    - Fe - O
    - Fe (III)
    - [ Fe(CN)6 ]3-
    - mg / L
    """
    if not text:
        return
    trim_right_punct = ",.;:，。；："
    scan_text = _normalize_formula_scan_text(text)
    for m in _RE_SPACED_FORMULA_SPAN.finditer(scan_text):
        span = text[m.start():m.end()]
        if not span or not any(ch.isspace() for ch in span):
            continue
        if len(span) > 80:
            continue

        left_trim = len(span) - len(span.lstrip())
        right_trim = len(span) - len(span.rstrip())
        start = m.start() + left_trim
        end = m.end() - right_trim
        while end > start and text[end - 1] in trim_right_punct:
            end -= 1
        if end <= start:
            continue

        original = text[start:end]
        compact_raw = re.sub(r"\s+", "", original)
        if len(compact_raw) < 2:
            continue
        # Skip plain words/sentences.
        if not re.search(r"[A-Za-z0-9α-ωΑ-ΩµμΩω%％]", compact_raw):
            continue
        if not re.search(
            r"[\-−＋+＝=≡/／·•∙⋅\(\)\[\]\{\}<>→←↔^0-9－‐‑‒–—―%％"
            r"⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻₀₁₂₃₄₅₆₇₈₉₊₋]",
            compact_raw,
        ):
            continue

        compact_norm = _normalize_chem_token_key(compact_raw)
        if not compact_norm:
            continue
        yield start, end, original, compact_raw, compact_norm


def _apply_manual_override_mask(
    marks: list[str | None],
    token_start: int,
    token_text: str,
    mask: str,
) -> None:
    limit = min(len(token_text), len(mask))
    for i in range(limit):
        flag = mask[i]
        if flag == "^":
            marks[token_start + i] = "superscript"
        elif flag == "_":
            marks[token_start + i] = "subscript"


def _parse_formula_core_marks(core: str, marks: list[str | None]) -> tuple[bool, int, int]:
    """Parse chemistry core text and mark subscript digits."""
    if not core:
        return False, 0, 0

    i = 0
    n = len(core)
    element_count = 0
    subscript_count = 0
    close_stack: list[str] = []
    group_has_content: list[bool] = []
    component_start = True
    prev_was_dot = False
    saw_group = False

    while i < n:
        ch = core[i]
        if ch in _DOT_SEPARATORS:
            if prev_was_dot or i == 0 or i == n - 1:
                return False, 0, 0
            prev_was_dot = True
            component_start = True
            i += 1
            continue

        prev_was_dot = False
        if component_start:
            while i < n and core[i].isdigit():
                i += 1
            if i >= n:
                return False, 0, 0

        ch = core[i]
        if ch in _BRACKET_OPEN_TO_CLOSE:
            close_stack.append(_BRACKET_OPEN_TO_CLOSE[ch])
            group_has_content.append(False)
            i += 1
            component_start = True
            continue

        if ch in _BRACKET_OPEN_TO_CLOSE.values():
            if not close_stack or ch != close_stack[-1]:
                return False, 0, 0
            if not group_has_content or not group_has_content[-1]:
                return False, 0, 0
            close_stack.pop()
            group_has_content.pop()
            i += 1
            d0 = i
            while i < n and core[i].isdigit():
                i += 1
            if i > d0:
                _mark_style(marks, d0, i, "subscript")
                subscript_count += (i - d0)
            if group_has_content:
                group_has_content[-1] = True
            saw_group = True
            component_start = False
            continue

        if not _is_ascii_upper(ch):
            return False, 0, 0

        symbol = ch
        if i + 1 < n and _is_ascii_lower(core[i + 1]):
            candidate = core[i:i + 2]
            if candidate in _ELEMENT_SYMBOLS:
                symbol = candidate
                i += 2
            elif ch in _ELEMENT_SYMBOLS:
                i += 1
            else:
                return False, 0, 0
        else:
            if symbol not in _ELEMENT_SYMBOLS:
                return False, 0, 0
            i += 1

        element_count += 1
        d0 = i
        while i < n and core[i].isdigit():
            i += 1
        if i > d0:
            _mark_style(marks, d0, i, "subscript")
            subscript_count += (i - d0)
        if group_has_content:
            group_has_content[-1] = True
        saw_group = True
        component_start = False

    if close_stack or prev_was_dot or not saw_group:
        return False, 0, 0
    return True, element_count, subscript_count


def _choose_charge_digits_len(core_prefix: str, charge_digits: str, has_caret: bool) -> int:
    if not charge_digits:
        return 0
    if has_caret:
        return len(charge_digits)
    if core_prefix and core_prefix[-1] in ")]}":
        return len(charge_digits)
    if len(charge_digits) >= 2:
        return 1

    # One trailing digit before +/- is ambiguous:
    # - Fe3+ -> charge digit
    # - NH4+ / MnO4- -> formula digit
    test = core_prefix + charge_digits
    temp_marks: list[str | None] = [None] * len(test)
    ok, element_count, _ = _parse_formula_core_marks(test, temp_marks)
    if not ok:
        return len(charge_digits)
    return 1 if element_count <= 1 else 0


def _apply_isotope_prefix_marks(token: str, core_end: int, marks: list[str | None]) -> None:
    if core_end <= 1 or not token or not token[0].isdigit():
        return

    i = 0
    while i < core_end and token[i].isdigit():
        i += 1
    if i <= 0 or i >= core_end:
        return

    metastable = False
    elem_pos = i
    if token[elem_pos] in {"m", "M"} and (elem_pos + 1) < core_end and _is_ascii_upper(token[elem_pos + 1]):
        metastable = True
        elem_pos += 1
    if elem_pos >= core_end or not _is_ascii_upper(token[elem_pos]):
        return

    prefix = token[:i]
    # Avoid turning stoichiometric coefficients (e.g. 2H2O) into isotope marks.
    if metastable or len(prefix) >= 2 or token.startswith("1O"):
        _mark_style(marks, 0, i, "superscript")
        if metastable:
            _mark_style(marks, i, i + 1, "superscript")


def _normalize_formula_case_drift_for_composite(token: str) -> str:
    """Conservatively recover single-letter case drift inside slash composites."""
    t = _normalize_formula_token_chars(token or "")
    if not t:
        return ""
    if not any(ch.isdigit() for ch in t):
        return t
    if not any(_is_ascii_upper(ch) for ch in t):
        return t

    chars = list(t)
    for i, ch in enumerate(chars):
        if not _is_ascii_lower(ch):
            continue
        prev = chars[i - 1] if i > 0 else ""
        next_ch = chars[i + 1] if (i + 1) < len(chars) else ""
        if i > 0 and _is_ascii_upper(prev) and (prev + ch) in _ELEMENT_SYMBOLS:
            continue
        if prev.isdigit() and (next_ch.isdigit() or _is_ascii_upper(next_ch)):
            chars[i] = ch.upper()
    return "".join(chars)


def _looks_like_material_plain_segment(token: str) -> bool:
    """Allow non-formula material abbreviations inside slash-joined composites."""
    t = _normalize_formula_token_chars((token or "").strip())
    if not t:
        return False
    if _RE_SINGLE_ELEMENT_TOKEN.fullmatch(t):
        return t in _ELEMENT_SYMBOLS
    if _looks_like_plain_unit_token(t):
        return True
    if re.fullmatch(r"[A-Z]{2,6}[a-z]{0,2}", t):
        return True
    if re.fullmatch(r"[A-Z](?:-[A-Z]{1,6}[a-z]{0,2})+", t):
        return True
    return False


def _build_slash_formula_marks(
    token: str,
    right_char: str = "",
    right_non_space_char: str = "",
) -> list[str | None]:
    token = _normalize_formula_token_chars(token or "")
    n = len(token)
    if n <= 0 or "/" not in token:
        return [None] * n

    parts = token.split("/")
    if len(parts) < 2 or any(not part for part in parts):
        return [None] * n

    out: list[str | None] = [None] * n
    cursor = 0
    strong_part_count = 0
    for idx, part in enumerate(parts):
        normalized_part = _normalize_formula_case_drift_for_composite(part)
        nested = _build_token_formula_marks(
            normalized_part,
            right_char="/" if idx < len(parts) - 1 else right_char,
            right_non_space_char="/" if idx < len(parts) - 1 else right_non_space_char,
        )
        if any(nested):
            strong_part_count += 1
        elif not _looks_like_material_plain_segment(part):
            return [None] * n

        for i, style in enumerate(nested):
            if style and (cursor + i) < n:
                out[cursor + i] = style
        cursor += len(part)
        if idx < len(parts) - 1:
            cursor += 1

    return out if strong_part_count > 0 else [None] * n


def _build_token_chem_marks(
    token: str,
    right_char: str = "",
    right_non_space_char: str = "",
) -> list[str | None]:
    token = _normalize_formula_token_chars(token or "")
    n = len(token)
    token_marks: list[str | None] = [None] * n
    if n <= 0:
        return token_marks

    # Leading isotope notation with caret, e.g. ^14C, ^13CH4
    if token.startswith("^") and n > 2 and token[1].isdigit():
        nested = _build_token_chem_marks(
            token[1:],
            right_char=right_char,
            right_non_space_char=right_non_space_char,
        )
        if any(nested):
            for i, style in enumerate(nested):
                if style:
                    token_marks[i + 1] = style
            return token_marks

    # Leading radical dot, e.g. ·SO42- / •SO42-.
    # Keep the leading dot in baseline; only format formula body.
    if token[0] in {"·", "•"} and n > 1:
        nested = _build_token_chem_marks(
            token[1:],
            # Charge parsing should be based on the inner token boundary.
            right_char="",
            right_non_space_char="",
        )
        if any(nested):
            for i, style in enumerate(nested):
                if style:
                    token_marks[i + 1] = style
            return token_marks

    # Metastable isotope notation without caret, e.g. 99mTc
    m0 = re.match(r"^(?P<mass>\d{1,3})(?P<meta>[mM])(?P<rest>[A-Z].*)$", token)
    if m0:
        mass = m0.group("mass")
        rest = m0.group("rest")
        nested = _build_token_chem_marks(
            mass + rest,
            right_char=right_char,
            right_non_space_char=right_non_space_char,
        )
        if any(nested):
            mass_len = len(mass)
            for i, style in enumerate(nested):
                if not style:
                    continue
                mapped_i = i if i < mass_len else i + 1
                if mapped_i < n:
                    token_marks[mapped_i] = style
            token_marks[mass_len] = "superscript"
            return token_marks

    # Wrapper-enclosed formula/ion, e.g. (Fe3+), [SO42-], (^14C)
    open_br = token[0] if token else ""
    close_br = _BRACKET_OPEN_TO_CLOSE.get(open_br, "")
    if close_br and n >= 3 and token[-1] == close_br:
        inner = token[1:-1]
        nested = _build_token_chem_marks(
            inner,
            # Inner formula right boundary is the closing bracket, not outer sentence char.
            right_char=close_br,
            right_non_space_char=close_br,
        )
        if any(nested):
            for i, style in enumerate(nested):
                if style:
                    token_marks[i + 1] = style
            return token_marks

    # Mass-spec adduct notation: [M+H]+, [M+2H]2+, [M-H]-
    m_adduct = _RE_MASS_ADDUCT_CHARGE.match(token)
    if m_adduct:
        body = token[1:token.rfind("]")]
        # Avoid misclassifying coordination complexes like [ZnCl4]2- as adducts.
        has_inner_adduct_sign = any(ch in _CHARGE_SIGNS for ch in body)
        if has_inner_adduct_sign and any(_is_ascii_upper(ch) for ch in body):
            charge = m_adduct.group(1)
            charge_start = n - len(charge)
            _mark_style(token_marks, charge_start, n, "superscript")
            return token_marks

    sign_start = n
    while sign_start > 0 and token[sign_start - 1] in _CHARGE_SIGNS:
        sign_start -= 1
    has_charge_tail = sign_start < n
    if has_charge_tail and right_char and _is_word_or_cjk(right_char):
        has_charge_tail = False
        sign_start = n

    charge_start = n
    charge_digits_start = sign_start
    if has_charge_tail:
        dstart = sign_start
        while dstart > 0 and token[dstart - 1].isdigit():
            dstart -= 1
        has_caret = dstart > 0 and token[dstart - 1] == "^"
        core_prefix = token[:dstart]
        charge_digits = token[dstart:sign_start]
        # Bond-like text split by whitespace, e.g. "Fe- O", should not treat '-' as ion charge.
        if (
            not charge_digits
            and not has_caret
            and right_char
            and right_char.isspace()
            and right_non_space_char
            and _is_ascii_upper(right_non_space_char)
            and core_prefix in _ELEMENT_SYMBOLS
        ):
            has_charge_tail = False
            sign_start = n
            charge_start = n
            charge_digits_start = n
        if not has_charge_tail:
            charge_start = n
            charge_digits_start = n
        else:
            charge_digits_len = _choose_charge_digits_len(core_prefix, charge_digits, has_caret)
            charge_digits_start = sign_start - charge_digits_len
            if has_caret:
                charge_start = dstart - 1
                charge_digits_start = dstart
            else:
                charge_start = charge_digits_start
    else:
        charge_start = n

    core = token[:charge_start]
    if not core:
        return token_marks

    core_marks: list[str | None] = [None] * len(core)
    ok, _, _ = _parse_formula_core_marks(core, core_marks)
    if not ok:
        return token_marks
    for i, style in enumerate(core_marks):
        if style:
            token_marks[i] = style

    _apply_isotope_prefix_marks(token, charge_start, token_marks)
    if has_charge_tail and charge_digits_start < n:
        _mark_style(token_marks, charge_digits_start, n, "superscript")

    return token_marks


def _is_radical_token_candidate(token: str) -> bool:
    if not token:
        return False
    open_br = token[0]
    close_br = _BRACKET_OPEN_TO_CLOSE.get(open_br, "")
    if close_br and len(token) >= 3 and token[-1] == close_br:
        inner = token[1:-1]
        if any(ch in _RADICAL_DOT_CHARS for ch in inner):
            return True
    if not any(ch in _RADICAL_DOT_CHARS for ch in token):
        return False

    # Prefix/suffix radical marks, e.g. ·OH, OH·
    if token[0] in _RADICAL_DOT_CHARS or token[-1] in _RADICAL_DOT_CHARS:
        return True

    # Dot next to charge patterns, e.g. O2·-, SO4^-·, SO4·2-
    for i, ch in enumerate(token):
        if ch not in _RADICAL_DOT_CHARS:
            continue
        prev_ch = token[i - 1] if i > 0 else ""
        next_ch = token[i + 1] if (i + 1) < len(token) else ""
        if prev_ch in _CHARGE_SIGNS + "^" or next_ch in _CHARGE_SIGNS + "^":
            return True
    return False


def _build_token_radical_marks(
    token: str,
    right_char: str = "",
    right_non_space_char: str = "",
) -> list[str | None]:
    """Recognize broader radical notations while keeping radical dot baseline."""
    n = len(token)
    marks: list[str | None] = [None] * n
    if n <= 0 or not _is_radical_token_candidate(token):
        return marks

    # Wrapper-enclosed radicals, e.g. (·OH), [SO4·-]
    open_br = token[0]
    close_br = _BRACKET_OPEN_TO_CLOSE.get(open_br, "")
    if close_br and n >= 3 and token[-1] == close_br:
        nested = _build_token_radical_marks(
            token[1:-1],
            # Inner radical right boundary is the closing bracket.
            right_char=close_br,
            right_non_space_char=close_br,
        )
        if any(nested):
            for i, style in enumerate(nested):
                if style:
                    marks[i + 1] = style
            return marks

    cleaned_chars: list[str] = []
    mapping: list[int] = []
    for idx, ch in enumerate(token):
        if ch in _RADICAL_DOT_CHARS:
            continue
        cleaned_chars.append(ch)
        mapping.append(idx)

    cleaned = "".join(cleaned_chars)
    if not cleaned:
        return marks

    nested = _build_token_chem_marks(
        cleaned,
        right_char=right_char,
        right_non_space_char=right_non_space_char,
    )
    # In radical contexts, O2- / N2- style is usually "subscript stoichiometry + charge".
    m_single = re.fullmatch(r"([A-Z][a-z]?)(\d)([+\-−＋－])", cleaned)
    if m_single:
        elem = m_single.group(1)
        digit_idx = len(elem)
        if (
            elem in {"O", "N", "S", "C", "H", "P"}
            and digit_idx < len(nested)
            and len(nested) >= 1
            and nested[digit_idx] == "superscript"
            and nested[-1] == "superscript"
        ):
            nested = list(nested)
            nested[digit_idx] = "subscript"

    if not any(nested):
        return marks

    for i, style in enumerate(nested):
        if not style:
            continue
        if i < len(mapping):
            marks[mapping[i]] = style
    return marks


def _is_unit_symbol_char(ch: str) -> bool:
    if _is_ascii_upper(ch) or _is_ascii_lower(ch):
        return True
    return ch in {"µ", "μ", "Ω", "ω", "°", "℃", "%", "‰"}


def _token_has_unit_symbol_hint(token: str) -> bool:
    """Heuristic: token looks like a scientific unit fragment."""
    t = _normalize_formula_token_chars(token or "")
    if not t:
        return False
    if any(_is_ascii_lower(ch) for ch in t):
        return True
    return any(ch in {"µ", "μ", "Ω", "ω", "%", "‰"} for ch in t)


def _normalize_unit_segment_key(unit_text: str) -> str:
    t = _normalize_formula_token_chars(unit_text or "")
    t = re.sub(r"\s+", "", t)
    if not t:
        return ""
    t = t.replace("µ", "μ")
    return t


def _is_known_unit_segment(unit_text: str) -> bool:
    """Conservative whitelist for unit stems before applying exponent typography."""
    key = _normalize_unit_segment_key(unit_text)
    if not key:
        return False

    key_low = key.lower()
    if key_low in _KNOWN_UNIT_SEGMENTS:
        return True
    if _looks_like_plain_unit_token(key):
        return True

    if key.startswith("(") and key.endswith(")") and len(key) > 2:
        inner = key[1:-1]
        if _looks_like_plain_unit_token(key):
            return True
        if re.fullmatch(r"[A-Za-zμΩω%·\./]+", inner or ""):
            return True
    return False


def _build_token_unit_formula_marks(token: str, right_char: str = "") -> list[str | None]:
    """Recognize scientific unit expressions and mark exponent part.

    Examples:
    - μmol·g-1
    - h-1
    - cm-2
    - mL-1
    """
    raw_token = token or ""
    token = _normalize_formula_token_chars(raw_token)
    n = len(token)
    token_marks: list[str | None] = [None] * n
    if n <= 0:
        return token_marks

    # Unit exponents are expected to be attached with sign/digit hints.
    if not any(ch.isdigit() for ch in token):
        return token_marks

    def _mark_unit_exp(start: int, end: int) -> None:
        for idx in range(max(0, start), min(n, end)):
            if idx < len(raw_token) and raw_token[idx] in _SUPER_SUB_UNICODE_CHARS:
                continue
            token_marks[idx] = "superscript"

    i = 0
    has_mark = False
    while i < n:
        while i < n and token[i].isdigit():
            i += 1
        if i >= n:
            return [None] * n

        seg_start = i
        if token[i] == "(":
            depth = 0
            while i < n:
                ch = token[i]
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                elif not (
                    _is_unit_symbol_char(ch)
                    or ch in _DOT_SEPARATORS
                    or ch == "/"
                    or ch.isspace()
                ):
                    return [None] * n
                i += 1
            if depth != 0:
                return [None] * n
        else:
            while i < n and _is_unit_symbol_char(token[i]):
                i += 1
            if i == seg_start:
                return [None] * n
        unit_text = token[seg_start:i]

        exp_start = i
        if i < n and token[i] == "^":
            i += 1
            exp_start = i

        has_sign = False
        if i < n and token[i] in _CHARGE_SIGNS:
            has_sign = True
            i += 1

        d0 = i
        while i < n and token[i].isdigit():
            i += 1

        # Guard number-range tokens like "200k-1.1M": this is usually a scale
        # interval, not a unit exponent, and should stay plain text.
        if (
            has_sign
            and i > d0
            and i < n
            and token[i] == "."
            and (i + 1) < n
            and token[i + 1].isdigit()
        ):
            return [None] * n

        # Signed exponent in unit expression, e.g. g-1 / mA-2.
        if has_sign and i > d0:
            if not _is_known_unit_segment(unit_text):
                return [None] * n
            _mark_unit_exp(exp_start, i)
            has_mark = True
        elif i > d0:
            # Bare positive exponent, e.g. cm2/m3. Keep this conservative.
            if _is_known_unit_segment(unit_text):
                if i < n and (_is_unit_symbol_char(token[i]) or token[i] == "("):
                    nested = _build_token_unit_formula_marks(token[i:], right_char=right_char)
                    if not any(nested):
                        return [None] * n
                _mark_unit_exp(d0, i)
                has_mark = True
            else:
                return [None] * n

        if i >= n:
            break

        if token[i] in _DOT_SEPARATORS + "/":
            i += 1
            continue
        # Accept implicit product segments, e.g. g-1h-1.
        if _is_unit_symbol_char(token[i]) or token[i] == "(":
            continue
        return [None] * n

    # Avoid cases like CHI760 where trailing digits should stay plain.
    if right_char and _is_word_or_cjk(right_char):
        # Allow unit exponents before CJK tails (common in Chinese text).
        if not (_is_cjk(right_char) and _token_has_unit_symbol_hint(token)):
            return [None] * n
    return token_marks if has_mark else [None] * n


def _neighbor_unit_context_chunk(text: str, *, abs_start: int, abs_end: int, left: bool) -> str:
    if left:
        m = re.search(r"([A-Za-zµμΩω%\(\)\-^0-9]+)\s*$", text[:abs_start])
    else:
        m = re.match(r"\s*([A-Za-zµμΩω%\(\)\-^0-9]+)", text[abs_end:])
    return m.group(1) if m else ""


def _chunk_has_strong_unit_signal(chunk: str) -> bool:
    t = _normalize_formula_token_chars((chunk or "").strip())
    if not t:
        return False
    if _is_known_unit_segment(t):
        return True
    return any(_build_token_unit_formula_marks(t))


def _is_weak_single_unit_exponent_token_in_context(
    text: str,
    abs_start: int,
    abs_end: int,
    token: str,
) -> bool:
    t = _normalize_formula_token_chars((token or "").strip())
    if not re.fullmatch(r"[a-z]-\d+", t):
        return False

    left_slice = text[:abs_start].rstrip()
    left_non_space = left_slice[-1] if left_slice else ""
    right_non_space = _first_non_space_char(text[abs_end:])

    if right_non_space and _is_cjk(right_non_space):
        return False
    if (
        (left_non_space and left_non_space in _DOT_SEPARATORS + "/")
        or (right_non_space and right_non_space in _DOT_SEPARATORS + "/")
    ):
        return False

    left_chunk = _neighbor_unit_context_chunk(
        text,
        abs_start=abs_start,
        abs_end=abs_end,
        left=True,
    )
    right_chunk = _neighbor_unit_context_chunk(
        text,
        abs_start=abs_start,
        abs_end=abs_end,
        left=False,
    )
    if _chunk_has_strong_unit_signal(left_chunk):
        return False
    if _chunk_has_strong_unit_signal(right_chunk):
        return False
    return True


def _is_weak_single_unit_exponent_leading_span(span_text: str) -> bool:
    span = _normalize_formula_scan_text((span_text or "").strip())
    if not span:
        return False

    m = re.match(r"(?P<token>[a-z]-\d+)\s+(?P<rest>.+)$", span)
    if not m:
        return False

    rest = m.group("rest").lstrip()
    if not rest:
        return True

    right_non_space = _first_non_space_char(rest)
    if right_non_space and _is_cjk(right_non_space):
        return False
    if right_non_space and right_non_space in _DOT_SEPARATORS + "/":
        return False

    next_chunk = _neighbor_unit_context_chunk(rest, abs_start=0, abs_end=0, left=False)
    if _chunk_has_strong_unit_signal(next_chunk):
        return False
    return True


def _build_token_formula_marks(
    token: str,
    right_char: str = "",
    right_non_space_char: str = "",
) -> list[str | None]:
    """Unified formula recognizer: chemistry first, then scientific units."""
    token = _normalize_formula_token_chars(token or "")
    n = len(token)
    if n <= 0:
        return []

    # Common tail qualifiers in corpora, e.g. μmol·g-1·h-1-dry
    m_suffix = re.fullmatch(r"(?P<core>.+?)(?P<suffix>[-_][A-Za-z]{2,12})", token)
    if m_suffix:
        core = m_suffix.group("core")
        if any(ch.isdigit() for ch in core):
            nested = _build_token_formula_marks(
                core,
                right_char=right_char,
                right_non_space_char=right_non_space_char,
            )
            if any(nested):
                out: list[str | None] = [None] * n
                for i, style in enumerate(nested):
                    if style:
                        out[i] = style
                return out

    m_phase = _RE_PHASE_PREFIX_TOKEN.fullmatch(token)
    if m_phase:
        nested = _build_token_formula_marks(
            m_phase.group("rest"),
            right_char=right_char,
            right_non_space_char=right_non_space_char,
        )
        if any(nested):
            out: list[str | None] = [None] * n
            offset = len(m_phase.group("prefix") + m_phase.group("sep"))
            for i, style in enumerate(nested):
                if style and (offset + i) < n:
                    out[offset + i] = style
            return out

    slash_marks = _build_slash_formula_marks(
        token,
        right_char=right_char,
        right_non_space_char=right_non_space_char,
    )
    if any(slash_marks):
        return slash_marks

    # Balanced wrapper around a single token, e.g. "(cm-2)", "[cm-2]".
    wrapper_pairs = {"(": ")", "[": "]", "{": "}"}
    outer_open = token[0]
    outer_close = wrapper_pairs.get(outer_open, "")
    if outer_close and n >= 3 and token[-1] == outer_close:
        depth = 0
        wrapped_once = True
        for idx, ch in enumerate(token):
            if ch == outer_open:
                depth += 1
            elif ch == outer_close:
                depth -= 1
                if depth == 0 and idx < n - 1:
                    wrapped_once = False
                    break
                if depth < 0:
                    wrapped_once = False
                    break
        inner = token[1:-1]
        if wrapped_once and depth == 0 and _token_has_unit_symbol_hint(inner):
            nested = _build_token_formula_marks(
                inner,
                right_char=outer_close,
                right_non_space_char=outer_close,
            )
            if any(nested):
                wrapped_marks: list[str | None] = [None] * n
                for i, style in enumerate(nested):
                    if style and (i + 1) < n:
                        wrapped_marks[i + 1] = style
                return wrapped_marks

    # Unbalanced wrapper noise around units, e.g. "(μmol·g-1·h-1" / "μmol·g-1·h-1)"
    unmatched_tail = {")": ("(", ")"), "]": ("[", "]"), "}": ("{", "}")}
    if token[-1] in unmatched_tail:
        open_ch, close_ch = unmatched_tail[token[-1]]
        if token.count(open_ch) < token.count(close_ch):
            nested = _build_token_formula_marks(
                token[:-1],
                right_char=token[-1],
                right_non_space_char=right_non_space_char,
            )
            if any(nested):
                return list(nested) + [None]

    unmatched_head = {"(": ("(", ")"), "[": ("[", "]"), "{": ("{", "}")}
    if token[0] in unmatched_head:
        open_ch, close_ch = unmatched_head[token[0]]
        if token.count(open_ch) > token.count(close_ch):
            nested = _build_token_formula_marks(
                token[1:],
                right_char=right_char,
                right_non_space_char=right_non_space_char,
            )
            if any(nested):
                out: list[str | None] = [None] * n
                for i, style in enumerate(nested):
                    if style and (i + 1) < n:
                        out[i + 1] = style
                return out

    m_roman = _RE_ROMAN_OX_STATE.fullmatch(token)
    if m_roman and m_roman.group("elem") in _ELEMENT_SYMBOLS:
        # Roman oxidation states are chemistry qualifiers, not charge marks.
        # Keep them eligible for chemistry-token/font detection via the
        # surrounding recognizer chain, but do not emit super/subscript here.
        return [None] * n

    if _RE_ROMAN_OXO_TOKEN.fullmatch(token):
        # Fe(IV)=O / Mn(V)=O-like tokens should keep formula font, but the
        # oxidation-state Roman numeral itself is baseline text rather than a
        # charge superscript.
        return [None] * n

    if _looks_like_isotope_label_token(token):
        m_iso = _RE_ISOTOPE_LABEL_TOKEN.fullmatch(token)
        if m_iso:
            isotope_marks: list[str | None] = [None] * n
            _mark_style(isotope_marks, m_iso.start("mass"), m_iso.end("mass"), "superscript")
            return isotope_marks

    m_greek = _RE_GREEK_PREFIX_TOKEN.fullmatch(token)
    if m_greek:
        rest = m_greek.group("rest")
        nested = _build_token_formula_marks(
            rest,
            right_char=right_char,
            right_non_space_char=right_non_space_char,
        )
        if any(nested):
            offset = len(m_greek.group("prefix") + m_greek.group("sep"))
            greek_marks: list[str | None] = [None] * n
            for i, style in enumerate(nested):
                if style and (offset + i) < n:
                    greek_marks[offset + i] = style
            return greek_marks

    is_hybrid = bool(_RE_HYBRIDIZATION_TOKEN.fullmatch(token))
    if not is_hybrid and "/" in token:
        parts = token.split("/")
        is_hybrid = bool(parts) and all(
            part and _RE_HYBRIDIZATION_TOKEN.fullmatch(part)
            for part in parts
        )
    if is_hybrid:
        hybrid_marks: list[str | None] = [None] * n
        for idx, ch in enumerate(token):
            if ch.isdigit():
                hybrid_marks[idx] = "superscript"
        return hybrid_marks

    if _is_ambiguous_neutral_compact_token(token):
        return [None] * n

    radical_marks = _build_token_radical_marks(
        token,
        right_char=right_char,
        right_non_space_char=right_non_space_char,
    )
    if any(radical_marks):
        return radical_marks

    has_upper = any(_is_ascii_upper(ch) for ch in token)
    has_math_hint = any(ch.isdigit() or ch in _CHARGE_SIGNS + "^()[]{}" for ch in token)
    if has_upper and has_math_hint:
        chem_marks = _build_token_chem_marks(
            token,
            right_char=right_char,
            right_non_space_char=right_non_space_char,
        )
        if any(chem_marks):
            return chem_marks

    if _RE_BRACKET_COMPLEX_WITH_CHARGE.fullmatch(token):
        complex_marks: list[str | None] = [None] * n
        m_charge = re.search(r"\d*[+\-−＋－]$", token)
        if m_charge:
            _mark_style(complex_marks, m_charge.start(), m_charge.end(), "superscript")
        for m_count in re.finditer(r"\)\d+", token):
            _mark_style(complex_marks, m_count.start() + 1, m_count.end(), "subscript")
        if any(complex_marks):
            return complex_marks

    return _build_token_unit_formula_marks(token, right_char=right_char)


def _is_bond_like_chem_token(token: str) -> bool:
    t = _normalize_formula_token_chars((token or "").strip())
    if not t:
        return False
    if not _RE_BOND_TOKEN.fullmatch(t):
        return False
    symbols = [part for part in re.split(r"[\-−－‐‑‒–—―=≡]+", t) if part]
    return len(symbols) >= 2 and all(sym in _ELEMENT_SYMBOLS for sym in symbols)


def _is_formula_like_token_for_font(
    token: str,
    right_char: str = "",
    right_non_space_char: str = "",
) -> bool:
    t = _normalize_formula_token_chars((token or "").strip())
    if not t:
        return False
    if _is_formula_like_token_without_arrow(
        t,
        right_char=right_char,
        right_non_space_char=right_non_space_char,
    ):
        return True
    return _looks_like_reaction_arrow_token(t)


def _looks_like_instrument_model_token(token: str) -> bool:
    t = _normalize_formula_token_chars((token or "").strip())
    t = re.sub(r"[?？]+$", "", t)
    t = re.sub(r"-type$", "", t, flags=re.IGNORECASE)
    if len(t) < 5:
        return False
    if not t.isascii():
        return False
    t_upper = t.upper()
    if any(ch in t_upper for ch in (_CHARGE_SIGNS + "^()[]{}" + _DOT_SEPARATORS)):
        return False
    if not re.fullmatch(r"[A-Z0-9\-]+", t_upper):
        return False
    m = re.fullmatch(r"([A-Z]{2,})(\d{2,})([A-Z0-9\-]*)", t_upper)
    if not m:
        return False
    prefix = m.group(1)
    digits = m.group(2)
    if len(digits) >= 3:
        return True
    return prefix in _INSTRUMENT_MODEL_PREFIXES


def _looks_like_domain_like_token(token: str) -> bool:
    t = _normalize_formula_token_chars((token or "").strip())
    if not t:
        return False
    return bool(_RE_DOMAIN_LIKE_TOKEN.fullmatch(t))


def _is_ambiguous_neutral_compact_token(token: str) -> bool:
    """Skip aggressive neutral-token recovery for identifier-like compact tokens."""
    t = _normalize_formula_token_chars((token or "").strip())
    if not t:
        return False
    if any(ch in t for ch in (_CHARGE_SIGNS + "^()[]{}" + _DOT_SEPARATORS + "/%")):
        return False
    if not re.fullmatch(r"[A-Z0-9]+", t):
        return False

    if re.fullmatch(r"[A-Z]\d+[A-Z]{2,}", t):
        return True

    if re.fullmatch(r"[A-Z]\d+[A-Z]", t):
        return t[-1] not in _ALLOWED_NEUTRAL_COMPACT_TAILS

    return False


def _looks_like_ambiguous_identifier_token(token: str) -> bool:
    """Conservative skip-list for non-chemical labels frequently seen in docs."""
    t = _normalize_formula_token_chars((token or "").strip())
    if not t:
        return False
    if _RE_APPENDIX_LABEL_TOKEN.fullmatch(t):
        return True
    if _RE_PREFIXED_APPENDIX_LABEL_TOKEN.fullmatch(t):
        return True
    if _looks_like_domain_like_token(t):
        return True
    if any(ch in t for ch in (_CHARGE_SIGNS + "^()[]{}" + _DOT_SEPARATORS + "/%")):
        return False
    if not t.isascii():
        return False

    t_upper = t.upper()
    if _RE_HISTONE_MARK_TOKEN.fullmatch(t_upper):
        return True
    if _RE_SHORT_IDENTIFIER_TOKEN.fullmatch(t_upper):
        return t_upper not in _COMMON_SINGLE_LETTER_FORMULA_TOKENS
    return False


def _looks_like_spaced_single_letter_isotope_noise(span_text: str, compact_token: str) -> bool:
    """Skip compacted number+single-letter spans produced by wide alignment gaps."""
    span = _normalize_formula_token_chars((span_text or "").strip())
    compact = _normalize_formula_token_chars((compact_token or "").strip())
    if not span or not compact:
        return False
    if not _RE_COMPACT_SINGLE_LETTER_ISOTOPE_TOKEN.fullmatch(compact):
        return False
    if bool(re.search(r"\s{2,}", span)):
        return True

    if re.fullmatch(r"\d+\s+[A-Z]", span) and compact[-1] in _COMMON_SPACED_SINGLE_LETTER_UNIT_SYMBOLS:
        return True

    symbol = compact[-1]
    mass = int(compact[:-1])
    if symbol == "D":
        return mass != 2
    if symbol == "T":
        return mass != 3

    atomic_number = _SINGLE_LETTER_ELEMENT_ATOMIC_NUMBERS.get(symbol)
    if atomic_number is None:
        return True

    # Conservative plausibility guard for compacted spaced isotopes. This keeps
    # common cases like 14 C / 15 N while filtering obvious measurement values
    # such as 300 W / 220 V / 300 N.
    upper_bound = max(atomic_number, (28 * atomic_number + 9) // 10)  # ceil(2.8 * Z)
    return not (atomic_number <= mass <= upper_bound)


def _build_chem_style_marks(
    text: str,
    chem_cfg=None,
    chem_runtime: ChemRuntime | None = None,
) -> list[str | None]:
    """Build per-char desired style marks for chemistry-like typography."""
    marks: list[str | None] = [None] * len(text)
    if not text:
        return marks

    runtime = chem_runtime if chem_runtime is not None else _build_chem_dictionary_runtime(chem_cfg)

    for abs_start, _, token, _, right_char, right_non_space_char, manual_mask in _iter_chem_token_candidates(
        text,
        chem_cfg=chem_cfg,
        chem_runtime=runtime,
    ):
        if manual_mask:
            _apply_manual_override_mask(marks, abs_start, token, manual_mask)
            continue

        token_marks = _build_token_formula_marks(
            token,
            right_char=right_char,
            right_non_space_char=right_non_space_char,
        )
        if not any(token_marks):
            continue
        for i, style in enumerate(token_marks):
            if style:
                marks[abs_start + i] = style

    for span_start, span_end, span_text, compact_raw, compact_norm in _iter_compacted_formula_spans(text):
        if _looks_like_spaced_single_letter_isotope_noise(span_text, compact_raw):
            continue
        if _is_weak_single_unit_exponent_leading_span(span_text):
            continue
        right_char = text[span_end] if span_end < len(text) else ""
        right_non_space_char = _first_non_space_char(text[span_end:])
        use_span, manual_mask = _resolve_chem_token_policy(compact_raw, compact_norm, runtime)
        if not use_span:
            continue

        non_space_offsets = [idx for idx, ch in enumerate(span_text) if not ch.isspace()]
        if not non_space_offsets:
            continue

        if manual_mask:
            limit = min(len(non_space_offsets), len(manual_mask))
            for i in range(limit):
                flag = manual_mask[i]
                if flag == "^":
                    marks[span_start + non_space_offsets[i]] = "superscript"
                elif flag == "_":
                    marks[span_start + non_space_offsets[i]] = "subscript"
            continue

        token_marks = _build_token_formula_marks(
            compact_raw,
            right_char=right_char,
            right_non_space_char=right_non_space_char,
        )
        if not any(token_marks):
            continue
        limit = min(len(non_space_offsets), len(token_marks))
        for i in range(limit):
            style = token_marks[i]
            if style:
                marks[span_start + non_space_offsets[i]] = style
    return marks


def _build_chem_font_mask(
    text: str,
    chem_cfg=None,
    chem_runtime: ChemRuntime | None = None,
) -> list[bool]:
    """Build per-char mask for formula-like tokens that should keep western font."""
    mask: list[bool] = [False] * len(text)
    if not text:
        return mask

    runtime = chem_runtime if chem_runtime is not None else _build_chem_dictionary_runtime(chem_cfg)

    for abs_start, abs_end, token, _, right_char, right_non_space_char, manual_mask in _iter_chem_token_candidates(
        text,
        chem_cfg=chem_cfg,
        chem_runtime=runtime,
    ):
        if manual_mask:
            for i in range(abs_start, abs_end):
                mask[i] = True
            continue
        if not _is_formula_like_token_for_font(
            token,
            right_char=right_char,
            right_non_space_char=right_non_space_char,
        ):
            continue
        for i in range(abs_start, abs_end):
            mask[i] = True

    for span_start, span_end, span_text, compact_raw, compact_norm in _iter_compacted_formula_spans(text):
        if _looks_like_spaced_single_letter_isotope_noise(span_text, compact_raw):
            continue
        if _is_weak_single_unit_exponent_leading_span(span_text):
            continue
        right_char = text[span_end] if span_end < len(text) else ""
        right_non_space_char = _first_non_space_char(text[span_end:])
        use_span, manual_mask = _resolve_chem_token_policy(compact_raw, compact_norm, runtime)
        if not use_span:
            continue

        non_space_offsets = [idx for idx, ch in enumerate(span_text) if not ch.isspace()]
        if not non_space_offsets:
            continue

        if manual_mask or _is_formula_like_token_for_font(
            compact_raw,
            right_char=right_char,
            right_non_space_char=right_non_space_char,
        ):
            for idx in non_space_offsets:
                mask[span_start + idx] = True
    return mask


def _set_rpr_vert_align(r_el, style: str) -> None:
    """Apply/override w:vertAlign on run element."""
    if style not in {"superscript", "subscript"}:
        return
    rpr = r_el.find(f"{{{_W_NS}}}rPr")
    if rpr is None:
        rpr = OxmlElement("w:rPr")
        r_el.insert(0, rpr)
    va = rpr.find(f"{{{_W_NS}}}vertAlign")
    if va is not None:
        rpr.remove(va)
    va = OxmlElement("w:vertAlign")
    va.set(f"{{{_W_NS}}}val", style)
    rpr.append(va)


def _new_text_run_element(text: str, base_rpr_el):
    r = OxmlElement("w:r")
    if base_rpr_el is not None:
        r.append(deepcopy(base_rpr_el))
    t = OxmlElement("w:t")
    t.text = text
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    r.append(t)
    return r


def _resolve_run_ascii_font(run_el) -> str | None:
    rpr = run_el.find(f"{{{_W_NS}}}rPr")
    if rpr is None:
        return None
    rfonts = rpr.find(f"{{{_W_NS}}}rFonts")
    if rfonts is None:
        return None
    for key in ("ascii", "hAnsi", "cs", "eastAsia"):
        val = rfonts.get(f"{{{_W_NS}}}{key}")
        if val:
            return val
    return None


def _normalize_explicit_run_font_hints_in_root(root) -> int:
    changed = 0
    hint_q = f"{{{_W_NS}}}hint"
    explicit_attrs = ("ascii", "hAnsi", "eastAsia", "cs")
    theme_attrs = ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "csTheme", "cstheme")
    for run_el in root.iter(f"{{{_W_NS}}}r"):
        rpr = run_el.find(f"{{{_W_NS}}}rPr")
        if rpr is None:
            continue
        rfonts = rpr.find(f"{{{_W_NS}}}rFonts")
        if rfonts is None:
            continue
        hint = str(rfonts.get(hint_q) or "").strip().lower()
        if hint != "eastasia":
            continue
        if not any(rfonts.get(f"{{{_W_NS}}}{attr}") for attr in explicit_attrs):
            continue
        rfonts.set(hint_q, "default")
        for attr in theme_attrs:
            q = f"{{{_W_NS}}}{attr}"
            if q in rfonts.attrib:
                rfonts.attrib.pop(q, None)
        changed += 1
    return changed


def _normalize_explicit_run_font_hints(doc: Document) -> int:
    return _normalize_explicit_run_font_hints_in_root(doc.element.body)


def normalize_explicit_run_font_hints_in_paragraph(paragraph) -> int:
    """Normalize explicit font hints only inside one authorized paragraph."""
    return _normalize_explicit_run_font_hints_in_root(paragraph._p)


def _normalize_related_story_part_font_hints(doc: Document) -> dict[str, int]:
    changed_parts: dict[str, int] = {}
    seen_partnames: set[str] = set()
    target_exact = {
        "/word/comments.xml",
        "/word/footnotes.xml",
        "/word/endnotes.xml",
    }
    target_prefixes = (
        "/word/header",
        "/word/footer",
    )

    for rel in doc.part.rels.values():
        part = getattr(rel, "target_part", None)
        partname = str(getattr(part, "partname", "") or "")
        if not partname or partname in seen_partnames:
            continue
        if partname not in target_exact and not any(
            partname.startswith(prefix) for prefix in target_prefixes
        ):
            continue
        seen_partnames.add(partname)

        root = getattr(part, "element", None)
        writeback_blob = False
        if root is None:
            blob = getattr(part, "blob", None)
            if not blob:
                continue
            try:
                root = etree.fromstring(blob)
            except Exception:
                continue
            writeback_blob = True

        part_changes = _normalize_explicit_run_font_hints_in_root(root)
        if not part_changes:
            continue

        changed_parts[partname] = part_changes
        if writeback_blob:
            part._blob = etree.tostring(
                root,
                encoding="UTF-8",
                xml_declaration=True,
                standalone=True,
            )

    return changed_parts


def _set_run_all_fonts(run_el, font_name: str) -> bool:
    if not font_name:
        return False
    rpr = run_el.find(f"{{{_W_NS}}}rPr")
    if rpr is None:
        rpr = OxmlElement("w:rPr")
        run_el.insert(0, rpr)
    rfonts = rpr.find(f"{{{_W_NS}}}rFonts")
    if rfonts is None:
        rfonts = etree.SubElement(rpr, f"{{{_W_NS}}}rFonts")

    changed = False
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        q = f"{{{_W_NS}}}{key}"
        if rfonts.get(q) != font_name:
            rfonts.set(q, font_name)
            changed = True
    hint_q = f"{{{_W_NS}}}hint"
    if rfonts.get(hint_q) != "default":
        rfonts.set(hint_q, "default")
        changed = True
    for attr in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "csTheme", "cstheme"):
        q = f"{{{_W_NS}}}{attr}"
        if q in rfonts.attrib:
            rfonts.attrib.pop(q, None)
            changed = True
    return changed


def _normalize_super_sub_unicode_font_in_para(para) -> int:
    """Force western font on unicode super/subscript symbols (e.g. ⁻²)."""
    if not para.runs:
        return 0

    changed_chars = 0
    runs_snapshot = list(para.runs)
    for run in runs_snapshot:
        txt = run.text or ""
        if not txt:
            continue
        has_special = any(ch in _SUPER_SUB_UNICODE_CHARS for ch in txt)
        if not has_special:
            continue

        parent = run._element.getparent()
        if parent is None:
            continue
        target_font = _resolve_run_ascii_font(run._element) or (run.font.name or "Times New Roman")

        if all(ch in _SUPER_SUB_UNICODE_CHARS for ch in txt):
            if _set_run_all_fonts(run._element, target_font):
                changed_chars += len(txt)
            continue

        base_rpr = run._element.find(f"{{{_W_NS}}}rPr")
        insert_at = parent.index(run._element)
        seg_start = 0
        current_is_special = txt[0] in _SUPER_SUB_UNICODE_CHARS
        for i in range(1, len(txt) + 1):
            is_boundary = i == len(txt) or (txt[i] in _SUPER_SUB_UNICODE_CHARS) != current_is_special
            if not is_boundary:
                continue
            seg_text = txt[seg_start:i]
            if seg_text:
                new_r = _new_text_run_element(seg_text, base_rpr)
                if current_is_special and _set_run_all_fonts(new_r, target_font):
                    changed_chars += len(seg_text)
                parent.insert(insert_at, new_r)
                insert_at += 1
            if i < len(txt):
                seg_start = i
                current_is_special = txt[i] in _SUPER_SUB_UNICODE_CHARS
        parent.remove(run._element)

    return changed_chars


def _apply_chem_marks_to_para_runs(para, marks: list[str | None]) -> int:
    """Split runs minimally and apply per-char vertical alignment marks."""
    if not para.runs:
        return 0

    changed_chars = 0
    runs_snapshot = list(para.runs)
    cursor = 0

    for run in runs_snapshot:
        txt = run.text or ""
        n = len(txt)
        if n == 0:
            continue

        existing = _run_vert_align(run)
        if existing in {"superscript", "subscript"}:
            cursor += n
            continue

        local_marks = marks[cursor: cursor + n]
        cursor += n
        if not any(local_marks):
            continue

        segments: list[tuple[str, str | None]] = []
        seg_start = 0
        current = local_marks[0]
        for i in range(1, n + 1):
            if i == n or local_marks[i] != current:
                seg_text = txt[seg_start:i]
                if seg_text:
                    segments.append((seg_text, current))
                if i < n:
                    seg_start = i
                    current = local_marks[i]

        parent = run._element.getparent()
        if parent is None:
            continue

        insert_at = parent.index(run._element)
        base_rpr = run._element.find(f"{{{_W_NS}}}rPr")
        for seg_text, seg_style in segments:
            new_r = _new_text_run_element(seg_text, base_rpr)
            if seg_style in {"superscript", "subscript"}:
                _set_rpr_vert_align(new_r, seg_style)
                if not _contains_cjk(seg_text):
                    target_font = _resolve_run_ascii_font(new_r)
                    if target_font:
                        _set_run_all_fonts(new_r, target_font)
                changed_chars += len(seg_text)
            parent.insert(insert_at, new_r)
            insert_at += 1
        parent.remove(run._element)

    return changed_chars


def _apply_formula_font_mask_to_para_runs(
    para,
    mask: list[bool],
    *,
    font_name: str | None = None,
) -> int:
    """Split runs and force western font on formula-like token spans."""
    if not para.runs:
        return 0

    changed_chars = 0
    runs_snapshot = list(para.runs)
    cursor = 0

    for run in runs_snapshot:
        txt = run.text or ""
        n = len(txt)
        if n == 0:
            continue

        local_mask = mask[cursor: cursor + n]
        cursor += n
        if not any(local_mask):
            continue

        segments: list[tuple[str, bool]] = []
        seg_start = 0
        current = bool(local_mask[0])
        for i in range(1, n + 1):
            if i == n or bool(local_mask[i]) != current:
                seg_text = txt[seg_start:i]
                if seg_text:
                    segments.append((seg_text, current))
                if i < n:
                    seg_start = i
                    current = bool(local_mask[i])

        parent = run._element.getparent()
        if parent is None:
            continue

        insert_at = parent.index(run._element)
        base_rpr = run._element.find(f"{{{_W_NS}}}rPr")
        for seg_text, need_western_font in segments:
            new_r = _new_text_run_element(seg_text, base_rpr)
            if need_western_font and not _contains_cjk(seg_text):
                target_font = (
                    str(font_name or "").strip()
                    or _resolve_run_ascii_font(new_r)
                    or run.font.name
                    or "Times New Roman"
                )
                if _set_run_all_fonts(new_r, target_font):
                    changed_chars += len(seg_text)
            parent.insert(insert_at, new_r)
            insert_at += 1
        parent.remove(run._element)

    return changed_chars


def _restore_reference_chem_typography(
    para,
    chem_cfg=None,
    chem_runtime: ChemRuntime | None = None,
) -> tuple[int, int]:
    """Recover lost superscript/subscript for chemistry tokens in references."""
    text = "".join((run.text or "") for run in para.runs) if para.runs else (para.text or "")
    if not text:
        return 0, 0

    font_mask = _build_chem_font_mask(text, chem_cfg=chem_cfg, chem_runtime=chem_runtime)
    marks = _build_chem_style_marks(text, chem_cfg=chem_cfg, chem_runtime=chem_runtime)
    if not any(font_mask) and not any(marks):
        return 0, 0

    font_changed = _normalize_super_sub_unicode_font_in_para(para)
    if any(font_mask):
        font_changed += _apply_formula_font_mask_to_para_runs(
            para,
            font_mask,
            font_name=str(getattr(chem_cfg, "western_font", "") or "").strip()
            or None,
        )
    if not any(marks):
        return font_changed, 0
    mark_changed = _apply_chem_marks_to_para_runs(para, marks)
    return font_changed, mark_changed


def build_chem_style_marks(text: str, *, chem_cfg=None) -> list[str | None]:
    return _build_chem_style_marks(text, chem_cfg=chem_cfg)



def build_chem_font_mask(text: str, *, chem_cfg=None) -> list[bool]:
    return _build_chem_font_mask(text, chem_cfg=chem_cfg)


def paragraph_has_chem_typography_evidence(para, *, chem_cfg=None) -> bool:
    text = (
        "".join((run.text or "") for run in para.runs)
        if para.runs
        else (para.text or "")
    )
    if not text:
        return False
    return bool(
        any(_build_chem_font_mask(text, chem_cfg=chem_cfg))
        or any(_build_chem_style_marks(text, chem_cfg=chem_cfg))
    )


def normalize_explicit_run_font_hints(doc: Document) -> dict[str, int]:
    """Remove stale East-Asia hints when runs already define explicit fonts."""
    body_count = _normalize_explicit_run_font_hints(doc)
    related = _normalize_related_story_part_font_hints(doc)
    return {
        "body": int(body_count),
        "related_parts": int(sum(related.values())),
        "total": int(body_count + sum(related.values())),
    }



def apply_chem_typography_to_paragraph(para, *, chem_cfg=None) -> tuple[int, int]:
    """Apply chemistry font + super/subscript recovery to a paragraph."""
    text = "".join((run.text or "") for run in para.runs) if para.runs else (para.text or "")
    if not text:
        return 0, 0

    font_mask = _build_chem_font_mask(text, chem_cfg=chem_cfg)
    marks = _build_chem_style_marks(text, chem_cfg=chem_cfg)
    if not any(font_mask) and not any(marks):
        return 0, 0

    font_changed = _normalize_super_sub_unicode_font_in_para(para)
    if any(font_mask):
        font_changed += _apply_formula_font_mask_to_para_runs(
            para,
            font_mask,
            font_name=str(getattr(chem_cfg, "western_font", "") or "").strip()
            or None,
        )
    if not any(marks):
        return font_changed, 0
    mark_changed = _apply_chem_marks_to_para_runs(para, marks)
    return font_changed, mark_changed
