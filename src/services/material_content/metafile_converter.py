"""Bounded deterministic WMF/EMF rasterization for content artifacts."""

from __future__ import annotations

from io import BytesIO
import warnings

from PIL import Image, UnidentifiedImageError


DEFAULT_METAFILE_DPI = 144
DEFAULT_MAX_METAFILE_PIXELS = 40_000_000


class MetafileConversionError(ValueError):
    pass


def convert_metafile_to_png(
    payload: bytes,
    *,
    max_pixels: int = DEFAULT_MAX_METAFILE_PIXELS,
    dpi: int = DEFAULT_METAFILE_DPI,
) -> tuple[bytes, int, int]:
    """Rasterize one metafile without shelling out or retaining metadata."""

    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    if isinstance(max_pixels, bool) or int(max_pixels) < 1:
        raise ValueError("max_pixels must be a positive integer")
    if isinstance(dpi, bool) or not 72 <= int(dpi) <= 600:
        raise ValueError("dpi must be between 72 and 600")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload)) as source:
                if str(source.format or "").upper() not in {"WMF", "EMF"}:
                    raise MetafileConversionError("payload is not a WMF/EMF image")
                source.load(dpi=int(dpi))
                width, height = source.size
                if width < 1 or height < 1 or width * height > int(max_pixels):
                    raise MetafileConversionError("metafile exceeds the pixel limit")
                raster = source.convert("RGBA")
    except MetafileConversionError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning) as exc:
        raise MetafileConversionError("metafile could not be rasterized") from exc
    output = BytesIO()
    raster.save(
        output,
        format="PNG",
        optimize=False,
        compress_level=9,
    )
    normalized = output.getvalue()
    try:
        with Image.open(BytesIO(normalized)) as verification:
            verification.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:  # pragma: no cover
        raise MetafileConversionError("rasterized PNG failed verification") from exc
    return normalized, width, height


__all__ = [
    "DEFAULT_MAX_METAFILE_PIXELS",
    "DEFAULT_METAFILE_DPI",
    "MetafileConversionError",
    "convert_metafile_to_png",
]
