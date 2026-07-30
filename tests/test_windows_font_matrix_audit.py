from __future__ import annotations

from pathlib import Path

from scripts.audit_windows_font_matrix import (
    BACKENDS,
    PHASES,
    SCALES,
    TEXT_SAMPLES,
    build_markdown_summary,
    summarize_phases,
)


ROOT = Path(__file__).resolve().parent.parent


def _phase(
    phase: int,
    *,
    digest: str,
    width: int = 20,
    ink: int = 100,
    core: int = 40,
    coverage: float = 70.0,
    colored: int = 0,
) -> dict[str, object]:
    return {
        "phase": phase,
        "physical_x_fraction": phase / 4,
        "bbox_physical": {"width": width, "height": 12},
        "ink_pixels": ink,
        "core_pixels": core,
        "ink_coverage_sum": coverage,
        "colored_subpixel_pixels": colored,
        "normalized_raster_sha256": digest,
    }


def test_matrix_covers_both_native_backends_all_required_scales_and_samples():
    assert BACKENDS == {
        "directwrite": "windows",
        "freetype": "windows:fontengine=freetype",
    }
    assert SCALES == (1.0, 1.25, 1.5, 1.75, 2.0)
    assert PHASES == (0, 1, 2, 3)
    assert [(sample.text, sample.weight) for sample in TEXT_SAMPLES] == [
        ("固定值", 400),
        ("标题编号", 400),
        ("标题编号", 700),
        ("宋体/Times A1", 400),
    ]


def test_phase_summary_keeps_exact_raster_and_distribution_contracts_separate():
    phases = [
        _phase(0, digest="a"),
        _phase(1, digest="b"),
        _phase(2, digest="b"),
        _phase(3, digest="a"),
    ]

    summary = summarize_phases(phases)

    assert summary["raster_variant_count"] == 2
    assert summary["pixel_identical_across_phases"] is False
    assert summary["geometry_consistent_across_phases"] is True
    assert summary["distribution_metrics_consistent_across_phases"] is True


def test_phase_summary_detects_clear_type_distribution_variation():
    phases = [
        _phase(0, digest="a", ink=100, core=45, colored=60),
        _phase(1, digest="b", ink=108, core=37, colored=74),
        _phase(2, digest="c", ink=104, core=41, colored=68),
        _phase(3, digest="d", ink=110, core=35, colored=80),
    ]

    summary = summarize_phases(phases)

    assert summary["colored_subpixel_pixel_range"] == [60, 80]
    assert summary["core_pixel_range"] == [35, 45]
    assert summary["distribution_metrics_consistent_across_phases"] is False


def test_markdown_summary_documents_layout_risk_and_phase_definitions():
    cells = []
    for backend in BACKENDS:
        samples = []
        for sample in TEXT_SAMPLES:
            phases = [_phase(phase, digest="same") for phase in PHASES]
            samples.append(
                {
                    "sample_id": sample.sample_id,
                    "advance_logical": 24.0 if backend == "directwrite" else 25.0,
                    "advance_physical": 24.0 if backend == "directwrite" else 25.0,
                    "glyph_runs": [
                        {
                            "family": "Microsoft YaHei",
                            "style": (
                                "Bold" if sample.sample_id == "heading_bold" else "Regular"
                            ),
                            "glyph_count": len(sample.text),
                        }
                    ],
                    "phases": phases,
                    "phase_summary": summarize_phases(phases),
                }
            )
        cells.append(
            {
                "backend": backend,
                "scale": 1.0,
                "png": f"{backend}.png",
                "samples": samples,
            }
        )

    markdown = build_markdown_summary(
        {"generated_at": "2026-07-12T00:00:00+08:00", "cells": cells}
    )

    assert "Layout advance comparison" in markdown
    assert "elision, fixed-width controls and line wrapping" in markdown
    assert "Exact pixels" in markdown
    assert "Distribution" in markdown
    assert "FreeType − DirectWrite" in markdown


def test_matrix_script_does_not_mutate_production_typography_or_widgets():
    source = (ROOT / "scripts/audit_windows_font_matrix.py").read_text(encoding="utf-8")

    assert "from src.shared.ui.typography_policy import UI_FONT_FAMILIES, build_font" in source
    assert "apply_application_typography" not in source
    assert "StyledComboBox" not in source
    assert "NavigationCard" not in source
