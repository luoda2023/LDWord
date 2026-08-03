import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene import SceneWorkspace
from src.services.production_runtime.material_artifacts import (
    plan_material_artifact_paths,
    publish_material_artifacts,
)


def test_publish_material_artifacts_writes_manifest_and_transactional_package(
    tmp_path,
):
    input_path = tmp_path / "source.docx"
    output_path = tmp_path / "source_formatted.docx"
    input_path.write_bytes(b"input")
    output_path.write_bytes(b"output")
    scene = SceneWorkspace(mode_id="custom")
    artifacts = scene.delivery_presets[0].artifacts
    artifacts.material_manifest = True
    artifacts.material_package = True

    outcome = publish_material_artifacts(
        input_path=input_path,
        output_dir=tmp_path,
        config=scene,
        material_snapshot=None,
        output_paths={"final": str(output_path)},
    )

    manifest_path = Path(outcome.material_manifest_paths["material"])
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["kind"] == "material_attachment_manifest"
    assert payload["delivery"]["output_paths"] == {
        "final": str(output_path)
    }
    package_path = Path(outcome.material_package_paths["zip"])
    assert package_path.is_file()
    assert outcome.material_package_receipt["status"] == "complete"
    with zipfile.ZipFile(package_path) as archive:
        assert "package_manifest.json" in archive.namelist()
        assert "manifest/material_manifest.json" in archive.namelist()
        assert "outputs/final_source_formatted.docx" in archive.namelist()


def test_publish_material_artifacts_is_noop_when_disabled(tmp_path):
    scene = SceneWorkspace(mode_id="custom")
    scene.delivery_presets[0].artifacts.material_manifest = False
    scene.delivery_presets[0].artifacts.material_package = False

    outcome = publish_material_artifacts(
        input_path=tmp_path / "source.docx",
        output_dir=tmp_path,
        config=scene,
        material_snapshot=None,
        output_paths={},
    )

    assert outcome.material_manifest_paths == {}
    assert outcome.material_package_paths == {}
    assert not list(tmp_path.glob("*material*"))


def test_material_only_delivery_has_a_real_preflight_output_plan(tmp_path):
    input_path = tmp_path / "qualification.archive.docx"
    scene = SceneWorkspace(mode_id="bidding")
    artifacts = scene.delivery_presets[0].artifacts
    artifacts.final_docx = False
    artifacts.material_manifest = True
    artifacts.material_package = True

    planned = plan_material_artifact_paths(
        input_path=input_path,
        output_dir=tmp_path / "out",
        config=scene,
    )

    assert {key: path.name for key, path in planned.items()} == {
        "material_manifest": "qualification.archive_material_manifest.json",
        "material_package_directory": "qualification.archive_material_package",
        "material_package_zip": "qualification.archive_material_package.zip",
    }


def test_material_package_redacts_local_paths_from_json_outputs(tmp_path):
    input_path = tmp_path / "source.docx"
    output_path = tmp_path / "runtime_manifest.json"
    input_path.write_bytes(b"input")
    output_path.write_text(
        json.dumps({"output_path": str(tmp_path / "private.docx")}),
        encoding="utf-8",
    )
    scene = SceneWorkspace(mode_id="official")
    scene.delivery_presets[0].artifacts.material_package = True

    outcome = publish_material_artifacts(
        input_path=input_path,
        output_dir=tmp_path,
        config=scene,
        material_snapshot=None,
        output_paths={"manifest": str(output_path)},
    )

    with zipfile.ZipFile(outcome.material_package_paths["zip"]) as archive:
        packaged = json.loads(
            archive.read("outputs/manifest_runtime_manifest.json")
        )
    serialized = json.dumps(packaged)
    assert str(tmp_path) not in serialized
    assert packaged["output_path"] == "private.docx"
