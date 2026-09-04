"""Source-bound ownership names for temporary Office layout shadows."""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import re
import uuid


LAYOUT_SHADOW_PREFIX = ".ldword-layout-"
LAYOUT_SHADOW_SOURCE_ID_LENGTH = 16
_LAYOUT_SHADOW_RE = re.compile(
    rf"^{re.escape(LAYOUT_SHADOW_PREFIX)}"
    rf"(?P<source_id>[0-9a-f]{{{LAYOUT_SHADOW_SOURCE_ID_LENGTH}}})-"
    r"(?P<nonce>[0-9a-f]{32})\.docx$"
)


def layout_shadow_source_id(source_path: str | Path) -> str:
    source = Path(source_path).expanduser().resolve()
    canonical = os.path.normcase(str(source))
    return sha256(canonical.encode("utf-8")).hexdigest()[
        :LAYOUT_SHADOW_SOURCE_ID_LENGTH
    ]


def build_controlled_layout_shadow_path(
    source_path: str | Path,
    *,
    nonce: str = "",
) -> Path:
    source = Path(source_path).expanduser().resolve()
    nonce_value = nonce or uuid.uuid4().hex
    if not re.fullmatch(r"[0-9a-f]{32}", nonce_value):
        raise ValueError("layout shadow nonce must be 32 lowercase hex characters")
    return source.parent / (
        f"{LAYOUT_SHADOW_PREFIX}{layout_shadow_source_id(source)}-"
        f"{nonce_value}.docx"
    )


def is_controlled_layout_shadow(
    source_path: str | Path,
    shadow_path: str | Path,
) -> bool:
    source = Path(source_path).expanduser().resolve()
    shadow = Path(shadow_path).expanduser().resolve()
    if shadow == source or shadow.parent != source.parent:
        return False
    matched = _LAYOUT_SHADOW_RE.fullmatch(shadow.name)
    return bool(
        matched
        and matched.group("source_id") == layout_shadow_source_id(source)
    )


__all__ = [
    "LAYOUT_SHADOW_PREFIX",
    "LAYOUT_SHADOW_SOURCE_ID_LENGTH",
    "build_controlled_layout_shadow_path",
    "is_controlled_layout_shadow",
    "layout_shadow_source_id",
]
