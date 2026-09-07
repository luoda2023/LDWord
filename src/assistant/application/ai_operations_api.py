# -*- coding: utf-8 -*-
"""AI 操作 API 注册表 — 软件每个功能都为 AI 预留的操作接口声明。

单一权威来源（single source of truth）：

* ``AI_OPERATIONS`` 声明软件内 AI 可以驱动的每一个功能：名称、参数、
  触达路径与当前状态（executable=直达 / gated=需用户确认 / planned=规划中）。
* ``ai_operations_directive()`` 把注册表渲染成注入 AI system prompt 的
  操作目录，让 AI 清楚"我能调用什么、怎么调用、哪些要用户点头"。
* ``DOCUMENT_ACTION_IDS``（active_document_continuation.py）是执行端的
  白名单：AI 建议的任何 document_action 都必须落在这个集合内，payload
  再经 action registry 校验。新增可执行功能时两边同步登记。

设计约定：这里只做"声明 + 提示词投影"，不放执行逻辑；执行仍走各
既有 mixin / continuation 校验器，保证 AI 永远不能绕过用户确认闸门。
"""
from __future__ import annotations

from src.assistant.application.active_document_continuation import (
    ACTION_APPROVE_EXECUTE,
    ACTION_CONFIRM_OUTLINE_AND_GENERATE,
    ACTION_GENERATE_CONTENT_DRAFT,
    ACTION_OPEN_ARTIFACT,
    ACTION_OPEN_CONTENT_DRAFT,
    ACTION_OPEN_OUTPUT_FOLDER,
    ACTION_PREFLIGHT,
    ACTION_REVISE_CONTENT_DRAFT,
    DOCUMENT_ACTION_IDS,
)

# 状态常量与 capability_registry 的三态保持同义。
AI_OP_EXECUTABLE = "executable"   # AI 可直接驱动（内部仍受状态机约束）
AI_OP_GATED = "gated"             # AI 可发起，执行前必须用户确认
AI_OP_PLANNED = "planned"         # 规划中的能力，AI 只能告知用户

# 每项：id → (名称, 参数说明, 状态, 触达路径)。顺序即 prompt 呈现顺序。
AI_OPERATIONS: dict[str, dict[str, str]] = {
    # ---- 对话与规划 -------------------------------------------------
    "chat": {
        "name": "对话交流",
        "params": "自然语言消息",
        "status": AI_OP_EXECUTABLE,
        "path": "assistant_panel._submit_message → provider turn",
    },
    "build_outline": {
        "name": "生成章节目录",
        "params": "项目描述（自然语言，可附参考文档）",
        "status": AI_OP_EXECUTABLE,
        "path": "document_workflow_mixin._start_content_generation → outline_confirm 卡",
    },
    "edit_outline_inline": {
        "name": "编辑章节目录",
        "params": "editable_outline=[标题…]",
        "status": AI_OP_EXECUTABLE,
        "path": "interaction_card 内嵌目录编辑器 → payload.editable_outline",
    },
    "author_chapters": {
        "name": "逐章流式写作",
        "params": "章节标题清单（编辑后目录）",
        "status": AI_OP_EXECUTABLE,
        "path": "content_generation_service → marktext_bridge.append_delta",
    },
    "revise_draft": {
        "name": "重写/润色章节",
        "params": "chapter_index 或自然语言润色要求",
        "status": AI_OP_EXECUTABLE,
        "path": "document_workflow_mixin._resolve_content_revision",
    },
    # ---- 排版与交付 -------------------------------------------------
    "apply_typesetting_template": {
        "name": "套用排版模板",
        "params": "template_id（config_library 模板）",
        "status": AI_OP_EXECUTABLE,
        "path": "capability_registry.TASK_OPERATION_TRANSFORM → template_overrides",
    },
    "reconcile_typesetting": {
        "name": "排版复核校准",
        "params": "template_id（按模板重排标题编号、修表格）",
        "status": AI_OP_EXECUTABLE,
        "path": "typesetting_reconcile.reconcile_document → reconcile_report",
    },
    "compose_word": {
        "name": "生成 Word 文档",
        "params": "无（走一条龙）或 plan 引用",
        "status": AI_OP_GATED,
        "path": ACTION_CONFIRM_OUTLINE_AND_GENERATE,
    },
    "preflight": {
        "name": "导出前预检",
        "params": "无",
        "status": AI_OP_EXECUTABLE,
        "path": ACTION_PREFLIGHT,
    },
    "approve_execute": {
        "name": "批准落盘执行",
        "params": "无（覆盖已有文件时必须用户确认）",
        "status": AI_OP_GATED,
        "path": ACTION_APPROVE_EXECUTE,
    },
    # ---- 文件与视图 -------------------------------------------------
    "open_artifact": {
        "name": "打开成品文档",
        "params": "无",
        "status": AI_OP_EXECUTABLE,
        "path": ACTION_OPEN_ARTIFACT,
    },
    "open_content_draft": {
        "name": "打开草稿文件",
        "params": "无",
        "status": AI_OP_EXECUTABLE,
        "path": ACTION_OPEN_CONTENT_DRAFT,
    },
    "open_output_folder": {
        "name": "打开输出文件夹",
        "params": "无",
        "status": AI_OP_EXECUTABLE,
        "path": ACTION_OPEN_OUTPUT_FOLDER,
    },
    "generate_content_draft": {
        "name": "仅生成草稿（不落盘 Word）",
        "params": "无",
        "status": AI_OP_EXECUTABLE,
        "path": ACTION_GENERATE_CONTENT_DRAFT,
    },
    "revise_content_draft": {
        "name": "修订草稿后重出",
        "params": "修订说明",
        "status": AI_OP_EXECUTABLE,
        "path": ACTION_REVISE_CONTENT_DRAFT,
    },
}

# 执行白名单一致性：注册表内 gated/executable 的文档动作必须都在
# DOCUMENT_ACTION_IDS 内，防止两边漂移（启动时由单测断言）。
_REGISTERED_DOCUMENT_ACTIONS = frozenset(
    op["path"]
    for op in AI_OPERATIONS.values()
    if op["path"] in DOCUMENT_ACTION_IDS
)


def ai_operations_directive() -> str:
    """Render the operation registry as the AI-facing capability catalog."""

    lines: list[str] = ["【AI 操作接口目录】软件的每个功能都为 AI 预留了操作接口，",]
    lines.append("你（AI）可以按下列方式驱动软件；标注「需用户确认」的动作")
    lines.append("必须先征得用户同意，不得代替用户做破坏性决定。")
    executed = [
        (key, op)
        for key, op in AI_OPERATIONS.items()
        if op["status"] == AI_OP_EXECUTABLE
    ]
    gated = [
        (key, op)
        for key, op in AI_OPERATIONS.items()
        if op["status"] == AI_OP_GATED
    ]
    planned = [
        (key, op)
        for key, op in AI_OPERATIONS.items()
        if op["status"] == AI_OP_PLANNED
    ]
    if executed:
        lines.append("可直接驱动：" + "；".join(f"{op['name']}（{key}）" for key, op in executed) + "。")
    if gated:
        lines.append("需用户确认：" + "；".join(f"{op['name']}（{key}）" for key, op in gated) + "。")
    if planned:
        lines.append("规划中（只能告知用户，不可假装已执行）：" + "；".join(f"{op['name']}（{key}）" for key, op in planned) + "。")
    lines.append(
        "调用约定：文档类操作通过类型化动作建议（document_action）发起，"
        "由本地状态机校验执行；写作时遵循【本次排版模板要求】的标题、字体、"
        "编号与表格规矩，保证边写边按模板排版。"
    )
    return "\n".join(lines)


__all__ = [
    "AI_OPERATIONS",
    "AI_OP_EXECUTABLE",
    "AI_OP_GATED",
    "AI_OP_PLANNED",
    "ai_operations_directive",
]
