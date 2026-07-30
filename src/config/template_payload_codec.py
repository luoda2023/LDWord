"""Lossless materialization and authoring-boundary checks for TemplateConfig."""

from __future__ import annotations

from dataclasses import asdict, fields
from typing import Any, Mapping

from src.config.dataclass_utils import dict_to_dataclass
from src.config.migration import normalize_template_payload
from src.config.template import TemplateConfig
from src.config.template_authoring_layout import BASELINE_NAME_PLACEHOLDER
from src.config.template_authoring_profile import TemplateAuthoringProfile
from src.config.template_authoring_validation import (
    TemplatePayloadValidationError,
    validate_complete_template_payload,
)


_LEGACY_SCENE_HINT_KEYS = {
    "capabilities",
    "category",
    "category_label",
    "default_template_id",
    "delivery_targets",
    "feature_settings",
    "features",
    "master_ref",
    "mode_id",
    "module_switches",
    "pipeline",
    "pipeline_critical_rules",
    "pipeline_strict_mode",
    "scene_id",
    "template_id",
    "template_overrides",
    "template_ref",
}


class TemplatePayloadCodecError(ValueError):
    """A payload cannot be represented losslessly as TemplateConfig."""


def materialize_template_payload(
    raw: Mapping[str, Any],
    *,
    profile: TemplateAuthoringProfile | None = None,
    baseline_template: Mapping[str, Any] | None = None,
) -> TemplateConfig:
    canonical_keys = {field.name for field in fields(TemplateConfig)}
    raw_keys = {str(key) for key in raw}
    scene_keys = sorted(raw_keys & _LEGACY_SCENE_HINT_KEYS)
    if scene_keys:
        raise TemplatePayloadCodecError(
            "检测到旧版“模板 + 方案”混合 JSON，自动导入会丢失方案行为字段"
            f"（{'、'.join(scene_keys[:8])}）。请使用本工作区的新提示词与基准配置重新生成"
        )
    unknown_keys = sorted(raw_keys - canonical_keys)
    if unknown_keys:
        raise TemplatePayloadCodecError(
            "存在当前模板结构不支持的顶层字段："
            f"{'、'.join(unknown_keys[:12])}。为避免静默丢失，已停止导入"
        )
    missing_keys = sorted(canonical_keys - raw_keys)
    if missing_keys:
        raise TemplatePayloadCodecError(
            "模板 JSON 不完整，缺少顶层字段："
            f"{'、'.join(missing_keys[:12])}。请让 AI 完整复制基准配置"
        )
    try:
        validate_complete_template_payload(raw)
    except TemplatePayloadValidationError as exc:
        raise TemplatePayloadCodecError(str(exc)) from exc

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise TemplatePayloadCodecError("模板 name 必须是非空文本")
    if name.strip() == BASELINE_NAME_PLACEHOLDER:
        raise TemplatePayloadCodecError(
            "AI 尚未把基准名称替换为来源文档对应的具体模板名称"
        )

    normalized = normalize_template_payload(raw)
    template = dict_to_dataclass(TemplateConfig, normalized)
    canonical_payload = asdict(template)
    changed_paths = _find_changed_or_unmodeled_paths(
        raw,
        canonical_payload,
        compare_values=False,
    )
    changed_paths.extend(
        _find_changed_or_unmodeled_paths(
            normalized,
            canonical_payload,
            compare_values=True,
        )
    )
    if changed_paths:
        raise TemplatePayloadCodecError(
            "以下字段无法被当前版本原样保存："
            f"{'、'.join(changed_paths[:12])}。为避免静默修改或丢失，已停止导入"
        )
    if profile is not None and baseline_template is not None:
        changed_roots = {
            root
            for root in canonical_keys - {"name", "description"}
            if raw.get(root) != baseline_template.get(root)
        }
        disallowed = sorted(changed_roots - set(profile.authorable_roots))
        if disallowed:
            raise TemplatePayloadCodecError(
                "创作结果修改了不可写模板根：" + "、".join(disallowed)
            )
    return template


def validate_authored_template_boundary(
    result_template: Mapping[str, Any],
    *,
    baseline_template: Mapping[str, Any],
    profile: TemplateAuthoringProfile,
) -> None:
    changed_frozen = [
        root
        for root in profile.frozen_roots
        if result_template.get(root) != baseline_template.get(root)
    ]
    if changed_frozen:
        raise TemplatePayloadCodecError(
            "以下字段属于方案或输出层，必须保持基准值："
            + "、".join(changed_frozen)
        )
    missing_paths = _find_missing_structure_paths(baseline_template, result_template)
    if missing_paths:
        raise TemplatePayloadCodecError(
            "创作结果删除了基准结构：" + "、".join(missing_paths[:12])
        )
    styles = result_template.get("styles")
    missing_roles = (
        sorted(set(profile.required_style_roles) - set(styles))
        if isinstance(styles, Mapping)
        else list(profile.required_style_roles)
    )
    if missing_roles:
        raise TemplatePayloadCodecError(
            "创作结果缺少当前模式必需的样式角色：" + "、".join(missing_roles)
        )


def _find_changed_or_unmodeled_paths(
    source: Any,
    materialized: Any,
    *,
    prefix: str = "",
    compare_values: bool,
) -> list[str]:
    changed: list[str] = []
    if isinstance(source, Mapping):
        if not isinstance(materialized, Mapping):
            return [prefix or "<root>"]
        for key, value in source.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in materialized:
                changed.append(path)
                continue
            changed.extend(
                _find_changed_or_unmodeled_paths(
                    value,
                    materialized[key],
                    prefix=path,
                    compare_values=compare_values,
                )
            )
    elif isinstance(source, list):
        if not isinstance(materialized, list):
            return [prefix or "<root>"]
        for index, value in enumerate(source):
            path = f"{prefix}[{index}]"
            if index >= len(materialized):
                changed.append(path)
                continue
            changed.extend(
                _find_changed_or_unmodeled_paths(
                    value,
                    materialized[index],
                    prefix=path,
                    compare_values=compare_values,
                )
            )
    elif compare_values and source != materialized:
        changed.append(prefix or "<root>")
    return changed


def _find_missing_structure_paths(
    baseline: Any,
    result: Any,
    *,
    prefix: str = "",
) -> list[str]:
    missing: list[str] = []
    if isinstance(baseline, Mapping):
        if not isinstance(result, Mapping):
            return [prefix or "<root>"]
        for key, baseline_value in baseline.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in result:
                missing.append(path)
                continue
            missing.extend(
                _find_missing_structure_paths(
                    baseline_value,
                    result[key],
                    prefix=path,
                )
            )
    elif isinstance(baseline, list):
        if not isinstance(result, list):
            return [prefix or "<root>"]
        if len(result) < len(baseline):
            missing.extend(
                f"{prefix}[{index}]"
                for index in range(len(result), len(baseline))
            )
        for index, baseline_value in enumerate(baseline[: len(result)]):
            missing.extend(
                _find_missing_structure_paths(
                    baseline_value,
                    result[index],
                    prefix=f"{prefix}[{index}]",
                )
            )
    return missing


__all__ = [
    "TemplatePayloadCodecError",
    "materialize_template_payload",
    "validate_authored_template_boundary",
]
