from __future__ import annotations

import ast
from dataclasses import asdict, fields
import json
from pathlib import Path

import pytest

from src.config.builtin_scenes import (
    create_builtin_scene,
    list_builtin_scene_resources,
)
from src.config.builtin_templates import create_builtin_template
from src.config.loader import ConfigLoadError, load_scene
from src.config.library import get_scene_descriptor
from src.config.scene import SceneWorkspace
from src.config.scene_presets import SCENE_METAS, create_scene


def test_every_builtin_plan_is_complete_and_materializes_losslessly() -> None:
    resources = list_builtin_scene_resources()

    assert {(mode_id, scene_id) for mode_id, scene_id, _path in resources} == {
        ("custom", "custom"),
        ("exam", "exam"),
        ("exam", "exam_quiz"),
        ("exam", "exam_term"),
        ("thesis", "thesis"),
        ("bidding", "bidding"),
        ("official", "official"),
        ("technical", "technical"),
        ("report", "report"),
    }
    for mode_id, scene_id, path in resources:
        payload = json.loads(path.read_text(encoding="utf-8"))
        scene = load_scene(path)

        assert set(payload) == {field.name for field in fields(SceneWorkspace)}
        assert payload == asdict(scene)
        assert scene.mode_id == mode_id
        assert scene.scene_id == scene_id


def test_scene_metadata_is_an_exact_projection_of_canonical_resources() -> None:
    resources = list_builtin_scene_resources()

    assert [meta.scene_id for meta in SCENE_METAS] == [
        scene_id for _mode_id, scene_id, _path in resources
    ]
    for meta, (mode_id, scene_id, path) in zip(SCENE_METAS, resources, strict=True):
        scene = load_scene(path)
        assert meta.scene_id == scene_id
        assert meta.name == scene.name
        assert meta.description == scene.description
        assert meta.template_id == scene.template_id
        assert meta.display_order == scene.display_order
        assert [item.template_id for item in meta.compatible_templates] == (
            scene.compatible_template_ids
        )
        assert all(item.mode_id == mode_id for item in meta.compatible_templates)
        assert all(
            item.name
            == create_builtin_template(
                item.template_id,
                mode_id=mode_id,
            ).name
            for item in meta.compatible_templates
        )


def test_builtin_scene_descriptors_are_exact_canonical_projections() -> None:
    for mode_id, scene_id, path in list_builtin_scene_resources():
        scene = load_scene(path)
        descriptor = get_scene_descriptor(scene_id, mode_id=mode_id)

        assert descriptor is not None
        assert descriptor.name == scene.name
        assert descriptor.description == scene.description
        assert descriptor.template_id == scene.template_id
        assert descriptor.compatible_template_ids == tuple(
            scene.compatible_template_ids
        )
        assert descriptor.display_order == scene.display_order


def test_builtin_scene_display_orders_are_unique_and_follow_resource_order() -> None:
    scenes = [
        load_scene(path)
        for _mode_id, _scene_id, path in list_builtin_scene_resources()
    ]
    orders = [scene.display_order for scene in scenes]

    assert orders == sorted(orders)
    assert len(orders) == len(set(orders))


def test_public_scene_constructors_are_thin_canonical_resource_projections() -> None:
    for mode_id, scene_id, _path in list_builtin_scene_resources():
        assert asdict(create_scene(scene_id)) == asdict(
            create_builtin_scene(scene_id, mode_id=mode_id)
        )


def test_scene_presets_contains_no_python_plan_content_factory() -> None:
    source_path = Path(__file__).resolve().parents[1] / "src" / "config" / "scene_presets.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    constructors = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "SceneWorkspace"
    ]

    assert constructors == []


def test_canonical_scene_loader_rejects_missing_nested_field(tmp_path: Path) -> None:
    source = create_builtin_scene("official", mode_id="official")
    payload = asdict(source)
    del payload["exam_paper"]["runtime_fields"]
    path = tmp_path / "partial.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ConfigLoadError, match="exam_paper.*runtime_fields"):
        load_scene(path)


def test_canonical_scene_loader_rejects_unknown_nested_field(tmp_path: Path) -> None:
    payload = asdict(create_builtin_scene("custom", mode_id="custom"))
    payload["delivery_presets"][0]["artifacts"]["silent_drop"] = True
    path = tmp_path / "unknown.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ConfigLoadError, match="silent_drop"):
        load_scene(path)


def test_canonical_scene_loader_does_not_infer_compatible_template_ids(tmp_path: Path) -> None:
    payload = asdict(create_builtin_scene("custom", mode_id="custom"))
    payload["compatible_template_ids"] = []
    path = tmp_path / "repair-required.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    scene = load_scene(path)

    assert scene.template_id == "default"
    assert scene.compatible_template_ids == []
