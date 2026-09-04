"""Presentation helpers for assistant runtime result side channels."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def format_evidence_payload(
    summary: Mapping[str, object],
    *,
    notices: Sequence[str] = (),
) -> dict[str, object]:
    """Project DOCX format evidence into the interaction-card payload."""

    digest = str(summary.get("sha256") or "")
    return {
        "facts": [
            {
                "label": "样稿",
                "value": str(summary.get("name") or "DOCX 标准样稿"),
            },
            {
                "label": "分节",
                "value": str(int(summary.get("section_count") or 0)),
            },
            {
                "label": "段落样式",
                "value": str(int(summary.get("paragraph_style_count") or 0)),
            },
            {
                "label": "表格",
                "value": str(int(summary.get("table_count") or 0)),
            },
            {
                "label": "编号段落",
                "value": str(int(summary.get("numbered_paragraph_count") or 0)),
            },
            {
                "label": "文件指纹",
                "value": f"{digest[:12]}…" if digest else "未生成",
            },
        ],
        "notices": list(notices),
        "actions": [],
    }


__all__ = ["format_evidence_payload"]
