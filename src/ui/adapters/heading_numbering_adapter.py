"""Heading numbering adapter used by template editing panels."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import TYPE_CHECKING

from src.config.heading_normalize import CHAIN_NUMBER_STYLE_BY_CORE, CURRENT_CORE_STYLE_ALIASES
from src.config.heading_style_semantics import (
    NON_NUMBERED_HEADING_CUSTOM,
    NON_NUMBERED_HEADING_INHERIT_HEADING1,
    NON_NUMBERED_HEADING_STYLE_KEY,
    ensure_heading_style_override,
    ensure_non_numbered_heading_style_override,
    normalize_non_numbered_heading_style_mode,
    remove_heading_style_override as _remove_heading_style_override,
    resolve_heading_style,
    resolve_heading_style_source,
    resolve_non_numbered_heading_style,
    resolve_non_numbered_heading_style_source,
)
from src.config.special_title_rules import (
    EXACT_RULE_KIND,
    PREFIX_RULE_KIND,
    capture_special_title_reference_snapshot,
    match_special_title,
    reconcile_special_title_references,
    restore_special_title_reference_snapshot,
    validate_special_title_values,
)
from src.config.style_semantics import display_font_size_with_name, resolve_style_size_pt
from src.qt_api import QObject, Signal
from src.shared.engine.numbering import format_number
from src.shared.engine.heading_numbering_format import (
    format_heading_level_number,
    parse_heading_number_chain,
)
from src.ui.heading_numbering_logic import default_chain_value

DEFAULT_HEADING_PRESET_KEY = "thesis_standard"

if TYPE_CHECKING:
    from src.config.template import (
        HeadingLevelBindingConfig,
        TemplateConfig,
    )


class HeadingNumberingAdapter(QObject):
    """UI adapter for heading numbering and per-level heading styles."""

    numbering_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._template: TemplateConfig | None = None
        self._snapshot_bindings: dict | None = None
        self._snapshot_styles: dict | None = None
        self._snapshot_model_fields: dict | None = None
        self._snapshot_special_title_references = None
        self._last_applied_preset_key: str | None = None

    def set_template(self, template: TemplateConfig) -> None:
        self._last_applied_preset_key = None
        self._template = template
        self.numbering_changed.emit()

    @property
    def template(self) -> TemplateConfig:
        if self._template is None:
            raise RuntimeError("Adapter 未绑定 template")
        return self._template

    @property
    def has_template(self) -> bool:
        return self._template is not None

    def capture_snapshot(self) -> None:
        if not self.has_template:
            self._snapshot_bindings = None
            self._snapshot_styles = None
            self._snapshot_model_fields = None
            self._snapshot_special_title_references = None
            return
        self._snapshot_bindings = deepcopy(self.template.heading_numbering.level_bindings)
        self._snapshot_styles = self._current_heading_styles_snapshot()
        self._snapshot_model_fields = self._current_model_fields_snapshot()
        self._snapshot_special_title_references = (
            capture_special_title_reference_snapshot(self.template)
        )

    def restore_snapshot(self) -> bool:
        if not self.has_template or self._snapshot_bindings is None:
            return False

        self.template.heading_numbering.level_bindings = deepcopy(self._snapshot_bindings)

        if self._snapshot_styles is not None:
            for key in list(self.template.styles.keys()):
                if key.startswith("heading"):
                    del self.template.styles[key]
            for key, value in self._snapshot_styles.items():
                self.template.styles[key] = deepcopy(value)

        if self._snapshot_model_fields is not None:
            model = self.template.heading_model
            model.max_heading_levels = self._snapshot_model_fields["max_heading_levels"]
            model.non_numbered_title_texts = list(
                self._snapshot_model_fields["non_numbered_title_texts"]
            )
            model.non_numbered_prefixes = list(
                self._snapshot_model_fields["non_numbered_prefixes"]
            )
            model.non_numbered_heading_style_mode = self._snapshot_model_fields[
                "non_numbered_heading_style_mode"
            ]
        if self._snapshot_special_title_references is not None:
            restore_special_title_reference_snapshot(
                self.template,
                self._snapshot_special_title_references,
            )
        self.numbering_changed.emit()
        return True

    @property
    def has_unsaved_changes(self) -> bool:
        if not self.has_template or self._snapshot_bindings is None:
            return False
        if self._snapshot_bindings != self.template.heading_numbering.level_bindings:
            return True
        if self._snapshot_styles != self._current_heading_styles_snapshot():
            return True
        if self._snapshot_model_fields != self._current_model_fields_snapshot():
            return True
        return (
            self._snapshot_special_title_references
            != capture_special_title_reference_snapshot(self.template)
        )

    def _current_heading_styles_snapshot(self) -> dict:
        return {
            key: deepcopy(value)
            for key, value in self.template.styles.items()
            if key.startswith("heading")
        }

    def _current_model_fields_snapshot(self) -> dict:
        model = self.template.heading_model
        return {
            "max_heading_levels": model.max_heading_levels,
            "non_numbered_title_texts": list(model.non_numbered_title_texts or []),
            "non_numbered_prefixes": list(model.non_numbered_prefixes or []),
            "non_numbered_heading_style_mode": normalize_non_numbered_heading_style_mode(
                getattr(model, "non_numbered_heading_style_mode", None)
            ),
        }

    def ensure_default_scheme(self, preset_key: str = DEFAULT_HEADING_PRESET_KEY) -> bool:
        if not self.has_template:
            return False
        bindings = self.template.heading_numbering.level_bindings
        if any(str(key).startswith("heading") for key in bindings):
            return False

        from src.config.heading_presets import get_preset_bindings, get_preset_max_levels

        preset_bindings = get_preset_bindings(preset_key)
        if preset_bindings is None:
            return False
        for key, binding in preset_bindings.items():
            bindings[key] = deepcopy(binding)
        max_levels = get_preset_max_levels(preset_key)
        if max_levels is not None:
            self.template.heading_model.max_heading_levels = max(1, min(int(max_levels), 8))
        self._last_applied_preset_key = preset_key
        return True

    def detect_active_preset(self) -> str | None:
        from src.config.heading_presets import get_scheme_catalog

        bindings = self.template.heading_numbering.level_bindings
        catalog = get_scheme_catalog()
        preferred_key = self._last_applied_preset_key
        if preferred_key and preferred_key in catalog:
            entry = catalog[preferred_key]
            if int(entry.get("max_levels") or self.max_levels) == self.max_levels:
                if self._bindings_match(bindings, entry["bindings"]):
                    return preferred_key

        for preset_key, entry in catalog.items():
            if int(entry.get("max_levels") or self.max_levels) != self.max_levels:
                continue
            if self._bindings_match(bindings, entry["bindings"]):
                return preset_key
        return None

    def _bindings_match(self, current: dict, preset: dict) -> bool:
        from src.config.template import HeadingLevelBindingConfig as BindingConfig

        for level in range(1, 9):
            key = f"heading{level}"
            current_binding = current.get(key) or BindingConfig()
            preset_binding = preset.get(key) or BindingConfig()
            if asdict(current_binding) != asdict(preset_binding):
                return False
        return True

    @property
    def max_levels(self) -> int:
        return self.template.heading_model.max_heading_levels

    def get_binding(self, level: int) -> HeadingLevelBindingConfig:
        key = f"heading{level}"
        bindings = self.template.heading_numbering.level_bindings
        if key in bindings:
            return deepcopy(bindings[key])
        from src.config.template import HeadingLevelBindingConfig as BindingConfig

        return BindingConfig()

    def get_non_numbered_texts(self) -> list[str]:
        return list(self.template.heading_model.non_numbered_title_texts or [])

    def get_non_numbered_prefixes(self) -> list[str]:
        return list(self.template.heading_model.non_numbered_prefixes or [])

    def get_non_numbered_heading_style_mode(self) -> str:
        return normalize_non_numbered_heading_style_mode(
            getattr(self.template.heading_model, "non_numbered_heading_style_mode", None)
        )

    def set_non_numbered_heading_style_mode(self, mode: str) -> None:
        normalized = normalize_non_numbered_heading_style_mode(mode)
        self.template.heading_model.non_numbered_heading_style_mode = normalized
        if normalized == NON_NUMBERED_HEADING_CUSTOM:
            ensure_non_numbered_heading_style_override(self.template)
        self.numbering_changed.emit()

    def get_non_numbered_heading_style(self):
        from src.config.template import StyleConfig

        style = resolve_non_numbered_heading_style(self.template, include_body_fallback=True)
        return style if style is not None else StyleConfig()

    def get_non_numbered_heading_style_source(self) -> str | None:
        return resolve_non_numbered_heading_style_source(self.template)

    def has_non_numbered_heading_style_override(self) -> bool:
        return NON_NUMBERED_HEADING_STYLE_KEY in self.template.styles

    def set_non_numbered_heading_style_field(self, field_name: str, value) -> None:
        style = ensure_non_numbered_heading_style_override(self.template)
        self.template.heading_model.non_numbered_heading_style_mode = NON_NUMBERED_HEADING_CUSTOM
        if hasattr(style, field_name):
            setattr(style, field_name, value)
            self.numbering_changed.emit()

    def remove_non_numbered_heading_style_override(self) -> bool:
        from src.config.heading_style_semantics import remove_non_numbered_heading_style_override

        result = remove_non_numbered_heading_style_override(self.template)
        self.template.heading_model.non_numbered_heading_style_mode = NON_NUMBERED_HEADING_INHERIT_HEADING1
        if result:
            self.numbering_changed.emit()
        return result

    def get_heading_style(self, level: int):
        from src.config.template import StyleConfig

        style = resolve_heading_style(self.template, level, include_body_fallback=True)
        return style if style is not None else StyleConfig()

    def get_heading_style_source(self, level: int) -> str | None:
        return resolve_heading_style_source(self.template, level, include_body_fallback=True)

    def heading_style_source_text(self, level: int) -> str:
        source = self.get_heading_style_source(level)
        own_key = f"heading{int(level)}"
        if source == own_key:
            return f"当前来源：本级覆盖样式（{own_key}）。"
        if source == "heading":
            return f"当前来源：通用标题样式（heading）。首次修改后会为级别 {level} 创建独立覆盖。"
        if source == "body":
            return f"当前来源：正文样式回退（body）。首次修改后会为级别 {level} 创建独立覆盖。"
        if source == "normal":
            return f"当前来源：普通样式回退（normal）。首次修改后会为级别 {level} 创建独立覆盖。"
        return f"当前来源：未定义样式。首次修改后会为级别 {level} 创建独立覆盖。"

    def set_heading_style_field(self, level: int, field_name: str, value) -> None:
        style = ensure_heading_style_override(self.template, level)
        if hasattr(style, field_name):
            setattr(style, field_name, value)
            self.numbering_changed.emit()

    def heading_style_summary(self, level: int) -> str:
        style = self.get_heading_style(level)
        parts: list[str] = []
        if style.font_cn:
            parts.append(style.font_cn)
        size_pt = resolve_style_size_pt(style)
        if size_pt is not None:
            parts.append(display_font_size_with_name(size_pt))
        if style.bold:
            parts.append("加粗")
        if style.italic:
            parts.append("斜体")

        alignment_labels = {
            "left": "左对齐",
            "center": "居中",
            "right": "右对齐",
            "justify": "两端对齐",
        }
        if style.alignment and style.alignment in alignment_labels:
            parts.append(alignment_labels[style.alignment])
        return " / ".join(parts) if parts else "未设置"

    def non_numbered_heading_style_summary(self) -> str:
        style = self.get_non_numbered_heading_style()
        parts: list[str] = []
        if style.font_cn:
            parts.append(style.font_cn)
        size_pt = resolve_style_size_pt(style)
        if size_pt is not None:
            parts.append(display_font_size_with_name(size_pt))
        if style.bold:
            parts.append("加粗")
        if style.italic:
            parts.append("斜体")
        alignment_labels = {
            "left": "左对齐",
            "center": "居中",
            "right": "右对齐",
            "justify": "两端对齐",
        }
        if style.alignment and style.alignment in alignment_labels:
            parts.append(alignment_labels[style.alignment])
        return " / ".join(parts) if parts else "未设置"

    def set_max_levels(self, value: int) -> None:
        value = max(1, min(value, 8))
        self.template.heading_model.max_heading_levels = value
        self._ensure_bindings_exist(value)
        self.numbering_changed.emit()

    def _ensure_bindings_exist(self, max_levels: int) -> None:
        from src.config.template import HeadingLevelBindingConfig as BindingConfig

        bindings = self.template.heading_numbering.level_bindings
        for level in range(1, max_levels + 1):
            key = f"heading{level}"
            if key not in bindings:
                preset_binding = self._scheme_binding_for_level(level)
                bindings[key] = deepcopy(preset_binding) if preset_binding is not None else BindingConfig(
                    enabled=True,
                    display_core_style="arabic",
                    reference_core_style="arabic",
                    chain=default_chain_value(level),
                    chain_separator=".",
                )

    def _scheme_binding_for_level(self, level: int):
        from src.config.heading_presets import get_scheme_catalog

        preset_key = self._last_applied_preset_key or self.detect_active_preset()
        if not preset_key:
            return None
        entry = get_scheme_catalog().get(preset_key)
        if not entry:
            return None
        return entry["bindings"].get(f"heading{int(level)}")

    def set_binding_field(self, level: int, field_name: str, value) -> None:
        key = f"heading{level}"
        bindings = self.template.heading_numbering.level_bindings
        if key not in bindings:
            from src.config.template import HeadingLevelBindingConfig as BindingConfig

            bindings[key] = BindingConfig()
        binding = bindings[key]
        if hasattr(binding, field_name):
            setattr(binding, field_name, value)
            self.numbering_changed.emit()

    def set_non_numbered_texts(self, texts: list[str]) -> None:
        model = self.template.heading_model
        exact, _prefixes = validate_special_title_values(
            texts,
            model.non_numbered_prefixes,
        )
        reconcile_special_title_references(
            self.template,
            kind=EXACT_RULE_KIND,
            old_values=model.non_numbered_title_texts,
            new_values=exact,
        )
        model.non_numbered_title_texts = exact
        self.numbering_changed.emit()

    def set_non_numbered_prefixes(self, prefixes: list[str]) -> None:
        model = self.template.heading_model
        _exact, normalized_prefixes = validate_special_title_values(
            model.non_numbered_title_texts,
            prefixes,
        )
        reconcile_special_title_references(
            self.template,
            kind=PREFIX_RULE_KIND,
            old_values=model.non_numbered_prefixes,
            new_values=normalized_prefixes,
        )
        model.non_numbered_prefixes = normalized_prefixes
        self.numbering_changed.emit()

    def preview_should_skip_numbering(self, title: str) -> bool:
        return (
            match_special_title(
                title,
                exact_values=self.get_non_numbered_texts(),
                prefix_values=self.get_non_numbered_prefixes(),
            )
            is not None
        )

    def preview_number(self, level: int, counter_value: int = 1) -> str:
        binding = self.get_binding(level)
        if not binding.enabled:
            return ""

        counters = [0] * 10
        for current_level in range(1, level):
            counters[current_level] = 1
        counters[level] = counter_value

        level_bindings = self.template.heading_numbering.level_bindings
        return format_heading_level_number(
            level,
            counters,
            binding,
            level_bindings,
        )

    def preview_heading_text(self, level: int, title: str, counter_value: int = 1) -> str:
        if self.preview_should_skip_numbering(title):
            return str(title or "")
        number_text = self.preview_number(level, counter_value=counter_value)
        if not number_text:
            return str(title or "")
        return f"{number_text}{title}"

    def preview_reference_number(self, level: int, counter_value: int = 1) -> str:
        binding = self.get_binding(level)
        raw_style = str(getattr(binding, "reference_core_style", "") or "arabic").strip()
        normalized = CURRENT_CORE_STYLE_ALIASES.get(raw_style, raw_style)
        chain_style = CHAIN_NUMBER_STYLE_BY_CORE.get(normalized, "arabic")
        return format_number(counter_value, chain_style)

    def preview_reference_usage(self, level: int, counter_value: int = 1) -> tuple[int, str] | None:
        for child_level in range(level + 1, self.max_levels + 1):
            child_binding = self.get_binding(child_level)
            if not child_binding.enabled:
                continue
            chain_segments = parse_heading_number_chain(child_binding.chain)
            parent_depth = sum(1 for segment in chain_segments if segment == "parent")
            if child_level - parent_depth <= level < child_level:
                preview = self.preview_number(child_level, counter_value=counter_value)
                title_separator = child_binding.title_separator or ""
                if title_separator:
                    preview = preview.removesuffix(title_separator)
                return child_level, preview
        return None

    def preview_all(self) -> list[tuple[int, str]]:
        return [(level, self.preview_number(level)) for level in range(1, self.max_levels + 1)]

    def summary_items(self) -> list[dict]:
        if not self.has_template:
            return []

        preset_key = self.detect_active_preset()
        if preset_key:
            from src.config.heading_presets import get_scheme_catalog

            preset_label = get_scheme_catalog().get(preset_key, {}).get("label", preset_key)
        else:
            preset_label = "自定义"

        items = [
            {"label": "当前预设", "value": preset_label, "span": 2},
            {"label": "最大级数", "value": f"{self.max_levels} 级", "span": 1},
        ]
        for level in range(1, min(self.max_levels + 1, 5)):
            preview = self.preview_number(level)
            binding = self.get_binding(level)
            items.append(
                {
                    "label": f"级别 {level}",
                    "value": preview if binding.enabled else "未启用",
                    "span": 1,
                }
            )
        return items

    def apply_preset(self, preset_key: str) -> None:
        from src.config.heading_presets import get_preset_bindings, get_preset_max_levels

        preset_bindings = get_preset_bindings(preset_key)
        if preset_bindings is None:
            return

        bindings = self.template.heading_numbering.level_bindings
        for key in [key for key in bindings if key.startswith("heading")]:
            del bindings[key]
        for key, binding in preset_bindings.items():
            bindings[key] = deepcopy(binding)

        max_levels = get_preset_max_levels(preset_key)
        if max_levels is not None:
            self.template.heading_model.max_heading_levels = max(1, min(int(max_levels), 8))
        self._last_applied_preset_key = preset_key
        self.numbering_changed.emit()

    # ── Per-level override / inherit helpers ──────────────

    def has_heading_style_override(self, level: int) -> bool:
        """Return True when the level has its own ``headingN`` style."""
        return f"heading{int(level)}" in self.template.styles

    def remove_heading_style_override(self, level: int) -> bool:
        """Delete the per-level ``headingN`` style, reverting to the inheritance chain."""
        result = _remove_heading_style_override(self.template, level)
        if result:
            self.numbering_changed.emit()
        return result

    def is_level_binding_from_preset(self, level: int) -> bool:
        """Return True when the level's binding matches the currently active preset."""
        from src.config.heading_presets import get_scheme_catalog
        from src.config.template import HeadingLevelBindingConfig as BindingConfig

        preset_key = self._last_applied_preset_key or self.detect_active_preset()
        catalog = get_scheme_catalog()
        if preset_key is None or preset_key not in catalog:
            return False

        preset_bindings = catalog[preset_key]["bindings"]
        key = f"heading{level}"
        current = self.template.heading_numbering.level_bindings.get(key) or BindingConfig()
        preset = preset_bindings.get(key) or BindingConfig()
        return asdict(current) == asdict(preset)

    def reset_level_binding_to_preset(self, level: int) -> bool:
        """Reset this level's binding to the last-applied preset value."""
        from src.config.heading_presets import get_scheme_catalog

        preset_key = self._last_applied_preset_key or self.detect_active_preset()
        catalog = get_scheme_catalog()
        if preset_key is None or preset_key not in catalog:
            return False

        preset_bindings = catalog[preset_key]["bindings"]
        key = f"heading{level}"
        if key in preset_bindings:
            self.template.heading_numbering.level_bindings[key] = deepcopy(preset_bindings[key])
        else:
            self.template.heading_numbering.level_bindings.pop(key, None)
        self.numbering_changed.emit()
        return True

    def numbering_source_text(self, level: int) -> str:
        """Human-readable description of the numbering source for this level."""
        from src.config.heading_presets import get_scheme_catalog

        preset_key = self._last_applied_preset_key or self.detect_active_preset()
        catalog = get_scheme_catalog()
        if preset_key and preset_key in catalog and self.is_level_binding_from_preset(level):
            entry = catalog[preset_key]
            label = entry.get("label", preset_key)
            source = "用户预设方案" if entry.get("source") == "user" else "内置预设方案"
            return f"来源：{source} {label}"
        return "来源：本级自定义"

    def active_scheme_source(self) -> str:
        from src.config.heading_presets import get_preset_source

        preset_key = self.active_scheme_key()
        return get_preset_source(preset_key) if preset_key else ""

    def active_scheme_key(self) -> str | None:
        return self._last_applied_preset_key or self.detect_active_preset()

    def scheme_matches_current(self, preset_key: str | None) -> bool:
        if not preset_key:
            return False
        from src.config.heading_presets import get_scheme_catalog

        entry = get_scheme_catalog().get(preset_key)
        if not entry:
            return False
        if int(entry.get("max_levels") or self.max_levels) != self.max_levels:
            return False
        return self._bindings_match(
            self.template.heading_numbering.level_bindings,
            entry["bindings"],
        )

    def active_scheme_has_changes(self) -> bool:
        preset_key = self.active_scheme_key()
        if not preset_key:
            return False
        return not self.scheme_matches_current(preset_key)

    def active_scheme_label(self) -> str:
        from src.config.heading_presets import get_scheme_catalog

        preset_key = self.active_scheme_key()
        if not preset_key:
            return "当前模板自定义"
        entry = get_scheme_catalog().get(preset_key)
        if not entry:
            return "当前模板自定义"
        suffix = "用户" if entry.get("source") == "user" else "内置"
        label = entry.get("label", preset_key)
        if self.scheme_matches_current(preset_key):
            return f"{label}（{suffix}）"
        return f"{label}（{suffix}，已修改）"

    def save_current_as_user_scheme(self, label: str) -> str:
        from src.config.heading_presets import save_user_preset

        scheme_id = save_user_preset(
            label,
            deepcopy(self.template.heading_numbering.level_bindings),
            max_levels=self.max_levels,
        )
        self._last_applied_preset_key = scheme_id
        self.numbering_changed.emit()
        return scheme_id

    def update_active_user_scheme(self) -> bool:
        from src.config.heading_presets import is_user_preset, save_user_preset, get_scheme_catalog

        preset_key = self._last_applied_preset_key or self.detect_active_preset()
        if not preset_key or not is_user_preset(preset_key):
            return False
        if not self.active_scheme_has_changes():
            return False
        label = get_scheme_catalog().get(preset_key, {}).get("label", preset_key.replace("user.", ""))
        save_user_preset(
            str(label),
            deepcopy(self.template.heading_numbering.level_bindings),
            max_levels=self.max_levels,
            scheme_id=preset_key,
        )
        self.numbering_changed.emit()
        return True

    def delete_active_user_scheme(self) -> bool:
        from src.config.heading_presets import delete_user_preset, is_user_preset

        preset_key = self._last_applied_preset_key or self.detect_active_preset()
        if not preset_key or not is_user_preset(preset_key):
            return False
        if delete_user_preset(preset_key):
            self._last_applied_preset_key = None
            self.numbering_changed.emit()
            return True
        return False
