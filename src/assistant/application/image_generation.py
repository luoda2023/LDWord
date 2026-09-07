# -*- coding: utf-8 -*-
"""Image-generation abstraction for turning AI figure placeholders into files.

Why this module exists
----------------------
The AI writes ``【图：说明】`` placeholders for figures it cannot express as
Markdown directly.  This module defines a provider-agnostic seam so a real
third-party text-to-image API can later be plugged in without touching the
authoring pipeline: a provider is asked to render each placeholder's Chinese
description into bytes, which are then landed under the session's ``images/``
directory and rewritten to ``![说明](images/xxx.png)``.

Until a concrete provider is configured, :class:`NoopImageGenerationProvider`
keeps the pipeline safe: placeholders are left untouched (so the DOCX exporter
still surfaces them as "待补充" figure slots).
"""
from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol

from src.assistant.storage.paths import assistant_storage_root


class ImageGenerationProvider(Protocol):
    """A pluggable text-to-image backend."""

    def generate(self, prompt: str, *, size: str = "1024x1024") -> bytes | None:
        """Return rendered image bytes, or ``None`` when generation is unavailable.

        ``prompt`` is a Chinese natural-language description of the figure
        (e.g. "施工流程图：从进场到竣工的5个阶段，含箭头流向").  Implementations
        may translate/adapt it for their own backend.
        """
        ...


class NoopImageGenerationProvider:
    """Default provider: generation is unavailable, placeholders stay put."""

    def generate(self, prompt: str, *, size: str = "1024x1024") -> bytes | None:
        return None


# Placeholder convention: 【图：说明】 with a configurable prefix/suffix.
_DEFAULT_PREFIX = "【图"
_DEFAULT_SUFFIX = "】"


def _placeholder_regex(prefix: str = _DEFAULT_PREFIX, suffix: str = _DEFAULT_SUFFIX) -> re.Pattern[str]:
    p = re.escape(prefix)
    s = re.escape(suffix)
    return re.compile(rf"{p}([^{re.escape(suffix)}\n]*){s}")


class ImageGenerationService:
    """Orchestrates placeholder → provider → landed image file."""

    def __init__(
        self,
        provider: ImageGenerationProvider | None = None,
        root: Path | None = None,
    ) -> None:
        self.provider = provider or NoopImageGenerationProvider()
        self.root = Path(root) if root is not None else assistant_storage_root()
        self.base = self.root / "workbench"

    def _images_dir(self, session_id: str) -> Path:
        safe = "".join(ch for ch in str(session_id) if ch.isalnum() or ch in "-_")
        if not safe:
            raise ValueError("invalid session id for image generation")
        return self.base / safe / "images"

    def materialize_placeholders(
        self,
        session_id: str,
        markdown: str,
        *,
        prefix: str = _DEFAULT_PREFIX,
        suffix: str = _DEFAULT_SUFFIX,
        size: str = "1024x1024",
    ) -> tuple[str, dict[str, str]]:
        """Replace ``【图：说明】`` placeholders with landed image references.

        Returns ``(rewritten_markdown, resource_paths)``.  Placeholders whose
        provider returns ``None`` are left unchanged.  Images are content-hash
        deduped under the session's ``images/`` directory.
        """
        source = str(markdown or "")
        if not source:
            return source, {}
        images_dir = self._images_dir(session_id)
        resource_paths: dict[str, str] = {}
        pattern = _placeholder_regex(prefix, suffix)

        def _materialise(match: re.Match[str]) -> str:
            description = (match.group(1) or "").strip()
            if not description:
                return match.group(0)
            raw = self.provider.generate(description, size=size)
            if not raw:
                return match.group(0)
            digest = hashlib.sha256(raw).hexdigest()[:16]
            stem = "".join(ch for ch in description[:24] if ch.isalnum() or ch in "-_") or "figure"
            filename = f"{stem}_{digest}.png"
            dest = images_dir / filename
            try:
                images_dir.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    dest.write_bytes(raw)
            except OSError:
                return match.group(0)
            relative = f"images/{filename}"
            resource_paths[relative] = str(dest)
            return f"![{description}]({relative})"

        rewritten = pattern.sub(_materialise, source)
        return rewritten, resource_paths


__all__ = [
    "ImageGenerationProvider",
    "NoopImageGenerationProvider",
    "ImageGenerationService",
    "_placeholder_regex",
]
