"""Visual verification artifacts for exam master samples."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.config.scene import ExamPaperConfig
from src.shared.engine.docx_page_renderer import (
    DocxPageRenderResult,
    png_has_content,
    render_docx_pages,
)
from src.shared.engine.exam_paper_style import (
    EXAM_SAMPLE_PAYLOAD,
    write_exam_answer_key_docx,
    write_exam_blank_style_sample_docx,
)


@dataclass(frozen=True, slots=True)
class ExamMasterVisualVerificationResult:
    style_id: str
    sample_docx_path: Path
    manifest_path: Path
    status: str
    preview_kind: str = "student"
    pdf_path: Path | None = None
    png_paths: tuple[Path, ...] = ()
    renderer: str = ""
    issues: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "style_id": self.style_id,
            "sample_docx_path": str(self.sample_docx_path),
            "manifest_path": str(self.manifest_path),
            "status": self.status,
            "preview_kind": self.preview_kind,
            "pdf_path": str(self.pdf_path or ""),
            "png_paths": [str(path) for path in self.png_paths],
            "renderer": self.renderer,
            "issues": list(self.issues),
        }


def verify_exam_master_sample_visual(
    style_id: str,
    output_dir: Path | str,
    *,
    config: ExamPaperConfig | None = None,
    preview_kind: str = "student",
    attempt_render: bool = True,
) -> ExamMasterVisualVerificationResult:
    normalized_style_id = str(style_id or "").strip() or "default_exam"
    normalized_kind = str(preview_kind or "student").strip().lower()
    if normalized_kind not in {"student", "answer"}:
        raise ValueError(f"Unsupported exam preview kind: {preview_kind}")
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    if normalized_kind == "answer":
        sample_docx = write_exam_answer_key_docx(
            normalized_style_id,
            target_dir,
            payload=EXAM_SAMPLE_PAYLOAD,
            config=config,
            filename="试卷方案_答案速查.docx",
        )
    else:
        sample_docx = write_exam_blank_style_sample_docx(
            normalized_style_id,
            target_dir,
            config=config,
        )
    manifest_path = target_dir / (
        f"{_safe_id(normalized_style_id)}_{normalized_kind}_visual_manifest.json"
    )
    rendered = render_docx_pages(
        sample_docx,
        target_dir,
        attempt_render=attempt_render,
    )
    result = _result_from_render(
        normalized_style_id,
        normalized_kind,
        manifest_path,
        rendered,
    )
    _write_manifest(result)
    return result


def _result_from_render(
    style_id: str,
    preview_kind: str,
    manifest_path: Path,
    rendered: DocxPageRenderResult,
) -> ExamMasterVisualVerificationResult:
    status = {
        "ready": "visual_png_ok",
        "png_blank": "png_blank",
    }.get(rendered.status, rendered.status)
    issues = rendered.issues
    if status == "docx_only" and not issues:
        issues = ("render_skipped",)
    return ExamMasterVisualVerificationResult(
        style_id=style_id,
        sample_docx_path=rendered.docx_path,
        manifest_path=manifest_path,
        status=status,
        preview_kind=preview_kind,
        pdf_path=rendered.pdf_path,
        png_paths=rendered.page_paths,
        renderer=rendered.renderer,
        issues=issues,
    )


def _write_manifest(result: ExamMasterVisualVerificationResult) -> None:
    result.manifest_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _safe_id(value: str) -> str:
    normalized = str(value or "").strip() or "default_exam"
    return "".join(
        character if character.isalnum() or character in {"_", "-"} else "_"
        for character in normalized
    )


__all__ = [
    "ExamMasterVisualVerificationResult",
    "png_has_content",
    "verify_exam_master_sample_visual",
]
