from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

import src.services.material_content.artifact_repository as repository_module
from src.config.content_artifacts import (
    CONTENT_COMPILER_CONTRACT,
    CONTENT_IR_CONTRACT,
)
from src.config.content_materials import DocumentFragment, ImageBlock
from src.services.material_content.artifact_repository import (
    ArtifactResourcePayload,
    ContentArtifactPublishCancelled,
    ContentArtifactRepository,
    ContentArtifactRepositoryError,
)
from src.services.material_content.import_contract import (
    ContentCompileReceipt,
    ContentSemanticInventory,
)
from src.services.material_content.source_capture import CapturedContentSource


def _captured(payload: bytes = b"# title\n") -> CapturedContentSource:
    return CapturedContentSource(
        original_name="source.md",
        source_format="markdown",
        media_type="text/markdown",
        payload=payload,
        sha256=sha256(payload).hexdigest(),
        byte_size=len(payload),
    )


def _receipt(source: CapturedContentSource) -> ContentCompileReceipt:
    return ContentCompileReceipt(
        compiler_contract=CONTENT_COMPILER_CONTRACT,
        parser_contract=CONTENT_IR_CONTRACT,
        source_sha256=source.sha256,
        inventory=ContentSemanticInventory.empty(),
    )


def test_publish_is_atomic_deduplicated_and_source_path_independent(
    tmp_path: Path,
) -> None:
    repository = ContentArtifactRepository(tmp_path / "content_artifacts")
    source = _captured()
    fragment = DocumentFragment(())

    first = repository.publish(source, fragment, _receipt(source))
    second = repository.publish(source, fragment, _receipt(source))

    assert first == second
    assert repository.load_fragment(first) == fragment
    assert repository.load_receipt(first) == _receipt(source)
    artifact_directories = [
        item
        for item in repository.artifacts_root.iterdir()
        if item.is_dir() and not item.name.startswith(".staging-")
    ]
    assert [item.name for item in artifact_directories] == [first.artifact_id]
    assert not list(repository.artifacts_root.glob(".staging-*"))


def test_resource_is_closed_verified_and_resolved_from_artifact(tmp_path: Path) -> None:
    repository = ContentArtifactRepository(tmp_path / "content_artifacts")
    source = _captured()
    resource = ArtifactResourcePayload.from_bytes(
        b"png-data",
        media_type="image/png",
        suffix="png",
    )
    fragment = DocumentFragment((ImageBlock(resource.resource_id),))

    ref = repository.publish(source, fragment, _receipt(source), (resource,))
    resource_path = repository.resolve_resource(ref, resource.resource_id)

    assert resource_path.read_bytes() == b"png-data"
    assert repository.load_fragment(ref) == fragment


def test_cancelled_publication_cleans_staging_and_publishes_nothing(
    tmp_path: Path,
) -> None:
    repository = ContentArtifactRepository(tmp_path / "content_artifacts")
    source = _captured()

    with pytest.raises(ContentArtifactPublishCancelled):
        repository.publish(source, DocumentFragment(()), _receipt(source), cancelled=lambda: True)

    assert not list(repository.artifacts_root.iterdir())


def test_validation_detects_tampering_and_gc_only_reports_candidates(
    tmp_path: Path,
) -> None:
    repository = ContentArtifactRepository(tmp_path / "content_artifacts")
    first_source = _captured(b"first")
    second_source = _captured(b"second")
    fragment = DocumentFragment(())
    first = repository.publish(first_source, fragment, _receipt(first_source))
    second = repository.publish(second_source, fragment, _receipt(second_source))

    assert repository.garbage_collection_candidates((first,)) == (
        second.artifact_id,
    )
    assert repository.validate(second).ref == second

    fragment_path = repository.artifacts_root / first.artifact_id / "fragment.json"
    fragment_path.write_bytes(b"{}")
    with pytest.raises(
        ContentArtifactRepositoryError,
        match="size does not match|digest does not match",
    ):
        repository.validate(first)


def test_fragment_resource_closure_is_required(tmp_path: Path) -> None:
    repository = ContentArtifactRepository(tmp_path / "content_artifacts")
    source = _captured()
    digest = sha256(b"missing").hexdigest()
    fragment = DocumentFragment((ImageBlock(f"sha256/{digest}.png"),))

    with pytest.raises(ValueError, match="closure mismatch"):
        repository.publish(source, fragment, _receipt(source))


def test_vendored_artifact_installs_cross_repository_without_identity_change(
    tmp_path: Path,
) -> None:
    source_repository = ContentArtifactRepository(tmp_path / "source-repository")
    captured = _captured()
    ref = source_repository.publish(
        captured,
        DocumentFragment(()),
        _receipt(captured),
    )
    vendored = source_repository.vendor(
        ref,
        tmp_path / "package" / "content_artifacts" / "sha256",
    )
    destination_repository = ContentArtifactRepository(
        tmp_path / "destination-repository"
    )

    installed = destination_repository.install_vendored(vendored)

    assert installed == ref
    assert destination_repository.load_fragment(installed) == DocumentFragment(())


def test_vendor_validation_failure_leaves_no_partial_public_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_repository = ContentArtifactRepository(tmp_path / "source-repository")
    captured = _captured()
    ref = source_repository.publish(
        captured,
        DocumentFragment(()),
        _receipt(captured),
    )
    vendor_root = tmp_path / "package" / "content_artifacts" / "sha256"
    original_validate = ContentArtifactRepository._validate_directory

    def fail_staging_validation(self, directory, *args, **options):
        if Path(directory).name.startswith(".staging-vendor-"):
            raise ContentArtifactRepositoryError(
                "injected_vendor_validation_failure",
                "injected vendor validation failure",
            )
        return original_validate(self, directory, *args, **options)

    monkeypatch.setattr(
        repository_module.ContentArtifactRepository,
        "_validate_directory",
        fail_staging_validation,
    )

    with pytest.raises(ContentArtifactRepositoryError):
        source_repository.vendor(ref, vendor_root)

    assert not (vendor_root / ref.artifact_id).exists()
    assert not list(vendor_root.glob(".staging-vendor-*"))
