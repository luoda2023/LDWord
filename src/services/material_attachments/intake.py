"""Byte-validated intake for files that remain delivery attachments."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from src.config.attachment_materials import (
    AttachmentBinding,
    AttachmentCardinality,
    AttachmentItem,
    AttachmentProcessingMode,
    AttachmentSourceKind,
    attachment_natural_path_key,
    normalize_attachment_relative_path,
)
from src.config.content_materials import FileAssetRef
from src.shared.io.safe_docx_package import (
    DocxPackageError,
    DocxPackageLimits,
    SafeDocxPackage,
    capture_bounded_file,
)


_DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
_XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
_XLS_MEDIA_TYPE = "application/vnd.ms-excel"
_MAX_ATTACHMENT_SOURCE_BYTES = 128 * 1024 * 1024
_IMAGE_FORMATS = {
    "PNG": ("image/png", {".png"}),
    "JPEG": ("image/jpeg", {".jpg", ".jpeg"}),
    "WEBP": ("image/webp", {".webp"}),
    "TIFF": ("image/tiff", {".tif", ".tiff"}),
    "BMP": ("image/bmp", {".bmp"}),
}
_KIND_EXTENSIONS = {
    "image": frozenset(ext for _mime, exts in _IMAGE_FORMATS.values() for ext in exts),
    "pdf": frozenset({".pdf"}),
    "docx": frozenset({".docx"}),
    "xlsx": frozenset({".xlsx", ".xls"}),
    "csv": frozenset({".csv"}),
    "markdown": frozenset({".md", ".markdown"}),
    "md": frozenset({".md", ".markdown"}),
    "txt": frozenset({".txt"}),
}
_KIND_MEDIA_TYPES = {
    "image": ("image/*",),
    "pdf": ("application/pdf",),
    "docx": (_DOCX_MEDIA_TYPE,),
    "xlsx": (_XLSX_MEDIA_TYPE, _XLS_MEDIA_TYPE),
    "csv": ("text/csv",),
    "markdown": ("text/markdown",),
    "md": ("text/markdown",),
    "txt": ("text/plain",),
}


class AttachmentIntakeError(ValueError):
    """Stable intake failure; no attachment binding is created."""


def inspect_attachment_file(
    source_path: str | Path,
    *,
    accepted_types: tuple[str, ...] | list[str],
) -> FileAssetRef:
    """Validate suffix and bytes, then return an immutable file identity."""

    source = Path(source_path)
    if not source.exists():
        raise AttachmentIntakeError(f"attachment_source_missing:{source}")
    if not source.is_file():
        raise AttachmentIntakeError(f"attachment_source_not_file:{source}")
    kinds = _normalized_types(accepted_types)
    allowed_extensions = frozenset(
        extension
        for kind in kinds
        for extension in _KIND_EXTENSIONS.get(kind, frozenset({f".{kind}"}))
    )
    extension = source.suffix.casefold()
    if extension not in allowed_extensions:
        raise AttachmentIntakeError(
            f"attachment_extension_not_allowed:{extension or '<none>'}"
        )
    try:
        raw = capture_bounded_file(
            source,
            limits=DocxPackageLimits(
                max_source_bytes=_MAX_ATTACHMENT_SOURCE_BYTES,
            ),
        )
    except DocxPackageError as exc:
        raise AttachmentIntakeError(f"attachment_{exc.code}:{source}") from exc
    media_type = _detect_media_type(source, raw, kinds)
    return FileAssetRef(
        source_path=str(source.resolve()),
        original_name=source.name,
        media_type=media_type,
        content_sha256=sha256(raw).hexdigest(),
        byte_size=len(raw),
    )


def attachment_extensions_for_types(
    accepted_types: tuple[str, ...] | list[str],
) -> tuple[str, ...]:
    """Return the intake-owned extension allow-list for UI acquisition hints."""

    kinds = _normalized_types(accepted_types)
    return tuple(
        sorted(
            {
                extension
                for kind in kinds
                for extension in _KIND_EXTENSIONS.get(
                    kind,
                    frozenset({f".{kind}"}),
                )
            }
        )
    )


def build_single_attachment_binding(
    *,
    role: str,
    source_path: str | Path,
    accepted_types: tuple[str, ...] | list[str],
    required: bool = False,
    label: str = "",
    processing_mode: AttachmentProcessingMode | str = (
        AttachmentProcessingMode.PASSTHROUGH
    ),
) -> AttachmentBinding:
    """Build one single-cardinality delivery binding after byte validation."""

    return build_attachment_binding(
        role=role,
        source_paths=(source_path,),
        accepted_types=accepted_types,
        cardinality=AttachmentCardinality.SINGLE,
        required=required,
        min_items=1 if required else 0,
        max_items=1,
        label=label,
        source_kind=AttachmentSourceKind.SINGLE_FILE,
        processing_mode=processing_mode,
    )


def build_attachment_binding(
    *,
    role: str,
    source_paths: tuple[str | Path, ...] | list[str | Path],
    accepted_types: tuple[str, ...] | list[str],
    cardinality: AttachmentCardinality | str = AttachmentCardinality.MULTIPLE,
    required: bool = False,
    min_items: int = 0,
    max_items: int | None = None,
    label: str = "",
    source_kind: AttachmentSourceKind | str | None = None,
    processing_mode: AttachmentProcessingMode | str = (
        AttachmentProcessingMode.PASSTHROUGH
    ),
) -> AttachmentBinding:
    """Build a single file or flat file-set binding atomically."""

    kinds = _normalized_types(accepted_types)
    try:
        resolved_cardinality = (
            cardinality
            if isinstance(cardinality, AttachmentCardinality)
            else AttachmentCardinality(str(cardinality))
        )
    except ValueError as exc:
        raise AttachmentIntakeError("attachment_cardinality_invalid") from exc
    if source_kind is None:
        resolved_source_kind = (
            AttachmentSourceKind.SINGLE_FILE
            if resolved_cardinality is AttachmentCardinality.SINGLE
            else AttachmentSourceKind.FILE_SET
        )
    else:
        try:
            resolved_source_kind = (
                source_kind
                if isinstance(source_kind, AttachmentSourceKind)
                else AttachmentSourceKind(str(source_kind))
            )
        except ValueError as exc:
            raise AttachmentIntakeError("attachment_source_kind_invalid") from exc
    if resolved_source_kind is AttachmentSourceKind.DIRECTORY_PACKAGE:
        raise AttachmentIntakeError("use_directory_attachment_binding")
    expected_cardinality = (
        AttachmentCardinality.SINGLE
        if resolved_source_kind is AttachmentSourceKind.SINGLE_FILE
        else AttachmentCardinality.MULTIPLE
    )
    if resolved_cardinality is not expected_cardinality:
        raise AttachmentIntakeError("attachment_source_kind_cardinality_conflict")
    paths = tuple(source_paths or ())
    if resolved_cardinality is AttachmentCardinality.SINGLE and len(paths) > 1:
        raise AttachmentIntakeError("single_attachment_accepts_one_file")
    file_refs = tuple(
        inspect_attachment_file(path, accepted_types=kinds) for path in paths
    )
    extensions, media_types = _contracts_for_types(kinds)
    items = tuple(
        AttachmentItem(
            item_id=_attachment_item_id(role, file_ref.original_name),
            file_ref=file_ref,
            label=label,
            sequence=sequence,
            relative_path=file_ref.original_name,
        )
        for sequence, file_ref in enumerate(file_refs)
    )
    try:
        return AttachmentBinding(
            role=role,
            label=label,
            source_kind=resolved_source_kind,
            source_path=(
                file_refs[0].source_path
                if file_refs
                and resolved_source_kind is AttachmentSourceKind.SINGLE_FILE
                else ""
            ),
            processing_mode=processing_mode,
            cardinality=resolved_cardinality,
            items=items,
            required=required,
            min_items=max(int(min_items), 1 if required else 0),
            max_items=(
                1
                if resolved_cardinality is AttachmentCardinality.SINGLE
                else max_items
            ),
            accepted_media_types=media_types,
            accepted_extensions=extensions,
        )
    except (TypeError, ValueError) as exc:
        raise AttachmentIntakeError(str(exc)) from exc


def build_directory_attachment_binding(
    *,
    role: str,
    source_directory: str | Path,
    accepted_types: tuple[str, ...] | list[str],
    recursive: bool = True,
    processing_mode: AttachmentProcessingMode | str = (
        AttachmentProcessingMode.PASSTHROUGH
    ),
    required: bool = False,
    min_items: int = 0,
    max_items: int | None = None,
    label: str = "",
) -> AttachmentBinding:
    """Enumerate and byte-validate one directory package without flattening it."""

    if not isinstance(recursive, bool):
        raise AttachmentIntakeError("attachment_recursive_invalid")
    root = Path(source_directory).expanduser()
    try:
        root = root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise AttachmentIntakeError(
            f"attachment_directory_missing:{source_directory}"
        ) from exc
    if not root.is_dir():
        raise AttachmentIntakeError(f"attachment_source_not_directory:{root}")
    if _is_link_or_reparse(root):
        raise AttachmentIntakeError(f"attachment_directory_link_forbidden:{root}")

    kinds = _normalized_types(accepted_types)
    paths = _enumerate_directory_files(root, recursive=recursive)
    entries = tuple(
        sorted(
            (
                (
                    normalize_attachment_relative_path(
                        path.relative_to(root).as_posix()
                    ),
                    path,
                )
                for path in paths
            ),
            key=lambda item: attachment_natural_path_key(item[0]),
        )
    )
    file_refs = tuple(
        inspect_attachment_file(path, accepted_types=kinds)
        for _relative_path, path in entries
    )
    extensions, media_types = _contracts_for_types(kinds)
    items = tuple(
        AttachmentItem(
            item_id=_attachment_item_id(role, relative_path),
            file_ref=file_ref,
            label=label,
            sequence=sequence,
            relative_path=relative_path,
        )
        for sequence, ((relative_path, _path), file_ref) in enumerate(
            zip(entries, file_refs, strict=True)
        )
    )
    try:
        return AttachmentBinding(
            role=role,
            label=label,
            source_kind=AttachmentSourceKind.DIRECTORY_PACKAGE,
            source_path=str(root),
            recursive=recursive,
            processing_mode=processing_mode,
            cardinality=AttachmentCardinality.MULTIPLE,
            items=items,
            required=required,
            min_items=max(int(min_items), 1 if required else 0),
            max_items=max_items,
            accepted_media_types=media_types,
            accepted_extensions=extensions,
        )
    except (TypeError, ValueError) as exc:
        raise AttachmentIntakeError(str(exc)) from exc


def _enumerate_directory_files(root: Path, *, recursive: bool) -> tuple[Path, ...]:
    files: list[Path] = []
    if not recursive:
        try:
            entries = tuple(root.iterdir())
        except OSError as exc:
            raise AttachmentIntakeError(
                f"attachment_directory_unreadable:{root}"
            ) from exc
        for entry in entries:
            if _is_link_or_reparse(entry):
                raise AttachmentIntakeError(
                    f"attachment_directory_link_forbidden:{entry}"
                )
            if _is_transient_package_file(entry.name):
                continue
            if entry.is_file():
                files.append(_resolved_within(entry, root))
        return tuple(files)

    def onerror(error: OSError) -> None:
        raise AttachmentIntakeError(
            f"attachment_directory_unreadable:{error.filename or root}"
        ) from error

    for current_text, directory_names, file_names in os.walk(
        root,
        topdown=True,
        onerror=onerror,
        followlinks=False,
    ):
        current = Path(current_text)
        for name in tuple(directory_names):
            directory = current / name
            if _is_link_or_reparse(directory):
                raise AttachmentIntakeError(
                    f"attachment_directory_link_forbidden:{directory}"
                )
            _resolved_within(directory, root)
        for name in file_names:
            candidate = current / name
            if _is_link_or_reparse(candidate):
                raise AttachmentIntakeError(
                    f"attachment_directory_link_forbidden:{candidate}"
                )
            if _is_transient_package_file(name):
                continue
            files.append(_resolved_within(candidate, root))
    return tuple(files)


def _is_transient_package_file(name: str) -> bool:
    """Ignore only well-known editor lock files, never arbitrary hidden files."""

    normalized = str(name or "").strip()
    return normalized.startswith("~$") or (
        normalized.startswith(".~lock.") and normalized.endswith("#")
    )


def _resolved_within(path: Path, root: Path) -> Path:
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise AttachmentIntakeError(
            f"attachment_directory_path_escape:{path}"
        ) from exc
    return resolved


def _is_link_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
        attributes = getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0)
        return bool(attributes & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT
    except OSError as exc:
        raise AttachmentIntakeError(f"attachment_source_unreadable:{path}") from exc


def _attachment_item_id(role: str, relative_path: str) -> str:
    normalized_role = str(role or "").strip()
    normalized_path = normalize_attachment_relative_path(relative_path)
    digest = sha256(
        f"{normalized_role}\0{normalized_path.casefold()}".encode("utf-8")
    ).hexdigest()
    return f"{normalized_role}:{digest[:24]}"


def _contracts_for_types(
    kinds: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    extensions = tuple(
        sorted(
            {
                extension
                for kind in kinds
                for extension in _KIND_EXTENSIONS.get(
                    kind, frozenset({f".{kind}"})
                )
            }
        )
    )
    media_types = tuple(
        sorted(
            {
                media_type
                for kind in kinds
                for media_type in _KIND_MEDIA_TYPES.get(
                    kind, ("application/octet-stream",)
                )
            }
        )
    )
    return extensions, media_types


def _normalized_types(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    normalized = tuple(
        dict.fromkeys(
            str(item or "").strip().casefold()
            for item in tuple(values or ())
            if str(item or "").strip()
        )
    )
    if not normalized:
        raise AttachmentIntakeError("attachment_accepted_types_empty")
    return normalized


def _detect_media_type(source: Path, raw: bytes, kinds: tuple[str, ...]) -> str:
    extension = source.suffix.casefold()
    if extension in _KIND_EXTENSIONS["image"]:
        try:
            with Image.open(BytesIO(raw)) as image:
                image_format = str(image.format or "").upper()
                image.verify()
        except (OSError, UnidentifiedImageError, ValueError) as exc:
            raise AttachmentIntakeError("attachment_image_bytes_invalid") from exc
        contract = _IMAGE_FORMATS.get(image_format)
        if contract is None or extension not in contract[1]:
            raise AttachmentIntakeError("attachment_image_extension_mismatch")
        return contract[0]
    if extension == ".pdf":
        if not raw.startswith(b"%PDF-"):
            raise AttachmentIntakeError("attachment_pdf_bytes_invalid")
        return "application/pdf"
    if extension in {".docx", ".xlsx"}:
        try:
            package = SafeDocxPackage.open(raw)
            names = set(package.part_names)
            expected = "word/document.xml" if extension == ".docx" else "xl/workbook.xml"
            package.parse_xml(expected)
        except (DocxPackageError, OSError, RuntimeError) as exc:
            raise AttachmentIntakeError("attachment_openxml_package_invalid") from exc
        if "[Content_Types].xml" not in names or expected not in names:
            raise AttachmentIntakeError("attachment_openxml_kind_mismatch")
        return _DOCX_MEDIA_TYPE if extension == ".docx" else _XLSX_MEDIA_TYPE
    if extension == ".xls":
        if not raw.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
            raise AttachmentIntakeError("attachment_xls_bytes_invalid")
        return _XLS_MEDIA_TYPE
    if extension == ".csv":
        return "text/csv"
    if extension in {".md", ".markdown"}:
        return "text/markdown"
    if extension == ".txt":
        return "text/plain"
    kind = next((item for item in kinds if extension == f".{item}"), "")
    if not kind:
        raise AttachmentIntakeError("attachment_type_detection_failed")
    return "application/octet-stream"


__all__ = [
    "AttachmentIntakeError",
    "attachment_extensions_for_types",
    "build_attachment_binding",
    "build_directory_attachment_binding",
    "build_single_attachment_binding",
    "inspect_attachment_file",
]
