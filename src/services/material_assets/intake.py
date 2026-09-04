"""Convert resolved UI image assets into content-addressed Freeze inputs."""

from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path

from src.config.content_materials import FileAssetRef
from src.config.image_materials import ImageMaterialRule, ImageSourceItem
from src.config.materials import AssetItem, IMAGE_EXTENSIONS


_MEDIA_BY_EXTENSION = {
    ".bmp": "image/bmp",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".webp": "image/webp",
}


class ImageMaterialIntakeError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        role: str = "",
        item_id: str = "",
        path: str = "",
    ) -> None:
        self.code = str(code)
        self.role = str(role)
        self.item_id = str(item_id)
        self.path = str(path)
        super().__init__(str(message))


def build_image_source_items(
    asset_items: Sequence[AssetItem],
    rules: Sequence[ImageMaterialRule],
) -> tuple[ImageSourceItem, ...]:
    """Build deterministic source facts only for roles owned by new image rules."""

    typed_rules = tuple(rules or ())
    if any(not isinstance(item, ImageMaterialRule) for item in typed_rules):
        raise TypeError("rules must contain ImageMaterialRule values")
    typed_assets = tuple(asset_items or ())
    if any(not isinstance(item, AssetItem) for item in typed_assets):
        raise TypeError("asset_items must contain AssetItem values")
    owned_roles = {rule.source_role for rule in typed_rules}
    selected: dict[str, list[tuple[int, AssetItem]]] = {
        role: [] for role in owned_roles
    }
    for source_index, item in enumerate(typed_assets):
        role = str(item.role or "").strip()
        if role in selected:
            selected[role].append((source_index, item))

    results: list[ImageSourceItem] = []
    seen_item_ids: set[str] = set()
    for role in sorted(selected, key=str.casefold):
        indexed = sorted(selected[role], key=_asset_sort_key)
        used_sequences: set[int] = set()
        for _source_index, item in indexed:
            if item.sequence is not None:
                if item.sequence < 0 or item.sequence in used_sequences:
                    raise ImageMaterialIntakeError(
                        "image_sequence_duplicate",
                        f"role {role!r} has invalid or duplicate sequence {item.sequence}",
                        role=role,
                        item_id=item.item_id,
                        path=item.path,
                    )
                used_sequences.add(item.sequence)
        next_sequence = 0
        for _source_index, item in indexed:
            path = Path(str(item.path or item.source_path or "").strip()).expanduser()
            if not path.is_file() or path.is_symlink():
                raise ImageMaterialIntakeError(
                    "image_source_missing",
                    "selected image source is not a regular file",
                    role=role,
                    item_id=item.item_id,
                    path=str(path),
                )
            suffix = path.suffix.casefold()
            if suffix not in IMAGE_EXTENSIONS or suffix not in _MEDIA_BY_EXTENSION:
                raise ImageMaterialIntakeError(
                    "image_extension_not_allowed",
                    f"selected source extension {suffix or '<none>'!r} is not an image",
                    role=role,
                    item_id=item.item_id,
                    path=str(path),
                )
            payload = path.read_bytes()
            digest = sha256(payload).hexdigest()
            declared_hash = str(item.content_hash or "").strip().casefold()
            if declared_hash.startswith("sha256:"):
                declared_hash = declared_hash.removeprefix("sha256:")
            if declared_hash and declared_hash != digest:
                raise ImageMaterialIntakeError(
                    "image_source_hash_mismatch",
                    "selected image changed after asset resolution",
                    role=role,
                    item_id=item.item_id,
                    path=str(path),
                )
            actual_media = _MEDIA_BY_EXTENSION[suffix]
            declared_media = str(item.mime_type or "").split(";", 1)[0].strip().casefold()
            if declared_media and declared_media not in {
                actual_media,
                "image/jpg" if actual_media == "image/jpeg" else actual_media,
                "image/x-ms-bmp" if actual_media == "image/bmp" else actual_media,
            }:
                raise ImageMaterialIntakeError(
                    "image_mime_extension_mismatch",
                    "declared image MIME does not match the selected extension",
                    role=role,
                    item_id=item.item_id,
                    path=str(path),
                )
            sequence = item.sequence
            if sequence is None:
                while next_sequence in used_sequences:
                    next_sequence += 1
                sequence = next_sequence
                used_sequences.add(sequence)
                next_sequence += 1
            item_id = str(item.item_id or "").strip() or (
                f"{role}-{sequence}-{digest[:12]}"
            )
            if item_id in seen_item_ids:
                raise ImageMaterialIntakeError(
                    "image_item_id_duplicate",
                    f"image item_id {item_id!r} is not unique",
                    role=role,
                    item_id=item_id,
                    path=str(path),
                )
            seen_item_ids.add(item_id)
            results.append(
                ImageSourceItem(
                    role=role,
                    item_id=item_id,
                    sequence=sequence,
                    image_ref=FileAssetRef(
                        source_path=str(path.resolve()),
                        original_name=path.name,
                        media_type=actual_media,
                        content_sha256=digest,
                        byte_size=len(payload),
                    ),
                )
            )
    return tuple(results)


def _asset_sort_key(pair: tuple[int, AssetItem]) -> tuple[object, ...]:
    source_index, item = pair
    return (
        0 if item.sequence is not None else 1,
        item.sequence if item.sequence is not None else 0,
        str(
            item.original_relative_path
            or item.normalized_name
            or item.path
            or item.source_path
        ).casefold(),
        str(item.item_id or "").casefold(),
        source_index,
    )


__all__ = [
    "ImageMaterialIntakeError",
    "build_image_source_items",
]
