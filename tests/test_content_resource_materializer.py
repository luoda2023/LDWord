from pathlib import Path

from PIL import Image
import pytest

from content_artifact_test_utils import compile_content_binding
from src.config.content_materials import ContentResourceKey
from src.services.material_content.artifact_repository import ContentArtifactRepository
from src.services.material_content.resource_materializer import (
    ContentResourceMaterializationError,
    materialize_content_fragment_resources,
)


def _compiled(tmp_path: Path):
    root = tmp_path / "material"
    image = root / "images" / "diagram.png"
    image.parent.mkdir(parents=True)
    Image.new("RGB", (20, 12), (15, 90, 170)).save(image, format="PNG")
    markdown = root / "content.md"
    markdown.write_text("![route](images/diagram.png)\n", encoding="utf-8")
    repository = ContentArtifactRepository(tmp_path / "artifacts")
    binding = compile_content_binding(markdown, repository)
    return binding, repository.load_fragment(binding.artifact_ref), repository, markdown, image


def test_materialization_resolves_artifact_after_sources_are_deleted(tmp_path: Path):
    binding, fragment, repository, markdown, image = _compiled(tmp_path)
    expected = image.read_bytes()
    markdown.unlink()
    image.unlink()
    first = materialize_content_fragment_resources(
        (binding,), {binding.content_id: fragment}, repository
    )
    second = materialize_content_fragment_resources(
        (binding,), {binding.content_id: fragment}, repository
    )
    assert second == first
    entry = first.entries[0]
    assert entry.key == ContentResourceKey(binding.content_id, entry.resource.resource_id)
    assert Path(entry.source_path).read_bytes() == expected


def test_materialization_rejects_tampered_artifact(tmp_path: Path):
    binding, fragment, repository, _, _ = _compiled(tmp_path)
    resolved = repository.validate(binding.artifact_ref)
    resource_path = resolved.resource_path(resolved.manifest.resources[0].resource_id)
    resource_path.write_bytes(b"tampered")
    with pytest.raises(ContentResourceMaterializationError) as raised:
        materialize_content_fragment_resources(
            (binding,), {binding.content_id: fragment}, repository
        )
    assert raised.value.diagnostics[0].content_id == binding.content_id
    assert raised.value.diagnostics[0].code in {
        "artifact_file_size_mismatch", "artifact_file_hash_mismatch"
    }
