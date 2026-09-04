"""
ChangeTracker — 修改记录器

每个模块通过 tracker.record() 记录执行的每一次修改，
最终汇入报告和 PipelineResult.failed_items。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChangeRecord:
    """单条修改记录。"""

    rule_name: str              # 模块 name
    target: str                 # 修改目标描述
    section: str                # 所属节 / 区域
    change_type: str            # "format" | "insert" | "delete" | "skip" | "error" | ...
    before: str = ""            # 修改前值（摘要）
    after: str = ""             # 修改后值（摘要）
    paragraph_index: int = -1   # 段落索引，-1 表示全局
    success: bool = True
    failure_reason: str | None = None


class ChangeTracker:
    """收集管线执行过程中的全部修改记录。"""

    def __init__(self) -> None:
        self._records: list[ChangeRecord] = []

    def record(
        self,
        *,
        rule_name: str,
        target: str,
        section: str,
        change_type: str,
        before: str = "",
        after: str = "",
        paragraph_index: int = -1,
        success: bool = True,
        failure_reason: str | None = None,
    ) -> None:
        self._records.append(
            ChangeRecord(
                rule_name=rule_name,
                target=target,
                section=section,
                change_type=change_type,
                before=before,
                after=after,
                paragraph_index=paragraph_index,
                success=success,
                failure_reason=failure_reason,
            )
        )

    def get_all(self) -> list[ChangeRecord]:
        return list(self._records)

    def get_failures(self) -> list[ChangeRecord]:
        return [r for r in self._records if not r.success]

    def get_by_module(self, module_name: str) -> list[ChangeRecord]:
        return [r for r in self._records if r.rule_name == module_name]

    @property
    def total_count(self) -> int:
        return len(self._records)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self._records if not r.success)
