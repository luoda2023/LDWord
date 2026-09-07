"""Per-scene mapping of material-package fields onto cover roles.

The export cover is produced from two editable roles: the **cover title**
(封面标题) and the **cover subtitle** (封面副标题).  Historically the
recognition was hard-coded: the title came from the document's first level-1
heading, and the subtitle was filled from whatever material field happened to
match a fixed set of alias keys (``project_name`` / ``项目名称`` ... for the
project, ``company_name`` / ``公司名称`` ... for the company).

This module makes that mapping *configurable and per-scene*.  For every scene a
user can say which material field should feed the cover title and which should
feed the cover subtitle.  The resolution is:

* **cover_title**  <- one of: a named material field, ``document_first_h1``
  (today's default), or ``none`` (leave empty for the user to type).
* **cover_subtitle** <- one of: a named material field, ``document_context``
  (today's default fallback), or ``none``.

A *scene* is identified by ``scene_id``.  The mapping is persisted through the
same ``QSettings`` store the cover-date preference uses, so choices survive
restarts and each document scene keeps its own mapping.  When no override is
saved for the active scene the *default* mapping (which reproduces today's
behavior exactly) is used.
"""

from __future__ import annotations

from collections.abc import Mapping

# --------------------------------------------------------------------------
# Settings plumbing (mirrors the cover-date format helpers in assistant_panel)
# --------------------------------------------------------------------------

_QSETTINGS_ORG = "LDWord"
_QSETTINGS_APP = "LDWord"
_COVER_MAP_PREFIX = "export/cover_field_map/"

# Special "source" ids accepted for a cover role.  These are not material
# fields; they name the fallback the dialog already implements today.
SRC_DOCUMENT_FIRST_H1 = "document_first_h1"
SRC_DOCUMENT_CONTEXT = "document_context"
SRC_NONE = "none"

# Material-role sources the user may map a cover role onto.  ``project``
# resolves through :data:`PROJECT_FIELD_KEYS`, ``company`` through
# :data:`COMPANY_FIELD_KEYS`.
SRC_PROJECT = "project"
SRC_COMPANY = "company"

# Choices offered for the cover *title* role.
TITLE_SOURCE_OPTIONS = (
    (SRC_DOCUMENT_FIRST_H1, "文档一级标题（默认）"),
    (SRC_PROJECT, "项目/工程名"),
    (SRC_COMPANY, "单位/公司名"),
    (SRC_NONE, "留空（手动填写）"),
)

# Choices offered for the cover *subtitle* role.
SUBTITLE_SOURCE_OPTIONS = (
    (SRC_DOCUMENT_CONTEXT, "文档类型/项目上下文（默认）"),
    (SRC_PROJECT, "项目/工程名"),
    (SRC_COMPANY, "单位/公司名"),
    (SRC_NONE, "留空（手动填写）"),
)

_ALL_SOURCES = frozenset(
    [
        SRC_DOCUMENT_FIRST_H1,
        SRC_DOCUMENT_CONTEXT,
        SRC_PROJECT,
        SRC_COMPANY,
        SRC_NONE,
    ]
)

_DEFAULT_SOURCES = (
    # scene-less default: reproduce today's behavior exactly.
    (SRC_DOCUMENT_FIRST_H1, SRC_DOCUMENT_CONTEXT),
)


def save_role_source(scene_key: str, role: str, source: str) -> None:
    """Persist which source feeds a cover role for a given scene.

    ``role`` is ``"cover_title"`` or ``"cover_subtitle"``; ``source`` must be
    one of :data:`_ALL_SOURCES`.  ``SRC_NONE`` clears the override so the
    built-in default applies again.
    """
    candidate = str(source or "").strip()
    if candidate == SRC_NONE or candidate not in _ALL_SOURCES:
        if candidate in _ALL_SOURCES:
            # "none" is an explicit choice meaning "do not auto-fill this role";
            # store it so the prefill leaves the field empty for the user.
            candidate = SRC_NONE
        else:
            # Unknown value: clear the override so the default applies again.
            _clear_role(scene_key, role)
            return
    try:
        from src.qt_api import QSettings

        settings = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)
        settings.setValue(f"{_COVER_MAP_PREFIX}{role}/{scene_key}", candidate)
        settings.sync()
    except Exception:  # noqa: BLE001 - preference persistence must never crash
        pass


def _clear_role(scene_key: str, role: str) -> None:
    try:
        from src.qt_api import QSettings

        settings = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)
        settings.remove(f"{_COVER_MAP_PREFIX}{role}/{scene_key}")
    except Exception:  # noqa: BLE001 - best-effort cleanup
        pass


def _load_role_source(scene_key: str, role: str) -> str:
    """Return the saved source for a cover role of a scene, else ``""``."""
    try:
        from src.qt_api import QSettings

        settings = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)
        value = str(
            settings.value(f"{_COVER_MAP_PREFIX}{role}/{scene_key}", "") or ""
        ).strip()
        if value in _ALL_SOURCES:
            return value
    except Exception:  # noqa: BLE001 - never block on settings errors
        pass
    return ""


def clear_scene_mapping(scene_key: str) -> None:
    """Remove every saved override for a scene (restore the built-in default)."""
    for role in ("cover_title", "cover_subtitle"):
        _clear_role(scene_key, role)


def scene_key_for(mode_id: str, scene_id: str) -> str:
    """Build a stable settings key identifying the current document scene."""
    mode = str(mode_id or "").strip()
    scene = str(scene_id or "").strip()
    if scene:
        return f"{mode}::{scene}"
    if mode:
        return f"{mode}::"
    return "default::"


def resolve_sources(scene_key: str) -> tuple[str, str]:
    """Return ``(cover_title_source, cover_subtitle_source)`` for a scene.

    Honors a saved per-scene override for each role; falls back to the built-in
    defaults (document first H1 for the title, document context for the
    subtitle) that reproduce the pre-mapping behavior.
    """
    title_src = _load_role_source(scene_key, "cover_title")
    subtitle_src = _load_role_source(scene_key, "cover_subtitle")
    if not title_src and not subtitle_src:
        return _DEFAULT_SOURCES[0]
    default_title, default_subtitle = _DEFAULT_SOURCES[0]
    return (
        title_src if title_src else default_title,
        subtitle_src if subtitle_src else default_subtitle,
    )


# --------------------------------------------------------------------------
# Material field recognition
# --------------------------------------------------------------------------

# Ordered alias sets used to recognise the two canonical material fields when
# the mapping points at "project"/"company".  Kept as tuples so lookup is fast.
PROJECT_FIELD_KEYS = (
    "project_name",
    "项目名称",
    "entity_name",
    "项目名",
    "project",
    "project_title",
)
COMPANY_FIELD_KEYS = (
    "company_name",
    "公司名称",
    "公司名",
    "企业名称",
    "单位名称",
    "company",
)

# Canonical names surfaced in the config UI.
PROJECT_ROLE_LABEL = "项目/工程名"
COMPANY_ROLE_LABEL = "单位/公司名"


def canonical_field_for(key: str) -> str:
    """Return ``project``/``company``/``""`` for a raw material field key.

    Used so a saved override can refer to the *role* (project / company) rather
    than one brittle alias spelling; the actual value is then looked up through
    the alias set regardless of which alias the material package happened to
    use.
    """
    lowered = str(key or "").strip()
    if lowered in PROJECT_FIELD_KEYS:
        return "project"
    if lowered in COMPANY_FIELD_KEYS:
        return "company"
    return ""


def look_up_field(values: Mapping[str, object], field_key: str) -> str:
    """Return the first non-placeholder value under ``field_key`` in ``values``.

    ``field_key`` may be a concrete key or the role ``project``/``company``; a
    role scans its whole alias set so packages that name the field differently
    still resolve.  Placeholder tokens (``{{@text:...}}``) are ignored.
    """
    token_marker = "{{@text:"
    role = canonical_field_for(field_key)
    wanted = role or str(field_key or "").strip()

    def _candidate_matches(candidate_key: str) -> bool:
        candidate = str(candidate_key or "").strip()
        if role == "project":
            return candidate in PROJECT_FIELD_KEYS
        if role == "company":
            return candidate in COMPANY_FIELD_KEYS
        return candidate == wanted

    for key, raw in values.items():
        text = str(raw or "").strip()
        if not text or token_marker in text or ("{{" in text and "}}" in text):
            continue
        if _candidate_matches(str(key)):
            return text
    return ""



