"""
ConfigLoader — canonical YAML/JSON -> TemplateConfig + SceneWorkspace.

Nested dataclass materialization is delegated to config.dataclass_utils,
keeping loader focused on file I/O and strict current-schema enforcement.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from src.config.dataclass_utils import dict_to_dataclass
from src.config.execution_config_integrity import delivery_preset_identity_issue
from src.config.strict_payload_validation import (
    StrictPayloadValidationError,
    validate_complete_dataclass_payload,
)
from src.config.atomic_io import atomic_write_text

if TYPE_CHECKING:
    from src.config.scene import SceneWorkspace
    from src.config.template import TemplateConfig


class ConfigLoadError(ValueError):
    """External configuration bytes or payload structure cannot be loaded."""


def load_template(path: str | Path) -> "TemplateConfig":
    """Load a complete current-version ``TemplateConfig`` payload."""
    from src.config.template import TemplateConfig

    data = _load_file(path)
    return _materialize_canonical_payload(
        TemplateConfig,
        data,
        path=Path(path),
        root_label="模板根对象",
    )


def load_scene(path: str | Path) -> "SceneWorkspace":
    """Load a complete current-version ``SceneWorkspace`` payload."""
    from src.config.scene import SceneWorkspace

    data = _load_file(path)
    materialized = _materialize_canonical_payload(
        SceneWorkspace,
        data,
        path=Path(path),
        root_label="方案根对象",
    )
    delivery_issue = delivery_preset_identity_issue(materialized)
    if delivery_issue:
        raise ConfigLoadError(
            f"Invalid canonical config payload: {Path(path)}: {delivery_issue}"
        )
    return materialized


def save_scene(scene: "SceneWorkspace", path: str | Path) -> Path:
    """Save SceneWorkspace to a YAML or JSON file."""
    target = Path(path)
    suffix = target.suffix.lower()
    data = asdict(scene)

    if suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required to save YAML config files: pip install pyyaml"
            ) from exc
        payload = yaml.safe_dump(
            data,
            allow_unicode=True,
            sort_keys=False,
        )
    elif suffix == ".json":
        payload = json.dumps(data, ensure_ascii=False, indent=2)
    else:
        raise ValueError(
            f"Unsupported config file format: {target.suffix} (expected .yaml/.yml/.json)"
        )

    return atomic_write_text(target, payload, encoding="utf-8")


def save_template(template: "TemplateConfig", path: str | Path) -> Path:
    """Save TemplateConfig to a YAML or JSON file."""
    target = Path(path)
    suffix = target.suffix.lower()
    data = asdict(template)

    if suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required to save YAML config files: pip install pyyaml"
            ) from exc
        payload = yaml.safe_dump(
            data,
            allow_unicode=True,
            sort_keys=False,
        )
    elif suffix == ".json":
        payload = json.dumps(data, ensure_ascii=False, indent=2)
    else:
        raise ValueError(
            f"Unsupported config file format: {target.suffix} (expected .yaml/.yml/.json)"
        )

    return atomic_write_text(target, payload, encoding="utf-8")


def _load_file(path: str | Path) -> dict:
    """Load a YAML or JSON config file."""
    p = Path(path)
    if not p.exists():
        raise ConfigLoadError(f"Config file not found: {p}")

    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ConfigLoadError(f"Config file is unreadable: {p}") from exc

    suffix = p.suffix.casefold()
    if suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required to load YAML config files: pip install pyyaml"
            ) from exc
        try:
            payload = yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:
            raise ConfigLoadError(f"Invalid YAML config: {p}") from exc
        return _require_mapping_payload(payload, p)

    if suffix == ".json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigLoadError(f"Invalid JSON config: {p}") from exc
        return _require_mapping_payload(payload, p)

    raise ConfigLoadError(
        f"Unsupported config file format: {p.suffix} (expected .yaml/.yml/.json)"
    )


def _require_mapping_payload(payload: object, path: Path) -> dict:
    if not isinstance(payload, Mapping):
        raise ConfigLoadError(f"Config root must be an object: {path}")
    return dict(payload)


def _materialize_canonical_payload(
    dataclass_type: type,
    data: dict,
    *,
    path: Path,
    root_label: str,
):
    """Materialize without migration, default repair, or field loss."""

    try:
        validate_complete_dataclass_payload(
            dataclass_type,
            data,
            root_label=root_label,
        )
    except StrictPayloadValidationError as exc:
        raise ConfigLoadError(f"Invalid canonical config payload: {path}: {exc}") from exc

    try:
        materialized = dict_to_dataclass(dataclass_type, data)
    except (TypeError, ValueError) as exc:
        raise ConfigLoadError(f"Invalid canonical config payload: {path}") from exc

    canonical = asdict(materialized)
    difference = _first_payload_difference(data, canonical)
    if difference:
        raise ConfigLoadError(
            "Canonical config changes during materialization: "
            f"{path}: field `{difference}`. Regenerate the resource explicitly."
        )
    return materialized


def _first_payload_difference(source: object, canonical: object, path: str = "") -> str:
    if isinstance(source, Mapping) and isinstance(canonical, Mapping):
        source_keys = set(source)
        canonical_keys = set(canonical)
        for key in sorted(source_keys | canonical_keys, key=str):
            field_path = f"{path}.{key}" if path else str(key)
            if key not in source or key not in canonical:
                return field_path
            difference = _first_payload_difference(
                source[key],
                canonical[key],
                field_path,
            )
            if difference:
                return difference
        return ""
    if isinstance(source, list) and isinstance(canonical, list):
        if len(source) != len(canonical):
            return path or "<root>"
        for index, (source_item, canonical_item) in enumerate(zip(source, canonical)):
            item_path = f"{path}[{index}]"
            difference = _first_payload_difference(
                source_item,
                canonical_item,
                item_path,
            )
            if difference:
                return difference
        return ""
    return "" if source == canonical else (path or "<root>")
