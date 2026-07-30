"""UI selector projections for work-mode scoped configs.

The data layer still uses ``SceneWorkspace`` and ``TemplateConfig``.  This
adapter gives panels one shared vocabulary for user-facing selectors:
plans, templates, and masters.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.config.library import (
    ConfigLibraryEntry,
    SceneLibraryDescriptor,
    list_scene_descriptors,
    list_template_entries,
    get_template_entry,
)
from src.config.master_library import MasterSpec, list_masters


SOURCE_LABELS: dict[str, str] = {
    "builtin": "内置",
    "user": "用户",
    "legacy": "旧版",
    "discovered": "用户",
}


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

    return tuple(list_scene_descriptors(mode_id=str(mode_id or "").strip()))


def template_display_label(
    template_id: str,
    *,
    mode_id: str,
    fallback: str = "",
) -> str:
    entry = get_template_entry(template_id, mode_id=mode_id)
    if entry is not None:
        return str(entry.display_name or entry.config_id).strip()
    return str(fallback or template_id or "").strip()


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
    return tuple(options)


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


def material_package_sample_selector_options(
    mode_id: str,
    *,
    source_type: str | None = None,
    profile_id: str | None = None,
    include_source_prefix: bool = True,
) -> tuple[SelectorOption, ...]:
    """Return material package samples visible for one work mode."""

    mode = str(mode_id or "").strip()
    if mode != "official":
        return ()

    from src.shared.engine.official_document_material_package import (
        list_official_document_material_package_samples,
    )

    target_profile = str(profile_id or "").strip()
    if target_profile.startswith("official:"):
        target_profile = target_profile.split(":", 1)[1].strip()

    return tuple(
        SelectorOption(
            value=sample.qualified_id,
            label=_source_prefixed(
                str(sample.label or sample.sample_id).strip(),
                sample.source_type,
                "资料包",
                include_source_prefix=include_source_prefix,
            ),
            tooltip=_path_or_error_tooltip(sample.path, sample.load_error),
            source_type=sample.source_type,
            disabled=not sample.is_available,
        )
        for sample in list_official_document_material_package_samples(
            source_type=source_type,
        )
        if (
            not target_profile
            or sample.profile_id == target_profile
            or not sample.is_available
        )
    )


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
    "SelectorOption",
    "SOURCE_LABELS",
    "master_display_label",
    "master_selector_options",
    "material_package_sample_selector_options",
    "plan_combo_label",
    "plan_display_label",
    "plan_selector_descriptors",
    "plan_selector_options",
    "strip_source_prefix",
    "template_combo_label",
    "template_display_label",
    "template_selector_options",
]
