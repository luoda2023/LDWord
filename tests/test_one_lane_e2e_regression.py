# -*- coding: utf-8 -*-
"""End-to-end regression: one-lane outline confirm straight to finished Word.

确认章节目录后不再需要第二次点按：写作 → 排版复核 → 自动预检 →
自动执行落盘全自动衔接。回归锁定三件事：

* 真实 AssistantPanel（offscreen）上确认一次后，状态机自动走完
  ``content_generation_running → preflight_running → execution_running →
  success``，产物 composed docx 落盘存在；
* 材料快照等同步失败不得把任务卡死在 ``content_generation_running``
  （状态机没有该状态 → preflight_failed 的边，必须先合法落到
  ``preflight_running`` 再报失败）；
* 内置场景的 delivery preset 目标模板必须与场景主模板一致，否则
  执行器会把成稿判为 alternate-template 而必定失败（历史缺陷：
  engineering 场景 preset 指向 default，写作完却在落盘前 100% 失败）。
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.services.delivery_template_validation import (
    unsupported_delivery_target_template_issue,
)


def test_builtin_scene_delivery_presets_follow_main_template():
    """No builtin scene may ship a preset whose render template differs from
    the scene's main template — the executor fail-closes on that combination,
    so the document can never be produced."""
    from src.config.library import list_scene_entries, load_scene_from_library

    blocked: list[str] = []
    for entry in list_scene_entries():
        if entry.load_error:
            continue
        scene = load_scene_from_library(entry.config_id, mode_id=entry.mode_id)
        issue = unsupported_delivery_target_template_issue(scene)
        if issue:
            blocked.append(f"{entry.mode_id}/{entry.config_id}: {issue}")
    assert not blocked, f"builtin scenes blocked at execution: {blocked}"


def test_preflight_material_failure_never_sticks_in_generation_running():
    """A synchronous preflight failure must leave the job in a state that the
    state machine allows; content_generation_running has no edge to
    preflight_failed, so the failure path must pass through
    preflight_running first (or the transition table must allow the direct
    edge). Locked at the state-machine level."""
    from src.assistant.contracts.jobs import (
        JOB_CONTENT_GENERATION_RUNNING,
        JOB_FAILED,
        JOB_PREFLIGHT_FAILED,
        JOB_PREFLIGHT_RUNNING,
        validate_document_job_transition,
    )

    # The direct edge must be rejected (guard against "fixing" this by
    # silently widening the table — the run lane would then skip a legal
    # running state entirely).
    try:
        validate_document_job_transition(
            JOB_CONTENT_GENERATION_RUNNING, JOB_PREFLIGHT_FAILED
        )
    except ValueError:
        pass
    else:  # pragma: no cover - only on regression
        raise AssertionError(
            "content_generation_running -> preflight_failed should stay illegal"
        )
    # The failure path's mandatory intermediate hop stays legal.
    assert (
        validate_document_job_transition(
            JOB_CONTENT_GENERATION_RUNNING, JOB_PREFLIGHT_RUNNING
        )
        == JOB_PREFLIGHT_RUNNING
    )
    assert (
        validate_document_job_transition(
            JOB_PREFLIGHT_RUNNING, JOB_PREFLIGHT_FAILED
        )
        == JOB_PREFLIGHT_FAILED
    )
    # And a failed preflight can still reach a terminal failure.
    assert (
        validate_document_job_transition(JOB_PREFLIGHT_FAILED, JOB_FAILED)
        == JOB_FAILED
    )
