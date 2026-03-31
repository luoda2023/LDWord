from dataclasses import dataclass, field


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
    scene_label: str = "未绑定场景"
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
class ExecutionResultState:
    status: str = "idle"
    summary: str = "尚未执行"
    error_text: str = ""
    output_path: str = ""
    report_paths: list[str] = field(default_factory=list)
    failed_count: int = 0


@dataclass(slots=True)
class RecentRunState:
    status: str = "idle"
    title: str = "最近结果"
    summary: str = "暂无最近结果"
    output_label: str = ""
    report_label: str = ""
    error_summary: str = ""
