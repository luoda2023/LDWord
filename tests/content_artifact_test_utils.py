"""Small test factories for the compiled content-artifact contract."""

from __future__ import annotations

from pathlib import Path

from src.config.content_artifacts import (
    ContentArtifactRef,
    ContentMaterialBinding,
)
from src.services.material_content.artifact_repository import (
    ContentArtifactRepository,
)
from src.services.material_content.compiler import compile_content_material


def dummy_content_binding(
    content_id: str = "technical_route",
    *,
    label: str = "Technical route",
    artifact_hex: str = "a",
) -> ContentMaterialBinding:
    digest = artifact_hex.casefold() * 64
    return ContentMaterialBinding(
        content_id=content_id,
        label=label,
        artifact_ref=ContentArtifactRef(
            artifact_id=digest,
            manifest_sha256=digest,
        ),
    )


def compile_content_binding(
    source: str | Path,
    repository: ContentArtifactRepository,
    *,
    content_id: str = "technical_route",
    label: str = "Technical route",
) -> ContentMaterialBinding:
    result = compile_content_material(source, repository)
    assert not result.blocked, result.findings
    assert result.artifact_ref is not None
    return ContentMaterialBinding(
        content_id=content_id,
        label=label,
        artifact_ref=result.artifact_ref,
    )


__all__ = ["compile_content_binding", "dummy_content_binding"]
