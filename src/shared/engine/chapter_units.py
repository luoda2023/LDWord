"""Canonical single source for the Chinese chapter-unit convention.

One list of top-level unit words drives BOTH the authoring prompt directive
(so the AI names only recognizer-supported units) and the recognition tests
(so the four recognition points are exercised against the exact same set).  If
the two were maintained separately, tests could pass while the prompt quietly
dropped a unit (单元/部分/卷 were once trimmed) and AI output would no longer
round-trip through the recognizer.

Only this module should hard-code the unit set.  Consumers import
``TOP_LEVEL_UNITS`` / ``render_chapter_units_directive`` / the example heading
lists rather than re-typing the words.
"""

from __future__ import annotations

# Top-level chapter units (H1 / split boundaries), in directive order.
# “部分” is matched before the single-character “部”, “单元” before any single
# character, so the recognizer keeps these exact two-letter words.
TOP_LEVEL_UNITS: tuple[str, ...] = ("单元", "部分", "章", "篇", "部", "卷", "分")

# 章内小节单位（H2）
SECTION_UNIT = "节"


def render_chapter_units_directive(
    units: tuple[str, ...] = TOP_LEVEL_UNITS,
) -> str:
    """Render the prose the authoring prompts embed for chapter naming.

    The text is derived from *units* so it can never drift from the canonical
    set — e.g. it always lists 第X单元/第X部分/第X卷 etc.  Returns a sentence
    fragment (no trailing newline) callers append after their own lead-in.
    """
    quoted = "“第X" + "”“第X".join(units) + "”"
    bare = "/".join(units)
    return (
        "顶级结构一律用"
        + quoted
        + "这些单位词（第X"
        + bare
        + "都会被识别为一级标题/拆分边界），"
        "章内小节才用 x.x 或“第X"
        + SECTION_UNIT
        + "”（识别为二级标题），条目用 1）2）等。"
        "不要把这里列出的单位词之外的其它词（如“回/编/辑/则”或自造单位）当作顶级"
        "章节词去命名，以免与后续排版识别不一致。"
    )


# 规范示例：顶级标题（每单位至少一条，含“章内数字/中文/带空格”写法）。
EXAMPLE_TOP_LEVEL_HEADINGS: tuple[str, ...] = (
    "第一单元 概述",
    "第3部分 专项",
    "第一章 工程概况",
    "第一篇 总论",
    "第6部 专项说明",
    "第5卷 附录",
    # 带空格写法
    "第 二 单元 施工准备",
    "第 三 部分 验收",
    "第 一 章 工程概况",
)

# 规范示例：章内小节（H2），不应被当顶级。
EXAMPLE_SECTION_HEADINGS: tuple[str, ...] = (
    "第1节 项目背景",
    "第 2 节 地形地貌",
    "1.1 引言",
    "2.1.1 数据说明",
)

# 每个顶级单位各配一条代表性标题（含“第X<单位>”式样，数字取首个可识别字），
# 供四处识别点“逐单位各抽一条”做同步校验，也保证与提示里第X<单位>一一对应。
TOP_LEVEL_UNIT_EXAMPLES: tuple[tuple[str, str], ...] = (
    ("单元", "第一单元 概述"),
    ("部分", "第二部分 施工"),
    ("章", "第一章 工程概况"),
    ("篇", "第一篇 总论"),
    ("部", "第6部 专项说明"),
    ("卷", "第5卷 专题资料"),
    ("分", "第4分 专项说明"),
)


__all__ = [
    "SECTION_UNIT",
    "TOP_LEVEL_UNIT_EXAMPLES",
    "TOP_LEVEL_UNITS",
    "EXAMPLE_SECTION_HEADINGS",
    "EXAMPLE_TOP_LEVEL_HEADINGS",
    "render_chapter_units_directive",
]
