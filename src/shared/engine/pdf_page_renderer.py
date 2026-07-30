"""Render PDF pages to PNG without depending on a system PDF viewer."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def render_pdf_pages_png(
    pdf_path: Path | str,
    output_dir: Path | str,
    *,
    scale: float = 2.0,
) -> tuple[tuple[Path, ...], tuple[str, ...]]:
    """Rasterize every PDF page, preferring the bundled PDFium backend."""

    source = Path(pdf_path)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    pdfium_paths, pdfium_issue = _render_with_pdfium(
        source,
        target_dir,
        scale=scale,
    )
    if pdfium_paths:
        return pdfium_paths, ()

    poppler_paths, poppler_issue = _render_with_pdftoppm(source, target_dir)
    if poppler_paths:
        return poppler_paths, ()

    issues = tuple(issue for issue in (pdfium_issue, poppler_issue) if issue)
    return (), issues or ("pdf_rasterizer_unavailable",)


def _render_with_pdfium(
    pdf_path: Path,
    output_dir: Path,
    *,
    scale: float,
) -> tuple[tuple[Path, ...], str]:
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return (), "pypdfium2_unavailable"

    document = None
    paths: list[Path] = []
    try:
        document = pdfium.PdfDocument(str(pdf_path))
        for page_index in range(len(document)):
            page = document[page_index]
            bitmap = None
            try:
                bitmap = page.render(scale=max(0.25, float(scale)))
                image = bitmap.to_pil()
                png_path = output_dir / (
                    f"{pdf_path.stem}_page-{page_index + 1:03d}.png"
                )
                image.save(png_path, format="PNG")
                paths.append(png_path)
            finally:
                if bitmap is not None:
                    close = getattr(bitmap, "close", None)
                    if callable(close):
                        close()
                close = getattr(page, "close", None)
                if callable(close):
                    close()
    except Exception as exc:
        for path in paths:
            path.unlink(missing_ok=True)
        return (), f"pypdfium2_failed: {exc}"
    finally:
        if document is not None:
            close = getattr(document, "close", None)
            if callable(close):
                close()

    return tuple(paths), "" if paths else "pypdfium2_no_png_output"


def _render_with_pdftoppm(
    pdf_path: Path,
    output_dir: Path,
) -> tuple[tuple[Path, ...], str]:
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        return (), "pdftoppm_unavailable"

    prefix = output_dir / f"{pdf_path.stem}_page"
    try:
        completed = subprocess.run(
            [pdftoppm, "-png", str(pdf_path), str(prefix)],
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
    except Exception as exc:
        return (), f"pdftoppm_failed: {exc}"
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        return (), f"pdftoppm_failed: {message}"

    paths = tuple(sorted(output_dir.glob(f"{prefix.name}-*.png")))
    return paths, "" if paths else "pdftoppm_no_png_output"
