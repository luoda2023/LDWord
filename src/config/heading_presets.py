"""
heading_presets — 标题编号预设目录

每个预设是一组完整的 level_bindings，可直接应用到 TemplateConfig。
"""

from __future__ import annotations

from typing import TypedDict

from src.config.template import HeadingLevelBindingConfig


class _PresetEntry(TypedDict):
    label: str
    bindings: dict[str, HeadingLevelBindingConfig]


def _b(**kwargs) -> HeadingLevelBindingConfig:
    """快捷构造。"""
    return HeadingLevelBindingConfig(enabled=True, **kwargs)


# ── 预设定义 ──────────────────────────────────────

PRESET_CATALOG: dict[str, _PresetEntry] = {}


def _register(key: str, label: str, bindings: dict[str, HeadingLevelBindingConfig]):
    PRESET_CATALOG[key] = {"label": label, "bindings": bindings}


# 论文标准: 第一章 / 1.1 / (一) / a)
_register("thesis_standard", "论文标准", {
    "heading1": _b(
        display_core_style="chinese_chapter",
        display_template="第{cn}章",
        reference_core_style="arabic",
        chain="current_only",
    ),
    "heading2": _b(
        display_core_style="arabic",
        reference_core_style="arabic",
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
})

# 纯数字: 1 / 1.1 / 1.1.1 / 1.1.1.1
_register("arabic_dot", "阿拉伯数字", {
    f"heading{i}": _b(
        display_core_style="arabic",
        reference_core_style="arabic",
        chain=".".join(["parent"] * (i - 1)) + (".current" if i > 1 else "current_only"),
        chain_separator=".",
    )
    for i in range(1, 5)
})

# 中文章节: 第一章 / 第一节 / 一、 / (一)
_register("cn_chapter", "中文章节", {
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
})

# 罗马编号: Ⅰ / Ⅱ / Ⅲ
_register("roman", "罗马编号", {
    f"heading{i}": _b(
        display_core_style="roman_upper" if i == 1 else "arabic",
        reference_core_style="arabic",
        chain="current_only" if i == 1 else ".".join(["parent"] * (i - 1)) + ".current",
        chain_separator=".",
    )
    for i in range(1, 5)
})

# 无编号
_register("none", "无编号", {
    f"heading{i}": HeadingLevelBindingConfig(enabled=False)
    for i in range(1, 9)
})


# ── 公共 API ─────────────────────────────────────

def get_preset_labels() -> list[tuple[str, str]]:
    """返回 [(key, label), ...] 供 UI 下拉使用。"""
    return [(k, v["label"]) for k, v in PRESET_CATALOG.items()]


def get_preset_bindings(key: str) -> dict[str, HeadingLevelBindingConfig] | None:
    """返回预设的 level_bindings 副本, 不存在则返回 None。"""
    entry = PRESET_CATALOG.get(key)
    if entry is None:
        return None
    from copy import deepcopy
    return deepcopy(entry["bindings"])
