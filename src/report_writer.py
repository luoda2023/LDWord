"""
report_writer — 排版报告生成

将 PipelineResult 输出为 JSON 和 Markdown 报告。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.pipeline.result import PipelineResult


def write_json_report(
    result: PipelineResult,
    *,
    input_path: Path,
    output_path: Path,
    report_path: Path,
    elapsed: float,
    modules_enabled: int,
    modules_total: int,
) -> None:
    """写入 JSON 变更报告。"""
    changes = _extract_changes(result)
    report_data = {
        "input": str(input_path),
        "output": str(output_path),
        "status": result.status,
        "elapsed_seconds": round(elapsed, 2),
        "modules_enabled": modules_enabled,
        "modules_total": modules_total,
        "changes": changes,
        "failed_items": result.failed_items or [],
    }
    report_path.write_text(
        json.dumps(report_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_markdown_report(
    result: PipelineResult,
    *,
    input_path: Path,
    report_path: Path,
    elapsed: float,
    modules_enabled: int,
    modules_total: int,
) -> None:
    """写入 Markdown 变更报告。"""
    changes = _extract_changes(result)
    lines = [
        f"# 排版报告 — {input_path.name}",
        "",
        f"- 状态: **{result.status}**",
        f"- 耗时: {elapsed:.2f}s",
        f"- 模块: {modules_enabled}/{modules_total} 启用",
        "",
    ]

    if result.failed_items:
        lines.append(f"## ⚠️ 非关键失败 ({len(result.failed_items)})")
        lines.append("")
        for item in result.failed_items:
            lines.append(f"- **{item.get('rule_name', '?')}**: {item.get('reason', '?')}")
        lines.append("")

    lines.append(f"## 变更记录 ({len(changes)} 项)")
    lines.append("")
    for c in changes[:50]:
        if isinstance(c, dict):
            lines.append(
                f"- [{c.get('rule_name', '?')}] {c.get('target', '')} "
                f"→ {c.get('after', '')}"
            )
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def _extract_changes(result: PipelineResult) -> list[dict]:
    """从 tracker 提取变更记录。"""
    if not result.tracker:
        return []
    return [
        {
            "rule_name": r.rule_name,
            "target": r.target,
            "section": r.section,
            "change_type": r.change_type,
            "before": r.before,
            "after": r.after,
            "paragraph_index": r.paragraph_index,
            "success": r.success,
        }
        for r in result.tracker.get_all()
    ]
