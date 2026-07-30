"""Minimal artifact transfer boundary used by material-package archives.

The entity model belongs to ``src.config`` and must stay importable without
loading the content-material service implementation.  Archive IO therefore
depends on this small structural contract; the concrete repository is resolved
only when a caller actually needs the historical default repository.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

from src.config.content_artifacts import ContentArtifactRef


class ContentArtifactRepository(Protocol):
    """Operations required to transfer content-addressed package artifacts."""

    def vendor(
        self,
        ref: ContentArtifactRef,
        vendor_artifacts_root: str | Path,
    ) -> Path: ...

    def install_vendored(
        self,
        artifact_directory: str | Path,
    ) -> ContentArtifactRef: ...


def default_content_artifact_repository(
    root: str | Path,
) -> ContentArtifactRepository:
    """Create the production repository without an import-time layer edge."""

    module = import_module(
        "src.services.material_content.artifact_repository"
    )
    repository_type = getattr(module, "ContentArtifactRepository")
    return cast(ContentArtifactRepository, repository_type(root))


__all__ = [
    "ContentArtifactRepository",
    "default_content_artifact_repository",
]
