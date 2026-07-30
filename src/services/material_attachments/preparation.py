"""Batch preparation projection for Token-aware attachment packages.

The workbench edits canonical profile fields and timeline plans.  This module
only derives a report from those facts; it never stores a second UI status or
attachment-local field value.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from src.config.asset_resolution import resolve_profile_assets
from src.config.attachment_materials import AttachmentBinding
from src.config.entity import EntityProfile
from src.config.materials import is_supported_image_path
from src.shared.engine.material_timeline import (
    resolve_timeline_plans,
    timeline_output_field_keys,
)
from src.services.material_attachments.requirements import (
    AttachmentRequirementReport,
    AttachmentRequirementKind,
    AttachmentRequirementOwner,
    AttachmentRequirementProjection,
    AttachmentRequirementState,
    project_attachment_token_requirements,
    scan_attachment_token_requirements,
)


@dataclass(frozen=True, slots=True)
class AttachmentProfileRequirement:
    """One requirement projected against one canonical profile."""

    profile_id: str
    profile_name: str
    resource_key: str
    owner: AttachmentRequirementOwner
    value: str
    state: AttachmentRequirementState
    declared: bool = False


@dataclass(frozen=True, slots=True)
class AttachmentPreparationRequirement:
    """One unique Token aggregated across every profile in scope."""

    token: str
    kind: AttachmentRequirementKind
    namespace: str
    identifier: str
    owner: AttachmentRequirementOwner
    state: AttachmentRequirementState
    source: str
    status: str
    occurrence_count: int
    relative_paths: tuple[str, ...]
    profiles: tuple[AttachmentProfileRequirement, ...]
    issue_code: str = ""

    @property
    def resolved_profile_count(self) -> int:
        return sum(
            item.state is AttachmentRequirementState.RESOLVED
            for item in self.profiles
        )

    @property
    def missing_profile_count(self) -> int:
        return sum(
            item.state is not AttachmentRequirementState.RESOLVED
            for item in self.profiles
        )

    @property
    def declared_profile_count(self) -> int:
        return sum(item.declared for item in self.profiles)

    @property
    def is_ready(self) -> bool:
        return bool(self.profiles) and not self.missing_profile_count

    @property
    def is_mapped(self) -> bool:
        return bool(self.profiles) and self.declared_profile_count == len(self.profiles)

    @property
    def resource_keys(self) -> tuple[str, ...]:
        return tuple(item.resource_key for item in self.profiles)


@dataclass(frozen=True, slots=True)
class AttachmentPreparationReport:
    """Stable workbench projection for one attachment binding."""

    binding_revision: str
    docx_count: int
    profile_count: int
    requirements: tuple[AttachmentPreparationRequirement, ...]
    source_file_count: int = 0
    unreadable_paths: tuple[str, ...] = ()

    @property
    def token_count(self) -> int:
        return len(self.requirements)

    @property
    def occurrence_count(self) -> int:
        return sum(item.occurrence_count for item in self.requirements)

    @property
    def resolved_requirement_count(self) -> int:
        return sum(item.is_ready for item in self.requirements)

    @property
    def mapped_requirement_count(self) -> int:
        return sum(item.is_mapped for item in self.requirements)

    @property
    def pending_requirements(self) -> tuple[AttachmentPreparationRequirement, ...]:
        return tuple(item for item in self.requirements if not item.is_ready)

    @property
    def direct_pending_requirements(
        self,
    ) -> tuple[AttachmentPreparationRequirement, ...]:
        return tuple(
            item
            for item in self.pending_requirements
            if item.owner is AttachmentRequirementOwner.FIELD
        )

    @property
    def timeline_pending_requirements(
        self,
    ) -> tuple[AttachmentPreparationRequirement, ...]:
        return tuple(
            item
            for item in self.pending_requirements
            if item.owner is AttachmentRequirementOwner.TIMELINE
        )

    @property
    def issue_requirements(self) -> tuple[AttachmentPreparationRequirement, ...]:
        return tuple(
            item
            for item in self.pending_requirements
            if item.owner
            in {
                AttachmentRequirementOwner.IMAGE,
                AttachmentRequirementOwner.ISSUE,
                AttachmentRequirementOwner.CONFLICT,
            }
        )

    @property
    def ready_profile_count(self) -> int:
        if not self.profile_count:
            return 0
        ready = 0
        for profile_index in range(self.profile_count):
            if all(
                profile_index < len(requirement.profiles)
                and requirement.profiles[profile_index].state
                is AttachmentRequirementState.RESOLVED
                for requirement in self.requirements
            ):
                ready += 1
        return ready

    @property
    def is_ready(self) -> bool:
        return (
            bool(self.profile_count)
            and self.ready_profile_count == self.profile_count
            and not self.unreadable_paths
        )


def build_attachment_preparation_report(
    binding: AttachmentBinding,
    profiles: Sequence[EntityProfile],
    *,
    requirement_report: AttachmentRequirementReport | None = None,
    image_token_bindings: Mapping[str, str] | None = None,
) -> AttachmentPreparationReport:
    """Project one scanned package against all profile values and rules."""

    scanned = requirement_report or scan_attachment_token_requirements(binding)
    profile_list = tuple(profiles)
    rows_by_profile: list[dict[str, AttachmentRequirementProjection]] = []
    declared_by_profile: list[set[str]] = []

    for profile in profile_list:
        timeline_keys = set(timeline_output_field_keys(profile.timeline_plans))
        timeline_resolution = resolve_timeline_plans(
            profile.fields,
            profile.timeline_plans,
        )
        resolved_fields = {
            **dict(profile.fields),
            **dict(timeline_resolution.values),
        }
        declared = {
            str(key or "").strip()
            for key in (
                *profile.fields.keys(),
                *profile.declared_field_keys,
            )
            if str(key or "").strip()
        }
        image_bindings = _profile_image_token_bindings(
            profile,
            image_token_bindings or {},
        )
        image_values, available_image_roles = _profile_image_values(profile)
        projected = project_attachment_token_requirements(
            scanned,
            field_values=resolved_fields,
            field_aliases=profile.field_aliases,
            available_field_keys=declared,
            timeline_field_keys=timeline_keys,
            image_token_bindings=image_bindings,
            image_values=image_values,
            available_image_roles=available_image_roles,
            processing_enabled=binding.processing_mode.value == "substitute_copy",
        )
        rows_by_profile.append(
            {row.token: row for row in projected}
        )
        declared_by_profile.append(declared)

    requirements: list[AttachmentPreparationRequirement] = []
    for scanned_requirement in scanned.requirements:
        projected_profiles: list[AttachmentProfileRequirement] = []
        kind = scanned_requirement.kind
        for index, profile in enumerate(profile_list):
            row = rows_by_profile[index][scanned_requirement.token]
            row_resource_key = str(row.resource_key or "").strip()
            is_timeline = row.owner is AttachmentRequirementOwner.TIMELINE
            if kind is AttachmentRequirementKind.IMAGE:
                # Image mapping is package-wide rather than profile-owned.  A
                # configured role is structurally mapped even while its image
                # value is still empty; readiness remains derived from state.
                is_declared = bool(row_resource_key)
            else:
                is_declared = (
                    is_timeline
                    or row_resource_key in declared_by_profile[index]
                )
            projected_profiles.append(
                AttachmentProfileRequirement(
                    profile_id=str(profile.profile_id or ""),
                    profile_name=str(profile.profile_name or f"第 {index + 1} 份"),
                    resource_key=row_resource_key,
                    owner=row.owner,
                    value=row.value,
                    state=row.state,
                    declared=is_declared,
                )
            )

        namespace = scanned_requirement.namespace
        profile_owners = {item.owner for item in projected_profiles}
        if len(profile_owners) > 1:
            owner = AttachmentRequirementOwner.CONFLICT
            source = "映射冲突"
        elif profile_owners:
            owner = next(iter(profile_owners))
            source = _owner_source(owner)
        else:
            owner = AttachmentRequirementOwner.ISSUE
            source = "未选择数据"

        states = tuple(item.state for item in projected_profiles)
        state = (
            AttachmentRequirementState.ERROR
            if owner is AttachmentRequirementOwner.CONFLICT
            else _aggregate_requirement_state(states)
        )
        status = _aggregate_requirement_status(
            state,
            resolved=sum(
                item is AttachmentRequirementState.RESOLVED for item in states
            ),
            total=len(states),
            owner=owner,
        )
        requirements.append(
            AttachmentPreparationRequirement(
                token=scanned_requirement.token,
                kind=kind,
                namespace=namespace,
                identifier=scanned_requirement.identifier,
                owner=owner,
                state=state,
                source=source,
                status=status,
                occurrence_count=scanned_requirement.occurrence_count,
                relative_paths=scanned_requirement.relative_paths,
                profiles=tuple(projected_profiles),
                issue_code=(
                    "profile_requirement_owner_conflict"
                    if owner is AttachmentRequirementOwner.CONFLICT
                    else scanned_requirement.issue_code
                ),
            )
        )

    return AttachmentPreparationReport(
        binding_revision=binding.binding_revision,
        docx_count=scanned.docx_count,
        profile_count=len(profile_list),
        requirements=tuple(requirements),
        source_file_count=len(tuple(binding.items)),
        unreadable_paths=scanned.unreadable_paths,
    )


def _aggregate_requirement_state(
    states: Sequence[AttachmentRequirementState],
) -> AttachmentRequirementState:
    if not states:
        return AttachmentRequirementState.MISSING
    if all(state is AttachmentRequirementState.RESOLVED for state in states):
        return AttachmentRequirementState.RESOLVED
    if any(state is AttachmentRequirementState.ERROR for state in states):
        return AttachmentRequirementState.ERROR
    if any(state is AttachmentRequirementState.DISABLED for state in states):
        return AttachmentRequirementState.DISABLED
    if any(state is AttachmentRequirementState.RESOLVED for state in states):
        return AttachmentRequirementState.PARTIAL
    if any(state is AttachmentRequirementState.UNCONFIGURED for state in states):
        return AttachmentRequirementState.UNCONFIGURED
    if any(state is AttachmentRequirementState.EMPTY for state in states):
        return AttachmentRequirementState.EMPTY
    return AttachmentRequirementState.MISSING


def _aggregate_requirement_status(
    state: AttachmentRequirementState,
    *,
    resolved: int,
    total: int,
    owner: AttachmentRequirementOwner,
) -> str:
    if owner is AttachmentRequirementOwner.CONFLICT:
        return "不同数据的资料归属不一致"
    if state is AttachmentRequirementState.RESOLVED:
        return "已就绪"
    if state is AttachmentRequirementState.PARTIAL:
        return f"{max(0, total - resolved)} 条待填写"
    if state is AttachmentRequirementState.UNCONFIGURED:
        return "时间计划未就绪"
    if state is AttachmentRequirementState.EMPTY:
        if owner is AttachmentRequirementOwner.IMAGE:
            return f"{total} 条待选择图片"
        return f"{total} 条待填写"
    if state is AttachmentRequirementState.MISSING:
        if owner is AttachmentRequirementOwner.IMAGE:
            return "图片 Token 未配置"
        return "字段未创建"
    if state is AttachmentRequirementState.DISABLED:
        return "未启用同步"
    return "需要修复源文件"


def _owner_source(owner: AttachmentRequirementOwner) -> str:
    return {
        AttachmentRequirementOwner.FIELD: "直接字段",
        AttachmentRequirementOwner.TIMELINE: "时间计划",
        AttachmentRequirementOwner.IMAGE: "图片资料",
        AttachmentRequirementOwner.ISSUE: "源文件",
        AttachmentRequirementOwner.CONFLICT: "映射冲突",
    }[owner]


def _profile_image_token_bindings(
    profile: EntityProfile,
    base_bindings: Mapping[str, str],
) -> dict[str, str]:
    bindings = dict(base_bindings)
    for rule in profile.image_material_rules.values():
        token = str(getattr(rule, "anchor_token", "") or "").strip()
        role = str(getattr(rule, "source_role", "") or "").strip()
        if token and role:
            bindings[token] = role
    return bindings


def _profile_image_values(
    profile: EntityProfile,
) -> tuple[dict[str, str], tuple[str, ...]]:
    values: dict[str, str] = {}
    for item in resolve_profile_assets(profile).items:
        role = str(getattr(item, "role", "") or "").strip()
        path = str(getattr(item, "path", "") or "").strip()
        if role and path and is_supported_image_path(path):
            values.setdefault(role, Path(path).name)
    return values, tuple(values)


__all__ = [
    "AttachmentPreparationReport",
    "AttachmentPreparationRequirement",
    "AttachmentProfileRequirement",
    "build_attachment_preparation_report",
]
