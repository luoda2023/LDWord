"""Shared bounded, non-networked reader for OOXML content packages."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Mapping
from zipfile import BadZipFile, LargeZipFile, ZipFile

from lxml import etree


@dataclass(frozen=True, slots=True)
class DocxPackageLimits:
    max_source_bytes: int = 128 * 1024 * 1024
    max_members: int = 2048
    max_member_bytes: int = 32 * 1024 * 1024
    max_total_uncompressed_bytes: int = 256 * 1024 * 1024
    max_compression_ratio: float = 200.0
    max_xml_bytes: int = 16 * 1024 * 1024
    max_xml_nodes: int = 500_000
    max_xml_depth: int = 128

    def __post_init__(self) -> None:
        for name in (
            "max_source_bytes",
            "max_members",
            "max_member_bytes",
            "max_total_uncompressed_bytes",
            "max_xml_bytes",
            "max_xml_nodes",
            "max_xml_depth",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or int(value) < 1:
                raise ValueError(f"{name} must be a positive integer")
        if isinstance(self.max_compression_ratio, bool) or float(
            self.max_compression_ratio
        ) < 1:
            raise ValueError("max_compression_ratio must be at least 1")


class DocxPackageError(ValueError):
    """Stable package failure that is safe to project as one root finding."""

    def __init__(self, code: str, message: str, *, part: str = "") -> None:
        self.code = str(code or "").strip()
        self.part = str(part or "").strip()
        super().__init__(message)


class SafeDocxPackage:
    """An in-memory package whose members passed all configured limits."""

    def __init__(
        self,
        parts: Mapping[str, bytes],
        *,
        limits: DocxPackageLimits,
        source_sha256: str = "",
        source_size: int = 0,
    ) -> None:
        self._parts = MappingProxyType(dict(parts))
        self.limits = limits
        self.source_sha256 = str(source_sha256 or "")
        self.source_size = int(source_size)

    @property
    def part_names(self) -> tuple[str, ...]:
        return tuple(self._parts)

    @property
    def parts(self) -> Mapping[str, bytes]:
        return self._parts

    def has_part(self, part: str) -> bool:
        return str(part) in self._parts

    def read_part(self, part: str) -> bytes:
        try:
            return self._parts[str(part)]
        except KeyError as exc:
            raise DocxPackageError(
                "package_part_missing",
                f"OOXML part is missing: {part}",
                part=str(part),
            ) from exc

    def parse_xml(self, part: str) -> etree._Element:
        payload = self.read_part(part)
        if len(payload) > self.limits.max_xml_bytes:
            raise DocxPackageError(
                "xml_part_too_large",
                f"XML part exceeds the {self.limits.max_xml_bytes} byte limit",
                part=part,
            )
        if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
            raise DocxPackageError(
                "xml_doctype_forbidden",
                "XML document types and entity declarations are not allowed",
                part=part,
            )
        parser = etree.XMLParser(
            resolve_entities=False,
            no_network=True,
            load_dtd=False,
            recover=False,
            huge_tree=False,
            remove_blank_text=False,
        )
        try:
            root = etree.fromstring(payload, parser=parser)
        except (etree.XMLSyntaxError, ValueError) as exc:
            raise DocxPackageError(
                "xml_malformed",
                "OOXML part is not well-formed XML",
                part=part,
            ) from exc
        docinfo = root.getroottree().docinfo
        if docinfo.doctype or docinfo.internalDTD is not None:
            raise DocxPackageError(
                "xml_doctype_forbidden",
                "XML document types and entity declarations are not allowed",
                part=part,
            )
        node_count = 0
        stack: list[tuple[etree._Element, int]] = [(root, 1)]
        while stack:
            node, depth = stack.pop()
            node_count += 1
            if node_count > self.limits.max_xml_nodes:
                raise DocxPackageError(
                    "xml_node_limit_exceeded",
                    "OOXML part contains too many XML nodes",
                    part=part,
                )
            if depth > self.limits.max_xml_depth:
                raise DocxPackageError(
                    "xml_depth_limit_exceeded",
                    "OOXML part exceeds the XML nesting limit",
                    part=part,
                )
            stack.extend((child, depth + 1) for child in node)
        return root

    def validate_xml_parts(self) -> None:
        """Parse every XML-bearing package part with the bounded safe parser."""

        for part in sorted(self.part_names, key=str.casefold):
            if part.casefold().endswith((".xml", ".rels")):
                self.parse_xml(part)

    @classmethod
    def open(
        cls,
        payload: bytes,
        *,
        limits: DocxPackageLimits | None = None,
    ) -> "SafeDocxPackage":
        if not isinstance(payload, bytes):
            raise TypeError("payload must be bytes")
        active_limits = limits or DocxPackageLimits()
        if len(payload) > active_limits.max_source_bytes:
            raise DocxPackageError(
                "source_too_large",
                f"DOCX exceeds the {active_limits.max_source_bytes} byte limit",
            )
        try:
            with ZipFile(BytesIO(payload), "r", allowZip64=True) as archive:
                infos = [item for item in archive.infolist() if not item.is_dir()]
                if len(infos) > active_limits.max_members:
                    raise DocxPackageError(
                        "zip_member_limit_exceeded",
                        "DOCX package contains too many members",
                    )
                names: set[str] = set()
                total_size = 0
                for info in infos:
                    name = _safe_part_name(info.filename)
                    folded = name.casefold()
                    if folded in names:
                        raise DocxPackageError(
                            "zip_duplicate_member",
                            "DOCX package contains duplicate member names",
                            part=name,
                        )
                    names.add(folded)
                    if info.flag_bits & 0x1:
                        raise DocxPackageError(
                            "zip_encrypted_member",
                            "Encrypted DOCX package members are not supported",
                            part=name,
                        )
                    if info.file_size > active_limits.max_member_bytes:
                        raise DocxPackageError(
                            "zip_member_too_large",
                            "DOCX package member exceeds the size limit",
                            part=name,
                        )
                    total_size += info.file_size
                    if total_size > active_limits.max_total_uncompressed_bytes:
                        raise DocxPackageError(
                            "zip_total_size_exceeded",
                            "DOCX package exceeds the total uncompressed size limit",
                        )
                    ratio = _compression_ratio(info.file_size, info.compress_size)
                    if ratio > active_limits.max_compression_ratio:
                        raise DocxPackageError(
                            "zip_compression_ratio_exceeded",
                            "DOCX package member exceeds the compression-ratio limit",
                            part=name,
                        )
                parts: dict[str, bytes] = {}
                for info in infos:
                    name = _safe_part_name(info.filename)
                    with archive.open(info, "r") as stream:
                        member = stream.read(active_limits.max_member_bytes + 1)
                    if len(member) > active_limits.max_member_bytes:
                        raise DocxPackageError(
                            "zip_member_too_large",
                            "DOCX package member exceeds the size limit",
                            part=name,
                        )
                    if len(member) != info.file_size:
                        raise DocxPackageError(
                            "zip_member_size_mismatch",
                            "DOCX package member size does not match its directory entry",
                            part=name,
                        )
                    parts[name] = member
        except DocxPackageError:
            raise
        except (BadZipFile, LargeZipFile, OSError, RuntimeError) as exc:
            raise DocxPackageError(
                "zip_invalid",
                "Source is not a readable DOCX ZIP package",
            ) from exc
        return cls(
            parts,
            limits=active_limits,
            source_sha256=sha256(payload).hexdigest(),
            source_size=len(payload),
        )

    @classmethod
    def open_path(
        cls,
        path: str | Path,
        *,
        limits: DocxPackageLimits | None = None,
    ) -> "SafeDocxPackage":
        """Capture one stable, bounded file descriptor before opening OOXML.

        The size check happens both before and during the read.  Descriptor
        metadata is checked again afterwards so an in-place mutation cannot be
        mistaken for one immutable source capture.
        """

        active_limits = limits or DocxPackageLimits()
        payload = capture_bounded_file(path, limits=active_limits)
        return cls.open(payload, limits=active_limits)


def capture_bounded_file(
    path: str | Path,
    *,
    limits: DocxPackageLimits | None = None,
) -> bytes:
    """Return one bounded source snapshot captured from a stable descriptor."""

    active_limits = limits or DocxPackageLimits()
    source = Path(path)
    try:
        with source.open("rb") as stream:
            before = os.fstat(stream.fileno())
            if before.st_size > active_limits.max_source_bytes:
                raise DocxPackageError(
                    "source_too_large",
                    f"DOCX exceeds the {active_limits.max_source_bytes} byte limit",
                )
            payload = stream.read(active_limits.max_source_bytes + 1)
            after = os.fstat(stream.fileno())
    except DocxPackageError:
        raise
    except OSError as exc:
        raise DocxPackageError(
            "source_unreadable",
            "Source DOCX cannot be read",
        ) from exc
    if len(payload) > active_limits.max_source_bytes:
        raise DocxPackageError(
            "source_too_large",
            f"DOCX exceeds the {active_limits.max_source_bytes} byte limit",
        )
    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    )
    if before_identity != after_identity or len(payload) != after.st_size:
        raise DocxPackageError(
            "source_changed_during_read",
            "Source DOCX changed while it was being captured",
        )
    return payload


def _safe_part_name(value: str) -> str:
    raw = str(value or "")
    if not raw or "\\" in raw or "\x00" in raw:
        raise DocxPackageError(
            "zip_unsafe_member_path",
            "DOCX package contains an unsafe member path",
            part=raw,
        )
    path = PurePosixPath(raw)
    if (
        raw.startswith("/")
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or ":" in path.parts[0]
    ):
        raise DocxPackageError(
            "zip_unsafe_member_path",
            "DOCX package contains an unsafe member path",
            part=raw,
        )
    return path.as_posix()


def _compression_ratio(file_size: int, compressed_size: int) -> float:
    if file_size == 0:
        return 1.0
    if compressed_size <= 0:
        return float("inf")
    return file_size / compressed_size


__all__ = [
    "DocxPackageError",
    "DocxPackageLimits",
    "SafeDocxPackage",
    "capture_bounded_file",
]
