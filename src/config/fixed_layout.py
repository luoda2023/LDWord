"""Fixed-layout scene policies.

Fixed-layout policies keep form/certificate/table-positioning behavior out of
generic template table styling.  They are scene-family contracts: a profile may
preserve or enforce Word XML layout details such as ``w:trHeight`` without
reintroducing legacy ``TableConfig.row_height_pt``.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config.fixed_layout_contract import FixedLayoutRowHeightPolicy


ALLOWED_ROW_HEIGHT_MODES: tuple[str, ...] = (
    "preserve_existing",
    "enforce_exact",
    "enforce_at_least",
    "clear",
)

@dataclass(frozen=True, slots=True)
class FixedLayoutPolicyAuditResult:
    """Static audit result for fixed-layout policy declarations."""

    invalid_modes: tuple[tuple[str, str], ...] = ()
    missing_height_values: tuple[str, ...] = ()
    unknown_parameter_paths: tuple[str, ...] = ()

    @property
    def is_clean(self) -> bool:
        return not (
            self.invalid_modes
            or self.missing_height_values
            or self.unknown_parameter_paths
        )


FIXED_LAYOUT_ROW_HEIGHT_POLICIES: tuple[FixedLayoutRowHeightPolicy, ...] = (
    FixedLayoutRowHeightPolicy(
        policy_id="form_batch_documents.table_row_height",
        family_id="form_batch_documents",
        label="固定版位表格行高",
        mode="preserve_existing",
        row_height_pt=None,
        parameter_path="form_batch_documents.table.row_height_pt",
        applies_to=("tables", "content_controls", "textboxes"),
        rationale=(
            "Fixed-layout form profiles preserve existing w:trHeight by default; "
            "explicit enforce policies must be profile-scoped."
        ),
    ),
)

FIXED_LAYOUT_ROW_HEIGHT_POLICY_MAP: dict[str, FixedLayoutRowHeightPolicy] = {
    policy.policy_id: policy for policy in FIXED_LAYOUT_ROW_HEIGHT_POLICIES
}


def list_fixed_layout_row_height_policies() -> tuple[FixedLayoutRowHeightPolicy, ...]:
    """Return registered fixed-layout row-height policies."""

    return FIXED_LAYOUT_ROW_HEIGHT_POLICIES


def get_fixed_layout_row_height_policy(policy_id: str) -> FixedLayoutRowHeightPolicy:
    """Look up a fixed-layout row-height policy by id."""

    normalized = str(policy_id or "").strip()
    try:
        return FIXED_LAYOUT_ROW_HEIGHT_POLICY_MAP[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown fixed-layout row-height policy: {policy_id}") from exc


def fixed_layout_row_height_policy_for_family(
    family_id: str,
) -> FixedLayoutRowHeightPolicy | None:
    """Return the default row-height policy for a planned scene family."""

    normalized = str(family_id or "").strip()
    for policy in FIXED_LAYOUT_ROW_HEIGHT_POLICIES:
        if policy.family_id == normalized:
            return policy
    return None


def audit_fixed_layout_row_height_policies() -> FixedLayoutPolicyAuditResult:
    """Audit policy declarations without touching runtime documents."""

    invalid_modes = tuple(
        sorted(
            (policy.policy_id, policy.mode)
            for policy in FIXED_LAYOUT_ROW_HEIGHT_POLICIES
            if policy.mode not in ALLOWED_ROW_HEIGHT_MODES
        )
    )
    missing_height_values = tuple(
        sorted(
            policy.policy_id
            for policy in FIXED_LAYOUT_ROW_HEIGHT_POLICIES
            if policy.requires_height_value and policy.row_height_pt is None
        )
    )
    unknown_parameter_paths = tuple(
        sorted(
            policy.policy_id
            for policy in FIXED_LAYOUT_ROW_HEIGHT_POLICIES
            if policy.parameter_path != "form_batch_documents.table.row_height_pt"
        )
    )
    return FixedLayoutPolicyAuditResult(
        invalid_modes=invalid_modes,
        missing_height_values=missing_height_values,
        unknown_parameter_paths=unknown_parameter_paths,
    )


def build_fixed_layout_row_height_policy_summary(
    policy: FixedLayoutRowHeightPolicy,
) -> str:
    """Build a compact policy summary for docs and audit tests."""

    height = "-" if policy.row_height_pt is None else f"{policy.row_height_pt:g}pt"
    applies_to = "/".join(policy.applies_to)
    return (
        f"{policy.policy_id} [{policy.family_id}] -> {policy.mode}; "
        f"height={height}; path={policy.parameter_path}; "
        f"touchpoint={policy.ooxml_touchpoint}; applies={applies_to}"
    )


__all__ = [
    "ALLOWED_ROW_HEIGHT_MODES",
    "FIXED_LAYOUT_ROW_HEIGHT_POLICIES",
    "FIXED_LAYOUT_ROW_HEIGHT_POLICY_MAP",
    "FixedLayoutPolicyAuditResult",
    "FixedLayoutRowHeightPolicy",
    "audit_fixed_layout_row_height_policies",
    "build_fixed_layout_row_height_policy_summary",
    "fixed_layout_row_height_policy_for_family",
    "get_fixed_layout_row_height_policy",
    "list_fixed_layout_row_height_policies",
]
