"""Navigation card definitions for the scene configuration panel."""

from __future__ import annotations


CARD_DEFINITIONS: dict[str, tuple[str, str]] = {
    # Fixed Layer 1: Identity
    "scn_overview": ("场景概览", "mountain-snow"),
    # Scenario-specific assembly pages
    "scn_exam_paper": ("试卷装配", "file-text"),
    # Fixed Layer 2: Scenario rules
    "scn_rules": ("场景规则", "sliders-horizontal"),
    "scn_cleanup": ("风险检查", "scan"),
    "scn_content": ("资料包与填充", "pen-tool"),
    "scn_output": ("生成结果", "folder-output"),
}

CARD_ORDER = (
    "scn_overview",
    "scn_exam_paper",
    "scn_rules",
    "scn_content",
)

FIXED_CARDS = (
    "scn_overview",
    "scn_exam_paper",
    "scn_rules",
)

FORMAT_TEMPLATE_CARDS = (
    "scn_exam_paper",
    "scn_rules",
)

INPUT_MATERIAL_CARDS = ("scn_content",)

NAV_SECTION_CARD_GROUPS = (
    ("format_template", FORMAT_TEMPLATE_CARDS),
    ("input_material", INPUT_MATERIAL_CARDS),
)
