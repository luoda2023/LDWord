"""Build a native Windows text-rendering matrix for Qt font-engine decisions.

The coordinator starts a fresh native Qt process for every backend/DPR pair.
Each child paints the same semantic 13 px samples at four logical x offsets,
then records both layout and raster evidence.  Explicit-DPR QImages make the
matrix repeatable on a single Windows machine without changing the monitor's
system scaling setting.

Usage::

    python scripts/audit_windows_font_matrix.py
    python scripts/audit_windows_font_matrix.py --output-dir output/audits/my-run

The output directory contains ten PNG contact sheets, ten cell JSON files, one
aggregate ``matrix.json`` and one human-readable ``summary.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable, Sequence

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


BACKENDS: dict[str, str] = {
    "directwrite": "windows",
    "freetype": "windows:fontengine=freetype",
}
SCALES: tuple[float, ...] = (1.0, 1.25, 1.5, 1.75, 2.0)
PHASES: tuple[int, ...] = (0, 1, 2, 3)
PATCH_LOGICAL_SIZE = (196, 56)
PATCH_TEXT_ORIGIN = (12, 36)
FOREGROUND_RGB = (15, 23, 42)
BACKGROUND_RGB = (255, 255, 255)
SUBPIXEL_ALPHA_SPREAD_THRESHOLD = 0.08


@dataclass(frozen=True)
class TextSample:
    sample_id: str
    text: str
    pixel_size: int
    weight: int


TEXT_SAMPLES: tuple[TextSample, ...] = (
    TextSample("fixed_regular", "固定值", 13, 400),
    TextSample("heading_regular", "标题编号", 13, 400),
    TextSample("heading_bold", "标题编号", 13, 700),
    TextSample("font_name_mixed", "宋体/Times A1", 13, 400),
)


def _scale_slug(scale: float) -> str:
    return f"{scale:.2f}".replace(".", "p")


def _rounded(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def _relative_span(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    mean = fmean(values)
    if mean == 0:
        return 0.0 if max(values) == min(values) else float("inf")
    return (max(values) - min(values)) / mean


def _qimage_to_pillow(image: Any) -> Image.Image:
    """Copy a QImage to a tightly owned Pillow RGB image."""

    from PySide6.QtGui import QImage

    converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
    rgba = Image.frombytes(
        "RGBA",
        (converted.width(), converted.height()),
        bytes(converted.bits()),
        "raw",
        "RGBA",
        converted.bytesPerLine(),
        1,
    )
    return rgba.convert("RGB")


def _pixel_coverage(pixel: tuple[int, int, int]) -> tuple[float, float, float]:
    channels: list[float] = []
    for channel, foreground, background in zip(
        pixel,
        FOREGROUND_RGB,
        BACKGROUND_RGB,
        strict=True,
    ):
        denominator = background - foreground
        coverage = (background - channel) / denominator
        channels.append(max(0.0, min(1.0, coverage)))
    return channels[0], channels[1], channels[2]


def _analyze_patch(image: Any, *, scale: float, phase: int) -> dict[str, Any]:
    pil_image = _qimage_to_pillow(image)
    background = Image.new("RGB", pil_image.size, BACKGROUND_RGB)
    bbox = ImageChops.difference(pil_image, background).getbbox()
    if bbox is None:
        raise RuntimeError("Text patch has no non-background pixels")

    crop = pil_image.crop(bbox)
    ink_pixels = 0
    core_pixels = 0
    colored_subpixel_pixels = 0
    coverage_sum = 0.0
    maximum_channel_spread = 0.0

    for pixel in crop.get_flattened_data():
        if pixel == BACKGROUND_RGB:
            continue
        ink_pixels += 1
        coverage = _pixel_coverage(pixel)
        channel_spread = max(coverage) - min(coverage)
        maximum_channel_spread = max(maximum_channel_spread, channel_spread)
        coverage_sum += fmean(coverage)
        if min(coverage) >= 0.95:
            core_pixels += 1
        if channel_spread >= SUBPIXEL_ALPHA_SPREAD_THRESHOLD:
            colored_subpixel_pixels += 1

    bbox_width = bbox[2] - bbox[0]
    bbox_height = bbox[3] - bbox[1]
    normalized_bytes = (
        f"{bbox_width}x{bbox_height}:".encode("ascii") + crop.tobytes()
    )
    origin_physical = (PATCH_TEXT_ORIGIN[0] + phase) * scale
    return {
        "phase": phase,
        "logical_x": PATCH_TEXT_ORIGIN[0] + phase,
        "physical_x": _rounded(origin_physical),
        "physical_x_fraction": _rounded(origin_physical % 1.0),
        "bbox_physical": {
            "left": bbox[0],
            "top": bbox[1],
            "right": bbox[2],
            "bottom": bbox[3],
            "width": bbox_width,
            "height": bbox_height,
        },
        "ink_pixels": ink_pixels,
        "core_pixels": core_pixels,
        "ink_coverage_sum": _rounded(coverage_sum),
        "colored_subpixel_pixels": colored_subpixel_pixels,
        "maximum_channel_coverage_spread": _rounded(maximum_channel_spread),
        "normalized_raster_sha256": hashlib.sha256(normalized_bytes).hexdigest(),
    }


def summarize_phases(phases: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Summarize exact and perceptual stability without conflating them."""

    if not phases:
        raise ValueError("At least one phase result is required")

    hashes = [str(item["normalized_raster_sha256"]) for item in phases]
    bbox_sizes = [
        (
            int(item["bbox_physical"]["width"]),
            int(item["bbox_physical"]["height"]),
        )
        for item in phases
    ]
    ink_pixels = [int(item["ink_pixels"]) for item in phases]
    core_pixels = [int(item["core_pixels"]) for item in phases]
    coverage = [float(item["ink_coverage_sum"]) for item in phases]
    colored = [int(item["colored_subpixel_pixels"]) for item in phases]
    metric_signatures = [
        (
            bbox_sizes[index],
            ink_pixels[index],
            core_pixels[index],
            _rounded(coverage[index]),
            colored[index],
        )
        for index in range(len(phases))
    ]

    return {
        "origin_physical_fractions": [
            float(item["physical_x_fraction"]) for item in phases
        ],
        "raster_variant_count": len(set(hashes)),
        "bbox_size_variant_count": len(set(bbox_sizes)),
        "ink_pixel_range": [min(ink_pixels), max(ink_pixels)],
        "core_pixel_range": [min(core_pixels), max(core_pixels)],
        "ink_coverage_sum_range": [
            _rounded(min(coverage)),
            _rounded(max(coverage)),
        ],
        "colored_subpixel_pixel_range": [min(colored), max(colored)],
        "ink_pixel_relative_span": _rounded(_relative_span(ink_pixels)),
        "core_pixel_relative_span": _rounded(_relative_span(core_pixels)),
        "ink_coverage_relative_span": _rounded(_relative_span(coverage)),
        "pixel_identical_across_phases": len(set(hashes)) == 1,
        "geometry_consistent_across_phases": len(set(bbox_sizes)) == 1,
        "distribution_metrics_consistent_across_phases": (
            len(set(metric_signatures)) == 1
        ),
    }


def _glyph_runs(text: str, font: Any) -> list[dict[str, Any]]:
    from PySide6.QtGui import QTextLayout

    layout = QTextLayout(text, font)
    layout.beginLayout()
    line = layout.createLine()
    line.setLineWidth(1000.0)
    layout.endLayout()

    resolved: list[dict[str, Any]] = []
    for run in layout.glyphRuns():
        raw_font = run.rawFont()
        glyph_indexes = list(run.glyphIndexes())
        advances = raw_font.advancesForGlyphIndexes(glyph_indexes)
        resolved.append(
            {
                "family": raw_font.familyName(),
                "style": raw_font.styleName(),
                "raw_pixel_size": _rounded(raw_font.pixelSize()),
                "glyph_count": len(glyph_indexes),
                "string_indexes": [int(index) for index in run.stringIndexes()],
                "glyph_advances_x": [_rounded(point.x()) for point in advances],
                "glyph_advance_sum": _rounded(sum(point.x() for point in advances)),
            }
        )
    return resolved


def _render_patch(text: str, font: Any, scale: float, phase: int) -> Any:
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QImage, QPainter

    width = round(PATCH_LOGICAL_SIZE[0] * scale)
    height = round(PATCH_LOGICAL_SIZE[1] * scale)
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.setDevicePixelRatio(scale)
    image.fill(QColor(*BACKGROUND_RGB))

    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(font)
        painter.setPen(QColor(*FOREGROUND_RGB))
        painter.drawText(
            QPointF(PATCH_TEXT_ORIGIN[0] + phase, PATCH_TEXT_ORIGIN[1]),
            text,
        )
    finally:
        painter.end()
    return image


def _save_contact_sheet(
    path: Path,
    *,
    backend: str,
    scale: float,
    rendered_samples: Sequence[tuple[TextSample, Sequence[Any]]],
) -> None:
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen

    left_width = 156
    column_gap = 12
    header_height = 60
    row_height = 72
    footer_height = 16
    logical_width = (
        left_width
        + len(PHASES) * (PATCH_LOGICAL_SIZE[0] + column_gap)
        - column_gap
        + 16
    )
    logical_height = header_height + len(rendered_samples) * row_height + footer_height
    sheet = QImage(
        round(logical_width * scale),
        round(logical_height * scale),
        QImage.Format.Format_RGB32,
    )
    sheet.setDevicePixelRatio(scale)
    sheet.fill(QColor(248, 250, 252))

    painter = QPainter(sheet)
    try:
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        header_font = QFont("Segoe UI")
        header_font.setPixelSize(13)
        header_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(header_font)
        painter.setPen(QColor(30, 41, 59))
        painter.drawText(
            QRectF(16, 8, logical_width - 32, 22),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"Windows font matrix · {backend} · DPR {scale:g}",
        )

        label_font = QFont("Segoe UI")
        label_font.setPixelSize(11)
        label_font.setWeight(QFont.Weight.Normal)
        painter.setFont(label_font)
        painter.setPen(QColor(71, 85, 105))
        for column, phase in enumerate(PHASES):
            x = left_width + column * (PATCH_LOGICAL_SIZE[0] + column_gap)
            fraction = ((PATCH_TEXT_ORIGIN[0] + phase) * scale) % 1.0
            painter.drawText(
                QRectF(x, 31, PATCH_LOGICAL_SIZE[0], 20),
                Qt.AlignmentFlag.AlignCenter,
                f"x + {phase}  ·  physical phase {fraction:.2f}",
            )

        border_pen = QPen(QColor(203, 213, 225))
        border_pen.setWidthF(1.0)
        for row, (sample, patches) in enumerate(rendered_samples):
            y = header_height + row * row_height + 8
            painter.setFont(label_font)
            painter.setPen(QColor(51, 65, 85))
            painter.drawText(
                QRectF(16, y, left_width - 28, PATCH_LOGICAL_SIZE[1]),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"{sample.sample_id}\n{sample.pixel_size}px / {sample.weight}",
            )
            for column, patch in enumerate(patches):
                x = left_width + column * (PATCH_LOGICAL_SIZE[0] + column_gap)
                painter.drawImage(QPointF(x, y), patch)
                painter.setPen(border_pen)
                painter.drawRect(
                    QRectF(
                        x,
                        y,
                        PATCH_LOGICAL_SIZE[0],
                        PATCH_LOGICAL_SIZE[1],
                    )
                )
    finally:
        painter.end()

    path.parent.mkdir(parents=True, exist_ok=True)
    if not sheet.save(str(path)):
        raise RuntimeError(f"Failed to save contact sheet: {path}")


def _render_cell(
    *,
    backend: str,
    scale: float,
    png_path: Path,
) -> dict[str, Any]:
    from PySide6.QtCore import __version__ as pyside_version
    from PySide6.QtCore import qVersion
    from PySide6.QtGui import QFontInfo, QFontMetricsF
    from PySide6.QtWidgets import QApplication

    from src.shared.ui.typography_policy import UI_FONT_FAMILIES, build_font
    from src.shared.ui.typography_policy import register_windows_ui_fonts_for_freetype

    requested_platform = BACKENDS[backend]
    app = QApplication(["font-matrix", "-platform", requested_platform])
    font_registration = register_windows_ui_fonts_for_freetype(backend)
    screen = app.primaryScreen()
    rendered_samples: list[tuple[TextSample, Sequence[Any]]] = []
    samples: list[dict[str, Any]] = []

    for sample in TEXT_SAMPLES:
        font = build_font(
            UI_FONT_FAMILIES,
            pixel_size=sample.pixel_size,
            weight=sample.weight,
        )
        font_info = QFontInfo(font)
        metrics = QFontMetricsF(font)
        patches = [
            _render_patch(sample.text, font, scale, phase) for phase in PHASES
        ]
        rendered_samples.append((sample, patches))
        phase_results = [
            _analyze_patch(patch, scale=scale, phase=phase)
            for phase, patch in zip(PHASES, patches, strict=True)
        ]
        advance_logical = metrics.horizontalAdvance(sample.text)
        runs = _glyph_runs(sample.text, font)
        samples.append(
            {
                **asdict(sample),
                "requested_families": list(UI_FONT_FAMILIES),
                "resolved_font_info": {
                    "family": font_info.family(),
                    "style": font_info.styleName(),
                    "pixel_size": font_info.pixelSize(),
                    "weight": int(font_info.weight()),
                    "exact_match": font_info.exactMatch(),
                },
                "glyph_runs": runs,
                "advance_logical": _rounded(advance_logical),
                "advance_physical": _rounded(advance_logical * scale),
                "font_height_logical": _rounded(metrics.height()),
                "phases": phase_results,
                "phase_summary": summarize_phases(phase_results),
                "raw_style_matches_requested_emphasis": (
                    sample.weight < 700
                    or any("bold" in run["style"].lower() for run in runs)
                ),
            }
        )

    _save_contact_sheet(
        png_path,
        backend=backend,
        scale=scale,
        rendered_samples=rendered_samples,
    )
    return {
        "schema_version": 1,
        "backend": backend,
        "requested_qpa_platform": requested_platform,
        "actual_qpa_platform": app.platformName(),
        "scale": scale,
        "scale_source": "explicit QImage devicePixelRatio",
        "screen_device_pixel_ratio": (
            _rounded(screen.devicePixelRatio()) if screen is not None else None
        ),
        "screen_logical_dpi": (
            _rounded(screen.logicalDotsPerInch()) if screen is not None else None
        ),
        "python": platform.python_version(),
        "qt": qVersion(),
        "pyside": pyside_version,
        "platform": platform.platform(),
        "png": png_path.name,
        "ui_font_registration": asdict(font_registration),
        "samples": samples,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _glyph_run_label(sample: dict[str, Any]) -> str:
    return ", ".join(
        f"{run['family']} {run['style']}×{run['glyph_count']}"
        for run in sample["glyph_runs"]
    )


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _fractional_backend_counts(
    cells: Sequence[dict[str, Any]], backend: str
) -> dict[str, int]:
    summaries = [
        sample["phase_summary"]
        for cell in cells
        if cell["backend"] == backend and not float(cell["scale"]).is_integer()
        for sample in cell["samples"]
    ]
    return {
        "total": len(summaries),
        "exact": sum(item["pixel_identical_across_phases"] for item in summaries),
        "geometry": sum(
            item["geometry_consistent_across_phases"] for item in summaries
        ),
        "distribution": sum(
            item["distribution_metrics_consistent_across_phases"]
            for item in summaries
        ),
    }


def build_markdown_summary(payload: dict[str, Any]) -> str:
    cells = payload["cells"]
    fractional_counts = {
        backend: _fractional_backend_counts(cells, backend) for backend in BACKENDS
    }
    colored_totals = {
        backend: sum(
            phase["colored_subpixel_pixels"]
            for cell in cells
            if cell["backend"] == backend
            for sample in cell["samples"]
            for phase in sample["phases"]
        )
        for backend in BACKENDS
    }
    first_by_backend = {
        backend: next(cell for cell in cells if cell["backend"] == backend)
        for backend in BACKENDS
    }
    directwrite_bold = next(
        sample
        for sample in first_by_backend["directwrite"]["samples"]
        if sample["sample_id"] == "heading_bold"
    )
    freetype_bold = next(
        sample
        for sample in first_by_backend["freetype"]["samples"]
        if sample["sample_id"] == "heading_bold"
    )
    bold_delta = (
        freetype_bold["advance_logical"] - directwrite_bold["advance_logical"]
    )
    freetype_bold_is_real = any(
        "bold" in run["style"].lower() for run in freetype_bold["glyph_runs"]
    )
    lines = [
        "# Windows native font rendering matrix",
        "",
        f"Generated: `{payload['generated_at']}`",
        "",
        (
            "This matrix initializes a fresh native Windows Qt process for every "
            "font backend. DPR is applied explicitly at the QImage paint boundary, "
            "so all five scales are reproducible without changing monitor settings."
        ),
        "",
        "## Backend overview",
        "",
        "| Backend | Cells | Samples | Pixel-identical | Geometry-consistent | "
        "Distribution-consistent | Colored subpixel pixels |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for backend in BACKENDS:
        backend_cells = [cell for cell in cells if cell["backend"] == backend]
        summaries = [
            sample["phase_summary"]
            for cell in backend_cells
            for sample in cell["samples"]
        ]
        lines.append(
            "| "
            + " | ".join(
                [
                    backend,
                    str(len(backend_cells)),
                    str(len(summaries)),
                    str(sum(item["pixel_identical_across_phases"] for item in summaries)),
                    str(sum(item["geometry_consistent_across_phases"] for item in summaries)),
                    str(
                        sum(
                            item["distribution_metrics_consistent_across_phases"]
                            for item in summaries
                        )
                    ),
                    str(
                        sum(
                            sum(phase["colored_subpixel_pixels"] for phase in sample["phases"])
                            for cell in backend_cells
                            for sample in cell["samples"]
                        )
                    ),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Observed decision evidence",
            "",
            (
                f"- At fractional DPRs, DirectWrite is exact for "
                f"{fractional_counts['directwrite']['exact']}/"
                f"{fractional_counts['directwrite']['total']} samples, geometry-consistent "
                f"for {fractional_counts['directwrite']['geometry']}/"
                f"{fractional_counts['directwrite']['total']}, and distribution-consistent "
                f"for {fractional_counts['directwrite']['distribution']}/"
                f"{fractional_counts['directwrite']['total']}."
            ),
            (
                f"- At fractional DPRs, FreeType is exact for "
                f"{fractional_counts['freetype']['exact']}/"
                f"{fractional_counts['freetype']['total']} samples, geometry-consistent "
                f"for {fractional_counts['freetype']['geometry']}/"
                f"{fractional_counts['freetype']['total']}, and distribution-consistent "
                f"for {fractional_counts['freetype']['distribution']}/"
                f"{fractional_counts['freetype']['total']}. It therefore does not make "
                "fractional-origin rendering universally pixel- or geometry-identical."
            ),
            (
                f"- Colored-subpixel pixels across the complete matrix: DirectWrite "
                f"{colored_totals['directwrite']}, FreeType {colored_totals['freetype']}. "
                "FreeType removes the ClearType color-fringe mechanism in this raster target."
            ),
            (
                f"- The OS YaHei TTC registration bridge makes FreeType `heading_bold` "
                f"resolve to {'a real Bold face' if freetype_bold_is_real else 'a synthetic face'}; "
                f"its advance delta versus DirectWrite is {bold_delta:+.4f} logical px."
            ),
            (
                "- Result: a global FreeType switch can remove color fringing, but the matrix "
                "does not support treating it as a complete phase-consistency fix. Elision, "
                "wrapping and fixed-width controls remain separate acceptance gates."
            ),
            "",
            "## Layout advance comparison",
            "",
            "Logical advances are backend layout contracts; a difference can affect "
            "elision, fixed-width controls and line wrapping even when raster output looks better.",
            "",
            "| Sample | DirectWrite | FreeType | FreeType − DirectWrite | Glyph runs |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
    )
    for sample_spec in TEXT_SAMPLES:
        directwrite = next(
            item
            for item in first_by_backend["directwrite"]["samples"]
            if item["sample_id"] == sample_spec.sample_id
        )
        freetype = next(
            item
            for item in first_by_backend["freetype"]["samples"]
            if item["sample_id"] == sample_spec.sample_id
        )
        delta = freetype["advance_logical"] - directwrite["advance_logical"]
        lines.append(
            f"| {sample_spec.sample_id} | {directwrite['advance_logical']:.4f} | "
            f"{freetype['advance_logical']:.4f} | {delta:+.4f} | "
            f"DW: {_glyph_run_label(directwrite)}<br>FT: {_glyph_run_label(freetype)} |"
        )

    lines.extend(
        [
            "",
            "## Per-scale phase evidence",
            "",
            "| Backend | DPR | Sample | Advance (logical / physical) | BBox variants | "
            "Raster variants | Ink range | Core range | Colored range | Exact pixels | "
            "Geometry | Distribution | PNG |",
            "| --- | ---: | --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for cell in cells:
        for sample in cell["samples"]:
            summary = sample["phase_summary"]
            lines.append(
                f"| {cell['backend']} | {cell['scale']:g} | {sample['sample_id']} | "
                f"{sample['advance_logical']:.4f} / {sample['advance_physical']:.4f} | "
                f"{summary['bbox_size_variant_count']} | {summary['raster_variant_count']} | "
                f"{summary['ink_pixel_range'][0]}–{summary['ink_pixel_range'][1]} | "
                f"{summary['core_pixel_range'][0]}–{summary['core_pixel_range'][1]} | "
                f"{summary['colored_subpixel_pixel_range'][0]}–"
                f"{summary['colored_subpixel_pixel_range'][1]} | "
                f"{_yes_no(summary['pixel_identical_across_phases'])} | "
                f"{_yes_no(summary['geometry_consistent_across_phases'])} | "
                f"{_yes_no(summary['distribution_metrics_consistent_across_phases'])} | "
                f"[{cell['png']}]({cell['png']}) |"
            )

    lines.extend(
        [
            "",
            "## Interpretation guardrails",
            "",
            "- `Exact pixels` requires the normalized RGB crop hash to match at all four x origins.",
            "- `Geometry` requires identical physical ink-bbox width and height.",
            (
                "- `Distribution` requires bbox size, ink pixels, core pixels, total coverage "
                "and colored-subpixel count all to match. It may be yes while exact hashes "
                "differ only by a grayscale phase redistribution."
            ),
            (
                "- `Colored range` detects per-channel coverage divergence after accounting "
                "for the navy foreground color; it is not a raw R/G/B inequality count."
            ),
            (
                "- The matrix is evidence for a backend decision, not by itself permission "
                "to switch production. Advance deltas must be checked against elision, wrap "
                "and fixed-width layout baselines."
            ),
            "",
            "## Reproduce",
            "",
            "```powershell",
            "python scripts/audit_windows_font_matrix.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _child_command(
    *,
    backend: str,
    scale: float,
    png_path: Path,
    json_path: Path,
) -> list[str]:
    return [
        sys.executable,
        str(Path(__file__).resolve()),
        "--child",
        "--backend",
        backend,
        "--scale",
        str(scale),
        "--png-path",
        str(png_path),
        "--json-path",
        str(json_path),
    ]


def run_matrix(output_dir: Path) -> dict[str, Any]:
    if sys.platform != "win32":
        raise RuntimeError("This audit requires the native Windows Qt platform plugin")

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cells: list[dict[str, Any]] = []
    for backend, requested_platform in BACKENDS.items():
        for scale in SCALES:
            slug = f"{backend}_dpr_{_scale_slug(scale)}"
            png_path = output_dir / f"{slug}.png"
            json_path = output_dir / f"{slug}.json"
            env = os.environ.copy()
            env["QT_QPA_PLATFORM"] = requested_platform
            env.pop("QT_SCALE_FACTOR", None)
            env.pop("QT_SCREEN_SCALE_FACTORS", None)
            completed = subprocess.run(
                _child_command(
                    backend=backend,
                    scale=scale,
                    png_path=png_path,
                    json_path=json_path,
                ),
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    f"Font matrix child failed for {backend} DPR {scale:g}\n"
                    f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
                )
            if not json_path.is_file() or not png_path.is_file():
                raise RuntimeError(f"Child omitted output for {backend} DPR {scale:g}")
            cell = json.loads(json_path.read_text(encoding="utf-8"))
            if completed.stderr.strip():
                cell["child_stderr"] = completed.stderr.strip()
                _write_json(json_path, cell)
            cells.append(cell)

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "command": "python scripts/audit_windows_font_matrix.py",
        "backends": BACKENDS,
        "scales": list(SCALES),
        "phases": list(PHASES),
        "text_samples": [asdict(sample) for sample in TEXT_SAMPLES],
        "subpixel_alpha_spread_threshold": SUBPIXEL_ALPHA_SPREAD_THRESHOLD,
        "cells": cells,
    }
    _write_json(output_dir / "matrix.json", payload)
    (output_dir / "summary.md").write_text(
        build_markdown_summary(payload),
        encoding="utf-8",
    )
    return payload


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "output" / "audits" / f"windows_font_matrix_{date.today().isoformat()}",
        help="Directory for PNG/JSON/Markdown evidence",
    )
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--backend", choices=tuple(BACKENDS), help=argparse.SUPPRESS)
    parser.add_argument("--scale", type=float, help=argparse.SUPPRESS)
    parser.add_argument("--png-path", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--json-path", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.child:
        if args.backend is None or args.scale is None:
            raise SystemExit("--child requires --backend and --scale")
        if args.png_path is None or args.json_path is None:
            raise SystemExit("--child requires --png-path and --json-path")
        payload = _render_cell(
            backend=args.backend,
            scale=args.scale,
            png_path=args.png_path.resolve(),
        )
        _write_json(args.json_path.resolve(), payload)
        return 0

    payload = run_matrix(args.output_dir)
    output_dir = args.output_dir.resolve()
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "cells": len(payload["cells"]),
                "png_files": len(list(output_dir.glob("*.png"))),
                "matrix_json": str(output_dir / "matrix.json"),
                "summary_md": str(output_dir / "summary.md"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
