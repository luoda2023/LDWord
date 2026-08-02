from __future__ import annotations

from src.ui.adapters import config_selector_models


def test_selector_projection_cache_is_limited_to_one_construction_scope(
    monkeypatch,
):
    calls: list[str] = []

    def list_descriptors(*, mode_id: str):
        calls.append(mode_id)
        return (object(),)

    monkeypatch.setattr(
        config_selector_models,
        "list_scene_descriptors",
        list_descriptors,
    )

    @config_selector_models.scoped_selector_projections
    def construct():
        first = config_selector_models.plan_selector_descriptors("custom")
        second = config_selector_models.plan_selector_descriptors("custom")
        assert first is second

    construct()
    construct()

    assert calls == ["custom", "custom"]


def test_selector_projection_reads_are_not_cached_outside_scope(monkeypatch):
    calls: list[str] = []

    def list_descriptors(*, mode_id: str):
        calls.append(mode_id)
        return ()

    monkeypatch.setattr(
        config_selector_models,
        "list_scene_descriptors",
        list_descriptors,
    )

    config_selector_models.plan_selector_descriptors("custom")
    config_selector_models.plan_selector_descriptors("custom")

    assert calls == ["custom", "custom"]
