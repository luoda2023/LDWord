"""
Lark-Formatter V1.0 — 管线模块基类与元数据定义

每个管线模块继承 BaseModule 并声明 ModuleMeta，
Pipeline 调度器依据 meta 自动排序、校验、执行。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker

    from docx import Document


@dataclass(frozen=True)
class ModuleMeta:
    """模块元数据声明（不可变）。

    Pipeline 调度器读取此结构来完成：
    - 拓扑排序（depends_on / soft_after）
    - 上下文校验（consumes / provides）
    - 增量执行（requires_config）
    - 结构保护（modifies_structure）
    """

    # ── 身份 ──────────────────────────────────────────
    name: str                           # 技术 ID, e.g. "heading_numbering"
    description: str                    # 用户可见名, e.g. "标题编号"
    category: str                       # 分类: basic / structure / table /
                                        #       fill / insert / special / validate

    # ── 依赖 ──────────────────────────────────────────
    depends_on: tuple[str, ...] = ()    # 硬依赖：必须先执行的模块 name
    soft_after: tuple[str, ...] = ()    # 软依赖：建议先执行，缺失不报错

    # ── 数据流 ────────────────────────────────────────
    consumes: tuple[str, ...] = ()      # 从 PipelineContext 读取的 key
    provides: tuple[str, ...] = ()      # 写入 PipelineContext 的 key

    # ── 配置 ──────────────────────────────────────────
    requires_config: tuple[str, ...] = ()   # 依赖的 ResolvedConfig 段名
                                            # 增量执行用：配置段变化 → 标记脏

    # ── 行为 ──────────────────────────────────────────
    modifies_structure: bool = False    # 是否会增删段落（触发索引失效通知）
    enabled_by_default: bool = False    # 模块默认启用状态（单一事实来源）


@dataclass
class Issue:
    """校验问题条目。"""

    level: str          # "error" | "warning" | "info"
    module_name: str    # 产生问题的模块 name
    message: str
    location: str = ""  # 可选：段落索引 / 节名


class BaseModule(ABC):
    """所有管线模块的抽象基类。

    子类**必须**：
    1. 定义类属性 ``meta: ModuleMeta``
    2. 实现 ``apply()``

    子类**可选**覆写：
    - ``validate()``       执行前的前置校验
    - ``estimate_impact()`` 预估影响范围（用于 UI 预览）
    """

    meta: ModuleMeta  # 子类必须声明

    @abstractmethod
    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        """执行模块逻辑，直接修改 doc 对象。

        - 通过 tracker.record() 记录每次修改
        - 通过 context 读取前置模块产出 / 写入本模块产出
        - 异常会被 Pipeline 捕获并记录为失败项
        """
        ...

    def validate(
        self,
        doc: Document,
        config: ResolvedConfig,
        context: PipelineContext,
    ) -> list[Issue]:
        """执行前的前置校验（可选）。

        返回空列表表示无问题。Pipeline **不会**因为 warning 阻止执行。
        """
        return []

    def estimate_impact(
        self,
        doc: Document,
        config: ResolvedConfig,
    ) -> dict[str, int]:
        """预估影响范围（可选）。

        返回示例: {"paragraphs": 42, "tables": 3}
        用于 UI 执行前预览。
        """
        return {}
