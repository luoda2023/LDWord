# -*- coding: utf-8 -*-
"""Regression tests for the cover preview data shown in the export-confirm box.

The export confirmation dialog now displays a 「封面预览」 panel (when the user
enables 生成封面页) that mirrors the exact cover title / subtitle / date that
would be generated, including the real project name and company name pulled
from the bound material package (the "取自资料包" source annotation).

These tests lock the pure data the preview renders — the same helpers the
dialog calls to fill the editable cover fields and to annotate the source:
* ``_cover_entity_identity`` reads project + company names from the material
  snapshot (package scope, falling back to the material records);
* ``_cover_context_prefill`` puts those names into the subtitle (joined by "·")
  and prefers the document's first level-1 heading as the cover title.

Run headless; these helpers do not touch a QWidget, so they are exercised on a
minimal ``__new__`` host with a stubbed material snapshot and bridge.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.assistant.ui.assistant_panel import AssistantPanel


class _Bridge:
    def current_document_path(self):
        return ""

    def current_material_run_selection(self):
        return None

    def current_work_mode(self):
        return None

    def current_scene(self):
        return None


class _PackageSnapshot:
    package_field_values = {
        "project_name": "智慧园区建设项目",
        "company_name": "某某工程咨询有限公司",
    }
    records = ()


class _RecordSnapshot:
    package_field_values = {}
    records = (
        type(
            "_Record",
            (),
            {"field_values": {"project_name": "江河治理工程", "company_name": "水利设计院"}},
        )(),
    )


def _make_host(snapshot):
    host = AssistantPanel.__new__(AssistantPanel)
    host.bridge = _Bridge()
    host._active_session = None
    host._workbench_source_path = ""
    host._turn_material_snapshots = {}
    host._plan_material_snapshots = {}
    host._best_cover_material_snapshot = lambda: snapshot
    return host


def test_entity_identity_from_package_scope():
    host = _make_host(_PackageSnapshot())
    project, company = host._cover_entity_identity()
    assert project == "智慧园区建设项目"
    assert company == "某某工程咨询有限公司"


def test_entity_identity_falls_back_to_material_records():
    host = _make_host(_RecordSnapshot())
    project, company = host._cover_entity_identity()
    assert project == "江河治理工程"
    assert company == "水利设计院"


def test_entity_identity_empty_without_snapshot():
    host = _make_host(None)
    assert host._cover_entity_identity() == ("", "")


def test_cover_prefill_title_from_first_h1_and_subtitle_has_entities():
    host = _make_host(_PackageSnapshot())
    markdown = "# 某某园区可行性研究报告\n\n## 第一章 项目背景\n正文。"
    title, subtitle, _date = host._cover_context_prefill(markdown=markdown)
    assert title == "某某园区可行性研究报告"
    assert "智慧园区建设项目" in subtitle
    assert "某某工程咨询有限公司" in subtitle


def test_cover_prefill_empty_markdown_takes_project_into_main_title():
    host = _make_host(_PackageSnapshot())
    # When the body has no first-H1, the main title now prefers the real project
    # name from the material package (拼进主标题) over leaving it empty / the
    # raw file stem; the project is then not duplicated in the subtitle.
    title, subtitle, _date = host._cover_context_prefill(markdown="")
    assert title == "智慧园区建设项目"
    assert "智慧园区建设项目" not in subtitle
    assert "某某工程咨询有限公司" in subtitle


def test_cover_prefill_project_title_beats_filename_fallback():
    host = _make_host(_PackageSnapshot())
    host._workbench_source_path = "C:/tmp/草案.docx"
    title, _subtitle, _date = host._cover_context_prefill(markdown="")
    # project_name must win over the doc filename when there is no first-H1.
    assert title == "智慧园区建设项目"
