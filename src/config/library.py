"""Unified scene/template config library helpers.

This module gives V1.0 a real dual-file configuration source:
- ``templates/`` for template configs
- ``scenes/`` for scene configs

Built-in factories remain the seed source, but runtime panels load from the
library directories so scene/template selection can be path-aware.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.builtin_templates import create_builtin_template
from src.config.loader import load_scene, load_template, save_scene, save_template


DEFAULT_TEMPLATE_ID = "default"
DEFAULT_SCENE_ID = "custom"
TEMPLATE_LIBRARY_SEED_IDS: tuple[str, ...] = ("default", "thesis_gbt")
OBSOLETE_TEMPLATE_LIBRARY_IDS: tuple[str, ...] = (
    "bid_custom",
    "bid_engineering",
    "bid_procurement",
    "official_custom",
    "official_gbt",
    "report_custom",
    "report_default",
    "tech_custom",
    "tech_standard",
    "thesis_custom",
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_LIBRARY_DIR = _PROJECT_ROOT / "templates"
SCENE_LIBRARY_DIR = _PROJECT_ROOT / "scenes"
_CONFIG_SUFFIXES: tuple[str, ...] = (".json", ".yaml", ".yml")
_BUILTIN_SCENE_DISPLAY_NAMES: dict[str, str] = {
    "custom": "通用-默认",
    "exam": "试卷-默认",
    "thesis": "论文-默认",
    "bidding": "标书-默认",
    "official": "公文-默认",
    "technical": "技术文档-默认",
    "report": "通用报告-默认",
}


@dataclass(frozen=True, slots=True)
class ConfigLibraryEntry:
    kind: str
    config_id: str
    name: str
    path: Path


@dataclass(frozen=True, slots=True)
class SceneLibraryDescriptor:
    config_id: str
    scene_id: str
    name: str
    description: str
    default_template_id: str
    compatible_template_ids: tuple[str, ...]
    path: Path
    load_error: str = ""

    @property
    def is_available(self) -> bool:
        return not self.load_error

    @property
    def display_name(self) -> str:
        return self.name if self.is_available else f"{self.name} (Unavailable)"


def ensure_config_library() -> None:
    _seed_template_library()
    _prune_obsolete_template_library_entries()
    _seed_scene_library()


def list_template_entries() -> list[ConfigLibraryEntry]:
    ensure_config_library()
    return _list_entries("template", TEMPLATE_LIBRARY_DIR, load_template)


def list_scene_entries() -> list[ConfigLibraryEntry]:
    ensure_config_library()
    return _list_entries("scene", SCENE_LIBRARY_DIR, load_scene)


def list_scene_descriptors() -> list[SceneLibraryDescriptor]:
    ensure_config_library()
    builtin_order = _builtin_scene_order()
    descriptors: list[SceneLibraryDescriptor] = []
    for path in _iter_config_files(SCENE_LIBRARY_DIR):
        descriptor = _build_scene_descriptor_from_path(path)
        if descriptor is not None:
            descriptors.append(descriptor)
    descriptors.sort(
        key=lambda item: (
            1 if item.config_id in builtin_order else 0,
            builtin_order.get(item.config_id, len(builtin_order)),
            item.name,
            item.config_id,
        )
    )
    return descriptors


def get_template_entry(template_id: str) -> ConfigLibraryEntry | None:
    ensure_config_library()
    return _get_entry("template", TEMPLATE_LIBRARY_DIR, template_id, load_template)


def get_scene_entry(scene_id: str) -> ConfigLibraryEntry | None:
    ensure_config_library()
    return _get_entry("scene", SCENE_LIBRARY_DIR, scene_id, load_scene)


def get_scene_descriptor(scene_id: str) -> SceneLibraryDescriptor | None:
    path = _find_config_path(SCENE_LIBRARY_DIR, scene_id)
    if path is None:
        return None
    return _build_scene_descriptor_from_path(path)


def load_template_from_library(template_id: str):
    entry = get_template_entry(template_id)
    if entry is not None:
        return load_template(entry.path)
    return create_builtin_template(template_id)


def load_scene_from_library(scene_id: str):
    path = _find_config_path(SCENE_LIBRARY_DIR, scene_id)
    if path is not None:
        entry = ConfigLibraryEntry("scene", path.stem, path.stem, path)
        return _load_scene_entry(entry)
    return _create_builtin_scene(scene_id)


def default_template_entry() -> ConfigLibraryEntry | None:
    entry = get_template_entry(DEFAULT_TEMPLATE_ID)
    if entry is not None:
        return entry
    entries = list_template_entries()
    return entries[0] if entries else None


def default_scene_entry() -> ConfigLibraryEntry | None:
    entry = get_scene_entry(DEFAULT_SCENE_ID)
    if entry is not None:
        return entry
    entries = list_scene_entries()
    return entries[0] if entries else None


def default_scene_descriptor() -> SceneLibraryDescriptor | None:
    descriptor = get_scene_descriptor(DEFAULT_SCENE_ID)
    if descriptor is not None and descriptor.is_available:
        return descriptor
    descriptors = list_scene_descriptors()
    return next((item for item in descriptors if item.is_available), None)


def is_template_library_path(path: str | Path) -> bool:
    return _is_under_directory(path, TEMPLATE_LIBRARY_DIR)


def is_scene_library_path(path: str | Path) -> bool:
    return _is_under_directory(path, SCENE_LIBRARY_DIR)


def save_template_to_library(template, template_id: str | None = None) -> ConfigLibraryEntry:
    ensure_config_library()
    entry_id = str(template_id or "").strip() or _safe_config_id(getattr(template, "name", "") or "template")
    target = TEMPLATE_LIBRARY_DIR / f"{entry_id}.json"
    save_template(template, target)
    reloaded = load_template(target)
    return ConfigLibraryEntry("template", entry_id, str(getattr(reloaded, "name", "") or entry_id), target)


def save_scene_to_library(scene, scene_id: str | None = None) -> ConfigLibraryEntry:
    ensure_config_library()
    entry_id = str(scene_id or "").strip() or _safe_config_id(getattr(scene, "name", "") or "scene")
    _set_scene_identity(scene, entry_id)
    _normalize_scene_templates(scene)
    target = SCENE_LIBRARY_DIR / f"{entry_id}.json"
    save_scene(scene, target)
    reloaded = _load_scene_entry(ConfigLibraryEntry("scene", entry_id, entry_id, target))
    return ConfigLibraryEntry("scene", entry_id, str(getattr(reloaded, "name", "") or entry_id), target)


def _seed_template_library() -> None:
    TEMPLATE_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    for template_id in TEMPLATE_LIBRARY_SEED_IDS:
        target = TEMPLATE_LIBRARY_DIR / f"{template_id}.json"
        if target.exists():
            continue
        save_template(create_builtin_template(template_id), target)


def _prune_obsolete_template_library_entries() -> None:
    for template_id in OBSOLETE_TEMPLATE_LIBRARY_IDS:
        for suffix in _CONFIG_SUFFIXES:
            target = TEMPLATE_LIBRARY_DIR / f"{template_id}{suffix}"
            if target.exists() and target.is_file():
                try:
                    target.unlink()
                except OSError:
                    continue


def _seed_scene_library() -> None:
    SCENE_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    from src.config.scene_presets import SCENE_METAS

    for meta in SCENE_METAS:
        target = SCENE_LIBRARY_DIR / f"{meta.scene_id}.json"
        if target.exists():
            continue
        save_scene(_create_builtin_scene(meta.scene_id), target)


def _create_builtin_scene(scene_id: str):
    from src.config.scene_presets import create_scene

    scene = create_scene(scene_id)
    _normalize_scene_templates(scene)
    return scene


def _load_scene_entry(entry: ConfigLibraryEntry):
    scene = load_scene(entry.path)
    _set_scene_identity(scene, entry.config_id)
    _normalize_scene_templates(scene)
    return scene


def _set_scene_identity(scene, scene_id: str) -> None:
    normalized_id = str(scene_id or "").strip()
    if not normalized_id:
        return
    current_id = str(getattr(scene, "scene_id", "") or "").strip()
    if current_id == normalized_id:
        return
    try:
        scene.scene_id = normalized_id
    except Exception:
        pass


def _normalize_scene_templates(scene) -> None:
    candidate_ids = [
        str(getattr(scene, "template_id", "") or "").strip(),
        str(getattr(scene, "default_template_id", "") or "").strip(),
        *[
            str(template_id or "").strip()
            for template_id in getattr(scene, "compatible_template_ids", []) or []
        ],
    ]
    compatible_ids = _available_scene_template_ids(
        candidate_ids,
        scene_id=str(getattr(scene, "scene_id", "") or "").strip(),
        category=str(getattr(scene, "category", "") or "").strip(),
    )
    if not compatible_ids:
        compatible_ids = [DEFAULT_TEMPLATE_ID]
    try:
        scene.compatible_template_ids = compatible_ids
    except Exception:
        pass

    current_template_id = str(getattr(scene, "template_id", "") or "").strip()
    if not _template_id_is_available(current_template_id):
        try:
            scene.template_id = compatible_ids[0]
        except Exception:
            pass

    default_template_id = str(getattr(scene, "default_template_id", "") or "").strip()
    if not _template_id_is_available(default_template_id):
        try:
            scene.default_template_id = compatible_ids[0]
        except Exception:
            pass


def _available_scene_template_ids(
    template_ids,
    *,
    scene_id: str = "",
    category: str = "",
) -> list[str]:
    filtered: list[str] = []
    raw_ids = [str(template_id or "").strip() for template_id in template_ids]
    for template_id in raw_ids:
        if not _template_id_is_available(template_id):
            continue
        if template_id not in filtered:
            filtered.append(template_id)
    if filtered:
        return filtered
    fallback_id = (
        "thesis_gbt"
        if (
            "thesis_gbt" in raw_ids
            or str(scene_id or "").strip() == "thesis"
            or str(category or "").strip() == "academic"
        )
        else DEFAULT_TEMPLATE_ID
    )
    return [fallback_id if _template_id_is_available(fallback_id) else DEFAULT_TEMPLATE_ID]


def _template_id_is_available(template_id: str) -> bool:
    normalized = str(template_id or "").strip()
    if not normalized or normalized in OBSOLETE_TEMPLATE_LIBRARY_IDS:
        return False
    if normalized in TEMPLATE_LIBRARY_SEED_IDS:
        return True
    for suffix in _CONFIG_SUFFIXES:
        path = TEMPLATE_LIBRARY_DIR / f"{normalized}{suffix}"
        if path.exists() and path.is_file():
            return True
    return False


def _build_scene_descriptor(entry: ConfigLibraryEntry) -> SceneLibraryDescriptor | None:
    return _build_scene_descriptor_from_path(entry.path)


def _build_scene_descriptor_from_path(path: Path) -> SceneLibraryDescriptor | None:
    config_id = path.stem
    fallback_meta = _builtin_scene_meta_map().get(config_id)
    try:
        scene = _load_scene_entry(ConfigLibraryEntry("scene", config_id, config_id, path))
    except Exception as exc:
        fallback_name = (fallback_meta.name if fallback_meta is not None else config_id) or config_id
        fallback_name = _builtin_scene_display_name(config_id, fallback_name)
        fallback_description = str(
            fallback_meta.description if fallback_meta is not None else ""
        ).strip()
        fallback_template_id = str(
            fallback_meta.default_template_id if fallback_meta is not None else ""
        ).strip()
        compatible_template_ids: tuple[str, ...] = ()
        if fallback_meta is not None:
            compatible_template_ids = tuple(
                _available_scene_template_ids(
                    (
                        fallback_template_id,
                        *(meta.template_id for meta in fallback_meta.compatible_templates),
                    ),
                    scene_id=config_id,
                )
            )
        if not _template_id_is_available(fallback_template_id):
            fallback_template_id = (
                compatible_template_ids[0]
                if compatible_template_ids
                else DEFAULT_TEMPLATE_ID
            )
        return SceneLibraryDescriptor(
            config_id=config_id,
            scene_id=config_id,
            name=fallback_name,
            description=fallback_description,
            default_template_id=fallback_template_id,
            compatible_template_ids=compatible_template_ids,
            path=path,
            load_error=f"{type(exc).__name__}: {exc}",
        )

    scene_id = str(getattr(scene, "scene_id", "") or config_id).strip() or config_id
    name = str(
        getattr(scene, "name", "") or (fallback_meta.name if fallback_meta is not None else "") or config_id
    ).strip() or config_id
    name = _builtin_scene_display_name(config_id, name)
    description = str(
        getattr(scene, "description", "") or (fallback_meta.description if fallback_meta is not None else "")
    ).strip()
    default_template_id = str(
        getattr(scene, "default_template_id", "")
        or getattr(scene, "template_id", "")
        or (fallback_meta.default_template_id if fallback_meta is not None else "")
    ).strip()

    compatible_template_ids = tuple(
        item
        for item in (
            str(template_id or "").strip()
            for template_id in getattr(scene, "compatible_template_ids", [])
        )
        if item
    )
    if not compatible_template_ids and fallback_meta is not None:
        compatible_template_ids = tuple(meta.template_id for meta in fallback_meta.compatible_templates)
    if not compatible_template_ids and default_template_id:
        compatible_template_ids = (default_template_id,)

    return SceneLibraryDescriptor(
        config_id=config_id,
        scene_id=scene_id,
        name=name,
        description=description,
        default_template_id=default_template_id,
        compatible_template_ids=compatible_template_ids,
        path=path,
    )


def _list_entries(kind: str, directory: Path, loader) -> list[ConfigLibraryEntry]:
    entries: list[ConfigLibraryEntry] = []
    for path in _iter_config_files(directory):
        config_id = path.stem
        if kind == "template" and config_id in OBSOLETE_TEMPLATE_LIBRARY_IDS:
            continue
        try:
            cfg = loader(path)
        except Exception:
            continue
        name = str(getattr(cfg, "name", "") or config_id).strip() or config_id
        entries.append(ConfigLibraryEntry(kind, config_id, name, path))
    entries.sort(key=lambda item: (item.name, item.config_id))
    return entries


def _get_entry(kind: str, directory: Path, config_id: str, loader) -> ConfigLibraryEntry | None:
    target_id = str(config_id or "").strip()
    if not target_id:
        return None
    for suffix in _CONFIG_SUFFIXES:
        path = directory / f"{target_id}{suffix}"
        if not path.exists():
            continue
        if kind == "template" and target_id in OBSOLETE_TEMPLATE_LIBRARY_IDS:
            continue
        try:
            cfg = loader(path)
        except Exception:
            continue
        name = str(getattr(cfg, "name", "") or target_id).strip() or target_id
        return ConfigLibraryEntry(kind, target_id, name, path)
    return None


def _find_config_path(directory: Path, config_id: str) -> Path | None:
    target_id = str(config_id or "").strip()
    if not target_id:
        return None
    for suffix in _CONFIG_SUFFIXES:
        path = directory / f"{target_id}{suffix}"
        if path.exists():
            return path
    return None


def _iter_config_files(directory: Path):
    if not directory.exists():
        return []
    files: list[Path] = []
    for suffix in _CONFIG_SUFFIXES:
        files.extend(sorted(directory.glob(f"*{suffix}")))
    seen: set[Path] = set()
    unique_files: list[Path] = []
    for path in files:
        if path in seen:
            continue
        seen.add(path)
        unique_files.append(path)
    return unique_files


def _is_under_directory(path: str | Path, directory: Path) -> bool:
    candidate = Path(path)
    try:
        candidate_resolved = candidate.resolve()
        directory_resolved = directory.resolve()
    except Exception:
        return False
    return directory_resolved == candidate_resolved or directory_resolved in candidate_resolved.parents


def _safe_config_id(value: str) -> str:
    forbidden = '<>:"/\\|?*'
    cleaned = "".join(ch if ch not in forbidden else "_" for ch in str(value or "").strip())
    cleaned = cleaned.strip(" ._")
    return cleaned or "config"


def _builtin_scene_order() -> dict[str, int]:
    from src.config.scene_presets import SCENE_METAS

    return {meta.scene_id: index for index, meta in enumerate(SCENE_METAS)}


def _builtin_scene_display_name(scene_id: str, fallback: str) -> str:
    normalized = str(scene_id or "").strip()
    return _BUILTIN_SCENE_DISPLAY_NAMES.get(normalized, fallback)


def _builtin_scene_meta_map():
    from src.config.scene_presets import SCENE_META_MAP

    return SCENE_META_MAP


__all__ = [
    "ConfigLibraryEntry",
    "DEFAULT_SCENE_ID",
    "DEFAULT_TEMPLATE_ID",
    "OBSOLETE_TEMPLATE_LIBRARY_IDS",
    "SCENE_LIBRARY_DIR",
    "TEMPLATE_LIBRARY_SEED_IDS",
    "SceneLibraryDescriptor",
    "TEMPLATE_LIBRARY_DIR",
    "default_scene_descriptor",
    "default_scene_entry",
    "default_template_entry",
    "ensure_config_library",
    "get_scene_descriptor",
    "get_scene_entry",
    "get_template_entry",
    "is_scene_library_path",
    "is_template_library_path",
    "list_scene_descriptors",
    "list_scene_entries",
    "list_template_entries",
    "load_scene_from_library",
    "load_template_from_library",
    "save_scene_to_library",
    "save_template_to_library",
]
