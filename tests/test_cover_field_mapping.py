# -*- coding: utf-8 -*-
"""Regression tests for the configurable per-scene cover field mapping.

The export cover prefill used to hard-code which material field feeds the cover
title vs subtitle (title <- document first H1; subtitle <- project + company).
This suite locks the new, per-scene configurable mapping module:

* the mapping module persists per ``scene_id`` overrides through QSettings and
  resolves (title_source, subtitle_source) with the built-in default (which
  reproduces the old behavior);
* ``look_up_field`` recognises the project/company alias sets and skips
  placeholder tokens;
* ``clear_scene_mapping`` restores a scene's defaults.

(The panel-side behavior — ``_cover_context_prefill`` honoring the active
scene's mapping — lives in ``test_cover_field_mapping_panel.py`` so this pure
module suite stands alone.)

Settings writes are isolated to a per-run test namespace so they never touch the
real user preferences.
"""

import os
import uuid

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from src.assistant.ui import cover_field_mapping as cfm  # noqa: E402
from src.assistant.ui.cover_field_mapping import (  # noqa: E402
    SRC_COMPANY,
    SRC_DOCUMENT_CONTEXT,
    SRC_DOCUMENT_FIRST_H1,
    SRC_NONE,
    SRC_PROJECT,
    clear_scene_mapping,
    resolve_sources,
    save_role_source,
    scene_key_for,
)


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch):
    """Point QSettings at a throwaway org/app so tests don't touch real prefs."""
    ns = f"LDWord_test_{uuid.uuid4().hex[:10]}"
    monkeypatch.setattr(cfm, "_QSETTINGS_ORG", ns)
    monkeypatch.setattr(cfm, "_QSETTINGS_APP", ns)


class TestSceneKey:
    def test_key_includes_mode_and_scene(self):
        assert scene_key_for("official", "bid_001") == "official::bid_001"

    def test_key_differs_by_scene_in_same_mode(self):
        assert scene_key_for("official", "a") != scene_key_for("official", "b")

    def test_key_mode_only_and_default(self):
        assert scene_key_for("official", "") == "official::"
        assert scene_key_for("", "") == "default::"


class TestResolveAndPersist:
    def test_default_mapping_reproduces_old_behavior(self):
        assert resolve_sources("mode::scene") == (
            SRC_DOCUMENT_FIRST_H1,
            SRC_DOCUMENT_CONTEXT,
        )

    def test_override_title_to_project_subtitle_to_company(self):
        key = "mode::bid"
        save_role_source(key, "cover_title", SRC_PROJECT)
        save_role_source(key, "cover_subtitle", SRC_COMPANY)
        assert resolve_sources(key) == (SRC_PROJECT, SRC_COMPANY)

    def test_per_scene_override_does_not_leak(self):
        save_role_source("mode::bid", "cover_title", SRC_PROJECT)
        save_role_source("mode::bid", "cover_subtitle", SRC_COMPANY)
        # A different scene keeps the defaults.
        assert resolve_sources("mode::other") == (
            SRC_DOCUMENT_FIRST_H1,
            SRC_DOCUMENT_CONTEXT,
        )

    def test_none_is_a_stored_choice_not_a_clear(self):
        key = "mode::scene"
        save_role_source(key, "cover_title", SRC_NONE)
        title_src, subtitle_src = resolve_sources(key)
        assert title_src == SRC_NONE
        assert subtitle_src == SRC_DOCUMENT_CONTEXT

    def test_clear_restores_default(self):
        key = "mode::scene"
        save_role_source(key, "cover_title", SRC_PROJECT)
        save_role_source(key, "cover_subtitle", SRC_COMPANY)
        clear_scene_mapping(key)
        assert resolve_sources(key) == (
            SRC_DOCUMENT_FIRST_H1,
            SRC_DOCUMENT_CONTEXT,
        )

    def test_unknown_value_clears_override(self):
        key = "mode::scene"
        save_role_source(key, "cover_title", SRC_PROJECT)
        save_role_source(key, "cover_title", "bogus_value")
        assert resolve_sources(key)[0] == SRC_DOCUMENT_FIRST_H1


class TestLookUpField:
    def test_project_role_resolves_alias(self):
        values = {"project_name": "智慧园区", "company_name": "某某公司"}
        assert cfm.look_up_field(values, SRC_PROJECT) == "智慧园区"
        assert cfm.look_up_field(values, SRC_COMPANY) == "某某公司"

    def test_chinese_alias_resolves(self):
        values = {"项目名称": "江河工程"}
        assert cfm.look_up_field(values, SRC_PROJECT) == "江河工程"

    def test_placeholder_token_ignored(self):
        values = {"project_name": "{{@text:project_name}}", "company_name": "公司A"}
        assert cfm.look_up_field(values, SRC_PROJECT) == ""
        assert cfm.look_up_field(values, SRC_COMPANY) == "公司A"
