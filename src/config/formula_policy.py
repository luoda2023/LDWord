"""Thesis-owned formula, equation-table, and script-recovery policy.

These settings are intentionally not part of :class:`TemplateConfig`.  A
template describes reusable document appearance, while formula conversion,
equation numbering, formula-table geometry, and chemical super/subscript
recovery are thesis-plan behavior.  ``ResolvedConfig`` keeps flat projections
only because execution modules consume that shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.config.feature_configs import (
    EquationNumberingConfig,
    FormulaStyleConfig,
    FormulaTableConfig,
)


THESIS_FORMULA_MODULE_NAMES: frozenset[str] = frozenset(
    {
        "formula_convert",
        "equation_table_format",
        "chem_typography",
    }
)


@dataclass
class FormulaConvertOptions:
    """Formula recognition and conversion strategy."""

    enabled: bool = True
    output_mode: str = "word_native"
    low_confidence_policy: str = "skip_and_mark"
    office_fallback_enabled: bool = False
    office_fallback_timeout_sec: int = 30


@dataclass
class ChemTypographyOptions:
    """Chemical typography and super/subscript recovery strategy."""

    enabled: bool = False
    western_font: str = "Times New Roman"
    scopes: dict[str, bool] = field(
        default_factory=lambda: {
            "references": False,
            "body": False,
            "headings": False,
            "abstract_cn": False,
            "abstract_en": False,
            "captions": False,
            "tables": False,
        }
    )
    allow_tokens: list[str] = field(default_factory=list)
    allow_patterns: list[str] = field(default_factory=list)
    ignore_tokens: list[str] = field(default_factory=list)
    ignore_patterns: list[str] = field(default_factory=list)
    manual_overrides: dict[str, str] = field(default_factory=dict)


@dataclass
class FormulaToTableOptions:
    """Containerization policy retained from the V0.2 formula workflow."""

    enabled: bool = True
    block_only: bool = True


@dataclass
class ThesisFormulaRules:
    """The single persisted owner of thesis formula behavior."""

    # Master gate for the formula domain. Child workflow switches remain
    # retained while this feature is disabled.
    formula_enabled: bool = True
    formula_convert: FormulaConvertOptions = field(
        default_factory=FormulaConvertOptions
    )
    formula_to_table: FormulaToTableOptions = field(
        default_factory=FormulaToTableOptions
    )
    formula_table: FormulaTableConfig = field(default_factory=FormulaTableConfig)
    formula_style: FormulaStyleConfig = field(default_factory=FormulaStyleConfig)
    equation_numbering: EquationNumberingConfig = field(
        default_factory=EquationNumberingConfig
    )
    chem_typography: ChemTypographyOptions = field(
        default_factory=ChemTypographyOptions
    )


def is_thesis_formula_mode(mode_id: object) -> bool:
    """Return whether a plan is authorized to own and execute formula rules."""

    return str(mode_id or "").strip().casefold() == "thesis"


__all__ = [
    "ChemTypographyOptions",
    "FormulaConvertOptions",
    "FormulaToTableOptions",
    "THESIS_FORMULA_MODULE_NAMES",
    "ThesisFormulaRules",
    "is_thesis_formula_mode",
]
