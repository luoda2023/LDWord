from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.stage_release_config_library import stage_release_config_library


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_release_config_staging_only_copies_immutable_product_resources(
    tmp_path: Path,
) -> None:
    source = tmp_path / "config_library"
    target = tmp_path / "release_config_library"
    _write_json(source / "plans" / "official" / "builtin" / "official.json", {"id": "official"})
    _write_json(source / "plans" / "official" / "user" / "private.json", {"id": "private"})
    _write_json(
        source / "material_packages" / "official" / "builtin" / "sample" / "package.json",
        {"id": "sample"},
    )
    _write_json(
        source / "content_artifacts" / "sha256" / ("a" * 64) / "manifest.json",
        {"artifact_id": "a" * 64},
    )
    _write_json(
        source / "template_workbench" / "official" / "模板基准.json",
        {"kind": "template_authoring_profile"},
    )

    count, _ = stage_release_config_library(source, target)

    assert count == 3
    assert (target / "plans" / "official" / "builtin" / "official.json").is_file()
    assert (
        target / "material_packages" / "official" / "builtin" / "sample" / "package.json"
    ).is_file()
    assert (target / "template_workbench" / "official" / "模板基准.json").is_file()
    assert not list(target.rglob("user"))
    assert not list(target.rglob("content_artifacts"))


def test_release_config_staging_rejects_absolute_host_paths(tmp_path: Path) -> None:
    source = tmp_path / "config_library"
    target = tmp_path / "release_config_library"
    _write_json(
        source / "plans" / "official" / "builtin" / "official.json",
        {"source_path": r"C:\Users\developer\private.docx"},
    )

    with pytest.raises(ValueError, match="release_config_absolute_host_path"):
        stage_release_config_library(source, target)
