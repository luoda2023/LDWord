"""UI selector projections for work-mode scoped configs.

The data layer still uses ``SceneWorkspace`` and ``TemplateConfig``.  This
adapter gives panels one shared vocabulary for user-facing selectors:
plans, templates, and masters.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from pathlib import Path

from src.config.library import (
    ConfigLibraryEntry,
    SceneLibraryDescriptor,
    get_template_entry,
    library_read_session,
    list_scene_descriptors,
    list_template_entries,
)
from src.config.master_library import MasterSpec, list_masters
from src.config.material_package_library import list_material_package_entries

SOURCE_LABELS: dict[str, str] = {
    "builtin": "内置",
    "user": "用户",
    "legacy": "旧版",
    "discovered": "用户",
}

_SELECTOR_PROJECTION_CACHE: ContextVar[dict[object, object] | None] = ContextVar(
    "selector_projection_cache",
    default=None,
)


def scoped_selector_projections(function: Callable):
    """Share immutable selector reads only within one UI construction call."""

    @wraps(function)
    def wrapped(*args, **kwargs):
        token = _SELECTOR_PROJECTION_CACHE.set({})
        try:
            with library_read_session():
                return function(*args, **kwargs)
        finally:
            _SELECTOR_PROJECTION_CACHE.reset(token)

    return wrapped


@dataclass(frozen=True, slots=True)
class SelectorOption:
    """One item shown in a combo box or selector list."""

    value: str
    label: str
    tooltip: str = ""
    source_type: str = ""
    disabled: bool = False


def strip_source_prefix(label: str) -> str:
    """Remove source prefixes added for compact combo labels."""

    text = str(label or "").strip()
    for source in SOURCE_LABELS.values():
        for noun in ("方案", "模板", "母版", "卷面", "版式", "装配项", "资料包"):
            prefix = f"{source}{noun}："
            if text.startswith(prefix):
                return text[len(prefix) :].strip()
    return text


def plan_display_label(descriptor: SceneLibraryDescriptor) -> str:
    """Return the user-facing plan name for a scene descriptor."""

    return _with_noun(
        str(getattr(descriptor, "display_name", "") or getattr(descriptor, "name", "") or "").strip(),
        "方案",
    )


def plan_combo_label(
    descriptor: SceneLibraryDescriptor,
    *,
    include_source_prefix: bool = False,
) -> str:
    return _source_prefixed(
        plan_display_label(descriptor),
        str(getattr(descriptor, "source_type", "") or ""),
        "方案",
        include_source_prefix=include_source_prefix,
    )


def plan_selector_options(
    mode_id: str,
    *,
    include_source_prefix: bool = False,
) -> tuple[SelectorOption, ...]:
    return tuple(
        SelectorOption(
            value=descriptor.config_id,
            label=plan_combo_label(
                descriptor,
                include_source_prefix=include_source_prefix,
            ),
            tooltip=_path_or_error_tooltip(
                getattr(descriptor, "path", None),
                getattr(descriptor, "load_error", ""),
            ),
            source_type=str(getattr(descriptor, "source_type", "") or ""),
            disabled=bool(getattr(descriptor, "load_error", "")),
        )
        for descriptor in plan_selector_descriptors(mode_id)
    )


def plan_selector_descriptors(mode_id: str) -> tuple[SceneLibraryDescriptor, ...]:
    """Return the processing plans owned by one work mode."""

    normalized_mode = str(mode_id or "").strip()
    cache = _SELECTOR_PROJECTION_CACHE.get()
    cache_key = ("plan_descriptors", normalized_mode)
    if cache is not None and cache_key in cache:
        return cache[cache_key]
    result = tuple(list_scene_descriptors(mode_id=normalized_mode))
    if cache is not None:
        cache[cache_key] = result
    return result


def template_display_label(
    template_id: str,
    *,
    mode_id: str,
    fallback: str = "",
) -> str:
    cache = _SELECTOR_PROJECTION_CACHE.get()
    cache_key = (
        "template_display_label",
        str(mode_id or "").strip(),
        str(template_id or "").strip(),
        str(fallback or ""),
    )
    if cache is not None and cache_key in cache:
        return cache[cache_key]
    entry = get_template_entry(template_id, mode_id=mode_id)
    if entry is not None:
        result = str(entry.display_name or entry.config_id).strip()
    else:
        result = str(fallback or template_id or "").strip()
    if cache is not None:
        cache[cache_key] = result
    return result


def template_combo_label(
    label: str,
    entry: ConfigLibraryEntry | None,
    *,
    include_source_prefix: bool = True,
) -> str:
    return _source_prefixed(
        str(label or "").strip(),
        str(getattr(entry, "source_type", "") or ""),
        "模板",
        include_source_prefix=include_source_prefix,
    )


def template_selector_options(
    mode_id: str,
    *,
    template_ids: Iterable[str] | None = None,
    fallback_labels: dict[str, str] | None = None,
    include_source_prefix: bool = True,
) -> tuple[SelectorOption, ...]:
    fallbacks = dict(fallback_labels or {})
    requested_ids = [
        str(template_id or "").strip()
        for template_id in list(template_ids or ())
        if str(template_id or "").strip()
    ]
    cache = _SELECTOR_PROJECTION_CACHE.get()
    cache_key = (
        "template_options",
        str(mode_id or "").strip(),
        tuple(requested_ids),
        tuple(sorted((str(key), str(value)) for key, value in fallbacks.items())),
        bool(include_source_prefix),
    )
    if cache is not None and cache_key in cache:
        return cache[cache_key]
    if not requested_ids:
        requested_ids = [
            str(entry.config_id or "").strip()
            for entry in list_template_entries(mode_id=mode_id)
            if str(entry.config_id or "").strip()
        ]

    options: list[SelectorOption] = []
    seen: set[str] = set()
    for template_id in requested_ids:
        if template_id in seen:
            continue
        seen.add(template_id)
        entry = get_template_entry(template_id, mode_id=mode_id)
        if entry is None:
            continue
        label = (
            str(getattr(entry, "name", "") or "").strip()
        )
        if not label or label == template_id:
            if str(getattr(entry, "source_type", "") or "").strip() == "builtin":
                label = str(fallbacks.get(template_id) or template_id).strip()
            else:
                label = str(label or template_id).strip()
        if not bool(getattr(entry, "is_available", True)):
            label = f"{label} (Unavailable)"
        options.append(
            SelectorOption(
                value=template_id,
                label=template_combo_label(
                    label,
                    entry,
                    include_source_prefix=include_source_prefix,
                ),
                tooltip=_path_or_error_tooltip(
                    getattr(entry, "path", None),
                    getattr(entry, "load_error", ""),
                ),
                source_type=str(getattr(entry, "source_type", "") or ""),
                disabled=bool(getattr(entry, "load_error", "")),
            )
        )
    result = tuple(options)
    if cache is not None:
        cache[cache_key] = result
    return result


def master_display_label(master: MasterSpec) -> str:
    text = str(getattr(master, "label", "") or getattr(master, "master_id", "") or "").strip()
    mode = str(getattr(master, "mode_id", "") or "").strip()
    if mode == "exam":
        if str(getattr(master, "source_type", "") or "").strip() == "builtin":
            return _exam_builtin_master_label(
                text,
                master_id=str(getattr(master, "master_id", "") or ""),
            )
        return text
    if mode == "official":
        return text.replace("母版", "版式")
    return _with_noun(text, "装配项")


def master_selector_options(
    mode_id: str,
    *,
    exam_config=None,
    user_master_dir=None,
    include_source_prefix: bool = False,
) -> tuple[SelectorOption, ...]:
    noun = _master_source_noun(mode_id)
    return tuple(
        SelectorOption(
            value=master.master_id,
            label=_source_prefixed(
                master_display_label(master),
                master.source_type,
                noun,
                include_source_prefix=include_source_prefix,
            ),
            tooltip=_path_or_error_tooltip(master.docx_path, ""),
            source_type=master.source_type,
            disabled=False,
        )
        for master in list_masters(
            mode_id,
            exam_config=exam_config,
            user_master_dir=user_master_dir,
        )
    )


def material_package_selector_options(
    mode_id: str,
    *,
    include_source_prefix: bool = False,
) -> tuple[SelectorOption, ...]:
    """Return every saved material package visible in one work mode."""

    entries = tuple(list_material_package_entries(mode_id=mode_id))
    name_counts: dict[str, int] = {}
    for entry in entries:
        key = entry.display_name.casefold()
        name_counts[key] = name_counts.get(key, 0) + 1

    return tuple(
        SelectorOption(
            value=entry.qualified_id,
            label=_source_prefixed(
                _disambiguated_material_package_label(
                    entry.display_name,
                    entry.package_id,
                    duplicate=name_counts.get(
                        entry.display_name.casefold(),
                        0,
                    )
                    > 1,
                ),
                entry.source_type,
                "资料包",
                include_source_prefix=include_source_prefix,
            ),
            tooltip=_path_or_error_tooltip(entry.path, entry.load_error),
            source_type=entry.source_type,
            disabled=not entry.is_available,
        )
        for entry in entries
    )


def _disambiguated_material_package_label(
    display_name: str,
    package_id: str,
    *,
    duplicate: bool,
) -> str:
    if not duplicate:
        return display_name
    short_id = str(package_id or "").removeprefix("pkg_")[-6:]
    return f"{display_name} · {short_id or '未编号'}"


def _master_source_noun(mode_id: str) -> str:
    mode = str(mode_id or "").strip()
    if mode == "exam":
        return "卷面"
    if mode == "official":
        return "版式"
    return "装配项"


def _exam_builtin_master_label(label: str, *, master_id: str = "") -> str:
    display_by_id = {
        "default_exam": "A4 标准卷面",
    }
    normalized_id = str(master_id or "").strip()
    if normalized_id in display_by_id:
        return display_by_id[normalized_id]
    text = str(label or "").strip()
    legacy_map = {
        "默认试卷": "A4 标准卷面",
        "默认卷面": "A4 标准卷面",
    }
    if text in legacy_map:
        return legacy_map[text]
    if text.endswith("试卷"):
        text = text[: -len("试卷")].rstrip()
    return _with_noun(text or "默认", "卷面")


def _with_noun(label: str, noun: str) -> str:
    text = str(label or "").strip() or noun
    if text.endswith(noun):
        return text
    return f"{text}{noun}"


def _source_prefixed(
    label: str,
    source_type: str,
    noun: str,
    *,
    include_source_prefix: bool,
) -> str:
    text = str(label or "").strip()
    if not include_source_prefix:
        return text
    source = SOURCE_LABELS.get(str(source_type or "").strip())
    if source and text:
        return f"{source}{noun}：{text}"
    return text


def _path_or_error_tooltip(path: Path | str | None, error: str) -> str:
    error_text = str(error or "").strip()
    if error_text:
        return error_text
    if path is None:
        return ""
    return str(path)


__all__ = [
    "SOURCE_LABELS",
    "SelectorOption",
    "master_display_label",
    "master_selector_options",
    "material_package_selector_options",
    "plan_combo_label",
    "plan_display_label",
    "plan_selector_descriptors",
    "plan_selector_options",
    "strip_source_prefix",
    "template_combo_label",
    "template_display_label",
    "template_selector_options",
]
