from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from src.services.material_content.source_capture import (
    ContentSourceCaptureError,
    capture_content_source,
)


def test_source_that_keeps_changing_returns_one_stable_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "changing.md"
    source.write_text("body", encoding="utf-8")
    calls = 0

    def changing_identity(_stat):
        nonlocal calls
        calls += 1
        return (0, 0, 4, calls)

    monkeypatch.setattr(
        "src.services.material_content.source_capture._stat_identity",
        changing_identity,
    )

    with pytest.raises(ContentSourceCaptureError) as raised:
        capture_content_source(source, attempts=3)

    assert raised.value.code == "source_not_stable"
    assert calls == 6


def test_capture_freezes_source_bytes_and_identity(tmp_path) -> None:
    source = tmp_path / "content.docx"
    source.write_bytes(b"docx-bytes")

    captured = capture_content_source(source)
    source.unlink()

    assert captured.payload == b"docx-bytes"
    assert captured.sha256 == sha256(b"docx-bytes").hexdigest()
    assert captured.byte_size == len(b"docx-bytes")
    assert captured.source_format == "docx"
    assert captured.original_name == "content.docx"


def test_capture_rejects_unsupported_and_oversized_sources(tmp_path) -> None:
    unsupported = tmp_path / "content.pdf"
    unsupported.write_bytes(b"pdf")
    with pytest.raises(ContentSourceCaptureError) as raised:
        capture_content_source(unsupported)
    assert raised.value.code == "source_extension_not_allowed"

    source = tmp_path / "content.md"
    source.write_bytes(b"12345")
    with pytest.raises(ContentSourceCaptureError) as raised:
        capture_content_source(source, max_bytes=4)
    assert raised.value.code == "source_too_large"
