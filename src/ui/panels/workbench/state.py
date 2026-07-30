from dataclasses import dataclass, field


from src.shared.ui.style_presentation_envelope import StylePresentationEnvelope


@dataclass(slots=True)
class CurrentTaskState:
    document_label: str = "未选择文档"
    strategy_label: str = "未选择策略"
    ready: bool = False
    status_text: str = "待执行"


@dataclass(slots=True)
class StrategySummaryState:
    name: str = "未命名策略"
    source_type: str = "default"
    template_label: str = "未绑定模板"
    scene_label: str = "未绑定方案"
    strict_mode: bool = True
    enabled_module_count: int = 0


@dataclass(slots=True)
class FeatureCardState:
    feature_id: str
    title: str
    enabled: bool = False
    subtitle: str = ""
    badge_text: str = ""
    badge_variant: str = "neutral"


@dataclass(slots=True)
class WorkbenchHomeState:
    selected_card_id: str = "quick_execute"
    enabled_features: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ReadinessState:
    ready: bool = False
    label: str = "待执行"
    reasons: list[str] = field(default_factory=lambda: ["未选择文档", "未选择策略"])


@dataclass(slots=True)
class ExecutionProgressState:
    stage_text: str = "等待执行"
    current_step: int = 0
    total_steps: int = 0
    percent: int = 0


@dataclass(slots=True)
class ArtifactItemState:
    kind: str = ""
    label: str = ""
    group_id: str = ""
    group_label: str = ""
    path: str = ""
    fragment: str = ""
    status: str = "available"
    detail: str = ""


@dataclass(slots=True)
class ExecutionResultState:
    status: str = "idle"
    summary: str = "尚未执行"
    error_text: str = ""
    # Owned JSON/plain-data snapshot. Mutable typed fields below are isolated
    # projections and must never alias this canonical terminal evidence tree.
    terminal_payload: dict[str, object] = field(default_factory=dict)
    execution_session: dict[str, object] = field(default_factory=dict)
    style_source: dict[str, object] = field(default_factory=dict)
    style_source_summary: str = ""
    style_source_envelope: StylePresentationEnvelope = field(
        default_factory=StylePresentationEnvelope
    )
    output_path: str = ""
    output_paths: dict[str, str] = field(default_factory=dict)
    compare_paths: dict[str, str] = field(default_factory=dict)
    report_paths: list[str] = field(default_factory=list)
    intermediate_paths: dict[str, str] = field(default_factory=dict)
    material_manifest_paths: dict[str, str] = field(default_factory=dict)
    material_package_paths: dict[str, str] = field(default_factory=dict)
    material_package_receipt: dict[str, object] = field(default_factory=dict)
    material_package_receipts: dict[str, object] = field(default_factory=dict)
    attachment_bundles: dict[str, object] = field(default_factory=dict)
    attachment_bundle_summary: str = ""
    material_dependency_usage: dict[str, object] = field(default_factory=dict)
    material_dependency_summary: str = ""
    scene_sample_manifest_paths: dict[str, str] = field(default_factory=dict)
    failed_count: int = 0
    artifact_failure_count: int = 0
    diagnostics_count: int = 0
    diagnostics_summary: str = ""
    object_preflight: dict[str, object] = field(default_factory=dict)
    object_preflight_summary: str = ""
    object_preflight_details: list[str] = field(default_factory=list)
    material_field_consistency: dict[str, object] = field(default_factory=dict)
    material_field_consistency_summary: str = ""
    batch_isolation: dict[str, object] = field(default_factory=dict)
    batch_isolation_summary: str = ""
    batch_isolation_details: list[str] = field(default_factory=list)
    question_figure_repair_queue: dict[str, object] = field(default_factory=dict)
    artifact_items: list[ArtifactItemState] = field(default_factory=list)
    issue_items: list[object] = field(default_factory=list)


@dataclass(slots=True)
class RecentRunState:
    status: str = "idle"
    title: str = "最近结果"
    summary: str = "暂无最近结果"
    # Independent copy of the result state's canonical terminal evidence.
    terminal_payload: dict[str, object] = field(default_factory=dict)
    execution_session: dict[str, object] = field(default_factory=dict)
    style_source: dict[str, object] = field(default_factory=dict)
    style_source_summary: str = ""
    style_source_envelope: StylePresentationEnvelope = field(
        default_factory=StylePresentationEnvelope
    )
    output_label: str = ""
    compare_label: str = ""
    report_label: str = ""
    intermediate_label: str = ""
    material_manifest_label: str = ""
    material_package_label: str = ""
    attachment_bundles: dict[str, object] = field(default_factory=dict)
    attachment_bundle_summary: str = ""
    material_dependency_usage: dict[str, object] = field(default_factory=dict)
    material_dependency_summary: str = ""
    scene_sample_manifest_label: str = ""
    artifact_label: str = ""
    artifact_items: list[ArtifactItemState] = field(default_factory=list)
    error_summary: str = ""
    diagnostics_count: int = 0
    diagnostics_summary: str = ""
    object_preflight: dict[str, object] = field(default_factory=dict)
    object_preflight_summary: str = ""
    object_preflight_details: list[str] = field(default_factory=list)
    material_field_consistency: dict[str, object] = field(default_factory=dict)
    material_field_consistency_summary: str = ""
    batch_isolation: dict[str, object] = field(default_factory=dict)
    batch_isolation_summary: str = ""
    batch_isolation_details: list[str] = field(default_factory=list)
    question_figure_repair_queue: dict[str, object] = field(default_factory=dict)


def effective_style_source_envelope(
    envelope: StylePresentationEnvelope | object | None,
    summary: str = "",
) -> StylePresentationEnvelope:
    presentation = StylePresentationEnvelope.from_object(
        envelope,
        kind="execution_receipt",
    )
    if presentation.receipt_summary(title_fallback="样式来源"):
        return presentation
    return StylePresentationEnvelope.from_summary(
        summary,
        kind="execution_receipt",
        title="样式来源",
    )
