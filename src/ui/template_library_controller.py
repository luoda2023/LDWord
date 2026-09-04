"""UI-agnostic template-library selection and CRUD decisions."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
import re

from src.config.library import (
    ConfigLibraryEntry,
    default_template_entry,
    get_template_entry,
    is_template_user_library_path,
    is_template_library_path,
    list_template_entries,
    load_template_from_library,
    save_template_to_library,
    template_source_type_for_path,
)
from src.config.loader import load_template
from src.config.template import TemplateConfig
from src.config.template_identity import allocate_template_id, safe_template_file_stem


@dataclass(frozen=True, slots=True)
class TemplateLibraryOption:
    template_id: str
    name: str
    tooltip: str = ""
    source_type: str = "builtin"
    disabled: bool = False


@dataclass(frozen=True, slots=True)
class TemplateLibrarySelection:
    template: TemplateConfig
    template_id: str
    path: str
    source: str
    source_type: str


class TemplateLibraryController:
    """Keep storage and provenance rules outside the 2,000-line panel."""

    def options(
        self,
        *,
        mode_id: str,
        current_template_id: str,
        current_template: TemplateConfig | None,
        include_current: bool,
    ) -> tuple[TemplateLibraryOption, ...]:
        entries = list_template_entries(mode_id=mode_id)
        entry_by_id = {entry.config_id: entry for entry in entries}
        ordered_ids: list[str] = []
        seen: set[str] = set()
        for entry in entries:
            if entry.config_id and entry.config_id not in seen:
                seen.add(entry.config_id)
                ordered_ids.append(entry.config_id)
        current_id = str(current_template_id or "").strip()
        if current_id and current_id not in seen and include_current:
            ordered_ids.insert(0, current_id)

        options: list[TemplateLibraryOption] = []
        for template_id in ordered_ids:
            entry = entry_by_id.get(template_id)
            name = self._option_name(
                template_id,
                entry=entry,
                current_template_id=current_id,
                current_template=current_template,
            )
            load_error = str(getattr(entry, "load_error", "") or "").strip()
            options.append(
                TemplateLibraryOption(
                    template_id=template_id,
                    name=name,
                    tooltip=load_error or str(getattr(entry, "path", "") or ""),
                    source_type=str(getattr(entry, "source_type", "") or "user"),
                    disabled=bool(load_error),
                )
            )
        return tuple(options)

    def load_selection(
        self,
        *,
        mode_id: str,
        template_id: str,
        current_template_id: str,
        current_template: TemplateConfig | None,
        current_path: str,
        current_source: str,
    ) -> TemplateLibrarySelection:
        target_id = str(template_id or "").strip()
        if not target_id:
            raise ValueError("模板 id 为空")
        entry = get_template_entry(target_id, mode_id=mode_id)
        if entry is not None:
            if not entry.is_available:
                raise ValueError(
                    f"模板“{entry.name or target_id}”不可用：{entry.load_error}"
                )
            return TemplateLibrarySelection(
                template=load_template_from_library(
                    entry.config_id,
                    mode_id=mode_id,
                ),
                template_id=entry.config_id,
                path=str(entry.path),
                source="library",
                source_type=entry.source_type,
            )
        if target_id == str(current_template_id or "").strip():
            path = Path(current_path) if str(current_path or "").strip() else None
            if path is not None and path.exists() and not path.is_dir():
                source = "library" if is_template_library_path(path) else "file"
                return TemplateLibrarySelection(
                    template=load_template(path),
                    template_id=target_id,
                    path=str(path),
                    source=source,
                    source_type=template_source_type_for_path(path),
                )
            if current_template is not None:
                source = str(current_source or "").strip()
                return TemplateLibrarySelection(
                    template=current_template,
                    template_id=target_id,
                    path=str(current_path or ""),
                    source=source,
                    source_type=("builtin" if source == "builtin" else ""),
                )
        raise ValueError(f"找不到模板：{target_id}")

    def create_copy(
        self,
        *,
        mode_id: str,
        source_template: TemplateConfig | None,
        name: str,
    ) -> TemplateLibrarySelection:
        if source_template is None:
            source_template = self.default_selection(mode_id=mode_id).template
        template = copy.deepcopy(source_template)
        template.name = name
        entry = save_template_to_library(
            template,
            template_id=self.unique_template_id(mode_id=mode_id, name=name),
            mode_id=mode_id,
        )
        return TemplateLibrarySelection(
            template=load_template_from_library(entry.config_id, mode_id=mode_id),
            template_id=entry.config_id,
            path=str(entry.path),
            source="library",
            source_type="user",
        )

    def unique_template_id(self, *, mode_id: str, name: str) -> str:
        return allocate_template_id(name=name, mode_id=mode_id)

    def unique_copy_name(
        self,
        *,
        mode_id: str,
        current_name: str,
    ) -> str:
        normalized = str(current_name or "自定义模板").strip() or "自定义模板"
        base_name = re.sub(r"\s*副本(?:\s*\d+)?$", "", normalized).strip() or normalized
        existing_names = {
            str(entry.name or "").strip()
            for entry in list_template_entries(mode_id=mode_id)
            if str(entry.name or "").strip()
        }

        def available(name: str) -> bool:
            return (
                name not in existing_names
                and self.unique_template_id(mode_id=mode_id, name=name)
                == safe_template_file_stem(name)
            )

        first = f"{base_name} 副本"
        if available(first):
            return first
        for index in range(2, 1001):
            candidate = f"{base_name} 副本 {index}"
            if available(candidate):
                return candidate
        return f"{base_name} 副本 1001"

    def is_builtin(
        self,
        *,
        mode_id: str,
        template_id: str,
        path: str,
        source: str,
        source_type: str,
    ) -> bool:
        target_id = str(template_id or "").strip()
        if not target_id:
            return False
        if source_type:
            return source_type == "builtin"
        if source == "builtin":
            return True
        if source == "file":
            return False
        entry = get_template_entry(target_id, mode_id=mode_id)
        if entry is not None:
            current_path = Path(path) if str(path or "").strip() else None
            if current_path is None:
                return entry.source_type == "builtin"
            try:
                if current_path.resolve() == entry.path.resolve():
                    return entry.source_type == "builtin"
            except OSError:
                if current_path == entry.path:
                    return entry.source_type == "builtin"
            if source == "library":
                return False
        return False

    def manageable_path(self, *, path: str, source_type: str) -> Path | None:
        candidate = Path(path) if str(path or "").strip() else None
        if candidate is None or not candidate.exists() or candidate.is_dir():
            return None
        claimed_source = str(source_type or "").strip()
        if claimed_source and claimed_source != "user":
            return None
        return candidate if is_template_user_library_path(candidate) else None

    def source_type_for_context(
        self,
        *,
        mode_id: str,
        template_id: str,
        path: str,
        source: str,
    ) -> str:
        channel = str(source or "").strip()
        if channel in {"builtin", "runtime"}:
            return channel
        if str(path or "").strip():
            return template_source_type_for_path(path)
        if channel == "file":
            return "external"
        if channel == "library":
            entry = get_template_entry(template_id, mode_id=mode_id)
            if entry is not None:
                return entry.source_type
        return ""

    def default_selection(self, *, mode_id: str) -> TemplateLibrarySelection:
        entry = default_template_entry(mode_id=mode_id)
        if entry is not None:
            return TemplateLibrarySelection(
                template=load_template_from_library(entry.config_id, mode_id=mode_id),
                template_id=entry.config_id,
                path=str(entry.path),
                source="library",
                source_type=entry.source_type,
            )
        raise FileNotFoundError(
            f"default_template_ref_unresolved: mode={str(mode_id or '').strip()}"
        )

    @staticmethod
    def delete_user_template(path: Path) -> None:
        if not is_template_user_library_path(path):
            raise ValueError(f"not an owned user template: {path}")
        path.unlink()

    @staticmethod
    def _option_name(
        template_id: str,
        *,
        entry: ConfigLibraryEntry | None,
        current_template_id: str,
        current_template: TemplateConfig | None,
    ) -> str:
        if entry is not None and not entry.is_available:
            return entry.display_name
        if template_id == current_template_id and current_template is not None:
            current_name = str(current_template.name or "").strip()
            if current_name:
                return current_name
        if entry is not None:
            return entry.name
        return template_id


__all__ = [
    "TemplateLibraryController",
    "TemplateLibraryOption",
    "TemplateLibrarySelection",
]
