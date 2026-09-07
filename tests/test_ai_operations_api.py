# -*- coding: utf-8 -*-
"""AI 操作接口目录（ai_operations_api）与模板逐级标题规矩的回归测试。

锁定的约定：

* 注册表覆盖文档全链路动作，且 gated/executable 声明与执行端
  ``DOCUMENT_ACTION_IDS`` 白名单一致，两边不许漂移。
* ``ai_operations_directive()`` 渲染出可直接驱动/需用户确认两个分区，
  并写明"文档类操作通过 document_action 发起"的调用约定。
* ``AssistantTurnRunner`` 的 system prompt 注入操作目录。
* ``typesetting_directives_from_library_template`` 把模板的 heading1–4
  字体/字号逐级报给 AI（预设规矩：AI 边写边按模板排版）。
* 模板缺显式 headingN 时从通用 heading 派生字号递减链兜底。
* builtin 模板库 14 个模板全部带 heading1–4（工程/公文/论文等行业惯例）。
"""
from __future__ import annotations

import pytest

from src.assistant.application.ai_operations_api import (
    AI_OPERATIONS,
    AI_OP_EXECUTABLE,
    AI_OP_GATED,
    ai_operations_directive,
)
from src.assistant.application.active_document_continuation import (
    ACTION_CONFIRM_OUTLINE_AND_GENERATE,
    ACTION_PREFLIGHT,
    DOCUMENT_ACTION_IDS,
)
from src.assistant.application.typesetting_templates import (
    typesetting_directives_from_library_template,
)
from src.assistant.runtime.turn_runner import AssistantTurnRunner
from src.config.loader import load_template


def test_registry_covers_core_document_lifecycle():
    for op_id in ("chat", "build_outline", "author_chapters", "compose_word"):
        assert op_id in AI_OPERATIONS, f"missing operation: {op_id}"


def test_registry_matches_execution_whitelist():
    registered = {
        op["path"]
        for op in AI_OPERATIONS.values()
        if op["path"] in DOCUMENT_ACTION_IDS
    }
    # 每个声明为文档动作的 path 必须在执行白名单内。
    assert registered <= DOCUMENT_ACTION_IDS
    # 核心闸门：目录确认这条一条龙入口必须标 gated（AI 不能替代用户确认）；
    # 预检是只读安全动作，标 executable。
    confirm_ops = [
        op
        for op in AI_OPERATIONS.values()
        if op["path"] == ACTION_CONFIRM_OUTLINE_AND_GENERATE
    ]
    assert confirm_ops and confirm_ops[0]["status"] == AI_OP_GATED
    preflight_ops = [
        op for op in AI_OPERATIONS.values() if op["path"] == ACTION_PREFLIGHT
    ]
    assert preflight_ops and preflight_ops[0]["status"] == AI_OP_EXECUTABLE


def test_directive_renders_partitions():
    text = ai_operations_directive()
    assert "【AI 操作接口目录】" in text
    assert "可直接驱动" in text
    assert "需用户确认" in text
    assert "document_action" in text


def test_turn_runner_system_prompt_includes_catalog():
    class _Gateway:
        def cancel(self):  # pragma: no cover - not used here
            pass

    runner = AssistantTurnRunner(_Gateway())
    assert "【AI 操作接口目录】" in runner.system_prompt


def test_library_template_directives_expose_heading_levels():
    text = typesetting_directives_from_library_template(
        "eng_document", mode_id="engineering"
    )
    assert "各级标题" in text
    # 工程惯例：H1 黑体三号、H2 小三、H3 四号。
    assert "黑体 16pt（三号）" in text
    assert "15pt（小三）" in text
    assert "14pt（四号）" in text


def test_official_template_directives_use_gbt_fonts():
    text = typesetting_directives_from_library_template(
        "official_gbt", mode_id="official"
    )
    assert "黑体" in text and "楷体" in text and "仿宋" in text


def test_builtin_templates_all_define_heading_levels():
    import glob

    for path in sorted(glob.glob("config_library/templates/*/*/*.json")):
        template = load_template(path)
        for level in ("heading1", "heading2", "heading3", "heading4"):
            assert level in template.styles, f"{path} missing {level}"


def test_missing_levels_derive_from_generic_heading():
    """构造只有通用 heading 的 payload，验证派生兜底（字号递减、下限 12）。"""
    from src.config.template import StyleConfig

    class _T:
        page_setup = None
        styles = {
            "body": StyleConfig(),
            "heading": StyleConfig(size_pt=15, bold=True),
        }
        heading_model = None
        heading_numbering = None
        table = None
        caption = None
        header_footer = None

    from src.assistant.application import typesetting_templates as tt

    styles = {
        "body": StyleConfig(),
        "heading": StyleConfig(size_pt=15, bold=True),
    }
    resolved = tt._resolve_heading_level_styles(styles, styles["heading"])
    assert [float(s.size_pt) for s in resolved] == [15.0, 14.0, 13.0, 12.0]
    assert resolved[0].bold is True and resolved[1].bold is False
