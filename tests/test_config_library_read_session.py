from __future__ import annotations

from src.config import library


def test_library_read_session_materializes_each_domain_once(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        library,
        "_seed_template_library",
        lambda: calls.append("template"),
    )
    monkeypatch.setattr(
        library,
        "_seed_scene_library",
        lambda: calls.append("scene"),
    )

    with library.library_read_session():
        library.ensure_template_library()
        library.ensure_template_library()
        library.ensure_scene_library()
        library.ensure_scene_library()

    assert calls == ["template", "scene"]


def test_library_read_session_does_not_cache_across_flows(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        library,
        "_seed_template_library",
        lambda: calls.append("template"),
    )

    with library.library_read_session():
        library.ensure_template_library()
    with library.library_read_session():
        library.ensure_template_library()

    assert calls == ["template", "template"]
