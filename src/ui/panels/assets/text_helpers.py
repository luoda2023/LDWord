"""Text parsing and formatting helpers for assets-panel editors."""

from __future__ import annotations

from src.config.resolved import ReplacementRule


def _parse_replacements_text(text: str) -> list[ReplacementRule]:
    replacements: list[ReplacementRule] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            old, new = line.split("=", 1)
        elif ":" in line:
            old, new = line.split(":", 1)
        else:
            continue
        old = old.strip()
        if old:
            replacements.append(ReplacementRule(old=old, new=new.strip()))
    return replacements


def _format_replacements_text(replacements: list[ReplacementRule]) -> str:
    return "\n".join(f"{rule.old}={rule.new}" for rule in replacements)


def _format_image_rules_text(rules) -> str:
    return "\n".join(f"{rule.asset_role}={rule.target}" for rule in rules)


__all__ = [
    "_parse_replacements_text",
    "_format_replacements_text",
    "_format_image_rules_text",
]
