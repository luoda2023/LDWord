"""Pure, dependency-free rules for persisted Scene identities."""

from __future__ import annotations

import re
import unicodedata


MAX_SCENE_ID_LENGTH = 96
_WINDOWS_RESERVED_STEMS = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


def safe_scene_file_stem(value: object) -> str:
    """Return a portable, bounded stem suitable for one Scene JSON file."""

    forbidden = '<>:"/\\|?*'
    normalized = unicodedata.normalize("NFKC", str(value or "").strip())
    cleaned = "".join(
        character
        if (
            character not in forbidden
            and unicodedata.category(character) not in {"Cc", "Cf", "Cs"}
        )
        else "_"
        for character in normalized
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._")
    if not cleaned:
        cleaned = "plan"
    if cleaned.split(".", 1)[0].casefold() in _WINDOWS_RESERVED_STEMS:
        cleaned = f"plan_{cleaned}"
    cleaned = cleaned[:MAX_SCENE_ID_LENGTH].rstrip(" ._")
    return cleaned or "plan"


def require_canonical_scene_id(
    value: object,
    *,
    label: str = "scene id",
) -> str:
    """Return ``value`` only when it already satisfies the Scene ID contract."""

    normalized = str(value or "")
    if not normalized or normalized != safe_scene_file_stem(normalized):
        qualifier = "" if label == "config id" else " (config id)"
        raise ValueError(f"invalid {label}{qualifier}: {value!r}")
    return normalized


__all__ = [
    "MAX_SCENE_ID_LENGTH",
    "require_canonical_scene_id",
    "safe_scene_file_stem",
]
