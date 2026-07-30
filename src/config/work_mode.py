"""Top-level work mode registry.

Work modes are product entry points. They select the visible domain for scenes,
masters, material schemas, and default navigation, but they do not replace
``SceneWorkspace`` or ``TemplateConfig``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


WorkModeStatus = Literal["active", "deprecated", "hidden"]


@dataclass(frozen=True, slots=True)
class WorkModeSpec:
    """One top-level document workflow mode."""

    mode_id: str
    label: str
    description: str
    default_scene_id: str
    default_template_id: str
    display_order: int = 0
    status: WorkModeStatus = "active"
    template_authoring_profile_id: str | None = None
    default_master_id: str = ""
    master_domain: str = ""
    master_family_ids: tuple[str, ...] = ()
    material_schema_ids: tuple[str, ...] = ()
    visible_panels: tuple[str, ...] = (
        "workbench",
        "scene",
        "template",
        "assets",
    )
    default_entry_panel: str = "workbench"
    aliases: tuple[str, ...] = ()


DEFAULT_WORK_MODE_ID = "custom"
_SCENE_ID_WORK_MODE_OVERRIDES: dict[str, str] = {
    "exam_quiz": "exam",
    "exam_teaching": "exam",
    "exam_term": "exam",
}

_WORK_MODES: tuple[WorkModeSpec, ...] = (
    WorkModeSpec(
        mode_id="custom",
        label="通用版",
        description="通用文档处理入口，保留现有默认方案行为。",
        default_scene_id="custom",
        default_template_id="default",
        display_order=10,
        template_authoring_profile_id="template_authoring.custom.v1",
        master_domain="general_master",
        master_family_ids=("general",),
        aliases=("default", "general"),
    ),
    WorkModeSpec(
        mode_id="exam",
        label="试卷版",
        description="试题内容装配为学生卷、答案速查等试卷交付版本。",
        default_scene_id="exam",
        default_template_id="default",
        display_order=20,
        template_authoring_profile_id="template_authoring.exam.v1",
        default_master_id="default_exam",
        master_domain="exam_blank_master",
        master_family_ids=("exam",),
        material_schema_ids=("exam_items_v1",),
        aliases=("exam_paper", "paper", "试卷"),
    ),
    WorkModeSpec(
        mode_id="thesis",
        label="论文版",
        description="中文学位论文、课程论文、综述和开题等论文排版入口。",
        default_scene_id="thesis",
        default_template_id="thesis_gbt",
        display_order=30,
        template_authoring_profile_id="template_authoring.thesis.v1",
        master_domain="thesis_master",
        master_family_ids=("thesis",),
        aliases=("paper_thesis", "论文"),
    ),
    WorkModeSpec(
        mode_id="bidding",
        label="标书版",
        description="工程投标、政府采购和商务投标文档装配入口。",
        default_scene_id="bidding",
        default_template_id="bid_engineering",
        display_order=40,
        template_authoring_profile_id="template_authoring.bidding.v1",
        master_domain="bidding_master",
        master_family_ids=("bidding",),
        material_schema_ids=("bid_materials_v1",),
        aliases=("bid", "tender", "标书"),
    ),
    WorkModeSpec(
        mode_id="official",
        label="公文版",
        description="通知、请示、报告、批复、函、纪要等公文装配入口。",
        default_scene_id="official",
        default_template_id="official_gbt",
        display_order=50,
        template_authoring_profile_id="template_authoring.official.v1",
        master_domain="official_master",
        master_family_ids=("official",),
        material_schema_ids=("official_document_v1", "administrative_meeting_fields_v1"),
        aliases=("official_document", "公文"),
    ),
    WorkModeSpec(
        mode_id="technical",
        label="技术文档版",
        description="技术规范、操作手册和设计文档处理入口。",
        default_scene_id="technical",
        default_template_id="tech_standard",
        display_order=60,
        template_authoring_profile_id="template_authoring.technical.v1",
        master_domain="technical_master",
        master_family_ids=("technical",),
        material_schema_ids=("technical_document_v1",),
        aliases=("tech", "技术文档"),
    ),
    WorkModeSpec(
        mode_id="report",
        label="报告版",
        description="汇报、总结和调研报告处理入口。",
        default_scene_id="report",
        default_template_id="report_default",
        display_order=70,
        template_authoring_profile_id="template_authoring.report.v1",
        master_domain="report_master",
        master_family_ids=("report",),
        aliases=("general_report", "报告"),
    ),
)

def list_work_modes(
    *,
    include_inactive: bool = False,
) -> tuple[WorkModeSpec, ...]:
    """Return active modes by default, in display order."""

    return tuple(
        mode
        for mode in sorted(
            _WORK_MODES,
            key=lambda item: (item.display_order, item.mode_id),
        )
        if include_inactive or mode.status == "active"
    )


def list_template_authoring_work_modes(
    *,
    include_inactive: bool = False,
) -> tuple[WorkModeSpec, ...]:
    """Return modes that explicitly opt into AI template authoring.

    Mode count is product data, not a schema invariant.  Inactive modes keep
    their durable identity and data, but are excluded from new workbench
    creation and inbox monitoring unless a migration explicitly requests them.
    """

    return tuple(
        mode
        for mode in list_work_modes(include_inactive=include_inactive)
        if mode.template_authoring_profile_id
    )


def get_work_mode(mode_id: str) -> WorkModeSpec | None:
    """Return a work mode by id, label, or alias."""

    key = str(mode_id or "").strip()
    if not key:
        return None
    normalized = key.casefold()
    for mode in _WORK_MODES:
        if normalized in {
            alias.casefold()
            for alias in (mode.mode_id, mode.label, *mode.aliases)
        }:
            return mode
    return None


def default_work_mode() -> WorkModeSpec:
    """Return the configured default work mode or fail closed."""

    configured = next(
        (mode for mode in _WORK_MODES if mode.mode_id == DEFAULT_WORK_MODE_ID),
        None,
    )
    if configured is None:
        raise RuntimeError(
            f"default work mode is not registered: {DEFAULT_WORK_MODE_ID}"
        )
    if configured.status != "active":
        raise RuntimeError(
            f"default work mode is not active: {DEFAULT_WORK_MODE_ID}"
        )
    return configured


def work_mode_for_scene_id(scene_id: str) -> WorkModeSpec:
    """Resolve the work mode that owns a scene id, falling back to custom."""

    target = str(scene_id or "").strip()
    override = _SCENE_ID_WORK_MODE_OVERRIDES.get(target)
    if override:
        resolved = get_work_mode(override)
        if resolved is not None:
            return resolved
    for mode in _WORK_MODES:
        if mode.default_scene_id == target or mode.mode_id == target:
            return mode
    return default_work_mode()


def resolve_work_mode_id(
    scene: object | None = None,
    *,
    requested_mode_id: object = "",
) -> str:
    """Normalize one UI/input mode without consulting scene/category aliases."""

    for candidate in (
        requested_mode_id,
        getattr(scene, "mode_id", "") if scene is not None else "",
    ):
        raw_mode = str(candidate or "").strip()
        if not raw_mode:
            continue
        registered = get_work_mode(raw_mode)
        return registered.mode_id if registered is not None else raw_mode.casefold()

    return default_work_mode().mode_id


def resolve_execution_work_mode_id(
    scene: object | None,
    *,
    requested_mode_id: object = "",
) -> str:
    """Return the mode used to capture an invalid-or-valid execution graph.

    The persisted scene field owns execution identity. Caller input is used only
    when the field is absent so validation can return a precise missing-mode
    issue without performing a cross-mode lookup.
    """

    scene_mode = str(
        getattr(scene, "mode_id", "") if scene is not None else ""
    ).strip()
    raw_mode = scene_mode or str(requested_mode_id or "").strip()
    registered = get_work_mode(raw_mode)
    return registered.mode_id if registered is not None else raw_mode.casefold()


def execution_work_mode_issue(
    scene: object | None,
    *,
    requested_mode_id: object = "",
) -> str:
    """Return a fail-closed issue for missing, aliased, or conflicting modes."""

    scene_mode = str(
        getattr(scene, "mode_id", "") if scene is not None else ""
    ).strip()
    if not scene_mode:
        return "execution_mode_missing:scene.mode_id"
    scene_spec = get_work_mode(scene_mode)
    if scene_spec is None:
        return f"execution_mode_unknown:scene.mode_id:{scene_mode.casefold()}"
    if scene_mode != scene_spec.mode_id:
        return (
            "execution_mode_not_canonical:scene.mode_id:"
            f"{scene_mode}:{scene_spec.mode_id}"
        )
    if scene_spec.status != "active":
        return f"execution_mode_inactive:scene.mode_id:{scene_spec.mode_id}"

    requested_mode = str(requested_mode_id or "").strip()
    if not requested_mode:
        return ""
    requested_spec = get_work_mode(requested_mode)
    if requested_spec is None:
        return f"execution_mode_unknown:requested_mode_id:{requested_mode.casefold()}"
    if requested_mode != requested_spec.mode_id:
        return (
            "execution_mode_not_canonical:requested_mode_id:"
            f"{requested_mode}:{requested_spec.mode_id}"
        )
    if requested_spec.status != "active":
        return f"execution_mode_inactive:requested_mode_id:{requested_spec.mode_id}"
    if requested_spec.mode_id != scene_spec.mode_id:
        return (
            "execution_mode_conflict:"
            f"scene.mode_id={scene_spec.mode_id}:"
            f"requested_mode_id={requested_spec.mode_id}"
        )
    return ""


__all__ = [
    "DEFAULT_WORK_MODE_ID",
    "WorkModeSpec",
    "WorkModeStatus",
    "default_work_mode",
    "execution_work_mode_issue",
    "get_work_mode",
    "list_template_authoring_work_modes",
    "list_work_modes",
    "resolve_work_mode_id",
    "resolve_execution_work_mode_id",
    "work_mode_for_scene_id",
]
