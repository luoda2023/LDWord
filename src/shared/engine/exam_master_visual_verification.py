"""Visual verification artifacts for exam master samples."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from PIL import Image

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


@dataclass(frozen=True, slots=True)
class ExamDocumentVisualQualityResult:
    """Rendered page-count and page-use evidence for one student paper."""

    docx_path: Path
    status: str
    target_page_min: int
    target_page_max: int
    actual_page_count: int = 0
    substantive_page_count: int = 0
    page_ink_ratios: tuple[float, ...] = ()
    structured_response_page_numbers: tuple[int, ...] = ()
    pdf_path: Path | None = None
    png_paths: tuple[Path, ...] = ()
    renderer: str = ""
    issues: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.status == "quality_ok"

    def to_dict(self) -> dict[str, object]:
        return {
            "docx_path": str(self.docx_path),
            "status": self.status,
            "target_page_min": self.target_page_min,
            "target_page_max": self.target_page_max,
            "actual_page_count": self.actual_page_count,
            "substantive_page_count": self.substantive_page_count,
            "page_ink_ratios": [
                round(value, 6) for value in self.page_ink_ratios
            ],
            "structured_response_page_numbers": list(
                self.structured_response_page_numbers
            ),
            "pdf_path": str(self.pdf_path or ""),
            "png_paths": [str(path) for path in self.png_paths],
            "renderer": self.renderer,
            "issues": list(self.issues),
        }


def verify_exam_document_visual(
    docx_path: Path | str,
    output_dir: Path | str,
    *,
    target_page_min: int,
    target_page_max: int,
    attempt_render: bool = True,
    preferred_renderers: tuple[str, ...] = ("wps_com", "word_com"),
    substantive_ink_ratio: float = 0.008,
) -> ExamDocumentVisualQualityResult:
    """Render one final student paper and test physical and substantive pages."""

    source = Path(docx_path)
    minimum = max(1, int(target_page_min))
    maximum = max(minimum, int(target_page_max))
    if not source.is_file():
        return ExamDocumentVisualQualityResult(
            docx_path=source,
            status="docx_missing",
            target_page_min=minimum,
            target_page_max=maximum,
            issues=("docx_missing",),
        )
    if not _docx_package_is_readable(source):
        return ExamDocumentVisualQualityResult(
            docx_path=source,
            status="docx_corrupt",
            target_page_min=minimum,
            target_page_max=maximum,
            issues=("docx_package_corrupt",),
        )
    rendered = render_docx_pages(
        source,
        output_dir,
        attempt_render=attempt_render,
        preferred_renderers=preferred_renderers,
    )
    if not rendered.page_paths:
        return ExamDocumentVisualQualityResult(
            docx_path=source,
            status=rendered.status,
            target_page_min=minimum,
            target_page_max=maximum,
            pdf_path=rendered.pdf_path,
            renderer=rendered.renderer,
            issues=rendered.issues,
        )

    page_ratios = tuple(_page_ink_ratio(path) for path in rendered.page_paths)
    actual_page_count = len(rendered.page_paths)
    structured_response_page_numbers = tuple(
        page_number
        for page_number, (path, ratio) in enumerate(
            zip(rendered.page_paths, page_ratios),
            start=1,
        )
        if ratio < substantive_ink_ratio
        and _page_has_ruled_response_area(path)
    )
    structured_response_pages = set(structured_response_page_numbers)
    substantive_page_count = sum(
        ratio >= substantive_ink_ratio
        or page_number in structured_response_pages
        for page_number, ratio in enumerate(page_ratios, start=1)
    )
    issues = list(rendered.issues)
    if actual_page_count < minimum:
        issues.append(
            f"page_count_below_target:{actual_page_count}<{minimum}"
        )
    if actual_page_count > maximum:
        issues.append(
            f"page_count_above_target:{actual_page_count}>{maximum}"
        )
    if substantive_page_count < minimum:
        issues.append(
            "substantive_page_count_below_target:"
            f"{substantive_page_count}<{minimum}"
        )
    if (
        actual_page_count > 1
        and page_ratios[-1] < substantive_ink_ratio
        and actual_page_count not in structured_response_pages
    ):
        issues.append(
            "trailing_page_underfilled:"
            f"{page_ratios[-1]:.6f}<{substantive_ink_ratio:.6f}"
        )
    return ExamDocumentVisualQualityResult(
        docx_path=source,
        status="quality_failed" if issues else "quality_ok",
        target_page_min=minimum,
        target_page_max=maximum,
        actual_page_count=actual_page_count,
        substantive_page_count=substantive_page_count,
        page_ink_ratios=page_ratios,
        structured_response_page_numbers=structured_response_page_numbers,
        pdf_path=rendered.pdf_path,
        png_paths=rendered.page_paths,
        renderer=rendered.renderer,
        issues=tuple(issues),
    )


def _page_ink_ratio(path: Path) -> float:
    with Image.open(path) as image:
        grayscale = image.convert("L")
        histogram = grayscale.histogram()
        ink_pixels = sum(histogram[:245])
        total_pixels = max(1, grayscale.width * grayscale.height)
    return ink_pixels / total_pixels


def _docx_package_is_readable(path: Path) -> bool:
    try:
        with ZipFile(path) as archive:
            members = set(archive.namelist())
            if not {"[Content_Types].xml", "word/document.xml"}.issubset(
                members
            ):
                return False
            if archive.testzip() is not None:
                return False
            archive.read("[Content_Types].xml")
            archive.read("word/document.xml")
    except (BadZipFile, KeyError, OSError, RuntimeError):
        return False
    return True


def _page_has_ruled_response_area(path: Path) -> bool:
    """Recognize intentional low-ink answer pages made of long ruled lines.

    Ink coverage alone cannot distinguish an accidental blank page from a
    student response page.  Four or more long horizontal rules are strong
    structural evidence that the whitespace is deliberate and usable.
    """

    with Image.open(path) as image:
        grayscale = image.convert("L")
        width, height = grayscale.size
        pixels = grayscale.load()
        minimum_dark_pixels = max(1, int(width * 0.35))
        minimum_span = max(1, int(width * 0.5))
        matching_rows: list[int] = []
        for y in range(height):
            dark_count = 0
            first_dark = -1
            last_dark = -1
            for x in range(width):
                if pixels[x, y] >= 245:
                    continue
                dark_count += 1
                if first_dark < 0:
                    first_dark = x
                last_dark = x
            if (
                dark_count >= minimum_dark_pixels
                and last_dark - first_dark >= minimum_span
            ):
                matching_rows.append(y)

    rule_groups = 0
    previous_row = -2
    for row in matching_rows:
        if row > previous_row + 1:
            rule_groups += 1
            if rule_groups >= 4:
                return True
        previous_row = row
    return False


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
    "ExamDocumentVisualQualityResult",
    "ExamMasterVisualVerificationResult",
    "png_has_content",
    "verify_exam_document_visual",
    "verify_exam_master_sample_visual",
]
