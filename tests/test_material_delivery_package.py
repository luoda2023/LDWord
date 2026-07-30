from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from PIL import Image
import pytest

from content_artifact_test_utils import compile_content_binding
import src.services.material_delivery.package_builder as package_builder_module
from src.services.material_delivery import (
    DeliveryPackageBuildError,
    DeliveryPackageBuildRequest,
    build_material_delivery_package,
    capture_delivery_package_source_receipt,
)
from src.config.material_context import MaterialExecutionContext
from src.services.material_content.artifact_repository import ContentArtifactRepository
from src.services.production_runtime.material_artifacts import (
    material_package_path_map,
    write_material_package_artifacts,
    material_package_receipt_payload,
)


def _manifest(path: Path, sources: tuple[Path, Path]) -> Path:
    payload = {
        "kind": "material_attachment_manifest",
        "schema_version": 1,
        "material_schema": {},
        "material_profile": {},
        "missing": {},
        "summary": {},
        "asset_items": [],
        "material_domains": {
            "content": {"bindings": []},
            "attachment": {
                "bindings": [
                    {
                        "role": "qualification",
                        "source_kind": "file_set",
                        "cardinality": "multiple",
                        "max_items": None,
                        "package_subdir": "attachments/qualification",
                        "items": [
                            {
                                "item_id": "part-a",
                                "relative_path": "part-a/proof.pdf",
                                "file_ref": {
                                    "source_path": str(sources[0]),
                                    "original_name": "proof.pdf",
                                    "media_type": "application/pdf",
                                    "content_sha256": _digest(sources[0]),
                                    "byte_size": sources[0].stat().st_size,
                                },
                            },
                            {
                                "item_id": "part-b",
                                "relative_path": "part-b/proof.pdf",
                                "file_ref": {
                                    "source_path": str(sources[1]),
                                    "original_name": "proof.pdf",
                                    "media_type": "application/pdf",
                                    "content_sha256": _digest(sources[1]),
                                    "byte_size": sources[1].stat().st_size,
                                },
                            },
                        ],
                    }
                ]
            },
        },
        "delivery": {},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _source_receipts(*paths: Path):
    return tuple(capture_delivery_package_source_receipt(path) for path in paths)


def _nested_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return {
            *(str(key) for key in value),
            *(key for item in value.values() for key in _nested_keys(item)),
        }
    if isinstance(value, list):
        return {key for item in value for key in _nested_keys(item)}
    return set()


def _typed_manifest(
    path: Path,
    *,
    content_bindings: list[dict[str, object]] | None = None,
    asset_items: list[dict[str, object]] | None = None,
    missing: dict[str, object] | None = None,
) -> Path:
    payload = {
        "kind": "material_attachment_manifest",
        "schema_version": 1,
        "material_schema": {},
        "material_profile": {},
        "missing": dict(missing or {}),
        "summary": {},
        "asset_items": list(asset_items or []),
        "material_domains": {
            "content": {"bindings": list(content_bindings or [])},
            "attachment": {"bindings": []},
        },
        "delivery": {},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _declared_zip_paths(receipt) -> set[str]:
    payload = json.loads(receipt.package_manifest_path.read_text(encoding="utf-8"))
    return {
        *(str(item["path"]) for item in payload["files"]),
        *(str(path) for path in payload["control_files"]),
    }


def test_typed_content_artifact_is_vendored_with_source_and_resources(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "content-source"
    source_root.mkdir()
    image = source_root / "images" / "route.png"
    image.parent.mkdir()
    Image.new("RGB", (12, 8), "navy").save(image)
    markdown = source_root / "route.md"
    markdown.write_text("# Route\n\n![](images/route.png)\n", encoding="utf-8")
    repository = ContentArtifactRepository(tmp_path / "content-artifacts")
    binding = compile_content_binding(markdown, repository)
    manifest = _typed_manifest(
        tmp_path / "manifest.json",
        content_bindings=[binding.to_dict()],
    )

    receipt = build_material_delivery_package(
        DeliveryPackageBuildRequest(
            input_path=tmp_path / "input.docx",
            output_dir=tmp_path / "output",
            manifest_path=manifest,
            source_receipts=_source_receipts(manifest),
            content_artifact_root=repository.root,
        )
    )

    assert receipt.status == "complete"
    vendored = (
        receipt.directory_path
        / "content_artifacts"
        / "sha256"
        / binding.artifact_ref.artifact_id
    )
    resolved = repository.validate(binding.artifact_ref)
    expected_relative = {
        "manifest.json",
        resolved.manifest.source.blob.path,
        resolved.manifest.fragment.path,
        resolved.manifest.receipt.path,
        *(item.file.path for item in resolved.manifest.resources),
    }
    assert {
        path.relative_to(vendored).as_posix()
        for path in vendored.rglob("*")
        if path.is_file()
    } == expected_relative
    package_payload = json.loads(
        receipt.package_manifest_path.read_text(encoding="utf-8")
    )
    content_files = [
        item
        for item in package_payload["files"]
        if item["category"] == "content_artifact"
    ]
    assert len(content_files) == len(expected_relative)
    assert all(
        _digest(receipt.directory_path / item["path"]) == item["sha256"]
        and (receipt.directory_path / item["path"]).stat().st_size
        == item["byte_size"]
        for item in content_files
    )
    with ZipFile(receipt.zip_path) as archive:
        assert set(archive.namelist()) == _declared_zip_paths(receipt)


def test_duplicate_content_artifact_refs_are_validated_before_dedup(
    tmp_path: Path,
) -> None:
    source = tmp_path / "content.md"
    source.write_text("# Content", encoding="utf-8")
    repository = ContentArtifactRepository(tmp_path / "artifact-repository")
    binding = compile_content_binding(source, repository, content_id="first")
    conflicting_binding = {
        **binding.to_dict(),
        "content_id": "second",
        "artifact_ref": {
            **binding.artifact_ref.to_dict(),
            "manifest_sha256": "0" * 64,
        },
    }
    manifest = _typed_manifest(
        tmp_path / "manifest.json",
        content_bindings=[binding.to_dict(), conflicting_binding],
    )

    receipt = build_material_delivery_package(
        DeliveryPackageBuildRequest(
            input_path=tmp_path / "input.docx",
            output_dir=tmp_path / "output",
            manifest_path=manifest,
            source_receipts=_source_receipts(manifest),
            content_artifact_root=repository.root,
        )
    )

    package_manifest = json.loads(
        receipt.package_manifest_path.read_text(encoding="utf-8")
    )
    assert receipt.status == "incomplete"
    assert receipt.missing_reference_count == 1
    assert package_manifest["missing_references"][0]["key"] == "second"
    assert (
        package_manifest["missing_references"][0]["code"]
        == "content_artifact_unavailable"
    )


def test_asset_source_drift_is_reported_and_not_copied(tmp_path: Path) -> None:
    asset = tmp_path / "logo.png"
    asset.write_bytes(b"version-one")
    manifest = _typed_manifest(
        tmp_path / "manifest.json",
        asset_items=[
            {
                "item_id": "logo-1",
                "role": "logo",
                "path": str(asset),
                "archive_dir": "logo",
                "content_sha256": _digest(asset),
                "byte_size": asset.stat().st_size,
            }
        ],
    )
    asset.write_bytes(b"version-two")

    receipt = build_material_delivery_package(
        DeliveryPackageBuildRequest(
            input_path=tmp_path / "input.docx",
            output_dir=tmp_path / "output",
            manifest_path=manifest,
            source_receipts=_source_receipts(manifest, asset),
        )
    )

    assert receipt.status == "incomplete"
    package_payload = json.loads(
        receipt.package_manifest_path.read_text(encoding="utf-8")
    )
    assert not any(item["category"] == "asset" for item in package_payload["files"])
    assert any(
        item["category"] == "asset"
        and item["code"] == "source_identity_mismatch"
        for item in package_payload["missing_references"]
    )
    with ZipFile(receipt.zip_path) as archive:
        assert set(archive.namelist()) == _declared_zip_paths(receipt)


def test_partial_copy_is_removed_and_publication_is_aborted(
    tmp_path: Path,
    monkeypatch,
) -> None:
    asset = tmp_path / "logo.png"
    asset.write_bytes(b"complete-asset")
    manifest = _typed_manifest(
        tmp_path / "manifest.json",
        asset_items=[
            {
                "item_id": "logo-1",
                "role": "logo",
                "path": str(asset),
                "archive_dir": "logo",
                "content_sha256": _digest(asset),
                "byte_size": asset.stat().st_size,
            }
        ],
    )
    original_copy = package_builder_module._copy_verified_receipt

    def _partial_asset_copy(receipt, destination, *args, **kwargs):
        if receipt.path == asset.resolve():
            Path(destination).write_bytes(b"PARTIAL")
            raise DeliveryPackageBuildError("simulated interrupted copy")
        return original_copy(receipt, destination, *args, **kwargs)

    monkeypatch.setattr(
        package_builder_module,
        "_copy_verified_receipt",
        _partial_asset_copy,
    )

    with pytest.raises(DeliveryPackageBuildError, match="simulated interrupted copy"):
        build_material_delivery_package(
            DeliveryPackageBuildRequest(
                input_path=tmp_path / "input.docx",
                output_dir=tmp_path / "output",
                manifest_path=manifest,
                source_receipts=_source_receipts(manifest, asset),
            )
        )

    assert not (tmp_path / "output" / "input_material_package").exists()
    assert not (tmp_path / "output" / "input_material_package.zip").exists()
    assert not any(
        path.read_bytes() == b"PARTIAL"
        for path in (tmp_path / "output").rglob("*")
        if path.is_file()
    )


def test_manifest_drift_during_copy_aborts_publication(
    tmp_path: Path,
) -> None:
    manifest = _typed_manifest(tmp_path / "manifest.json")
    output_dir = tmp_path / "output"
    receipts = _source_receipts(manifest)
    manifest.write_text('{"kind":"changed"}', encoding="utf-8")

    with pytest.raises(
        DeliveryPackageBuildError,
        match="material_manifest_evidence_invalid",
    ):
        build_material_delivery_package(
            DeliveryPackageBuildRequest(
                input_path=tmp_path / "input.docx",
                output_dir=output_dir,
                manifest_path=manifest,
                source_receipts=receipts,
            )
        )

    assert not (output_dir / "input_material_package").exists()
    assert not (output_dir / "input_material_package.zip").exists()


def test_workbench_adapter_reports_incomplete_package_receipt(tmp_path: Path) -> None:
    manifest = _typed_manifest(
        tmp_path / "manifest.json",
        missing={"field_keys": ["company_name"]},
    )
    config = SimpleNamespace(
        output=SimpleNamespace(material_package=True),
        delivery_presets=[],
    )

    package_result = write_material_package_artifacts(
        input_path=tmp_path / "input.docx",
        output_dir=tmp_path / "adapter-output",
        config=config,
        material_manifest_paths={"material": str(manifest)},
        material_context=MaterialExecutionContext(),
        output_paths={},
        compare_paths={},
        report_paths=[],
        intermediate_paths={},
    )

    package_paths = material_package_path_map(package_result)
    receipt_payload = material_package_receipt_payload(package_result)
    assert receipt_payload["status"] == "incomplete"
    assert receipt_payload["missing_reference_count"] == 0
    assert Path(package_paths["package_manifest"]).exists()
    assert Path(package_paths["zip"]).exists()


@pytest.mark.parametrize(
    "manifest_paths",
    (
        {},
        {"material": ""},
        {"unrelated_manifest": "manifest.json"},
    ),
)
def test_workbench_adapter_requires_explicit_material_manifest_path(
    tmp_path: Path,
    manifest_paths: dict[str, str],
) -> None:
    manifest = _typed_manifest(tmp_path / "manifest.json")
    resolved_paths = {
        key: str(manifest) if value == "manifest.json" else value
        for key, value in manifest_paths.items()
    }
    config = SimpleNamespace(
        output=SimpleNamespace(material_package=True),
        delivery_presets=[],
    )

    package_result = write_material_package_artifacts(
        input_path=tmp_path / "input.docx",
        output_dir=tmp_path / "adapter-output",
        config=config,
        material_manifest_paths=resolved_paths,
        material_context=MaterialExecutionContext(),
        output_paths={},
        compare_paths={},
        report_paths=[],
        intermediate_paths={},
    )

    assert package_result is None
    assert not (tmp_path / "adapter-output").exists()


def test_delivery_package_preserves_attachment_relative_tree(tmp_path: Path) -> None:
    first = tmp_path / "sources" / "a.pdf"
    second = tmp_path / "sources" / "b.pdf"
    first.parent.mkdir()
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    manifest = _manifest(tmp_path / "manifest.json", (first, second))

    receipt = build_material_delivery_package(
        DeliveryPackageBuildRequest(
            input_path=tmp_path / "input.docx",
            output_dir=tmp_path / "output",
            manifest_path=manifest,
            source_receipts=_source_receipts(manifest, first, second),
        )
    )

    expected = {
        "attachments/qualification/part-a/proof.pdf",
        "attachments/qualification/part-b/proof.pdf",
    }
    assert {
        item["path"]
        for item in json.loads(
            receipt.package_manifest_path.read_text(encoding="utf-8")
        )["files"]
        if item["category"] == "attachment"
    } == expected
    assert all((receipt.directory_path / path).is_file() for path in expected)
    with ZipFile(receipt.zip_path) as archive:
        assert expected <= set(archive.namelist())


def test_unproven_attachment_binding_is_not_partially_copied(tmp_path: Path) -> None:
    first = tmp_path / "sources" / "a.pdf"
    second = tmp_path / "sources" / "b.pdf"
    first.parent.mkdir()
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    manifest = _manifest(tmp_path / "manifest.json", (first, second))
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    del payload["material_domains"]["attachment"]["bindings"][0]["items"][0][
        "file_ref"
    ]["content_sha256"]
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    receipt = build_material_delivery_package(
        DeliveryPackageBuildRequest(
            input_path=tmp_path / "input.docx",
            output_dir=tmp_path / "output",
            manifest_path=manifest,
            source_receipts=_source_receipts(manifest, first, second),
        )
    )

    package_payload = json.loads(
        receipt.package_manifest_path.read_text(encoding="utf-8")
    )
    assert receipt.status == "incomplete"
    assert not any(
        item["category"] == "attachment" for item in package_payload["files"]
    )
    assert any(
        item["category"] == "attachment_binding"
        and item["code"] == "typed_contract_invalid"
        for item in package_payload["missing_references"]
    )
    with ZipFile(receipt.zip_path) as archive:
        assert set(archive.namelist()) == _declared_zip_paths(receipt)


def test_failed_rebuild_keeps_previous_directory_and_zip(tmp_path: Path) -> None:
    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    manifest = _manifest(tmp_path / "manifest.json", (first, second))
    request = DeliveryPackageBuildRequest(
        input_path=tmp_path / "input.docx",
        output_dir=tmp_path / "output",
        manifest_path=manifest,
        source_receipts=_source_receipts(manifest, first, second),
    )
    receipt = build_material_delivery_package(request)
    prior_manifest = receipt.package_manifest_path.read_bytes()
    prior_zip_digest = _digest(receipt.zip_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["material_domains"]["attachment"]["bindings"][0]["items"][0][
        "relative_path"
    ] = "../escape.pdf"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    bad_request = DeliveryPackageBuildRequest(
        input_path=request.input_path,
        output_dir=request.output_dir,
        manifest_path=manifest,
        source_receipts=_source_receipts(manifest, first, second),
    )

    with pytest.raises(DeliveryPackageBuildError, match="unsafe_package_relative_path"):
        build_material_delivery_package(bad_request)

    assert receipt.package_manifest_path.read_bytes() == prior_manifest
    assert _digest(receipt.zip_path) == prior_zip_digest
    assert not list(request.output_dir.glob("*.staging"))
    assert not list(request.output_dir.glob("*.backup"))


def test_second_publication_failure_restores_previous_directory_and_zip(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    manifest = _manifest(tmp_path / "manifest.json", (first, second))
    request = DeliveryPackageBuildRequest(
        input_path=tmp_path / "input.docx",
        output_dir=tmp_path / "output",
        manifest_path=manifest,
        source_receipts=_source_receipts(manifest, first, second),
    )
    receipt = build_material_delivery_package(request)
    prior_tree = {
        path.relative_to(receipt.directory_path).as_posix(): path.read_bytes()
        for path in receipt.directory_path.rglob("*")
        if path.is_file()
    }
    prior_zip = receipt.zip_path.read_bytes()
    original_replace = package_builder_module.os.replace

    def fail_staged_zip_publication(source, destination):
        source_path = Path(source)
        destination_path = Path(destination)
        if source_path.name.endswith(".zip.tmp") and destination_path == receipt.zip_path:
            raise OSError("injected staged ZIP publication failure")
        return original_replace(source, destination)

    monkeypatch.setattr(
        package_builder_module.os,
        "replace",
        fail_staged_zip_publication,
    )

    with pytest.raises(
        DeliveryPackageBuildError,
        match="material_package_publish_failed",
    ):
        build_material_delivery_package(request)

    assert {
        path.relative_to(receipt.directory_path).as_posix(): path.read_bytes()
        for path in receipt.directory_path.rglob("*")
        if path.is_file()
    } == prior_tree
    assert receipt.zip_path.read_bytes() == prior_zip
    assert not list(request.output_dir.glob(".*.backup"))
    assert not list(request.output_dir.glob(".*.staging"))
    assert not list(request.output_dir.glob(".*.zip.tmp"))


def test_processed_attachment_receipt_drift_blocks_package_rebuild(
    tmp_path: Path,
) -> None:
    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"
    first.write_bytes(b"configured-first")
    second.write_bytes(b"configured-second")
    processed_dir = tmp_path / "processed"
    processed = processed_dir / "part-a" / "proof.pdf"
    processed.parent.mkdir(parents=True)
    processed.write_bytes(b"processed")
    (processed_dir / "attachment_bundle_receipt.json").write_text(
        '{"receipt_id":"evidence"}',
        encoding="utf-8",
    )
    manifest = _manifest(tmp_path / "manifest.json", (first, second))
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["material_domains"]["attachment"]["execution"] = {
        "status": "applied",
        "receipts": {
            "qualification": {
                "output_directory": str(processed_dir),
                "files": [
                    {
                        "item_id": "part-a",
                        "relative_path": "part-a/proof.pdf",
                        "output_sha256": _digest(processed),
                        "output_byte_size": processed.stat().st_size,
                        "status": "substituted",
                    }
                ],
            }
        },
        "errors": {},
    }
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    request = DeliveryPackageBuildRequest(
        input_path=tmp_path / "input.docx",
        output_dir=tmp_path / "output",
        manifest_path=manifest,
        source_receipts=_source_receipts(manifest, processed),
    )
    receipt = build_material_delivery_package(request)
    prior_manifest = receipt.package_manifest_path.read_bytes()
    prior_zip_digest = _digest(receipt.zip_path)

    processed.write_bytes(b"drifted")

    with pytest.raises(
        DeliveryPackageBuildError,
        match="material_package_source_evidence_invalid",
    ):
        build_material_delivery_package(request)

    assert receipt.package_manifest_path.read_bytes() == prior_manifest
    assert _digest(receipt.zip_path) == prior_zip_digest


def test_processed_attachment_receipt_cannot_escape_through_symlink(
    tmp_path: Path,
) -> None:
    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"
    first.write_bytes(b"configured-first")
    second.write_bytes(b"configured-second")
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"outside")
    processed_dir = tmp_path / "processed"
    linked = processed_dir / "part-a" / "proof.pdf"
    linked.parent.mkdir(parents=True)
    try:
        linked.symlink_to(outside)
    except OSError:
        pytest.skip("symbolic links are unavailable in this Windows environment")
    (processed_dir / "attachment_bundle_receipt.json").write_text(
        '{"receipt_id":"evidence"}',
        encoding="utf-8",
    )
    manifest = _manifest(tmp_path / "manifest.json", (first, second))
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["material_domains"]["attachment"]["execution"] = {
        "status": "applied",
        "receipts": {
            "qualification": {
                "output_directory": str(processed_dir),
                "files": [
                    {
                        "item_id": "part-a",
                        "relative_path": "part-a/proof.pdf",
                        "output_sha256": _digest(outside),
                        "output_byte_size": outside.stat().st_size,
                        "status": "substituted",
                    }
                ],
            }
        },
        "errors": {},
    }
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        DeliveryPackageBuildError,
        match="attachment_receipt_source_reparse_component",
    ):
        build_material_delivery_package(
            DeliveryPackageBuildRequest(
                input_path=tmp_path / "input.docx",
                output_dir=tmp_path / "output",
                manifest_path=manifest,
                source_receipts=_source_receipts(manifest),
            )
        )

    assert not (tmp_path / "output" / "input_material_package").exists()


@pytest.mark.parametrize("reference_kind", ["asset", "output"])
def test_unreceipted_existing_source_aborts_without_artifacts(
    tmp_path: Path,
    reference_kind: str,
) -> None:
    secret = tmp_path / "outside_secret.txt"
    secret.write_text("private", encoding="utf-8")
    manifest = _typed_manifest(tmp_path / "manifest.json")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if reference_kind == "asset":
        payload["asset_items"] = [
            {
                "item_id": "malicious",
                "role": "logo",
                "path": str(secret),
                "archive_dir": "logo",
                "content_sha256": _digest(secret),
                "byte_size": secret.stat().st_size,
            }
        ]
    else:
        payload["delivery"] = {"output_paths": {"malicious": str(secret)}}
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    output_dir = tmp_path / "output"

    with pytest.raises(
        DeliveryPackageBuildError,
        match="material_package_source_unauthorized",
    ):
        build_material_delivery_package(
            DeliveryPackageBuildRequest(
                input_path=tmp_path / "input.docx",
                output_dir=output_dir,
                manifest_path=manifest,
                source_receipts=_source_receipts(manifest),
            )
        )

    assert not (output_dir / "input_material_package").exists()
    assert not (output_dir / "input_material_package.zip").exists()
    assert not any(path.is_file() for path in output_dir.rglob("*"))


def test_receipted_symlink_source_is_rejected_before_copy(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    linked = tmp_path / "linked.txt"
    try:
        linked.symlink_to(outside)
    except OSError:
        pytest.skip("symbolic links are unavailable in this Windows environment")
    manifest = _typed_manifest(
        tmp_path / "manifest.json",
        asset_items=[
            {
                "item_id": "linked",
                "role": "logo",
                "path": str(linked),
                "archive_dir": "logo",
                "content_sha256": _digest(outside),
                "byte_size": outside.stat().st_size,
            }
        ],
    )
    output_dir = tmp_path / "output"

    with pytest.raises(DeliveryPackageBuildError, match="reparse_component"):
        build_material_delivery_package(
            DeliveryPackageBuildRequest(
                input_path=tmp_path / "input.docx",
                output_dir=output_dir,
                manifest_path=manifest,
                source_receipts=_source_receipts(manifest, outside),
            )
        )

    assert not (output_dir / "input_material_package").exists()
    assert not (output_dir / "input_material_package.zip").exists()


def test_junction_component_is_rejected_during_receipt_capture(
    tmp_path: Path,
    monkeypatch,
) -> None:
    junction = tmp_path / "junction"
    junction.mkdir()
    source = junction / "source.txt"
    source.write_text("source", encoding="utf-8")
    path_type = type(source)
    original_is_junction = path_type.is_junction

    def _is_junction(path: Path) -> bool:
        return path == junction or original_is_junction(path)

    monkeypatch.setattr(path_type, "is_junction", _is_junction)
    with pytest.raises(
        DeliveryPackageBuildError,
        match="material_package_source_receipt_reparse_component",
    ):
        capture_delivery_package_source_receipt(source)


def test_public_package_uses_relative_identity_records_without_local_paths(
    tmp_path: Path,
) -> None:
    first = tmp_path / "sources" / "a.pdf"
    second = tmp_path / "sources" / "b.pdf"
    first.parent.mkdir()
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    manifest = _manifest(tmp_path / "local_manifest.json", (first, second))
    receipt = build_material_delivery_package(
        DeliveryPackageBuildRequest(
            input_path=tmp_path / "input.docx",
            output_dir=tmp_path / "output",
            manifest_path=manifest,
            source_receipts=_source_receipts(manifest, first, second),
        )
    )

    package_payload = json.loads(
        receipt.package_manifest_path.read_text(encoding="utf-8")
    )
    assert package_payload["visibility"] == "public_delivery"
    assert not ({"input", "source", "source_manifest", "reason"} & _nested_keys(package_payload))
    attachment_files = [
        item for item in package_payload["files"] if item["category"] == "attachment"
    ]
    assert attachment_files
    for item in attachment_files:
        assert not Path(item["path"]).is_absolute()
        copied = receipt.directory_path.joinpath(*item["path"].split("/"))
        assert copied.is_file()
        assert item["sha256"] == _digest(copied)
        assert item["byte_size"] == copied.stat().st_size

    local_markers = {str(tmp_path), tmp_path.as_posix(), str(manifest)}
    with ZipFile(receipt.zip_path) as archive:
        for name in archive.namelist():
            if Path(name).suffix.casefold() not in {".json", ".md"}:
                continue
            text = archive.read(name).decode("utf-8")
            assert all(marker not in text for marker in local_markers)
            if name.endswith(".json"):
                payload = json.loads(text)
                assert not (
                    {"input", "source", "source_manifest", "reason"}
                    & _nested_keys(payload)
                )
        public_manifest = json.loads(
            archive.read("manifest/material_manifest.json").decode("utf-8")
        )
    assert public_manifest["visibility"] == "public_delivery"


def test_public_report_projection_redacts_local_json_paths(tmp_path: Path) -> None:
    report = tmp_path / "source_changes.json"
    local_output = tmp_path / "rendered.docx"
    local_output.write_bytes(b"rendered")
    report.write_text(
        json.dumps(
            {
                "input": str(tmp_path / "input.docx"),
                "outputs": {"primary": str(local_output)},
                "status": "complete",
            }
        ),
        encoding="utf-8",
    )
    manifest = _typed_manifest(tmp_path / "local_manifest.json")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["delivery"] = {"report_paths": [str(report)]}
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    receipt = build_material_delivery_package(
        DeliveryPackageBuildRequest(
            input_path=tmp_path / "input.docx",
            output_dir=tmp_path / "output",
            manifest_path=manifest,
            source_receipts=_source_receipts(manifest, report),
        )
    )

    with ZipFile(receipt.zip_path) as archive:
        report_name = next(
            name for name in archive.namelist() if name.endswith("source_changes.json")
        )
        projected = json.loads(archive.read(report_name).decode("utf-8"))
        projected_text = json.dumps(projected)
    assert "input" not in projected
    assert projected["outputs"]["primary"] == "rendered.docx"
    assert str(tmp_path) not in projected_text
    assert tmp_path.as_posix() not in projected_text
