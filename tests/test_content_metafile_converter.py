from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path

from PIL import Image
import pytest

from src.config.content_materials import ImageBlock
from src.services.material_content.artifact_repository import (
    ContentArtifactRepository,
)
from src.services.material_content.compiler import compile_content_material
from src.services.material_content.metafile_converter import (
    convert_metafile_to_png,
)
from tests.content_docx_fixture_factory import (
    build_docx_with_emf,
    build_docx_with_wmf,
    emf_bytes,
    wmf_bytes,
)


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows metafile fixture")


@pytest.mark.parametrize("factory", (emf_bytes, wmf_bytes))
def test_metafile_conversion_is_deterministic_and_bounded(factory) -> None:
    source = factory()

    first = convert_metafile_to_png(source)
    second = convert_metafile_to_png(source)

    assert first == second
    payload, width, height = first
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert width > 0 and height > 0 and width * height < 40_000_000
    with Image.open(BytesIO(payload)) as image:
        assert image.format == "PNG"
        assert image.size == (width, height)


@pytest.mark.parametrize(
    "builder",
    (build_docx_with_emf, build_docx_with_wmf),
)
def test_docx_metafile_is_published_as_png_artifact_resource(
    tmp_path: Path,
    builder,
) -> None:
    source = builder(tmp_path / "metafile.docx")
    repository = ContentArtifactRepository(tmp_path / "artifacts")

    result = compile_content_material(source, repository)

    assert result.blocked is False
    assert "metafile_rasterized" in {item.code for item in result.findings}
    image = next(block for block in result.fragment.blocks if isinstance(block, ImageBlock))
    assert image.resource_id.endswith(".png")
    payload = repository.resolve_resource(
        result.artifact_ref,
        image.resource_id,
    ).read_bytes()
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
