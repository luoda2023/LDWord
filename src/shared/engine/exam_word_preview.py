"""Exam adapter for the shared Word preview pipeline."""

from __future__ import annotations

import copy
from dataclasses import asdict
from pathlib import Path

from src.config.master_library import get_master
from src.config.scene import ExamPaperConfig, coerce_exam_paper_config
from src.shared.engine.document_word_preview import (
    DocumentWordPreviewRequest,
    DocumentWordPreviewResult,
    PreviewDocumentBuild,
    file_cache_signature,
    render_document_word_preview,
)
from src.shared.engine.exam_paper_style import (
    EXAM_SAMPLE_PAYLOAD,
    write_exam_answer_key_docx,
    write_exam_blank_style_sample_docx,
)


ExamWordPreviewResult = DocumentWordPreviewResult


def build_exam_word_preview_request(
    *,
    style_id: str,
    config: ExamPaperConfig | dict | None,
    preview_kind: str = "student",
    template_id: str = "",
) -> DocumentWordPreviewRequest:
    normalized_style_id = str(style_id or "").strip() or "default_exam"
    normalized_kind = str(preview_kind or "student").strip().lower()
    if normalized_kind not in {"student", "answer"}:
        raise ValueError(f"Unsupported exam preview kind: {preview_kind}")
    config_snapshot = copy.deepcopy(coerce_exam_paper_config(config))
    master = get_master(normalized_style_id, "exam", exam_config=config_snapshot)

    def build_document(output_dir: Path) -> PreviewDocumentBuild:
        if normalized_kind == "answer":
            docx_path = write_exam_answer_key_docx(
                normalized_style_id,
                output_dir,
                payload=EXAM_SAMPLE_PAYLOAD,
                config=config_snapshot,
                filename="试卷方案_答案速查.docx",
            )
        else:
            docx_path = write_exam_blank_style_sample_docx(
                normalized_style_id,
                output_dir,
                config=config_snapshot,
            )
        return PreviewDocumentBuild(
            status="ready",
            docx_path=docx_path,
            uses_sample_data=True,
        )

    return DocumentWordPreviewRequest(
        provider_id="exam",
        variant_id=normalized_kind,
        cache_payload={
            "style_id": normalized_style_id,
            "config": asdict(config_snapshot),
            "master_signature": (
                file_cache_signature(master.docx_path) if master is not None else ()
            ),
            "template_id": str(template_id or ""),
        },
        build_document=build_document,
    )


def render_exam_word_preview(
    *,
    style_id: str,
    config: ExamPaperConfig | dict | None,
    preview_kind: str = "student",
    template_id: str = "",
    cache_root: Path | str | None = None,
    attempt_render: bool = True,
    max_cache_entries: int = 12,
    force: bool = False,
) -> DocumentWordPreviewResult:
    request = build_exam_word_preview_request(
        style_id=style_id,
        config=config,
        preview_kind=preview_kind,
        template_id=template_id,
    )
    return render_document_word_preview(
        request,
        cache_root=cache_root,
        attempt_render=attempt_render,
        max_cache_entries=max_cache_entries,
        force=force,
    )


__all__ = [
    "ExamWordPreviewResult",
    "build_exam_word_preview_request",
    "render_exam_word_preview",
]
