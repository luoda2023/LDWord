from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from src.shared.io.safe_docx_package import (
    capture_bounded_file,
    DocxPackageError,
    DocxPackageLimits,
    SafeDocxPackage,
)


def _zip(entries: list[tuple[str, bytes]]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, payload in entries:
            archive.writestr(name, payload)
    return output.getvalue()


def test_safe_package_reads_bounded_members_and_xml() -> None:
    payload = _zip(
        [
            ("[Content_Types].xml", b"<Types/>"),
            ("word/document.xml", b"<document><body/></document>"),
        ]
    )

    package = SafeDocxPackage.open(payload)

    assert package.part_names == ("[Content_Types].xml", "word/document.xml")
    assert package.parse_xml("word/document.xml").tag == "document"


@pytest.mark.parametrize("unsafe_name", ("../escape", "/absolute", "C:/drive"))
def test_package_rejects_path_traversal(unsafe_name: str) -> None:
    with pytest.raises(DocxPackageError) as raised:
        SafeDocxPackage.open(_zip([(unsafe_name, b"payload")]))
    assert raised.value.code == "zip_unsafe_member_path"


def test_package_rejects_duplicate_members() -> None:
    with pytest.warns(UserWarning, match="Duplicate name"):
        payload = _zip([("word/document.xml", b"one"), ("word/document.xml", b"two")])

    with pytest.raises(DocxPackageError) as raised:
        SafeDocxPackage.open(payload)
    assert raised.value.code == "zip_duplicate_member"


def test_package_rejects_case_insensitive_duplicate_members() -> None:
    payload = _zip(
        [
            ("word/document.xml", b"one"),
            ("WORD/DOCUMENT.XML", b"two"),
        ]
    )

    with pytest.raises(DocxPackageError) as raised:
        SafeDocxPackage.open(payload)
    assert raised.value.code == "zip_duplicate_member"


def test_open_path_captures_bounded_source_identity(tmp_path: Path) -> None:
    payload = _zip([("word/document.xml", b"<document/>")])
    source = tmp_path / "source.docx"
    source.write_bytes(payload)

    package = SafeDocxPackage.open_path(source)

    assert package.source_size == len(payload)
    assert len(package.source_sha256) == 64
    with pytest.raises(DocxPackageError) as raised:
        SafeDocxPackage.open_path(
            source,
            limits=DocxPackageLimits(max_source_bytes=len(payload) - 1),
        )
    assert raised.value.code == "source_too_large"


def test_package_rejects_excessive_compression_ratio() -> None:
    payload = _zip([("word/document.xml", b"A" * 100_000)])

    with pytest.raises(DocxPackageError) as raised:
        SafeDocxPackage.open(
            payload,
            limits=DocxPackageLimits(max_compression_ratio=2.0),
        )
    assert raised.value.code == "zip_compression_ratio_exceeded"


def test_package_rejects_member_and_total_size_limits() -> None:
    with pytest.raises(DocxPackageError) as member_error:
        SafeDocxPackage.open(
            _zip([("word/document.xml", b"1234")]),
            limits=DocxPackageLimits(max_member_bytes=3),
        )
    assert member_error.value.code == "zip_member_too_large"

    with pytest.raises(DocxPackageError) as total_error:
        SafeDocxPackage.open(
            _zip([("first.bin", b"1234"), ("second.bin", b"5678")]),
            limits=DocxPackageLimits(
                max_member_bytes=10,
                max_total_uncompressed_bytes=7,
            ),
        )
    assert total_error.value.code == "zip_total_size_exceeded"


def test_package_rejects_xml_depth_and_doctype() -> None:
    deep_xml = ("<n>" * 10 + "</n>" * 10).encode()
    package = SafeDocxPackage.open(
        _zip([("word/document.xml", deep_xml)]),
        limits=DocxPackageLimits(max_xml_depth=5),
    )
    with pytest.raises(DocxPackageError) as raised:
        package.parse_xml("word/document.xml")
    assert raised.value.code == "xml_depth_limit_exceeded"

    doctype = SafeDocxPackage.open(
        _zip([("word/document.xml", b"<!DOCTYPE x><x/>")])
    )
    with pytest.raises(DocxPackageError) as raised:
        doctype.parse_xml("word/document.xml")
    assert raised.value.code == "xml_doctype_forbidden"


@pytest.mark.parametrize("part", ("customXml/item.xml", "word/_rels/item.xml.rels"))
def test_package_validates_every_xml_and_relationship_part(part: str) -> None:
    package = SafeDocxPackage.open(
        _zip(
            [
                ("[Content_Types].xml", b"<Types/>"),
                ("_rels/.rels", b"<Relationships/>"),
                ("word/document.xml", b"<document/>"),
                (part, b"<!ENTITY unsafe 'value'><root/>")
            ]
        )
    )

    with pytest.raises(DocxPackageError) as raised:
        package.validate_xml_parts()
    assert raised.value.code == "xml_doctype_forbidden"
    assert raised.value.part == part


def test_capture_rejects_source_identity_change(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "changing.docx"
    source.write_bytes(_zip([("word/document.xml", b"<document/>")]))

    import src.shared.io.safe_docx_package as safe_docx_module

    real_fstat = safe_docx_module.os.fstat
    call_count = 0

    def changing_fstat(file_descriptor: int):
        nonlocal call_count
        call_count += 1
        stat = real_fstat(file_descriptor)
        if call_count != 2:
            return stat

        class ChangedStat:
            st_dev = stat.st_dev
            st_ino = stat.st_ino
            st_size = stat.st_size
            st_mtime_ns = stat.st_mtime_ns + 1

        return ChangedStat()

    monkeypatch.setattr(safe_docx_module.os, "fstat", changing_fstat)

    with pytest.raises(DocxPackageError) as raised:
        capture_bounded_file(source)
    assert raised.value.code == "source_changed_during_read"
