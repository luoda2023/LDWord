# -*- coding: utf-8 -*-
"""Regression tests for the post-generation typesetting reconcile pass.

逐章写作完成后，组装 DOCX 前自动运行一轮排版复核校准：
标题/表格按模板规则统一刷一遍，差异以报告形式回传 UI 提示。

Contract pinned here:

  * Heading numbering is re-rendered from the template's own level bindings
    (第X章 / 1.1 / （一）…), counters continue across chapters and reset for
    deeper levels; wording after the number is never touched.
  * Markdown tables gain a missing separator row; ragged rows are padded or
    truncated to the header width.
  * The pass is idempotent: a second run must not change anything.
  * Unresolvable templates and empty drafts yield an empty report (never
    raise), so the generation pipeline can call it unconditionally.
  * Page-number plan is reported informationally (owned by the DOCX composer).
"""

import pytest

from src.assistant.application.typesetting_reconcile import (
    reconcile_generated_markdown,
)

_TEMPLATE = ("default", "custom")  # 第{cn}章 / {chain} / （{cn}） / {nn})


def _reconcile(markdown: str):
    return reconcile_generated_markdown(
        markdown, template_id=_TEMPLATE[0], mode_id=_TEMPLATE[1]
    )


def test_heading_numbering_rendered_from_template():
    report = _reconcile(
        "# 概述\n## 背景\n## 目标\n### 现状\n# 施工部署\n## 机构\n"
    )
    assert report.changed
    assert report.corrected_markdown.splitlines() == [
        "# 第一章　概述",
        "## 1.1　背景",
        "## 1.2　目标",
        "### （一）　现状",
        "# 第二章　施工部署",
        "## 2.1　机构",
    ]
    codes = {d.code for d in report.deviations}
    assert "heading_numbering_normalized" in codes
    assert report.fix_count >= 1


def test_numbering_preserves_title_wording():
    report = _reconcile("# 项目概况及编制依据\n## 编制依据\n")
    assert report.corrected_markdown.startswith("# 第一章　项目概况及编制依据")
    assert "编制依据" in report.corrected_markdown


def test_table_separator_and_ragged_rows_fixed():
    report = _reconcile("| A | B |\n| 1 | 2 | 3 |\n")
    lines = report.corrected_markdown.splitlines()
    assert "| --- | --- |" in lines
    assert "|  1  |  2  |" in lines  # truncated to header width
    codes = {d.code for d in report.deviations}
    assert "table_separator_missing" in codes
    assert "table_row_ragged" in codes


def test_reconcile_is_idempotent():
    first = _reconcile(
        "# 概述\n| A | B |\n| 1 | 2 | 3 |\n## 背景\n"
    )
    assert first.changed
    second = _reconcile(first.corrected_markdown)
    assert not second.changed
    assert second.corrected_markdown == first.corrected_markdown


def test_unresolvable_template_returns_empty_report():
    report = reconcile_generated_markdown(
        "# 任意\n", template_id="no_such_template", mode_id="custom"
    )
    assert report.template_id == "no_such_template"
    assert report.deviations == ()
    assert not report.changed


def test_empty_draft_returns_empty_report():
    report = _reconcile("   \n  ")
    assert report.deviations == ()
    assert not report.changed


def test_page_number_plan_reported_informationally():
    report = _reconcile("# 概述\n")
    page_notes = [
        d for d in report.deviations if d.code == "page_number_plan_applied"
    ]
    assert page_notes, "page-number plan must be surfaced in the report"
    assert page_notes[0].severity == "info"
    assert not page_notes[0].auto_fixed


def test_remote_image_warns_and_depth_warns():
    report = _reconcile(
        "##### 五级\n\n![x](https://example.com/a.png)\n"
    )
    codes = {d.code for d in report.deviations}
    assert "remote_image_reference" in codes
    assert "heading_depth_exceeds_template" in codes
    assert report.warn_count >= 2


def test_checked_list_covers_all_rules():
    report = _reconcile("# 概述\n")
    for name in (
        "heading_depth",
        "heading_numbering",
        "table_structure",
        "caption_prefix",
        "figure_placeholder",
        "page_number_plan",
    ):
        assert name in report.checked
