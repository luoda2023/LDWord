"""Shared DOCX-to-PDF-to-PNG rendering infrastructure."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
from src.shared.win_process import run_hidden
import sys

from PIL import Image

from src.shared.engine.pdf_page_renderer import render_pdf_pages_png


REAL_WORD_PREVIEW_ENV = "LDWORD_REAL_WORD_PREVIEW"
DocxPdfRenderer = Callable[[Path, Path], str | None]
ComRendererSpec = tuple[str, str]

_WINDOWS_COM_RENDERERS: tuple[ComRendererSpec, ...] = (
    ("word_com", "Word.Application"),
    ("wps_com", "KWPS.Application"),
)


@dataclass(frozen=True, slots=True)
class DocxPageRenderResult:
    status: str
    docx_path: Path
    pdf_path: Path | None = None
    page_paths: tuple[Path, ...] = ()
    renderer: str = ""
    issues: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return self.status == "ready" and bool(self.page_paths)


def real_word_preview_enabled(environ: Mapping[str, str] | None = None) -> bool:
    values = os.environ if environ is None else environ
    raw = str(values.get(REAL_WORD_PREVIEW_ENV, "") or "").strip().lower()
    if raw:
        return raw not in {"0", "false", "no", "off"}
    return not bool(values.get("PYTEST_CURRENT_TEST"))


def render_docx_pages(
    docx_path: Path | str,
    output_dir: Path | str,
    *,
    attempt_render: bool = True,
    preferred_renderers: Sequence[str] = (),
) -> DocxPageRenderResult:
    source = Path(docx_path)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    if not source.is_file():
        return DocxPageRenderResult(
            status="docx_missing",
            docx_path=source,
            issues=("docx_missing",),
        )
    if not attempt_render:
        return DocxPageRenderResult(status="docx_only", docx_path=source)

    renderer_entry = available_docx_pdf_renderer(
        preferred_renderers=preferred_renderers,
    )
    if renderer_entry is None:
        return DocxPageRenderResult(
            status="renderer_unavailable",
            docx_path=source,
            issues=("docx_to_pdf_renderer_unavailable",),
        )
    renderer_name, renderer = renderer_entry
    pdf_path = target_dir / f"{source.stem}.pdf"
    try:
        resolved_renderer = renderer(source, pdf_path)
        if resolved_renderer:
            renderer_name = str(resolved_renderer)
    except Exception as exc:
        return DocxPageRenderResult(
            status="pdf_render_failed",
            docx_path=source,
            pdf_path=pdf_path,
            renderer=renderer_name,
            issues=(f"pdf_render_failed: {exc}",),
        )
    if not pdf_path.is_file():
        return DocxPageRenderResult(
            status="pdf_missing_after_render",
            docx_path=source,
            pdf_path=pdf_path,
            renderer=renderer_name,
            issues=("pdf_missing_after_render",),
        )

    page_paths, issues = render_pdf_pages_png(pdf_path, target_dir)
    if not page_paths:
        return DocxPageRenderResult(
            status="png_render_failed",
            docx_path=source,
            pdf_path=pdf_path,
            renderer=renderer_name,
            issues=issues or ("png_render_failed",),
        )
    blank_paths = tuple(path for path in page_paths if not png_has_content(path))
    if blank_paths:
        issues = (*issues, *(f"blank_png: {path.name}" for path in blank_paths))
        status = "png_blank"
    else:
        status = "ready"
    return DocxPageRenderResult(
        status=status,
        docx_path=source,
        pdf_path=pdf_path,
        page_paths=page_paths,
        renderer=renderer_name,
        issues=tuple(issues),
    )


def png_has_content(path: Path | str) -> bool:
    with Image.open(path) as image:
        if image.width <= 0 or image.height <= 0:
            return False
        extrema = image.convert("RGB").getextrema()
    return any(low != high for low, high in extrema)


def available_docx_pdf_renderer(
    *,
    preferred_renderers: Sequence[str] = (),
) -> tuple[str, DocxPdfRenderer] | None:
    if sys.platform == "win32":
        com_renderers = _registered_windows_com_renderers()
        com_renderers = _prioritize_com_renderers(
            com_renderers,
            preferred_renderers,
        )
        if _win32com_available() and com_renderers:
            return "office_com", lambda docx, pdf: _render_docx_to_pdf_windows_com(
                com_renderers, docx, pdf
            )
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        return "libreoffice", lambda docx, pdf: _render_docx_to_pdf_libreoffice(
            Path(soffice), docx, pdf
        )
    return None


def _prioritize_com_renderers(
    renderers: tuple[ComRendererSpec, ...],
    preferred_renderers: Sequence[str],
) -> tuple[ComRendererSpec, ...]:
    priorities = {
        str(renderer_name or "").strip(): index
        for index, renderer_name in enumerate(preferred_renderers)
        if str(renderer_name or "").strip()
    }
    if not priorities:
        return renderers
    original_positions = {
        renderer_name: index
        for index, (renderer_name, _prog_id) in enumerate(renderers)
    }
    fallback_priority = len(priorities)
    return tuple(
        sorted(
            renderers,
            key=lambda item: (
                priorities.get(item[0], fallback_priority),
                original_positions[item[0]],
            ),
        )
    )


def _win32com_available() -> bool:
    try:
        import win32com.client  # noqa: F401
    except Exception:
        return False
    return True


def _registered_windows_com_renderers() -> tuple[ComRendererSpec, ...]:
    try:
        import winreg
    except ImportError:
        return ()
    available: list[ComRendererSpec] = []
    for renderer_name, prog_id in _WINDOWS_COM_RENDERERS:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"{prog_id}\CLSID"):
                available.append((renderer_name, prog_id))
        except OSError:
            continue
    return tuple(available)


def _render_docx_to_pdf_libreoffice(
    soffice_path: Path,
    docx_path: Path,
    pdf_path: Path,
) -> None:
    completed = run_hidden(
        [
            str(soffice_path),
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(pdf_path.parent),
            str(docx_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "").strip())
    produced = pdf_path.parent / f"{docx_path.stem}.pdf"
    if produced != pdf_path and produced.is_file():
        produced.replace(pdf_path)


def _render_docx_to_pdf_windows_com(
    renderers: tuple[ComRendererSpec, ...],
    docx_path: Path,
    pdf_path: Path,
) -> str:
    issues: list[str] = []
    for renderer_name, prog_id in renderers:
        try:
            _render_docx_to_pdf_com(prog_id, docx_path, pdf_path)
            if not pdf_path.is_file():
                raise RuntimeError("PDF file was not created")
            return renderer_name
        except Exception as exc:
            pdf_path.unlink(missing_ok=True)
            issues.append(f"{renderer_name}: {exc}")
    raise RuntimeError("; ".join(issues) or "No Office COM renderer succeeded")


def _render_docx_to_pdf_com(prog_id: str, docx_path: Path, pdf_path: Path) -> None:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    application = None
    document = None
    try:
        try:
            application = win32com.client.DispatchEx(prog_id)
        except Exception:
            application = win32com.client.Dispatch(prog_id)
        application.Visible = False
        application.DisplayAlerts = 0
        document = application.Documents.Open(str(docx_path.resolve()), ReadOnly=True)
        try:
            document.ExportAsFixedFormat(str(pdf_path.resolve()), 17)
        except Exception:
            document.SaveAs2(str(pdf_path.resolve()), 17)
    finally:
        if document is not None:
            try:
                document.Close(False)
            except Exception:
                pass
        if application is not None:
            try:
                application.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


__all__ = [
    "DocxPageRenderResult",
    "REAL_WORD_PREVIEW_ENV",
    "available_docx_pdf_renderer",
    "png_has_content",
    "real_word_preview_enabled",
    "render_docx_pages",
]
