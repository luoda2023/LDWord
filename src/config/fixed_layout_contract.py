"""Customer-runtime fixed-layout row-height contract."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FixedLayoutRowHeightPolicy:
    """Scene-family policy for Word table row height handling."""

    policy_id: str
    family_id: str
    label: str
    mode: str
    row_height_pt: float | None
    parameter_path: str
    owner_layer: str = "scene"
    ooxml_touchpoint: str = "w:trHeight"
    applies_to: tuple[str, ...] = ("tables",)
    rationale: str = ""

    @property
    def requires_height_value(self) -> bool:
        return self.mode in {"enforce_exact", "enforce_at_least"}

    @property
    def height_rule(self) -> str:
        if self.mode == "enforce_at_least":
            return "atLeast"
        return "exact"


__all__ = ["FixedLayoutRowHeightPolicy"]
