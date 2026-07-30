"""Shared Workbench issue data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MaterialReadinessIssueGroups:
    """Structured material readiness issues for Workbench pre-execution UI."""

    schema_ids: tuple[str, ...] = ()
    incompatible_schema_ids: tuple[str, ...] = ()
    field_keys: tuple[str, ...] = ()
    asset_roles: tuple[str, ...] = ()
    source_notes: tuple[str, ...] = ()
    recommendation_schema_id: str = ""
    recommendation_reasons: tuple[str, ...] = ()

    @property
    def has_issues(self) -> bool:
        return bool(
            self.schema_ids
            or self.incompatible_schema_ids
            or self.field_keys
            or self.asset_roles
        )

    def to_reasons(self) -> list[str]:
        reasons: list[str] = []
        if self.schema_ids:
            reasons.append("资料 Schema 未注册：" + ", ".join(self.schema_ids))
        if self.incompatible_schema_ids:
            reasons.append(
                "资料包 Schema 与当前方案不兼容："
                + ", ".join(self.incompatible_schema_ids)
            )
        if self.field_keys:
            reasons.append("资料字段缺失：" + ", ".join(self.field_keys))
        if self.asset_roles:
            reasons.append("资料资产缺失：" + ", ".join(self.asset_roles))
        return reasons

    def detail_lines(self) -> list[str]:
        lines: list[str] = []
        if self.schema_ids:
            lines.append("Schema：未注册 " + ", ".join(self.schema_ids))
        if self.incompatible_schema_ids:
            lines.append(
                "Schema：资料包不兼容 "
                + ", ".join(self.incompatible_schema_ids)
            )
        if self.field_keys:
            lines.append("字段：" + ", ".join(self.field_keys))
        if self.asset_roles:
            lines.append("资产：" + ", ".join(self.asset_roles))
        if self.recommendation_schema_id:
            recommendation = "推荐替换：" + self.recommendation_schema_id
            if self.recommendation_reasons:
                recommendation += "（" + "; ".join(self.recommendation_reasons) + "）"
            lines.append(recommendation)
        for note in self.source_notes:
            lines.append("来源：" + note)
        return lines


@dataclass(frozen=True, slots=True)
class WorkbenchIssueItem:
    """One structured issue for Workbench pre-execution problem lists."""

    issue_id: str
    category: str
    severity: str
    title: str
    summary: str
    details: tuple[str, ...] = ()
    source_notes: tuple[str, ...] = ()
    repair_target_type: str = ""
    repair_target_key: str = ""
    repair_context: tuple[tuple[str, str], ...] = ()
    blocking: bool = False
    status: str = "open"
    owner: str = ""

    def tooltip_lines(self) -> list[str]:
        lines = [f"{self.title}：{self.summary}" if self.summary else self.title]
        lines.extend(self.details)
        for note in self.source_notes:
            lines.append("来源：" + note)
        return [line for line in lines if str(line or "").strip()]


@dataclass(frozen=True, slots=True)
class WorkbenchIssueActionVisualProjection:
    """Stable UI projection for a Workbench issue action group."""

    group: str = "view_only"
    label: str = "仅查看"
    rank: int = 2
    badge_tone: str = "neutral"
    detail_tone: str = "neutral"


@dataclass(frozen=True, slots=True)
class WorkbenchIssueEvidenceLineProjection:
    """Stable readable projection for one Workbench issue evidence line."""

    kind: str
    label: str
    text: str
    action_type: str = ""
    action_value: str = ""
    action_label: str = ""
    tone: str = "neutral"

    def has_action(self) -> bool:
        return bool(self.action_type and self.action_value)

    def display_text(self) -> str:
        if self.text:
            return f"{self.label}：{self.text}"
        return self.label


ISSUE_TERMINAL_STATUS_VALUES: tuple[str, ...] = ("resolved", "ignored")
ISSUE_ACTION_GROUP_VALUES: tuple[str, ...] = (
    "handle_first",
    "confirm",
    "view_only",
)
