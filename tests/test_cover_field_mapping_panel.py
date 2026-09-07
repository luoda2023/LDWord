# -*- coding: utf-8 -*-
"""Panel-side integration tests for the per-scene cover field mapping.

These exercise ``_cover_context_prefill`` on a real ``AssistantPanel`` host and
therefore depend on the cover/export wiring inside ``assistant_panel.py``.  They
are kept separate from the pure-module tests in ``test_cover_field_mapping.py``
so the mapping module and its pure logic can stand alone.
"""

import os
import uuid

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from src.assistant.ui import cover_field_mapping as cfm  # noqa: E402
from src.assistant.ui.cover_field_mapping import (  # noqa: E402
    SRC_COMPANY,
    SRC_DOCUMENT_CONTEXT,
    SRC_NONE,
    SRC_PROJECT,
    save_role_source,
    scene_key_for,
)


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch):
    """Point QSettings at a throwaway org/app so tests don't touch real prefs."""
    ns = f"LDWord_test_{uuid.uuid4().hex[:10]}"
    monkeypatch.setattr(cfm, "_QSETTINGS_ORG", ns)
    monkeypatch.setattr(cfm, "_QSETTINGS_APP", ns)


from src.assistant.ui.assistant_panel import AssistantPanel  # noqa: E402


class _Bridge:
    def __init__(self, mode_id="official", scene_id="bid_001"):
        self._mode = mode_id
        self._scene = scene_id

    def current_work_mode_id(self):
        return self._mode

    def current_scene_id(self):
        return self._scene

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


def _make_host(bridge=None):
    host = AssistantPanel.__new__(AssistantPanel)
    host.bridge = bridge or _Bridge()
    host._active_session = None
    host._workbench_source_path = ""
    host._turn_material_snapshots = {}
    host._plan_material_snapshots = {}
    host._best_cover_material_snapshot = lambda: _PackageSnapshot()
    return host


class TestPanelPrefillSceneAware:
    def test_default_still_puts_entities_in_subtitle(self):
        host = _make_host()
        title, subtitle, _date = host._cover_context_prefill(
            markdown="# 某某园区可研报告\n\n正文"
        )
        assert title == "某某园区可研报告"
        assert "智慧园区建设项目" in subtitle
        assert "某某工程咨询有限公司" in subtitle

    def test_project_feeds_title_when_scene_maps_it(self):
        host = _make_host()
        key = scene_key_for("official", "bid_001")
        save_role_source(key, "cover_title", SRC_PROJECT)
        save_role_source(key, "cover_subtitle", SRC_COMPANY)
        title, subtitle, _date = host._cover_context_prefill(
            markdown="# 某某园区可研报告\n\n正文"
        )
        # 项目名→封面标题：即使文档有 H1，映射要求标题取自项目名。
        assert title == "智慧园区建设项目"
        # 公司名→封面副标题：只有公司名，不含项目名。
        assert subtitle == "某某工程咨询有限公司"

    def test_explicit_project_subtitle_is_project_only(self):
        # Regression: an explicit 副标题←项目/工程名 must yield ONLY the project
        # name, never also append the company name.
        host = _make_host()
        key = scene_key_for("official", "bid_001")
        save_role_source(key, "cover_title", SRC_COMPANY)
        save_role_source(key, "cover_subtitle", SRC_PROJECT)
        title, subtitle, _date = host._cover_context_prefill(
            markdown="# 某某园区可研报告\n\n正文"
        )
        assert title == "某某工程咨询有限公司"
        assert subtitle == "智慧园区建设项目"

    def test_project_title_with_default_subtitle_no_duplicate(self):
        # When the title is taken from the project and the subtitle keeps its
        # default source, the subtitle must not repeat the same project name.
        host = _make_host()
        key = scene_key_for("official", "bid_001")
        save_role_source(key, "cover_title", SRC_PROJECT)
        save_role_source(key, "cover_subtitle", SRC_DOCUMENT_CONTEXT)
        title, subtitle, _date = host._cover_context_prefill(
            markdown="# 某某园区可研报告\n\n正文"
        )
        assert title == "智慧园区建设项目"
        assert subtitle == "某某工程咨询有限公司"

    def test_no_h1_default_title_takes_project_over_filename(self):
        # Default mapping (no per-scene override).  When the body has no first
        # H1, the main title must prefer the real project name from the material
        # package over the raw doc filename.
        host = _make_host()
        host._workbench_source_path = "C:/tmp/草案.docx"
        title, subtitle, _date = host._cover_context_prefill(markdown="")
        assert title == "智慧园区建设项目"
        # The project is used as the title, so it is not duplicated in the
        # subtitle (only the company name stays there).
        assert "智慧园区建设项目" not in subtitle
        assert subtitle == "某某工程咨询有限公司"

    def test_none_mapping_leaves_title_empty(self):
        host = _make_host()
        key = scene_key_for("official", "bid_001")
        save_role_source(key, "cover_title", SRC_NONE)
        title, _subtitle, _date = host._cover_context_prefill(
            markdown="# 某某园区可研报告\n\n正文"
        )
        assert title == ""

    def test_scene_mapping_does_not_leak_between_scenes(self):
        host_a = _make_host(_Bridge("official", "bid_001"))
        host_b = _make_host(_Bridge("official", "bid_002"))
        key = scene_key_for("official", "bid_001")
        save_role_source(key, "cover_title", SRC_PROJECT)
        # Scene B still defaults to the document first H1.
        title_b, _sub, _date = host_b._cover_context_prefill(
            markdown="# 另一文档标题\n\n正文"
        )
        assert title_b == "另一文档标题"
        title_a, _s2, _d2 = host_a._cover_context_prefill(
            markdown="# 另一文档标题\n\n正文"
        )
        assert title_a == "智慧园区建设项目"
