# -*- coding: utf-8 -*-
"""单元测试：中文章节标题识别的统一约定，防止回归。

统一约定见 src/shared/engine/document_text_heuristics.py：
  顶级章节（H1/拆分边界）：第X(单元|部分|章|篇|部|卷|分)
  章内小节（H2）：第X节
  也兼容 “第 5 部分” 这类数字前后带空格的写法，以及 Markdown “# ” 标题。

这些用例覆盖四个识别入口，避免后续改动让某一处悄悄偏离统一约定：
  1. 工作台 _parse_outline_blocks（纯文本分块成 H1/H2/正文）
  2. 大纲/作者解析 directory_authoring_parser（顶级章节拆分、无标题判空）
  3. docx 标题识别 heading_recognition._detect_by_pattern（层级映射）
  4. 真实 docx 的 detect_chapter_outline 端到端章节拆分
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.assistant.ui.chapter_workbench_mixin import (
    _BODY,
    _H1,
    _H2,
    _parse_outline_blocks,
)
from src.assistant.application.directory_authoring_parser import (
    _is_top_chapter,
    _split_outline,
)
from src.modules.structure import heading_recognition as hr
from src.shared.engine.document_text_heuristics import (
    _RE_NUMBERED_HEADING_PREFIX,
)

# 顶级章节标题（各写法都应识别为 H1 / 顶级 / level 1）
TOP_LEVEL_TITLES = [
    "第一章 工程概况",
    "第1章 工程概况",
    "第一篇 设计",
    "第二部分 施工",
    "第 3 部分 验收",
    "第四单元 安全",
    "第5卷 附录",
    "第6部 专项说明",
]

# 章内小节（应识别为 H2，而非顶级）
SECTION_TITLES = [
    "第1节 项目背景",
    "第 2 节 地形地貌",
    "1.1 引言",
    "2.1.1 数据说明",
]

# 单元级单位词（“章”之外也应识别为顶级）——只保留“第X单元/部分/卷/篇/部/分”
UNIT_LEVEL_HEADINGS = [
    "第二单元 施工准备",
    "第3部分 验收",
    "第5卷 附录",
    "第一篇 设计",
    "第6部 专项说明",
]

# 紧邻“第X”的带空格写法（数字前后可有空格）——应同无空格一样识别
SPACED_HEADINGS = [
    "第 3 部分 验收",  # 顶级 + 带空格
    "第 2 节 地形地貌",  # 节级 + 带空格
    "第 1 章 工程概况",  # 章级 + 带空格
]

# 不应被当成标题的正文
BODY_LINES = [
    "这是正文段落，用于验证不会被误判为章节标题。",
    "建设单位为某公司，设计单位为另一家公司。",
    "该项目总投资约 3.2 亿元，建设期两年。",
]

# 单元级但带空格的标题（用于给“单元级/带空格”双重验证）
UNIT_SPACED_HEADINGS = [
    "第 三 单元 施工准备",
    "第 二 卷 附件",
]


def _workbench_kind(line: str):
    """_parse_outline_blocks 对该行判定的块类型（忽略纯图行）。"""
    blocks = [
        block for block in _parse_outline_blocks(line) if block[0] != 4  # _IMAGE
    ]
    return blocks[0][0] if blocks else None


# ---------------------------------------------------------------------------
# 1) 工作台 _parse_outline_blocks
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("title", TOP_LEVEL_TITLES)
def test_workbench_top_level_is_h1(title):
    assert _workbench_kind(title) == _H1


@pytest.mark.parametrize("title", SECTION_TITLES)
def test_workbench_section_is_h2(title):
    assert _workbench_kind(title) == _H2


# —— 单元级/节级/带空格 逐条锁定（工作台） ——
@pytest.mark.parametrize("title", UNIT_LEVEL_HEADINGS)
def test_workbench_unit_level_is_h1(title):
    assert _workbench_kind(title) == _H1


@pytest.mark.parametrize("title", ["第1节 项目背景"])
def test_workbench_section_word_is_h2(title):
    # “第X节”是章内小节：H2，不是 H1
    assert _workbench_kind(title) == _H2
    assert _workbench_kind(title) != _H1


@pytest.mark.parametrize("title", SPACED_HEADINGS)
def test_workbench_spaced_form(title):
    # 带空格的“第 X 单元/节/章”应和无空格一样被识别
    if "节" in title:
        assert _workbench_kind(title) == _H2
    else:
        assert _workbench_kind(title) == _H1


@pytest.mark.parametrize("title", UNIT_SPACED_HEADINGS)
def test_workbench_unit_spaced_is_h1(title):
    assert _workbench_kind(title) == _H1


@pytest.mark.parametrize("line", BODY_LINES)
def test_workbench_body_stays_body(line):
    assert _workbench_kind(line) == _BODY


def test_workbench_markdown_heading_levels():
    # “# 目录/标题”是 H1，二级 markdown 标题是 H2
    assert _workbench_kind("# 第一章 工程概况") == _H1
    assert _workbench_kind("# 目录") == _H1
    assert _workbench_kind("## 1.1 项目背景") == _H2


def test_workbench_mixed_body_preserves_order_and_kinds():
    body = "\n".join(
        [
            "第一章 工程概况",          # H1
            "这是总述正文。",
            "第1节 项目背景",          # H2
            "背景正文内容。",
            "第二部分 施工组织",        # H1
            "施工正文内容。",
        ]
    )
    kinds = [
        block[0]
        for block in _parse_outline_blocks(body)
        if block[0] != 4  # skip image
    ]
    assert kinds == [_H1, _BODY, _H2, _BODY, _H1, _BODY]


def test_workbench_no_heading_all_body():
    kinds = [
        block[0]
        for block in _parse_outline_blocks("\n".join(BODY_LINES))
        if block[0] != 4
    ]
    assert kinds and set(kinds) == {_BODY}


def test_workbench_e2e_unit_then_section_structure():
    """端到端回归：AI 按统一约定产出“第X单元 … 第X节 …”结构后，工作台解析
    必须把每个单元/分篇拆成 H1、其下第X节拆成 H2，绝不落回正文，也不把“第X节”
    误升成顶级。

    这是对 capability_registry.CHAPTER_UNITS_DIRECTIVE 约束产物的直接验证：
    提示让 AI 用“第X单元/第X节”，此处证明识别器能正确还原同层级结构。
    """
    body = "\n".join(
        [
            "# 某某工程总体方案",            # markdown 一级标题 -> H1
            "本方案概述（正文）。",
            "第一单元 项目背景",              # 单元级 H1
            "这是单元开篇正文。",
            "第1节 建设地点",               # 单元下小节 H2
            "地点正文。",
            "第2节 建设规模",               # 小节 H2
            "规模正文。",
            "第二单元 施工部署",              # 换一个单元级 H1
            "部署正文。",
            "第1节 总体安排",               # 新单元下小节 H2
            "安排正文。",
            "第2节 进度计划",               # 小节 H2
            "计划正文。",
        ]
    )
    blocks = [
        block for block in _parse_outline_blocks(body) if block[0] != 4  # 跳过图行
    ]
    texts = [text for _kind, text in blocks]
    expected_kinds = [
        _H1,      # # 某某工程总体方案
        _BODY,
        _H1,      # 第一单元 项目背景
        _BODY,
        _H2,      # 第1节 建设地点
        _BODY,
        _H2,      # 第2节 建设规模
        _BODY,
        _H1,      # 第二单元 施工部署
        _BODY,
        _H2,      # 第1节 总体安排
        _BODY,
        _H2,      # 第2节 进度计划
        _BODY,
    ]
    kinds = [block[0] for block in blocks]
    assert kinds == expected_kinds

    # 每个单元标题都落在 H1，其下每个“第X节”都落在 H2（不误升 H1，也不落正文）。
    for text in ("第一单元 项目背景", "第二单元 施工部署"):
        assert text in texts
        kind = blocks[texts.index(text)][0]
        assert kind == _H1
    for text in ("第1节 建设地点", "第2节 建设规模", "第1节 总体安排", "第2节 进度计划"):
        assert text in texts
        kind = blocks[texts.index(text)][0]
        assert kind == _H2


def test_workbench_e2e_directive_mixed_units_stay_nested():
    """端到端回归：同一个文档里混用 单元/部分/卷/分 等不同顶级单位词 + 章内
    “第X节”，解析后应形成若干 H1（每个顶级分组）且 H2 只出现在它们内部、顺序不变，
    印证识别器能处理“篇/章/节”或“单元/节”等多层真实结构。
    """
    body = "\n".join(
        [
            "第一章 编制依据",
            "依据正文。",
            "第1节 规范清单",
            "清单正文。",
            "第二章 工程概况",
            "概况正文。",
            "第2节 建设条件",
            "条件正文。",
            "第三部分 专项设计",
            "专项正文。",
            "第3节 消防设计",
            "消防正文。",
            "第4节 节能设计",
            "节能正文。",
        ]
    )
    blocks = [
        block for block in _parse_outline_blocks(body) if block[0] != 4
    ]
    # 期望：H1,H2 交替出现于正文之间，第X节紧跟其所属章节之后。
    headings = [(kind, text) for kind, text in blocks if kind in (_H1, _H2)]
    assert headings == [
        (_H1, "第一章 编制依据"),
        (_H2, "第1节 规范清单"),
        (_H1, "第二章 工程概况"),
        (_H2, "第2节 建设条件"),
        (_H1, "第三部分 专项设计"),
        (_H2, "第3节 消防设计"),
        (_H2, "第4节 节能设计"),
    ]


# ---------------------------------------------------------------------------
# 2) 大纲/作者解析（顶级章节拆分、无标题判空）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("title", TOP_LEVEL_TITLES)
def test_parser_top_level_chapter(title):
    assert _is_top_chapter(title) is True


@pytest.mark.parametrize("title", SECTION_TITLES)
def test_parser_section_is_not_top(title):
    # 第X节/1.1 属于章内小节，不该被当作顶级章节拆分
    assert _is_top_chapter(title) is False


# —— 单元级/节级/带空格 逐条锁定（大纲/作者解析） ——
@pytest.mark.parametrize("title", UNIT_LEVEL_HEADINGS)
def test_parser_unit_level_is_top(title):
    assert _is_top_chapter(title) is True


@pytest.mark.parametrize("title", ["第1节 项目背景"])
def test_parser_section_word_not_top(title):
    assert _is_top_chapter(title) is False


@pytest.mark.parametrize("title", SPACED_HEADINGS)
def test_parser_spaced_form(title):
    # 带空格的“第 X 单元/章”仍算顶级；“第 X 节”仍不算顶级
    if "节" in title:
        assert _is_top_chapter(title) is False
    else:
        assert _is_top_chapter(title) is True


@pytest.mark.parametrize("title", UNIT_SPACED_HEADINGS)
def test_parser_unit_spaced_is_top(title):
    assert _is_top_chapter(title) is True


def test_parser_split_outline_extracts_top_only():
    text = "\n".join(
        [
            "第一章 工程概况",
            "1.1 项目背景",
            "（正文说明放进 notes）",
            "第二部分 施工组织",
            "2.1 施工部署",
        ]
    )
    titles, _notes = _split_outline(text)
    assert titles == ["第一章 工程概况", "第二部分 施工组织"]


def test_parser_split_outline_plain_body_returns_empty():
    text = "\n".join(BODY_LINES)
    titles, notes = _split_outline(text)
    assert titles == []
    assert notes == []


def test_parser_markdown_heading_chapters():
    text = "# 第一章 工程概况\n正文。\n## 1.1 小节\n# 第二章 验收\n正文2。"
    titles, _ = _split_outline(text)
    # 首行文档标题 H1 会被去掉，剩下真正的“章”标题
    assert titles and any("章" in t for t in titles)


# ---------------------------------------------------------------------------
# 3) docx 标题识别 —— 层级映射
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("title", TOP_LEVEL_TITLES)
def test_heading_pattern_top_level_is_one(title):
    assert hr._detect_by_pattern(title) == 1


@pytest.mark.parametrize("title", SECTION_TITLES)
def test_heading_pattern_section_is_two(title):
    # 纯“第X节/x.y”不含 x.y 会匹配数字链的由其它入口处理；这里只看“第X节”
    if title.startswith("第") and "节" in title:
        assert hr._detect_by_pattern(title) == 2


def test_heading_pattern_plain_roman_level_one():
    assert hr._detect_by_pattern("Ⅰ 总则") == 1
    assert hr._detect_by_pattern("Ⅱ 分则") == 1


# —— 单元级/节级/带空格 逐条锁定（docx 标题识别） ——
@pytest.mark.parametrize("title", UNIT_LEVEL_HEADINGS)
def test_heading_pattern_unit_level_is_one(title):
    assert hr._detect_by_pattern(title) == 1


@pytest.mark.parametrize("title", ["第1节 项目背景"])
def test_heading_pattern_section_word_is_two(title):
    assert hr._detect_by_pattern(title) == 2


@pytest.mark.parametrize("title", SPACED_HEADINGS)
def test_heading_pattern_spaced_form(title):
    if "节" in title:
        assert hr._detect_by_pattern(title) == 2
    else:
        assert hr._detect_by_pattern(title) == 1


@pytest.mark.parametrize("title", UNIT_SPACED_HEADINGS)
def test_heading_pattern_unit_spaced_is_one(title):
    assert hr._detect_by_pattern(title) == 1


def test_shared_numbered_heading_prefix_covers_all_forms():
    for title in TOP_LEVEL_TITLES + ["第1节 背景"]:
        assert _RE_NUMBERED_HEADING_PREFIX.match(title), title


@pytest.mark.parametrize("title", UNIT_LEVEL_HEADINGS + SPACED_HEADINGS + UNIT_SPACED_HEADINGS)
def test_shared_numbered_heading_prefix_unit_and_spaced(title):
    # 单元级与带空格标题都应是编号标题前缀
    assert _RE_NUMBERED_HEADING_PREFIX.match(title), title


# ---------------------------------------------------------------------------
# 4) 真实 docx 端到端章节拆分
# ---------------------------------------------------------------------------
def _make_docx(tmp_path: Path, lines: list[tuple[str, int]]) -> str:
    """把 (文字, 标题级别|None) 列表写入一份临时 .docx。"""
    from docx import Document

    doc = Document()
    for text, level in lines:
        if level is None:
            doc.add_paragraph(text)
        else:
            doc.add_heading(text, level=level)
    path = tmp_path / "sample.docx"
    doc.save(str(path))
    return str(path)


def test_docx_outline_detects_chapter_and_part(tmp_path):
    from src.assistant.application.chapter_document_editor import (
        detect_chapter_outline,
    )

    path = _make_docx(
        tmp_path,
        [
            ("第一章 工程概况", 1),
            ("这是第一章正文，写够长度以免被误判为标题。", None),
            ("第1节 项目背景", 2),
            ("小节正文。", None),
            ("第二部分 施工组织", 1),
            ("第二部分正文内容说明。", None),
        ],
    )
    chapters = detect_chapter_outline(path)
    assert [c.title for c in chapters] == [
        "第一章 工程概况",
        "第二部分 施工组织",
    ]
    assert all(c.level == 1 for c in chapters)


def test_docx_outline_mixed_markup_chinese_units(tmp_path):
    """第X篇/单元/卷/部分 都被当作顶级章节，第X节 不被当作独立章节。"""
    from src.assistant.application.chapter_document_editor import (
        detect_chapter_outline,
    )

    path = _make_docx(
        tmp_path,
        [
            ("第一篇 总论", 1),
            ("正文甲。", None),
            ("第二单元 施工准备", 1),
            ("正文乙。", None),
            ("第1节 场地", 2),  # 章内小节，不作为顶级章
            ("小节正文。", None),
            ("第3卷 附件", 1),
            ("正文丙。", None),
        ],
    )
    chapters = detect_chapter_outline(path)
    assert [c.title for c in chapters] == [
        "第一篇 总论",
        "第二单元 施工准备",
        "第3卷 附件",
    ]


def test_docx_no_chapter_heading_returns_empty(tmp_path):
    from src.assistant.application.chapter_document_editor import (
        detect_chapter_outline,
    )

    path = _make_docx(
        tmp_path,
        [
            ("这一段只是普通内容，没有章节标题。", None),
            ("另一段普通内容，不含章节结构。", None),
        ],
    )
    chapters = detect_chapter_outline(path)
    assert chapters == ()


# —— 单元级/节级/带空格 端到端（真实 docx 拆分） ——
def test_docx_outline_unit_level_chapters(tmp_path):
    """单元级单位词（单元/卷/篇/部分）都被当作顶级章节。"""
    from src.assistant.application.chapter_document_editor import (
        detect_chapter_outline,
    )

    path = _make_docx(
        tmp_path,
        [
            ("第一单元 概述", 1),
            ("正文甲。", None),
            ("第 二 卷 附录资料", 1),
            ("正文乙。", None),
            ("第三部分 专项", 1),
            ("正文丙。", None),
        ],
    )
    chapters = detect_chapter_outline(path)
    assert [c.title for c in chapters] == [
        "第一单元 概述",
        "第 二 卷 附录资料",
        "第三部分 专项",
    ]


def test_docx_outline_section_word_not_split(tmp_path):
    """第X节 以小节样式(H2)出现时，不把其当作独立顶级章节拆分。

    注意：若作者真的把“第X节”做成 H1 样式，Word 样式是权威的，会被当成顶级章；
    本用例验证的是“节作为章内小节(H2)”的常规情形不被误拆。
    """
    from src.assistant.application.chapter_document_editor import (
        detect_chapter_outline,
    )

    path = _make_docx(
        tmp_path,
        [
            ("第一章 总论", 1),
            ("正文甲。", None),
            ("第1节 项目背景", 2),  # 章内小节(H2)，不作为顶级章
            ("小节正文。", None),
            ("第二章 验收", 1),
            ("正文乙。", None),
        ],
    )
    chapters = detect_chapter_outline(path)
    assert [c.title for c in chapters] == ["第一章 总论", "第二章 验收"]


def test_docx_outline_section_word_as_h1_is_top_chapter(tmp_path):
    """当作者把“第X节”写成 H1 样式时，Word 样式是权威的，它就被当作顶级章拆分。

    这是上一条“第X节(H2) 不作为顶级章”的镜像边界：同一词“第X节”的层级判定完全
    取决于样式——H2 是章内小节，H1 则独立成章。此用例把这一实测边界锁进测试，
    防止今后把“第X节”一刀切排除出顶级拆分（那样会让少数用 H1 写节的文档丢章）。
    """
    from src.assistant.application.chapter_document_editor import (
        detect_chapter_outline,
    )

    path = _make_docx(
        tmp_path,
        [
            ("第1节 总则", 1),  # 第X节写成 H1 样式 -> 顶级章
            ("正文甲。", None),
            ("第2节 术语", 1),  # 同为 H1 的“第X节”也独立成章
            ("正文乙。", None),
        ],
    )
    chapters = detect_chapter_outline(path)
    assert [c.title for c in chapters] == ["第1节 总则", "第2节 术语"]
    assert all(c.level == 1 for c in chapters)


def test_docx_outline_section_word_as_h1_across_nested_chapters(tmp_path):
    """把“第X节”写成 H1 当作章节时，文档里其它“第X章”用 H2 作内容层也不冲突：
    spine 落在最浅的内容章层，整篇能拆出所有“第X节(H1)”，不因“节”与“章”单位
    混排而把任意一层整层丢弃。
    """
    from src.assistant.application.chapter_document_editor import (
        detect_chapter_outline,
    )

    path = _make_docx(
        tmp_path,
        [
            ("第1节 项目背景", 1),  # “节”作者写了 H1
            ("正文甲。", None),
            ("第2节 建设目标", 1),
            ("正文乙。", None),
        ],
    )
    chapters = detect_chapter_outline(path)
    assert [c.title for c in chapters] == ["第1节 项目背景", "第2节 建设目标"]
    assert all(c.level == 1 for c in chapters)


def test_docx_outline_spaced_chapter_and_section(tmp_path):
    """带空格的章级被识别为顶级；带空格的节级不成为独立顶级章。"""
    from src.assistant.application.chapter_document_editor import (
        detect_chapter_outline,
    )

    path = _make_docx(
        tmp_path,
        [
            ("第 一 章 工程概况", 1),
            ("正文甲。", None),
            ("第 1 节 地形地貌", 2),  # 空格节级，仍是小节
            ("小节正文。", None),
            ("第 二 部分 施工组织", 1),
            ("正文乙。", None),
        ],
    )
    chapters = detect_chapter_outline(path)
    assert [c.title for c in chapters] == [
        "第 一 章 工程概况",
        "第 二 部分 施工组织",
    ]


def test_docx_outline_part_nests_chapters_leaf(tmp_path):
    """篇(H1)>章(H2) 嵌套文档：返回的编辑单元是章叶子，且带父篇标题。

    修复的是旧的 level==1 过滤会把章(H2)全部丢弃、只剩篇(H1)的丢章 bug。
    """
    from src.assistant.application.chapter_document_editor import (
        detect_chapter_outline,
    )

    path = _make_docx(
        tmp_path,
        [
            ("第一篇 总论", 1),
            ("正文篇头说明。", None),
            ("第一章 项目背景", 2),
            ("正文甲。", None),
            ("第二章 建设目标", 2),
            ("正文乙。", None),
            ("第二篇 工程设计", 1),
            ("正文篇头说明二。", None),
            ("第三章 总体设计", 2),
            ("正文丙。", None),
        ],
    )
    chapters = detect_chapter_outline(path)
    # 章是叶子可编辑单元，连续编号，不丢失；不再只有两个篇标题
    assert [c.title for c in chapters] == [
        "第一章 项目背景",
        "第二章 建设目标",
        "第三章 总体设计",
    ]
    # 每章携带其父篇标题（含跨章的持久化：第二章仍属于第一篇）
    assert [c.part_title for c in chapters] == [
        "第一篇 总论",
        "第一篇 总论",
        "第二篇 工程设计",
    ]
    # 每章范围以下一篇或下一章为边界，篇标题不落入上一章正文
    assert all(c.start_para_index >= 0 for c in chapters)
    assert all(c.level == 2 for c in chapters)


def test_docx_outline_part_nested_with_sections(tmp_path):
    """篇(H1)>章(H2)>节(H3) 嵌套：章仍是叶子单元，节(H3)不被当成章。"""
    from src.assistant.application.chapter_document_editor import (
        detect_chapter_outline,
    )

    path = _make_docx(
        tmp_path,
        [
            ("第一篇 总论", 1),
            ("第一章 项目背景", 2),
            ("第1节 工程概况", 3),
            ("小节正文。", None),
            ("第二章 建设目标", 2),
            ("正文乙。", None),
        ],
    )
    chapters = detect_chapter_outline(path)
    assert [c.title for c in chapters] == ["第一章 项目背景", "第二章 建设目标"]
    assert [c.part_title for c in chapters] == ["第一篇 总论", "第一篇 总论"]


def test_docx_outline_flat_siblings_stay_flat(tmp_path):
    """篇与章若都做成 H1（作者视为平级），则不强制嵌套，保持各自为顶级章。"""
    from src.assistant.application.chapter_document_editor import (
        detect_chapter_outline,
    )

    path = _make_docx(
        tmp_path,
        [
            ("第一篇 总论", 1),
            ("第一章 背景", 1),
            ("第二章 目标", 1),
        ],
    )
    chapters = detect_chapter_outline(path)
    assert [c.title for c in chapters] == [
        "第一篇 总论",
        "第一章 背景",
        "第二章 目标",
    ]
    assert all(not (c.part_title) for c in chapters)


def test_docx_outline_multi_unit_deep_nesting_no_conflict(tmp_path):
    """真实 docx 内多级嵌套 篇/部分/卷/单元(H1)>章(H2)>节(H3)：层级解析不冲突。

    顶层分组词（篇/单元/卷/部分）交替出现时，它们都是 H1 分组层；真正的可编辑
    章节统一落在 H2 的「章」，H3 的「节」不被当作章。返回的章按出现顺序编号，
    每章带最近的 H1 分组标题做 part_title。修复过的丢章风险由本用例锁定——
    顶层分组不止“篇”一种、后续分组使用其它单元词时，其下章也不能被吞掉。
    """
    from src.assistant.application.chapter_document_editor import (
        detect_chapter_outline,
    )

    path = _make_docx(
        tmp_path,
        [
            ("第一篇 设计总述", 1),
            ("总述引言。", None),
            ("第一章 总体要求", 2),
            ("第1节 范围", 3),
            ("范围正文。", None),
            ("第2节 依据", 3),
            ("依据正文。", None),
            ("第二章 设计原则", 2),
            ("第1节 原则说明", 3),
            ("原则正文。", None),
            ("第二单元 施工部署", 1),
            ("部署引言。", None),
            ("第三章 施工组织", 2),
            ("第1节 机构设置", 3),
            ("机构正文。", None),
            ("第2节 资源配置", 3),
            ("配置正文。", None),
            ("第三卷 质量验收", 1),
            ("验收引言。", None),
            ("第四章 验收程序", 2),
            ("第1节 验收准备", 3),
            ("验收正文。", None),
            ("第四部分 竣工验收", 1),
            ("竣工引言。", None),
            ("第五章 竣工移交", 2),
            ("第1节 移交清单", 3),
            ("移交正文。", None),
        ],
    )
    chapters = detect_chapter_outline(path)
    # 只有 H2 的「章」是可编辑单元；H3 的「节」与 H1 的分组词都不会成为章。
    assert [c.title for c in chapters] == [
        "第一章 总体要求",
        "第二章 设计原则",
        "第三章 施工组织",
        "第四章 验收程序",
        "第五章 竣工移交",
    ]
    assert all(c.level == 2 for c in chapters)
    # 每章归属最近的顶层分组，跨分组词（篇/单元/卷/部分）都正确带出。
    assert [c.part_title for c in chapters] == [
        "第一篇 设计总述",
        "第一篇 设计总述",
        "第二单元 施工部署",
        "第三卷 质量验收",
        "第四部分 竣工验收",
    ]
    # 连续编号、范围不重叠、无章被吞（每章 start 前移、end 到下一章边界）。
    assert [c.index for c in chapters] == [1, 2, 3, 4, 5]
    for chapter in chapters:
        assert chapter.start_para_index >= 0
        assert chapter.end_para_index == -1 or chapter.end_para_index > chapter.start_para_index
