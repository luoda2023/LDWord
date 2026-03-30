"""
ConfigLoader ? YAML/JSON -> TemplateConfig + SceneWorkspace.

Nested dataclass materialization is delegated to config.dataclass_utils,
keeping loader focused on file I/O + normalize.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.config.dataclass_utils import dict_to_dataclass
from src.config.migration import (
    normalize_scene_payload,
    normalize_template_payload,
)


def load_template(path: str | Path) -> "TemplateConfig":
    """Load TemplateConfig from a YAML/JSON file."""
    from src.config.template import TemplateConfig

    data = _load_file(path)
    return dict_to_dataclass(TemplateConfig, normalize_template_payload(data))


def load_scene(path: str | Path) -> "SceneWorkspace":
    """Load SceneWorkspace from a YAML/JSON file."""
    from src.config.scene import SceneWorkspace

    data = _load_file(path)
    return dict_to_dataclass(SceneWorkspace, normalize_scene_payload(data))


def _load_file(path: str | Path) -> dict:
    """Load a YAML or JSON config file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {p}")

    text = p.read_text(encoding="utf-8")

    if p.suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required to load YAML config files: pip install pyyaml"
            ) from exc
        return yaml.safe_load(text) or {}

    if p.suffix == ".json":
        return json.loads(text)

    raise ValueError(
        f"Unsupported config file format: {p.suffix} (expected .yaml/.yml/.json)"
    )
