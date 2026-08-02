"""Navigation card definitions for the scene configuration panel."""

from __future__ import annotations


CARD_DEFINITIONS: dict[str, tuple[str, str]] = {
    # Fixed Layer 1: Identity
    "scn_overview": ("方案概览", "mountain-snow"),
    # Scenario-specific assembly pages
    "scn_exam_paper": ("方案概览", "layers"),
    # Fixed Layer 2: Scenario rules
    "scn_rules": ("方案规则", "sliders-horizontal"),
    # Thesis-only Layer 2 feature editors
    "scn_formula": ("公式处理", "sigma"),
    "scn_chem_typography": ("上下角标与化学式", "whole-word"),
    "scn_output": ("生成结果", "folder-output"),
}

CARD_ORDER = (
    "scn_exam_paper",
    "scn_rules",
)

FIXED_CARDS = (
    "scn_exam_paper",
    "scn_rules",
)

FORMAT_TEMPLATE_CARDS = (
    "scn_overview",
    "scn_exam_paper",
    "scn_rules",
    "scn_formula",
    "scn_chem_typography",
)

NAV_SECTION_CARD_GROUPS = (
    ("format_template", FORMAT_TEMPLATE_CARDS),
)
