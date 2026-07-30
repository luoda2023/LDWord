from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from docx import Document as open_document

import src.pipeline.runner as runner_module
from src.config.resolver import resolve_config
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig
from src.pipeline.runner import Pipeline
from src.shared.io.safe_docx_package import DocxPackageError


def _zip(entries: list[tuple[str, bytes]]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, payload in entries:
            archive.writestr(name, payload)
    return output.getvalue()


def _pipeline(tmp_path: Path) -> Pipeline:
    return Pipeline(
        modules=[],
        config=resolve_config(TemplateConfig(), SceneWorkspace()),
        output_dir=str(tmp_path / "out"),
    )


def _assert_no_document_or_output(
    tmp_path: Path,
    monkeypatch,
    *,
    source_payload: bytes,
    expected_error: str,
) -> None:
    source = tmp_path / "unsafe.docx"
    source.write_bytes(source_payload)
    document_called = False

    def forbidden_document(_source):
        nonlocal document_called
        document_called = True
        raise AssertionError("Document must not receive an unsafe package")

    monkeypatch.setattr(runner_module, "Document", forbidden_document)

    result = _pipeline(tmp_path).execute(str(source))

    assert result.success is False
    assert result.error == expected_error
    assert document_called is False
    assert not (tmp_path / "out").exists()


def test_pipeline_rejects_high_compression_package_before_document(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _assert_no_document_or_output(
        tmp_path,
        monkeypatch,
        source_payload=_zip([("word/document.xml", b"A" * 1_000_000)]),
        expected_error="unsafe_docx_package:zip_compression_ratio_exceeded",
    )


@pytest.mark.parametrize(
    "declaration",
    (
        b"<!DOCTYPE root><root/>",
        b"<!ENTITY unsafe 'value'><root/>",
        "<!DOCTYPE root [<!ENTITY unsafe 'value'>]><root/>".encode("utf-16"),
    ),
)
def test_pipeline_rejects_doctype_or_entity_in_any_xml_part_before_document(
    tmp_path: Path,
    monkeypatch,
    declaration: bytes,
) -> None:
    _assert_no_document_or_output(
        tmp_path,
        monkeypatch,
        source_payload=_zip(
            [
                ("[Content_Types].xml", b"<Types/>"),
                ("_rels/.rels", b"<Relationships/>"),
                ("word/document.xml", b"<document/>"),
                ("customXml/unreferenced.xml", declaration),
            ]
        ),
        expected_error="unsafe_docx_package:xml_doctype_forbidden",
    )


@pytest.mark.parametrize(
    ("failure_stage", "code"),
    (
        ("capture", "source_too_large"),
        ("capture", "source_changed_during_read"),
        ("open", "zip_member_too_large"),
        ("open", "zip_total_size_exceeded"),
    ),
)
def test_pipeline_projects_stable_intake_limit_errors_before_document(
    tmp_path: Path,
    monkeypatch,
    failure_stage: str,
    code: str,
) -> None:
    source = tmp_path / "source.docx"
    source.write_bytes(b"source")

    def fail(*_args, **_kwargs):
        raise DocxPackageError(code, "internal diagnostic")

    if failure_stage == "capture":
        monkeypatch.setattr(runner_module, "capture_bounded_file", fail)
    else:
        monkeypatch.setattr(runner_module.SafeDocxPackage, "open", fail)

    document_called = False

    def forbidden_document(_source):
        nonlocal document_called
        document_called = True
        raise AssertionError("Document must not run after an intake failure")

    monkeypatch.setattr(runner_module, "Document", forbidden_document)

    result = _pipeline(tmp_path).execute(str(source))

    assert result.success is False
    assert result.error == f"unsafe_docx_package:{code}"
    assert "internal diagnostic" not in result.error
    assert document_called is False
    assert not (tmp_path / "out").exists()


def test_pipeline_uses_one_snapshot_for_document_and_object_preflight(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "valid.docx"
    document = open_document()
    document.add_paragraph("snapshot content")
    document.save(source)
    original_payload = source.read_bytes()
    expected_sha256 = sha256(original_payload).hexdigest()

    document_received_bytes_io = False
    preflight_received_snapshot = False
    real_inspect = runner_module.inspect_docx_package

    def document_from_snapshot(stream):
        nonlocal document_received_bytes_io
        document_received_bytes_io = isinstance(stream, BytesIO)
        loaded = open_document(stream)
        source.write_bytes(b"changed after the bounded snapshot")
        return loaded

    def inspect_snapshot(path, policy=None, *, safe_package=None):
        nonlocal preflight_received_snapshot
        preflight_received_snapshot = (
            safe_package is not None
            and safe_package.source_sha256 == expected_sha256
            and safe_package.source_size == len(original_payload)
        )
        return real_inspect(path, policy, safe_package=safe_package)

    monkeypatch.setattr(runner_module, "Document", document_from_snapshot)
    monkeypatch.setattr(runner_module, "inspect_docx_package", inspect_snapshot)

    result = _pipeline(tmp_path).execute(str(source))

    assert result.success is True
    assert document_received_bytes_io is True
    assert preflight_received_snapshot is True
    assert Path(result.output_paths["final"]).is_file()
