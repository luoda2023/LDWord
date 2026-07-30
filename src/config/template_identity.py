"""One source of truth for user-template file identities."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import re

from src.config.builtin_templates import list_builtin_template_ids
from src.config.library import list_template_entries, template_user_dir
from src.config.template import TemplateConfig


_WINDOWS_RESERVED_STEMS = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def safe_template_file_stem(value: str) -> str:
    forbidden = '<>:"/\\|?*'
    cleaned = "".join(
        character if character not in forbidden and ord(character) >= 32 else "_"
        for character in str(value or "").strip()
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._")
    if not cleaned:
        cleaned = "template"
    if cleaned.upper() in _WINDOWS_RESERVED_STEMS:
        cleaned = f"template_{cleaned}"
    return cleaned[:96].rstrip(" ._") or "template"


def allocate_template_id(
    *,
    name: str,
    mode_id: str,
    equivalent_template: TemplateConfig | None = None,
) -> str:
    """Allocate a collision-free id, optionally recognizing an identical file."""

    base_id = safe_template_file_stem(name)
    entries = {
        str(entry.config_id or "").casefold(): entry
        for entry in list_template_entries(mode_id=mode_id)
        if str(entry.config_id or "").strip()
    }
    reserved_ids = {item.casefold() for item in list_builtin_template_ids()}
    user_dir = template_user_dir(mode_id)
    desired_payload = (
        asdict(equivalent_template) if equivalent_template is not None else None
    )

    for index in range(1, 1001):
        candidate = base_id if index == 1 else f"{base_id}_{index}"
        candidate_key = candidate.casefold()
        existing = entries.get(candidate_key)
        if (
            desired_payload is not None
            and existing is not None
            and existing.source_type == "user"
            and existing.path.suffix.casefold() == ".json"
            and existing.path.exists()
        ):
            try:
                from src.config.loader import load_template

                if asdict(load_template(existing.path)) == desired_payload:
                    return existing.config_id
            except (OSError, ValueError, TypeError):
                pass
        if (
            candidate_key not in entries
            and candidate_key not in reserved_ids
            and not any(
                path.exists() for path in _candidate_paths(user_dir, candidate)
            )
        ):
            return candidate
    raise ValueError("无法为模板分配不冲突的内部名称")


def _candidate_paths(directory: Path, template_id: str) -> set[Path]:
    return {
        directory / f"{template_id}{suffix}"
        for suffix in (".json", ".yaml", ".yml")
    }


__all__ = ["allocate_template_id", "safe_template_file_stem"]
