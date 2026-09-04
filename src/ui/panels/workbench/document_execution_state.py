from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Literal

from src.application.materials import MaterialPreviewSnapshot
from src.domain.materials import MaterialRunSelection

from .document_input_manifest import DocumentInputManifest

SourceRequirement = Literal["required", "optional", "generated"]
TopologyKind = Literal["single", "files", "records", "mapping_required"]
ReadinessKind = Literal["empty", "ready", "blocked"]


@dataclass(frozen=True, slots=True)
class SceneBinding:
    scene_id: str = ""
    scene: Any = None


@dataclass(frozen=True, slots=True)
class TemplateBinding:
    template_id: str = ""
    template: Any = None


@dataclass(frozen=True, slots=True)
class OutputPolicy:
    custom_root: str = ""
    preserve_source_structure: bool = True


@dataclass(frozen=True, slots=True)
class DocumentExecutionState:
    status: str = "idle"
    progress_current: int = 0
    progress_total: int = 0
    stage_text: str = ""


@dataclass(frozen=True, slots=True)
class DocumentExecutionSnapshot:
    """Authority snapshot for one document-execution workspace.

    Mutable domain values are cloned on construction so mode projections cannot
    accidentally edit Bridge-owned state or another mode's cached state.
    """

    input_manifest: DocumentInputManifest = field(
        default_factory=DocumentInputManifest
    )
    material_selection: MaterialRunSelection | None = None
    material_preview: MaterialPreviewSnapshot | None = None
    scene_binding: SceneBinding = field(default_factory=SceneBinding)
    template_binding: TemplateBinding = field(default_factory=TemplateBinding)
    source_requirement: SourceRequirement = "required"
    output_policy: OutputPolicy = field(default_factory=OutputPolicy)
    execution_state: DocumentExecutionState = field(
        default_factory=DocumentExecutionState
    )

    @classmethod
    def capture(
        cls,
        *,
        input_manifest: DocumentInputManifest | None = None,
        material_selection: MaterialRunSelection | None = None,
        material_preview: MaterialPreviewSnapshot | None = None,
        scene_binding: SceneBinding | None = None,
        template_binding: TemplateBinding | None = None,
        source_requirement: SourceRequirement = "required",
        output_policy: OutputPolicy | None = None,
        execution_state: DocumentExecutionState | None = None,
    ) -> DocumentExecutionSnapshot:
        return cls(
            input_manifest=input_manifest or DocumentInputManifest(),
            material_selection=(
                material_selection
                if isinstance(material_selection, MaterialRunSelection)
                else None
            ),
            material_preview=(
                material_preview
                if isinstance(material_preview, MaterialPreviewSnapshot)
                else None
            ),
            scene_binding=copy.deepcopy(scene_binding or SceneBinding()),
            template_binding=copy.deepcopy(
                template_binding or TemplateBinding()
            ),
            source_requirement=normalize_source_requirement(
                source_requirement
            ),
            output_policy=copy.deepcopy(output_policy or OutputPolicy()),
            execution_state=copy.deepcopy(
                execution_state or DocumentExecutionState()
            ),
        )


@dataclass(frozen=True, slots=True)
class DocumentExecutionTopology:
    """Resolved execution shape; this is system state, not a user mode."""

    kind: TopologyKind
    document_count: int
    record_count: int
    expected_output_count: int
    summary: str
    source_requirement: SourceRequirement = "required"
    blocking_reason: str = ""

    @property
    def blocked(self) -> bool:
        return bool(self.blocking_reason)


@dataclass(frozen=True, slots=True)
class DocumentExecutionReadiness:
    state: ReadinessKind
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def can_execute(self) -> bool:
        return self.state == "ready" and not self.blockers


@dataclass(frozen=True, slots=True)
class DocumentExecutionPresentation:
    topology_text: str
    badge_text: str
    badge_variant: str
    action_text: str
    action_enabled: bool
    issue_text: str = ""


def normalize_source_requirement(value: object) -> SourceRequirement:
    normalized = str(value or "").strip().casefold()
    if normalized in {"required", "optional", "generated"}:
        return normalized  # type: ignore[return-value]
    return "required"


def _unique_value_count(values) -> int:
    return len(
        {
            str(value or "").strip().casefold()
            for value in values
            if str(value or "").strip()
        }
    )


def resolve_document_execution_topology(
    *,
    document_paths=(),
    record_ids=(),
    source_requirement: SourceRequirement = "required",
) -> DocumentExecutionTopology:
    requirement = normalize_source_requirement(source_requirement)
    document_count = _unique_value_count(document_paths)
    record_count = _unique_value_count(record_ids)

    if document_count > 1 and record_count > 1:
        return DocumentExecutionTopology(
            kind="mapping_required",
            document_count=document_count,
            record_count=record_count,
            expected_output_count=0,
            summary=(
                f"已识别 {document_count} 份文档和 {record_count} 条资料记录；"
                "尚未建立唯一映射"
            ),
            source_requirement=requirement,
            blocking_reason=(
                "多文档与批次资料不能静默组合。请保留一份共用文档，"
                "或清除批次资料后按文件执行。系统不会猜测映射关系。"
            ),
        )

    if record_count > 1:
        if document_count == 1:
            source_label = "1 份共用底稿"
        elif requirement == "generated":
            source_label = "无需底稿"
        elif requirement == "optional":
            source_label = "未使用共用底稿"
        else:
            source_label = "缺少共用底稿"
        return DocumentExecutionTopology(
            kind="records",
            document_count=document_count,
            record_count=record_count,
            expected_output_count=record_count,
            summary=(
                f"按资料生成：{source_label} × {record_count} 条记录"
                f" → 预计生成 {record_count} 份"
            ),
            source_requirement=requirement,
        )

    if document_count > 1:
        return DocumentExecutionTopology(
            kind="files",
            document_count=document_count,
            record_count=0,
            expected_output_count=document_count,
            summary=(
                f"多文档执行：{document_count} 份文档共享当前资料"
                f" → 预计生成 {document_count} 份"
            ),
            source_requirement=requirement,
        )

    if record_count == 1:
        source_label = (
            "1 份文档 × 当前资料"
            if document_count == 1
            else (
                "当前资料（无需底稿）"
                if requirement == "generated"
                else (
                    "当前资料（未使用底稿）"
                    if requirement == "optional"
                    else "当前资料（缺少底稿）"
                )
            )
        )
        return DocumentExecutionTopology(
            kind="single",
            document_count=document_count,
            record_count=1,
            expected_output_count=1,
            summary=f"单份执行：{source_label} → 预计生成 1 份",
            source_requirement=requirement,
        )

    if document_count == 1:
        return DocumentExecutionTopology(
            kind="single",
            document_count=1,
            record_count=0,
            expected_output_count=1,
            summary="单份执行：1 份文档 → 预计生成 1 份",
            source_requirement=requirement,
        )

    return DocumentExecutionTopology(
        kind="single",
        document_count=0,
        record_count=0,
        expected_output_count=0,
        summary="",
        source_requirement=requirement,
    )


def inspect_document_execution_readiness(
    topology: DocumentExecutionTopology,
    *,
    input_issues: tuple[str, ...] = (),
    input_truncated: bool = False,
    domain_blockers: tuple[str, ...] = (),
    domain_warnings: tuple[str, ...] = (),
) -> DocumentExecutionReadiness:
    blockers: list[str] = []
    warnings = [
        str(issue)
        for issue in (*input_issues, *domain_warnings)
        if str(issue).strip()
    ]

    if topology.kind == "mapping_required":
        blockers.append(topology.blocking_reason)
    elif topology.kind == "records":
        if (
            topology.source_requirement == "required"
            and topology.document_count != 1
        ):
            blockers.append("当前方案需要一份共用底稿，请先在上方选择文档")
    elif topology.kind == "files":
        if topology.document_count < 2:
            blockers.append("多文档执行至少需要两份可读取文档")
    elif topology.kind == "single" and topology.document_count == 0:
        if topology.record_count == 0:
            return DocumentExecutionReadiness(
                state="empty",
                warnings=tuple(warnings),
            )
        if topology.source_requirement == "required":
            blockers.append("当前方案需要底稿，请先在上方选择文档")

    blockers.extend(
        str(reason)
        for reason in domain_blockers
        if str(reason).strip()
    )
    if input_truncated:
        blockers.append("输入超过单次处理上限，请缩小文件夹范围")

    return DocumentExecutionReadiness(
        state="blocked" if blockers else "ready",
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def present_document_execution(
    topology: DocumentExecutionTopology,
    readiness: DocumentExecutionReadiness,
) -> DocumentExecutionPresentation:
    if readiness.state == "empty":
        return DocumentExecutionPresentation(
            topology_text="",
            badge_text="",
            badge_variant="neutral",
            action_text="生成文档",
            action_enabled=False,
        )
    if not readiness.can_execute:
        issue_text = "；".join(readiness.blockers)
        return DocumentExecutionPresentation(
            topology_text=topology.summary,
            badge_text="需处理",
            badge_variant="warning",
            action_text="生成文档",
            action_enabled=False,
            issue_text=issue_text,
        )
    action_by_kind = {
        "single": "生成文档",
        "files": f"执行 {topology.document_count} 份文档",
        "records": f"生成 {topology.expected_output_count} 份",
    }
    warning_text = "；".join(readiness.warnings)
    return DocumentExecutionPresentation(
        topology_text=topology.summary,
        badge_text=(
            "需确认"
            if warning_text
            else {
                "single": "单份",
                "files": "多文档",
                "records": "按资料",
            }.get(topology.kind, "")
        ),
        badge_variant="warning" if warning_text else "info",
        action_text=action_by_kind.get(topology.kind, "开始执行"),
        action_enabled=True,
        issue_text=warning_text,
    )


__all__ = [
    "DocumentExecutionPresentation",
    "DocumentExecutionReadiness",
    "DocumentExecutionSnapshot",
    "DocumentExecutionState",
    "DocumentExecutionTopology",
    "OutputPolicy",
    "SceneBinding",
    "SourceRequirement",
    "TemplateBinding",
    "inspect_document_execution_readiness",
    "normalize_source_requirement",
    "present_document_execution",
    "resolve_document_execution_topology",
]
