"""Immutable evidence contract for a prepared material image."""

from __future__ import annotations

from dataclasses import dataclass
import re


IMAGE_TRANSFORM_CONTRACT = "image-transform-v1"


@dataclass(frozen=True, slots=True)
class PreparedImage:
    cache_key: str
    output_path: str
    output_sha256: str
    media_type: str
    width_px: int
    height_px: int
    source_sha256: str
    watermark_text_sha256: str
    transform_contract: str = IMAGE_TRANSFORM_CONTRACT
    cache_hit: bool = False

    def __post_init__(self) -> None:
        for name in ("cache_key", "output_sha256", "source_sha256"):
            value = getattr(self, name)
            if not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError(f"{name} must be a lowercase SHA-256")
        if self.watermark_text_sha256 and not re.fullmatch(
            r"[0-9a-f]{64}", self.watermark_text_sha256
        ):
            raise ValueError("watermark_text_sha256 must be empty or a SHA-256")
        if self.media_type not in {"image/png", "image/jpeg"}:
            raise ValueError("prepared images must be PNG or JPEG")
        if self.width_px <= 0 or self.height_px <= 0:
            raise ValueError("prepared image dimensions must be positive")


__all__ = ["IMAGE_TRANSFORM_CONTRACT", "PreparedImage"]
