MATERIAL_SUITE_DELIVERY_CARD_ID = "material_suite_generate"

# These identifiers belonged to the retired duplicate material-fill surface.
# Keep an explicit deny-list in addition to removing their registrations so a
# stale navigation intent or future registry refactor cannot expose them again.
RETIRED_WORKBENCH_CARD_IDS = frozenset({"content_fill", "quick_fill"})

# Release boundary: the suite-delivery workflow is still under development.
# Keep it unreachable from production UI until an explicit release decision
# changes this constant and the accompanying release-policy tests.
MATERIAL_SUITE_DELIVERY_RELEASED = False


def is_workbench_card_released(card_id: str) -> bool:
    """Return whether a Workbench destination may be exposed in this release."""

    normalized = str(card_id or "").strip()
    if normalized in RETIRED_WORKBENCH_CARD_IDS:
        return False
    if normalized == MATERIAL_SUITE_DELIVERY_CARD_ID:
        return MATERIAL_SUITE_DELIVERY_RELEASED
    return True


__all__ = [
    "MATERIAL_SUITE_DELIVERY_CARD_ID",
    "MATERIAL_SUITE_DELIVERY_RELEASED",
    "RETIRED_WORKBENCH_CARD_IDS",
    "is_workbench_card_released",
]
