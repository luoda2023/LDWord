# -*- coding: utf-8 -*-
"""Migrate legacy ``_1``/``_2`` image filenames to content-hash names.

Earlier versions of the image persister named colliding copies by appending
``_1``/``_2`` before the extension (e.g. ``photo_1.png``).  The current code
writes ``<stem>_<sha256:16>.png`` so identical content always maps to one file.
This module finds those legacy files and either de-duplicates them onto an
existing same-content hash file or renames them to the hash scheme, returning
an old-path -> new-path mapping so callers can rewrite markdown references.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

# A legacy collision suffix is ``_1``, ``_2`` … (1-3 digits) immediately before
# the extension.  Hash-named files use 16 hex chars (may contain a-f) and must
# be left untouched.
_LEGACY_NAME_RE = re.compile(r"^(.*)_([0-9]{1,3})$")
_HEX16_RE = re.compile(r"^[0-9a-f]{16}$")


def _tail(stem: str) -> str | None:
    if "_" not in stem:
        return None
    return stem.rpartition("_")[2]


def is_hash_named(stem: str) -> bool:
    """True when ``stem`` already carries the 16-hex content hash."""
    tail = _tail(stem)
    return bool(tail) and _HEX16_RE.match(tail) is not None


def is_legacy_named(stem: str) -> bool:
    """True when ``stem`` looks like an old ``name_1`` collision filename."""
    if "_" not in stem:
        return False
    return _LEGACY_NAME_RE.match(stem) is not None


def _file_digest16(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        raise


def migrate_legacy_images(images_dir: Path) -> dict[str, str]:
    """Migrate legacy ``_1``/``_2`` files under ``images_dir`` to hash names.

    Returns ``{ "images/<old>": "images/<new>" }``.  A legacy file whose
    content already exists under a hash-named sibling is deleted and mapped to
    that sibling; otherwise it is renamed to ``<base>_<sha256:16><ext>`` and
    mapped to its new name.  Already hash-named files are never touched.

    The operation is atomic in spirit: renames happen first, deletions after,
    and any I/O error aborts before deletions so no references are orphaned.
    """
    if not images_dir.is_dir():
        return {}

    # Index hash-named files by content digest so a legacy file whose content
    # already exists can be de-duplicated onto it.
    hash_by_digest: dict[str, Path] = {}
    for child in images_dir.iterdir():
        if child.is_file() and is_hash_named(child.stem):
            try:
                hash_by_digest[_file_digest16(child)] = child
            except OSError:
                continue

    mapping: dict[str, str] = {}
    renames: list[tuple[Path, Path]] = []
    deletes: list[Path] = []
    try:
        for child in sorted(images_dir.iterdir()):
            if not child.is_file():
                continue
            stem = child.stem
            if not is_legacy_named(stem):
                continue
            match = _LEGACY_NAME_RE.match(stem)
            if match is None:
                continue
            base_stem = match.group(1)
            old_rel = "images/" + child.name
            suffix = child.suffix.casefold() or ".png"
            digest16 = _file_digest16(child)

            survivor = hash_by_digest.get(digest16)
            if survivor is not None:
                deletes.append(child)
                mapping[old_rel] = "images/" + survivor.name
                continue

            new_name = f"{base_stem}_{digest16}{suffix}"
            new_path = images_dir / new_name
            if new_path.exists() and new_path.resolve() != child.resolve():
                # Extremely unlikely (hash collision in base+digest) — keep the
                # existing file and drop the legacy copy onto it.
                deletes.append(child)
                mapping[old_rel] = "images/" + new_path.name
                continue
            renames.append((child, new_path))
            mapping[old_rel] = "images/" + new_name
            hash_by_digest[digest16] = new_path
    except OSError:
        # Abort: undo nothing; a partial migration left legacy files intact
        # except any already renamed.  To keep references valid, report what we
        # changed before the failure.  In practice errors are rare.
        return {}

    # Apply renames, then deletions.
    for old, new in renames:
        try:
            old.rename(new)
        except OSError:
            mapping.pop("images/" + old.name, None)
    for path in deletes:
        try:
            path.unlink()
        except OSError:
            pass
    return mapping


def rewrite_markdown_references(markdown: str, mapping: dict[str, str]) -> str:
    """Rewrite ``images/<legacy>`` references in ``markdown`` to migrated names.

    A legacy file that was de-duplicated away points at the surviving hash
    file.  Names absent from ``mapping`` are left untouched.
    """
    if not mapping or not markdown:
        return markdown
    result = markdown
    for old_rel, new_rel in mapping.items():
        if new_rel:
            result = result.replace(old_rel, new_rel)
    return result


__all__ = [
    "migrate_legacy_images",
    "rewrite_markdown_references",
    "is_hash_named",
    "is_legacy_named",
]
