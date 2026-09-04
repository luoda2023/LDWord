"""Heading-numbering scheme catalog.

Built-in schemes stay read-only and user schemes are stored as JSON files under
``heading_numbering_schemes/``.  The legacy public names (``get_preset_labels``,
``get_preset_bindings`` and ``PRESET_CATALOG``) are intentionally kept so older
panels/tests can keep treating schemes as presets.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, fields
from pathlib import Path
from typing import TypedDict

from src.app_paths import heading_numbering_scheme_data_root
from src.config.template import HeadingLevelBindingConfig


class _PresetEntry(TypedDict):
    label: str
    bindings: dict[str, HeadingLevelBindingConfig]
    max_levels: int
    source: str
    description: str


def _b(**kwargs) -> HeadingLevelBindingConfig:
    """快捷构造。"""
    return HeadingLevelBindingConfig(enabled=True, **kwargs)


USER_SCHEME_DIR = heading_numbering_scheme_data_root()
SUPPORTED_LEVELS = 8
BUILTIN_SOURCE = "builtin"
USER_SOURCE = "user"
_BINDING_FIELD_NAMES = {field.name for field in fields(HeadingLevelBindingConfig)}


def _chain_to_root(level: int) -> str:
    if level <= 1:
        return "current_only"
    return ".".join(["parent"] * (level - 1)) + ".current"


def _disabled_bindings() -> dict[str, HeadingLevelBindingConfig]:
    return {f"heading{i}": HeadingLevelBindingConfig(enabled=False) for i in range(1, SUPPORTED_LEVELS + 1)}


def _with_8_levels(
    bindings: dict[str, HeadingLevelBindingConfig],
    *,
    fallback_kind: str = "local_decimal",
) -> dict[str, HeadingLevelBindingConfig]:
    """Return a complete heading1-heading8 binding map.

    ``fallback_kind`` keeps each scheme's deep-level behavior deliberate instead
    of falling back to the adapter's generic arabic chain for every scheme.
    """
    result = {key: value for key, value in bindings.items()}
    for level in range(1, SUPPORTED_LEVELS + 1):
        key = f"heading{level}"
        if key in result:
            continue
        if fallback_kind == "chain_decimal":
            result[key] = _b(
                display_core_style="arabic",
                reference_core_style="arabic",
                display_template="{chain}" if level > 1 else "{nn}",
                chain=_chain_to_root(level),
                chain_separator=".",
            )
        else:
            result[key] = _b(
                display_core_style="arabic",
                reference_core_style="arabic",
                display_template="{nn}.",
                chain="current_only",
                chain_separator=".",
            )
    return result


# ── 预设定义 ──────────────────────────────────────

PRESET_CATALOG: dict[str, _PresetEntry] = {}


def _register(
    key: str,
    label: str,
    bindings: dict[str, HeadingLevelBindingConfig],
    *,
    max_levels: int = 4,
    description: str = "",
) -> None:
    PRESET_CATALOG[key] = {
        "label": label,
        "bindings": bindings,
        "max_levels": max(1, min(int(max_levels or 4), SUPPORTED_LEVELS)),
        "source": BUILTIN_SOURCE,
        "description": description,
    }


# 论文标准: 第一章 / 1.1 / (一) / a)
_register(
    "thesis_standard",
    "论文标准",
    _with_8_levels(
        {
            "heading1": _b(
                display_core_style="chinese_chapter",
                display_template="第{cn}章",
                reference_core_style="arabic",
                chain="current_only",
            ),
            "heading2": _b(
                display_core_style="arabic",
                reference_core_style="arabic",
                display_template="{chain}",
                chain="parent.current",
                chain_separator=".",
            ),
            "heading3": _b(
                display_core_style="chinese_lower",
                display_template="（{cn}）",
                reference_core_style="chinese_lower",
                chain="current_only",
            ),
            "heading4": _b(
                display_core_style="arabic",
                display_template="{nn})",
                chain="current_only",
            ),
            "heading5": _b(
                display_core_style="arabic",
                display_template="（{nn}）",
                chain="current_only",
            ),
            "heading6": _b(
                display_core_style="circled",
                display_template="{cc}",
                chain="current_only",
            ),
            "heading7": _b(
                display_core_style="alpha_lower",
                display_template="{al})",
                chain="current_only",
            ),
            "heading8": _b(
                display_core_style="alpha_upper",
                display_template="{AL})",
                chain="current_only",
            ),
        }
    ),
    max_levels=4,
    description="论文常用中文章、数字节与局部深层编号。",
)

# 纯数字: 1 / 1.1 / 1.1.1 / 1.1.1.1
_register(
    "arabic_dot",
    "阿拉伯数字",
    {
        f"heading{i}": _b(
            display_core_style="arabic",
            reference_core_style="arabic",
            display_template="{chain}" if i > 1 else "{nn}",
            chain=_chain_to_root(i),
            chain_separator=".",
        )
        for i in range(1, SUPPORTED_LEVELS + 1)
    },
    max_levels=4,
    description="技术文档常用的 1 / 1.1 / 1.1.1 全链式编号。",
)

# 中文章节: 第一章 / 第一节 / 一、 / (一)
_register(
    "cn_chapter",
    "中文章节",
    _with_8_levels(
        {
            "heading1": _b(
                display_template="第{cn}章",
                display_core_style="chinese_lower",
                reference_core_style="arabic",
                chain="current_only",
            ),
            "heading2": _b(
                display_template="第{cn}节",
                display_core_style="chinese_lower",
                reference_core_style="arabic",
                chain="current_only",
            ),
            "heading3": _b(
                display_core_style="chinese_lower",
                display_template="{cn}、",
                chain="current_only",
                title_separator="",
            ),
            "heading4": _b(
                display_core_style="chinese_lower",
                display_template="（{cn}）",
                chain="current_only",
            ),
            "heading5": _b(
                display_core_style="arabic",
                display_template="{nn}.",
                chain="current_only",
            ),
            "heading6": _b(
                display_core_style="arabic",
                display_template="（{nn}）",
                chain="current_only",
            ),
            "heading7": _b(
                display_core_style="circled",
                display_template="{cc}",
                chain="current_only",
            ),
            "heading8": _b(
                display_core_style="alpha_lower",
                display_template="{al})",
                chain="current_only",
            ),
        }
    ),
    max_levels=4,
    description="中文章、节、款式的本地层级编号。",
)

# 罗马编号: Ⅰ / Ⅱ / Ⅲ
_register(
    "roman",
    "罗马编号",
    {
        **{
            f"heading{i}": _b(
                display_core_style="roman_upper" if i == 1 else "arabic",
                reference_core_style="arabic",
                display_template="{RN}" if i == 1 else "{chain}",
                chain="current_only" if i == 1 else _chain_to_root(i),
                chain_separator=".",
            )
            for i in range(1, 5)
        },
        "heading5": _b(display_core_style="alpha_lower", display_template="{al})", chain="current_only"),
        "heading6": _b(display_core_style="alpha_upper", display_template="{AL})", chain="current_only"),
        "heading7": _b(display_core_style="circled", display_template="{cc}", chain="current_only"),
        "heading8": _b(display_core_style="arabic", display_template="{nn})", chain="current_only"),
    },
    max_levels=4,
    description="一级罗马数字，浅层链式数字，深层局部短编号。",
)

# 无编号
_register(
    "none",
    "无编号",
    _disabled_bindings(),
    max_levels=8,
    description="保留标题语义，不添加标题编号。",
)


# ── 公共 API ─────────────────────────────────────

def _coerce_binding(payload: object) -> HeadingLevelBindingConfig:
    if isinstance(payload, HeadingLevelBindingConfig):
        return payload
    if not isinstance(payload, dict):
        return HeadingLevelBindingConfig(enabled=False)
    filtered = {key: value for key, value in payload.items() if key in _BINDING_FIELD_NAMES}
    return HeadingLevelBindingConfig(**filtered)


def _coerce_bindings(payload: object) -> dict[str, HeadingLevelBindingConfig]:
    if not isinstance(payload, dict):
        return _disabled_bindings()
    bindings = {
        str(key): _coerce_binding(value)
        for key, value in payload.items()
        if str(key).startswith("heading")
    }
    return _with_8_levels(bindings, fallback_kind="chain_decimal")


def _safe_scheme_id(label: str) -> str:
    raw = str(label or "").strip().lower()
    safe = re.sub(r"[^a-z0-9_\-\u4e00-\u9fff]+", "_", raw).strip("_")
    return safe or "heading_scheme"


def _normalize_scheme_label(label: str) -> str:
    return re.sub(r"\s+", " ", str(label or "").strip())


def scheme_label_exists(label: str, *, exclude_scheme_id: str | None = None) -> bool:
    normalized = _normalize_scheme_label(label)
    if not normalized:
        return False
    for scheme_id, entry in get_scheme_catalog().items():
        if exclude_scheme_id and scheme_id == exclude_scheme_id:
            continue
        if _normalize_scheme_label(str(entry.get("label") or "")) == normalized:
            return True
    return False


def _user_scheme_path(scheme_id: str) -> Path:
    bare = str(scheme_id or "").strip()
    if bare.startswith("user."):
        bare = bare[5:]
    safe = _safe_scheme_id(bare)
    return USER_SCHEME_DIR / f"user.{safe}.json"


def _load_user_schemes() -> dict[str, _PresetEntry]:
    if not USER_SCHEME_DIR.exists():
        return {}
    schemes: dict[str, _PresetEntry] = {}
    used_labels = {
        _normalize_scheme_label(str(entry.get("label") or ""))
        for entry in PRESET_CATALOG.values()
    }
    for path in sorted(USER_SCHEME_DIR.glob("user.*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        scheme_id = str(payload.get("scheme_id") or path.stem).strip()
        if not scheme_id.startswith("user."):
            scheme_id = f"user.{_safe_scheme_id(scheme_id)}"
        label = str(payload.get("name") or payload.get("label") or path.stem).strip() or path.stem
        normalized_label = _normalize_scheme_label(label)
        if not normalized_label or normalized_label in used_labels:
            continue
        used_labels.add(normalized_label)
        schemes[scheme_id] = {
            "label": label,
            "bindings": _coerce_bindings(payload.get("level_bindings")),
            "max_levels": max(1, min(int(payload.get("max_levels") or 4), SUPPORTED_LEVELS)),
            "source": USER_SOURCE,
            "description": str(payload.get("description") or ""),
        }
    return schemes


def get_scheme_catalog(*, include_user: bool = True) -> dict[str, _PresetEntry]:
    catalog = {key: value for key, value in PRESET_CATALOG.items()}
    if include_user:
        catalog.update(_load_user_schemes())
    return catalog


def get_preset_labels(*, include_user: bool = True) -> list[tuple[str, str]]:
    """返回 [(key, label), ...] 供 UI 下拉使用。"""
    return [(k, v["label"]) for k, v in get_scheme_catalog(include_user=include_user).items()]


def get_preset_bindings(key: str) -> dict[str, HeadingLevelBindingConfig] | None:
    """返回预设的 level_bindings 副本, 不存在则返回 None。"""
    entry = get_scheme_catalog().get(key)
    if entry is None:
        return None
    from copy import deepcopy
    return deepcopy(entry["bindings"])


def get_preset_max_levels(key: str) -> int | None:
    entry = get_scheme_catalog().get(key)
    if entry is None:
        return None
    return int(entry.get("max_levels") or 4)


def get_preset_source(key: str) -> str:
    entry = get_scheme_catalog().get(key)
    if entry is None:
        return ""
    return str(entry.get("source") or "")


def is_user_preset(key: str) -> bool:
    return get_preset_source(key) == USER_SOURCE


def save_user_preset(
    label: str,
    bindings: dict[str, HeadingLevelBindingConfig],
    *,
    max_levels: int = 4,
    scheme_id: str | None = None,
    description: str = "",
) -> str:
    """Save a user heading-numbering scheme and return its scheme id."""
    USER_SCHEME_DIR.mkdir(parents=True, exist_ok=True)
    normalized_label = _normalize_scheme_label(label)
    if scheme_id and is_user_preset(scheme_id):
        target_id = scheme_id
    else:
        if scheme_label_exists(normalized_label):
            raise ValueError("编号方案名称已存在")
        target_id = f"user.{_safe_scheme_id(normalized_label)}"
        existing = get_scheme_catalog()
        suffix = 2
        base_id = target_id
        while target_id in existing:
            target_id = f"{base_id}_{suffix}"
            suffix += 1
    complete_bindings = _coerce_bindings({key: asdict(value) for key, value in bindings.items()})
    payload = {
        "scheme_id": target_id,
        "name": normalized_label or target_id.replace("user.", ""),
        "source": USER_SOURCE,
        "max_levels": max(1, min(int(max_levels or 4), SUPPORTED_LEVELS)),
        "supported_levels": SUPPORTED_LEVELS,
        "description": str(description or ""),
        "level_bindings": {key: asdict(value) for key, value in complete_bindings.items()},
    }
    _user_scheme_path(target_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target_id


def delete_user_preset(key: str) -> bool:
    if not is_user_preset(key):
        return False
    path = _user_scheme_path(key)
    if not path.exists():
        return False
    path.unlink()
    return True
