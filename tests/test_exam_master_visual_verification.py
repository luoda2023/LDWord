import json
from pathlib import Path

from PIL import Image

import src.shared.engine.exam_master_visual_verification as visual
import src.shared.engine.docx_page_renderer as docx_renderer
from src.shared.engine.docx_page_renderer import DocxPageRenderResult
from src.shared.engine.exam_master_visual_verification import (
    png_has_content,
    verify_exam_document_visual,
    verify_exam_master_sample_visual,
)


def test_exam_master_visual_verification_writes_docx_only_manifest(tmp_path):
    result = verify_exam_master_sample_visual(
        "default_exam",
        tmp_path,
        attempt_render=False,
    )

    assert result.status == "docx_only"
    assert result.sample_docx_path.is_file()
    assert result.manifest_path.is_file()

    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert payload["style_id"] == "default_exam"
    assert payload["status"] == "docx_only"
    assert payload["sample_docx_path"] == str(result.sample_docx_path)
    assert payload["issues"] == ["render_skipped"]


def test_exam_master_visual_verification_records_renderer_unavailable(
    monkeypatch,
    tmp_path,
):
    def unavailable(docx_path, _output_dir, *, attempt_render=True):
        del attempt_render
        return DocxPageRenderResult(
            status="renderer_unavailable",
            docx_path=Path(docx_path),
            issues=("docx_to_pdf_renderer_unavailable",),
        )

    monkeypatch.setattr(visual, "render_docx_pages", unavailable)

    result = verify_exam_master_sample_visual("default_exam", tmp_path)

    assert result.status == "renderer_unavailable"
    assert result.sample_docx_path.is_file()
    assert result.pdf_path is None
    assert result.png_paths == ()
    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert payload["status"] == "renderer_unavailable"
    assert payload["issues"] == ["docx_to_pdf_renderer_unavailable"]


def test_exam_master_visual_verification_records_pdf_and_png_evidence(
    monkeypatch,
    tmp_path,
):
    def fake_render(docx_path: Path, output_dir: Path, *, attempt_render=True):
        assert attempt_render is True
        pdf_path = output_dir / f"{docx_path.stem}.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n% fake\n")
        png_path = output_dir / f"{docx_path.stem}_page-1.png"
        image = Image.new("RGB", (8, 8), "white")
        image.putpixel((2, 2), (0, 0, 0))
        image.save(png_path)
        return DocxPageRenderResult(
            status="ready",
            docx_path=docx_path,
            pdf_path=pdf_path,
            page_paths=(png_path,),
            renderer="fake_renderer",
        )

    monkeypatch.setattr(visual, "render_docx_pages", fake_render)

    result = verify_exam_master_sample_visual("default_exam", tmp_path)

    assert result.status == "visual_png_ok"
    assert result.renderer == "fake_renderer"
    assert result.pdf_path is not None
    assert result.pdf_path.is_file()
    assert len(result.png_paths) == 1
    assert png_has_content(result.png_paths[0]) is True

    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert payload["status"] == "visual_png_ok"
    assert payload["renderer"] == "fake_renderer"
    assert payload["png_paths"] == [str(result.png_paths[0])]


def test_png_has_content_rejects_blank_images(tmp_path):
    blank = tmp_path / "blank.png"
    Image.new("RGB", (4, 4), "white").save(blank)

    assert png_has_content(blank) is False


def test_exam_document_visual_quality_rejects_corrupt_docx_before_render(
    monkeypatch,
    tmp_path,
):
    docx = tmp_path / "corrupt.docx"
    docx.write_bytes(b"not-a-zip-package")
    monkeypatch.setattr(
        visual,
        "render_docx_pages",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("corrupt DOCX must not reach the renderer")
        ),
    )

    result = verify_exam_document_visual(
        docx,
        tmp_path,
        target_page_min=1,
        target_page_max=8,
    )

    assert result.status == "docx_corrupt"
    assert result.issues == ("docx_package_corrupt",)


def test_exam_document_visual_quality_distinguishes_physical_and_substantive_pages(
    monkeypatch,
    tmp_path,
):
    docx = tmp_path / "student.docx"
    docx.write_bytes(b"docx")
    pages = []
    for index in range(4):
        path = tmp_path / f"page-{index + 1}.png"
        image = Image.new("L", (100, 100), 255)
        if index < 3:
            for x in range(10, 90):
                for y in range(10, 40):
                    image.putpixel((x, y), 0)
        image.save(path)
        pages.append(path)

    monkeypatch.setattr(
        visual,
        "render_docx_pages",
        lambda *_args, **_kwargs: DocxPageRenderResult(
            status="ready",
            docx_path=docx,
            page_paths=tuple(pages),
            renderer="fake",
        ),
    )
    monkeypatch.setattr(
        visual,
        "_docx_package_is_readable",
        lambda _path: True,
    )

    result = verify_exam_document_visual(
        docx,
        tmp_path,
        target_page_min=4,
        target_page_max=8,
    )

    assert result.actual_page_count == 4
    assert result.substantive_page_count == 3
    assert result.status == "quality_failed"
    assert any(
        issue.startswith("substantive_page_count_below_target")
        for issue in result.issues
    )
    assert any(
        issue.startswith("trailing_page_underfilled")
        for issue in result.issues
    )


def test_exam_document_visual_quality_accepts_intentional_ruled_response_page(
    monkeypatch,
    tmp_path,
):
    docx = tmp_path / "student.docx"
    docx.write_bytes(b"docx")
    pages = []
    for index in range(4):
        path = tmp_path / f"page-{index + 1}.png"
        image = Image.new("L", (1000, 1400), 255)
        if index < 3:
            for x in range(100, 900):
                for y in range(100, 160):
                    image.putpixel((x, y), 0)
        else:
            for y in (180, 280, 380, 480, 580, 680):
                for x in range(150, 850):
                    image.putpixel((x, y), 190)
        image.save(path)
        pages.append(path)

    monkeypatch.setattr(
        visual,
        "render_docx_pages",
        lambda *_args, **_kwargs: DocxPageRenderResult(
            status="ready",
            docx_path=docx,
            page_paths=tuple(pages),
            renderer="fake",
        ),
    )
    monkeypatch.setattr(
        visual,
        "_docx_package_is_readable",
        lambda _path: True,
    )

    result = verify_exam_document_visual(
        docx,
        tmp_path,
        target_page_min=4,
        target_page_max=8,
    )

    assert result.page_ink_ratios[-1] < 0.008
    assert result.structured_response_page_numbers == (4,)
    assert result.substantive_page_count == 4
    assert result.status == "quality_ok"
    assert result.issues == ()


def test_windows_renderer_selects_wps_when_only_wps_is_registered(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(docx_renderer.sys, "platform", "win32")
    monkeypatch.setattr(docx_renderer, "_win32com_available", lambda: True)
    monkeypatch.setattr(
        docx_renderer,
        "_registered_windows_com_renderers",
        lambda: (("wps_com", "KWPS.Application"),),
    )
    monkeypatch.setattr(docx_renderer.shutil, "which", lambda _name: None)
    calls = []

    def fake_com_renderer(prog_id, _docx_path, pdf_path):
        calls.append(prog_id)
        pdf_path.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(docx_renderer, "_render_docx_to_pdf_com", fake_com_renderer)

    entry = docx_renderer.available_docx_pdf_renderer()
    assert entry is not None
    renderer_name, renderer = entry
    assert renderer_name == "office_com"
    resolved_name = renderer(tmp_path / "sample.docx", tmp_path / "sample.pdf")

    assert resolved_name == "wps_com"
    assert calls == ["KWPS.Application"]


def test_windows_renderer_falls_back_from_word_to_wps(monkeypatch, tmp_path):
    calls = []

    def fake_com_renderer(prog_id, _docx_path, pdf_path):
        calls.append(prog_id)
        if prog_id == "Word.Application":
            raise RuntimeError("Word unavailable")
        pdf_path.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(docx_renderer, "_render_docx_to_pdf_com", fake_com_renderer)
    resolved_name = docx_renderer._render_docx_to_pdf_windows_com(
        (
            ("word_com", "Word.Application"),
            ("wps_com", "KWPS.Application"),
        ),
        tmp_path / "sample.docx",
        tmp_path / "sample.pdf",
    )

    assert resolved_name == "wps_com"
    assert calls == ["Word.Application", "KWPS.Application"]
