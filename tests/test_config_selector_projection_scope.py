from __future__ import annotations

from pathlib import Path

from src.config.material_package_library import MaterialPackageLibraryEntry
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


def test_duplicate_material_package_names_are_disambiguated(monkeypatch):
    entries = (
        MaterialPackageLibraryEntry(
            package_id="pkg_aaaaaaaaaaaaaaaaaaaaaaaaaa111111",
            name="223",
            path=Path("first/package.json"),
            mode_id="custom",
            source_type="user",
        ),
        MaterialPackageLibraryEntry(
            package_id="pkg_bbbbbbbbbbbbbbbbbbbbbbbbbb222222",
            name="223",
            path=Path("second/package.json"),
            mode_id="custom",
            source_type="user",
        ),
        MaterialPackageLibraryEntry(
            package_id="pkg_cccccccccccccccccccccccccc333333",
            name="Unique",
            path=Path("third/package.json"),
            mode_id="custom",
            source_type="user",
        ),
    )
    monkeypatch.setattr(
        config_selector_models,
        "list_material_package_entries",
        lambda *, mode_id: entries,
    )

    options = config_selector_models.material_package_selector_options(
        "custom"
    )

    assert [option.label for option in options] == [
        "223 · 111111",
        "223 · 222222",
        "Unique",
    ]
