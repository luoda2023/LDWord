# -*- coding: utf-8 -*-
"""Best-effort text extraction for Excel / PowerPoint sources.

The AI assistant accepts real-world engineering materials in many formats.
Word (docx/doc/wps) already extracts its paragraph text; this module adds:

* ``.xlsx``  —— every sheet's rows become tab-separated lines (read via
  openpyxl when installed); a sheet named like 目录/大纲/章节 or whose first
  cells are chapter-like lines is a strong outline source.
* ``.pptx``  —— slide titles + body text are read from the OOXML zip
  (no python-pptx dependency required).

The produced plain text is fed through the same directory-outline parser, so
an Excel 目录 or a PPT 汇报大纲 can drive chapter-by-chapter authoring just
like a Markdown outline.
"""
from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile, BadZipFile

_SUPPORTED_EXCEL = {".xlsx", ".xlsm"}
_SUPPORTED_SLIDES = {".pptx", ".pptm"}
_SHEET_NAME_HINTS = ("目录", "大纲", "章节", "toc", "outline", "chapter")


def office_text_for_outline(path: str | Path) -> str:
    """Return plain text of an xlsx/pptx source for outline parsing."""
    target = Path(str(path or "")).expanduser()
    suffix = target.suffix.casefold()
    if suffix in _SUPPORTED_EXCEL:
        return _excel_sheet_text(target)
    if suffix in _SUPPORTED_SLIDES:
        return _pptx_text(target)
    return ""


def is_office_outline_supported(path: str | Path) -> bool:
    suffix = Path(str(path or "")).suffix.casefold()
    return suffix in _SUPPORTED_EXCEL or suffix in _SUPPORTED_SLIDES


def _excel_sheet_text(path: Path) -> str:
    """Read every sheet; prefer an outline-like sheet first."""
    try:
        import openpyxl
    except Exception:  # noqa: BLE001
        return ""
    try:
        workbook = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    except Exception:  # noqa: BLE001
        return ""
    sections: list[str] = []
    sheet_names = list(workbook.sheetnames)
    ordered = sorted(
        sheet_names,
        key=lambda name: 0 if any(h in name.casefold() for h in _SHEET_NAME_HINTS) else 1,
    )
    for name in ordered:
        try:
            sheet = workbook[name]
        except Exception:  # noqa: BLE001
            continue
        lines: list[str] = []
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if cells:
                lines.append("\t".join(cells))
        if lines:
            sections.append("\n".join(lines))
    try:
        workbook.close()
    except Exception:  # noqa: BLE001
        pass
    return "\n\n".join(sections).strip()


def _pptx_text(path: Path) -> str:
    """Slide titles + body text from the OOXML zip (no python-pptx needed)."""
    import re

    lines: list[str] = []
    try:
        with ZipFile(str(path)) as archive:
            slide_names = sorted(
                (n for n in archive.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                key=lambda n: int(re.search(r"(\d+)", n).group(1)),
            )
            for name in slide_names:
                try:
                    xml = archive.read(name).decode("utf-8", errors="ignore")
                except (KeyError, BadZipFile):
                    continue
                # <a:t> carries run text; keep order of appearance.
                texts = re.findall(r"<a:t>(.*?)</a:t>", xml, flags=re.S)
                cleaned = [
                    re.sub(r"&amp;", "&", re.sub(r"&lt;", "<", re.sub(r"&gt;", ">", t)))
                    for t in texts
                ]
                cleaned = [t.strip() for t in cleaned if t.strip()]
                if cleaned:
                    lines.append("\n".join(cleaned))
    except (OSError, BadZipFile, KeyError):
        return ""
    return "\n\n".join(lines).strip()


__all__ = [
    "is_office_outline_supported",
    "office_text_for_outline",
]
