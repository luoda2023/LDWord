"""OOXML helpers for fixed-layout table policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.shared.engine.ooxml_ops import find_or_create, qn


@dataclass(frozen=True, slots=True)
class RowHeightState:
    """Current ``w:trHeight`` state for one table row."""

    row_index: int
    height_twips: int | None
    rule: str


@dataclass(frozen=True, slots=True)
class RowHeightPolicyApplication:
    """Result of applying a fixed-layout row-height policy."""

    policy_id: str
    mode: str
    row_count: int
    changed_count: int
    preserved_count: int
    cleared_count: int
    target_twips: int | None
    target_rule: str


def pt_to_twips(pt: float) -> int:
    """Convert points to Word twips."""

    return int(round(float(pt) * 20))


def row_height_state(row, *, row_index: int = 0) -> RowHeightState:
    """Read ``w:trHeight`` from a python-docx row or raw ``w:tr`` element."""

    tr = _row_element(row)
    tr_pr = tr.find(qn("w:trPr"))
    if tr_pr is None:
        return RowHeightState(row_index=row_index, height_twips=None, rule="")
    height = tr_pr.find(qn("w:trHeight"))
    if height is None:
        return RowHeightState(row_index=row_index, height_twips=None, rule="")
    raw_height = height.get(qn("w:val"))
    try:
        height_twips = int(raw_height) if raw_height not in (None, "") else None
    except ValueError:
        height_twips = None
    return RowHeightState(
        row_index=row_index,
        height_twips=height_twips,
        rule=str(height.get(qn("w:hRule")) or ""),
    )


def set_fixed_layout_row_height(row, height_pt: float, *, rule: str = "exact") -> bool:
    """Set one row's ``w:trHeight`` and return whether XML changed."""

    target_twips = pt_to_twips(height_pt)
    normalized_rule = _normalize_height_rule(rule)
    tr = _row_element(row)
    before = row_height_state(tr)
    tr_pr = find_or_create(tr, "w:trPr")
    height = find_or_create(tr_pr, "w:trHeight")
    height.set(qn("w:val"), str(target_twips))
    height.set(qn("w:hRule"), normalized_rule)
    return before.height_twips != target_twips or before.rule != normalized_rule


def clear_fixed_layout_row_height(row) -> bool:
    """Remove one row's ``w:trHeight`` and return whether XML changed."""

    tr = _row_element(row)
    tr_pr = tr.find(qn("w:trPr"))
    if tr_pr is None:
        return False
    changed = False
    for height in list(tr_pr.findall(qn("w:trHeight"))):
        tr_pr.remove(height)
        changed = True
    return changed


def apply_fixed_layout_row_height_policy(
    table,
    policy,
    *,
    row_indices: Iterable[int] | None = None,
) -> RowHeightPolicyApplication:
    """Apply a fixed-layout row-height policy to a python-docx table.

    Supported modes:
    - ``preserve_existing``: inspect only, no XML write.
    - ``enforce_exact``: set ``w:hRule="exact"`` and ``w:val``.
    - ``enforce_at_least``: set ``w:hRule="atLeast"`` and ``w:val``.
    - ``clear``: remove row-height overrides.
    """

    rows = list(table.rows)
    selected_indices = _selected_row_indices(len(rows), row_indices)
    mode = str(getattr(policy, "mode", "") or "").strip()
    policy_id = str(getattr(policy, "policy_id", "") or "")
    changed = 0
    preserved = 0
    cleared = 0
    target_twips = None
    target_rule = ""

    if mode in {"enforce_exact", "enforce_at_least"}:
        height_pt = getattr(policy, "row_height_pt", None)
        if height_pt is None:
            raise ValueError(f"{policy_id or 'policy'} requires row_height_pt")
        target_twips = pt_to_twips(float(height_pt))
        target_rule = "atLeast" if mode == "enforce_at_least" else "exact"

    for index in selected_indices:
        row = rows[index]
        if mode == "preserve_existing":
            if row_height_state(row, row_index=index).height_twips is not None:
                preserved += 1
        elif mode == "clear":
            if clear_fixed_layout_row_height(row):
                changed += 1
                cleared += 1
        elif mode in {"enforce_exact", "enforce_at_least"}:
            if set_fixed_layout_row_height(row, float(policy.row_height_pt), rule=target_rule):
                changed += 1
        else:
            raise ValueError(f"Unsupported fixed-layout row-height mode: {mode}")

    return RowHeightPolicyApplication(
        policy_id=policy_id,
        mode=mode,
        row_count=len(selected_indices),
        changed_count=changed,
        preserved_count=preserved,
        cleared_count=cleared,
        target_twips=target_twips,
        target_rule=target_rule,
    )


def _selected_row_indices(row_count: int, row_indices: Iterable[int] | None) -> list[int]:
    if row_indices is None:
        return list(range(row_count))
    result: list[int] = []
    for raw_index in row_indices:
        index = int(raw_index)
        if index < 0 or index >= row_count:
            continue
        if index not in result:
            result.append(index)
    return result


def _normalize_height_rule(rule: str) -> str:
    normalized = str(rule or "exact").strip()
    return normalized if normalized in {"exact", "atLeast", "auto"} else "exact"


def _row_element(row):
    return getattr(row, "_element", row)


__all__ = [
    "RowHeightPolicyApplication",
    "RowHeightState",
    "apply_fixed_layout_row_height_policy",
    "clear_fixed_layout_row_height",
    "pt_to_twips",
    "row_height_state",
    "set_fixed_layout_row_height",
]
