"""Memory-bounded raster decoding for thumbnails and interactive previews."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from PIL.ImageQt import ImageQt

from src.qt_api import QImageReader, QPixmap, QSize, Qt

DEFAULT_PREVIEW_PIXEL_BUDGET = 12_000_000


@dataclass(frozen=True, slots=True)
class BoundedRasterResult:
    pixmap: QPixmap
    source_size: QSize
    image_format: str = ""
    error: str = ""
    downsampled: bool = False


def raster_source_size(path: str | Path) -> QSize:
    """Read dimensions from the image header without decoding its pixels."""

    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    return QSize(reader.size())


def load_bounded_raster(
    path: str | Path,
    *,
    bounding_size: QSize | None = None,
    max_pixels: int | None = None,
) -> BoundedRasterResult:
    """Decode a raster inside the requested dimensions and pixel budget.

    Qt plugins that support decoder-side scaling take the fast path. Formats
    such as very large PNG files can still be rejected against Qt's original
    allocation estimate, so Pillow provides a guarded fallback and retains
    only the reduced result in the returned ``QPixmap``.
    """

    candidate = Path(path)
    if not candidate.is_file():
        return BoundedRasterResult(QPixmap(), QSize(), error="文件不存在")

    reader = QImageReader(str(candidate))
    reader.setAutoTransform(True)
    source_size = QSize(reader.size())
    target_size = _bounded_size(
        source_size,
        bounding_size=bounding_size,
        max_pixels=max_pixels,
    )
    if (
        target_size.isValid()
        and not target_size.isEmpty()
        and target_size != source_size
    ):
        reader.setScaledSize(target_size)
    image = reader.read()
    image_format = bytes(reader.format()).decode("ascii", "ignore").upper()
    if not image.isNull():
        pixmap = QPixmap.fromImage(image)
        pixmap = _fit_pixmap(pixmap, target_size)
        return BoundedRasterResult(
            pixmap,
            source_size if source_size.isValid() else pixmap.size(),
            image_format=image_format,
            downsampled=(
                source_size.isValid()
                and not source_size.isEmpty()
                and pixmap.size() != source_size
            ),
        )

    qt_error = reader.errorString()
    try:
        pixmap, pillow_size, pillow_format = _load_with_pillow(
            candidate,
            target_size=target_size,
        )
    except Image.DecompressionBombError:
        error = "图片像素尺寸超过安全预览范围"
    except MemoryError:
        error = "图片解码所需内存过大"
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        error = str(exc) or qt_error or "无法读取图片"
    else:
        resolved_source_size = (
            source_size if source_size.isValid() else pillow_size
        )
        return BoundedRasterResult(
            pixmap,
            resolved_source_size,
            image_format=image_format or pillow_format,
            downsampled=(
                resolved_source_size.isValid()
                and not resolved_source_size.isEmpty()
                and pixmap.size() != resolved_source_size
            ),
        )
    return BoundedRasterResult(
        QPixmap(),
        source_size,
        image_format=image_format,
        error=error or qt_error or "无法读取图片",
    )


def _bounded_size(
    source_size: QSize,
    *,
    bounding_size: QSize | None,
    max_pixels: int | None,
) -> QSize:
    if not source_size.isValid() or source_size.isEmpty():
        return QSize(bounding_size or QSize())
    width = source_size.width()
    height = source_size.height()
    scale = 1.0
    if bounding_size is not None and bounding_size.isValid():
        scale = min(
            scale,
            max(1, bounding_size.width()) / width,
            max(1, bounding_size.height()) / height,
        )
    pixel_budget = max(1, int(max_pixels or 0))
    pixel_count = width * height
    if max_pixels is not None and pixel_count > pixel_budget:
        scale = min(scale, sqrt(pixel_budget / pixel_count))
    if scale >= 1.0:
        return QSize(source_size)
    return QSize(
        max(1, round(width * scale)),
        max(1, round(height * scale)),
    )


def _load_with_pillow(
    path: Path,
    *,
    target_size: QSize,
) -> tuple[QPixmap, QSize, str]:
    with Image.open(path) as source:
        source_size = QSize(*source.size)
        image_format = str(source.format or "").upper()
        target = (
            (target_size.width(), target_size.height())
            if target_size.isValid() and not target_size.isEmpty()
            else source.size
        )
        source.draft(None, target)
        source.thumbnail(
            target,
            Image.Resampling.LANCZOS,
            reducing_gap=3.0,
        )
        oriented = ImageOps.exif_transpose(source)
        if oriented.mode not in {"RGB", "RGBA"}:
            oriented = oriented.convert("RGBA")
        pixmap = QPixmap.fromImage(ImageQt(oriented))
    if pixmap.isNull():
        raise OSError("无法创建图片预览")
    return _fit_pixmap(pixmap, target_size), source_size, image_format


def _fit_pixmap(pixmap: QPixmap, target_size: QSize) -> QPixmap:
    if (
        pixmap.isNull()
        or not target_size.isValid()
        or target_size.isEmpty()
        or (
            pixmap.width() <= target_size.width()
            and pixmap.height() <= target_size.height()
        )
    ):
        return pixmap
    return pixmap.scaled(
        target_size,
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation,
    )


__all__ = [
    "DEFAULT_PREVIEW_PIXEL_BUDGET",
    "BoundedRasterResult",
    "load_bounded_raster",
    "raster_source_size",
]
